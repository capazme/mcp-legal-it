# Newsletter — mappatura del tracciamento nelle email (percorso ripetibile)

## Quadro
- **Garante, «Linee Guida in materia di utilizzo di tracking pixel nelle comunicazioni di posta elettronica»**, provv. 17 aprile 2026 n. 284 [doc. web 10241943], G.U. Serie Generale n. 98 del 29 aprile 2026. Termine per l'adeguamento: 6 mesi dalla pubblicazione, cioè **29 ottobre 2026** (data indicata dal Garante nella notizia del 5 ottobre 2026, doc. web 10303585, che annuncia anche la verifica dell'applicazione delle Linee guida tra le attività ispettive del secondo semestre 2026). I § citati sotto sono quelli delle Linee guida.
- **Art. 122 Codice privacy**: il pixel nella email realizza sia l'archiviazione di informazioni nel terminale (l'inserimento del pixel) sia l'accesso a informazioni già archiviate (la rilevazione dell'apertura) — §1, in linea con le **Linee guida EDPB 2/2023** del 7 ottobre 2024 sull'ambito tecnico dell'art. 5(3) della direttiva e-Privacy (§3.1, che cita espressamente il pixel inserito in una email per sapere quando viene letta).
- **Art. 130 Codice**: disciplina l'invio di comunicazioni promozionali (consenso; c. 4 per i clienti, «soft spam»). Il consenso a ricevere le email e quello al tracciamento sono distinti, ma possono essere raccolti con una richiesta **unica** se formulata in modo neutro (§6).

## Cosa serve (minimo coinvolgimento del cliente)
1. **Due caselle di prova dello studio** (mai indirizzi personali o del cliente).
2. **Iscrizione dal sito del cliente** con entrambe le caselle. Arrivano subito la mail di conferma (double opt-in) o di benvenuto, dallo stesso servizio di invio e con lo stesso tracciamento; poi la prima newsletter.
3. **Salvare i messaggi in formato `.eml`** (contiene intestazioni e HTML originali):
   - Gmail: apri il messaggio → ⋮ → «Scarica il messaggio»;
   - Apple Mail: Archivio → Salva come… → formato «Sorgente originale»;
   - Thunderbird: File → Salva come → File;
   - Outlook web / nuovo Outlook: ⋯ → Scarica / Salva con nome (.eml). Il `.msg` di Outlook classico non va bene: inoltra il messaggio **come allegato** a una casella Gmail e scarica da lì il messaggio ricevuto — lo strumento riconosce l'inoltro e analizza l'originale allegato (intestazioni e corpo).

   Non inoltrare il messaggio nel corpo di una nuova email: il client riscrive l'HTML e il tracciamento si perde o si altera.
