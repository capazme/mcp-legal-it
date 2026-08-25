---
name: recupero-credito
description: Workflow completo per recupero crediti insoluti con calcolo interessi di mora, rivalutazione ISTAT, predisposizione decreto ingiuntivo e parcella avvocato. Usa quando l'utente ha un credito da recuperare, una fattura non pagata, chiede interessi di mora o vuole procedere con decreto ingiuntivo.
---

# Recupero Credito

Workflow completo: interessi mora, rivalutazione, decreto ingiuntivo, parcella.

## Workflow

### 1. Interessi di mora

Chiama `legal-it:interessi_mora` con capitale, data_inizio (decorrenza della mora) e data_fine (data di calcolo).

- **Commerciale** (imprese/PA): usa `legal-it:interessi_mora` — tasso BCE + 8 punti (D.Lgs. 231/2002)
- **Privato** (crediti tra privati): usa `legal-it:interessi_legali` — tasso legale art. 1284 c.c.

### 2. Rivalutazione monetaria

Chiama `legal-it:rivalutazione_monetaria` con l'importo del credito, dalla data di scadenza a oggi.

**Nota**: mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi, indica il piu favorevole.

### 3. Decreto ingiuntivo

Chiama `legal-it:decreto_ingiuntivo` con l'importo del credito per verificare:

- Competenza — Giudice di Pace fino a € 10.000 per i procedimenti instaurati dal 28/2/2023 (riforma Cartabia, D.Lgs. 149/2022); fino a € 5.000 per quelli anteriori. Oltre la soglia, Tribunale.
- Contributo unificato dovuto
- Requisiti documentali (fatture, contratto, estratto autentico notarile)
- Possibilità di provvisoria esecutività (art. 642 c.p.c.)

### 4. Parcella

Chiama `legal-it:parcella_avvocato_civile` con valore della causa pari all'importo del credito, per fase monitoria. Indica il range compenso (minimo/medio/massimo) da D.M. 55/2014.

## Formato output

### Riepilogo Recupero Credito

| Voce | Importo |
|------|---------|
| Capitale | € `importo` |
| Interessi di mora (da `data_scadenza` a oggi) | € ... |
| Rivalutazione ISTAT (alternativa) | € ... |
| **Totale dovuto** | **€ ...** |

### Costi procedura

| Voce | Importo |
|------|---------|
| Contributo unificato | € ... |
| Marca da bollo | € 27,00 |
| Diritti di notifica | € ... |
| Compenso avvocato (medio) | € ... |
| **Costo totale procedura** | **€ ...** |

## Raccomandazioni

- Indicare se conviene la diffida stragiudiziale prima del ricorso
- Valutare la provvisoria esecutività
- Tempi medi della procedura
