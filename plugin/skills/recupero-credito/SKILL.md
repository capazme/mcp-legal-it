---
name: recupero-credito
description: Workflow completo per recupero crediti insoluti con calcolo interessi di mora, rivalutazione ISTAT, predisposizione decreto ingiuntivo e parcella avvocato. Usa quando l'utente ha un credito da recuperare, una fattura non pagata, chiede interessi di mora o vuole procedere con decreto ingiuntivo.
argument-hint: "[importo] [data scadenza] [tipo debitore]"
allowed-tools: mcp__legal-it__interessi_mora, mcp__legal-it__rivalutazione_monetaria, mcp__legal-it__decreto_ingiuntivo, mcp__legal-it__parcella_avvocato_civile
---

# Recupero Credito

Workflow completo: interessi mora, rivalutazione, decreto ingiuntivo, parcella.

## Workflow

### 1. Interessi di mora

Chiama `legal-it:interessi_mora` con importo e data_decorrenza.

- **Commerciale**: tasso BCE + 8 punti (D.Lgs. 231/2002)
- **Privato**: tasso legale art. 1284 c.c.

### 2. Rivalutazione monetaria

Chiama `legal-it:rivalutazione_monetaria`.

**Nota**: mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi, indica il piu favorevole.

### 3. Decreto ingiuntivo

Chiama `legal-it:decreto_ingiuntivo`: competenza, CU, requisiti, provvisoria esecutivita.

### 4. Parcella

Chiama `legal-it:parcella_avvocato_civile` per fase monitoria.
