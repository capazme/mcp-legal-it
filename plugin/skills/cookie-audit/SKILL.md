---
name: cookie-audit
description: Usa questa skill per l'audit di cookie, pixel e altri strumenti di tracciamento di un sito e delle sue newsletter — es. «analisi cookie», «che cookie o pixel usa questo sito», «c'è il pixel di Meta/TikTok?», «analizza il banner», «verifica la conformità cookie», «mappatura degli strumenti di tracciamento», «tracking pixel nelle email/newsletter», «adeguamento alle linee guida del Garante sui pixel». Osserva il sito nel browser prima e dopo il consenso (cookie, pixel, ID, dati inviati), legge lato server il container GTM e la configurazione dei pixel Meta, analizza i file .eml delle newsletter (pixel individuali, link tracciati, revoca granulare), valuta la conformità (art. 122 Codice privacy, GDPR, Linee guida cookie 2021, Linee guida sui tracking pixel nelle e-mail 2026), esporta un report Word e propone la remediation. Usala anche quando l'utente nomina un sito o una newsletter e chiede genericamente «i cookie», «i pixel» o «il tracciamento».
---

# Cookie Audit — cookie, pixel e tracciamento di sito e newsletter

Produce un'analisi tecnico-legale degli strumenti di tracciamento di un sito pubblico e delle sue newsletter, con la rigorosità di un accertamento privacy: non ci si limita a leggere la cookie policy dichiarata (spesso auto-generata e imprecisa), ma si **osserva il comportamento reale** — nel browser, distinguendo ciò che accade **prima** e **dopo** il consenso, e nelle email effettivamente ricevute.

