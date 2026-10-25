"""MCP Legal IT — 231 Italian legal tools: calculations, normative citations, case law (Cassazione, Corte Costituzionale, CeRDEF, TAR/CdS, CGUE), Gazzetta Ufficiale, parliamentary bills (Senato/Camera open data), EU→IT transposition, GDPR compliance, CONSOB, ANAC, document generation."""

import asyncio
import os
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from mcp_legal_it._profilo import profilo_richiesto
from mcp_legal_it.cli_version import package_version

mcp = FastMCP(
    "Legal IT",
    version=package_version(),
    instructions="""\
Strumenti di diritto italiano. Cerca i tool di questo server quando l'utente chiede:
- CALCOLI DANNI/SINISTRI: risarcimento, danno biologico, invalidità, ITT/ITP
- INTERESSI/RIVALUTAZIONE: interessi legali, mora, rivalutazione ISTAT, inflazione
- SCADENZE PROCESSUALI: termini, memorie, impugnazioni, prescrizione
- ATTI GIUDIZIARI: contributo unificato, decreto ingiuntivo, pignoramento, precetto
- PARCELLE AVVOCATI: compenso, notula, preventivo, fattura avvocato
- PARCELLE PROFESSIONISTI: CTU, curatore, mediatore, fattura professionista
- CALCOLI FISCALI: IRPEF, detrazioni, TFR, regime forfettario, ravvedimento
- PROPRIETÀ/SUCCESSIONI: eredità, IMU, usufrutto, compravendita, imposta registro
- INVESTIMENTI: BOT, BTP, buoni postali, rendimento
- UTILITÀ: codice fiscale, IBAN, scorporo IVA, patente, alcolemico, ATECO
- NORMATIVA: cite_law() per testo vigente, Brocardi per dottrina, PDF norme
- VERIFICA CITAZIONI: verifica_citazioni() controlla esistenza e metadati di un elenco di norme e sentenze citate (NON verifica il merito)
- GAZZETTA UFFICIALE: cerca_gazzetta_ufficiale, leggi_atto_gazzetta, sommario_gazzetta, ultime_gazzette, scarica_pdf_gazzetta — atti pubblicati in GU (leggi, decreti, ELI)
- DDL E ITER PARLAMENTARE: cerca_ddl, iter_ddl, ddl_su_norma — disegni di legge pendenti, navette Senato/Camera, riforme in corso (dati.senato.it + dati.camera.it; ddl_su_norma cerca solo nei TITOLI, best-effort dichiarato)
- GIURISPRUDENZA: sentenze Cassazione (Italgiure, archivio 2020+). Strategia: esplora → filtra → leggi
- CORTE COSTITUZIONALE: cerca_pronuncia_costituzionale, leggi_pronuncia_costituzionale, pronunce_cost_su_norma, ultime_pronunce_cost — sentenze/ordinanze Consulta, massime, parametri costituzionali
- ORIENTAMENTO GIURISPRUDENZIALE: orientamento_su_norma, orientamento_su_principio, mappa_orientamento — conformi vs contrasti, interventi Sezioni Unite (descrittivo, non predittivo)
- GIURISPRUDENZA TRIBUTARIA: sentenze CTP/CTR/CGT, Cassazione tributaria, IVA, IRES, accertamento, riscossione (CeRDEF)
- GARANTE PRIVACY: provvedimenti GPDP, ricerca sanzioni, linee guida
- GDPR/PRIVACY COMPLIANCE: informative privacy (art. 13-14), cookie policy, DPA (art. 28), registro trattamenti (art. 30), DPIA (art. 35), data breach (art. 33-34), sanzioni (art. 83), base giuridica (art. 6), analisi mastrino fornitori (verifica_partita_iva_vies per VIES, genera_report_fornitori per l'Excel standard)
- CONSOB: delibere, provvedimenti, regolamenti mercati finanziari, intermediari, abusi di mercato
- ANAC: cerca_atti_anac, leggi_atto_anac, ultimi_atti_anac — delibere, pareri di precontenzioso e sulla normativa, linee guida, bandi tipo (contratti pubblici, anticorruzione, trasparenza)
- GIUSTIZIA AMMINISTRATIVA: sentenze TAR, Consiglio di Stato, appalti, urbanistica, PA, edilizia, accesso atti
- GIURISPRUDENZA UE: sentenze CGUE, Corte di Giustizia UE, Tribunale UE, rinvio pregiudiziale, conclusioni AG, ECLI
- ATTUAZIONE UE→IT: get_italian_implementation()/elenco_misure_nazionali() per le misure nazionali di recepimento di una direttiva, get_eu_basis() per la base UE di un atto italiano (CELLAR/SPARQL)
- REDAZIONE ATTI: genera_modello_atto() per catalogo 100 tipi atti (DI, precetto, procura, relata, attestazione, citazione, pignoramento, preventivo, privacy)
- RECUPERO CREDITI SERIALE: genera_procura_liti_docx() procura ex art. 83 c.p.c. pronta-firma; genera_quotazione_docx() lettera quotazione compensi D.M. 55/2014 (monitorio/esecuzione/opposizione) con accettazione cliente

REGOLE: cite_law() PRIMA di citare norme. leggi_sentenza() DIRETTO per sentenze note.
OUTPUT: € 1.234,56 | GG/MM/AAAA | segnalare INDICATIVO se stimato. Provenienza: riporta `dati_applicati` (col loro vintage) e `mcp-legal-it/fonti_consultate` dal `_meta`.

WORKFLOW:
Sinistro → danno_biologico_* → danno_non_patrimoniale → rivalutazione_monetaria → interessi_legali
Credito → interessi_mora → rivalutazione_monetaria → decreto_ingiuntivo → parcella_avvocato_civile
Procure/quotazioni seriali → genera_procura_liti_docx + genera_quotazione_docx (tipo in base alla fase: monitorio | esecuzione | opposizione)
Norma → cite_law → cerca_brocardi → giurisprudenza_su_norma → leggi_sentenza
Orientamento → orientamento_su_norma/orientamento_su_principio → mappa_orientamento (conformi/contrasti/SS.UU.)
Costituzionale → cerca_pronuncia_costituzionale → leggi_pronuncia_costituzionale | pronunce_cost_su_norma → cite_law
Gazzetta → ultime_gazzette/cerca_gazzetta_ufficiale → leggi_atto_gazzetta → cite_law
Riforme pendenti → ddl_su_norma(norma)/cerca_ddl(tema) → iter_ddl(atto) → citare numero atto + stato + data + scheda
Recepimento UE → get_italian_implementation(direttiva) → cite_law | get_eu_basis(atto IT) → cite_law
Giurisprudenza → cerca_giurisprudenza(modalita="esplora") → cerca_giurisprudenza(filtri) → leggi_sentenza
Privacy → cite_law (GDPR) → cerca_provvedimenti_garante → leggi_provvedimento_garante
Compliance GDPR → analisi_base_giuridica → verifica_necessita_dpia → genera_registro_trattamenti → genera_informativa_privacy → genera_dpa
Analisi fornitori → verifica_partita_iva_vies → verifica_dpa_fornitore (dominio del fornitore; non_trovato/bloccato/dominio_irraggiungibile NON sono un "no": segue ricerca mirata) → genera_report_fornitori → genera_dpa (nomine per i responsabili senza DPA)
Marchi → cerca_marchi | verifica_anteriorita_marchio(nome, classi) → leggi_marchio(st13)
Data Breach → valutazione_data_breach → genera_notifica_data_breach → calcolo_sanzione_gdpr
CONSOB → cerca_delibere_consob → leggi_delibera_consob
Contratti pubblici/ANAC → cerca_atti_anac(query, tipologia) → leggi_atto_anac(riferimento) → cite_law
Tributario → cerca_giurisprudenza_tributaria → cerdef_leggi_provvedimento → cite_law
Amministrativo → cerca_giurisprudenza_amministrativa → leggi_provvedimento_amm → cite_law
Diritto UE → cerca_giurisprudenza_cgue → leggi_sentenza_cgue → cite_law
Redazione atti → genera_modello_atto(tipo) → [raccolta dati] → [tool calcolo] → [composizione atto]
""",
)

