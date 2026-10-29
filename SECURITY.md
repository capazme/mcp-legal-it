# Sicurezza e verificabilità

Questo progetto produce numeri e testi che finiscono in atti. Chi lo valuta
prima di usarlo su pratiche vere si pone sempre le stesse domande, e merita di
poterle risolvere in minuti anziché in giorni di lettura del codice.

Questo documento risponde a quelle domande. Dove possibile la risposta non è
una promessa scritta qui, ma un test che fa fallire la build se smette di
essere vera: le promesse invecchiano in silenzio, i test no.

## Telemetria

**Nessuna.** Il server non raccoglie né trasmette statistiche d'uso, non ha
endpoint di analytics, non registra le query su alcun sistema remoto. Le uniche
connessioni in uscita sono le interrogazioni alle fonti elencate sotto,
necessarie per rispondere alla domanda che hai posto.

Verificabile in un comando:

```bash
grep -rnE "https?://" --include="*.py" plugin/server/mcp_legal_it/ | grep -vE "normattiva|gazzettaufficiale|italgiure|giustizia-amministrativa|cortecostituzionale|def\.finanze|corteconti|garanteprivacy|gpdp|consob|anticorruzione|senato\.it|camera\.it|europa\.eu|brocardi|tmdn\.org|w3\.org|oasis-open|esempio\.it|mozilla\.org"
```

Se non stampa nulla, nel codice non esiste alcun host oltre a quelli dichiarati.

## Dove vanno le tue interrogazioni

L'elenco autoritativo è codice, non prosa: [`mcp_legal_it/lib/_egress.py`](plugin/server/mcp_legal_it/lib/_egress.py).
`tests/unit/test_egress_allowlist.py` fa fallire la CI se in `plugin/server/mcp_legal_it/` compare un
URL verso un host non dichiarato, **e** se un host dichiarato non compare in
questo documento. Le due liste non possono divergere.

### Host contattati dal server

| Host | Titolare |
|------|----------|
| `www.normattiva.it` | Normattiva — Istituto Poligrafico e Zecca dello Stato |
| `www.gazzettaufficiale.it` | Gazzetta Ufficiale — IPZS |
| `www.italgiure.giustizia.it` | Corte di cassazione — Ministero della giustizia |
| `www.giustizia-amministrativa.it` | Giustizia amministrativa (TAR e Consiglio di Stato) |
| `mdp.giustizia-amministrativa.it` | Giustizia amministrativa — testi integrali |
| `dati.cortecostituzionale.it` | Corte costituzionale — open data |
| `dati.senato.it` | Senato della Repubblica — open data (SPARQL) |
| `dati.camera.it` | Camera dei deputati — open data (SPARQL) |
| `def.finanze.it` | CeRDEF — Ministero dell'economia e delle finanze |
| `banchedati.corteconti.it` | Corte dei conti — banca dati (configurazione pubblica e scheda delle deliberazioni) |
| `corteconti-iit.almawave.cloud` | Corte dei conti — servizio di ricerca della banca dati, gestito dal fornitore Almawave |
| `www.garanteprivacy.it` | Garante per la protezione dei dati personali |
| `servizi.gpdp.it` | Garante privacy — servizi |
| `www.consob.it` | CONSOB |
| `www.anticorruzione.it` | ANAC — Autorità Nazionale Anticorruzione |
| `eur-lex.europa.eu` | EUR-Lex — Ufficio delle pubblicazioni UE |
| `publications.europa.eu` | CELLAR / SPARQL — Ufficio delle pubblicazioni UE |
| `ec.europa.eu` | VIES — Commissione europea (validazione partite IVA) |
| `www.tmdn.org` | TMview — EUIPO / EU Intellectual Property Network (banca dati marchi) |
| `www.brocardi.it` | **Brocardi.it — fonte privata** (vedi sotto) |

**Brocardi è l'unica fonte non istituzionale**, ed è una scelta deliberata da
conoscere. Fornisce annotazioni dottrinali e massime; **non fornisce mai il
testo di una norma**, che arriva sempre da Normattiva o da EUR-Lex. Se questa
dipendenza non ti va bene, spegnila:

