"""MCP Legal IT — 147 Italian legal tools: calculations, normative citations, case law."""

import os

from fastmcp import FastMCP

mcp = FastMCP(
    "Legal IT",
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
- GIURISPRUDENZA: sentenze Cassazione (Italgiure), ricerca full-text
- GARANTE PRIVACY: provvedimenti GPDP, ricerca sanzioni, linee guida

REGOLE: cite_law() PRIMA di citare norme. leggi_sentenza() DIRETTO per sentenze note.
OUTPUT: € 1.234,56 | GG/MM/AAAA | segnalare INDICATIVO se stimato.

WORKFLOW:
Sinistro → danno_biologico_* → danno_non_patrimoniale → rivalutazione_monetaria → interessi_legali
Credito → interessi_mora → rivalutazione_monetaria → decreto_ingiuntivo → parcella_avvocato_civile
Norma → cite_law → cerca_brocardi → cerca_giurisprudenza → leggi_sentenza
Privacy → cite_law (GDPR) → cerca_provvedimenti_garante → leggi_provvedimento_garante
""",
)

# Import all tool modules — each registers its tools via @mcp.tool()
from src.tools import (  # noqa: E402, F401
    rivalutazioni_istat,
    tassi_interessi,
    scadenze_termini,
    atti_giudiziari,
    fatturazione_avvocati,
    parcelle_professionisti,
    risarcimento_danni,
    diritto_penale,
    proprieta_successioni,
    investimenti,
    dichiarazione_redditi,
    varie,
    legal_citations,
    italgiure,
    gpdp,
)

from src import prompts, resources  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Profile-based tool filtering (for Desktop/Browser — lighter context)
# Usage: LEGAL_PROFILE=sinistro python -m src.server
# Default: "full" (all 147 tools — for Claude Code with Tool Search)
# ---------------------------------------------------------------------------
_PROFILES: dict[str, set[str]] = {
    "sinistro": {"danni", "rivalutazione", "interessi", "normativa", "giurisprudenza", "sinistro"},
    "credito": {"interessi", "rivalutazione", "parcelle_avv", "normativa", "giurisprudenza", "credito"},
    "penale": {"penale", "normativa", "giurisprudenza"},
    "fiscale": {"fiscale", "proprieta", "utility"},
    "normativa": {"normativa", "giurisprudenza", "privacy"},
    "studio": {"scadenze", "giudiziario", "parcelle_avv", "parcelle_prof"},
}

_profile = os.environ.get("LEGAL_PROFILE", "full")
if _profile != "full" and _profile in _PROFILES:
    mcp.include_tags = _PROFILES[_profile]