4. **Analisi**:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/cookie-audit/scripts/inspect_newsletter.py" \
       --compare benvenuto_prova1.eml benvenuto_prova2.eml \
       --recipient prova1@studio-esempio.example --recipient prova2@studio-esempio.example
   ```
   Ripeti per la newsletter vera e propria. Con un solo file l'analisi funziona comunque, ma non può dire se il pixel è individuale o uguale per tutti.
5. **Sul sito**: sonda §7 sul modulo di iscrizione (informativa e consenso) e sonda §5 per le piattaforme email installate sul sito (Klaviyo, HubSpot, Mailchimp, ActiveCampaign, Brevo, Omnisend…), che riconoscono chi arriva dai link della newsletter.

## Cosa verificare

| Verifica | Come la rileva lo strumento | Linee guida 2026 |
|----------|-----------------------------|------------------|
| C'è un pixel o un'immagine con identificativo | immagini 1×1 o nascoste, percorsi tipici di apertura, immagini remote con parametri opachi | §1: si applica l'art. 122 |
| Pixel **individuale** o **uguale per tutti** | `--compare` su due copie | §5: la deroga del conteggio statistico globale richiede pixel uguali per tutti i destinatari della campagna e dati tecnici (IP, client) anonimizzati |
| L'indirizzo del destinatario nell'URL (in chiaro, base64, esadecimale, MD5/SHA-1/SHA-256) | `--recipient` | §6: identificativo inintelligibile e non sequenziale, associato all'indirizzo in un livello separato della piattaforma; l'indirizzo non deve stare nella richiesta del pixel |
| Link o icona nel footer per rifiutare **solo** il tracciamento | testo e link del piè di pagina | §6: revoca anche granulare, per i nuovi trattamenti e per le liste già in uso |
| Informativa sul tracciamento | testo del messaggio + sonda §7 sul modulo | §4: informativa sempre dovuta, anche su più livelli (sintetica nel modulo + estesa, eventualmente nella cookie policy); per le liste già in uso con il primo invio utile |
| Consenso | sonda §7 (caselle, testo, preselezioni) + domande al cliente | §6: raccolto preferibilmente al momento dell'acquisizione dell'indirizzo; può essere unico con quello al marketing se neutro; rifiutare il tracciamento non deve limitare il servizio; scelte registrate (art. 7, par. 1, GDPR) |
| Link tracciati e ID portati sul sito (`mc_eid`, `_kx`, `_hsenc`, `vgo_ee`…) | redirect e parametri dei link | tracciamento via URL (EDPB 2/2023): da dichiarare; sul sito vale la disciplina dei cookie e degli altri strumenti di tracciamento |
| Terze parti nel messaggio (analytics, reti pubblicitarie, contenuti dinamici) | domini contattati | §3: ruoli da definire (anche contitolarità, art. 26 GDPR), informativa e consenso |
| Piattaforma di invio | intestazioni (Return-Path, DKIM, Received, List-*) | §3: di norma responsabile del trattamento (art. 28 GDPR): verificare il contratto |

## Tipo di messaggio e regime (indicativo: la qualificazione spetta al legale)

| Tipo (§3) | Regime di partenza (§5-§6) |
|-----------|----------------------------|
| Newsletter, DEM | consenso (anche unico con il marketing), salvo pixel per il solo conteggio statistico globale e anonimo |
| Transazionali e automatici (benvenuto, conferme d'ordine, credenziali temporanee) | consenso, salvo che il pixel serva alla **sicurezza dell'autenticazione** (conferma di attivazione dell'account, cambio password, richieste di esercizio dei diritti): deroga |
| Di servizio che il titolare ha l'**obbligo giuridico** di inviare (esempi del §5: istituti del diritto bancario, attività istituzionali di soggetti pubblici, avvisi su phishing o frodi, modifiche contrattuali o logistico-organizzative, termini di servizio, informative privacy, incidenti di sicurezza, campagne istituzionali, promemoria di scadenze contrattuali o contributive) | deroga solo se c'è l'obbligo di invio e rileva l'effettiva presa di conoscenza del destinatario |

Esempi di finalità che **richiedono il consenso** (§6): misurare le aperture del singolo per migliorare le campagne (oggetto, frequenza); interrompere gli invii a chi non apre; dedurre gusti e preferenze per profilare.

## Domande al cliente (solo ciò che non si vede da fuori)
1. Quale piattaforma usate per newsletter/DEM e per le email automatiche? C'è il contratto ex art. 28 GDPR?
2. Il tracciamento delle aperture e dei clic è attivo? Con integrazioni (Google Analytics, e-commerce, CRM)?
3. Come usate i dati di apertura e clic? Solo statistiche complessive / per singolo destinatario / segmentazione / stop degli invii a chi non apre / profilazione.
4. Come raccogliete gli indirizzi? Modulo con consenso / clienti (art. 130, c. 4) / liste acquistate o noleggiate.
5. Le liste sono in uso da prima delle Linee guida? (regime transitorio §6: informativa al primo invio utile + revoca granulare).
6. Conservate la prova del consenso (data, testo mostrato, fonte)?
7. La piattaforma consente di inviare senza pixel ai contatti che rifiutano il solo tracciamento?
8. Per quanto tempo conservate i dati di apertura e clic?

## Cosa produce
Per ogni flusso email (benvenuto, newsletter, automatici): piattaforma, tipo di messaggio, pixel individuale o aggregato, link tracciati, ID portati sul sito, terze parti, indirizzo negli URL, revoca granulare, informativa. Sono righe della **mappa unica** degli strumenti di tracciamento, insieme a cookie e pixel del sito, con i gap ordinati per priorità rispetto al 29 ottobre 2026. Da questa mappa si costruiscono i modelli: informativa breve nel modulo, testo del consenso, sezione estesa sui pixel, footer con revoca granulare, cookie policy.

**Fuori portata dello strumento**: ciò che accade sui server della piattaforma (conservazione, anonimizzazione dell'IP, uso dei dati di apertura). Va chiesto al cliente e verificato nel contratto con la piattaforma.
