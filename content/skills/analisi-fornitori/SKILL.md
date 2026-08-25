---
name: analisi-fornitori
description: Usa questa skill quando il cliente invia il mastrino fornitori (o un elenco fatture/fornitori) e serve lo screening privacy — es. «analizza il mastrino fornitori», «chi dobbiamo nominare responsabile ex art. 28», «screening fornitori GDPR», «analisi fornitori per la nomina», «il cliente ci ha mandato l'elenco dei fornitori/fatture». Estrae i fornitori da qualunque formato (Excel, CSV, PDF, scansioni, corpo mail), li deduplica, li identifica via web e VIES, ipotizza il ruolo privacy di ciascuno (Responsabile art. 28 / Titolare autonomo / Fuori perimetro) con confidenza tarata, produce l'Excel standard con genera_report_fornitori e, su conferma, le bozze di nomina ex art. 28 con genera_dpa per i responsabili senza DPA proprio.
tools: [genera_dpa, genera_report_fornitori, verifica_partita_iva_vies]
---

# Analisi fornitori — screening privacy del mastrino

Qualifica ogni fornitore del mastrino rispetto al ruolo privacy nel rapporto con il
**cliente dello studio (il titolare del trattamento)**. È uno screening di primo
livello: la qualifica dipende dalla prestazione CONCRETA resa al cliente, che il
mastrino non rivela — l'esito va validato con cliente e contratti, e la Confidenza
deve rifletterlo.

## Regole d'oro (valgono in ogni fase)

1. **Mai inventare**: attività, P.IVA e servizi si affermano solo con una fonte
   (URL) o con conferma VIES. Fornitore non identificabile → categoria più
   probabile + Confidenza `basso` + alternative in `note`.
2. **Gli importi sono irrilevanti**: ignorarli sempre.
3. **Confidenza al ribasso**: nel dubbio, abbassa. `alto` SOLO con identificazione
   univoca confermata (P.IVA presente o agganciata via VIES). Senza P.IVA nel
   mastrino, `alto` è l'eccezione.
4. **Contratto canonico**: ogni fornitore analizzato è un oggetto JSON con i campi
   di `references/metodologia.md` §Contratto. I tool lo validano — rispettalo.

## Fase 0 — Setup

Chiedi (se non già noti): denominazione del **cliente titolare** e file del
mastrino. Crea `analisi_fornitori_checkpoint.json` accanto al mastrino (fallback:
directory corrente). Se esiste già un checkpoint per quel mastrino, proponi di
riprendere dal primo fornitore non analizzato invece di ripartire.

Struttura del checkpoint:

```json
{
  "versione": 1,
  "cliente": "...",
  "file_mastrino": "...",
  "creato": "ISO-8601",
  "fase": "estrazione | dedup | ricerca | completata",
  "fornitori_estratti": [],
  "fornitori_unici": [],
  "analisi": []
}
```

Aggiorna il checkpoint dopo OGNI mutazione (fine estrazione, fine dedup, fine di
ogni blocco di ricerca).

## Fase 1 — Estrazione

Leggi il mastrino nel formato in cui arriva (guida per formato in
`references/metodologia.md` §Estrazione). Estrai per ogni riga: denominazione
e P.IVA/CF se presente. Se il file è illeggibile (scansione pessima, corrotto):
fermati e chiedi una copia migliore. Salva in `fornitori_estratti`.

## Fase 2 — Dedup e gate

Applica le regole di `references/metodologia.md` §Dedup. Salva in
`fornitori_unici` (con le varianti unificate in `varianti`). Poi **fermati** e
chiedi: *«N fornitori unici (da M righe). Procedo con la ricerca? [tempo stimato:
~X min]»*. Sopra ~40 fornitori proponi anche la modalità parallela (sotto).

## Fase 3 — Ricerca e classificazione

A blocchi di ~15 fornitori. Per ciascuno:

1. **Aggancio**: se ha P.IVA → `verifica_partita_iva_vies(partita_iva=...)`. Se
   `valido` e `denominazione` compatibile → identità confermata (`fonte_piva`
   resta `"mastrino"`; annota la conferma). Se il VIES è indisponibile
   (`disponibile: false`) → prosegui web-only e annotalo in `note`.
2. **Ricerca web**: attività e servizi reali (strategia e query in
   `references/metodologia.md` §Identificazione). Cita sempre la fonte in `fonti`.
3. **Classificazione**: applica `references/classificazione.md` (3 categorie,
   casi controversi con default e flag).
4. **DPA** (solo responsabili): consulta `references/dpa-whitelist.md`; se non in
   lista, ricerca mirata «{fornitore} data processing agreement / DPA / nomina
   responsabile»; esito `si`/`no`/`da_verificare`.
5. **Confidenza**: tabella in `references/metodologia.md` §Confidenza.

Appendi ogni record completato ad `analisi` nel checkpoint a fine blocco.

### Modalità parallela (>~40 fornitori, su conferma dell'utente)

Elabora a blocchi di ~15 fornitori; se il tuo ambiente supporta l'esecuzione parallela
(subagent), lancia un blocco per subagent con questo prompt, compilando i placeholder:

> Sei un DPO esperto di GDPR e prassi del Garante. Analizza questi fornitori del
> cliente «{CLIENTE}» (titolare del trattamento) e restituisci SOLO un array JSON
> di record canonici, nessun altro testo. Per ogni fornitore: (1) se ha P.IVA
> usa il tool verifica_partita_iva_vies per confermare l'identità; (2) ricerca
> web per attività/servizi, cita gli URL in `fonti`, non inventare nulla; (3)
> classifica secondo le regole che seguono; (4) per i responsabili valuta se il
> fornitore pubblica un proprio DPA standard; (5) taratura confidenza: `alto`
> solo con P.IVA confermata, nel dubbio abbassa. Fornitore non identificabile o
> omonimia → categoria più probabile, confidenza `basso`, alternative in `note`.
> REGOLE DI CLASSIFICAZIONE: {contenuto integrale di references/classificazione.md}
> CONTRATTO RECORD: {sezione Contratto di references/metodologia.md}
> WHITELIST DPA: {contenuto di references/dpa-whitelist.md}
> FORNITORI DA ANALIZZARE: {blocco JSON da fornitori_unici}

Al merge di ogni blocco applica i **guardrail**:
- record con `confidenza: "alto"` senza P.IVA confermata → declassa a `"medio"`;
- record che non rispettano il contratto → scarta e rifai quel blocco in
  modalità sequenziale.

## Fase 4 — Report

Chiama `genera_report_fornitori(fornitori=<analisi dal checkpoint>,
cliente=..., data_analisi=..., file_sorgente=...)`. Se restituisce errori di
validazione, correggi i record indicati e richiama. Consegna il file all'utente
e imposta `fase: "completata"` (report e nomine sono rigenerabili in qualsiasi
momento dai dati del checkpoint).

## Fase 5 — Nomine ex art. 28 (su conferma)

Elenca i responsabili con `dpa_proprio: "no"` e chiedi UNA conferma per
generarle tutte. Per ciascuno chiama `genera_dpa` con titolare = cliente,
responsabile = fornitore (usa denominazione confermata e P.IVA se nota) e la
descrizione del trattamento derivata da `attivita`/`categorie_dati`. Un DOCX
per fornitore. Ricorda all'utente che per i responsabili `da_verificare` va
prima chiarito il rapporto contrattuale.
