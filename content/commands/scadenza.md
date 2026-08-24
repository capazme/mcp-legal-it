---
name: scadenza
description: Calcola una scadenza processuale o termine
argument-hint: "[tipo scadenza] [data di riferimento, es. 2026-06-18]"
tools: scadenza_processuale, termini_processuali_civili, termini_183_190_cpc, scadenze_impugnazioni, termini_esecuzioni, prescrizione_diritti, prescrizione_reato, termini_memorie_repliche
---

In base al tipo di scadenza richiesta:

- **Termini processuali civili**: Usa `scadenza_processuale` o `termini_processuali_civili`.
- **Memorie 183/190 c.p.c.**: Usa `termini_183_190_cpc` con data udienza.
- **Impugnazioni**: Usa `scadenze_impugnazioni` con tipo e data pubblicazione.
- **Esecuzioni**: Usa `termini_esecuzioni`.
- **Prescrizione**: Usa `prescrizione_diritti` (civile) o `prescrizione_reato` (penale).
- **Memorie e repliche**: Usa `termini_memorie_repliche`.

Chiedi la data di riferimento se non specificata. Indica se il termine cade in giorno festivo (proroga al primo giorno lavorativo utile).
