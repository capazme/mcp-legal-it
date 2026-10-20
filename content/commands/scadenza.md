---
name: scadenza
description: Calcola una scadenza processuale o termine
argument-hint: "[tipo scadenza] [data di riferimento, es. 2026-06-18]"
tools: scadenza_processuale, termini_processuali_civili, termini_183_190_cpc, scadenze_impugnazioni, termini_esecuzioni, prescrizione_diritti, prescrizione_reato, termini_memorie_repliche
---

In base al tipo di scadenza richiesta:

- **Termini processuali civili**: Usa `scadenza_processuale` o `termini_processuali_civili` (memorie ex art. 171-ter a ritroso dall'udienza ex art. 183; note, conclusionale e replica ex art. 189 a ritroso dall'udienza di rimessione in decisione).
- **Memorie 183/190 c.p.c. (solo cause iscritte prima del 28/02/2023)**: Usa `termini_183_190_cpc` con data udienza. Il tool è marcato `Regime: PREVIGENTE`: per le cause successive usa `termini_memorie_repliche`.
- **Impugnazioni**: Usa `scadenze_impugnazioni` con tipo e data pubblicazione.
- **Esecuzioni**: Usa `termini_esecuzioni`.
- **Prescrizione**: Usa `prescrizione_diritti` (civile) o `prescrizione_reato` (penale).
- **Memorie e repliche**: Usa `termini_memorie_repliche`.

Chiedi la data di riferimento se non specificata e se la causa è tra quelle escluse dalla sospensione feriale (lavoro, previdenza, sfratti, opposizioni esecutive, cautelari: art. 3 L. 742/1969), nel qual caso passa `sospensione_feriale=False`. Indica se il termine cade in giorno festivo (proroga al primo giorno non festivo per i termini in avanti, anticipazione per quelli a ritroso) e se la sospensione feriale ha inciso sul conteggio (`sospensione_feriale_incidente`).