# Import all tool modules — each registers its tools via @mcp.tool()
from mcp_legal_it.tools import (  # noqa: E402, F401
    rivalutazioni_istat,
    tassi_interessi,
    scadenze_termini,
    atti_giudiziari,
    fatturazione_avvocati,
    parcelle_professionisti,
    risarcimento_danni,
    diritto_penale,
    diritto_societario,
    diritto_lavoro,
    crisi_impresa,
    proprieta_successioni,
    investimenti,
    dichiarazione_redditi,
    varie,
    legal_citations,
    italgiure,
    gpdp,
    consob,
    anac,
    cerdef,
    giustizia_amm,
    cgue,
    giurisprudenza_unificata,
    privacy_gdpr,
    modelli_atti,
    procedura_civile,
    corte_cost,
    gazzetta,
    parlamento,
    orientamento,
    eu_implementation,
    procure_quotazioni,
    analisi_fornitori,
    tmview,
)

from mcp_legal_it import prompts, resources  # noqa: E402, F401
from mcp_legal_it.lib import _brocardi_switch  # noqa: E402
from mcp_legal_it.lib._ledger import apply_table_ledger  # noqa: E402
from mcp_legal_it.lib._regime import ENV_SWITCH as _PREVIGENTE_SWITCH  # noqa: E402
from mcp_legal_it.lib._regime import TAG as _PREVIGENTE_TAG  # noqa: E402
from mcp_legal_it.lib._regime import hidden_by_environment as _previgenti_nascosti  # noqa: E402
from mcp_legal_it.source_bindings import TOOL_SOURCES  # noqa: E402
from mcp_legal_it.table_bindings import TABLE_CONSTANTS, TOOL_ALTERNATIVES, TOOL_TABLES  # noqa: E402
from mcp_legal_it.tool_annotations import PREVIGENTE, READ_ONLY, WRITES_FILES, apply_tool_annotations  # noqa: E402
from mcp_legal_it.tool_taxonomy import VOCABULARY  # noqa: E402

