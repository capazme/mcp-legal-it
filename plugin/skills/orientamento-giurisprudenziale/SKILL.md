---
name: orientamento-giurisprudenziale
description: Mappa descrittiva degli orientamenti di legittimità su una norma o un principio — conformi vs contrasti, interventi delle Sezioni Unite, evoluzione temporale. Usa quando l'utente chiede se un orientamento è consolidato, se c'è contrasto in Cassazione o come si è evoluta la giurisprudenza su una norma.
---

# Orientamento Giurisprudenziale

Costruisci una mappa DESCRITTIVA degli orientamenti della Cassazione.

## Dati richiesti

- **riferimento** — una norma, es. "art. 2043 c.c.", oppure un principio/massima. Se non fornito, chiedilo.
- **archivio** (opzionale, default `tutti`) — filtro archivio: civile / penale / tutti.

## Workflow

### Fase 1 — Mappa orientamenti
Se il riferimento è una NORMA, chiama `legal-it:mappa_orientamento(riferimento=<riferimento>, archivio=<archivio>)`
(orchestratore: ancora le massime Brocardi, recupera le decisioni successive, isola le Sezioni Unite).
In alternativa: `legal-it:orientamento_su_norma(...)` per una norma o `legal-it:orientamento_su_principio(principio="...")`
per un principio espresso a parole.

### Fase 2 — Lettura decisioni rappresentative
Presenta la distribuzione (Sezioni Unite, cluster per sezione, trend per anno, segnali testuali di
contrasto/conformità) e chiedi all'utente quali decisioni leggere. Per ciascuna scelta usa
`legal-it:leggi_sentenza(numero, anno)`.

### Fase 3 — Fondamento normativo
Per le norme rilevanti chiama `legal-it:cite_law(reference)`.

### Fase 4 — Sintesi
Riporta: orientamento prevalente, eventuali contrasti segnalati, intervento delle Sezioni Unite (se
presente) ed evoluzione temporale.

## Regole — IMPORTANTE

- La mappa è DESCRITTIVA (distribuzioni, segnali testuali "contrasto/consolidato"), NON una previsione
  di overruling né una classifica dell'indirizzo "vincente" (art. 15 L. 132/2025 — ogni decisione su
  interpretazione, fatti e prove è riservata al magistrato).
- I segnali di (dis)conformità indicano che la decisione DISCUTE il contrasto/la conformità, non che essa
  conforma/diverge in fatto. Etichettali come "decisioni che segnalano...".
- Copertura full-text Italgiure ~dal 2020; segnalare il limite temporale.
- Mai numeri di sentenza a memoria.
