---
name: confronto-norme
description: Confronto tra due o più norme con analisi di differenze, sovrapposizioni, prevalenza e coordinamento.
  Usa quando l'utente chiede di confrontare articoli di legge o capire quale norma prevale.
argument-hint: "[norma 1, es. 'art. 2043 c.c.'] [norma 2, es. 'art. 2050 c.c.'] [contesto opzionale]"
---

# Workflow Confronto Norme

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Recupero testi
Chiama `cite_law` per ciascuna norma da confrontare.
Per entrambe, chiama anche con `include_annotations=true` per giurisprudenza e dottrina.

## Step 2 — Analisi comparativa
Confronta le norme su:
- **Ambito oggettivo**: quale materia disciplinano
- **Ambito soggettivo**: a chi si applicano
- **Presupposti**: quando si attivano
- **Effetti**: quali conseguenze producono
- **Sanzioni**: apparato sanzionatorio

## Step 3 — Rapporto tra le norme
Determina la relazione:
- **Specialità** (art. 15 c.p. / lex specialis): una è speciale rispetto all'altra?
- **Successione temporale** (lex posterior): una ha abrogato l'altra?
- **Gerarchia**: una prevale per rango (Costituzione > legge > regolamento)?
- **Concorso**: si applicano entrambe contemporaneamente?
- **Complementarietà**: disciplinano aspetti diversi della stessa materia?

## Step 4 — Giurisprudenza sul coordinamento
Dalle annotazioni, individua pronunce che hanno affrontato il rapporto tra le due norme.

## Step 5 — Presentazione risultati

### Testi a Confronto
| Elemento | Norma 1 | Norma 2 |
|----------|---------|---------|
| Fonte | ... | ... |
| Ambito oggettivo | ... | ... |
| Ambito soggettivo | ... | ... |
| Presupposti | ... | ... |
| Effetti | ... | ... |
| Sanzioni | ... | ... |

### Rapporto tra le Norme
Analisi del criterio di prevalenza applicabile.

### Aree di Sovrapposizione
Casi in cui entrambe le norme sono potenzialmente applicabili e come si coordinano.

### Orientamento Giurisprudenziale
Come la giurisprudenza ha risolto i conflitti tra queste norme.

### Conclusioni Operative
Indicazione pratica su quale norma applicare e in quali circostanze.

## Note
- Entrambi i testi DEVONO provenire da `cite_law`.
- Non dare per scontata la prevalenza di una norma — argomentare il criterio.
- Se il rapporto è controverso, esporre le diverse tesi.
