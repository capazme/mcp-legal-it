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
#: Every shipped table is verified or has only indicative readers, so the
#: refusal that feeds the ledger runs on the probe server
#: (`plugin/server/probe_precision.py`), where `sourced` declares ESATTO on a
#: table that ships unverified. History of the pin: `codice_fiscale` (comuni,
#: until the ISTAT reconciliation of 2026-09-20 left no shipped tool refusing).
REFUSING_TOOL = "sonda_rifiuto"
REFUSING_TABLE = "codici_ateco"
#: The probe only registers the refusing tool; the readback runs on the shipped
#: server, which reads the same ledger because both runs share `MCP_CACHE_DIR`.
PROBE_SCRIPT = "plugin/server/probe_precision.py"
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
    arguments = {REFUSING_TOOL: {"keyword": "commercio"}}
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
    call_tools(env, [REFUSING_TOOL], arguments, timeout=300,
               script=PROBE_SCRIPT)
    # The same tool, negotiated: the acceptance is the other event the tally
    # exists to count, so the ledger gets both halves from one run.
    accepted = {**arguments[REFUSING_TOOL], "accetta_precisione": "INDICATIVO"}
    call_tools(env, [REFUSING_TOOL], {REFUSING_TOOL: accepted}, timeout=300,
               script=PROBE_SCRIPT)

    # The ledger lives where the *server's* env put it, not where this test
    # process would resolve it: the path is read back from the same env dict.
    path = pathlib.Path(env["MCP_CACHE_DIR"]) / _refusals.LEDGER_NAME
    assert path.exists(), "the ledger was on: the refusals had to be recorded"
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rifiuti = [voce for voce in lines if voce["evento"] == "rifiuto"]
    assert len(rifiuti) >= CALLS, lines
    voce = rifiuti[0]
    assert voce["tool"] == REFUSING_TOOL
    assert REFUSING_TABLE in voce["tables"]
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
    arguments = {REFUSING_TOOL: {"keyword": "commercio"}}
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
    # The refusal lands in the ledger from the probe run; the readback runs on
    # the shipped server, which shares `MCP_CACHE_DIR` with it.
    call_tools(env, [REFUSING_TOOL], arguments, timeout=300, script=PROBE_SCRIPT)
    replies = call_tools(
        env,
        ["backlog_riconciliazione"],
        {"backlog_riconciliazione": {}},
        timeout=300,
    )
    payload = _payload(replies["backlog_riconciliazione"])

    assert payload["n_tabelle"] >= 2, "the shipped tables still carry unverified ones"
    assert payload["tabelle"], "the list itself cannot be empty"
    stati = {voce["stato"] for voce in payload["tabelle"]}
    assert stati <= {"non_verificata", "scaduta"}

    # The static half comes from the audit: `codici_ateco` and
    # `tribunali_competenti` are the only unverified tables left, and a table
    # whose only readers are indicative blocks none of them.
    per_tabella = {voce["tabella"]: voce for voce in payload["tabelle"]}
    assert set(per_tabella) <= {"codici_ateco", "tribunali_competenti"}, sorted(per_tabella)
    assert all(voce["uso_statico"]["rifiutano"] == [] for voce in per_tabella.values()), (
        "only indicative readers are left: nothing refuses statically"
    )

    # The observed tally names the table the refusals were about, and the
    # ranking says so: observed tables first, ordered by tally.
    verbale = payload["verbale_rifiuti"]
    assert verbale.get("disponibile") is True
    assert verbale.get("rifiuti", {}).get(REFUSING_TOOL) == CALLS
    assert verbale.get("tabelle", {}).get(REFUSING_TABLE) == CALLS
    first = payload["tabelle"][0]["tabella"]
    assert first == REFUSING_TABLE, (
        "the table that actually blocked outranks the static order"
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


def _write_ledger(path: pathlib.Path, voci: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in voci),
        encoding="utf-8",
    )


