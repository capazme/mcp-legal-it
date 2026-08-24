---
name: analisi-delibere-consob
description: Ricerca e analisi delibere CONSOB su un tema con lettura provvedimenti, quadro normativo TUF/MiFID e sintesi orientamenti. Usa quando l'utente chiede delibere CONSOB, provvedimenti su mercati finanziari, sanzioni CONSOB, intermediari, emittenti, OPA, abusi di mercato, crowdfunding o cripto-attivita.
tools: [cerca_delibere_consob, cerca_giurisprudenza, cite_law, leggi_delibera_consob]
prompt: {"name": "analisi_delibere_consob", "description": "Ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, regolamenti mercati finanziari", "args": [{"name": "tema", "type": "str"}, {"name": "tipologia", "type": "str", "default": ""}, {"name": "argomento", "type": "str", "default": ""}]}
---

# Analisi Delibere CONSOB

Ricerca, lettura e analisi delibere/provvedimenti CONSOB.

## Workflow

### 1. Ricerca delibere

Chiama `cerca_delibere_consob` con query e filtri (tipologia, argomento, date).
Se il tema e ampio, esegui piu ricerche con query diverse.

### 2. Lettura delibere chiave

Seleziona 2-3 delibere significative.
Per ciascuna: `leggi_delibera_consob` con numero.

Privilegia:
- Delibere recenti (ultimo biennio)
- Delibere con principi generali o sanzioni rilevanti

### 3. Quadro normativo

Per le norme richiamate: `cite_law`.

Fonti tipiche:
- TUF (D.Lgs. 58/1998)
- Reg. Emittenti (11971/1999)
- Reg. Intermediari (20307/2018)
- MAR (Reg. UE 596/2014)
- MiFID II / MiFIR
- MiCA (Reg. UE 2023/1114)

### 4. Giurisprudenza (se pertinente)

Chiama `cerca_giurisprudenza` per verificare sentenze correlate.

## Output atteso

### Orientamento CONSOB
| Delibera | Data | Principio/Esito |
|----------|------|-----------------|
| ... | ... | ... |

### Sanzioni e misure
### Principi consolidati
### Indicazioni operative
