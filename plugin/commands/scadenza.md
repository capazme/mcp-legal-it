---
name: scadenza
description: Calcola una scadenza processuale o termine
argument-hint: "[tipo scadenza] [data di riferimento, es. 2026-06-18]"
allowed-tools: mcp__legal-it__scadenza_processuale, mcp__legal-it__termini_processuali_civili, mcp__legal-it__termini_183_190_cpc, mcp__legal-it__scadenze_impugnazioni, mcp__legal-it__termini_esecuzioni, mcp__legal-it__prescrizione_diritti, mcp__legal-it__prescrizione_reato, mcp__legal-it__termini_memorie_repliche
---

In base al tipo di scadenza richiesta:

- **Termini processuali civili**: Usa `legal-it:scadenza_processuale` o `legal-it:termini_processuali_civili` (memorie ex art. 171-ter a ritroso dall'udienza ex art. 183; note, conclusionale e replica ex art. 189 a ritroso dall'udienza di rimessione in decisione).
- **Memorie 183/190 c.p.c. (solo cause iscritte prima del 28/02/2023)**: Usa `legal-it:termini_183_190_cpc` con data udienza. Il tool è marcato `Regime: PREVIGENTE`: per le cause successive usa `termini_memorie_repliche`.
- **Impugnazioni**: Usa `legal-it:scadenze_impugnazioni` con tipo e data pubblicazione.
- **Esecuzioni**: Usa `legal-it:termini_esecuzioni`.
- **Prescrizione**: Usa `legal-it:prescrizione_diritti` (civile) o `legal-it:prescrizione_reato` (penale).
- **Memorie e repliche**: Usa `legal-it:termini_memorie_repliche`.

Chiedi la data di riferimento se non specificata e se la causa è tra quelle escluse dalla sospensione feriale (lavoro, previdenza, sfratti, opposizioni esecutive, cautelari: art. 3 L. 742/1969), nel qual caso passa `sospensione_feriale=False`. Indica se il termine cade in giorno festivo (proroga al primo giorno non festivo per i termini in avanti, anticipazione per quelli a ritroso) e se la sospensione feriale ha inciso sul conteggio (`sospensione_feriale_incidente`).
