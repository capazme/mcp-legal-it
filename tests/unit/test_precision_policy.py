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
#: (`contributo_unificato` was reconciled with the DPR 115/2002 in force on
#: 2026-09-18 and `imposte_successione` with the Agenzia delle Entrate schedule
#: on 2026-09-19; their refusals went away -- which is the mechanism working,
#: not the test breaking.)
UNVERIFIED_TABLE = "comuni"
#: The tool that declares `ESATTO` on it, and must therefore refuse.
REFUSING_TOOL = "codice_fiscale"
#: The tool that declares `INDICATIVO` on a table still unverified.
DOWNGRADED_TOOL = "ricerca_codici_ateco"
#: A table under way at the pinned present, expired a year later.
IN_FORCE = "tassi_legali"

PRESENT = {"LEGAL_TODAY": "2026-09-15", "LEGAL_NOW": "2026-09-15T12:00:00", "TZ": "UTC"}

PRECISION_KEY = "mcp-legal-it/precisione"
#: The tool that can do without `comuni` if the caller brings the catastal code,
#: and the parameter it brings it in.
SUPPLYING_TOOL = "codice_fiscale"
SUPPLYING_PARAM = "codice_catastale"
#: The table that parameter makes unnecessary.
SUPPLIED_TABLE = "comuni"
#: The tool whose table is a contract that gets renewed: no vintage can be right
#: for every case, so the notice period travels in the call.
CCNL_TOOL = "indennita_preavviso"
CCNL_PARAM = "giorni_preavviso"


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


def test_an_acceptance_buys_a_lower_grade_and_never_the_withdrawn_claim():
    """Negotiation, in both directions: what it grants and what it refuses to.

    The claim itself is not for sale. A caller who accepts `INDICATIVO` gets an
    indicative answer; a caller who insists on `ESATTO` is refused *and told* what
    would have worked, so the retry is a decision rather than another guess.
    """
    granted = _precision.decide("ESATTO", ["non_verificata"], accettata="INDICATIVO")
    assert (granted.esito, granted.effettiva) == ("ridotta", "INDICATIVO")
    assert granted.accettata == "INDICATIVO", (
        "the answer says the acceptance is what let it stand"
    )

    stricter = _precision.decide("ESATTO", ["non_verificata"], accettata="STIMATO")
    assert stricter.effettiva == "STIMATO", (
        "being more cautious than the rule requires is always allowed"
    )

    for word in ("ESATTO", "VARIABILE"):
        refused = _precision.decide("ESATTO", ["non_verificata"], accettata=word)
        assert refused.esito == "rifiuta", word
        assert refused.negoziabile is True
        assert refused.concedibile == "INDICATIVO", (
            "a refusal has to name the grade that would have been granted"
        )
        assert refused.accettata == word

    silent = _precision.decide("ESATTO", ["non_verificata"])
    assert silent.concedibile == "INDICATIVO", "the offer is there before it is asked for"

    forever = _precision.decide("STIMATO", ["non_verificata"], accettata="STIMATO")
    assert forever.esito == "ridotta", (
        "a forecast has nothing to trade: accepting it costs nothing and buys the answer"
    )


def test_an_expired_table_under_a_figure_about_today_is_not_negotiable():
    """An acceptance lowers a claim; it cannot make a wrong number right."""
    stale = _precision.decide("ESATTO", ["scaduta"], True, accettata="STIMATO")
    assert stale.esito == "rifiuta"
    assert stale.negoziabile is False, (
        "a rate table that stopped being refreshed cannot compute today's interest "
        "at any grade, so there is nothing to concede"
    )
    assert stale.concedibile is None

    closed = _precision.decide("ESATTO", ["scaduta"], False, accettata="STIMATO")
    assert (closed.esito, closed.effettiva) == ("ridotta", "STIMATO"), (
        "the same table on a closed period is a caveat, and the caller may tighten it"
    )


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
    independent implementations, over all 222 docstrings.
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
    """The tools that show every outcome, called once each, over stdio.

    `codice_fiscale` shows two of them with two argument sets, so it gets two
    calls: bare it refuses, with the catastal code it answers. The results are
    keyed by outcome, not by tool name -- one tool, two stories.
    """
    manifest = {tool["name"]: tool for tool in tools()}
    arguments = {
        name: arguments_for(manifest[name])
        for name in (REFUSING_TOOL, DOWNGRADED_TOOL, CCNL_TOOL)
    }
    arguments[CCNL_TOOL] = {**arguments[CCNL_TOOL], CCNL_PARAM: 60}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="precision-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="precision-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    replies = call_tools(
        env, [REFUSING_TOOL, DOWNGRADED_TOOL, CCNL_TOOL], arguments, timeout=300
    )
    supplied = call_tools(
        env,
        [REFUSING_TOOL],
        {REFUSING_TOOL: {**arguments[REFUSING_TOOL], SUPPLYING_PARAM: "H501"}},
        timeout=300,
    )
    return {
        "refusal": replies[REFUSING_TOOL],
        "supplied": supplied[REFUSING_TOOL],
        "downgraded": replies[DOWNGRADED_TOOL],
        "ccnl": replies[CCNL_TOOL],
    }


def test_an_exact_tool_refuses_over_the_wire_and_a_host_can_see_it(answers):
    """The same fact in the body and in `_meta`, on a real call."""
    reply = answers["refusal"]
    payload, meta = _payload(reply), _meta(reply)
    assert payload.get("errore") == "dati_non_affidabili"
    assert meta.get(PRECISION_KEY, {}).get("effettiva") == "nessuna", (
        "a host that reads only the meta must not think the answer stands"
    )
    assert meta.get(PRECISION_KEY, {}).get("dichiarata") == "ESATTO"
    text = answer_text(reply)
    assert UNVERIFIED_TABLE in text, "the refusal names the table it is about"
    assert "non verificata" in text


