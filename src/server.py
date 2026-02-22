"""MCP Legal IT — 60+ Italian legal calculation tools + legal citation scraping."""

from fastmcp import FastMCP

mcp = FastMCP(
    "Legal IT",
    instructions="""\
STRUMENTI DISPONIBILI (13 categorie):
1. RIVALUTAZIONE MONETARIA: rivalutazione_monetaria, rivalutazione_mensile, adeguamento_canone_locazione, calcolo_inflazione, rivalutazione_tfr, interessi_vari_capitale_rivalutato, lettera_adeguamento_canone, calcolo_devalutazione, rivalutazione_storica, variazioni_istat, rivalutazione_annuale_media
2. INTERESSI E TASSI: interessi_legali, interessi_mora, interessi_tasso_fisso, calcolo_ammortamento, verifica_usura, interessi_acconti, calcolo_maggior_danno, interessi_corso_causa, calcolo_surroga_mutuo, calcolo_taeg
3. SCADENZE E TERMINI: scadenza_processuale, termini_processuali_civili, termini_separazione_divorzio, scadenze_impugnazioni, scadenze_multe, termini_memorie_repliche, termini_procedimento_semplificato, termini_183_190_cpc, termini_esecuzioni, termini_deposito_atti_appello, termini_deposito_ctu
4. ATTI GIUDIZIARI: contributo_unificato, diritti_copia, pignoramento_stipendio, decreto_ingiuntivo, tassazione_atti, note_iscrizione_ruolo, fascicolo_di_parte, procura_alle_liti, relata_notifica_pec, note_trattazione_scritta, sfratto_morosita, atto_di_precetto, nota_precisazione_credito, dichiarazione_553_cpc, testimonianza_scritta, cerca_ufficio_giudiziario
5. PARCELLE AVVOCATI: parcella_avvocato_civile, parcella_avvocato_penale, parcella_stragiudiziale, parcella_volontaria_giurisdizione, fattura_avvocato, nota_spese, preventivo_civile, preventivo_stragiudiziale, spese_trasferta_avvocati, modello_notula, calcolo_notula_penale
6. PARCELLE PROFESSIONISTI: fattura_professionista, compenso_ctu, spese_mediazione, compenso_orario, ritenuta_acconto, compenso_curatore_fallimentare, compenso_delegati_vendite, compenso_mediatore_familiare, fattura_enasarco, ricevuta_prestazione_occasionale, tariffe_mediazione
7. RISARCIMENTO DANNI: danno_biologico_micro, danno_biologico_macro, danno_parentale, menomazioni_plurime, risarcimento_inail, danno_non_patrimoniale, equo_indennizzo
8. DIRITTO PENALE: aumenti_riduzioni_pena, conversione_pena, fine_pena, prescrizione_reato, pena_concordata
9. PROPRIETÀ E SUCCESSIONI: calcolo_eredita, imposte_successione, calcolo_usufrutto, calcolo_imu, imposte_compravendita, pensione_reversibilita, grado_parentela, calcolo_valore_catastale, cedolare_secca, imposta_registro_locazioni, spese_condominiali
10. INVESTIMENTI: rendimento_bot, rendimento_btp, pronti_termine, rendimento_buoni_postali, confronto_investimenti
11. DICHIARAZIONE REDDITI: calcolo_irpef, regime_forfettario, calcolo_tfr, ravvedimento_operoso, assegno_unico, detrazione_figli, detrazione_coniuge, detrazione_lavoro_dipendente, detrazione_pensione, detrazione_assegno_coniuge, detrazione_canone_locazione, acconto_irpef, acconto_cedolare_secca, rateizzazione_imposte
12. VARIE: codice_fiscale, decodifica_codice_fiscale, verifica_iban, conta_giorni, scorporo_iva, decurtazione_punti_patente, tasso_alcolemico, prescrizione_diritti, calcolo_tempo_trascorso, verifica_partita_iva, calcolo_eta_anagrafica, ricerca_codici_ateco
13. CONSULTAZIONE NORMATIVA: cite_law, fetch_law_article, fetch_law_annotations, cerca_brocardi, download_law_pdf
14. GIURISPRUDENZA CASSAZIONE (Italgiure): leggi_sentenza, cerca_giurisprudenza, giurisprudenza_su_norma, ultime_pronunce
15. PROVVEDIMENTI GARANTE PRIVACY (GPDP): cerca_provvedimenti_garante, leggi_provvedimento_garante, ultimi_provvedimenti_garante

LEGAL GROUNDING PROTOCOL: Prima di citare o ragionare su QUALSIASI norma, chiama cite_law() per ottenere il testo vigente da Normattiva/EUR-Lex. Per approfondimenti dottrinali e giurisprudenziali, usa cerca_brocardi() che restituisce ratio legis, spiegazione, massime con riferimenti strutturati alla Cassazione. Mai usare la conoscenza pregressa per il contenuto di articoli o numeri di sentenza. Eccezione: i tool di calcolo applicano le norme internamente, non richiedono cite_law.

WORKFLOW DISCOVERY → LETTURA UFFICIALE:
Il web search è AMMESSO e UTILE nella fase di discovery (trovare identificatori di documenti).
Dopo la discovery, usa SEMPRE i tool ufficiali per leggere il testo completo — mai il web per il contenuto normativo.

Regole per tipo di documento:
- NORME: se conosci il riferimento → cite_law/fetch_law_article direttamente. Se lo devi trovare → web search per individuare numero/anno/decreto, poi cite_law.
- SENTENZE CASSAZIONE con numero noto (es. "Cass. n. 10787/2024") → leggi_sentenza IMMEDIATAMENTE, NON web search. Se ignori il numero → cerca_giurisprudenza per trovarlo, poi leggi_sentenza.
- PROVVEDIMENTI GARANTE con docweb noto → leggi_provvedimento_garante direttamente. Se ignori il docweb → cerca_provvedimenti_garante o web search per trovare il docweb ID, poi leggi_provvedimento_garante.
- ALTRI DOCUMENTI (circolari, pareri ministeri, atti AGCM, ecc.) → web search per discovery è il metodo corretto; cita la fonte ufficiale nella risposta.

WORKFLOW COMUNI:
Sinistro: danno_biologico_micro/macro → danno_non_patrimoniale → rivalutazione_monetaria → interessi_legali
Recupero credito: interessi_mora → rivalutazione_monetaria → decreto_ingiuntivo → parcella_avvocato_civile
Causa civile: contributo_unificato → scadenza_processuale → scadenze_impugnazioni → preventivo_civile
Successione: calcolo_eredita → imposte_successione → imposte_compravendita → calcolo_valore_catastale
Analisi norma: cite_law → cerca_brocardi → cerca_giurisprudenza/giurisprudenza_su_norma → leggi_sentenza
Privacy/GDPR: cite_law (art. GDPR) → cerca_provvedimenti_garante → leggi_provvedimento_garante

REGOLE OUTPUT: Importi con 2 decimali e separatore migliaia (€ 1.234,56). Date in formato GG/MM/AAAA. Segnalare quando un risultato è INDICATIVO. Non arrotondare risultati intermedi.
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

