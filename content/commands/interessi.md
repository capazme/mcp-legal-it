---
name: interessi
description: Calcola interessi legali o di mora su un importo
argument-hint: "[importo data_inizio data_fine tipo(legale|mora)]"
tools: interessi_legali, interessi_mora, rivalutazione_monetaria
---

Chiedi all'utente (se non ha gia specificato): importo (capitale), data inizio decorrenza (data_inizio), data fine/calcolo (data_fine), tipo (legale o mora commerciale).

- **Interessi legali**: Usa `interessi_legali` con `capitale`, `data_inizio` e `data_fine`.
- **Interessi di mora commerciale**: Usa `interessi_mora` (tasso BCE + 8 punti, D.Lgs. 231/2002).
- **Rivalutazione monetaria**: Se utile, calcola anche con `rivalutazione_monetaria` (`capitale`, `data_inizio`, `data_fine`, opzionale `con_interessi_legali`).

Nota: per un credito di denaro la rivalutazione non è automatica: è il maggior danno dell'art. 1224, co. 2, c.c., da chiedere e provare (anche in via presuntiva, Cass. SS.UU. n. 19499/2008), e spetta solo per la parte che eccede gli interessi moratori: i due importi non si sommano. Presenta entrambi i calcoli e indica il più favorevole.
