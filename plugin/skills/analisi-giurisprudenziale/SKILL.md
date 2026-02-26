---
name: analisi-giurisprudenziale
description: Analisi degli orientamenti giurisprudenziali su un tema con sintesi delle sentenze principali.
  Usa quando l'utente chiede di ricercare giurisprudenza, orientamenti della Cassazione, o precedenti.
argument-hint: "[tema giuridico o questione da ricercare]"
---

# Workflow Analisi Giurisprudenziale

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Ricerca decisioni
Chiama `cerca_giurisprudenza(query, archivio, max_risultati=15)` con:
- `query`: il tema giuridico descritto dall'utente
- `archivio`: "civile", "penale", o "tutti" a seconda del contesto

Se il tema è collegato a una norma specifica, chiama anche `giurisprudenza_su_norma(riferimento)`.

## Step 2 — Lettura sentenze chiave
Dalle decisioni trovate, seleziona le 3-5 più rilevanti (per pertinenza e per rappresentatività degli orientamenti).

Per ciascuna, chiama `leggi_sentenza(numero, anno)` per il testo integrale.

Criteri di selezione:
- Sentenze delle Sezioni Unite (prevalgono)
- Sentenze più recenti (orientamento attuale)
- Sentenze che rappresentano orientamenti diversi (se c'è contrasto)

## Step 3 — Verifica normativa
Per ogni norma citata nelle sentenze lette, chiama `cite_law(reference)` per verificare il testo vigente.

Questo è essenziale perché la norma potrebbe essere stata modificata dopo la sentenza.

## Step 4 — Mappatura orientamenti
Classifica le decisioni trovate per orientamento:
- **Orientamento consolidato**: posizione costante della Cassazione
- **Orientamento recente/in evoluzione**: cambio di direzione
- **Contrasto giurisprudenziale**: posizioni divergenti tra sezioni

## Step 5 — Sintesi strutturata

### Quadro normativo di riferimento
Le norme rilevanti (con testo da cite_law).

### Orientamento prevalente
La posizione dominante della Cassazione, con sentenze chiave.

### Orientamenti minoritari o in evoluzione
Posizioni alternative, se presenti.

### Sentenze chiave

| Sentenza | Sezione | Principio |
|----------|---------|-----------|
| Cass. n. .../... | ... | ... |

### Conclusioni operative
- Stato attuale dell'orientamento
- Livello di consolidamento
- Rischi di revirement
- Raccomandazioni per chi deve impostare una strategia processuale
