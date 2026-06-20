---
name: interessi
description: Calcola interessi legali o di mora su un importo
argument-hint: "[importo data_inizio data_fine tipo(legale|mora)]"
allowed-tools: mcp__legal-it__interessi_legali, mcp__legal-it__interessi_mora, mcp__legal-it__rivalutazione_monetaria
---

Chiedi all'utente (se non ha gia specificato): importo (capitale), data inizio decorrenza (data_inizio), data fine/calcolo (data_fine), tipo (legale o mora commerciale).

- **Interessi legali**: Usa `legal-it:interessi_legali` con `capitale`, `data_inizio` e `data_fine`.
- **Interessi di mora commerciale**: Usa `legal-it:interessi_mora` (tasso BCE + 8 punti, D.Lgs. 231/2002).
- **Rivalutazione monetaria**: Se utile, calcola anche con `legal-it:rivalutazione_monetaria` (`capitale`, `data_inizio`, `data_fine`, opzionale `con_interessi_legali`).

Nota: interessi di mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi indicando quale e piu favorevole.
