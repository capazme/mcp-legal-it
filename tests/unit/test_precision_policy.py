"""What an unverified or expired table does to the answer, not just to the footer.

`tests/unit/test_vintage_warnings.py` covers the reporting: which tables a call
applied, and in what state. Reporting a number as possibly stale is not the same
as doing something about it, and this file covers the half that acts -- each tool
declares a grade in its own docstring (`Precisione: ESATTO ...`), and a table that
cannot support that grade changes the answer:

* an **unverified** table is a hole in provenance, so an exact claim is withdrawn
  (the tool refuses and says what would unblock it) while an indicative one steps
  down to `STIMATO` and says so in the body;
* an **expired** table is a hole in coverage: a figure about *today* cannot rest
  on it, while a figure about a period that has already closed can, at the lower
  grade. Whether the call read the clock is the difference, which is why
  `_clock.consulted()` exists.

The states are pinned to shipped tables, so the test fails the day a table gains
a source and the refusal stops happening. A fixture that imitated the states
would keep passing after the real tables were fixed, which is the one thing this
file is meant to prevent.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tempfile
from types import SimpleNamespace

import pytest

from src.lib import _clock, _data, _precision, _tables_open

from .mcp_harness import (
    REPO,
    answer_text,
    arguments_for,
    call_tools,
    server_env,
    tools,
)

#: A table nobody sources: the provenance gap, whichever tool reads it.
UNVERIFIED_TABLE = "contributo_unificato"
#: The tool that declares `ESATTO` on it, and must therefore refuse.
REFUSING_TOOL = "contributo_unificato"
#: The tool that declares `INDICATIVO` on it, and can therefore step down.
DOWNGRADED_TOOL = "preventivo_civile"
#: A table under way at the pinned present, expired a year later.
IN_FORCE = "tassi_legali"

PRESENT = {"LEGAL_TODAY": "2026-09-15", "LEGAL_NOW": "2026-09-15T12:00:00", "TZ": "UTC"}

PRECISION_KEY = "mcp-legal-it/precisione"


def _audit_module():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import audit_tool_annotations  # type: ignore[import-not-found]

        return audit_tool_annotations
    finally:
        sys.path.pop(0)


def _payload(reply: dict) -> dict:
    structured = ((reply or {}).get("result") or {}).get("structuredContent")
    return structured if isinstance(structured, dict) else {}


def _meta(reply: dict) -> dict:
    return (((reply or {}).get("result") or {}).get("_meta")) or {}


def _tool(docstring: str, payload, declared: str):
    """A function with `docstring`, wrapped by `sourced` exactly as a tool is."""

    def tool():
        return payload

    tool.__doc__ = docstring
    return _data.sourced(declared)(tool)


def _answer(wrapped, tables: str, clock_reading: bool = False):
    with _tables_open.recording(), _clock.recording(), _precision.recording():
        _tables_open.note(tables)
        if clock_reading:
            _clock.today()
        return wrapped()


def test_the_grade_comes_from_the_docstring_the_model_reads():
    """The claim lives where the caller reads it; the runtime parses that line."""
    declared = _tool(
        "Fa qualcosa.\n    Precisione: ESATTO per indici FOI (tabella x).\n    Args:\n        a: b\n",
        {"totale": 1},
        "festivita",
    ).__precisione_dichiarata__

    assert isinstance(declared, _precision.Dichiarata)
    assert declared.grado == _precision.ESATTO
    assert declared.qualificatore == "per indici FOI (tabella x)."

    silent = _tool("Fa qualcosa.", {"totale": 1}, "festivita")
    assert silent.__precisione_dichiarata__ is None, "no line, no claim"


def test_an_unverified_table_withdraws_an_exact_claim_and_downgrades_an_indicative_one():
    """The two outcomes the request asks for, from the same state."""
    exact = _precision.decide("ESATTO", ["non_verificata"])
    assert (exact.esito, exact.effettiva) == ("rifiuta", "nessuna"), (
        "nobody vouched for the table: the figure it would produce is not asserted"
    )

    downgraded = _precision.decide("INDICATIVO", ["non_verificata"])
    assert (downgraded.esito, downgraded.effettiva) == ("ridotta", "STIMATO"), (
        "an indicative answer can still be given as a forecast"
    )
    assert _precision.decide("STIMATO", ["non_verificata"]).esito == "rifiuta", (
        "a forecast has no grade left to fall back on"
    )

    # A word the module does not know is read as the strongest claim, so a typo
    # cannot quietly buy leniency.
    assert _precision.decide("VARIABILE", ["non_verificata"]).esito == "rifiuta"


def test_an_expired_table_bites_only_when_the_answer_is_anchored_to_today():
    """Coverage is not provenance: a closed period stays answerable."""
    anchored = _precision.decide("ESATTO", ["scaduta"], ancorata_al_presente=True)
    assert (anchored.esito, anchored.effettiva) == ("rifiuta", "nessuna"), (
        "a figure about today computed on an expired table is a figure that lies"
    )
    closed = _precision.decide("ESATTO", ["scaduta"], ancorata_al_presente=False)
    assert (closed.esito, closed.effettiva) == ("ridotta", "INDICATIVO"), (
        "the number is right for its period; only the claim has to fall"
    )
    assert _precision.decide("STIMATO", ["scaduta"], False).esito == "rifiuta"
    assert _precision.decide("ESATTO", [], False).esito == "piena", "nothing flagged"


def test_the_refusal_has_no_figure_and_says_what_would_unblock_it():
    """A refusal is an answer: what is wrong, about which table, and the way out."""
    body = _tool(
        "Calcola il contributo.\n    Precisione: ESATTO (scaglioni per valore).\n",
        {"contributo": 1234.0},
        UNVERIFIED_TABLE,
    )
    with _tables_open.recording(), _clock.recording(), _precision.recording():
        _tables_open.note(UNVERIFIED_TABLE)
        out = body()
        esito = _precision.current()

    assert out["errore"] == "dati_non_affidabili"
    assert "contributo" not in out, "a refusal that still hands over the number is not one"
    assert out["precisione"]["dichiarata"] == "ESATTO"
    assert out["precisione"]["effettiva"] == "nessuna"
    assert out["tabelle"][0]["tabella"] == UNVERIFIED_TABLE
    assert out["avvisi_dati"] == out["tabelle"], (
        "a refusal is the strongest form of the warning, not a second vocabulary"
    )
    assert UNVERIFIED_TABLE + ".json" in out["come_sbloccare"], (
        "a refusal has to say which file would make it computable"
    )
    assert "ESATTO" in out["messaggio"], "the claim being withdrawn is named"
    assert esito is not None and esito.esito == "rifiuta", (
        "the outcome is recorded for the meta, the only channel a string answer has"
    )


def test_a_downgraded_answer_keeps_its_numbers_and_declares_the_lower_grade():
    """Reducing precision is not refusing: what stands is said to stand."""
    body = _tool(
        "Preventivo.\n    Precisione: INDICATIVO per i compensi (tabella contributo).\n",
        {"totale": 1234.0, "voci": ["a"]},
        UNVERIFIED_TABLE,
    )
    with _tables_open.recording(), _clock.recording(), _precision.recording():
        _tables_open.note(UNVERIFIED_TABLE)
        out = body()
        esito = _precision.current()

    assert out["totale"] == 1234.0, "a downgrade must not lose the computation"
    assert out["precisione"]["dichiarata"] == "INDICATIVO"
    assert out["precisione"]["effettiva"] == "STIMATO"
    assert out["precisione"]["nota"] == "per i compensi (tabella contributo).", (
        "the reader learns which claim was reduced"
    )
    assert esito is not None and esito.effettiva == "STIMATO"


def test_a_table_expired_under_a_call_that_read_the_clock_stops_it(monkeypatch):
    """The clock is what makes the difference, and it is observed, not guessed."""
    monkeypatch.setenv("LEGAL_TODAY", "2027-06-01")
    monkeypatch.setenv("LEGAL_NOW", "2027-06-01T12:00:00")
    body = _tool(
        "Interessi.\n    Precisione: ESATTO per tassi legali storici.\n",
        {"interessi": 100.0},
        IN_FORCE,
    )

    closed = _answer(body, IN_FORCE)
    to_present = _answer(body, IN_FORCE, clock_reading=True)

    assert closed["precisione"]["effettiva"] == "INDICATIVO", (
        "same table, same date: the call that never asked the clock keeps answering"
    )
    assert closed["interessi"] == 100.0
    assert to_present["errore"] == "dati_non_affidabili", (
        "asking the clock is what turns an expired table into a refusal"
    )
    assert to_present["tabelle"][0]["stato"] == "scaduta", (
        "the structured state keeps the machine word a client matches on"
    )
    assert "periodo coperto" in to_present["messaggio"], (
        "the sentence a model reads says what the state means"
    )


def test_the_audit_and_the_runtime_read_the_same_line_the_same_way():
    """Two readers of one docstring: a disagreement would bless an unread claim.

    The audit decides whether a tool may answer from a table; the wrapper decides
    what happens when it does. Both parse the `Precisione:` line, with two
    independent implementations, over all 221 docstrings.
    """
    module = _audit_module()
    audit = module.Audit(pathlib.Path(REPO / "plugin/server/src"))
    assert module.runtime_grades() == list(_precision.GRADI), (
        "the audit and src/lib/_precision.py disagree on the vocabulary"
    )

    disagree = {}
    for fq, name in sorted(audit.tools.items()):
        doc = ast.get_docstring(audit.functions[fq]) or ""
        runtime = _precision.declared(SimpleNamespace(__doc__=doc))
        theirs, ours = module.declared_precision(audit.functions[fq]), (
            runtime.grado if runtime else None
        )
        if theirs != ours:
            disagree[name] = (theirs, ours)
    assert not disagree, "audit and runtime read different grades: %s" % disagree

    applying = {
        name: module.declared_precision(audit.functions[fq])
        for fq, name in audit.tools.items()
        if audit.datasets(fq)
    }
    assert applying, "no tool applies a table: the check is vacuous"
    assert all(applying.values()), (
        "these tools apply a table and declare no grade: %s"
        % sorted(name for name, grade in applying.items() if not grade)
    )
    assert not module.verify_precision(audit), "the audit reports its own surface"


@pytest.fixture(scope="module")
def answers():
    """The two tools that show the two outcomes, called once each, over stdio."""
    manifest = {tool["name"]: tool for tool in tools()}
    names = [REFUSING_TOOL, DOWNGRADED_TOOL]
    arguments = {name: arguments_for(manifest[name]) for name in names}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="precision-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="precision-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    return call_tools(env, names, arguments, timeout=300)


def test_an_exact_tool_refuses_over_the_wire_and_a_host_can_see_it(answers):
    """The same fact in the body and in `_meta`, on a real call."""
    reply = answers[REFUSING_TOOL]
    payload, meta = _payload(reply), _meta(reply)
    assert payload.get("errore") == "dati_non_affidabili"
    assert meta.get(PRECISION_KEY, {}).get("effettiva") == "nessuna", (
        "a host that reads only the meta must not think the answer stands"
    )
    assert meta.get(PRECISION_KEY, {}).get("dichiarata") == "ESATTO"
    text = answer_text(reply)
    assert UNVERIFIED_TABLE in text, "the refusal names the table it is about"
    assert "non verificata" in text


def test_a_downgraded_tool_still_computes_over_the_wire(answers):
    reply = answers[DOWNGRADED_TOOL]
    payload, meta = _payload(reply), _meta(reply)
    assert "errore" not in payload, "an indicative tool keeps answering"
    assert payload["precisione"]["effettiva"] == "STIMATO"
    assert meta.get(PRECISION_KEY, {}).get("effettiva") == "STIMATO", (
        "the downgrade reaches a host that reads only the meta"
    )
    carried = set(payload) - {"precisione", "dati_applicati", "avvisi_dati"}
    assert carried, "the downgraded answer still carries its computation"
