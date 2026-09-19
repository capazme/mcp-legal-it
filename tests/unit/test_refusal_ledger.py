"""The refusal ledger: what the vintage policy blocked, recorded and readable.

Two halves, tested apart:

* the recording (`src/lib/_refusals.py`): opt-in (`LEGAL_REFUSAL_LEDGER=on`),
  one JSONL line under the cache root, best-effort -- off by default, because a
  read-only tool that refuses must not start writing files the host never asked
  for (that is the same discipline as `LEGAL_CACHE`, and for the same reason:
  `test_read_only_contract` fingerprints the filesystem and must stay true);
* the readback (`backlog_riconciliazione`): the same tally, shaped for a caller,
  which re-ranks the static backlog by what actually blocked.

The ledger is exercised over a real server on the wire, with `LEGAL_NOW` pinned:
a file whose timestamp came from anywhere else would not be deterministic, and
the audit already forces every calendar read through `src/lib/_clock.py`.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from src.lib import _refusals

from .mcp_harness import (
    REPO,
    arguments_for,
    call_tools,
    server_env,
    tools,
)

PRESENT = {"LEGAL_TODAY": "2026-09-15", "LEGAL_NOW": "2026-09-15T12:00:00", "TZ": "UTC"}
#: (`imposte_successione` used to be the pin; it was reconciled with the
#: Agenzia delle Entrate schedule on 2026-09-19 and its refusal went away.
#: `comuni` is the strongest refusal left: two tools, and one of them now
#: proves both halves of the ledger in a single wire run -- refuse without the
#: catastal code, answer with it.)
REFUSING_TOOL = "codice_fiscale"
#: `call_tools` fires one call per tool, so one refusal per run here.
CALLS = 1


def _payload(reply: dict) -> dict:
    structured = ((reply or {}).get("result") or {}).get("structuredContent")
    return structured if isinstance(structured, dict) else {}


def _meta(reply: dict) -> dict:
    return (((reply or {}).get("result") or {}).get("_meta")) or {}


def test_the_ledger_is_opt_in_and_silent_by_default(monkeypatch):
    monkeypatch.delenv(_refusals.ENABLE_ENV, raising=False)
    assert _refusals.ledger_enabled() is False
    # Off: recording is a no-op even with the API hit directly.
    _refusals.record({"evento": "rifiuto", "tool": "x"})
    assert not _refusals.ledger_path().exists()

    monkeypatch.setenv(_refusals.ENABLE_ENV, "on")
    assert _refusals.ledger_enabled() is True


def test_a_refusal_and_an_acceptance_land_in_the_ledger_over_the_wire():
    """One JSONL line per blocked call, one per negotiated call, nothing else."""
    manifest = {tool["name"]: tool for tool in tools()}
    arguments = {name: arguments_for(manifest[name]) for name in (REFUSING_TOOL,)}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="ledger-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="ledger-tmp-"))
    env = server_env(
        sandbox,
        scratch,
        extra={
            **PRESENT,
            "LEGAL_CACHE": "off",
            _refusals.ENABLE_ENV: "on",
        },
    )
    call_tools(env, [REFUSING_TOOL], arguments, timeout=300)
    # The same tool, negotiated: the acceptance is the other event the tally
    # exists to count, so the ledger gets both halves from one run.
    accepted = {**arguments[REFUSING_TOOL], "accetta_precisione": "INDICATIVO"}
    call_tools(env, [REFUSING_TOOL], {REFUSING_TOOL: accepted}, timeout=300)

    # The ledger lives where the *server's* env put it, not where this test
    # process would resolve it: the path is read back from the same env dict.
    path = pathlib.Path(env["MCP_CACHE_DIR"]) / _refusals.LEDGER_NAME
    assert path.exists(), "the ledger was on: the refusals had to be recorded"
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rifiuti = [voce for voce in lines if voce["evento"] == "rifiuto"]
    assert len(rifiuti) >= CALLS, lines
    voce = rifiuti[0]
    assert voce["tool"] == REFUSING_TOOL
    assert "comuni" in voce["tables"]
    assert voce["stati"] == ["non_verificata"]
    assert voce["dichiarata"] == "ESATTO"
    assert voce["concedibile"] == "INDICATIVO"
    assert voce["ts"].startswith("2026-09-15T12:00:00"), (
        "the timestamp goes through `_clock`, so a pinned LEGAL_NOW pins the ledger too"
    )
    # The accepted call lands in the same file with its own event: the backlog
    # needs both, or a table whose refusals are always negotiated would look
    # worse than it is.
    accettazioni = [voce for voce in lines if voce["evento"] == "accettazione"]
    assert len(accettazioni) >= CALLS, "the acceptance half of the tally is what keeps it honest"
    assert accettazioni[0]["accettata"] == "INDICATIVO"
    assert accettazioni[0]["dichiarata"] == "ESATTO"


def test_the_backlog_readout_reports_the_ledger_and_reranks():
    manifest = {tool["name"]: tool for tool in tools()}
    arguments = {name: arguments_for(manifest[name]) for name in (REFUSING_TOOL,)}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="backlog-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="backlog-tmp-"))
    env = server_env(
        sandbox,
        scratch,
        extra={
            **PRESENT,
            "LEGAL_CACHE": "off",
            _refusals.ENABLE_ENV: "on",
        },
    )
    replies = call_tools(
        env,
        [REFUSING_TOOL, "backlog_riconciliazione"],
        {**arguments, "backlog_riconciliazione": {}},
        timeout=300,
    )
    payload = _payload(replies["backlog_riconciliazione"])

    assert payload["n_tabelle"] >= 5, "the shipped tables still carry unverified ones"
    assert payload["tabelle"], "the list itself cannot be empty"
    stati = {voce["stato"] for voce in payload["tabelle"]}
    assert stati <= {"non_verificata", "scaduta"}

    # The static half comes from the audit: `imposte_successione` blocks two
    # tools, `comuni` two, and a table with only indicative readers blocks none.
    per_tabella = {voce["tabella"]: voce for voce in payload["tabelle"]}
    assert len(per_tabella["comuni"]["uso_statico"]["rifiutano"]) == 2
    assert per_tabella["preavviso_ccnl"]["uso_statico"]["rifiutano"] == ["indennita_preavviso"]

    # The observed tally names the table the refusals were about, and the
    # ranking says so: observed tables first, ordered by tally.
    verbale = payload["verbale_rifiuti"]
    assert verbale.get("disponibile") is True
    assert verbale.get("rifiuti", {}).get(REFUSING_TOOL) == CALLS
    assert verbale.get("tabelle", {}).get("comuni") == CALLS
    first = payload["tabelle"][0]["tabella"]
    assert first == "comuni", (
        "the table that actually blocked twice outranks the static order"
    )
    # And the action tells the caller what to do without opening any code.
    assert "verifica: manuale" in per_tabella[first]["azione"]


def test_the_backlog_says_so_when_the_ledger_is_off():
    """`disponibile: false` is not an error: silence must be distinguishable."""
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="backlog2-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="backlog2-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    reply = call_tools(env, ["backlog_riconciliazione"], {"backlog_riconciliazione": {}}, timeout=300)
    verbale = _payload(reply["backlog_riconciliazione"])["verbale_rifiuti"]
    assert verbale["disponibile"] is False
    assert "LEGAL_REFUSAL_LEDGER" in verbale["motivo"]


def test_the_readout_names_every_alternative_the_server_declares():
    """The `alternativa` registry and the tools must tell the same story."""
    audit_path = REPO / "plugin/server/src/table_bindings.py"
    namespace: dict = {}
    exec(compile(audit_path.read_text(), str(audit_path), "exec"), namespace)
    alternatives = namespace["TOOL_ALTERNATIVES"]
    assert set(alternatives) >= {
        "codice_fiscale",
        "indennita_preavviso",
        "contributo_unificato",
        "imposte_successione",
        "imposte_compravendita",
        "decurtazione_punti_patente",
        "decodifica_codice_fiscale",
    }, "a blocking table without an escape is a wall, not a negotiation"
    # Reconciled tables keep their escape: the alternative is not a crutch the
    # code drops once the shipped file is verified, it is the permanent contract
    # for whoever brings fresher data than the repo has.
    for name in ("contributo_unificato", "imposte_successione", "decurtazione_punti_patente"):
        assert name in alternatives, "%s lost its escape after the reconciliation" % name


def test_every_blocking_table_has_a_working_escape_over_the_wire():
    """The five alternatives added with the ledger actually deliver answers.

    Each call supplies the datum its table would have provided, so the answer
    must arrive with no refusal, no warning about the table it skipped, and the
    substitution named -- the same contract `codice_fiscale` established.
    """
    manifest = {tool["name"]: tool for tool in tools()}
    suppled = {
        "contributo_unificato": {
            "tabella_contributo_unificato": {
                "civile": {
                    "cognizione": [
                        {"fino_a": 1100, "importo": 50},
                        {"fino_a": 5200, "importo": 100},
                        {"fino_a": 26000, "importo": 250},
                        {"fino_a": 52000, "importo": 500},
                        {"fino_a": 260000, "importo": 700},
                        {"fino_a": 520000, "importo": 1100},
                        {"oltre": True, "importo": 1500},
                    ],
                    "esecuzione_immobiliare": 278,
                    "esecuzione_mobiliare": {"scaglioni": [{"fino_a": 2499.99, "importo": 43}, {"oltre": True, "importo": 139}]},
                    "volontaria_giurisdizione": 98,
                    "separazione_consensuale": 43,
                    "separazione_giudiziale": 98,
                    "divorzio_congiunto": 43,
                    "divorzio_giudiziale": 98,
                    "cautelari": {"riduzione": 0.5},
                },
                "appello": {"moltiplicatore": 1.5},
                "cassazione": {"moltiplicatore": 2.0},
                "lavoro": {"primo_grado": 0, "appello": {"fino_a": 2500, "importo": 0, "fino_a_50000": 112.5, "oltre": 225}},
                "tributario": {"scaglioni": [{"fino_a": 2582.28, "importo": 30}, {"fino_a": 5000, "importo": 60}, {"fino_a": 25000, "importo": 120}, {"fino_a": 75000, "importo": 250}, {"fino_a": 200000, "importo": 500}, {"oltre": True, "importo": 1500}]},
            },
            "valore_causa": 10000,
        },
        "imposte_successione": {
            "aliquote_franchigie": [
                {"parentela": "coniuge_linea_retta", "aliquota": 4, "franchigia": 1000000},
                {"parentela": "altri", "aliquota": 8, "franchigia": 0},
            ],
            "valore_beni": 500000,
            "parentela": "coniuge_linea_retta",
        },
        "imposte_compravendita": {
            "aliquote_registro": {
                "prima_casa": {"registro": 2, "ipotecaria": 0.5, "catastale": 1, "minimo_registro": 1000},
                "seconda_casa": {"registro": 9, "ipotecaria": 2, "catastale": 1, "minimo_registro": 1000},
                "terreno_agricolo": {"registro": 15, "ipotecaria": 2, "catastale": 1},
                "da_costruttore_iva": {"prima_casa": {"iva": 4, "registro": 168, "ipotecaria": 168, "catastale": 168}, "seconda_casa": {"iva": 10, "registro": 168, "ipotecaria": 168, "catastale": 168}, "lusso": {"iva": 22, "registro": 168, "ipotecaria": 168, "catastale": 168}},
            },
            "prezzo": 200000,
            "prima_casa": True,
        },
        "decurtazione_punti_patente": {
            "tabella_violazioni": {
                "sorpasso": {"punti": 3, "articolo": "Art. 148 c.15 CdS", "descrizione": "Sorpasso vietato"},
            },
            "violazione": "sorpasso",
        },
        "decodifica_codice_fiscale": {
            "mappa_comuni": {"ROMA": "H501"},
            "codice_fiscale": "RSSMRA80A01H501U",
        },
    }
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="alt-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="alt-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    replies = call_tools(env, sorted(suppled), suppled, timeout=300)
    for name, arguments in suppled.items():
        payload = _payload(replies[name])
        assert "errore" not in payload, "%s refused with its own data: %s" % (
            name,
            payload.get("errore"),
        )
        assert payload.get("dati_forniti_dal_chiamante"), (
            "%s did not name the substitution" % name
        )
        assert payload.get("dati_applicati") in ([], None) or all(
            "non verificate" not in riga for riga in payload["dati_applicati"]
        ), "%s still reports the vintage of a table it did not read" % name
    # And the supplied values really reached the answers.
    assert _payload(replies["contributo_unificato"])["importo_dovuto"] == 250
    assert _payload(replies["imposte_successione"])["imposta_successione"] == 0.0
    assert _payload(replies["decurtazione_punti_patente"])["punti"] == 3
    assert "ROMA" in _payload(replies["decodifica_codice_fiscale"])["dati"]["comune_nascita"]
