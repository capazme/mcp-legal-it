---
name: confronto-norme
description: Confronta due o piu norme evidenziando differenze, sovrapposizioni, criteri di prevalenza e coordinamento. Usa quando l'utente chiede di confrontare articoli, verificare quale norma prevale, risolvere un conflitto normativo o capire il rapporto tra due disposizioni.
tools: [cerca_brocardi, cite_law]
prompt: {"name": "confronto_norme", "description": "Confronto tra due o più norme: differenze, sovrapposizioni, prevalenza e coordinamento", "args": [{"name": "norma_1", "type": "str"}, {"name": "norma_2", "type": "str"}, {"name": "contesto", "type": "str", "default": ""}]}
---

# Confronto Norme

Differenze, sovrapposizioni, prevalenza e coordinamento.

## Workflow

### 1. Recupero testi

Chiama `cite_law` per ciascuna norma. Per annotazioni: `cerca_brocardi`.

### 2. Analisi comparativa

Confronta su: ambito oggettivo, soggettivo, presupposti, effetti, sanzioni.

### 3. Rapporto tra le norme

- **Specialita** (lex specialis)
- **Successione** (lex posterior)
- **Gerarchia** (rango)
- **Concorso** (applicazione contemporanea)
- **Complementarieta**

### 4. Giurisprudenza sul coordinamento

Dalle annotazioni, individua pronunce sul rapporto tra le norme.
