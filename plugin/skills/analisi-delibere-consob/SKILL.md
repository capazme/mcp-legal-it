---
name: analisi-delibere-consob
description: Ricerca e analisi delibere CONSOB su un tema con lettura provvedimenti, quadro normativo TUF/MiFID e sintesi orientamenti. Usa quando l'utente chiede delibere CONSOB, provvedimenti su mercati finanziari, sanzioni CONSOB, intermediari, emittenti, OPA, abusi di mercato, crowdfunding o cripto-attivita.
---

# Analisi Delibere CONSOB

Ricerca, lettura e analisi delibere/provvedimenti CONSOB.

## Workflow

### 1. Ricerca delibere

Chiama `legal-it:cerca_delibere_consob` con query e filtri (tipologia, argomento, date).

Valori ammessi per i filtri:
- Tipologia: delibere / comunicazioni / provvedimenti_urgenti / opa
- Argomento: abusi_di_mercato / intermediari / emittenti / mercati / cripto_attivita / crowdfunding

Se il tema e ampio, esegui piu ricerche con query diverse.

### 2. Lettura delibere chiave

Seleziona 2-3 delibere significative.
Per ciascuna: `legal-it:leggi_delibera_consob` con numero.

Privilegia:
- Delibere recenti (ultimo biennio)
- Delibere con principi generali o sanzioni rilevanti
- Provvedimenti che riguardano fattispecie analoghe al tema richiesto

### 3. Quadro normativo

Per le norme richiamate: `legal-it:cite_law`.

Fonti tipiche:
- TUF (D.Lgs. 58/1998) — Testo Unico della Finanza
- Reg. Emittenti (Reg. CONSOB 11971/1999)
- Reg. Intermediari (Reg. CONSOB 20307/2018)
- Regolamento Mercati (Reg. CONSOB 20249/2017)
- MAR (Reg. UE 596/2014) — abusi di mercato
- MiFID II (Dir. 2014/65/UE) / MiFIR (Reg. UE 600/2014)
- Reg. UE 2020/1503 — crowdfunding
- MiCA (Reg. UE 2023/1114) — cripto-attivita

### 4. Giurisprudenza (se pertinente)

Se le delibere citano pronunce giurisdizionali o se il tema ha risvolti contenziosi:
1. Esplora la distribuzione: `legal-it:cerca_giurisprudenza` con il tema tra virgolette e `modalita` esplora.
2. Filtra con materia/sezione dai facets, poi leggi il testo completo delle decisioni chiave (tool legal-it:leggi_sentenza, se disponibile).

Usa virgolette per frasi esatte.

## Output atteso

### Quadro regolatorio
Norme primarie e secondarie applicabili (testo da `legal-it:cite_law`).

### Orientamento CONSOB
| Delibera | Data | Principio/Esito |
|----------|------|-----------------|
| ... | ... | ... |

### Sanzioni e misure
Tabella delle sanzioni comminate o delle misure adottate nei provvedimenti esaminati.

### Principi consolidati
Sintesi dei principi ricorrenti nelle delibere CONSOB sul tema.

### Indicazioni operative
Raccomandazioni pratiche derivanti dall'analisi.

## Regole

- Usare `legal-it:cerca_delibere_consob` e `legal-it:leggi_delibera_consob` per i provvedimenti CONSOB.
- Usare `legal-it:cite_law` per TUTTE le norme citate — mai citare a memoria.
- Indicare espressamente il numero e la data di ogni delibera citata.
- Segnalare se l'orientamento e consolidato o in evoluzione.
