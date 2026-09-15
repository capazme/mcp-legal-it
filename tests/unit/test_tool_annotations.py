"""Tool annotations: the policy must cover every tool the server registers.

A tool missing from the policy is a silent regression -- hosts that pre-approve
read-only tools would stop offering it -- so the sets are checked against the
live registry rather than against a hand-kept list.
"""

import asyncio

from fastmcp import Client
from src.server import mcp
from src.tool_annotations import READ_ONLY, WRITES_FILES, annotations_for


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


def test_local_calculators_are_not_open_world():
    for name in ("interessi_legali", "calcolo_irpef", "codice_fiscale"):
        annotations = annotations_for(name)
        assert annotations.readOnlyHint is True
        assert annotations.openWorldHint is False
