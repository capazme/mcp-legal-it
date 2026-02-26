---
name: sinistro
description: Analisi completa sinistro con quantificazione danni, rivalutazione e interessi.
  Usa quando l'utente descrive un sinistro o chiede risarcimento danni.
argument-hint: "[tipo: stradale|sanitario|lavoro] [% invalidità] [età vittima]"
---

# Workflow Sinistro

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Classificazione sinistro
Identifica dall'input dell'utente:
- **Tipo sinistro**: stradale, sanitario, lavoro
- **Percentuale invalidità permanente** (IP)
- **Età della vittima** al momento del sinistro
- **Giorni di inabilità temporanea** (ITT, ITP 75%, 50%, 25%) se disponibili
- **Eventuale danno parentale** (decesso o invalidità gravissima)

Se mancano dati essenziali (% invalidità, età), chiedi all'utente.

## Step 2 — Calcolo danno biologico
- Se IP ≤ 9%: chiama `danno_biologico_micro(percentuale_invalidita, eta_vittima, giorni_itt, giorni_itp75, giorni_itp50, giorni_itp25)`
- Se IP ≥ 10%: chiama `danno_biologico_macro(percentuale_invalidita, eta_vittima)`

Annota il risultato: importo base + personalizzazione.

## Step 3 — Calcolo danno non patrimoniale complessivo
Chiama `danno_non_patrimoniale(percentuale_invalidita, eta_vittima, ...)` con tutti i parametri disponibili (ITT, ITP, danno morale, esistenziale).

Questo tool calcola tutte le componenti: biologico + morale + esistenziale.

## Step 4 — Rivalutazione monetaria
Se il sinistro non è recentissimo (>6 mesi), chiama `rivalutazione_monetaria(importo, data_iniziale, data_finale)` con:
- `importo`: il totale del danno non patrimoniale
- `data_iniziale`: data del sinistro
- `data_finale`: oggi o data di liquidazione

## Step 5 — Interessi compensativi
Chiama `interessi_legali(capitale, data_iniziale, data_finale)` con:
- `capitale`: l'importo rivalutato
- Le stesse date usate per la rivalutazione

## Step 6 — Danno parentale (se applicabile)
Se c'è decesso o invalidità gravissima, chiama `danno_parentale(...)` per i congiunti.

## Step 7 — Tabella riepilogativa
Presenta i risultati in una tabella markdown:

| Voce | Importo |
|------|---------|
| Danno biologico (IP X%) | € ... |
| Danno morale | € ... |
| Danno esistenziale | € ... |
| **Subtotale danno non patrimoniale** | **€ ...** |
| Rivalutazione monetaria | € ... |
| Interessi compensativi | € ... |
| Danno parentale | € ... |
| **TOTALE RISARCIMENTO** | **€ ...** |

Aggiungi note su: base normativa (art. 138/139 CdA), tabelle applicate, eventuali componenti INDICATIVE.
