---
name: verbale
description: Report mensile dei rifiuti osservati dal verbale, con confronto mese su mese e classifica di cosa ha bloccato davvero
argument-hint: "[mesi opzionale, default 6]"
allowed-tools: mcp__legal-it__verbale_mensile, Bash, Read
---

# Comando /verbale — la serie storica dei rifiuti

Chiama `legal-it:verbale_mensile` (con `months: $ARGUMENTS` se indicato) e
mostra la serie: una riga per mese con rifiuti, accettazioni, il delta col mese
precedente e il tool/tabella che ha guidato il mese.

## Cosa leggere nella serie

1. **Il mese corrente**: se `delta_mese_precedente` è positivo, il primo posto
   della classifica (`top_tool`, `top_tabella`) dice *cosa* è peggiorato —
   parti da lì, non dal backlog completo.
2. **Il confronto col backlog**: chiama anche `legal-it:backlog_riconciliazione`
   e incrocia: una tabella con rifiuti osservati ma zero `rifiutano` statici
   indica che la qualità dei dati è peggiorata dopo l'ultima verifica (o che
   qualcuno ha rimosso una `alternativa`); una tabella in cima al backlog senza
   rifiuti osservati è rumore, non priorità.
3. **Un mese a zero non è un buco**: o il verbale è spento
   (`disponibile: false` — dillo esplicitamente e suggerisci
   `LEGAL_REFUSAL_LEDGER=on`), o il mese è andato davvero liscio.

## Manutenzione senza aprire il codice

- Stessa aggregazione da terminale: `python3 scripts/verbale-report.py`
  (`--out report.md` per archiviarlo, `--strict` per far fallire una pipeline
  quando il mese è peggiorato).
- Il verbale registra **solo** rifiuti e accettazioni di precisione — mai dati
  di causa. Nessun regime di riservatezza necessario.
- Dopo una riconciliazione (vedi `/dati`), il mese successivo deve mostrare il
  calo: se non lo mostra, la riconciliazione non ha toccato i tool che
  bloccano davvero.

## Nota

Il report legge `<MCP_CACHE_DIR>/refusals.jsonl`, lo stesso file che il
middleware scrive a ogni rifiuto/accettazione: tool e script non possono mai
disaccordarsi sui numeri.
