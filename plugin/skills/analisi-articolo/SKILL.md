---
name: analisi-articolo
description: Analisi approfondita di un singolo articolo di legge con testo vigente, ratio legis, giurisprudenza di riferimento e norme collegate. Usa quando l'utente chiede di spiegare, analizzare o approfondire un articolo specifico (es. "spiegami l'art. 2043 c.c.").
---

# Analisi Articolo

Testo, ratio, giurisprudenza e collegamenti per un articolo di legge.

Formati accettati per il riferimento: "art. 13 GDPR", "art. 2043 c.c.", "art. 6 D.Lgs. 231/2001".

## Workflow

### 1. Testo vigente

Chiama `legal-it:cite_law` con il riferimento normativo. Se modificato, recupera anche la versione precedente.

### 2. Annotazioni e giurisprudenza

Chiama `legal-it:cerca_brocardi` per:
- Ratio legis
- Spiegazione dottrinale
- Massime giurisprudenziali
- Casistica applicativa

I riferimenti Cassazione nelle massime possono essere letti con `legal-it:leggi_sentenza`.

### 3. Norme collegate

Con `legal-it:cite_law` recupera:
- Articoli precedenti/successivi (contesto sistematico)
- Norme richiamate nel testo
- Disposizioni di attuazione
- Norme che richiamano questo articolo

### 4. Evoluzione storica

Dalle annotazioni:
- Versioni precedenti del testo
- Leggi di modifica con date
- Motivazioni delle modifiche (relazioni illustrative)

Se rilevante, verifica con `legal-it:ddl_su_norma` se pendono DDL sull'atto: segnalali
solo con estremi verificati (atto, stato, data, scheda ufficiale), ricordando
che la ricerca copre i soli titoli dei DDL.

## Output atteso

### Testo vigente
> [da legal-it:cite_law]

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
| art. ... | richiamo espresso / sistematico | ... |

### Note operative
Indicazioni pratiche per l'applicazione della norma.

## Regole

- Il testo dell'articolo DEVE provenire da `legal-it:cite_law`, non dalla memoria.
- Se Brocardi non ha annotazioni per questa norma, indicarlo espressamente.
- Distinguere tra interpretazione consolidata e orientamenti minoritari.
