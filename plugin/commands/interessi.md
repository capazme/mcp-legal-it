---
name: interessi
description: Calcola interessi legali o di mora su un importo
argument-hint: "[importo data_inizio data_fine tipo(legale|mora)]"
allowed-tools: mcp__legal-it__interessi_legali, mcp__plugin_legal-it_legal-it__interessi_legali, mcp__legal-it__interessi_mora, mcp__plugin_legal-it_legal-it__interessi_mora, mcp__legal-it__rivalutazione_monetaria, mcp__plugin_legal-it_legal-it__rivalutazione_monetaria
---

Chiedi all'utente (se non ha gia specificato): importo (capitale), data inizio decorrenza (data_inizio), data fine/calcolo (data_fine), tipo (legale o mora commerciale).

- **Interessi legali**: Usa `legal-it:interessi_legali` con `capitale`, `data_inizio` e `data_fine`.
- **Interessi di mora commerciale**: Usa `legal-it:interessi_mora` (tasso BCE + 8 punti, D.Lgs. 231/2002).
- **Rivalutazione monetaria**: Se utile, calcola anche con `legal-it:rivalutazione_monetaria` (`capitale`, `data_inizio`, `data_fine`, opzionale `con_interessi_legali`).

Nota: per un credito di denaro la rivalutazione non è automatica: è il maggior danno dell'art. 1224, co. 2, c.c., da chiedere e provare. Secondo Cass. SS.UU. n. 19499/2008 si presume quando, durante la mora, il rendimento netto dei titoli di Stato fino a 12 mesi ha superato il saggio legale (verificalo sui dati del periodo di mora: con un saggio legale basso, come l'1,60% del 2026 fissato dal DM MEF 10/12/2025, la presunzione può tornare a operare); per somme maggiori il creditore deve provarlo (l'imprenditore, ad esempio, con il costo del credito bancario o la redditività dell'impresa), e il debitore può provare che il denaro non avrebbe reso di più. Spetta solo per la parte che eccede gli interessi moratori: i due importi non si sommano. La rivalutazione ISTAT è una stima di confronto, non il criterio delle SS.UU.
