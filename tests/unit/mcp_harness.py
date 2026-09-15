"""Drive the MCP server the way a host does: stdio, in a sandbox, one call each.

Shared by `test_read_only_contract.py` (nothing may be written) and
`test_golden_calcoli.py` (the numbers may not drift). Both need the same three
things, and keeping them in one place is what makes the two tests comparable:
the tool manifest with its schemas, arguments generated from those schemas, and
a subprocess that speaks JSON-RPC to `plugin/server/run_server.py`.

The environment builder is the other half: every run gets its own `HOME`,
`XDG_CACHE_HOME`, `TMPDIR` and `MCP_CACHE_DIR`, so a tool that writes somewhere
it should not cannot touch the developer's real files, and `FASTMCP_*` is turned
off so the framework itself does not create files in the sandbox.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER_SERVER = REPO / "plugin/server/run_server.py"

# Arguments the schema cannot express well enough: enums worth pinning (the
# closed sets the tools validate against live in the docstring or the data
# tables, not in the schema), names that look like dates but are not, and
# free-form strings with a documented format. Each entry here is a tool the
# generated arguments could only make fail.
CURATED = {
    # `tipo_societa` is validated against a closed list that the schema calls a
    # free string; `rate` is a number of installments, and 10000 of them make
    # the Newton-Raphson iteration diverge.
    "costi_costituzione": {"tipo_societa": "srl"},
    "quorum_assembleari": {"tipo_societa": "srl", "tipo_delibera": "ordinaria",
                          "capitale_totale": 100000.0, "capitale_presente": 60000.0,
                          "voti_favorevoli": 40000.0},
    "calcolo_taeg": {"capitale": 10000.0, "rate": 12, "importi_rate": 900.0,
                     "spese_iniziali": 100.0, "spese_periodiche": 2.0},
    "indennita_preavviso": {"ccnl": "commercio", "livello": "2_3", "anzianita_anni": 7.0,
                            "retribuzione_mensile": 2500.0, "tipo": "licenziamento"},
    "codice_fiscale": {"nome": "Mario", "cognome": "Rossi", "data_nascita": "1980-01-01",
                       "sesso": "M", "comune_nascita": "Roma"},
    "verifica_iban": {"iban": "IT60X0542811101000000123456"},
    "verifica_partita_iva": {"partita_iva": "12345678903"},
    "scorporo_iva": {"importo_ivato": 1220, "aliquota": 22},
    "calcolo_hash": {"testo": "contratto"},
    "cerca_codice_tributo": {"query": "1001"},
    "cerca_gazzetta_ufficiale": {"query": "decreto"},
    "verifica_mediazione_obbligatoria": {"materia": "condominio"},
    # Closed vocabularies the schema calls a free string (each value below is
    # one the tool itself accepts, read from its docstring or its table):
    "analisi_base_giuridica": {"tipo_trattamento": "invio newsletter", "contesto": "B2C",
                              "finalita": "marketing diretto via email a clienti esistenti"},
    "calcolo_notula_penale": {"competenza": "tribunale_monocratico"},
    "calcolo_sanzione_gdpr": {"tipo_violazione": "art83_5", "fatturato_annuo": 10_000_000.0,
                              "fattori_aggravanti": ["larga scala"], "precedenti": False},
    "compenso_ctu": {"tipo_incarico": "perizia_immobiliare", "valore_causa": 50000.0,
                     "ore_lavoro": 20},
    "danno_parentale": {"vittima": "figlio", "superstite": "genitore"},
    "decurtazione_punti_patente": {"violazione": "cellulare"},
    "equo_indennizzo": {"categoria_tabella": "1", "percentuale_invalidita": 85.0,
                        "stipendio_annuo": 35000.0},
    "genera_modello_atto": {"tipo_atto": "decreto_ingiuntivo_ordinario"},
    "grado_parentela": {"relazione": "figlio"},
    "imposte_successione": {"valore_beni": 500000.0, "parentela": "coniuge_linea_retta"},
    "modello_notula": {"tipo_procedimento": "decreto_ingiuntivo", "avvocato": "Avv. Mario Rossi",
                       "cliente": "Alfa Srl", "valore_causa": 25000.0},
    "parcella_avvocato_penale": {"competenza": "tribunale_monocratico"},
    "prescrizione_diritti": {"tipo_diritto": "risarcimento_danni", "data_evento": "2021-01-01"},
    "scadenze_impugnazioni": {"data_pubblicazione": "2021-01-01",
                              "tipo_impugnazione": "appello_sentenza", "notificata": False},
    "scadenze_multe": {"data_notifica": "2021-01-01", "tipo_ricorso": "prefetto"},
    "tassazione_atti": {"tipo_atto": "sentenza_condanna", "valore": 10000.0},
    "termini_processuali_civili": {"data_udienza": "2022-03-15", "tipo_termine": "memoria_I"},
    "termini_separazione_divorzio": {"data_evento": "2021-01-01", "tipo": "separazione_consensuale"},
    "valutazione_data_breach": {"tipo_violazione": "confidenzialita",
                                "categorie_dati": ["email", "password hash"],
                                "n_interessati": 500, "impatto": "medio",
                                "misure_protezione": ["cifratura AES-256"]},
    # Formats and ranges the schema states but cannot enforce:
    "calcolo_imu": {"rendita_catastale": 900.0, "categoria": "A/2", "prima_casa": False},
    "calcolo_valore_catastale": {"rendita_catastale": 900.0, "categoria": "A/2"},
    "calcolo_usufrutto": {"valore_piena_proprieta": 200000.0, "eta_usufruttuario": 65},
    "danno_biologico_macro": {"percentuale_invalidita": 15, "eta_vittima": 45},
    "danno_biologico_micro": {"percentuale_invalidita": 3, "eta_vittima": 45, "giorni_itt": 10,
                              "giorni_itp50": 20, "personalizzazione_pct": 5.0},
    "decodifica_codice_fiscale": {"codice_fiscale": "RSSMRA80A01H501U"},
    "menomazioni_plurime": {"percentuali": [15, 10, 5]},
    "nota_spese": {"voci": [{"descrizione": "attività di studio", "importo": 2000.0,
                             "tipo": "compenso"}]},
    "pensione_reversibilita": {"pensione_de_cuius": 18000.0, "reddito_beneficiario": 20000.0,
                               "beneficiari": {"coniuge": True, "figli": 1, "figli_minori": 1,
                                               "genitori": 0}},
    "tasso_alcolemico": {"sesso": "M", "peso_kg": 80.0, "unita_alcoliche": 3.0,
                         "ore_trascorse": 2.0},
    "interessi_acconti": {"capitale": 10000.0, "data_inizio": "2021-01-01",
                          "data_fine": "2024-06-30",
                          "acconti": [{"data": "2022-06-30", "importo": 5000.0}]},
    "termini_deposito_atti_appello": {"data_pubblicazione": "2021-01-01"},
}
# Free-form strings: an empty value usually makes the tool reject the call
# before doing any work, which would prove nothing.
STRING_HINTS = (
    ("query", "condominio"), ("testo", "testo di prova"), ("riferimento", "art. 2043 c.c."),
    ("articolo", "art. 2043 c.c."), ("norma", "art. 2043 c.c."), ("materia", "civile"),
    ("tipo", "ordinario"), ("nome", "Mario"), ("cognome", "Rossi"), ("titolo", "Atto"),
    ("descrizione", "descrizione"), ("iban", "IT60X0542811101000000123456"),
    ("piva", "12345678903"), ("testo_contratto", "locazione"), ("query_text", "eredità"),
)
# Absolute dates, never "today": a golden value that moves with the calendar
# would be regenerated instead of reported. Roles matter -- an interval closed
# on the same day both starts and ends nowhere useful, and the rate tools reject
# it -- so `data_inizio`/`data_fine` are deliberately different days.
DATE_VALUE = "2023-01-01"
DATE_END = "2024-06-30"
# Tools take two or three dates and validate their order ("data_fine deve essere
# successiva a data_inizio"), so one constant for every `data_*` parameter is
# not enough: each name gets a distinct day from the role it describes. The
# values are absolute, and distinct, which is what the tools check.
DATE_PALETTE = (
    (("fine", "finale", "attuale", "adeguamento", "oggi", "termine", "analisi", "vigenza",
      "arrivo", "sollecito", "sentenza", "scoperta", "notifica", "comunicazione", "deposito"),
     DATE_END),
    (("inizio", "iniziale", "partenza", "nascita", "evento", "stipula", "passata", "violazione",
      "citazione", "notifica_reato", "scadenza", "pubblicazione"),
     "2021-01-01"),
)
#: Years follow the same logic: `anno_partenza` < `anno_arrivo`, or the tool
#: rejects the interval before computing anything.
YEAR_START = 2020
YEAR_END = 2024
YEAR_PALETTE = (
    (("partenza", "inizio", "iniziale", "da"), YEAR_START),
    (("arrivo", "fine", "finale", "attuale", "vigenza"), YEAR_END),
)


def date_value(name: str) -> str:
    lowered = name.lower()
    for tokens, value in DATE_PALETTE:
        if any(token in lowered for token in tokens):
            return value
    return DATE_VALUE


def year_value(name: str) -> int:
    lowered = name.lower()
    for tokens, value in YEAR_PALETTE:
        if any(token in lowered for token in tokens):
            return value
    return YEAR_END


def object_from(spec: dict) -> dict:
    """A minimal object for a schema: its required fields, one level deep.

    Several tools take structured rows (eredi, acconti, voci, rischi, ...).
    Filling their required properties is what turns "missing required argument"
    into an actual computation, which is the whole point of calling them.
    """
    properties = spec.get("properties") or {}

    def scalar(sub: dict) -> bool:
        kind = sub.get("type")
        if kind == "object":
            return False
        if kind == "array" and (sub.get("items") or {}).get("type") == "object":
            return False
        return True

    required = spec.get("required") or [name for name, sub in properties.items() if scalar(sub)]
    return {name: value_for(name, properties.get(name, {})) for name in required or list(properties)[:1]}


def value_for(name: str, schema: dict):
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    kind = schema.get("type")
    lowered = name.lower()
    if kind == "boolean":
        return True
    if kind == "object":
        return object_from(schema)
    if kind == "array":
        item = schema.get("items") or {}
        if item.get("type") == "object":
            row = object_from(item)
            return [row] if row else [{}]
        if item.get("type") in ("integer", "number"):
            return [1]
        if item.get("type") == "string" and lowered.startswith("data"):
            return [date_value(name)]
        return ["x"]
    if kind in ("number", "integer"):
        if any(key in lowered for key in ("percentuale", "tasso", "aliquota", "pct", "interesse")):
            return 5.0 if kind == "number" else 5
        if lowered.startswith("anno") or lowered.endswith("_anno"):
            year = year_value(name)
            return year if kind == "integer" else float(year)
        if "giorni" in lowered:
            return 30 if kind == "integer" else 30.0
        if "mesi" in lowered:
            return 12 if kind == "integer" else 12.0
        if "anni" in lowered:
            return 10 if kind == "integer" else 10.0
        if any(key in lowered for key in ("n_", "numero", "num_", "quantita", "count")):
            return 2 if kind == "integer" else 2.0
        return 10000.0 if kind == "number" else 10000
    if kind == "string" or kind is None:
        if lowered.startswith("data") or lowered.endswith("_data"):
            return date_value(name)
        for hint, value in STRING_HINTS:
            if hint in lowered:
                return value
        return "x"
    return None


def arguments_for(tool: dict) -> dict:
    """Arguments for one tool: curated where needed, else derived from the schema."""
    name = tool["name"]
    if name in CURATED:
        return dict(CURATED[name])
    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    args = {}
    for prop, spec in properties.items():
        if prop not in required and "default" in spec:
            continue
        value = value_for(prop, spec)
        if value is not None:
            args[prop] = value
    return args


def tools() -> list[dict]:
    """The tool manifest, read from the server in-process (no subprocess)."""
    from fastmcp import Client

    sys.path.insert(0, str(REPO / "plugin/server"))
    try:
        from src.server import mcp
    finally:
        sys.path.pop(0)

    async def run():
        async with Client(mcp) as client:
            return await client.list_tools()

    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "inputSchema": tool.inputSchema,
            "annotations": tool.annotations.model_dump() if tool.annotations else None,
        }
        for tool in asyncio.run(run())
    ]


def local_read_only(tools_: list[dict]) -> list[dict]:
    """Tools that neither write nor reach the network: the reproducible surface."""
    return [
        tool
        for tool in tools_
        if (tool.get("annotations") or {}).get("readOnlyHint") is True
        and (tool.get("annotations") or {}).get("openWorldHint") is not True
    ]


def server_env(sandbox: pathlib.Path, tmp_path: pathlib.Path, extra: dict | None = None) -> dict:
    """A hermetic environment for one server run."""
    (sandbox / ".cache").mkdir(parents=True, exist_ok=True)
    env = {
        "HOME": str(sandbox),
        "XDG_CACHE_HOME": str(sandbox / ".cache"),
        "MCP_CACHE_DIR": str(sandbox / "mcp-cache"),
        "USER": os.environ.get("USER", "user"),
        "LOGNAME": os.environ.get("LOGNAME", "user"),
        "SHELL": "/bin/zsh",
        "TMPDIR": str(tmp_path),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        # FastMCP itself would otherwise phone home to PyPI and drop a
        # version_cache.json in the (sandboxed) user data dir.
        "FASTMCP_CHECK_FOR_UPDATES": "off",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    if extra:
        env.update(extra)
    return env


def call_tools(env: dict, tool_names, arguments_by_tool, timeout: int) -> dict:
    """Start the server in `env` and call every tool, one request per tool."""
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER_SERVER)],
        cwd=str(REPO),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    results = {}
    try:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "mcp-harness", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        ]
        request_id = 2
        by_id = {}
        for name in tool_names:
            requests.append({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                             "params": {"name": name, "arguments": arguments_by_tool[name]}})
            by_id[request_id] = name
            request_id += 1
        for request in requests:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
        deadline = time.time() + timeout
        while len(results) < len(tool_names) and time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except ValueError:
                continue
            name = by_id.get(message.get("id"))
            if name:
                results[name] = message
    finally:
        proc.terminate()
        try:
            proc.stderr.close()
        except Exception:
            pass
    return results


def answer_text(reply: dict) -> str:
    """The textual answer of a `tools/call` reply ('' when it failed)."""
    if "result" not in reply or reply["result"].get("isError"):
        return ""
    content = reply["result"].get("content") or []
    return "\n".join(
        item.get("text", "") for item in content if item.get("type") == "text"
    ).strip()