def test_the_same_tool_answers_once_the_caller_brings_the_catastal_code(answers):
    """The escape is inside the refusal: one parameter turns it into an answer."""
    reply = answers["supplied"]
    payload, meta = _payload(reply), _meta(reply)
    assert payload.get("codice_fiscale") == "RSSMRA80A01H501U", (
        "the algorithm is exact once the catastal code is an input"
    )
    assert payload["dettaglio"]["catastale_dal_chiamante"] is True
    assert payload["dati_applicati"] == [], (
        "the table was not read, so naming its vintage would claim a source this "
        "answer does not rest on"
    )
    assert _meta(reply).get(PRECISION_KEY) is None, (
        "nothing is unverified in this answer: there is no claim to lower"
    )
    assert _meta(reply).get("mcp-legal-it/data_warnings") is None


def test_every_table_reading_tool_declares_the_negotiation_parameter():
    """Declared in the schema, documented in the description, never required.

    The parameter is added by `sourced`, which means the tool's own docstring is
    what describes it: a docstring shape the injector mishandles would leave a
    parameter a model cannot interpret, and this is the check that notices.
    """
    audit = _audit_module().Audit(pathlib.Path(REPO / "plugin/server/src"))
    readers = sorted(
        name for fq, name in audit.tools.items() if audit.datasets(fq)
    )
    assert len(readers) > 50, "only %d tools read a table" % len(readers)
    schemas = {tool["name"]: tool.get("inputSchema") or {} for tool in tools()}
    problems = {}
    for name in readers:
        schema = schemas.get(name) or {}
        consent = (schema.get("properties") or {}).get(_data.CONSENT_PARAM)
        if consent is None:
            problems[name] = "no %s in its schema" % _data.CONSENT_PARAM
        elif not consent.get("description"):
            problems[name] = "%s is not documented" % _data.CONSENT_PARAM
        elif _data.CONSENT_PARAM in (schema.get("required") or ()):
            problems[name] = "%s is required" % _data.CONSENT_PARAM
    assert not problems, "tools that cannot be negotiated with: %s" % problems


def test_a_supplied_datum_replaces_the_table_instead_of_being_refused(answers):
    """The other escape: the caller brings the datum the table would provide."""
    supplied = answers["supplied"]
    payload = _payload(supplied)
    assert "errore" not in payload, (
        "supplying the datum the table provides must not be refused: %s" % payload.get("errore")
    )
    assert payload["codice_fiscale"] == "RSSMRA80A01H501U", (
        "the algorithm is exact once the catastal code is an input"
    )
    assert payload["dettaglio"]["catastale_dal_chiamante"] is True
    assert payload["dati_applicati"] == [], (
        "the table was not read, so naming its vintage would claim a source this "
        "answer does not rest on"
    )
    assert payload["dati_forniti_dal_chiamante"] == {
        "parametro": SUPPLYING_PARAM,
        "al_posto_di": [SUPPLIED_TABLE],
    }, "the substitution is named, or the reader cannot tell what backs the number"
    assert _meta(supplied).get(PRECISION_KEY) is None, (
        "nothing is unverified in this answer: there is no claim to lower"
    )
    assert _meta(supplied).get("mcp-legal-it/data_warnings") is None, (
        "a host must not be warned about a table the call deliberately did not open"
    )


def test_an_acceptance_over_the_wire_lowers_the_grade_and_says_so(answers):
    """The same tool, the same arguments, one word more: a number instead of a block."""
    manifest = {tool["name"]: tool for tool in tools()}
    assert REFUSING_TOOL in manifest
    arguments = arguments_for(manifest[REFUSING_TOOL])
    arguments[_data.CONSENT_PARAM] = _precision.INDICATIVO
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="consent-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="consent-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    reply = call_tools(env, [REFUSING_TOOL], {REFUSING_TOOL: arguments}, timeout=300)[REFUSING_TOOL]

    payload, meta = _payload(reply), _meta(reply)
    assert "errore" not in payload, "the acceptance did not unlock the calculation"
    assert payload["precisione"]["effettiva"] == _precision.INDICATIVO
    assert payload["precisione"]["accettata"] == _precision.INDICATIVO, (
        "the answer names the acceptance as what let it stand"
    )
    assert meta.get(PRECISION_KEY, {}).get("accettata") == _precision.INDICATIVO, (
        "and a host that reads only the meta is told the same thing"
    )
    assert payload["dati_applicati"], "the table is still named, with its vintage"
    assert payload["avvisi_dati"], (
        "an accepted answer still carries the warning: the acceptance is not amnesia"
    )


def test_the_notice_period_can_come_from_the_contract_in_hand(answers):
    """The table nobody can ever finish sourcing: a CCNL that gets renewed."""
    payload = _payload(answers["ccnl"])
    assert "errore" not in payload
    assert payload["giorni_preavviso"] == 60
    assert payload["giorni_preavviso_fonte"] == "forniti dal chiamante"
    assert payload["importo"] == round(2500.0 / 30 * 60, 2), (
        "the arithmetic is still the tool's; only the days came from outside"
    )


def test_a_downgraded_tool_still_computes_over_the_wire(answers):
    reply = answers["downgraded"]
    payload, meta = _payload(reply), _meta(reply)
    assert "errore" not in payload, "an indicative tool keeps answering"
    assert payload["precisione"]["effettiva"] == "STIMATO"
    assert meta.get(PRECISION_KEY, {}).get("effettiva") == "STIMATO", (
        "the downgrade reaches a host that reads only the meta"
    )
    carried = set(payload) - {"precisione", "dati_applicati", "avvisi_dati"}
    assert carried, "the downgraded answer still carries its computation"
