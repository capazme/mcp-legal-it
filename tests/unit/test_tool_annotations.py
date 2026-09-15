"""Tool annotations: the policy must cover every tool the server registers.

A tool missing from the policy is a silent regression -- hosts that pre-approve
read-only tools would stop offering it -- so the sets are checked against the
live registry rather than against a hand-kept list.
"""

import asyncio
import pathlib
import subprocess
import sys

from fastmcp import Client
from src.server import mcp
from src.tool_annotations import READ_ONLY, WRITES_FILES, annotations_for

REPO = pathlib.Path(__file__).resolve().parents[2]


def _tools():
    async def run():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(run())


def test_policy_covers_every_registered_tool():
    names = {tool.name for tool in _tools()}
    assert names == READ_ONLY | WRITES_FILES
    assert not (READ_ONLY & WRITES_FILES)


def test_every_tool_is_annotated():
    for tool in _tools():
        assert tool.annotations is not None, tool.name
    stamped = {tool.name for tool in _tools() if tool.annotations.readOnlyHint}
    assert stamped == READ_ONLY


def test_document_and_cache_writers_are_not_read_only():
    # The five document generators plus the cache writers: never advertised as
    # side-effect free, or a host would run them without asking.
    for name in (
        "esporta_atto_docx",
        "download_law_pdf",
        "genera_report_fornitori",
        "genera_quotazione_docx",
        "genera_procura_liti_docx",
        "cite_law",
        "cerca_brocardi",
    ):
        assert name in WRITES_FILES
        assert annotations_for(name).readOnlyHint is False


def test_policy_matches_the_audit_script():
    """The committed policy must be what the audit derives from the source."""
    audit = REPO / "scripts" / "audit_tool_annotations.py"
    result = subprocess.run(
        [sys.executable, str(audit), "--check"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_audit_sees_the_write_in_a_document_generator():
    """A tool that builds a .docx must never come back read-only."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    from pathlib import Path

    audit = Audit(Path(REPO / "plugin/server/src"))
    fq = next(name for name, tool in audit.tools.items() if tool == "esporta_atto_docx")
    assert any("ctor Document()" in item for item in audit.writes_for(fq))
    lookup = next(name for name, tool in audit.tools.items() if tool == "interessi_legali")
    assert audit.writes_for(lookup) == []


def test_local_calculators_are_not_open_world():
    for name in ("interessi_legali", "calcolo_irpef", "codice_fiscale"):
        annotations = annotations_for(name)
        assert annotations.readOnlyHint is True
        assert annotations.openWorldHint is False
