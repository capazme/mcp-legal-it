---
name: recupero-credito
description: Workflow completo per recupero crediti insoluti con calcolo interessi di mora, rivalutazione ISTAT, predisposizione decreto ingiuntivo e parcella avvocato. Usa quando l'utente ha un credito da recuperare, una fattura non pagata, chiede interessi di mora o vuole procedere con decreto ingiuntivo.
tools: [decreto_ingiuntivo, interessi_legali, interessi_mora, parcella_avvocato_civile, rivalutazione_monetaria]
---

# Recupero Credito

Workflow completo: interessi mora, rivalutazione, decreto ingiuntivo, parcella.

## Workflow

### 1. Interessi di mora

Chiama `interessi_mora` con capitale, data_inizio (decorrenza della mora) e data_fine (data di calcolo).

- **Commerciale** (imprese/PA): usa `interessi_mora` — tasso BCE + 8 punti (D.Lgs. 231/2002)
- **Privato** (crediti tra privati): usa `interessi_legali` — tasso legale art. 1284 c.c.

### 2. Rivalutazione monetaria

Chiama `rivalutazione_monetaria`.

**Nota**: mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi, indica il piu favorevole.

### 3. Decreto ingiuntivo

Chiama `decreto_ingiuntivo`: competenza, CU, requisiti, provvisoria esecutivita.

### 4. Parcella

Chiama `parcella_avvocato_civile` per fase monitoria.
