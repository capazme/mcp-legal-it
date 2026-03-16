---
name: scadenza
description: Calcola una scadenza processuale o termine
allowed-tools: mcp__legal-it__scadenza_processuale, mcp__legal-it__termini_processuali_civili, mcp__legal-it__termini_183_190_cpc, mcp__legal-it__scadenze_impugnazioni, mcp__legal-it__termini_esecuzioni, mcp__legal-it__prescrizione_diritti, mcp__legal-it__prescrizione_reato, mcp__legal-it__termini_memorie_repliche
---

In base al tipo di scadenza richiesta:

- **Termini processuali civili**: Usa `legal-it:scadenza_processuale` o `legal-it:termini_processuali_civili`.
- **Memorie 183/190 c.p.c.**: Usa `legal-it:termini_183_190_cpc` con data udienza.
- **Impugnazioni**: Usa `legal-it:scadenze_impugnazioni` con tipo e data pubblicazione.
- **Esecuzioni**: Usa `legal-it:termini_esecuzioni`.
- **Prescrizione**: Usa `legal-it:prescrizione_diritti` (civile) o `legal-it:prescrizione_reato` (penale).
- **Memorie e repliche**: Usa `legal-it:termini_memorie_repliche`.

Chiedi la data di riferimento se non specificata. Indica se il termine cade in giorno festivo (proroga al primo giorno lavorativo utile).
