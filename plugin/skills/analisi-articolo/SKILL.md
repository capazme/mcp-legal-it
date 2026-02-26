---
name: analisi-articolo
description: Analisi approfondita di un singolo articolo di legge con testo, ratio, giurisprudenza e norme collegate.
  Simile ad analisi-norma ma include anche l'evoluzione storica e gli elementi costitutivi della fattispecie.
argument-hint: "[riferimento normativo, es. 'art. 2043 c.c.', 'art. 6 D.Lgs. 231/2001']"
---

# Workflow Analisi Articolo

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Testo vigente
Chiama `cite_law(riferimento)` per recuperare il testo ufficiale aggiornato.
Se la risposta indica che il testo è stato modificato, recupera anche la versione precedente.

## Step 2 — Annotazioni e giurisprudenza
Chiama `cerca_brocardi(riferimento)` per recuperare da Brocardi:
- Ratio legis (scopo della norma)
- Spiegazione dottrinale
- Massime giurisprudenziali rilevanti
- Casistica applicativa

## Step 3 — Norme collegate
Identifica e recupera con `cite_law`:
- Articoli precedenti e successivi nello stesso testo normativo (contesto sistematico)
- Norme richiamate espressamente nel testo
- Norme che richiamano questo articolo
- Disposizioni di attuazione o regolamentari

## Step 4 — Evoluzione storica
Se disponibile dalle annotazioni, riporta:
- Versioni precedenti del testo
- Leggi di modifica con date
- Motivazioni delle modifiche

## Step 5 — Presentazione risultati

### Testo Vigente
> [testo completo dell'articolo da cite_law]

### Ratio Legis
Spiegazione dello scopo e della funzione della norma nell'ordinamento.

### Elementi Costitutivi
Scomposizione della norma in:
- Presupposti (fattispecie astratta)
- Effetti giuridici (conseguenze)
- Soggetti destinatari
- Ambito di applicazione

### Giurisprudenza di Riferimento
| Pronuncia | Principio | Rilevanza |
|-----------|-----------|-----------|
| Cass. n. .../... | ... | ... |

### Norme Collegate
| Norma | Relazione | Contenuto |
|-------|-----------|-----------|
| art. ... | richiamo espresso / sistematico | ... |

### Note Operative
Indicazioni pratiche per l'applicazione della norma.

## Note
- Il testo DEVE provenire da `cite_law`, non dalla memoria.
- Se Brocardi non ha annotazioni per questa norma, indicarlo espressamente.
- Distinguere tra interpretazione consolidata e orientamenti minoritari.
