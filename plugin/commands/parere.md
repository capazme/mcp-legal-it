---
name: parere
description: Redazione parere legale strutturato con citazioni normative verificate e giurisprudenza. Usa quando l'utente chiede un parere, un'opinione legale o un'analisi giuridica su una questione.
argument-hint: "[descrizione della questione giuridica]"
allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi, mcp__legal-it__cerca_giurisprudenza, mcp__legal-it__leggi_sentenza
---

Esegui il workflow della skill `parere-legale`.

Al termine, proponi all'utente di esportare il parere in Word/PDF tramite la skill `esporta-documento` (es. "esporta in word" / "esporta in pdf").
