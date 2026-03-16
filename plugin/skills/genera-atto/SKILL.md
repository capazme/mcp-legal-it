---
name: genera-atto
description: Genera atti legali italiani (citazione, ricorso, decreto ingiuntivo, precetto, procura, relata, attestazione, pignoramento, sfratto, preventivo). Usa quando l'utente chiede di redigere, generare, preparare o creare un atto, documento legale, bozza processuale, relata di notifica, attestazione di conformita, procura alle liti, preventivo legale o fascicolo digitale. Copre 100 tipi di atti tra giudiziari, stragiudiziali, esecutivi, PCT e privacy.
---

# Genera Atto Legale

Workflow guidato per la redazione di atti legali italiani. Copre 100 tipi di documenti organizzati in 10 categorie.

## Workflow

### 1. Identificazione tipo atto

Determina il tipo di atto richiesto:

- Se l'utente specifica un atto → chiama `genera_modello_atto(tipo_atto="nome_specifico")`
- Se l'utente descrive una situazione → chiama `genera_modello_atto(tipo_atto="cerca", parametri={"query": "termine"})`
- Se l'utente vuole esplorare → chiama `lista_categorie_atti()` e poi `genera_modello_atto(tipo_atto="catalogo")`

### 2. Raccolta dati

Dal risultato di `genera_modello_atto`:
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
Leggi la resource indicata, compila i placeholder `{campo}` con i dati, includi i calcoli.

**Se `disponibile_da_fase` > 1:**
Usa il tool suggerito nelle `istruzioni` come approssimazione.

### 5. Verifica norme

Per ogni norma citata nell'atto, chiama `cite_law` per verificare il testo vigente.

### 6. Output

Presenta l'atto completo con:
- Testo dell'atto formattato
- Tabella riepilogativa dei calcoli (se presenti)
- Riferimenti normativi verificati
- Checklist allegati necessari
- Avvertenze

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

## Tool utilizzati

- `genera_modello_atto` — entry point, metadati e routing
- `lista_categorie_atti` — panoramica categorie
- `cite_law` — verifica norme
- Tool di calcolo specifici per tipo atto (CU, interessi, parcelle, scadenze)
- Tool di generazione atti (decreto_ingiuntivo, precetto, procura, relata, etc.)
