---
name: analisi-costituzionale
description: Analisi delle pronunce della Corte Costituzionale su un tema o una norma — ricerca, lettura delle pronunce chiave e sintesi con i parametri costituzionali invocati. Usa quando l'utente chiede sentenze della Consulta, questioni di legittimità costituzionale o pronunce additive/interpretative.
tools: [cerca_pronuncia_costituzionale, cite_law, leggi_pronuncia_costituzionale, pronunce_cost_su_norma]
prompt: {"name": "analisi_costituzionale", "description": "Analisi delle pronunce della Corte Costituzionale su un tema: ricerca, lettura sentenze/ordinanze chiave, parametri costituzionali invocati", "args": [{"name": "tema", "type": "str"}, {"name": "tipo", "type": "str", "default": ""}]}
---

# Analisi Costituzionale

Esegui un'analisi delle pronunce della Corte Costituzionale sul tema indicato.

## Dati richiesti

- **tema** — il tema costituzionale da analizzare. Se non fornito, chiedilo.
- **tipo** (opzionale) — filtro tipo: sentenza / ordinanza (vuoto = entrambi).

## Workflow

### Fase 1 — Ricerca pronunce
Chiama `cerca_pronuncia_costituzionale(query=<tema>, tipo=<tipo>)` per individuare le
pronunce rilevanti (numero/anno, ECLI, tipo, snippet).
Se il tema riguarda un parametro costituzionale o una norma specifica (es. "art. 3 Costituzione",
"art. 23 legge 87/1953"), chiama `pronunce_cost_su_norma(riferimento="art. ...")` per le pronunce
che lo invocano come parametro.

### Fase 2 — Lettura pronunce chiave
Presenta i risultati in tabella e chiedi all'utente quali approfondire (human-in-the-loop).
Per ciascuna scelta, chiama `leggi_pronuncia_costituzionale(numero, anno)` per epigrafe, testo,
dispositivo, collegio ed ECLI.

### Fase 3 — Fondamento normativo
Per le norme oggetto/parametro citate nelle pronunce, chiama `cite_law(reference)` per il testo
vigente dalla fonte ufficiale.

### Fase 4 — Sintesi
Produci una sintesi che includa: principio affermato dalla Consulta, tipo di decisione
(accoglimento / rigetto / inammissibilità / interpretativa / additiva), parametri costituzionali
invocati, ed effetti sulla norma impugnata.

## Regole

- Usare esclusivamente `cerca_pronuncia_costituzionale` / `leggi_pronuncia_costituzionale` /
  `pronunce_cost_su_norma` — mai numeri di pronuncia a memoria né web search.
- Citare le pronunce con gli estremi ufficiali (Corte cost., sent./ord. n./anno, ECLI).
