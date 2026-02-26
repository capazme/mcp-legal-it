---
name: pianificazione-successione
description: Pianificazione successoria con calcolo quote ereditarie, imposte e adempimenti.
  Usa quando l'utente chiede di calcolare eredità, quote, imposte di successione o pianificare una successione.
argument-hint: "[valore asse ereditario] [grado parentela] [numero eredi]"
---

# Workflow Pianificazione Successione

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati
Identifica dall'input dell'utente:
- **Valore asse ereditario** (in euro)
- **Grado di parentela** con il de cuius
- **Numero eredi**
- **Presenza di testamento** (sì/no)
- **Composizione asse** (immobili, mobili, conti, partecipazioni)

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Quote ereditarie
Chiama `calcolo_eredita(valore_asse, grado_parentela, numero_eredi)`.
Distingui tra:
- **Successione legittima** (senza testamento): quote ex artt. 565-586 c.c.
- **Quote di legittima** (con testamento): riserva ex artt. 536-564 c.c.

Indica la quota disponibile.

## Step 3 — Imposte di successione
Chiama `imposte_successione` per calcolare:
- Imposta di successione (aliquota per grado di parentela)
- Franchigia applicabile (€ 1M coniuge/figli, € 100K fratelli, nessuna altri)
- Imposte ipotecaria (2%) e catastale (1%) se ci sono immobili
- Imposta di bollo e tassa ipotecaria

## Step 4 — Imposte compravendita (se applicabile)
Se l'asse include immobili da vendere post-successione, chiama `imposte_compravendita` per stimare il carico fiscale sulla vendita.

## Step 5 — Tabella riepilogativa

### Quote Ereditarie
| Erede | Quota | Valore |
|-------|-------|--------|
| ... | ... | € ... |
| Disponibile | ... | € ... |

### Imposte di Successione
| Voce | Importo |
|------|---------|
| Base imponibile | € ... |
| Franchigia | € ... |
| Imposta di successione | € ... |
| Imposta ipotecaria (2%) | € ... |
| Imposta catastale (1%) | € ... |
| **Totale imposte** | **€ ...** |

### Adempimenti
- Dichiarazione di successione: entro 12 mesi dall'apertura
- Voltura catastale: entro 30 giorni dalla dichiarazione
- Accettazione eredità: espressa o tacita, con beneficio d'inventario se opportuno
- Pubblicazione testamento olografo (se presente): tribunale competente

### Avvertenze
- I calcoli sono indicativi; la situazione patrimoniale completa potrebbe variare le imposte.
- Per successioni internazionali si applica il Reg. UE 650/2012.
- Valutare l'opportunità del beneficio d'inventario (art. 484 c.c.).
