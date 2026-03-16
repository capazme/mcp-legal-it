---
name: analisi-delibere-consob
description: Ricerca e analisi delibere CONSOB su un tema con lettura provvedimenti, quadro normativo TUF/MiFID e sintesi orientamenti. Usa quando l'utente chiede delibere CONSOB, provvedimenti su mercati finanziari, sanzioni CONSOB, intermediari, emittenti, OPA, abusi di mercato, crowdfunding o cripto-attivita.
argument-hint: "[tema CONSOB, es. 'abusi di mercato']"
allowed-tools: mcp__legal-it__cerca_delibere_consob, mcp__legal-it__leggi_delibera_consob, mcp__legal-it__cite_law, mcp__legal-it__cerca_giurisprudenza
---

# Analisi Delibere CONSOB

Ricerca, lettura e analisi delibere/provvedimenti CONSOB.

## Workflow

### 1. Ricerca delibere

Chiama `legal-it:cerca_delibere_consob` con query e filtri (tipologia, argomento, date).
Se il tema e ampio, esegui piu ricerche con query diverse.

### 2. Lettura delibere chiave

Seleziona 2-3 delibere significative.
Per ciascuna: `legal-it:leggi_delibera_consob` con numero.

Privilegia:
- Delibere recenti (ultimo biennio)
- Delibere con principi generali o sanzioni rilevanti

### 3. Quadro normativo

Per le norme richiamate: `legal-it:cite_law`.

Fonti tipiche:
- TUF (D.Lgs. 58/1998)
- Reg. Emittenti (11971/1999)
- Reg. Intermediari (20307/2018)
- MAR (Reg. UE 596/2014)
- MiFID II / MiFIR
- MiCA (Reg. UE 2023/1114)

### 4. Giurisprudenza (se pertinente)

Chiama `legal-it:cerca_giurisprudenza` per verificare sentenze correlate.

## Output atteso

### Orientamento CONSOB
| Delibera | Data | Principio/Esito |
|----------|------|-----------------|
| ... | ... | ... |

### Sanzioni e misure
### Principi consolidati
### Indicazioni operative
