---
name: novita-consob
description: Usa quando l'utente chiede le ultime novità CONSOB, delibere recenti o aggiornamenti sui mercati finanziari — riepilogo delle ultime delibere con sintesi orientamenti per tipologia o argomento.
tools: [cite_law, leggi_delibera_consob, ultime_delibere_consob]
prompt: {"name": "novita_consob", "description": "Ultime novità CONSOB: delibere recenti per tipologia o argomento con sintesi degli orientamenti", "args": [{"name": "tipologia", "type": "str", "default": ""}, {"name": "argomento", "type": "str", "default": ""}]}
---

# Novita CONSOB

Ultime delibere con sintesi orientamenti.

## Workflow

### 1. Ultime delibere

Chiama `ultime_delibere_consob` con eventuali filtri (tipologia, argomento).

### 2. Approfondimento

Per le 2-3 delibere piu rilevanti: `leggi_delibera_consob` con numero.

### 3. Quadro normativo

Per le norme richiamate: `cite_law`.

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
- Per le norme, usare sempre `cite_law`.
- Indicare data e numero di ogni delibera.
