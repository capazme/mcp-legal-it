---
name: recupero-credito
description: Workflow completo recupero credito con interessi, rivalutazione, decreto ingiuntivo e parcella.
  Usa quando l'utente ha un credito da recuperare o chiede di calcolare interessi di mora.
argument-hint: "[importo credito] [data scadenza] [tipo debitore: impresa|PA|privato]"
---

# Workflow Recupero Credito

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati
Identifica dall'input dell'utente:
- **Importo del credito** (capitale originario)
- **Data di scadenza** del pagamento
- **Tipo di debitore**: impresa, pubblica amministrazione, privato
- **Tipo di transazione**: commerciale (B2B/B2PA) o non commerciale
- **Eventuale tasso convenzionale** pattuito

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Calcolo interessi di mora
Chiama `interessi_mora(capitale, data_scadenza, data_calcolo, tipo_transazione)`.
- Per transazioni commerciali: si applicano i tassi BCE + maggiorazione (D.Lgs. 231/2002)
- Per altre: interessi legali ex art. 1284 c.c.

## Step 3 — Rivalutazione monetaria
Chiama `rivalutazione_monetaria(importo, data_iniziale, data_finale)` con:
- `importo`: il capitale originario
- `data_iniziale`: data di scadenza del credito
- `data_finale`: oggi

## Step 4 — Decreto ingiuntivo
Chiama `decreto_ingiuntivo(valore_causa)` per calcolare:
- Contributo unificato
- Spese di notifica
- Diritti di cancelleria
- Marca da bollo

## Step 5 — Parcella avvocato
Chiama `parcella_avvocato_civile(valore_causa, fasi, complessita)` con:
- `valore_causa`: importo del credito + interessi
- `fasi`: ["studio", "introduttiva"] per monitorio, oppure tutte le fasi se si prevede opposizione

## Step 6 — Tabella riepilogativa

| Voce | Importo |
|------|---------|
| Capitale originario | € ... |
| Interessi di mora | € ... |
| Rivalutazione ISTAT | € ... |
| **Subtotale credito** | **€ ...** |
| Contributo unificato | € ... |
| Spese di giustizia | € ... |
| Parcella avvocato | € ... |
| **TOTALE DA RECUPERARE** | **€ ...** |

Aggiungi note su: base normativa, tasso BCE applicato, possibilità di provvisoria esecuzione ex art. 642 c.p.c.
