# Checklist di conformità e remediation

## Quadro normativo di riferimento
- **Art. 122 Codice Privacy** (D.Lgs. 196/2003) — consenso per archiviazione/accesso a informazioni nel terminale, salvo cookie tecnici. È il perno; recepisce l'**art. 5(3) Direttiva ePrivacy 2002/58/CE**.
- **GDPR (Reg. UE 2016/679)** — art. 5 (principi: minimizzazione, limitazione conservazione), art. 6 (liceità), art. 7 (condizioni del consenso: libero, specifico, informato, revocabile con pari facilità), art. 13 (informativa trasparente e accurata).
- **Provvedimento del Garante 10 giugno 2021, «Linee guida cookie e altri strumenti di tracciamento»** [doc. web 9677876, reg. n. 231] — soft law che detta i requisiti operativi del banner.
- **Trasferimenti USA**: dopo Schrems II, i tool Google (GA4, Ads) implicano trasferimento a Google LLC (USA); base attuale = **EU-US Data Privacy Framework** (decisione di adeguatezza 10.7.2023), di cui Google LLC è certificata. Da dichiarare in informativa.
- **Linee guida EDPB 2/2023** (v2.0, 7 ottobre 2024) sull'ambito tecnico dell'art. 5(3) e-Privacy, §3.1 «URL and pixel tracking» (punti 47-51): la distribuzione di pixel e link tracciati (su siti, email, messaggi) è un'archiviazione nel terminale e la raccolta dell'identificativo un accesso — la norma si applica anche senza cookie.
- **Pixel nelle email**: Linee guida del Garante sui tracking pixel nelle comunicazioni di posta elettronica, provv. 17 aprile 2026 n. 284 [doc. web 10241943], G.U. n. 98 del 29.4.2026, adeguamento entro il **29 ottobre 2026** → `newsletter-tracking.md`.
- **CGUE**: C-40/17 *Fashion ID* (29.7.2019), punto 2 del dispositivo: il gestore di un sito che vi inserisce un plug-in social che trasmette al fornitore i dati del visitatore può essere considerato responsabile del trattamento, limitatamente alla raccolta e alla comunicazione mediante trasmissione (lo schema si applica per analogia ai pixel di marketing); C-252/21 *Meta Platforms c. Bundeskartellamt* (Grande Sezione, 4.7.2023), punto 2 del dispositivo: i dati raccolti con cookie o tecnologie simili dalla consultazione di siti relativi a categorie particolari sono trattamento ex art. 9 se rivelano tali informazioni; C-21/23 *ND c. DR* (Grande Sezione, 4.10.2024), punto 2 del dispositivo: le informazioni inserite per ordinare online medicinali la cui vendita è riservata alle farmacie sono dati relativi alla salute, anche senza prescrizione.

> **Verifica delle citazioni**: prima di finalizzare, richiama `cite_law()` (plugin legal-it) per gli articoli citati come norme di legge (es. `art. 13 GDPR`, `art. 5 GDPR`, `art. 26 GDPR`, `art. 9 GDPR`, `art. 122 D.Lgs. 196/2003`, `art. 130 D.Lgs. 196/2003`). La Direttiva ePrivacy, le Linee guida EDPB e i provvedimenti del Garante sono **fuori copertura** di `cite_law()`: per i provvedimenti del Garante usa `leggi_provvedimento_garante(<doc. web>)`, per le sentenze CGUE `cerca_giurisprudenza_cgue` / `leggi_sentenza_cgue`.

## Checklist del banner (Provv. Garante 231/2021)
Per ciascun punto: Conforme / Non conforme / Da verificare, con evidenza osservata.