# ---------------------------------------------------------------------------
# Tool annotations: readOnlyHint/openWorldHint per tool, so hosts can tell a
# lookup from a file writer (see mcp_legal_it/tool_annotations.py for the audit rule).
# ---------------------------------------------------------------------------
apply_tool_annotations(mcp)

# ---------------------------------------------------------------------------
# Table ledger: every call declares in its result `_meta` which hand-maintained
# tables it actually read, observed rather than derived, and flags the ones whose
# vintage is expired or unverified (see mcp_legal_it/lib/_ledger.py). The same observation
# is what `mcp_legal_it/lib/_data.py` names in the `dati_applicati` footer.
# ---------------------------------------------------------------------------
_TABLES_WRAPPED = apply_table_ledger(
    mcp,
    TABLE_CONSTANTS,
    TOOL_TABLES,
    TOOL_ALTERNATIVES,
    tool_sources=TOOL_SOURCES,
    tool_regimes=PREVIGENTE,
)

# ---------------------------------------------------------------------------
# Profile-based tool filtering (for Desktop/Browser — lighter context)
# Usage: LEGAL_PROFILE=sinistro python -m mcp_legal_it.server
# Default: "full" (all tools — for Claude Code with Tool Search)
# The tags are the vocabulary in mcp_legal_it/tool_taxonomy.py (docs/tool-tags.md):
# a profile names kinds (normativa, giurisprudenza, autorita, diagnostica) and
# areas, never a single tool, so a new tool lands in the right profiles by its tags.
# Every profile carries `diagnostica`, so stato_server and the data report answer
# whatever surface was chosen. An unknown LEGAL_PROFILE refuses to start (_profilo.py).
# ---------------------------------------------------------------------------
_PROFILES: dict[str, set[str]] = {
    # Offline only: every `calcolo` tool answers from its inputs and the bundled tables,
    # and the diagnostics read the server itself (test_profiles checks no source is online).
    "calcoli": {"calcolo", "diagnostica"},
    "sinistro": {"danni", "rivalutazione", "interessi", "normativa", "giurisprudenza", "sinistro", "diagnostica"},
    "credito": {"interessi", "rivalutazione", "parcelle_avv", "normativa", "giurisprudenza", "credito", "diagnostica"},
    "penale": {"penale", "normativa", "giurisprudenza", "diagnostica"},
    "fiscale": {"fiscale", "proprieta", "utility", "consob", "investimenti", "crisi_impresa", "societario", "diagnostica"},
    "normativa": {"normativa", "giurisprudenza", "autorita", "registri", "privacy", "diagnostica"},
    "privacy": {"privacy", "garante", "normativa", "giurisprudenza", "diagnostica"},
    "studio": {"scadenze", "giudiziario", "parcelle_avv", "parcelle_prof", "investimenti", "lavoro", "diagnostica"},
    "redattore": {"atti", "giudiziario", "parcelle_avv", "scadenze", "normativa", "diagnostica"},
    "cowork": {"normativa", "giurisprudenza", "privacy", "parcelle_avv", "diagnostica"},
}

