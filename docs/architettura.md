# Architettura interna di mcp-legal-it

Documento tecnico per sviluppatori e LLM che operano sul codebase.

---

## 1. Schema generale

```
Client MCP (Claude Desktop / altro LLM)
        │
        │  protocollo MCP (stdio / SSE)
        ▼
  src/server.py          FastMCP — registra tool, prompt, resource
        │
        │  import a livello di modulo
        ▼
  src/tools/             15 moduli — ogni file registra i propri tool
  ├── rivalutazioni_istat.py
  ├── tassi_interessi.py
  ├── scadenze_termini.py
  ├── atti_giudiziari.py
  ├── fatturazione_avvocati.py
  ├── parcelle_professionisti.py
  ├── risarcimento_danni.py
  ├── diritto_penale.py
  ├── proprieta_successioni.py
  ├── investimenti.py
  ├── dichiarazione_redditi.py
  ├── varie.py
  ├── legal_citations.py     ← chiama visualex/
  ├── italgiure.py           ← chiama italgiure/
  └── gpdp.py                ← chiama gpdp/
        │
        │  chiamate HTTP async (httpx)
        ▼
  src/lib/               client HTTP e parser per fonti esterne
  ├── visualex/          Normattiva + EUR-Lex + Brocardi
  │   ├── map.py         dizionari URN e URL
  │   ├── models.py      costruzione URL da struttura Norma
  │   └── scraper.py     fetch HTML + parsing BeautifulSoup
  ├── italgiure/
  │   └── client.py      Solr API Cassazione
  └── gpdp/
      └── client.py      scraping Liferay Garante Privacy
        │
        │  HTTP/HTTPS
        ▼
  Fonti esterne ufficiali
  ├── normattiva.it      testo vigente delle norme
  ├── eur-lex.europa.eu  diritto europeo
  ├── brocardi.it        dottrina e massime giurisprudenziali
  ├── italgiure.giustizia.it  sentenze Cassazione (Solr)
  └── garanteprivacy.it  provvedimenti del Garante
```

Oltre ai tool, `server.py` importa `src/prompts` e `src/resources`, che registrano rispettivamente prompt riutilizzabili e resource statiche via `@mcp.prompt()` e `@mcp.resource()`.

---

## 2. Punto di ingresso: server.py

`server.py` è il file che avvia il server MCP. È intenzionalmente minimale: contiene solo la costruzione dell'istanza `FastMCP` e gli import dei moduli tool.

### Istanza FastMCP

```python
mcp = FastMCP("Legal IT", instructions="...")
```

Il parametro `instructions` è la stringa che FastMCP espone all'LLM client come system-level context del server. Contiene:

- **Indice categorico** dei 60+ tool disponibili, raggruppati in 15 categorie — aiuta l'LLM a scegliere il tool giusto senza dover enumerare ogni funzione
- **Legal Grounding Protocol** — regola fondamentale: prima di citare una norma, chiamare `cite_law()` per ottenere il testo vigente da Normattiva o EUR-Lex; mai usare la memoria pregressa per il contenuto degli articoli
- **Workflow discovery → lettura ufficiale** — il web search è ammesso per trovare identificatori (numero sentenza, DocWeb ID), ma la lettura del testo deve sempre passare dai tool ufficiali
- **Workflow comuni** — catene di tool suggerite per i casi d'uso più frequenti (sinistro, recupero credito, successione, analisi norma, privacy)
- **Regole output** — formato importi (€ 1.234,56), date (GG/MM/AAAA), obbligo di segnalare risultati indicativi

### Registrazione dei tool

I tool si registrano tramite import a livello di modulo: ogni `from src.tools import <modulo>` esegue il corpo del modulo, che contiene i decorator `@mcp.tool()`. L'ordine degli import non è significativo.

```python
from src.tools import (  # noqa: E402, F401
    rivalutazioni_istat,
    tassi_interessi,
    ...
    legal_citations,
    italgiure,
    gpdp,
)
from src import prompts, resources
```

### Aggiungere un nuovo modulo

