---
name: novita-consob
description: Usa quando l'utente chiede le ultime novità CONSOB, delibere recenti o aggiornamenti sui mercati finanziari — riepilogo delle ultime delibere con sintesi orientamenti per tipologia o argomento.
---

# Novita CONSOB

Ultime delibere con sintesi orientamenti.

## Workflow

### 1. Ultime delibere

Chiama `legal-it:ultime_delibere_consob` con eventuali filtri (tipologia, argomento).

### 2. Approfondimento

Per le 2-3 delibere piu rilevanti: `legal-it:leggi_delibera_consob` con numero.

### 3. Quadro normativo

Per le norme richiamate: `legal-it:cite_law`.

## Output atteso

### Panoramica
Tendenze emergenti dai provvedimenti recenti.

### Per ciascuna delibera letta:

#### Delibera n. ... del GG/MM/AAAA
- **Oggetto**
- **Norme di riferimento**
- **Decisione/Sanzione**
- **Rilevanza pratica**

### Tendenze e indicazioni
Sintesi orientamenti dalle delibere piu recenti.

## Regole

- Usare esclusivamente i tool CONSOB per i provvedimenti — mai citare a memoria.
- Per le norme, usare sempre `legal-it:cite_law`.
- Indicare data e numero di ogni delibera.
