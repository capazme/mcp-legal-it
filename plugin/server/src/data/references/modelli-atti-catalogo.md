CATALOGO MODELLI ATTI LEGALI — 100 TIPI DISPONIBILI
Per generare un atto: chiama genera_modello_atto(tipo_atto="nome_tipo") per i metadati.

═══════════════════════════════════════════════════════════
CATEGORIE E TIPI
═══════════════════════════════════════════════════════════

ATTI INTRODUTTIVI (11 tipi)
  Tier 1 (tool diretto): decreto_ingiuntivo_ordinario, decreto_ingiuntivo_professionale,
    decreto_ingiuntivo_condominiale, decreto_ingiuntivo_cambiale, sfratto_morosita
  Tier 2 (enhance): decreto_ingiuntivo_fatture, decreto_ingiuntivo_retribuzioni
  Tier 3 (resource): citazione_ordinaria, ricorso_giudice_pace, ricorso_semplificato,
    atto_appello, opposizione_decreto_ingiuntivo

ESECUZIONE (16 tipi)
  Tier 1: atto_di_precetto, nota_precisazione_credito, dichiarazione_553_cpc
  Tier 3: ricerca_beni_492bis, pignoramento_presso_terzi, pignoramento_immobiliare,
    avviso_543_5_cpc, cessazione_obbligo_custodia, ordinanza_assegnazione_somme,
    ordinanza_assegnazione_crediti, ordinanza_assegnazione_543_cpc, proroga_567_cpc,
    vendita_mobili, vendita_immobili, rinuncia_esecuzione, rinuncia_intervento,
    perdita_efficacia_pignoramento, assegnazione_510_cpc, termine_efficacia_titolo

NOTIFICHE (9 tipi)
  Tier 1: relata_pec_generica
  Tier 2: relata_pec_decreto_ingiuntivo, relata_pec_opposizione_di, relata_pec_appello,
    relata_pec_sentenza_giudicato, relata_pec_penale, relata_unep, relata_pat
  Tier 3: relata_posta

ATTESTAZIONI (11 tipi)
  Tier 1: attestazione_estratto, attestazione_copia_informatica, attestazione_duplicato
  Tier 2: attestazione_margine_fascicolo, attestazione_separata_fascicolo,
    attestazione_margine_scanner, attestazione_separata_scanner, attestazione_archivio_zip,
    attestazione_stampe_pec, attestazione_composito_di, attestazione_composito_decreto

PROCURE (8 tipi)
  Tier 1: procura_generale, procura_speciale, procura_appello
  Tier 2: procura_mediazione, procura_mediazione_sostanziale, procura_negoziazione,
    procura_arbitrato, procura_incarico_professionale

STRAGIUDIZIALE (8 tipi)
  Tier 1: sollecito_pagamento
  Tier 2: sollecito_formale_mora, sollecito_prima_richiesta, sollecito_post_sentenza
  Tier 3: invito_negoziazione, adesione_negoziazione, lettera_adeguamento_istat,
    richiesta_nominativi_morosi

ISTANZE (6 tipi)
  Tier 3: istanza_esecutorieta, certificato_giudicato, istanza_giudicato,
    ricorso_intervento, avviso_impugnazione, avviso_opposizione_di

PCT (2 tipi)
  Tier 3: nota_deposito_pct, nomina_ctp

PREVENTIVI (17 tipi)
  Tier 1: preventivo_civile, preventivo_stragiudiziale, preventivo_volontaria_giurisdizione
  Tier 4: preventivo_mediazione, preventivo_decreto_ingiuntivo, preventivo_opposizione_di,
    preventivo_precetto, preventivo_pignoramento, preventivo_esecuzione_mobiliare,
    preventivo_esecuzione_immobiliare, preventivo_atp, preventivo_giudice_pace,
    preventivo_cautelari, preventivo_lavoro, preventivo_appello, preventivo_penale,
    preventivo_sfratto

PRIVACY (8 tipi)
  Tier 1: informativa_privacy_art13, informativa_cookie, informativa_dipendenti,
    informativa_videosorveglianza, dpa_art28, registro_trattamenti, dpia,
    notifica_data_breach

═══════════════════════════════════════════════════════════
TIER E ROUTING
═══════════════════════════════════════════════════════════

Tier 1 — Tool diretto (27 tipi): l'atto è generato chiamando un tool esistente.
Tier 2 — Tool enhance (25 tipi): richiede enhancement dei tool esistenti (Fase 2).
Tier 3 — Resource + LLM (34 tipi): l'LLM compone l'atto leggendo un modello da resource (Fase 3).
Tier 4 — Preventivo parametrico (14 tipi): pianificato per la Fase 4 via preventivo_procedura (NON ancora disponibile); usare preventivo_civile come approssimazione nel frattempo.

═══════════════════════════════════════════════════════════
WORKFLOW TIPO
═══════════════════════════════════════════════════════════

1. genera_modello_atto(tipo_atto="decreto_ingiuntivo_ordinario")
   → Restituisce: tool_diretto="decreto_ingiuntivo", campi, calcoli necessari
2. Raccogli i campi obbligatori dall'utente
3. Chiama i tool_calcolo (contributo_unificato, parcella_avvocato_civile, ...)
4. Chiama il tool_diretto o leggi la resource_modello
5. Verifica norme con cite_law()
6. Presenta l'atto completo con calcoli e checklist
