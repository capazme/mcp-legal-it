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
from src.tool_annotations import CACHE_WRITES, READ_ONLY, WRITES_FILES, annotations_for

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


def test_the_provenance_gate_is_not_vacuous(tmp_path):
    """Every table a tool reads must be declared, or its vintage stays hidden.

    Checked on a copy of the source tree, sabotaged in both directions: a
    dropped `@sourced` (the answer would lose the provenance line) and an
    invented one (the answer would claim a table it never opens).
    """
    import shutil

    src = tmp_path / "src"
    shutil.copytree(REPO / "plugin/server/src", src, ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import (  # type: ignore[import-not-found]
            Audit,
            verify_provenance,
        )
    finally:
        sys.path.pop(0)

    varie = src / "tools" / "varie.py"
    text = varie.read_text(encoding="utf-8")
    assert '@sourced("comuni")' in text
    varie.write_text(
        text.replace('@sourced("comuni")\ndef codice_fiscale(', "def codice_fiscale(", 1),
        encoding="utf-8",
    )
    problems = verify_provenance(Audit(src))
    assert any("codice_fiscale reads comuni" in problem for problem in problems), problems

    redditi = src / "tools" / "dichiarazione_redditi.py"
    text = redditi.read_text(encoding="utf-8")
    redditi.write_text(
        text.replace("@sourced(", '@sourced("tegm")\n@sourced(', 1), encoding="utf-8"
    )
    problems = verify_provenance(Audit(src))
    assert any("never reads" in problem for problem in problems), problems


def test_a_table_nobody_reads_is_a_failure(tmp_path):
    """A shipped table applied by no tool is either dead data or a missed load.

    Sabotage: point a loader at a name the repository does not ship. The file is
    then applied by nobody, which is exactly how `codici_tributo`,
    `modelli_atti` and `preavviso_ccnl` were invisible while three tools were
    answering from them.
    """
    import shutil

    from audit_tool_annotations import (  # type: ignore[import-not-found]
        Audit,
        verify_provenance,
    )

    src = tmp_path / "src"
    shutil.copytree(
        REPO / "plugin/server/src", src, ignore=shutil.ignore_patterns("__pycache__")
    )
    redditi = src / "tools" / "dichiarazione_redditi.py"
    text = redditi.read_text(encoding="utf-8")
    assert '"codici_tributo.json"' in text
    redditi.write_text(
        text.replace('"codici_tributo.json"', '"codici_tributo_archivio.json"', 1),
        encoding="utf-8",
    )
    problems = verify_provenance(Audit(src))
    assert any(
        "codici_tributo.json is applied by no tool" in problem for problem in problems
    ), problems


def test_a_lib_helper_missing_from_the_policy_is_a_failure(monkeypatch, tmp_path):
    """A `src/lib` module the policy does not know becomes an "external service".

    Sabotage: add a plain helper to `src/lib`, which is how the ledger's own
    `_tables_open` arrived. `upstream_clients` then reported it as an upstream
    client for every tool that imported it -- 71 read-only calculations moved to
    the report's "external" column and its open-world count went from 50 to 121,
    while every annotation stayed correct, because `openWorldHint` reads the call
    graph instead and never saw the module as a client. Two readers of one tree
    disagreed and nothing failed.
    """
    import shutil

    import audit_tool_annotations as audit_module  # type: ignore[import-not-found]
    from audit_tool_annotations import (  # type: ignore[import-not-found]
        Audit,
        verify_lib_modules,
    )

    src = tmp_path / "src"
    shutil.copytree(
        REPO / "plugin/server/src", src, ignore=shutil.ignore_patterns("__pycache__")
    )
    assert verify_lib_modules(Audit(src)) == [], "the real tree is already undeclared"

    (src / "lib" / "_nuovo_helper.py").write_text("VALORE = 1\n", encoding="utf-8")
    problems = verify_lib_modules(Audit(src))
    assert any("_nuovo_helper.py" in p for p in problems), problems
    assert any("upstream service" in p for p in problems), problems

    # The other direction: a client is a package and cannot be declared local.
    monkeypatch.setattr(
        audit_module,
        "LOCAL_LIB_MODULES",
        set(audit_module.LOCAL_LIB_MODULES) | {"brocardi"},
    )
    problems = verify_lib_modules(Audit(src))
    assert any("client package" in p for p in problems), problems


def test_import_preloaded_tables_reach_the_tool_that_reads_them():
    """The three loader shapes a bare `X = json.load(f)` rule used to miss.

    `_CODICI_TRIBUTO` binds through a subscript, `_CATALOGO` through a dict
    comprehension, `_PREAVVISO` through an annotated assignment. Each is read at
    import and answers for a tool that, before this, carried no provenance at
    all.
    """
    audit = _audit()
    expected = {
        "cerca_codice_tributo": "codici_tributo",
        "genera_modello_atto": "modelli_atti",
        "lista_categorie_atti": "modelli_atti",
        "indennita_preavviso": "preavviso_ccnl",
        "costo_lavoro": "irpef_scaglioni",
        "ravvedimento_operoso": "tassi_legali",
    }
    for tool, dataset in expected.items():
        fq = next(f for f, name in audit.tools.items() if name == tool)
        assert dataset in audit.datasets(fq), tool
        assert dataset in audit.declared(fq), tool


def test_a_hand_kept_copy_of_a_table_is_a_failure(tmp_path):
    """A literal that restates a shipped table is invisible to every other check.

    The tool reads no file, so it declares no provenance and the golden
    reference never sees the table move -- while the copy drifts from the table
    it was taken from. The two shapes below are the ones that actually happened:
    the contributo unificato bands kept as a list of two-tuples (from a table
    that stores them as dicts) and a series pasted as a plain list.
    """
    import json as _json
    import shutil

    from audit_tool_annotations import (  # type: ignore[import-not-found]
        Audit,
        verify_table_copies,
    )

    src = tmp_path / "src"
    shutil.copytree(
        REPO / "plugin/server/src", src, ignore=shutil.ignore_patterns("__pycache__")
    )
    assert verify_table_copies(Audit(src)) == [], "the tree already contains a copy"

    varie = src / "tools" / "varie.py"
    original = varie.read_text(encoding="utf-8")
    varie.write_text(
        original
        + "\n_CONTRIBUTO_COPIATO = [\n"
        "    (1_100, 43), (5_200, 98), (26_000, 237), (52_000, 518),\n"
        "    (260_000, 759), (520_000, 1_214), (float(\"inf\"), 1_686),\n"
        "]\n",
        encoding="utf-8",
    )
    problems = verify_table_copies(Audit(src))
    assert any("restates src/data/contributo_unificato.json" in p for p in problems), problems

    series = _json.loads((src / "data" / "indici_foi.json").read_text(encoding="utf-8"))["indici"]
    year = list(series.values())[-1]
    varie.write_text(
        original + "\n_FOI_COPIATO = %r\n" % (list(year.values()),), encoding="utf-8"
    )
    problems = verify_table_copies(Audit(src))
    assert any("restates src/data/indici_foi.json" in p for p in problems), problems

    # An exemption that no longer matches anything is a failure too, so the
    # allow-list cannot outlive the code it excused.
    from audit_tool_annotations import TABLE_COPIES_ALLOWED  # type: ignore[import-not-found]

    assert TABLE_COPIES_ALLOWED == (), "declare exemptions only with a live copy behind them"


def _audit():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    from pathlib import Path

    return Audit(Path(REPO / "plugin/server/src"))


def test_cache_writers_refresh_a_cache_and_nothing_else():
    """Every cache writer must reach a directory resolved from MCP_CACHE_DIR.

    A tool that claims to only refresh the cache but resolves a path some other
    way would write wherever it likes without anyone noticing.
    """
    assert CACHE_WRITES <= WRITES_FILES
    assert not (CACHE_WRITES & READ_ONLY)
    audit = _audit()
    for name in sorted(CACHE_WRITES):
        fq = next(f for f, tool in audit.tools.items() if tool == name)
        assert audit.is_cache_only(fq), name
        documented = audit.cache_sources(fq) or [
            owner
            for owner, item in audit.write_sites(fq)
            if "cache" in item.lower()
        ]
        assert documented, "%s refreshes a cache but never resolves one" % name


def test_document_generators_are_not_cache_writes():
    for name in (
        "esporta_atto_docx",
        "genera_quotazione_docx",
        "genera_procura_liti_docx",
        "genera_report_fornitori",
        "download_law_pdf",
    ):
        assert name in WRITES_FILES
        assert name not in CACHE_WRITES


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