_PROMPTS_AND_RESOURCES = {"prompt", "resource", "template"}

_profile = profilo_richiesto(_PROFILES)
if _profile != "full":
    # FastMCP 3 replaced the `include_tags` attribute with a visibility transform:
    # `only=True` disables every component whose tags do not intersect the
    # profile; prompts and resources carry no tags, so the second transform
    # (the later one wins) keeps them available in every profile.
    mcp.enable(tags=_PROFILES[_profile], only=True)
    mcp.enable(components=_PROMPTS_AND_RESOURCES)

# ---------------------------------------------------------------------------
# Superseded-regime tools (`Regime: PREVIGENTE`, tag `previgente`): registered
# and flagged by default, because they are right for the residual cases they
# name; LEGAL_PREVIGENTE=off hides the whole group for hosts that would rather
# not expose them at all (see mcp_legal_it/lib/_regime.py). Applied after the profile so
# it wins whatever the profile enabled.
# ---------------------------------------------------------------------------
if _previgenti_nascosti(os.environ.get(_PREVIGENTE_SWITCH)):
    mcp.disable(tags={_PREVIGENTE_TAG})

# ---------------------------------------------------------------------------
# Brocardi switch: on by default; LEGAL_BROCARDI=off hides the tools whose answer
# is Brocardi content only (tag `solo_brocardi`), and the scrapers refuse every
# request to brocardi.it, so the mixed tools (tag `brocardi`) answer without it
# and say so (see mcp_legal_it/lib/_brocardi_switch.py). Applied last, like the
# regime switch, so no profile can bring the group back.
# ---------------------------------------------------------------------------
if _brocardi_switch.off_by_environment():
    mcp.disable(tags={_brocardi_switch.TAG_SOLO})


