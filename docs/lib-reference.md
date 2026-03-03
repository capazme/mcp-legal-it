# Library Reference — mcp-legal-it

> Documentazione delle librerie interne (`src/lib/`): API pubbliche, dataclass, dettagli tecnici.

## Indice

- [visualex — Normattiva & EUR-Lex](#visualex--normattiva--eur-lex)
  - [models.py — Norma, NormaVisitata](#modelspy--norma-normavisitata)
  - [map.py — Dizionari e helper](#mappy--dizionari-e-helper)
  - [scraper.py — Fetch articoli e PDF](#scraperpy--fetch-articoli-e-pdf)
- [brocardi — Scraper Brocardi](#brocardi--scraper-brocardiit)
  - [client.py — BrocardiResult, Massima](#clientpy--brocardiresult-massima)
- [italgiure — Client Solr Cassazione](#italgiure--client-solr-cassazione)
  - [client.py — Query e formattazione](#clientpy--query-e-formattazione)
- [gpdp — Garante Privacy](#gpdp--garante-privacy)
  - [client.py — DocResult, ricerca, fetch](#clientpy--docresult-ricerca-fetch)

---

## visualex — Normattiva & EUR-Lex

Libreria per la risoluzione e il fetch di atti normativi italiani (Normattiva) ed europei (EUR-Lex).

### models.py — Norma, NormaVisitata

**File**: `src/lib/visualex/models.py`

#### `Norma`

Dataclass che rappresenta un atto normativo e genera l'URL corretto per Normattiva o EUR-Lex.

```python
@dataclass
class Norma:
    tipo_atto: str        # es. "codice civile", "decreto legislativo"
    data: str = ""        # es. "2003-06-30" o "2003" (anno solo)
    numero_atto: str = "" # es. "196"
```

**Post-init**: imposta `tipo_atto_normalized` tramite `normalize_act_type()`.

| Metodo | Firma | Descrizione |
|--------|-------|-------------|
| `url(article)` | `(article: str = "") -> str` | Genera URL Normattiva o EUR-Lex. Aggiunge `~artNNN` per gli articoli. |
| `_is_eurlex()` | `() -> bool` | True se il tipo di atto è mappato in `EURLEX`. |
| `__str__()` | `() -> str` | Rappresentazione testuale: `"Tipo Data, n. Numero"`. |

**Logica URL**:
1. Se EUR-Lex: usa `EURLEX[norm]`. Se valore è URL diretto (trattati) lo restituisce; altrimenti costruisce `eur-lex.europa.eu/eli/{type}/{year}/{number}/oj/ita`.
2. Se codice noto: cerca `NORMATTIVA_URN_CODICI[norm]` e aggiunge `~artNNN`.
3. Altrimenti: costruisce URN Normattiva `tipo_atto:YYYY-MM-DD;numero`.

**Gestione articoli estesi** (`_append_article`): converte `"13-bis"` in `~art13bis`, `"2 bis"` in `~art2bis`.

#### `NormaVisitata`

Dataclass che combina un `Norma` con un numero articolo specifico.

```python
@dataclass
class NormaVisitata:
    norma: Norma
    numero_articolo: str = ""
    _urn: str = field(default="", repr=False)
```

| Metodo | Firma | Descrizione |
|--------|-------|-------------|
| `url()` | `() -> str` | Delega a `norma.url(article=numero_articolo)`. |
| `__str__()` | `() -> str` | es. `"Codice Civile art. 2043"`. |

---

### map.py — Dizionari e helper

**File**: `src/lib/visualex/map.py`

#### Dizionari principali

| Dizionario | Tipo | Dimensione | Scopo |
|------------|------|-----------|-------|
| `NORMATTIVA_URN_CODICI` | `dict[str, str]` | 33 voci | Nome codice → URN parziale Normattiva |
| `ATTI_NOTI` | `dict[str, dict]` | ~40 voci | Alias comuni (GDPR, DORA, c.c., ecc.) → parametri scraper |
| `NORMATTIVA_SEARCH` | `dict[str, str]` | ~80 voci | Abbreviazioni → nome esteso (D.Lgs., DPR, ecc.) |
| `EURLEX` | `dict[str, str]` | 5 voci | Tipo atto UE → prefisso CELEX (`reg`, `dir`) o URL diretto |
| `BROCARDI_CODICI` | `dict[str, str]` | ~80 voci | Nome codice completo → URL base Brocardi |
| `FONTI_PRINCIPALI` | `list[str]` | ~40 voci | Tipi di atto per prompts/resources |

**Esempi `ATTI_NOTI`**:
```python
"gdpr":    {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"}
"c.c.":    {"tipo_atto": "codice civile",  "data": "", "numero_atto": ""}
"tuir":    {"tipo_atto": "decreto del presidente della repubblica", "data": "1986", "numero_atto": "917"}
```

#### Funzioni pubbliche

```python
def normalize_act_type(input_type: str) -> str
```
Normalizza abbreviazioni (`"d.lgs."` → `"decreto legislativo"`). Gestisce i trattati UE (TUE, TFUE, CDFUE) senza trasformazione.

```python
def resolve_atto(name: str) -> dict | None
```
Risolve un nome comune ai parametri scraper. Catena di risoluzione:
1. Lookup diretto in `ATTI_NOTI`
2. `extract_codice_details()` — estrae data e numero dall'URN in `NORMATTIVA_URN_CODICI`
3. Normalizzazione via `NORMATTIVA_SEARCH` + tentativo 1 e 2 sul risultato

Restituisce `{"tipo_atto": str, "data": str, "numero_atto": str}` oppure `None`.

```python
def find_brocardi_url(tipo_atto: str, numero_atto: str = "") -> str | None
```
Trova l'URL base di Brocardi per un tipo di atto. Strategia:
1. Match diretto (lowercase) su `_BROCARDI_LOOKUP`
2. Lookup del nome normalizzato
3. Ricerca con numero atto nella chiave
4. Substring fuzzy match

```python
def extract_codice_details(codice_name: str) -> dict | None
```
Estrae `tipo_atto_reale`, `data`, `numero_atto` dall'URN in `NORMATTIVA_URN_CODICI`. Uso interno.

---

### scraper.py — Fetch articoli e PDF

**File**: `src/lib/visualex/scraper.py`

**Dipendenze**: `httpx` (async), `BeautifulSoup4` + `lxml`, `NormaVisitata`, `find_brocardi_url`.

**Cache in-memory**: `_brocardi_url_cache: dict[str, str]` — mappa `"base_url#article_num"` → URL articolo Brocardi. Si azzera a ogni restart.

**Timeout**: 30s (read), 10s (connect). EUR-Lex: 60s.

#### Funzioni pubbliche

```python
async def fetch_article(nv: NormaVisitata) -> dict
```
Fetch testo articolo da Normattiva o EUR-Lex.

Ritorna: `{"text": str, "url": str, "source": "normattiva"|"eurlex", "error"?: str}`

Per Normattiva: 4 scenari di parsing HTML (`art-comma-div-akn`, `art-just-text-akn`, `attachment-just-text`, fallback).
Per EUR-Lex: 4 strategie di estrazione articolo (`id="art_N"`, `p.oj-ti-art`, `eli-subdivision`, regex).

---

```python
async def fetch_annotations(nv: NormaVisitata) -> dict
```
Fetch annotazioni Brocardi (ratio, spiegazione, massime).

Ritorna: `{"annotations": dict, "url": str, "source": "brocardi", "error"?: str}`

Navigazione in 2 passi: indice codice → pagina articolo. Cache in `_brocardi_url_cache`.

---

```python
async def download_eurlex_pdf(norma: Norma) -> bytes
```
Download PDF ufficiale EUR-Lex via CELEX ID.

- Costruisce CELEX: `3{year}{R|L}{number_zfill4}` (es. `32016R0679` per GDPR)
- URL: `eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:{celex}`
- Verifica magic bytes `%PDF-` prima di restituire
- Raise `ValueError` per trattati (TUE, TFUE, CDFUE) — non hanno PDF CELEX

---

```python
async def fetch_normattiva_full_text(norma: Norma) -> dict
```
Fetch testo completo di un atto Normattiva (tutti gli articoli).

Normattiva renderizza solo Art. 1 nel DOM statico; gli altri articoli sono caricati on-demand via AJAX (`/atto/caricaArticolo`). Questa funzione:
1. Scarica la pagina principale
2. Estrae gli URL AJAX dal sidebar tree (`onclick="showArticle(...)"`)
3. Deduplica per `(idGruppo, idArticolo, flagTipoArticolo)` — conserva solo la versione vigente
4. Fetcha ogni articolo in sequenza

Ritorna: `{"text": str, "title": str, "url": str, "article_count": int}` o `{"error": str}`

Il testo degli articoli è separato da `"\n\n---\n\n"`.

---

```python
async def fetch_act_index(norma: Norma) -> dict
```
Fetch indice strutturato (rubriche) di un atto Normattiva senza scaricare il testo.

Usa l'endpoint `/atto/vediRubriche` con `codiceRedazionale` + `dataPubblicazioneGazzetta` estratti dalla pagina principale.

Ritorna: `{"index": list[str], "codice_redazionale": str, "data_gu": str, "url": str}` o `{"error": str}`

**Note tecniche**:
- WAF detection: se EUR-Lex risponde 202 o body < 5000 con "WAF", la funzione fallisce silenziosamente
- User-Agent: Chrome 120 su Windows per eludere blocchi bot su Normattiva

---

## brocardi — Scraper Brocardi.it

Scraper standalone per `brocardi.it`. Estrae struttura completa per ogni articolo: testo, ratio, dottrina, massime, relazioni storiche, glossario, note, cross-reference.

### client.py — BrocardiResult, Massima

**File**: `src/lib/brocardi/client.py`

**Cache persistente**: `~/.cache/mcp-legal-it/brocardi_urls.json` (sovrascrivibile via `$MCP_CACHE_DIR`). Mappa `"base_url#article_num"` → URL articolo. Persiste tra sessioni.

**Timeout**: 30s (read), 10s (connect).

#### Dataclass `Massima`

```python
@dataclass
class Massima:
    autorita: str | None = None   # es. "Cass. civ.", "Trib. Milano"
    numero:   str | None = None   # numero decisione
    anno:     str | None = None   # anno
    testo:    str = ""
```

| Property | Tipo | Descrizione |
|----------|------|-------------|
| `estremi` | `str | None` | Formatta `"Cass. civ. n. 12345/2024"` o None se dati incompleti |
| `is_cassazione` | `bool` | True se `autorita` inizia con "Cass" |

Autorità riconosciute: Corte Costituzionale, Cassazione (civ/pen/lav/sez.un), Consiglio di Stato, TAR (tutte le sedi), Corte dei Conti, Corte d'Appello, Tribunale, CGUE, CEDU.

#### Dataclass `BrocardiResult`

```python
@dataclass
class BrocardiResult:
    url: str = ""
    position: str = ""              # breadcrumb: "Libro IV > Titolo IX > Art. 2043"
    dispositivo: str = ""           # testo dell'articolo
    brocardi: list[str] = ...       # adagi e proverbi giuridici
    ratio: str = ""                 # ratio legis
    spiegazione: str = ""           # spiegazione dottrinale
    massime: list[Massima] = ...    # massime giurisprudenziali strutturate
    relazioni: list[Relazione] = ...# relazioni storiche (Guardasigilli, Ruini)
    glossario: list[GlossaryEntry]  # termini giuridici con link dizionario
    footnotes: list[dict] = ...     # note a piè di pagina
    cross_references: list[dict]    # link ad altri articoli nel testo
    related_articles: dict = ...    # {"previous": {...}, "next": {...}}
    error: str = ""
```

| Property/Metodo | Descrizione |
|-----------------|-------------|
| `cassazione_references` | `list[Massima]` — filtra solo massime Cassazione (per `leggi_sentenza`) |
| `to_markdown()` | Formatta l'intero risultato come testo markdown |

#### Funzioni pubbliche

```python
async def fetch_brocardi(
    tipo_atto: str,
    articolo: str,
    numero_atto: str = "",
) -> BrocardiResult
```
Entry point principale. Cerca la pagina articolo su Brocardi ed estrae tutte le sezioni.

Risolve l'URL base con `find_brocardi_url()`. Naviga la struttura a due livelli (indice codice → pagina articolo). Usa la cache persistente JSON.

---

```python
async def find_article_url(
    client: httpx.AsyncClient,
    base_url: str,
    article_num: str,
) -> str | None
```
Naviga Brocardi per trovare l'URL di un articolo specifico. Cerca prima nella pagina indice principale; se non trovato, scansiona le sub-pagine delle sezioni (senza limite fisso — si ferma appena trova il match).

Pattern ricerca: `href="...art{article_num}.html"` (word-boundary — non matcha `art2043x.html`).

---

```python
def parse_massime_references(massime: list[Massima]) -> list[dict[str, str | int]]
```
Estrae riferimenti Cassazione dalle massime per lookup diretto su Italgiure.

Ritorna: `[{"autorita": str, "numero": int, "anno": int}, ...]`

Solo massime con `is_cassazione=True` e campi `numero`+`anno` presenti. Deduplica per `numero/anno`.

---

## italgiure — Client Solr Cassazione

Client asincrono per le API Solr di Italgiure (Corte di Cassazione).

### client.py — Query e formattazione

**File**: `src/lib/italgiure/client.py`

**Endpoint**: `POST https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select?app.query`

**SSL**: `verify=False` — certificato non valido su `www.italgiure.giustizia.it`. Hardcoded, necessario.

**Auth**: Nessuna API key. Il client recupera prima la homepage per ottenere il session cookie (anti-bot check).

**Collezioni Solr**:

| Chiave | Collezione | Contenuto |
|--------|-----------|-----------|
| `"civile"` | `snciv` | ~186.000 decisioni civili |
| `"penale"` | `snpen` | ~238.000 decisioni penali |
| `"tutti"` | `snciv` + `snpen` | Entrambe |

**Campi Solr principali**:

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `numdec` | str | Numero decisione (zfill 5) |
| `anno` | str | Anno |
| `datdep` | str | Data deposito (`"YYYYMMDD"`) |
| `szdec` | str | Sezione (`"1"`, `"SU"`, `"L"`, ecc.) |
| `materia` | str | Materia (es. `"DIRITTO CIVILE"`) |
| `tipoprov` | str | Tipo provvedimento (`S`=sentenza, `O`=ordinanza, `D`=decreto) |
| `ocr` | str | Testo completo (troncato a 30.000 caratteri) |
| `ocrdis` | str | Dispositivo |
| `relatore` | str | Nome relatore |
| `presidente` | str | Nome presidente |

**Troncamento OCR**: `_MAX_OCR_LENGTH = 30000` caratteri per evitare saturazione context window.

#### Funzioni pubbliche

```python
async def solr_query(params: dict) -> dict
```
Esegue query Solr POST con body form-encoded. Gestisce parametri multi-valore (`fq` lista). Ritorna JSON Solr grezzo.

---

```python
def build_search_params(
    query: str,
    archivio: str = "tutti",      # "civile" | "penale" | "tutti"
    materia: str | None = None,
    sezione: str | None = None,
    anno_da: int | None = None,
    anno_a: int | None = None,
    rows: int = 10,
    start: int = 0,
    highlight: bool = True,
) -> dict
```
Costruisce parametri per ricerca full-text. Usa `defType=edismax`, boost `ocrdis^5 ocr^1`, sort per data deposito decrescente.

Con `highlight=True`: frammenti da 400 caratteri, 2 snippet per campo `ocr`/`ocrdis`.

---

```python
def build_lookup_params(
    numero: int,
    anno: int,
    archivio: str = "tutti",
    sezione: str | None = None,
) -> dict
```
Costruisce parametri per lookup diretto per numero+anno. Fetcha campi aggiuntivi (`ocr`, `relatore`, `presidente`). Ritorna massimo 5 risultati.

---

```python
def build_norma_variants(riferimento: str) -> str
```
Converte `"art. 2043 c.c."` in query Solr OR con varianti testuali comuni:
- `"art. 2043"`, `"articolo 2043"`
- Per codici noti: `"2043 c.c."`, `"2043 cod. civ."`, `"2043 codice civile"`

Ritorna stringa `ocr:(...)` pronta per la query Solr.

---

```python
def format_full_text(doc: dict) -> str
```
Formatta una decisione completa in markdown. Struttura: estremi, materia, relatore, presidente, testo (`ocr`), dispositivo (`ocrdis`). Aggiunge nota di troncamento se OCR > 30.000 caratteri.

---

```python
def format_summary(doc: dict, highlights: dict[str, list[str]] | None = None) -> str
```
Formatta un risultato di ricerca in formato compatto (lista). Mostra estremi, materia, estratto con highlight (se disponibile) o primi 200 caratteri del dispositivo.

---

```python
def format_estremi(doc: dict) -> str
```
Genera stringa estremi: `"Cass. civ., sez. I, n. 12345/2024, dep. 27/08/2024"`.

---

## gpdp — Garante Privacy

Client HTTP per il sito del Garante per la Protezione dei Dati Personali (GPDP).

### client.py — DocResult, ricerca, fetch

**File**: `src/lib/gpdp/client.py`

**Backend**: Liferay Portal — nessuna API JSON pubblica. Scraping HTML via BeautifulSoup.

**Endpoint**:
- Ricerca: `GET https://www.garanteprivacy.it/web/guest/home/ricerca` con parametri Liferay portlet
- Documento: `GET https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/print/{ID}`

**Identificatori**: DocWeb ID (interi sequenziali). Esempi noti: `9677876` (linee guida cookie 2021).

**Paginazione**: 10 risultati per pagina; `search_docs` fetcha automaticamente le pagine successive.

**Troncamento testo**: `_MAX_TEXT_LENGTH = 6000` caratteri per documento completo.

**Rate limiting**: Nessun throttling implementato — usare con moderazione.

#### Dataclass `DocResult`

```python
@dataclass
class DocResult:
    docweb_id: int
    title: str
    date: str           # formato "DD/MM/YYYY"
    tipologia: str      # es. "Provvedimento", "Parere", "Linee guida"
    argomenti: list[str] = field(default_factory=list)
    abstract: str = ""
```

#### Funzioni pubbliche

```python
async def search_docs(
    query: str = "",
    data_da: str = "",          # "DD/MM/YYYY"
    data_a: str = "",           # "DD/MM/YYYY"
    tipologia_id: str = "",     # ID Liferay tipologia
    argomento_id: str = "",     # ID Liferay argomento
    rows: int = 10,             # max 50
    sort_by: str = "data",
) -> list[DocResult]
```
Ricerca documenti GPDP. Fetcha automaticamente più pagine se `rows > 10`. Limite assoluto 50 risultati.

---

```python
async def fetch_doc(docweb_id: int) -> tuple[str, str]
```
Fetch testo completo documento via URL print. Ritorna `(title, body_text)`.

Rimuove tag `script`, `style`, `nav`, `header`, `footer` e toolbar Liferay prima dell'estrazione.

---

```python
def format_result(doc: DocResult) -> str
```
Formatta un `DocResult` come blocco markdown. Mostra: titolo, tipo, data, link DocWeb, argomenti, abstract (troncato a 300 caratteri).

---

```python
def format_full(title: str, text: str, docweb_id: int) -> str
```
Formatta documento completo come markdown. Aggiunge nota di troncamento se testo > 6.000 caratteri.

---

## Note tecniche trasversali

| Libreria | SSL | Auth | Rate limit | Cache |
|----------|-----|------|-----------|-------|
| visualex | Standard | Nessuna | Nessuno | In-memory (Brocardi URL) |
| brocardi | Standard | Nessuna | `asyncio.sleep(0.5)` tra sub-pagine | JSON persistente |
| italgiure | `verify=False` | Session cookie (homepage) | Nessuno | Nessuna |
| gpdp | Standard | Nessuna | Nessuno | Nessuna |

Tutti i client usano `httpx.AsyncClient` con `follow_redirects=True` e User-Agent Chrome 120.