```bash
LEGAL_BROCARDI=off mcp-legal-it        # oppure crea_server(brocardi=False) in codice
```

Con Brocardi spento:

- **nessuna richiesta parte verso `www.brocardi.it`**: i due scraper che costruiscono
  URL Brocardi (`mcp_legal_it/lib/brocardi/client.py`, `mcp_legal_it/lib/visualex/scraper.py`)
  passano da `mcp_legal_it/lib/_brocardi_switch.py` prima di qualunque I/O e si fermano
  (è questo il blocco: `_egress.is_allowed()`, che a runtime riflette lo stato
  dell'interruttore, è l'elenco consultabile, non un secondo strato di difesa);
- `cerca_brocardi` e `fetch_law_annotations` (tag `solo_brocardi`) non sono esposti;
- `cite_law(include_annotations=True)`, `giurisprudenza_articolo` e `mappa_orientamento`
  (tag `brocardi`) rispondono senza Brocardi e lo dichiarano nella risposta;
- uno *spento* nell'ambiente non può essere riacceso dal codice.

Questo controllo è **a runtime**, non solo statico:
`tests/unit/test_brocardi_switch.py` sostituisce la rete con un finto client che
registra ogni richiesta, chiama ogni tool con tag `brocardi` e fallisce se anche una
sola richiesta raggiunge un host Brocardi; un secondo test percorre il grafo delle
chiamate dei moduli `tools/` e fallisce se un tool arriva agli scraper Brocardi senza
il tag `brocardi`.

### Corte dei conti: il servizio del fornitore e le credenziali pubbliche del sito

La banca dati della Corte dei conti (`banchedati.corteconti.it`) è un'applicazione web
che interroga un servizio gestito dal fornitore Almawave (`corteconti-iit.almawave.cloud`):
le parole che cerchi con `cerca_deliberazioni_corte_conti` arrivano a quel servizio, come
quando usi il sito dal browser, e il servizio assegna a ogni ricerca un proprio numero di
registro (il sito la conserva nelle sue statistiche).

Il sito consegna a ogni visitatore, nel suo file di configurazione pubblico, una coppia di
credenziali HTTP Basic che il browser invia con ogni ricerca. Il server fa lo stesso: legge
quel file quando serve e usa le credenziali che contiene. Le credenziali:

- non sono scritte nel codice, nei test o nella documentazione;
- restano solo in memoria, per la vita del processo, e si rileggono dal sito se il servizio
  smette di accettarle;
- non finiscono mai in un log, in una cache su disco, in un messaggio d'errore o nelle
  registrazioni usate per i test di non regressione (`scripts/replay_mcp_outputs.py` le
  sostituisce con `<scrubbed>` prima di salvare; `tests/unit/test_corte_conti.py` lo verifica).

### L'unico host scelto da chi chiama: `verifica_dpa_fornitore`

Un solo tool contatta un host che non è nell'elenco qui sopra:
`verifica_dpa_fornitore(dominio)` (modulo `mcp_legal_it/lib/dpa_probe/`) visita il sito
del fornitore che il chiamante indica, su un elenco fisso di percorsi
convenzionali (`/legal/dpa`, `/privacy/dpa`, `/gdpr`, …), per accertare se
pubblica un DPA ex art. 28 GDPR. È l'eccezione dichiarata alla regola, e ha
i suoi limiti scritti nel codice, con test che li fanno rispettare
(`tests/unit/test_dpa_probe.py::TestDestinazionePubblica`):

- il bersaglio deve essere un **nome di dominio pubblico registrabile**: mai un
  indirizzo IP, una porta, credenziali, `localhost` o un nome locale/riservato
  (`.local`, `.internal`, `.lan`, `.test`, …);
