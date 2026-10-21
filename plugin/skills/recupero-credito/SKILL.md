---
name: recupero-credito
description: Usa quando l'utente ha un credito da recuperare, una fattura non pagata o vuole procedere con decreto ingiuntivo — interessi di mora, rivalutazione ISTAT, decreto ingiuntivo e parcella avvocato.
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

**Nota**: per un credito di denaro la rivalutazione non è automatica: è il maggior danno dell'art. 1224, co. 2, c.c., da chiedere e provare (anche in via presuntiva, Cass. SS.UU. n. 19499/2008), e spetta solo per la parte che eccede gli interessi moratori: i due importi non si sommano. Presenta entrambi i calcoli e indica il più favorevole.

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
