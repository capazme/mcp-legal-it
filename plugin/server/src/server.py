"""MCP Legal IT — 177 Italian legal tools: calculations, normative citations, case law (Cassazione, CeRDEF, TAR/CdS, CGUE), GDPR compliance, CONSOB, document generation."""

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
- GIURISPRUDENZA: sentenze Cassazione (Italgiure, archivio 2020+). Strategia: esplora → filtra → leggi
- GIURISPRUDENZA TRIBUTARIA: sentenze CTP/CTR/CGT, Cassazione tributaria, IVA, IRES, accertamento, riscossione (CeRDEF)
- GARANTE PRIVACY: provvedimenti GPDP, ricerca sanzioni, linee guida
- GDPR/PRIVACY COMPLIANCE: informative privacy (art. 13-14), cookie policy, DPA (art. 28), registro trattamenti (art. 30), DPIA (art. 35), data breach (art. 33-34), sanzioni (art. 83), base giuridica (art. 6)
- CONSOB: delibere, provvedimenti, regolamenti mercati finanziari, intermediari, abusi di mercato
- GIUSTIZIA AMMINISTRATIVA: sentenze TAR, Consiglio di Stato, appalti, urbanistica, PA, edilizia, accesso atti
- GIURISPRUDENZA UE: sentenze CGUE, Corte di Giustizia UE, Tribunale UE, rinvio pregiudiziale, conclusioni AG, ECLI
- REDAZIONE ATTI: genera_modello_atto() per catalogo 100 tipi atti (DI, precetto, procura, relata, attestazione, citazione, pignoramento, preventivo, privacy)

REGOLE: cite_law() PRIMA di citare norme. leggi_sentenza() DIRETTO per sentenze note.
OUTPUT: € 1.234,56 | GG/MM/AAAA | segnalare INDICATIVO se stimato.

WORKFLOW:
Sinistro → danno_biologico_* → danno_non_patrimoniale → rivalutazione_monetaria → interessi_legali
Credito → interessi_mora → rivalutazione_monetaria → decreto_ingiuntivo → parcella_avvocato_civile
Norma → cite_law → cerca_brocardi → giurisprudenza_su_norma → leggi_sentenza
Giurisprudenza → cerca_giurisprudenza(modalita="esplora") → cerca_giurisprudenza(filtri) → leggi_sentenza
Privacy → cite_law (GDPR) → cerca_provvedimenti_garante → leggi_provvedimento_garante
Compliance GDPR → analisi_base_giuridica → verifica_necessita_dpia → genera_registro_trattamenti → genera_informativa_privacy → genera_dpa
Data Breach → valutazione_data_breach → genera_notifica_data_breach → calcolo_sanzione_gdpr
CONSOB → cerca_delibere_consob → leggi_delibera_consob
Tributario → cerca_giurisprudenza_tributaria → cerdef_leggi_provvedimento → cite_law
Amministrativo → cerca_giurisprudenza_amministrativa → leggi_provvedimento_amm → cite_law
Diritto UE → cerca_giurisprudenza_cgue → leggi_sentenza_cgue → cite_law
Redazione atti → genera_modello_atto(tipo) → [raccolta dati] → [tool calcolo] → [composizione atto]
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
    cerdef,
    giustizia_amm,
    cgue,
    giurisprudenza_unificata,
    privacy_gdpr,
    modelli_atti,
    procedura_civile,
)

from src import prompts, resources  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Profile-based tool filtering (for Desktop/Browser — lighter context)
# Usage: LEGAL_PROFILE=sinistro python -m src.server
# Default: "full" (all tools — for Claude Code with Tool Search)
# ---------------------------------------------------------------------------
_PROFILES: dict[str, set[str]] = {
    "sinistro": {"danni", "rivalutazione", "interessi", "normativa", "giurisprudenza", "sinistro"},
    "credito": {"interessi", "rivalutazione", "parcelle_avv", "normativa", "giurisprudenza", "credito"},
    "penale": {"penale", "normativa", "giurisprudenza"},
    "fiscale": {"fiscale", "proprieta", "utility", "consob", "investimenti", "crisi_impresa", "societario"},
    "normativa": {"normativa", "giurisprudenza", "giurisprudenza_amm", "giurisprudenza_ue", "privacy", "consob"},
    "privacy": {"privacy", "normativa", "giurisprudenza"},
    "studio": {"scadenze", "giudiziario", "parcelle_avv", "parcelle_prof", "investimenti", "lavoro"},
    "redattore": {"atti", "giudiziario", "parcelle_avv", "scadenze", "normativa"},
}

_profile = os.environ.get("LEGAL_PROFILE", "full")
if _profile != "full" and _profile in _PROFILES:
    mcp.include_tags = _PROFILES[_profile]