def test_monthly_rolls_up_by_month_and_compares(monkeypatch, tmp_path):
    """The series: one row per month, zero for silent months, delta vs previous."""
    monkeypatch.setenv(_refusals.ENABLE_ENV, "on")
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("LEGAL_NOW", "2026-09-15T12:00:00")  # the window ends here
    _write_ledger(
        _refusals.ledger_path(),
        [
            {"ts": "2026-09-03T10:00:00", "evento": "rifiuto", "tool": "contributo_unificato", "tables": ["comuni"]},
            {"ts": "2026-09-04T10:00:00", "evento": "accettazione", "tool": "codice_fiscale", "accettata": "INDICATIVO"},
            {"ts": "2026-08-20T10:00:00", "evento": "rifiuto", "tool": "contributo_unificato", "tables": ["comuni"]},
            {"ts": "2026-08-21T10:00:00", "evento": "rifiuto", "tool": "codice_fiscale", "tables": ["comuni"]},
            # July has no events: a silent month is a row with zeroes, not a hole.
            {"ts": "2026-06-10T10:00:00", "evento": "rifiuto", "tool": "interessi_legali", "tables": ["tassi_mora"]},
        ],
    )
    report = _refusals.monthly(4)
    assert report["disponibile"] is True
    serie = report["serie"]
    assert [r["mese"] for r in serie] == ["2026-06", "2026-07", "2026-08", "2026-09"], (
        "oldest first, silent months included"
    )
    giugno, luglio, agosto, settembre = serie
    assert giugno["totale"] == 1 and luglio["totale"] == 0
    assert agosto["totale"] == 2 and settembre["totale"] == 2
    assert luglio["delta_mese_precedente"] == -1
    assert agosto["delta_mese_precedente"] == 2
    # September's first delta compares against August, not against June.
    assert settembre["delta_mese_precedente"] == 0
    assert settembre["rifiuti"] == {"contributo_unificato": 1}
    assert settembre["accettazioni"] == {"codice_fiscale": 1}
    assert agosto["tabelle"] == {"comuni": 2}
    assert agosto["top_tabella"] == "comuni"
    assert settembre["top_tool"] == "contributo_unificato"


def test_monthly_reports_zeros_when_the_ledger_file_is_missing(monkeypatch):
    """No file yet: a zeroed series, not an error -- absence is a valid month."""
    monkeypatch.setenv(_refusals.ENABLE_ENV, "on")
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_ledger_dir()))
    report = _refusals.monthly(3)
    assert report["disponibile"] is True
    assert report["serie"][-1]["totale"] == 0, "no file: zeros, not an error"


def tmp_ledger_dir() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="monthly-ledger-"))


def test_monthly_is_honest_when_the_ledger_is_off(monkeypatch):
    monkeypatch.delenv(_refusals.ENABLE_ENV, raising=False)
    report = _refusals.monthly(3)
    assert report["disponibile"] is False
    assert "LEGAL_REFUSAL_LEDGER" in report["motivo"]


def test_the_monthly_readback_arrives_over_the_wire():
    """`verbale_mensile` reads the same file the middleware writes, from the wire."""
    arguments = {REFUSING_TOOL: {"keyword": "commercio"}}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="mensile-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="mensile-tmp-"))
    env = server_env(
        sandbox,
        scratch,
        extra={**PRESENT, "LEGAL_CACHE": "off", _refusals.ENABLE_ENV: "on"},
    )
    call_tools(env, [REFUSING_TOOL], arguments, timeout=300, script=PROBE_SCRIPT)
    replies = call_tools(
        env, ["verbale_mensile"], {"verbale_mensile": {}}, timeout=300
    )
    payload = _payload(replies["verbale_mensile"])
    assert payload.get("disponibile") is True
    serie = payload.get("serie") or []
    assert serie, "the probe's refusal happened this month: the series cannot be empty"
    corrente = serie[-1]
    assert corrente["rifiuti"].get(REFUSING_TOOL) == 1
    # And the meta names the ledger, so a host can tell an empty window from a
    # misdirected one.
    meta = _meta(replies["verbale_mensile"]).get("mcp-legal-it/verbale_rifiuti") or {}
    assert meta.get("ledger", "").endswith(_refusals.LEDGER_NAME)
