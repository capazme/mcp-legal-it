---
name: pianificazione-successione
description: Usa quando l'utente chiede quote ereditarie, imposte di successione, eredità, testamento, franchigie o donazioni — pianifica la successione con calcolo quote legittime, imposte e adempimenti.
---

# Pianificazione Successione

Quote ereditarie, imposte e adempimenti.

## Workflow

### 1. Quote ereditarie

Chiama `legal-it:calcolo_eredita` con massa_ereditaria (valore totale dell'asse in €) ed eredi (dict: {'coniuge': bool, 'figli': int, 'ascendenti': bool, 'fratelli': int}).

Distingui tra:
- Successione legittima (senza testamento): quote ex artt. 565-586 c.c.
- Quote di legittima (con testamento): riserva ex artt. 536-564 c.c.

Indica la quota disponibile.

### 2. Imposte di successione

Chiama `legal-it:imposte_successione` con valore_beni, parentela (uno tra 'coniuge_linea_retta', 'fratelli_sorelle', 'parenti_fino_4_grado_affini_fino_3', 'altri'), immobili (bool), prima_casa (bool).
- Aliquota per grado di parentela
- Franchigia (€ 1M coniuge/figli, € 100K fratelli, nessuna franchigia per gli altri soggetti)
- Imposte ipotecaria (2%) e catastale (1%) se immobili
- Segnala che oltre a quanto calcolato dal tool si applicano tributi minori (imposta di bollo, tassa ipotecaria) non inclusi nell'output

### 3. Imposte compravendita (se immobili da vendere)

Chiama `legal-it:imposte_compravendita`.

## Formato output

```markdown
## Quote Ereditarie
| Erede | Quota | Valore |
|-------|-------|--------|
| ... | ... | € ... |
| Disponibile | ... | € ... |

## Imposte di Successione
| Voce | Importo |
|------|---------|
| Base imponibile | € ... |
| Franchigia | € ... |
| Imposta di successione | € ... |
| Imposta ipotecaria (2%) | € ... |
| Imposta catastale (1%) | € ... |
| **Totale imposte** | **€ ...** |
```

## Adempimenti da indicare

- Dichiarazione di successione: entro 12 mesi dall'apertura
- Voltura catastale: entro 30 giorni dalla dichiarazione
- Accettazione eredità: espressa o tacita, con beneficio d'inventario se opportuno
- Pubblicazione testamento olografo (se presente): tribunale competente

## Avvertenze

- I calcoli sono indicativi; la situazione patrimoniale completa potrebbe variare le imposte.
- Franchigie e aliquote vanno lette alla luce della riforma del D.Lgs. 139/2024, che ha introdotto l'autoliquidazione dell'imposta di successione.
- Per successioni internazionali si applica il Reg. UE 650/2012.
- Valutare l'opportunità del beneficio d'inventario (art. 484 c.c.).