# ---------------------------------------------------------------------------
# The instructions name tools, and a client reads them once, at initialize: a
# server that hides some tools must not keep sending the model to them (it would
# get "Unknown tool"). The literal above stays the single source (it is also
# what scripts/corpus/agents_md.py copies into AGENTS.md); a narrowed server gets
# it with the hidden tools taken out.
# ---------------------------------------------------------------------------
_STOCK_INSTRUCTIONS: str = mcp.instructions or ""
_ALL_TOOL_NAMES: frozenset[str] = READ_ONLY | WRITES_FILES
_TOOL_NAME = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def _visible_tool_names(server: FastMCP) -> set[str]:
    """The tools ``server`` lists, read on a private event loop (callable from async code too)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        tools = pool.submit(asyncio.run, server.list_tools()).result()
    return {t.name for t in tools}


def _instructions_for(available: set[str], text: str = _STOCK_INSTRUCTIONS) -> str:
    """``text`` without the tools a server does not list.

    A workflow step that is just a hidden tool (``→ cerca_brocardi →``) is dropped
    from its chain, and the chain goes when it keeps fewer than two steps after its
    label; any other line that still names a hidden tool is dropped whole.
    With every tool available the text comes back unchanged.
    """
    hidden = {name for name in _TOOL_NAME.findall(text) if name in _ALL_TOOL_NAMES} - available
    if not hidden:
        return text
    lines = []
    for line in text.split("\n"):
        if "cerca_brocardi" in hidden:
            line = line.replace(", Brocardi per dottrina", "")
        if " → " in line:
            steps = line.split(" → ")
            kept = [s for s in steps if s.strip() not in hidden]
            if len(kept) < len(steps) and len(kept) < 3:
                continue  # a label and a single step left: no workflow any more
            line = " → ".join(kept)
        if set(_TOOL_NAME.findall(line)) & hidden:
            continue
        lines.append(line)
    return "\n".join(lines)


if _brocardi_switch.off_by_environment():
    mcp.instructions = _instructions_for(_visible_tool_names(mcp))


# ---------------------------------------------------------------------------
# A server with only some of the tools, for a host that mounts mcp-legal-it into
# its own surface: an application that needs the sources (norms, case law) and
# none of the calculators, or a commercial deployment that must leave Brocardi out.
# ---------------------------------------------------------------------------
class _BrocardiOffMiddleware(Middleware):
    """Run every tool call of one server with Brocardi switched off."""

    async def on_call_tool(self, context, call_next):
        token = _brocardi_switch.set_for_context(False)
        try:
            return await call_next(context)
        finally:
            _brocardi_switch.reset(token)


def _checked_tags(tags: Iterable[str] | None, argument: str) -> set[str]:
    if tags is None:
        return set()
    if isinstance(tags, str):
        raise TypeError(f"{argument} takes a collection of tags, not the string {tags!r}")
    chosen = set(tags)
    unknown = sorted(chosen - VOCABULARY.keys())
    if unknown:
        raise ValueError(
            f"{argument}: unknown tags {unknown}; the vocabulary is in "
            f"mcp_legal_it/tool_taxonomy.py (docs/tool-tags.md): {sorted(VOCABULARY)}"
        )
    return chosen


def crea_server(
    include_tags: Iterable[str] | None = None,
    exclude_tags: Iterable[str] | None = None,
    brocardi: bool = True,
    *,
    name: str = "Legal IT",
    prompts: bool = True,
) -> FastMCP:
    """Build a FastMCP server that exposes only the selected tools.

    The stock server (``mcp``) is mounted into a new one and narrowed with
    visibility filters, so the tools keep their names, signatures, annotations,
    ``_meta`` and middleware; a tool left out is absent from ``list_tools`` and a
    call to it is answered as an unknown tool. The stock server is not changed.

    Args:
        include_tags: keep only the tools carrying at least one of these tags
            (``None``: every tool; an empty collection is refused, since it would
            select nothing). Tags are listed in ``docs/tool-tags.md``.
        exclude_tags: then drop every tool carrying one of these tags. Excluding
            ``brocardi`` drops every tool that can show Brocardi content,
            ``cite_law`` included; to keep those tools without Brocardi, use
            ``brocardi=False``.
        brocardi: ``False`` hides the ``solo_brocardi`` tools and runs every call
            of this server with Brocardi off, so no request reaches brocardi.it and
            the mixed tools say Brocardi is off. ``True`` follows the process
            (``LEGAL_BROCARDI=off`` in the environment still wins).
        name: the server name reported to clients.
        prompts: keep the prompts and the ``legal://`` resources (they are not
            tagged, so the tag filters never touch them). The prompts name tools:
            a prompt may suggest a tool the subset left out.

    The server's instructions are the stock ones without the tools it does not
    list, so the model is never sent to a tool it cannot call.

    The process-level switches still apply underneath, because they act on the
    stock server: ``LEGAL_PROFILE``, ``LEGAL_PREVIGENTE=off`` and
    ``LEGAL_BROCARDI=off`` can only narrow what this factory selects.

    Example::

        from mcp_legal_it.server import crea_server

        fonti = crea_server(include_tags={"normativa", "giurisprudenza"}, brocardi=False)
        fonti.run()  # or mount it: my_server.mount(fonti, namespace="legal")
    """
    if include_tags is not None and not set(include_tags):
        raise ValueError(
            "include_tags is empty, which would select no tool: pass None to keep every tool"
        )
    include = _checked_tags(include_tags, "include_tags")
    exclude = _checked_tags(exclude_tags, "exclude_tags")
    server = FastMCP(name, version=package_version(), instructions=_STOCK_INSTRUCTIONS)
    server.mount(mcp)
    if include:
        server.enable(tags=include, only=True)
    if exclude:
        server.disable(tags=exclude)
    if not brocardi:
        server.disable(tags={_brocardi_switch.TAG_SOLO})
        server.add_middleware(_BrocardiOffMiddleware())
    if prompts:
        server.enable(components=_PROMPTS_AND_RESOURCES)
    else:
        server.disable(components=_PROMPTS_AND_RESOURCES)
    server.instructions = _instructions_for(_visible_tool_names(server))
    return server