## Cosa produce
1. **Tabella cookie unica** — nome · fornitore/dominio · finalità · durata · categoria · stato (osservato / atteso / condizionale).
2. **Mappa dei pixel e dei tracciatori** — sito e newsletter: strumento · dove · ID · eventi e dati inviati · momento (pre/post consenso, all'apertura, al clic) · stato. Comprende CMP, container GTM e regole di attivazione dei tag, Advanced Matching, tagging lato server, piattaforma di invio delle email.
3. **Valutazione di conformità** — Provvedimento del Garante 10 giugno 2021 (cookie e altri strumenti di tracciamento), Linee guida del Garante sui tracking pixel nelle comunicazioni di posta elettronica (17 aprile 2026, adeguamento entro il **29 ottobre 2026**), GDPR, art. 122 Cod. privacy (vedi `references/compliance-checklist.md` e `references/newsletter-tracking.md`).
4. **Report Word** su richiesta (`scripts/generate_report.js`).
5. **Remediation** su richiesta — bozza di cookie policy e di informativa allineate allo stack reale + checklist di adeguamento.

## Principio cardine
Il test decisivo del diritto italiano/UE è: **nessun cookie non tecnico, nessun pixel e nessuna chiamata a terze parti non necessarie prima di un consenso libero e specifico** (art. 122 Cod. Privacy, che recepisce l'art. 5(3) Dir. ePrivacy). Il pixel è uno strumento di tracciamento anche quando non scrive cookie. Nelle email il pixel di apertura è un accesso al terminale del destinatario: serve sempre l'informativa e, salvo le deroghe delle Linee guida 2026, il consenso. Tutto il metodo ruota attorno a verificare empiricamente questi punti.

---

## Percorso ripetibile (minimo coinvolgimento del cliente)
Per mappare un cliente servono solo il **dominio del sito** e **due caselle email di prova dello studio**. Il resto si osserva dall'esterno:

| Passo | Cosa | Strumento | Coinvolge il cliente? |
|-------|------|-----------|-----------------------|
| A | Sito prima e dopo il consenso: cookie, pixel, ID, dati inviati | Fasi 1-3, sonde §1-§6 | No |
| B | Container GTM e configurazione dei pixel Meta | Fasi 3-bis e 3-ter (script lato server) | No |
| C | Modulo di iscrizione alla newsletter: informativa e consenso | Fase 5, sonda §7 | No |
| D | Newsletter: iscrizione con le due caselle di prova, analisi dei `.eml` | Fase 5, `inspect_newsletter.py` | No |
| E | Solo ciò che non si vede da fuori (piattaforma, uso dei dati di apertura, liste esistenti) | 8 domande in `references/newsletter-tracking.md` | Sì, minimo |
| F | Mappa unica, valutazione, priorità rispetto alle scadenze | Fase 6 | — |

---

## Metodo

### Setup del browser
Serve un MCP browser che sappia (a) navigare, (b) eseguire JavaScript nella pagina, (c) leggere le richieste di rete. Vanno bene **chrome-devtools** (`mcp__chrome-devtools__*`) o **claude-in-chrome** (`mcp__claude-in-chrome__*`); carica i tool via `ToolSearch` se sono deferred. Preferire chrome-devtools quando disponibile (contesto isolato, lettura della rete e del **corpo** delle richieste).

Apri il sito in un **contesto isolato/pulito** (nessun cookie pregresso) — es. `new_page({url, isolatedContext:"cookieaudit"})`. Un contesto sporco falsa la Fase 1. Per ripetere la prova (es. «Rifiuta» dopo «Accetta») apri un **nuovo** contesto isolato: il marcatore del consenso che separa le chiamate pre/post (§3) vive nel sessionStorage della scheda. Con chrome-devtools puoi ampliare subito il buffer delle richieste: `navigate_page({…, initScript: "performance.setResourceTimingBufferSize(5000)"})`.

⚠️ **Caveat ad-blocker (leggi sempre).** Molti browser hanno uBlock Origin o simili. Un ad-blocker: blocca il CSS `cookieblocker`, nasconde cosmeticamente il banner (`display:none`), **sostituisce `gtm.js`/`gtag/js` con uno stub**, blocca gli endpoint analytics e i pixel — talvolta **la CMP stessa**. Sintomi: `_ga` non compare dopo il consenso, `gtm.js` pesa pochi KB, richieste `net::ERR_BLOCKED_BY_CLIENT`. In tal caso le osservazioni **pre-consenso restano valide** (una richiesta avviata dal sito conta anche se il tuo browser la blocca), ma per l'inventario reale **non fidarti del browser**: usa le Fasi 3-bis e 3-ter (lato server) e gli `inlineIds` della sonda §5. Dichiara sempre questo caveat nel report e marca le voci non osservate come «Atteso».

I frammenti JavaScript esatti da incollare nel tool «evaluate script» sono in **`references/browser-probes.md`**.

### Fase 1 — Stato PRE-consenso (il test cardine)
Subito dopo il caricamento, **prima di toccare il banner**, esegui la probe pre-consenso (§1), la **sonda pixel (§5)** e la lista delle richieste di rete. Raccogli:
- `document.cookie`, `localStorage`, `sessionStorage`;
- richieste verso **domini di terze parti** (tutto ciò che non è il dominio del sito);
- pixel che hanno già trasmesso eventi (`hits`) o caricato la libreria (`scripts`), con ID, eventi, dati utente e segnali di consenso (`gcs`…);
- ID dei pixel scritti nel codice della pagina (`inlineIds`), anche se non sono ancora partiti.

**Valuta:** ci sono cookie di analytics/marketing o **chiamate di pixel** prima del consenso? Hit verso `google-analytics.com/…/collect`, `facebook.com/tr`, LinkedIn, TikTok, DoubleClick? Ping Google con `gcs=G100` (Consent Mode avanzata)? Anche il solo caricamento di `gtm.js` o di una libreria pixel comunica l'IP al fornitore: zona grigia da segnalare (vedi checklist).

### Fase 2 — CMP e banner
Identifica la **Consent Management Platform** dai prefissi cookie / globali JS / selettori (tabella in `references/cmp-tracker-fingerprints.md`). Poi ispeziona il DOM del banner (§2) — se l'ad-blocker lo nasconde, leggilo comunque dal DOM. Verifica i punti del Garante:
- **parità Accetta/Rifiuta** sul primo livello (stesso peso grafico: colore, dimensione, posizione)?
- pulsante di **rifiuto** presente subito, senza livelli aggiuntivi?
- **granularità** (categorie) e link a cookie/privacy policy?
- **no scroll-acceptance**, no cookie wall?
- consenso reso **nella lingua** dell'utente?
- eventuale **IAB TCF** attivo (gestione vendor)?

### Fase 3 — Stato POST-consenso
Concedi il consenso completo (§3: imposta anche il **marcatore** che separa le chiamate pre/post; se clicchi a mano, esegui prima il marcatore), attendi ~2s, ri-esegui §1 e **§5**. Registra i cookie, i pixel e gli eventi che si aggiungono e i segnali **Google Consent Mode v2** (`ad_storage`, `ad_user_data`, `ad_personalization`, `analytics_storage`). Per i pixel che inviano i dati nel corpo della richiesta (TikTok, Snap, LinkedIn) usa §6: riporta solo i **nomi** dei campi utente, mai i valori.

### Fase 3-bis — Container GTM reale: tag, ID e regole di attivazione (bypassa l'ad-blocker)
Se il sito usa GTM (`GTM-XXXXXXX`) o il Google tag (`G-…`, `AW-…`), **analizza il container lato server**:
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cookie-audit/scripts/inspect_container.py" GTM-XXXXXXX
```
(`bash …/inspect_container.sh GTM-XXXXXXX` fa la stessa cosa; `--json` per l'output strutturato; un URL completo per i loader serviti dal dominio del sito.) Lo script legge il container come dato e riporta, tag per tag: il pixel o fornitore (Meta, TikTok, LinkedIn, Pinterest, Microsoft, Criteo, Floodlight, piattaforme email…), gli **ID**, gli **eventi**, i **dati utente** inviati (Advanced Matching, enhanced conversions, email con hash) e le **condizioni di attivazione** — con un verdetto regola per regola: le regole di attivazione sono alternative, quindi basta **una** regola che non legge una scelta di consenso (es. «All Pages», «Consent Initialization», un evento della CMP che parte a ogni caricamento come `OneTrustGroupsUpdated`) per il ⚠. Riporta anche i default di Consent Mode (⚠ se «granted» per default), i tag in pausa e gli indizi di **tagging lato server**. Interpreta i risultati con `references/pixel-fingerprints.md` e `cmp-tracker-fingerprints.md` (§ boilerplate GA4).

Limite: le condizioni sono quelle del container. Se la CMP blocca l'intero GTM fino al consenso, il container non lo mostra: il verdetto «⚠ senza vincolo» va confermato con la Fase 1.

### Fase 3-ter — Configurazione dei pixel Meta
Per ogni ID Meta trovato (rete, `inlineIds`, container):
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cookie-audit/scripts/inspect_pixel_config.py" <ID_PIXEL> [<ID_PIXEL> …]
```
Legge la configurazione che Meta pubblica per quel pixel: **Advanced Matching automatico** e campi letti dai moduli del sito (email, telefono, nome, data di nascita…), eventi automatici, parametri che Meta filtra come indesiderati (indizio di dati personali inviati in passato). Per TikTok la configurazione pubblicata non è affidabile: usa §6.

### Fase 3-quater — Inventario dichiarato
Apri la **cookie policy** del sito (di norma linkata nel footer / nel banner) ed estrai la tabella dei cookie e degli strumenti dichiarati. Confronta col reale: le policy auto-scansionate spesso elencano cookie di **CMP diverse** (es. `OptanonConsent` di OneTrust, `CookieConsent` di Cookiebot) o plugin **non in uso** (Elementor, WPML) → voci **spurie**, difetto di trasparenza (art. 13 GDPR); e quasi mai elencano i **pixel** senza cookie → omissione da segnalare.

### Fase 4 — Sintesi del sito
Consolida in **una tabella cookie** e **una mappa dei pixel** (vedi «Formato tabelle»). Valuta seguendo `references/compliance-checklist.md` (sezioni banner, informativa, pixel).

### Fase 5 — Newsletter (clienti che inviano email)
Segui `references/newsletter-tracking.md`:
1. **Modulo di iscrizione** sul sito: sonda §7 (informativa sintetica, testo del consenso, caselle preselezionate, menzione del tracciamento).
2. **Iscrizione con le due caselle di prova** dello studio; salva in `.eml` la mail di conferma/benvenuto e la prima newsletter.
3. **Analisi**:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/cookie-audit/scripts/inspect_newsletter.py" \
       --compare copia_prova1.eml copia_prova2.eml --recipient prova1@… --recipient prova2@…
   ```
   Riporta piattaforma di invio, pixel (individuale o uguale per tutti, dal confronto delle due copie), immagini con identificativi, link tracciati e ID portati sul sito, terze parti nel messaggio, indirizzo del destinatario negli URL (anche codificato o con hash), link di disiscrizione e di **revoca del solo tracciamento**, riferimenti all'informativa — con la valutazione rispetto ai §4-§6 delle Linee guida 2026.
4. **Collega sito e newsletter**: i parametri dei link (`mc_eid`, `_kx`, `_hsenc`, `vgo_ee`…) e gli script delle piattaforme email sul sito (sonda §5) sono lo stesso tracciamento visto da due lati.
5. **Domande al cliente**: solo le 8 di `newsletter-tracking.md` (piattaforma, uso dei dati di apertura, liste esistenti, prova del consenso…).

### Fase 6 — Mappa unica e valutazione
Unisci cookie, pixel del sito e tracciamento delle email in una **mappa unica degli strumenti di tracciamento**; per ciascuno: base giuridica necessaria, stato del consenso osservato, criticità e priorità (checklist § Remediation), con la scadenza del **29 ottobre 2026** per le newsletter. **Verifica le norme citate con `cite_law()`** prima di finalizzare (es. `art. 122 D.Lgs. 196/2003`, `art. 130 D.Lgs. 196/2003`, `art. 26 GDPR`); i provvedimenti del Garante con `leggi_provvedimento_garante`, le sentenze CGUE con `leggi_sentenza_cgue`; segnala come fuori copertura la Dir. ePrivacy e le Linee guida EDPB.

---

## Formato tabelle
**Tabella cookie** — colonne, in quest'ordine: **Nome cookie · Fornitore / Dominio · Finalità · Durata · Categoria · Stato**. Categorie: *Tecnico/necessario · Preferenze · Statistica · Marketing · Sicurezza*.

**Mappa dei pixel e dei tracciatori** — colonne: **Strumento · Dove · ID · Eventi e dati inviati · Momento · Stato**.
- *Dove*: Sito (pagina) · Container GTM · Newsletter (apertura) · Newsletter (clic) · Lato server.
- *Momento*: Pre-consenso · Post-consenso · All'apertura dell'email · Al clic · Non osservato (solo configurato).
- *Eventi e dati inviati*: nomi degli eventi (PageView, Purchase…) e **nomi** dei campi utente (`ud[em]`, email con hash…), mai i valori.

Stato (entrambe le tabelle), con legenda esplicita:
- **Osservato** — realmente presente nel browser o nell'email durante il test;
- **Atteso (post-consenso)** — non comparso per via dell'ad-blocker ma confermato dal container reale / codice della pagina / policy: presente per l'utente comune;
- **Configurato** — presente nel container o nel codice ma non osservato in funzione (es. scatta solo su eventi non riprodotti);
- **Condizionale** — solo su certe pagine (form, checkout, sottodomini) o certi messaggi.

Escludi (o segnala esplicitamente come spurie) le voci della policy che non trovano riscontro nel comportamento reale.

## Report Word (su richiesta)
Prepara un JSON con la struttura descritta in cima a `scripts/generate_report.js` (cookie, pixel, risultati newsletter), poi:
```
NODE_PATH="$(npm root -g)" node "${CLAUDE_PLUGIN_ROOT}/skills/cookie-audit/scripts/generate_report.js" audit.json "/percorso/Desktop/Analisi-tracciamento-<sito>-<data>.docx"
```
Richiede il pacchetto npm globale `docx` (`npm i -g docx`) — la stessa dipendenza di `esporta-documento`. Lo script stampa su stdout il path assoluto del file: riportalo sempre all'utente. La validazione del `.docx` è opzionale; se è installata la skill `docx` di Anthropic puoi usare `python ~/.claude/skills/docx/scripts/office/validate.py <file>`, altrimenti l'apertura del file conferma la buona formazione. In alternativa, per un report discorsivo in stile SAPG, scrivi il contenuto in markdown e passalo alla skill `esporta-documento`.

## Remediation (su richiesta)
Quando emergono criticità, produci — vedi `references/compliance-checklist.md` § Remediation:
1. **Bozza di cookie policy corretta** allineata allo stack reale, **pixel compresi** (puoi usare `genera_informativa_cookie` del plugin legal-it come base, poi correggere l'inventario coi dati raccolti).
2. Per le newsletter: **informativa sintetica nel modulo** + sezione estesa sul tracciamento delle email, **testo del consenso** (anche unico con il marketing, formulato in modo neutro), **footer con revoca granulare**.
3. **Checklist di adeguamento** ai provvedimenti del Garante, prioritizzata per gravità e per scadenza.

## Onestà del risultato
Distingui sempre osservato vs desunto. Se l'ad-blocker ha limitato le Fasi 1-3, dillo e offri di ripetere in un browser pulito. Non dichiarare durate di scadenza «esatte» se sono state desunte dalla config della CMP e non lette dal browser: `document.cookie` non espone la scadenza. Per i pixel: il container dice cosa è **configurato**, il browser cosa **parte davvero**; i flussi lato server (Conversions API, server GTM) e l'uso che la piattaforma email fa dei dati di apertura **non sono osservabili** dall'esterno — vanno chiesti al cliente. Con una sola copia di una newsletter non si può affermare che il pixel sia individuale: serve il confronto tra due caselle.

> Ambito: la skill diagnostica e propone; non sostituisce la validazione formale del titolare/DPO. Indicarlo nel report. Se il report va al cliente, ricorda all'avvocato l'informativa sull'uso di sistemi di intelligenza artificiale nella prestazione (art. 13, c. 2, L. 132/2025).
