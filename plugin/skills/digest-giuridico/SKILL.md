---
name: digest-giuridico
description: Briefing giuridico settimanale dalle ultime novita di tutte le fonti istituzionali (Cassazione, tributario, TAR/CdS, CGUE, Garante Privacy, CONSOB), deduplicato e raggruppato per fonte. Usa quando l'utente chiede le novita della settimana, un riepilogo periodico, un digest giuridico, le ultime decisioni o un aggiornamento complessivo su piu fonti.
---

# Digest Giuridico

Briefing settimanale delle ultime novita da tutte le fonti, raggruppato per fonte.

## Workflow

### 1. Raccolta — tutte le fonti

Interroga **tutte e sei** le `ultime_*` (con `max_risultati` 5-10 per fonte):
- `legal-it:ultime_pronunce` (Cassazione) — filtri: `materia`, `sezione`, `archivio`, `tipo_provvedimento`, `solo_sezioni_unite`
- `legal-it:ultime_sentenze_tributarie` (CeRDEF/MEF) — filtri: `ente`, `tipo_provvedimento`
- `legal-it:ultimi_provvedimenti_amm` (TAR/CdS) — filtri: `sede`, `tipo`
- `legal-it:ultime_sentenze_cgue` (CGUE) — filtri: `corte`, `tipo_documento`, `materia`
- `legal-it:ultimi_provvedimenti_garante` (Garante Privacy) — filtro: `tipologia`
- `legal-it:ultime_delibere_consob` (CONSOB) — filtri: `tipologia`, `argomento`

Se l'utente indica un tema/settore, applica i filtri pertinenti su ogni fonte che li supporta. Se una fonte e' irraggiungibile, registrala come non disponibile e prosegui (degrado visibile, mai silenzioso).

### 2. Deduplica

Una decisione puo' comparire in piu' liste (es. sentenza tributaria della Cassazione). Deduplica per estremi (numero + anno + organo).

### 3. Approfondimento (In evidenza)

Scegli le 2-3 decisioni piu' rilevanti (Sezioni Unite, novita' di principio, sanzioni significative). Per la Cassazione: `legal-it:leggi_sentenza` con numero e anno per dispositivo e massima.

### 4. Quadro normativo

Per le norme richiamate dalle decisioni in evidenza: `legal-it:cite_law`. Mai a memoria.

## Output atteso

### Intestazione
`# Briefing settimanale — settimana del <data corrente>`, con riga delle fonti interrogate e delle eventuali fonti non disponibili.

### In evidenza (top 3)
Le 3 decisioni piu' rilevanti della settimana, ciascuna con estremi, fonte e una riga di rilevanza pratica.

### Per ciascuna fonte
Tabella delle novita' (estremi, organo/sede, materia/argomento, tipo, data). Ometti le sezioni vuote.

### Norme citate
Articoli richiamati dalle decisioni in evidenza con testo vigente da `legal-it:cite_law`.