1. **Nessun cookie non tecnico prima del consenso** — dalla Fase 1. È il requisito più importante: la sua violazione è la contestazione tipica del Garante.
2. **Parità Accetta/Rifiuta** — il pulsante di rifiuto ha pari evidenza grafica (colore, dimensione, posizione) di quello di accettazione, sul primo livello.
3. **Rifiuto immediato** — «Rifiuta»/«Continua senza accettare» raggiungibile al primo livello, senza obbligare a entrare nelle preferenze.
4. **Chiusura (X) ≠ consenso** — chiudere il banner con la X equivale al rifiuto/mantenimento delle sole tecniche, non ad accettare.
5. **No scroll-acceptance, no cookie wall** — lo scroll non vale come consenso; l'accesso al sito non è subordinato all'accettazione (salvo alternative legittime, es. pay-or-consent, che vanno valutate a parte).
6. **Granularità** — categorie selezionabili separatamente (statistica, marketing, preferenze…).
7. **Consenso specifico e informato** — link a cookie policy e privacy policy dal banner; finalità chiare.
8. **Revocabilità** — modo semplice e sempre disponibile per modificare/revocare (widget/riapertura banner), con pari facilità della concessione (art. 7 GDPR).
9. **Lingua** — banner e informativa nella lingua dell'utente/della versione del sito.
10. **Durata della scelta** — la ri-riproposizione del banner rispetta i tempi delle linee guida (di norma non prima di 6 mesi, salvo cambi di condizioni).

## Checklist dell'informativa cookie (art. 13 GDPR)
- **Accuratezza**: l'inventario dichiarato corrisponde ai cookie/tracker realmente installati? (Confronto Fase 3 vs 3-ter.) Voci spurie (CMP diverse, plugin non usati, cookie legacy) = difetto.
- Titolare e, se presente, DPO; finalità e **base giuridica** per ciascuna categoria.
- **Terze parti** nominate, con link alle loro policy; **durate** di conservazione; diritti dell'interessato e reclamo al Garante.
- **Trasferimenti extra-UE** (Google/Meta/LinkedIn = USA) con la base (DPF/SCC).

## Pixel e altri strumenti di tracciamento sul sito
Per ciascun pixel (sonda §5, `inspect_container.py`, `inspect_pixel_config.py`):

