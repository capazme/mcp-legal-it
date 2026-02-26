---
name: ricerca-normativa
description: Ricerca normativa completa su un tema giuridico con gerarchia delle fonti e coordinamento.
  Usa quando l'utente chiede quali norme disciplinano un tema o vuole una panoramica del quadro normativo.
argument-hint: "[tema giuridico] [area: civile|penale|amministrativo|lavoro|tributario|privacy]"
---

# Workflow Ricerca Normativa

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Individuazione fonti primarie
Identifica le norme principali che disciplinano il tema.
Per ciascuna norma, chiama `cite_law` per recuperare il testo vigente.
Ordina per gerarchia delle fonti:
- Costituzione (artt. rilevanti)
- Regolamenti UE (direttamente applicabili)
- Direttive UE (recepite con D.Lgs.)
- Leggi ordinarie / D.Lgs. / D.L.
- Regolamenti ministeriali / D.M.
- Circolari e prassi amministrativa

## Step 2 — Norme collegate e coordinamento
Per ogni norma primaria, verifica:
- Norme di attuazione e regolamenti
- Modifiche successive (novelle, correttivi)
- Norme abrogate espressamente o implicitamente
- Disposizioni transitorie

Usa `cite_law` per ciascun articolo rilevante.

## Step 3 — Giurisprudenza e dottrina
Per le norme chiave, chiama `cite_law` con `include_annotations=true` per recuperare da Brocardi:
- Massime di Cassazione e Corte Costituzionale
- Orientamenti consolidati vs. questioni aperte
- Posizioni dottrinali prevalenti

## Step 4 — Quadro sanzionatorio (se pertinente)
Identifica:
- Sanzioni penali (contravvenzioni, delitti)
- Sanzioni amministrative (pecuniarie, interdittive)
- Responsabilità civile (risarcimento danni)
- Sanzioni disciplinari (ordini professionali, PA)

## Step 5 — Presentazione risultati

### Fonti Primarie
| Fonte | Norma | Oggetto |
|-------|-------|---------|
| Costituzione | art. ... | ... |
| Reg. UE | ... | ... |
| Legge | ... | ... |

### Articoli Chiave
Per ciascun articolo: testo (da cite_law), commento sintetico, nessi con altri articoli.

### Evoluzione Normativa
Timeline delle modifiche rilevanti.

### Orientamenti Interpretativi
Giurisprudenza consolidata e questioni aperte.

### Quadro Sanzionatorio
Tabella sanzioni applicabili.

## Note
- OGNI norma citata DEVE essere verificata con `cite_law` — mai citare a memoria.
- Indicare espressamente se una norma è stata modificata o abrogata.
- Segnalare norme in corso di modifica o proposte di riforma pendenti.
