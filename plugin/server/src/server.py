"""MCP Legal IT — 221 Italian legal tools: calculations, normative citations, case law (Cassazione, Corte Costituzionale, CeRDEF, TAR/CdS, CGUE), Gazzetta Ufficiale, parliamentary bills (Senato/Camera open data), EU→IT transposition, GDPR compliance, CONSOB, document generation."""

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
- GIUSTIZIA AMMINISTRATIVA: sentenze TAR, Consiglio di Stato, appalti, urbanistica, PA, edilizia, accesso atti
- GIURISPRUDENZA UE: sentenze CGUE, Corte di Giustizia UE, Tribunale UE, rinvio pregiudiziale, conclusioni AG, ECLI
- ATTUAZIONE UE→IT: get_italian_implementation()/elenco_misure_nazionali() per le misure nazionali di recepimento di una direttiva, get_eu_basis() per la base UE di un atto italiano (CELLAR/SPARQL)
- REDAZIONE ATTI: genera_modello_atto() per catalogo 100 tipi atti (DI, precetto, procura, relata, attestazione, citazione, pignoramento, preventivo, privacy)
- RECUPERO CREDITI SERIALE: genera_procura_liti_docx() procura ex art. 83 c.p.c. pronta-firma; genera_quotazione_docx() lettera quotazione compensi D.M. 55/2014 (monitorio/esecuzione/opposizione) con accettazione cliente

REGOLE: cite_law() PRIMA di citare norme. leggi_sentenza() DIRETTO per sentenze note.
OUTPUT: € 1.234,56 | GG/MM/AAAA | segnalare INDICATIVO se stimato.

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
Analisi fornitori → verifica_partita_iva_vies → genera_report_fornitori → genera_dpa (nomine per i responsabili senza DPA)
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
    corte_cost,
    gazzetta,
    parlamento,
    orientamento,
    eu_implementation,
    procure_quotazioni,
    analisi_fornitori,
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
    "normativa": {"normativa", "giurisprudenza", "giurisprudenza_amm", "giurisprudenza_ue", "privacy", "consob", "costituzionale"},
    "privacy": {"privacy", "normativa", "giurisprudenza"},
    "studio": {"scadenze", "giudiziario", "parcelle_avv", "parcelle_prof", "investimenti", "lavoro"},
    "redattore": {"atti", "giudiziario", "parcelle_avv", "scadenze", "normativa"},
    "cowork": {"normativa", "giurisprudenza", "privacy", "parcelle_avv"},
}

_profile = os.environ.get("LEGAL_PROFILE", "full")
if _profile != "full" and _profile in _PROFILES:
    mcp.include_tags = _PROFILES[_profile]