1. **Nessuna chiamata prima del consenso** — il pixel è uno strumento di tracciamento anche senza cookie (art. 122; EDPB 2/2023). Una chiamata che trasmette eventi (`hits`) pre-consenso è la violazione tipica. Il solo caricamento della libreria (`scripts`, es. `fbevents.js`) comunica comunque IP e dati del browser al fornitore: zona grigia, come `gtm.js`.
2. **Ping senza cookie (Consent Mode «avanzata»)** — chiamate Google con `gcs=G100` partite senza consenso: Google riceve comunque l'evento, senza cookie. Per la lettura dell'EDPB l'invio di informazioni dal terminale su istruzione del sito rientra nell'art. 5(3): la scelta prudente è la modalità «base» (tag bloccati finché manca il consenso).
3. **Advanced Matching / enhanced conversions** — email, telefono, nome inviati con hash (`ud[em]`, `em`, Advanced Matching automatico di Meta): l'hash è una pseudonimizzazione (cons. 26 GDPR), non un'anonimizzazione — serve proprio ad abbinare la persona a un profilo della piattaforma. Va dichiarato in informativa, coperto dal consenso e minimizzato (art. 5, par. 1, lett. c): disattivare i campi non necessari (data di nascita, genere, indirizzo).
4. **Contitolarità** — chi integra un pixel che trasmette alla piattaforma i dati del visitatore può esserne contitolare per la raccolta e la trasmissione (per analogia con C-40/17 *Fashion ID*, relativa a un plug-in social): serve l'accordo ex art. 26 GDPR (molte piattaforme lo prevedono nei termini per le aziende: verificarne l'accettazione) e l'informativa deve menzionarlo; il consenso per quella fase va raccolto dal gestore del sito.
5. **Pagine che rivelano dati particolari** — pixel di marketing su pagine di salute, farmacie, orientamento sessuale, religione, opinioni politiche, sindacati: URL, titolo della pagina, eventi e parametri inviati possono rivelare quelle informazioni (C-252/21, punto 2 del dispositivo; per gli ordini online di medicinali riservati alle farmacie C-21/23). Raccomandare l'esclusione dei pixel da quelle pagine.
6. **Dati in chiaro negli URL** — email o altri dati personali di un visitatore nella query string della pagina, inviati ai pixel (parametri `dl`, `rl`, `url`): violazione di minimizzazione e sicurezza (artt. 5 e 32 GDPR), da trattare con urgenza (prima verifica che non sia, ad esempio, l'indirizzo di contatto del sito presente nella pagina). Anche i parametri che Meta filtra come indesiderati (`inspect_pixel_config.py`) sono un indizio di invii passati.
7. **Tagging lato server** (server GTM, Stape, Conversions API) — i flussi server-to-server non si vedono dal browser ma il GDPR si applica: chiedere al titolare se gli invii lato server rispettano le scelte di consenso (es. stato del consenso inoltrato e applicato). Stato: «Da verificare».
8. **Piattaforme email sul sito** (Klaviyo, HubSpot, Mailchimp, ActiveCampaign…) — riconoscono chi arriva dai link della newsletter (`_kx`, `mc_eid`, `_hsenc`, `vgo_ee`) e ne seguono la navigazione: è profilazione che collega email e sito, da gestire come gli altri strumenti di marketing (consenso prima del caricamento) e da descrivere in entrambe le informative.
9. **Trasferimenti extra-UE** — per ogni piattaforma: sede del fornitore, base del trasferimento (decisione di adeguatezza/DPF, verificabile su dataprivacyframework.gov, oppure clausole contrattuali tipo con valutazione d'impatto); Yandex Metrica = Russia.
10. **Informativa** — i pixel vanno nella cookie policy («cookie e altri strumenti di tracciamento»): fornitore, finalità, dati inviati (anche con hash), durata dei cookie collegati, contitolarità, trasferimenti.

## Newsletter
Pixel nelle email, link tracciati, revoca granulare e informativa nel modulo di iscrizione: vedi `newsletter-tracking.md` (Linee guida del Garante del 17 aprile 2026, scadenza 29 ottobre 2026).

## Punti di attenzione ricorrenti (con inquadramento)
- **GTM caricato pre-consenso** — anche solo `gtm.js` comunica l'IP a Google prima del consenso: zona grigia. Difendibile se GTM non setta cookie e i tag sono gattati da Consent Mode, ma la lettura rigorosa lo considera già un trattamento. Molte CMP permettono di bloccarlo finché manca il consenso «statistico»: raccomandare la valutazione.
- **GA4 come «marketing» o «statistica»** — con Google Signals attivo sconfina nel marketing; coerenza tra categoria dichiarata, comportamento e consenso raccolto.
- **Durata `_ga` 2 anni** — standard Google; valutare in ottica di minimizzazione (art. 5 GDPR), accettabile ma segnalabile.
- **reCAPTCHA «necessario»** — comporta trattamento Google; classificazione da motivare.

## Remediation (quando richiesta)

### 1. Bozza di cookie policy corretta
Genera una base con `genera_informativa_cookie` (plugin legal-it), poi **sostituisci l'inventario** con i cookie realmente rilevati (tabella della Fase 4), rimuovendo le voci spurie e allineando durate/terze parti/categorie al comportamento osservato. L'informativa deve riflettere lo stack reale (CMP, tema, analytics), non un template generico.

### 2. Checklist di adeguamento (prioritizzata)
Ordina gli interventi per gravità:
- **Alta**: cookie non tecnici o pixel che trasmettono eventi prima del consenso; email o dati personali in chiaro negli URL inviati ai pixel; pixel di marketing su pagine che rivelano dati particolari; assenza di parità Accetta/Rifiuta; informativa materialmente errata; nelle newsletter: pixel individuale senza consenso né informativa, assenza di revoca granulare entro il 29.10.2026.
- **Media**: Advanced Matching non dichiarato o non minimizzato; accordo di contitolarità assente; ping senza cookie della Consent Mode avanzata; tagging lato server senza garanzie sul consenso; GTM o librerie dei pixel caricati pre-consenso; policy con voci spurie; lingua del banner; classificazione GA4/Signals da chiarire; trasferimenti extra-UE da dichiarare; indirizzo email negli URL delle newsletter.
- **Bassa**: durate lunghe da rivalutare; rifinitura testi.
Per ogni voce: cosa cambiare, dove (CMP/GTM/informativa), e il riferimento normativo.

> Ambito: la skill diagnostica e propone; non sostituisce la validazione formale del titolare/DPO. Indicarlo nel report.
