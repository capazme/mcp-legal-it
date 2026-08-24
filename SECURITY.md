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
grep -rnE "https?://" --include="*.py" src/ | grep -vE "normattiva|gazzettaufficiale|italgiure|giustizia-amministrativa|cortecostituzionale|def\.finanze|garanteprivacy|gpdp|consob|europa\.eu|brocardi|w3\.org|oasis-open|esempio\.it"
```

Se non stampa nulla, nel codice non esiste alcun host oltre a quelli dichiarati.

## Dove vanno le tue interrogazioni

L'elenco autoritativo è codice, non prosa: [`src/lib/_egress.py`](src/lib/_egress.py).
`tests/unit/test_egress_allowlist.py` fa fallire la CI se in `src/` compare un
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
| `def.finanze.it` | CeRDEF — Ministero dell'economia e delle finanze |
| `www.garanteprivacy.it` | Garante per la protezione dei dati personali |
| `servizi.gpdp.it` | Garante privacy — servizi |
| `www.consob.it` | CONSOB |
| `eur-lex.europa.eu` | EUR-Lex — Ufficio delle pubblicazioni UE |
| `publications.europa.eu` | CELLAR / SPARQL — Ufficio delle pubblicazioni UE |
| `ec.europa.eu` | VIES — Commissione europea (validazione partite IVA) |
| `www.brocardi.it` | **Brocardi.it — fonte privata** (vedi sotto) |

**Brocardi è l'unica fonte non istituzionale**, ed è una scelta deliberata da
conoscere. Fornisce annotazioni dottrinali e massime; **non fornisce mai il
testo di una norma**, che arriva sempre da Normattiva o da EUR-Lex. Se questa
dipendenza non ti va bene, i tool che la usano sono isolati in
`src/tools/legal_citations.py` (`cerca_brocardi`, `fetch_law_annotations`) e nel
profilo che li carica.

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

Il controllo è **statico**: legge gli URL scritti nel codice. Intercetta
l'aggiunta di un nuovo host, che è la deriva realistica. Non intercetterebbe un
URL assemblato a runtime da frammenti. Nessuno qui sostiene il contrario.

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
- **`.claude/settings.json`** registra un solo hook, `plugin/hooks/citation-gate.py`:
  uno script deterministico di ~100 righe che rilegge il transcript e avvisa se
  una norma è stata citata senza passare da `cite_law()`. Non fa rete, non
  scrive file. Leggilo prima di approvarlo — è breve apposta.
- **`plugin/.mcp.json`** usa solo `${CLAUDE_PLUGIN_ROOT}`, nessun percorso assoluto.
- Le 23 skill e i 6 agenti sono file markdown di istruzioni. Non eseguono nulla
  da soli.

## Dipendere da un solo manutentore

Il progetto ha un autore. È un rischio reale e la risposta corretta non è
fidarsi di più: è rendere il fork banale.

La licenza è **Apache-2.0**: puoi copiare, modificare e ridistribuire, anche
per uso commerciale, tenendo la nota di copyright. Il percorso consigliato per
chi lavora su pratiche vere:

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
`src/data/` dichiara un blocco `_vintage` con fonte e periodo di copertura, i
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
| [`ci.yml`](.github/workflows/ci.yml) | test su Python 3.10 e 3.12; coerenza delle dipendenze fra i quattro percorsi d'installazione |
| [`security-audit.yml`](.github/workflows/security-audit.yml) | `pip-audit` sulle dipendenze risolte, settimanale |
| [`data-freshness.yml`](.github/workflows/data-freshness.yml) | rinfresco mensile dei dati da fonti ufficiali e segnalazione delle tabelle scadute |
