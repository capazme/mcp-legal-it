---
name: analisi-norma
description: Analisi approfondita di una norma con testo, annotazioni, dottrina e giurisprudenza.
  Usa quando l'utente chiede di analizzare, spiegare o approfondire un articolo di legge.
argument-hint: "[riferimento normativo, es. 'art. 2043 c.c.', 'art. 13 GDPR']"
---

# Workflow Analisi Norma

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Recupero testo ufficiale
Chiama `cite_law(reference, include_annotations=True)` con il riferimento normativo fornito dall'utente.

Questo recupera:
- Testo vigente da Normattiva/EUR-Lex
- Annotazioni Brocardi (ratio legis, spiegazione) se disponibili

## Step 2 — Approfondimento dottrinale
Chiama `cerca_brocardi(reference)` per ottenere:
- Ratio legis
- Spiegazione dottrinale
- Massime giurisprudenziali con riferimenti strutturati alla Cassazione
- Relazioni storiche dell'articolo
- Note e riferimenti incrociati

## Step 3 — Giurisprudenza rilevante
Chiama `giurisprudenza_su_norma(reference)` per trovare le sentenze della Cassazione che citano questa norma.

Per le 2-3 sentenze più significative, chiama `leggi_sentenza(numero, anno)` per il testo integrale.

## Step 4 — Norme collegate
Se dall'analisi emergono norme collegate rilevanti (es. norme di attuazione, norme richiamate), chiama `cite_law()` anche per queste.

## Step 5 — Sintesi strutturata
Presenta l'analisi in questo formato:

### Testo vigente
Il testo dell'articolo come recuperato da Normattiva/EUR-Lex.

### Ratio legis
Perché il legislatore ha introdotto questa norma.

### Contenuto e interpretazione
Spiegazione del contenuto normativo, elementi costitutivi della fattispecie, presupposti di applicazione.

### Orientamenti giurisprudenziali
Le principali linee interpretative della Cassazione, con numero e anno delle sentenze chiave.

### Norme collegate
Articoli collegati e loro interazione con la norma analizzata.

### Evoluzione storica
Se disponibile, come la norma è cambiata nel tempo.
