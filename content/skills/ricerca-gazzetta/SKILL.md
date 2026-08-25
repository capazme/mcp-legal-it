---
name: ricerca-gazzetta
description: Usa quando l'utente chiede cosa è uscito in Gazzetta Ufficiale, il testo di un decreto appena pubblicato o il sommario di una GU — novità per serie, ricerca parametrica, testo as-published e PDF.
tools: [cerca_gazzetta_ufficiale, cite_law, leggi_atto_gazzetta, scarica_pdf_gazzetta, sommario_gazzetta, ultime_gazzette]
prompt: {"name": "ricerca_gazzetta", "description": "Ricerca e lettura di atti pubblicati in Gazzetta Ufficiale: novità per serie, ricerca parametrica, testo as-published + PDF ufficiale", "args": [{"name": "tema", "type": "str"}, {"name": "serie", "type": "str", "default": "serie_generale"}]}
---

# Ricerca Gazzetta

Esegui una ricerca sulla Gazzetta Ufficiale per il tema indicato.

## Dati richiesti

- **tema** — il tema da cercare in Gazzetta Ufficiale. Se non fornito, chiedilo.
- **serie** (opzionale, default `serie_generale`) — filtro serie: serie_generale / unione_europea / regioni / corte_costituzionale / parte_seconda / contratti / concorsi.

## Workflow

### Fase 1 — Novità o ricerca mirata
Per le ultime pubblicazioni, chiama `ultime_gazzette(serie=<serie>)` (fonte: feed RSS).
Per una ricerca mirata, chiama `cerca_gazzetta_ufficiale(titolo=<tema>, serie=<serie>)`
(usa anche `testo=`, `tipo_provvedimento=`, `emettitore=`, `materia=`, `anno_da=`, `anno_a=` se utile).

### Fase 2 — Lettura atto
Presenta i risultati e, per l'atto scelto, chiama
`leggi_atto_gazzetta(codice_redazionale, data_pubblicazione, serie=<serie>)` per metadati ELI +
testo as-published. Per il PDF ufficiale firmato usa `scarica_pdf_gazzetta(...)`.
Per l'intero sommario di un numero di GU usa `sommario_gazzetta(numero_gazzetta, data_pubblicazione)`.

### Fase 3 — Testo vigente vs as-published
La Gazzetta dà il testo ORIGINALE come pubblicato. Per il testo CONSOLIDATO/VIGENTE chiama
`cite_law(reference)` (Normattiva). Distingui sempre le due cose nella risposta.

## Regole

- La Gazzetta è la fonte dell'atto come pubblicato (con PDF/ELI citabile); Normattiva è la fonte del
  vigente. Non confonderle.
- Usare i tool, mai estremi a memoria.
