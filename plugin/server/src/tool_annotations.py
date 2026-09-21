"""MCP tool annotations, so hosts can tell a read-only lookup from a file writer.

`readOnlyHint` is asserted only for tools whose implementation cannot reach any
filesystem or network write: `scripts/audit_tool_annotations.py` walks the call
graph of every `@mcp.tool()` function in `src/` (helpers and imported clients
included) looking for `open(..., "w"/"a"/"x")`, `Path.write_text/write_bytes`,
`mkdir`, `unlink`, `replace`, `shutil.*`, the document constructors
(`Document`, `Workbook`, `FPDF`, `ZipFile`) and HTTP verbs that mutate
(`post`, `put`, `patch`).

The 17 tools that do write are listed in `WRITES_FILES` and get an explicit
`readOnlyHint=False` instead of being left blank: most of them write a cache
file, five of them write a document the user asked for. Neither group is
`destructiveHint` -- they add or refresh files, they do not delete user data --
so hosts that gate on destructiveness can still treat them as safe.

The 12 cache writers are also in `CACHE_WRITES`: their only write goes under
`${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}` (`akn_acts/` for parsed acts, the hit
counter and the URL-params index, `brocardi_urls.json` for article URLs,
`corte_cost/{kind}/{year}.json` for the Consulta massime, 7-day TTL). The
writes are best-effort -- with an unwritable cache directory `cite_law()` still
answers -- and `LEGAL_CACHE=off` keeps the server off the disk entirely: the
directory is then never read nor created (`src/lib/_cache.py` is the one module
that reads the switch, and the only one that resolves `MCP_CACHE_DIR`).
`docs/cache-inventory.md` carries the per-cache and per-tool detail.

`openWorldHint` marks the tools that reach outside the process (Normattiva,
EUR-Lex, Italgiure, the Garante, SPARQL endpoints, VIES, ...); the 169
local-only ones are pure calculations over the bundled JSON tables.

`ONLINE_SOURCES` names those same tools from the provenance side: every one of
them records what it consulted while answering (`src/lib/_sources.py`), and
the answer carries a `fonti_consultate` block in `_meta` with the dataset
names and the moment of the consult. The per-tool dataset map is
`source_bindings.py`, regenerated together with this policy.

`apply_tool_annotations` installs a middleware that stamps these annotations on
`tools/list`. It lives in one place on purpose: annotating 221 decorators would
be a diff nobody can review, and the audit rule is easier to re-run than to
re-derive. The policy is checked against the registered tools on the first
listing, so a renamed tool is reported instead of silently losing its hint.

Regenerate this file with `python scripts/audit_tool_annotations.py --write`;
`--check` fails the suite when it drifts from the source.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

from fastmcp.server.middleware import Middleware
from mcp.types import ToolAnnotations

# No reachable filesystem/network write.
READ_ONLY: frozenset[str] = frozenset({
    "acconto_cedolare_secca", "acconto_irpef", "adeguamento_canone_locazione", "analisi_base_giuridica",
    "assegno_unico", "attestazione_conformita", "atto_di_precetto", "aumenti_riduzioni_pena",
    "backlog_riconciliazione", "calcolo_ammortamento", "calcolo_devalutazione", "calcolo_eredita",
    "calcolo_eta_anagrafica", "calcolo_hash", "calcolo_imu", "calcolo_inflazione", "calcolo_irpef",
    "calcolo_maggior_danno", "calcolo_naspi", "calcolo_notula_penale", "calcolo_sanzione_gdpr",
    "calcolo_superficie_commerciale", "calcolo_surroga_mutuo", "calcolo_taeg", "calcolo_tempo_trascorso",
    "calcolo_tfr", "calcolo_usufrutto", "calcolo_valore_catastale", "cedolare_secca", "cerca_codice_tributo",
    "cerca_ddl", "cerca_delibere_consob", "cerca_gazzetta_ufficiale", "cerca_giurisprudenza",
    "cerca_giurisprudenza_amministrativa", "cerca_giurisprudenza_cgue", "cerca_giurisprudenza_tributaria",
    "cerca_giurisprudenza_unificata", "cerca_marchi", "cerca_provvedimenti_garante", "cerca_ufficio_giudiziario",
    "cerdef_leggi_provvedimento", "codice_fiscale", "codici_iscrizione_ruolo", "compenso_ctu",
    "compenso_curatore_fallimentare", "compenso_delegati_vendite", "compenso_mediatore_familiare",
    "compenso_occ", "compenso_orario", "competenza_giudice", "composizione_negoziata", "concordato_preventivo",
    "confronto_investimenti", "conta_giorni", "contributo_unificato", "conversione_pena",
    "copie_processo_tributario", "costi_costituzione", "costo_lavoro", "danno_biologico_macro",
    "danno_biologico_micro", "danno_non_patrimoniale", "danno_parentale", "ddl_su_norma",
    "decodifica_codice_fiscale", "decreto_ingiuntivo", "decurtazione_punti_patente", "detrazione_altri_familiari",
    "detrazione_assegno_coniuge", "detrazione_canone_locazione", "detrazione_coniuge", "detrazione_figli",
    "detrazione_lavoro_dipendente", "detrazione_pensione", "dichiarazione_553_cpc", "diritti_copia",
    "elenco_misure_nazionali", "equo_indennizzo", "fascicolo_di_parte", "fattura_avvocato",
    "fattura_enasarco", "fattura_professionista", "fetch_act_index", "fine_pena", "genera_dpa",
    "genera_dpia", "genera_informativa_cookie", "genera_informativa_dipendenti", "genera_informativa_privacy",
    "genera_informativa_videosorveglianza", "genera_modello_atto", "genera_notifica_data_breach",
    "genera_registro_trattamenti", "get_eu_basis", "get_italian_implementation", "giurisprudenza_amm_su_norma",
    "giurisprudenza_cgue_su_norma", "giurisprudenza_su_norma", "grado_parentela", "gratuito_patrocinio",
    "imposta_registro_locazioni", "imposte_compravendita", "imposte_successione", "indennita_licenziamento",
    "indennita_preavviso", "indice_documenti", "inflazione_titoli_stato", "interessi_acconti",
    "interessi_corso_causa", "interessi_legali", "interessi_mora", "interessi_tasso_fisso",
    "interessi_vari_capitale_rivalutato", "istanza_visibilita_fascicolo", "iter_ddl", "leggi_atto_gazzetta",
    "leggi_delibera_consob", "leggi_marchio", "leggi_provvedimento_amm", "leggi_provvedimento_garante",
    "leggi_sentenza", "leggi_sentenza_cgue", "lettera_adeguamento_canone", "lista_categorie_atti",
    "menomazioni_plurime", "modello_notula", "nota_precisazione_credito", "nota_spese", "note_iscrizione_ruolo",
    "note_trattazione_scritta", "offerta_conciliativa", "orientamento_su_norma", "orientamento_su_principio",
    "parcella_avvocato_civile", "parcella_avvocato_penale", "parcella_stragiudiziale", "parcella_volontaria_giurisdizione",
    "pena_concordata", "pensione_reversibilita", "pignoramento_stipendio", "prescrizione_diritti",
    "prescrizione_reato", "preventivo_civile", "preventivo_stragiudiziale", "preventivo_volontaria_giurisdizione",
    "procura_alle_liti", "pronti_termine", "quorum_assembleari", "rateizzazione_imposte",
    "ravvedimento_operoso", "regime_forfettario", "relata_notifica_pec", "rendimento_bot",
    "rendimento_btp", "rendimento_buoni_postali", "ricerca_codici_ateco", "ricevuta_prestazione_occasionale",
    "risarcimento_inail", "ritenuta_acconto", "rivalutazione_annuale_media", "rivalutazione_mensile",
    "rivalutazione_monetaria", "rivalutazione_storica", "rivalutazione_tfr", "scadenza_processuale",
    "scadenze_impugnazioni", "scadenze_licenziamento", "scadenze_multe", "scadenze_societarie",
    "scarica_pdf_gazzetta", "scorporo_iva", "sfratto_morosita", "soglie_organo_controllo_srl",
    "sollecito_pagamento", "sommario_gazzetta", "spese_condominiali", "spese_mediazione",
    "spese_trasferta_avvocati", "tariffe_mediazione", "tassazione_atti", "tasso_alcolemico",
    "termini_183_190_cpc", "termini_deposito_atti_appello", "termini_deposito_ctu", "termini_esecuzioni",
    "termini_memorie_repliche", "termini_procedimento_semplificato", "termini_processuali_civili",
    "termini_separazione_divorzio", "test_crisi_impresa", "testimonianza_scritta", "ultime_delibere_consob",
    "ultime_gazzette", "ultime_pronunce", "ultime_sentenze_cgue", "ultime_sentenze_tributarie",
    "ultimi_provvedimenti_amm", "ultimi_provvedimenti_garante", "valutazione_data_breach",
    "variazioni_istat", "verbale_mensile", "verifica_anteriorita_marchio", "verifica_iban",
    "verifica_mediazione_obbligatoria", "verifica_necessita_dpia", "verifica_partita_iva",
    "verifica_partita_iva_vies", "verifica_usura",
})

# Reachable write: cache refresh (12) or document generation (5).
WRITES_FILES: frozenset[str] = frozenset({
    "cerca_brocardi", "cerca_pronuncia_costituzionale", "cite_law", "download_law_pdf", "esporta_atto_docx",
    "fetch_full_act", "fetch_law_annotations", "fetch_law_article", "genera_procura_liti_docx",
    "genera_quotazione_docx", "genera_report_fornitori", "giurisprudenza_articolo", "leggi_pronuncia_costituzionale",
    "mappa_orientamento", "pronunce_cost_su_norma", "ultime_pronunce_cost", "verifica_citazioni",
    "verifica_dpa_fornitore",
})

# Reaches an external service.
OPEN_WORLD: frozenset[str] = frozenset({
    "cerca_brocardi", "cerca_ddl", "cerca_delibere_consob", "cerca_gazzetta_ufficiale", "cerca_giurisprudenza",
    "cerca_giurisprudenza_amministrativa", "cerca_giurisprudenza_cgue", "cerca_giurisprudenza_tributaria",
    "cerca_giurisprudenza_unificata", "cerca_marchi", "cerca_pronuncia_costituzionale", "cerca_provvedimenti_garante",
    "cerdef_leggi_provvedimento", "cite_law", "ddl_su_norma", "download_law_pdf", "elenco_misure_nazionali",
    "fetch_act_index", "fetch_full_act", "fetch_law_annotations", "fetch_law_article", "get_eu_basis",
    "get_italian_implementation", "giurisprudenza_amm_su_norma", "giurisprudenza_articolo",
    "giurisprudenza_cgue_su_norma", "giurisprudenza_su_norma", "iter_ddl", "leggi_atto_gazzetta",
    "leggi_delibera_consob", "leggi_marchio", "leggi_pronuncia_costituzionale", "leggi_provvedimento_amm",
    "leggi_provvedimento_garante", "leggi_sentenza", "leggi_sentenza_cgue", "mappa_orientamento",
    "orientamento_su_norma", "orientamento_su_principio", "pronunce_cost_su_norma", "scarica_pdf_gazzetta",
    "sommario_gazzetta", "ultime_delibere_consob", "ultime_gazzette", "ultime_pronunce",
    "ultime_pronunce_cost", "ultime_sentenze_cgue", "ultime_sentenze_tributarie", "ultimi_provvedimenti_amm",
    "ultimi_provvedimenti_garante", "verifica_anteriorita_marchio", "verifica_citazioni",
    "verifica_dpa_fornitore", "verifica_partita_iva_vies",
})

# Subset of WRITES_FILES whose only write refreshes the local cache under
# ${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}.
CACHE_WRITES: frozenset[str] = frozenset({
    "cerca_brocardi", "cerca_pronuncia_costituzionale", "cite_law", "fetch_full_act", "fetch_law_annotations",
    "fetch_law_article", "giurisprudenza_articolo", "leggi_pronuncia_costituzionale", "mappa_orientamento",
    "pronunce_cost_su_norma", "ultime_pronunce_cost", "verifica_citazioni", "verifica_dpa_fornitore",
})

# Reachable code that consults an online source (provenance recorded per call
# in `_meta` as `fonti_consultate`; the per-tool datasets are in
# `source_bindings.py`).
ONLINE_SOURCES: frozenset[str] = frozenset({
    "cerca_brocardi", "cerca_ddl", "cerca_delibere_consob", "cerca_gazzetta_ufficiale", "cerca_giurisprudenza",
    "cerca_giurisprudenza_amministrativa", "cerca_giurisprudenza_cgue", "cerca_giurisprudenza_tributaria",
    "cerca_giurisprudenza_unificata", "cerca_marchi", "cerca_pronuncia_costituzionale", "cerca_provvedimenti_garante",
    "cerdef_leggi_provvedimento", "cite_law", "ddl_su_norma", "download_law_pdf", "elenco_misure_nazionali",
    "fetch_act_index", "fetch_full_act", "fetch_law_annotations", "fetch_law_article", "get_eu_basis",
    "get_italian_implementation", "giurisprudenza_amm_su_norma", "giurisprudenza_articolo",
    "giurisprudenza_cgue_su_norma", "giurisprudenza_su_norma", "iter_ddl", "leggi_atto_gazzetta",
    "leggi_delibera_consob", "leggi_marchio", "leggi_pronuncia_costituzionale", "leggi_provvedimento_amm",
    "leggi_provvedimento_garante", "leggi_sentenza", "leggi_sentenza_cgue", "mappa_orientamento",
    "orientamento_su_norma", "orientamento_su_principio", "pronunce_cost_su_norma", "scarica_pdf_gazzetta",
    "sommario_gazzetta", "ultime_delibere_consob", "ultime_gazzette", "ultime_pronunce",
    "ultime_pronunce_cost", "ultime_sentenze_cgue", "ultime_sentenze_tributarie", "ultimi_provvedimenti_amm",
    "ultimi_provvedimenti_garante", "verifica_anteriorita_marchio", "verifica_citazioni",
    "verifica_dpa_fornitore", "verifica_partita_iva_vies",
})


def annotations_for(tool_name: str) -> ToolAnnotations | None:
    """Annotations for a tool, or None when the policy does not mention it."""
    if tool_name in READ_ONLY:
        return ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=tool_name in OPEN_WORLD,
        )
    if tool_name in WRITES_FILES:
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=tool_name in OPEN_WORLD,
        )
    return None


class ToolAnnotationMiddleware(Middleware):
    """Stamp the audited annotations on every `tools/list` response."""

    def __init__(self) -> None:
        self._checked = False

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        for tool in tools:
            annotations = annotations_for(tool.name)
            if annotations is not None:
                tool.annotations = annotations
        if not self._checked:
            self._checked = True
            self._warn_on_drift(t.name for t in tools)
        return tools

    def _warn_on_drift(self, registered: Iterable[str]) -> None:
        names = set(registered)
        missing = (READ_ONLY | WRITES_FILES) - names
        if missing:
            print(
                "tool_annotations: policy names no longer registered: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )


def apply_tool_annotations(server) -> None:
    """Install the annotation middleware on a FastMCP server."""
    server.add_middleware(ToolAnnotationMiddleware())
