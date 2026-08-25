---
name: confronto-norme
description: Usa quando l'utente chiede di confrontare articoli, verificare quale norma prevale o risolvere un conflitto normativo — differenze, sovrapposizioni, criteri di prevalenza e coordinamento.
---

# Confronto Norme

Differenze, sovrapposizioni, prevalenza e coordinamento.

## Workflow

### 1. Recupero testi

Chiama `legal-it:cite_law` per ciascuna norma. Per annotazioni: `legal-it:cerca_brocardi`.

### 2. Analisi comparativa

Confronta su: ambito oggettivo, soggettivo, presupposti, effetti, sanzioni.

### 3. Rapporto tra le norme

- **Specialita** (art. 15 c.p. / lex specialis): una e speciale rispetto all'altra?
- **Successione** (lex posterior): una ha abrogato l'altra?
- **Gerarchia**: una prevale per rango (Costituzione > legge > regolamento)?
- **Concorso**: si applicano entrambe contemporaneamente?
- **Complementarieta**: disciplinano aspetti diversi della stessa materia?

### 4. Giurisprudenza sul coordinamento

Dalle annotazioni, individua pronunce sul rapporto tra le norme.

## Formato output

Apri con il titolo «Confronto: `norma_1` vs. `norma_2`», poi:

### Testi a confronto

| Elemento | `norma_1` | `norma_2` |
|----------|-----------|-----------|
| Fonte | ... | ... |
| Ambito oggettivo | ... | ... |
| Ambito soggettivo | ... | ... |
| Presupposti | ... | ... |
| Effetti | ... | ... |
| Sanzioni | ... | ... |

### Rapporto tra le norme

Analisi del criterio di prevalenza applicabile.

### Aree di sovrapposizione

Casi in cui entrambe le norme sono potenzialmente applicabili e come si coordinano.

### Orientamento giurisprudenziale

Come la giurisprudenza ha risolto i conflitti tra queste norme.

### Conclusioni operative

Indicazione pratica su quale norma applicare e in quali circostanze.

## Regole

- Entrambi i testi DEVONO provenire da `legal-it:cite_law`.
- Non dare per scontata la prevalenza di una norma — argomentare il criterio.
- Se il rapporto e controverso, esporre le diverse tesi.
