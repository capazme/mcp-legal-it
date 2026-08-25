---
name: ricerca-gazzetta
description: Usa quando l'utente chiede cosa è uscito in Gazzetta Ufficiale, il testo di un decreto appena pubblicato o il sommario di una GU — novità per serie, ricerca parametrica, testo as-published e PDF.
---

# Ricerca Gazzetta

Esegui una ricerca sulla Gazzetta Ufficiale per il tema indicato.

## Dati richiesti

- **tema** — il tema da cercare in Gazzetta Ufficiale. Se non fornito, chiedilo.
- **serie** (opzionale, default `serie_generale`) — filtro serie: serie_generale / unione_europea / regioni / corte_costituzionale / parte_seconda / contratti / concorsi.

## Workflow

### Fase 1 — Novità o ricerca mirata
Per le ultime pubblicazioni, chiama `legal-it:ultime_gazzette(serie=<serie>)` (fonte: feed RSS).
Per una ricerca mirata, chiama `legal-it:cerca_gazzetta_ufficiale(titolo=<tema>, serie=<serie>)`
(usa anche `testo=`, `tipo_provvedimento=`, `emettitore=`, `materia=`, `anno_da=`, `anno_a=` se utile).

### Fase 2 — Lettura atto
Presenta i risultati e, per l'atto scelto, chiama
`legal-it:leggi_atto_gazzetta(codice_redazionale, data_pubblicazione, serie=<serie>)` per metadati ELI +
testo as-published. Per il PDF ufficiale firmato usa `legal-it:scarica_pdf_gazzetta(...)`.
Per l'intero sommario di un numero di GU usa `legal-it:sommario_gazzetta(numero_gazzetta, data_pubblicazione)`.

### Fase 3 — Testo vigente vs as-published
La Gazzetta dà il testo ORIGINALE come pubblicato. Per il testo CONSOLIDATO/VIGENTE chiama
`legal-it:cite_law(reference)` (Normattiva). Distingui sempre le due cose nella risposta.

## Regole

- La Gazzetta è la fonte dell'atto come pubblicato (con PDF/ELI citabile); Normattiva è la fonte del
  vigente. Non confonderle.
- Usare i tool, mai estremi a memoria.
