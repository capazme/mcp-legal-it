---
name: scadenza
description: Calcola una scadenza processuale o termine
allowed-tools: mcp__legal-it__scadenza_processuale, mcp__legal-it__termini_processuali_civili, mcp__legal-it__termini_183_190_cpc, mcp__legal-it__scadenze_impugnazioni, mcp__legal-it__termini_esecuzioni, mcp__legal-it__prescrizione_diritti, mcp__legal-it__prescrizione_reato, mcp__legal-it__termini_memorie_repliche
---

In base al tipo di scadenza richiesta:

- **Termini processuali civili**: Usa `scadenza_processuale` o `termini_processuali_civili`.
- **Memorie 183/190 c.p.c.**: Usa `termini_183_190_cpc` con data udienza.
- **Impugnazioni**: Usa `scadenze_impugnazioni` con tipo e data pubblicazione.
- **Esecuzioni**: Usa `termini_esecuzioni`.
- **Prescrizione**: Usa `prescrizione_diritti` (civile) o `prescrizione_reato` (penale).
- **Memorie e repliche**: Usa `termini_memorie_repliche`.

Chiedi la data di riferimento se non specificata. Indica se il termine cade in giorno festivo (proroga al primo giorno lavorativo utile).
