---
name: analisi-giurisprudenziale
description: Analisi strutturata degli orientamenti giurisprudenziali su un tema con ricerca sentenze Cassazione su Italgiure, lettura testo completo delle decisioni chiave e sintesi degli orientamenti. Usa quando l'utente chiede giurisprudenza su un argomento, orientamenti della Cassazione, precedenti, o sentenze su un tema specifico.
---

# Analisi Giurisprudenziale

Ricerca Italgiure, lettura decisioni chiave, sintesi orientamenti.

## Regola fondamentale

**Non citare mai numeri di sentenza a memoria**. Usa esclusivamente i risultati dei tool.

## Workflow

### Fase 1 — Panoramica

Chiama `legal-it:cerca_giurisprudenza` con query, archivio e max 15 risultati.

Se il tema riguarda una norma specifica, chiama prima `legal-it:giurisprudenza_su_norma` per trovare le decisioni che la citano.

### Fase 2 — Approfondimento

Seleziona 2-3 decisioni significative (privilegia Sezioni Unite).
Per ciascuna: `legal-it:leggi_sentenza` con numero e anno.

**Non fare web search per sentenze gia identificate.**

### Fase 3 — Annotazioni Brocardi

Se il tema ruota attorno a un articolo specifico: `legal-it:cerca_brocardi` per ratio legis, spiegazione e massime strutturate.

### Fase 4 — Fondamento normativo

Per le norme citate nelle decisioni: `legal-it:cite_law` per testo vigente.

### Fase 5 — Sintesi

1. **Orientamento prevalente**: principio di diritto
2. **Evoluzione**: cambiamenti nel tempo
3. **Contrasti**: divergenze tra sezioni
4. **Sezioni Unite**: principio di diritto (se pronunciate)
5. **Norme di riferimento**
6. **Decisioni citate**: elenco con estremi

## Tool utilizzati

- `legal-it:cerca_giurisprudenza` (ricerca full-text)
- `legal-it:giurisprudenza_su_norma` (sentenze su norma)
- `legal-it:leggi_sentenza` (testo completo)
- `legal-it:cerca_brocardi` (annotazioni e massime)
- `legal-it:cite_law` (norme citate)
