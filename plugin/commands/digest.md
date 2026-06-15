---
name: digest
description: Briefing giuridico settimanale dalle ultime novita di tutte le fonti (Cassazione, tributario, TAR/CdS, CGUE, Garante, CONSOB); opzionalmente pianificabile come cron settimanale
argument-hint: "[tema o settore opzionale, es. 'privacy' | 'schedule' per pianificare]"
allowed-tools: mcp__legal-it__ultime_pronunce, mcp__legal-it__ultime_sentenze_tributarie, mcp__legal-it__ultimi_provvedimenti_amm, mcp__legal-it__ultime_sentenze_cgue, mcp__legal-it__ultimi_provvedimenti_garante, mcp__legal-it__ultime_delibere_consob, mcp__legal-it__leggi_sentenza, mcp__legal-it__cite_law
---

# Digest giuridico settimanale

Produce un briefing markdown delle ultime novita da tutte le fonti istituzionali.

## Esecuzione on demand

Se l'argomento NON e' `schedule` (o e' vuoto / un tema), esegui subito il briefing:

1. Interroga **tutte e sei** le fonti `ultime_*`:
   - `legal-it:ultime_pronunce` (Cassazione)
   - `legal-it:ultime_sentenze_tributarie` (CeRDEF/MEF)
   - `legal-it:ultimi_provvedimenti_amm` (TAR/CdS)
   - `legal-it:ultime_sentenze_cgue` (CGUE)
   - `legal-it:ultimi_provvedimenti_garante` (Garante Privacy)
   - `legal-it:ultime_delibere_consob` (CONSOB)
   Se l'utente ha indicato un tema/settore, applica i filtri pertinenti (`materia`, `argomento`, `ente`, `sede`, `tipologia`); altrimenti chiama senza filtri.
2. Deduplica per estremi (numero + anno + organo).
3. Raggruppa per fonte (ometti le sezioni vuote; dichiara le fonti non disponibili).
4. **In evidenza**: scegli le 3 piu' rilevanti; per la Cassazione approfondisci con `legal-it:leggi_sentenza`.
5. **Norme citate**: recupera il testo vigente con `legal-it:cite_law`. Mai a memoria.
6. Intesta con `# Briefing settimanale — settimana del <data corrente>`.

Per il workflow dettagliato e la struttura completa dell'output, delega all'agente `digest-giuridico` o usa la skill omonima.

## Pianificazione settimanale (one-time setup)

Se l'argomento e' `schedule`, NON eseguire il briefing: configura un cron settimanale durevole una sola volta.

Registra il job tramite la **CronCreate** dell'harness con `durable: true` (persiste in `.claude/scheduled_tasks.json` e sopravvive ai riavvii):

- **cron**: `37 8 * * 1` — lunedi alle 08:37. Usa un minuto **diverso da :00 e :30** per non far convergere tutte le richieste sullo stesso istante (qui :37).
- **prompt**: `Esegui /digest e salva il briefing settimanale.`
- **recurring**: `true`
- **durable**: `true`

> ⚠️ **AVVERTENZA — i job ricorrenti durevoli scadono dopo 7 giorni.** Un job `recurring: true` viene eseguito un'ultima volta e poi **eliminato automaticamente dopo 7 giorni** (limite dell'harness, vale anche per i durevoli). Per una pianificazione settimanale stabile occorre **ri-registrarlo periodicamente** oppure, per durabilita' reale, usare il **cron di sistema del sistema operativo** (`crontab -e`) che invochi il client in modalita' headless. Comunica sempre questo limite all'utente quando pianifichi.

> ⚠️ **Il frontmatter del plugin NON ha un campo `cron`.** Comandi, agenti e skill non possono auto-pianificarsi tramite manifest: la pianificazione passa esclusivamente per la CronCreate dell'harness (sessione/durevole) o per il cron di sistema. Non aggiungere campi di scheduling al frontmatter — verrebbero ignorati.

Dopo la registrazione, conferma all'utente: ID del job, espressione cron, e il promemoria della scadenza a 7 giorni.
