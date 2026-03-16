---
name: novita-consob
description: Riepilogo delle ultime delibere e provvedimenti CONSOB con sintesi orientamenti per tipologia o argomento. Usa quando l'utente chiede le ultime novita CONSOB, delibere recenti, aggiornamenti sui mercati finanziari o provvedimenti recenti dell'autorita di vigilanza.
argument-hint: "[tipologia o argomento opzionale]"
allowed-tools: mcp__legal-it__ultime_delibere_consob, mcp__legal-it__leggi_delibera_consob, mcp__legal-it__cite_law
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
- **Oggetto**
- **Norme di riferimento**
- **Decisione/Sanzione**
- **Rilevanza pratica**

### Tendenze e indicazioni
Sintesi orientamenti dalle delibere piu recenti.
