---
name: dati
description: Mostra lo stato di freschezza delle tabelle dati del server e il backlog di riconciliazione, ordinato per quanto blocca davvero
argument-hint: "[nome tabella opzionale, es. contributo_unificato]"
allowed-tools: mcp__legal-it__backlog_riconciliazione, Bash, Read
---

# Comando /dati — aggiornare le tabelle senza aprire il codice

Chiama `legal-it:backlog_riconciliazione` e mostra il risultato così com'è: le
tabelle da riconciliare (o scadute) con il loro stato, chi le legge e con quale
esito previsto, e — quando `LEGAL_REFUSAL_LEDGER=on` — i rifiuti osservati che
le mettono in cima alla lista.

## Se l'utente ha indicato una tabella (`$ARGUMENTS`)

1. Trovala nella lista del backlog e mostra: stato (`non_verificata` /
   `scaduta`), fonte dichiarata, nota, tool coinvolti (rifiutano / degradano)
   e l'`azione` suggerita.
2. Guida la verifica della fonte: apri nel browser (o cerca nel web) la fonte
   indicata nel campo `fonte`, confronta i valori della tabella con quelli
   ufficiali e riferisci le differenze una per una.
3. Dopo la conferma dell'utente, aggiorna il file indicato dall'`azione`
   (`src/data/<tabella>.json`): i valori, poi `verifica: manuale` e
   `aggiornato_al` di oggi nel blocco `_vintage`. Se la fonte pubblica un
   periodo coperto, imposta anche `copre_fino_a`.
4. Aggiorna la coppia speculare se esiste (il file vive in
   `plugin/server/src/data/`, con `src/data` come symlink): non duplicare.
5. Riesegui `python3 scripts/update-data.py` per la conferma, e la suite dei
   golden (`GOLDEN_UPDATE=1 pytest tests/unit/test_golden_calcoli.py`) se dei
   numeri sono cambiati. Riporta il riepilogo.

## Se l'utente non ha indicato nulla

Mostra il backlog in forma di tabella (tabella | stato | rifiutano | degradano)
e proponi la prima della lista, spiegando in una riga perché è in cima (più
tool bloccati, o più rifiuti osservati dal verbale).

## Note

- Il `verbale_rifiuti` nel risultato del tool ha `disponibile: false` quando il
  ledger è spento: è il comportamento previsto, non un errore. Per attivarlo,
  `LEGAL_REFUSAL_LEDGER=on` nell'ambiente del server.
- Lo stesso comando esiste per la manutenzione da terminale:
  `python3 scripts/update-data.py` (stessa derivazione, vista da CLI).
- La serie storica dei rifiuti osservati (mese su mese) è il comando `/verbale`
  (`legal-it:verbale_mensile`, `scripts/verbale-report.py` da terminale).
- Non modificare mai il codice dei tool per cambiare un importo: gli importi
  vivono solo in `src/data/*.json`, e la suite segnala ogni effetto collaterale.
