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

Chiedi la data di riferimento se non specificata e se la causa è tra quelle escluse dalla sospensione feriale (lavoro e previdenza, alimenti, cautelari per la sola fase cautelare, sfratti, opposizione all'esecuzione e le altre dell'art. 92 R.D. 12/1941, richiamato dall'art. 3 L. 742/1969; il mantenimento non è escluso: per quello passa `materia="mantenimento"`), nel qual caso passa `materia` con il codice della materia (es. `materia="lavoro_previdenza"`); se la materia non è nota, il tool lo segnala e accanto a ogni scadenza spostata da agosto dà `scadenza_se_materia_esclusa`. Per l'art. 482 riporta il primo giorno utile e, se il precetto indica un termine più lungo, passa `termine_precetto_giorni`; se il tool dà una `data_prudente`, riportala con il rischio di nullità del pignoramento anticipato. Indica se il termine cade in giorno festivo (proroga al primo giorno non festivo per i termini in avanti, anticipazione per quelli a ritroso) e se la sospensione feriale ha inciso sul conteggio (`sospensione_feriale_incidente`): in quel caso riporta all'utente l'elenco delle materie escluse che il tool restituisce in `avviso_sospensione_feriale`.