- il nome viene **risolto prima di ogni richiesta** e rifiutato se anche uno
  solo degli indirizzi non è pubblico (loopback, reti private, link-local e
  quindi l'endpoint dei metadata cloud, riservati);
- la stessa verifica vale per **ogni redirect**: un sito pubblico che rimanda a
  un indirizzo interno viene fermato prima che la richiesta parta;
- il verdetto viene messo in cache (`dpa_probe.json`, 90 giorni, disattivabile
  con `LEGAL_CACHE=off`) e ogni risposta dichiara l'host consultato in
  `fonti_consultate`.

Un rifiuto è riportato come `dominio_irraggiungibile` con il motivo, mai come
un errore silenzioso. `test_egress_allowlist.py` continua a valere per tutto il
resto: nel codice non esiste alcun altro URL verso host non dichiarati.

### Host contattati solo dagli script di manutenzione

Girano in CI, mai nel server:

| Host | Uso |
|------|-----|
| `data-api.ecb.europa.eu` | serie BCE MRO per i tassi di mora (`scripts/refresh_data.py`) |
| `www.istat.it` | indici FOI per le rivalutazioni |
| `www.bancaditalia.it` | TEGM — indicato come fonte da consultare, non scaricato |
| `www.mef.gov.it` | decreti tassi legali — indicato come fonte |
| `www.finanze.gov.it` | coefficienti usufrutto — indicato come fonte |
| `www.mimit.gov.it` | DM danno biologico — indicato come fonte |

### Cosa il test garantisce, e cosa no

Il test è **statico**: legge gli URL scritti nel codice. Intercetta
l'aggiunta di un nuovo host, che è la deriva realistica. Non intercetterebbe un
URL assemblato a runtime da frammenti.

Per questo c'è anche un controllo **a runtime**, su ogni richiesta: ogni client
HTTP del server nasce in `mcp_legal_it/core/_http.py` per una fonte precisa, e una
guardia controlla ogni richiesta prima che parta, **redirect compresi**: schema
http(s), nessuna credenziale nell'URL, e un host previsto per quella fonte
(`HOST_PER_FONTE`, sottoinsieme dell'elenco qui sopra; Brocardi rifiutato quando è
spento). Una richiesta fuori regola non raggiunge la rete (`HostNonConsentito`). La
guardia resta anche quando un programma che usa la libreria inietta il proprio
client HTTP (`client_factory`): viene riapplicata al client che riceve.
`verifica_dpa_fornitore` è l'unica fonte senza elenco di host, per i motivi detti
sopra, e passa comunque dal controllo su schema e credenziali.

### Quanto chiediamo alle fonti

Le stesse regole di VisuaLex, per fonte e per processo (condivise da tutti i
thread): al massimo 3 richieste in corso e almeno 0,5 secondi tra due richieste
alla stessa fonte; un `Retry-After` dichiarato da una risposta 429 o 503 ferma
quella fonte per tutte le chiamate, al massimo per 30 secondi (se la fonte chiede
di più, la chiamata che ha ricevuto la risposta è rifiutata subito e le altre
riprovano dopo 30 secondi); i tentativi ripetuti sono al massimo due, con attesa
crescente. I limiti valgono dentro un processo: più processi sulla stessa
macchina contro la stessa fonte moltiplicano il tetto.
Facoltativo, per chi espone il server a più utenti: `LEGAL_CIRCUIT_BREAKER=on`
sospende per 5 minuti una fonte dopo 3 errori consecutivi (errori di rete, 5xx,
429; mai un 404).
La Corte dei conti ha un limite più stretto: una richiesta alla volta, ad almeno 1 secondo
l'una dall'altra, e al più 5 documenti per ricerca (il limite del suo servizio pubblico).

## I tuoi dati

Il server non ha un database e non conserva le tue interrogazioni. Scrive una
sola cosa su disco: una cache degli URL degli articoli di Brocardi, in
`$MCP_CACHE_DIR` (default `~/.cache/mcp-legal-it`), che contiene indirizzi di
pagine pubbliche e nessun contenuto tuo. Cancellarla è sempre sicuro.

I documenti generati (`.docx`, `.pdf`, `.xlsx`) sono scritti dove li chiedi e
non lasciano la tua macchina.

## Configurazioni annidate

Un repository altrui che porta con sé una configurazione da approvare merita
diffidenza, sempre. Ecco cosa contiene questo:

- **`.mcp.json` non è tracciato.** Lo era, con i percorsi assoluti dell'autore:
  inutilizzabile altrove e un file che chiedeva fiducia senza darne motivo.
  Oggi c'è [`.mcp.json.example`](.mcp.json.example), che risolve tutto dal
  checkout e che copi tu.
- **`.claude/settings.json`** registra un solo hook, di tipo `prompt` all'avvio della
  sessione: un promemoria del Legal Grounding Protocol, nessun comando eseguito.
- **`plugin/hooks/hooks.json`** (solo con il plugin installato) registra
  `plugin/hooks/citation-gate.py` su Stop e SubagentStop: uno script deterministico che
  usa la sola libreria standard più i moduli `core/citazioni.py` e `core/riferimenti.py`
  del server (anch'essi solo libreria standard), rilegge il transcript della sessione e
  quelli dei suoi subagenti (mai di altre sessioni: i file fuori dalla cartella
  `subagents/` della sessione, link simbolici compresi, sono ignorati) e avvisa se una
  norma o una decisione è stata citata senza averla letta con un tool. Non fa rete e non
  scrive file; `LEGAL_CITATION_GATE=off` lo spegne (vedi `docs/plugin.md`); `uv run --no-sync` lo avvia senza installare nulla. Leggilo prima di
  approvarlo.
- **`plugin/.mcp.json`** usa solo `${CLAUDE_PLUGIN_ROOT}`, nessun percorso assoluto, e avvia
  il server con `uv run --frozen`: le versioni esatte di `plugin/server/uv.lock`, in un
  ambiente del plugin, senza toccare il progetto dell'utente.
- Le 30 skill, i 9 comandi e i 6 agenti sono file markdown di istruzioni. Non eseguono nulla
  da soli.

## Dipendere da un solo manutentore

Il progetto ha un autore. È un rischio reale e la risposta corretta non è
fidarsi di più: è rendere il fork banale.

La licenza è **MPL-2.0** (fino alla linea 2.x era Apache-2.0, vedi `NOTICE`):
puoi copiare, modificare e ridistribuire, anche per uso commerciale, tenendo le
note di copyright; le modifiche ai file del progetto che distribuisci restano
sotto MPL-2.0 e ne va reso disponibile il sorgente, mentre il codice tuo in file
separati può avere la licenza che preferisci. Il percorso consigliato per chi
lavora su pratiche vere:

1. Forka il repository e tieni il tuo ramo di produzione su una versione che
   hai auditato.
2. Tieni `upstream` come **fonte da cui importare**, non da cui dipendere:
   confronta il diff prima di ogni bump.
3. Esegui dal tuo codice. L'unica dipendenza che resta è verso i siti dello
   Stato — la stessa che hai già consultando Normattiva a mano.

Il `CHANGELOG.md` dichiara ogni modifica per versione, così il diff fra due tag
si legge in pochi minuti.

## Verificare l'affidabilità dei dati

I calcoli poggiano su tabelle scritte a mano, che invecchiano. Ogni tabella in
`mcp_legal_it/data/` dichiara un blocco `_vintage` con fonte e periodo di copertura, i
tool lo stampano accanto al risultato, e `scripts/update-data.py --strict` fa
fallire la CI su una tabella scaduta o priva di dichiarazione. Le tabelle la cui
provenienza non è ancora stata accertata sono marcate `da_verificare` e lo
dicono esplicitamente nell'output: **è un avviso, non un difetto nascosto**.

```bash
python scripts/update-data.py     # stato di freschezza di tutte le tabelle
```

## Segnalare una vulnerabilità

Apri una issue su
[github.com/capazme/mcp-legal-it/issues](https://github.com/capazme/mcp-legal-it/issues).
Per problemi che è meglio non discutere in pubblico, usa
[GitHub Security Advisories](https://github.com/capazme/mcp-legal-it/security/advisories/new),
che apre un canale privato con il manutentore.

## Controlli automatici già attivi

| Workflow | Cosa fa |
|----------|---------|
| [`ci.yml`](.github/workflows/ci.yml) | test su Python 3.11 e 3.12; coerenza delle dipendenze fra i quattro percorsi d'installazione |
| [`security-audit.yml`](.github/workflows/security-audit.yml) | `pip-audit` sulle dipendenze risolte, settimanale |
| [`data-freshness.yml`](.github/workflows/data-freshness.yml) | rinfresco mensile dei dati da fonti ufficiali e segnalazione delle tabelle scadute |
