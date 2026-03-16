---
name: analisi-articolo
description: Analisi approfondita di un singolo articolo di legge con testo vigente, ratio legis, giurisprudenza di riferimento e norme collegate. Usa quando l'utente chiede di spiegare, analizzare o approfondire un articolo specifico (es. "spiegami l'art. 2043 c.c.").
---

# Analisi Articolo

Testo, ratio, giurisprudenza e collegamenti per un articolo di legge.

## Workflow

### 1. Testo vigente

Chiama `cite_law` con il riferimento normativo. Se modificato, recupera anche la versione precedente.

### 2. Annotazioni e giurisprudenza

Chiama `cerca_brocardi` per:
- Ratio legis
- Spiegazione dottrinale
- Massime giurisprudenziali
- Casistica applicativa

I riferimenti Cassazione nelle massime possono essere letti con `leggi_sentenza`.

### 3. Norme collegate

Con `cite_law` recupera:
- Articoli precedenti/successivi (contesto sistematico)
- Norme richiamate nel testo
- Disposizioni di attuazione

### 4. Evoluzione storica

Dalle annotazioni: versioni precedenti, leggi di modifica, motivazioni.

## Output atteso

### Testo vigente
> [da cite_law]

### Ratio legis
Scopo e funzione nell'ordinamento.

### Elementi costitutivi
- Presupposti (fattispecie astratta)
- Effetti giuridici
- Soggetti destinatari
- Ambito di applicazione

### Giurisprudenza
| Pronuncia | Principio | Rilevanza |
|-----------|-----------|-----------|
| ... | ... | ... |

### Norme collegate
| Norma | Relazione | Contenuto |
|-------|-----------|-----------|
| ... | ... | ... |

## Tool utilizzati

- `cite_law` (obbligatorio)
- `cerca_brocardi` (annotazioni complete)
- `leggi_sentenza` (testo sentenze citate)