1. Creare `src/tools/nuovo_modulo.py` con le funzioni `_impl` e i wrapper `@mcp.tool()`
2. Aggiungere l'import in `server.py`
3. Aggiornare la stringa `instructions` con la nuova categoria o i nuovi tool

---

## 3. Layer tools/ — pattern architetturale

**Tutti** i 15 moduli tool seguono lo stesso pattern: funzione `_impl` separata dal wrapper MCP.

```python
# Funzione _impl: logica pura, testabile senza contesto MCP
async def _nome_tool_impl(param1: str, param2: str = "default") -> str:
    # ... logica + chiamate a src/lib/
    return risultato

# Wrapper MCP: solo decoratore + docstring per l'LLM + delega
@mcp.tool()
async def nome_tool(param1: str, param2: str = "default") -> str:
    """Docstring esposta all'LLM via protocollo MCP.

    Descrive cosa fa il tool, i parametri accettati e il formato
    dell'output. Questa stringa è ciò che l'LLM legge per decidere
    se e come usare il tool.
    """
    return await _nome_tool_impl(param1, param2)
```

### Perché questo pattern

I test unitari mockano `httpx.AsyncClient` **prima** che il modulo venga importato, usando `@patch("src.lib.<modulo>.client.httpx.AsyncClient")`. Se la logica fosse direttamente nella funzione decorata con `@mcp.tool()`, il metaclass di FastMCP interferirebbe con il patching durante l'import. Separando la logica nella funzione `_impl`, i test possono importarla e testarla in isolamento:

```python
# In test:
from src.tools.legal_citations import _fetch_law_article_impl

# Il mock viene applicato prima dell'import del wrapper
@patch("src.lib.visualex.scraper.httpx.AsyncClient")
async def test_fetch_article(mock_client):
    result = await _fetch_law_article_impl("decreto legislativo", "2003", "196", "13")
    ...
```

---

## 4. Layer lib/ — tre client esterni

### 4.1 visualex/ — Normattiva, EUR-Lex, Brocardi

Questo è il client più articolato, composto da tre file.

#### map.py

Contiene i dizionari di mappatura che collegano nomi informali a identificatori ufficiali:

