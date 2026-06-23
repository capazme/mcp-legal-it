---
name: parcella
description: Calcola la parcella avvocato per un'attivita legale
argument-hint: "[civile|penale|stragiudiziale] [valore causa in euro]"
allowed-tools: mcp__legal-it__parcella_avvocato_civile, mcp__legal-it__parcella_avvocato_penale, mcp__legal-it__parcella_stragiudiziale
---

Chiedi all'utente (se non ha gia specificato): tipo di attivita (civile, penale, stragiudiziale) e valore della causa.

- **Civile**: Usa `legal-it:parcella_avvocato_civile` con valore e fasi processuali.
- **Penale**: Usa `legal-it:parcella_avvocato_penale` indicando la `competenza` (organo giudicante: giudice_pace, tribunale_monocratico, tribunale_collegiale, corte_assise, corte_appello, cassazione) e le fasi.
- **Stragiudiziale**: Usa `legal-it:parcella_stragiudiziale` con valore e attivita.

Mostra il dettaglio per fase (studio, introduttiva, istruttoria, decisionale) con compenso minimo, medio e massimo (D.M. 55/2014).
