---
name: genera-atto
description: Genera atti legali italiani (citazione, ricorso, decreto ingiuntivo, precetto, procura, relata, attestazione, pignoramento, sfratto, preventivo). Usa quando l'utente chiede di redigere, generare, preparare o creare un atto, documento legale, bozza processuale, relata di notifica, attestazione di conformita, procura alle liti, preventivo legale o fascicolo digitale. Copre 100 tipi di atti tra giudiziari, stragiudiziali, esecutivi, PCT e privacy.
argument-hint: "[tipo atto o descrizione situazione]"
allowed-tools: mcp__legal-it__genera_modello_atto, mcp__legal-it__lista_categorie_atti, mcp__legal-it__cite_law, mcp__legal-it__esporta_atto_docx, mcp__legal-it__contributo_unificato, mcp__legal-it__interessi_mora, mcp__legal-it__interessi_legali, mcp__legal-it__rivalutazione_monetaria, mcp__legal-it__variazioni_istat, mcp__legal-it__conta_giorni, mcp__legal-it__scadenza_processuale, mcp__legal-it__scadenze_impugnazioni, mcp__legal-it__decreto_ingiuntivo, mcp__legal-it__atto_di_precetto, mcp__legal-it__pignoramento_stipendio, mcp__legal-it__sfratto_morosita, mcp__legal-it__procura_alle_liti, mcp__legal-it__relata_notifica_pec, mcp__legal-it__attestazione_conformita, mcp__legal-it__calcolo_hash, mcp__legal-it__dichiarazione_553_cpc, mcp__legal-it__nota_precisazione_credito, mcp__legal-it__sollecito_pagamento, mcp__legal-it__spese_mediazione, mcp__legal-it__calcolo_valore_catastale, mcp__legal-it__compenso_ctu, mcp__legal-it__parcella_avvocato_civile, mcp__legal-it__preventivo_civile, mcp__legal-it__preventivo_stragiudiziale, mcp__legal-it__preventivo_volontaria_giurisdizione, mcp__legal-it__genera_informativa_privacy, mcp__legal-it__genera_informativa_cookie, mcp__legal-it__genera_informativa_dipendenti, mcp__legal-it__genera_informativa_videosorveglianza, mcp__legal-it__genera_dpa, mcp__legal-it__genera_dpia, mcp__legal-it__genera_registro_trattamenti, mcp__legal-it__genera_notifica_data_breach, mcp__legal-it__valutazione_data_breach, ReadMcpResourceTool
---

# Genera Atto Legale

Workflow guidato per la redazione di atti legali italiani. Copre 100 tipi di documenti organizzati in 10 categorie.

## Workflow

### 1. Identificazione tipo atto

Determina il tipo di atto richiesto:

- Se l'utente specifica un atto → chiama `legal-it:genera_modello_atto(tipo_atto="nome_specifico")`
- Se l'utente descrive una situazione → chiama `legal-it:genera_modello_atto(tipo_atto="cerca", parametri={"query": "termine"})`
- Se l'utente vuole esplorare → chiama `legal-it:lista_categorie_atti()` e poi `legal-it:genera_modello_atto(tipo_atto="catalogo")`

### 2. Raccolta dati

Dal risultato di `legal-it:genera_modello_atto`:
- Verifica `campi_mancanti` — chiedi all'utente i dati mancanti
- Spiega i `campi_opzionali` se pertinenti
- Comunica le `avvertenze` all'utente

### 3. Calcoli

Per ogni tool in `tool_calcolo`:
- Chiama il tool con i dati raccolti
- Annota i risultati (CU, interessi, compensi, scadenze)

### 4. Generazione atto

In base al routing restituito:

**Se `tool_diretto` presente:**
Chiama il tool indicato con i parametri dell'utente + `parametri_fissi` dal catalogo.

**Se `resource_modello` presente:**
Leggi la resource indicata con ReadMcpResourceTool (server `legal-it`, uri = `resource_modello`), compila i placeholder `{campo}` con i dati, includi i calcoli.

**Se `disponibile_da_fase` > 1:**
Usa il tool suggerito nelle `istruzioni` come approssimazione.

### 5. Verifica norme

Per ogni norma citata nell'atto, chiama `legal-it:cite_law` per verificare il testo vigente.

### 6. Output

Presenta l'atto completo con:
- Testo dell'atto formattato
- Tabella riepilogativa dei calcoli (se presenti)
- Riferimenti normativi verificati
- Checklist allegati necessari
- Avvertenze
- Su richiesta, esporta l'atto in .docx con `esporta_atto_docx(testo=..., titolo=..., autore=...)` e comunica il percorso file restituito.

## Mapping parole chiave → tipo_atto

| L'utente dice... | tipo_atto |
|---|---|
| decreto ingiuntivo, DI, ingiunzione | decreto_ingiuntivo_ordinario |
| precetto, intimazione pagamento | atto_di_precetto |
| sfratto, morosita locazione | sfratto_morosita |
| procura, mandato avvocato | procura_generale |
| attestazione, conformita PCT | attestazione_estratto |
| relata, notifica PEC | relata_pec_generica |
| sollecito, messa in mora | sollecito_pagamento |
| citazione, atto introduttivo | citazione_ordinaria |
| pignoramento, esecuzione | pignoramento_presso_terzi |
| preventivo, costi causa | preventivo_civile |
| informativa privacy | informativa_privacy_art13 |