- `NORMATTIVA_URN_CODICI`: mappa nomi come `"codice civile"` o `"codice del consumo"` ai loro URN Normattiva completi. I codici che sono allegati di un altro atto (es. il Codice Civile è l'allegato 2 del R.D. 262/1942) includono il suffisso `:N` nell'URN (es. `regio.decreto:1942-03-16;262:2`). Questo suffisso deve **precedere** il segmento `~artNNN` nella costruzione dell'URL.
- `EURLEX`: mappa tipi di atto europeo (regolamento, direttiva, GDPR...) ai prefissi CELEX o URL diretti per i trattati.
- `BROCARDI_CODICI`: mappa nomi di codici agli URL base di Brocardi.
- `normalize_act_type()`: normalizza varianti ortografiche del tipo di atto (es. `"d.lgs."`, `"d. lgs."`, `"decreto legislativo"` → forma canonica).
- `find_brocardi_url()`: cerca in `BROCARDI_CODICI` per tipo atto e numero.

#### models.py

Definisce due dataclass:

**`Norma`** — rappresenta un atto normativo identificato da tipo, data e numero:
```python
@dataclass
class Norma:
    tipo_atto: str   # es. "decreto legislativo"
    data: str        # es. "2003" o "2003-06-30"
    numero_atto: str # es. "196"
```

Il metodo `url(article="")` genera l'URL Normattiva o EUR-Lex secondo questa logica:
1. Se il tipo è in `EURLEX` → URL EUR-Lex con CELEX o URL diretto
2. Se il tipo è in `NORMATTIVA_URN_CODICI` → URN dal dizionario, con allegato `:N` già incluso
3. Altrimenti → URN costruito come `tipo.atto:YYYY-MM-DD;numero`

In tutti i casi, se viene passato un articolo, viene appeso tramite `_append_article()` che gestisce le varianti latine (`bis`, `ter`, `quater`, ...) sia nella forma `13-bis` sia `13 bis`.

**Dettaglio critico — codici-allegato**: Per `"codice civile"`, l'URN base è `regio.decreto:1942-03-16;262:2`. Quando si aggiunge un articolo, il risultato deve essere `regio.decreto:1942-03-16;262:2~art13` — il numero allegato `:2` precede `~artNNN`. La funzione `_append_article()` aggiunge sempre il segmento `~artNNN` in coda all'URN completo, quindi questo comportamento è automatico.

**`NormaVisitata`** — composizione di `Norma` + numero articolo, espone un unico metodo `url()`.

#### scraper.py

Client HTTP async (httpx) con tre funzioni pubbliche:

- **`fetch_article(nv: NormaVisitata)`**: scarica l'HTML da Normattiva o EUR-Lex e lo parsifica. Per Normattiva gestisce 4 scenari di struttura HTML (AKN dettagliato, AKN semplice, allegato, fallback). Per EUR-Lex prova 4 strategie di ricerca dell'articolo nel DOM.

- **`fetch_annotations(nv: NormaVisitata)`**: accede a Brocardi in due passi — prima carica la pagina principale del codice per trovare il link all'articolo specifico (con cache in-memory `_brocardi_url_cache`), poi carica la pagina dell'articolo ed estrae le sezioni: Ratio Legis, Spiegazione, adagi (Brocardi), Massime giurisprudenziali.

- **`fetch_normattiva_full_text(norma: Norma)`** + **`download_eurlex_pdf(norma: Norma)`**: per il download dell'atto completo in testo o PDF.

### 4.2 italgiure/ — Corte di Cassazione

**Endpoint**: `POST https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select?app.query`

Il sito espone un'API Solr non documentata ma aperta.

**Aspetti critici**:

- **SSL invalido**: `httpx.AsyncClient(verify=False, ...)` — il certificato di `www.italgiure.giustizia.it` non è valido; senza questo flag tutte le richieste falliscono.
- **Cookie anti-bot**: prima di ogni query Solr, il client fa una GET sulla homepage per ottenere il cookie di sessione. La stessa istanza `AsyncClient` viene riusata per la query POST successiva.
- **Archivi**: il campo `kind` filtra tra `snciv` (sentenze civili, ~186K) e `snpen` (penali, ~238K). L'archivio `sic` (massimario) contiene solo metadati, non il testo completo.
- **Campo `ocr`**: testo completo OCR della sentenza — campo su cui avviene la ricerca full-text.
- **Campo `numdec`**: numero della decisione come stringa, non zero-padded. Le query di lookup usano `numdec:10787` (senza padding).
- **Highlighting Solr**: abilitato con `hl=true`, `hl.fl=ocr`, `hl.fragsize=400` per restituire estratti contestuali.

**Funzioni principali** (`client.py`):

- `solr_query(params)`: esegue la richiesta — homepage GET + POST Solr
- `build_search_params(...)`: costruisce parametri per ricerca full-text in `ocr`
- `build_lookup_params(numero, anno, ...)`: costruisce parametri per lookup diretto
- `build_norma_variants(riferimento)`: converte `"art. 2043 c.c."` in query Solr con OR di varianti testuali (`"art. 2043"`, `"articolo 2043"`, `"2043 c.c."`, ecc.)
- `format_estremi(doc)`: formatta gli estremi citazionali (`Cass. civ. sez. III, n. 10787/2024, dep. 27/08/2025`)
- `format_summary(doc, highlight)` / `format_full_text(doc)`: formattazione markdown per risultati e testo completo

### 4.3 gpdp/ — Garante per la Protezione dei Dati Personali

**Sito**: Liferay Portal — nessuna API JSON pubblica. Tutto tramite scraping HTML.

**Ricerca** (`search_docs(...)`): GET su `/web/guest/home/ricerca` con parametri portlet. Il prefix di ogni parametro è `_g_gpdp5_search_GGpdp5SearchPortlet_`. I parametri principali sono `text` (query), `dataInizio`/`dataFine`, `idsTipologia`, `idsArgomenti`, `cur` (numero pagina). La funzione pagina automaticamente se `rows > 10`.

**Struttura HTML dei risultati**:
```
div.card-risultato
  a.titolo-risultato         → titolo + href con /docweb/{ID}
  div.data-risultato > p     → data in GG/MM/AAAA
  p.estratto-risultato       → abstract
  p.ricercaArgomentiPar      → label ("Tipologia:", "Argomenti:")
    (sibling div > a)        → badge con valori
```

**DocWeb ID**: intero sequenziale estratto dal path `/docweb/{ID}` nell'href del titolo. È l'identificatore universale per costruire URL di visualizzazione e stampa.

**Lettura documento** (`fetch_doc(docweb_id)`): GET su `...docweb-display/print/{ID}` — endpoint "stampa" di Liferay che serve HTML più pulito (senza navigazione, sidebar, cookies banner). La funzione `_parse_doc()` rimuove script/style/nav/header/footer e le sezioni Liferay di condivisione social, poi estrae titolo e testo del corpo.

**`DocResult`** (dataclass): `docweb_id`, `title`, `date`, `tipologia`, `argomenti`, `abstract`.

---

## 5. Test

```
tests/
├── unit/          test con httpx mockato — nessuna connessione di rete
└── integration/   (se presenti) test live marcati @pytest.mark.live
```

### Pattern di mock

I test unitari mockano `httpx.AsyncClient` a livello di modulo lib, non di tool:

```python
@patch("src.lib.visualex.scraper.httpx.AsyncClient")
async def test_fetch_article(mock_client_cls):
    mock_instance = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_instance
    mock_instance.get.return_value = mock_response(html="...")

    from src.tools.legal_citations import _fetch_law_article_impl
    result = await _fetch_law_article_impl(...)
```

Le funzioni `_impl` vengono importate **dopo** aver applicato il patch, oppure il patch viene applicato sul modulo lib (non sul wrapper tool) per evitare conflitti con il metaclass FastMCP.

---

## 6. Dipendenze principali

| Pacchetto | Uso |
|-----------|-----|
| `fastmcp>=2.0.0` | Framework MCP: `@mcp.tool()`, `@mcp.prompt()`, `@mcp.resource()` |
| `httpx>=0.27` | Client HTTP async per tutte le chiamate esterne |
| `beautifulsoup4` + `lxml` | Parsing HTML (Normattiva, Brocardi, GPDP) |
| `fpdf2` | Generazione PDF per alcuni tool di redazione atti |

Per la lista completa vedere `pyproject.toml` o `requirements.txt`.

---

## 7. Navigazione rapida del codebase

| Obiettivo | Dove guardare |
|-----------|--------------|
| Aggiungere un tool di calcolo | `src/tools/` — scegliere il modulo per categoria, seguire il pattern `_impl` + wrapper |
| Aggiungere un codice a Normattiva | `src/lib/visualex/map.py` — `NORMATTIVA_URN_CODICI` |
| Aggiungere un codice a Brocardi | `src/lib/visualex/map.py` — `BROCARDI_CODICI` |
| Cambiare le istruzioni all'LLM | `src/server.py` — parametro `instructions` di `FastMCP(...)` |
| Capire come viene costruito un URL Normattiva | `src/lib/visualex/models.py` — `Norma.url()` e `_append_article()` |
| Debug parsing HTML Normattiva | `src/lib/visualex/scraper.py` — `_extract_normattiva_article()` e i 4 scenari |
| Debug query Solr Cassazione | `src/lib/italgiure/client.py` — `solr_query()` e `build_search_params()` |
| Debug scraping GPDP | `src/lib/gpdp/client.py` — `_parse_results()` e `_parse_doc()` |
| Aggiungere prompt riutilizzabili | `src/prompts.py` — `@mcp.prompt()` |
| Aggiungere resource statiche | `src/resources.py` — `@mcp.resource()` |
