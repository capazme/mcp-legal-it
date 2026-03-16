---
name: parcella
description: Calcola la parcella avvocato per un'attivita legale
allowed-tools: mcp__legal-it__parcella_avvocato_civile, mcp__legal-it__parcella_avvocato_penale, mcp__legal-it__parcella_stragiudiziale
---

Chiedi all'utente (se non ha gia specificato): tipo di attivita (civile, penale, stragiudiziale) e valore della causa.

- **Civile**: Usa `legal-it:parcella_avvocato_civile` con valore e fasi processuali.
- **Penale**: Usa `legal-it:parcella_avvocato_penale` con tipo di reato e fasi.
- **Stragiudiziale**: Usa `legal-it:parcella_stragiudiziale` con valore e attivita.

Mostra il dettaglio per fase (studio, introduttiva, trattazione/istruttoria, decisionale) con compenso minimo, medio e massimo (D.M. 55/2014).
