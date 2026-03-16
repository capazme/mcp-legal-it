---
name: interessi
description: Calcola interessi legali o di mora su un importo
allowed-tools: mcp__legal-it__interessi_legali, mcp__legal-it__interessi_mora, mcp__legal-it__rivalutazione_monetaria
---

Chiedi all'utente (se non ha gia specificato): importo, data decorrenza, tipo (legale o mora commerciale).

- **Interessi legali**: Usa `interessi_legali` con importo e data_decorrenza.
- **Interessi di mora commerciale**: Usa `interessi_mora` (tasso BCE + 8 punti, D.Lgs. 231/2002).
- **Rivalutazione monetaria**: Se utile, calcola anche con `rivalutazione_monetaria`.

Nota: interessi di mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi indicando quale e piu favorevole.
