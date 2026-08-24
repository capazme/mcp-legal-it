# Architettura — mcp-legal-it

Documento tecnico per sviluppatori che lavorano sul codebase.
Per la panoramica ad alto livello vedere [README.md](README.md).

---

## Indice

1. [Entry points](#1-entry-points)
2. [Catena di import e registrazione tool](#2-catena-di-import-e-registrazione-tool)
3. [Sistema dei profili](#3-sistema-dei-profili)
4. [Pattern architetturale tool/impl](#4-pattern-architetturale-toolimpl)
5. [Layer lib/ — client esterni](#5-layer-lib----client-esterni)
6. [Prompts e Resources](#6-prompts-e-resources)
7. [Come aggiungere un nuovo tool](#7-come-aggiungere-un-nuovo-tool)
8. [Navigazione rapida del codebase](#8-navigazione-rapida-del-codebase)

---

## 1. Entry points

### `run_server.py` — transport selector

Entry point effettivo del processo. Seleziona il transport tramite env var e
avvia FastMCP con i parametri corretti:

```python
transport = os.environ.get("MCP_TRANSPORT", "stdio")

if transport == "sse":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)
else:
    mcp.run(transport="stdio")
```

Gestisce anche `MCP_PATH_PREFIX` per deployment SSE dietro reverse proxy:
se impostato, propaga `FASTMCP_SSE_PATH` e `FASTMCP_MESSAGE_PATH` prima
di importare `src.server` (FastMCP legge le env var all'inizializzazione).

### `src/server.py` — FastMCP init

Costruisce l'istanza `mcp` e registra tutti i moduli:

```python
mcp = FastMCP("Legal IT", instructions="...")

from src.tools import (  # 32 moduli — l'elenco completo è in src/server.py
    rivalutazioni_istat, tassi_interessi, scadenze_termini,
    atti_giudiziari, fatturazione_avvocati, parcelle_professionisti,
    risarcimento_danni, diritto_penale, diritto_societario, diritto_lavoro,
    crisi_impresa, proprieta_successioni, investimenti, dichiarazione_redditi,
    varie, procedura_civile, legal_citations, italgiure, gpdp, privacy_gdpr,
    cerdef, giustizia_amm, cgue, consob, gazzetta, corte_cost, orientamento,
    eu_implementation, giurisprudenza_unificata, modelli_atti,
    procure_quotazioni, analisi_fornitori,
)
from src import prompts, resources
```

Il parametro `instructions` è la stringa che FastMCP espone all'LLM client
come system-level context. Contiene: indice categorico dei tool, Legal Grounding
Protocol (obbligo di `cite_law()` prima di citare norme), workflow comuni, e
regole di formattazione output (`€ 1.234,56`, `GG/MM/AAAA`).

---

## 2. Catena di import e registrazione tool

La registrazione avviene per **side-effect di import**: quando Python esegue
`from src.tools import rivalutazioni_istat`, il corpo del modulo viene eseguito
e i decorator `@mcp.tool()` registrano le funzioni nell'istanza `mcp` globale.

```
run_server.py
  └─ from src.server import mcp
       └─ FastMCP("Legal IT") → istanza mcp
       └─ from src.tools import rivalutazioni_istat
            └─ @mcp.tool() → mcp._tool_registry["rivaluta_moneta"] = fn
       └─ from src.tools import tassi_interessi
            └─ @mcp.tool() → mcp._tool_registry["tasso_interesse_legale"] = fn
       └─ ... (32 moduli, 218 tool totali)
       └─ from src import prompts
            └─ @mcp.prompt() → 23 prompt registrati
       └─ from src import resources
            └─ @mcp.resource() → 15 resource statiche registrate
```

L'ordine degli import non è significativo per la correttezza, ma è mantenuto
stabile per la leggibilità del codice.

---

## 3. Sistema dei profili

Il profilo controlla quali tool vengono esposti all'LLM client tramite il
meccanismo `include_tags` di FastMCP. Solo i tool decorati con i tag inclusi
nel profilo vengono resi visibili.

```python
# src/server.py
_PROFILES: dict[str, set[str]] = {
    "sinistro":  {"danni", "rivalutazione", "interessi", "normativa", "giurisprudenza", "sinistro"},
    "credito":   {"interessi", "rivalutazione", "parcelle_avv", "normativa", "giurisprudenza", "credito"},
    "penale":    {"penale", "normativa", "giurisprudenza"},
    "fiscale":   {"fiscale", "proprieta", "utility", "consob", "investimenti", "crisi_impresa", "societario"},
    "normativa": {"normativa", "giurisprudenza", "giurisprudenza_amm", "giurisprudenza_ue", "privacy", "consob", "costituzionale"},
    "privacy":   {"privacy", "normativa", "giurisprudenza"},
    "studio":    {"scadenze", "giudiziario", "parcelle_avv", "parcelle_prof", "investimenti", "lavoro"},
    "redattore": {"atti", "giudiziario", "parcelle_avv", "scadenze", "normativa"},
    "cowork":    {"normativa", "giurisprudenza", "privacy", "parcelle_avv"},
}

_profile = os.environ.get("LEGAL_PROFILE", "full")
if _profile != "full" and _profile in _PROFILES:
    mcp.include_tags = _PROFILES[_profile]
```

| Profilo | Tool esposti | Caso d'uso |
|---------|-------------|-----------|
| `full` | 218 | Claude Code con Tool Search |
| `sinistro` | 73 | Risarcimento danni e sinistri |
| `credito` | 83 | Recupero crediti |
| `penale` | 45 | Diritto penale |
| `fiscale` | 62 | Calcoli fiscali, immobiliari, societari e di crisi |
| `normativa` | 60 | Ricerca normativa e giurisprudenziale (tutte le corti) |
| `privacy` | 57 | GDPR e privacy compliance |
| `studio` | 73 | Gestione studio legale |
| `redattore` | 78 | Redazione di atti giudiziari |
| `cowork` | 70 | Sessioni Cowork (set ridotto) |

Il profilo `full` è consigliato per Claude Code, che usa Tool Search per
caricare i tool on-demand senza saturare il context window.

---

## 4. Pattern architetturale tool/impl

I moduli tool seguono di norma il pattern `_impl` + wrapper `@mcp.tool()`:

```python
# Logica pura — testabile in isolamento, senza dipendenze FastMCP
async def _nome_tool_impl(param1: str, param2: str = "default") -> str:
    # chiama src/lib/, esegue calcoli, formatta risultato
    return risultato

# Wrapper MCP — solo decoratore + docstring per l'LLM + delega
@mcp.tool()
async def nome_tool(param1: str, param2: str = "default") -> str:
    """Docstring esposta all'LLM via protocollo MCP.

    Descrive cosa fa il tool, quando usarlo e il formato dell'output.
    """
    return await _nome_tool_impl(param1, param2)
```

**Perché questo pattern**: i test unitari mockano `httpx.AsyncClient` prima
dell'import del wrapper. Se la logica fosse nel corpo della funzione decorata,
il metaclass FastMCP interferirebbe con il patching. La funzione `_impl` può
essere importata e testata in isolamento:

```python
# In test:
@patch("src.lib.visualex.scraper.httpx.AsyncClient")
async def test_fetch_article(mock_client):
    from src.tools.legal_citations import _fetch_law_article_impl
    result = await _fetch_law_article_impl("decreto legislativo", "2003", "196", "13")
    assert "art. 13" in result
```

**Tool sincroni**: i tool di calcolo puro (senza I/O) usono `def` (non `async def`)
sia per `_impl` che per il wrapper. FastMCP gestisce entrambi correttamente.

---

## 5. Layer lib/ — client esterni

`src/lib/` contiene 12 moduli, uno per fonte esterna. Nessuno di essi importa
`src.server`: dipendono solo da httpx, BeautifulSoup e dalla stdlib, così restano
testabili senza il server MCP.

| Modulo | Fonte | Trasporto | Note |
|--------|-------|-----------|------|
| `visualex/` | Normattiva, EUR-Lex | HTML scraping | Vedi dettaglio sotto |
| `brocardi/` | Brocardi.it | HTML scraping | Massime strutturate, cache URL su disco |
| `italgiure/` | Cassazione | API Solr | `verify=False`, cookie anti-bot |
| `corte_cost/` | Corte Costituzionale | HTML scraping | Sentenze e ordinanze, parametri costituzionali |
| `cerdef/` | CeRDEF (MEF) | POST + XML embeddato | Paginazione via cookie di sessione |
| `giustizia_amm/` | TAR e Consiglio di Stato | Liferay + XML | Portlet con id d'istanza letto a runtime |
| `cgue/` | Corte di Giustizia UE | SPARQL su CELLAR | CELEX literal con `^^xsd:string` |
| `gpdp/` | Garante Privacy | Liferay scraping | Lettura via endpoint "stampa" |
| `consob/` | CONSOB | Liferay scraping | Bollettino delibere |
| `gazzetta/` | Gazzetta Ufficiale | HTML + RSS | Ricerca parametrica e sommari |
| `eu_implementation/` | EUR-Lex | HTML scraping | Misure nazionali di recepimento |
| `vies/` | VIES (Commissione UE) | SOAP | Validazione P.IVA intracomunitaria |

I quattro moduli storici sono documentati in dettaglio qui sotto; per gli altri il
riferimento è il rispettivo `client.py`, che espone le funzioni pubbliche via `__init__.py`.

### `src/lib/visualex/` — Normattiva, EUR-Lex, Brocardi

Tre file distinti:

- **`map.py`**: dizionari di mappatura — `NORMATTIVA_URN_CODICI` (codici → URN),
  `EURLEX` (tipi atto UE → prefissi CELEX), `BROCARDI_CODICI` (codici → URL base),
  `normalize_act_type()`, `find_brocardi_url()`.

- **`models.py`**: dataclass `Norma` (tipo, data, numero) con metodo `url(article="")`
  che genera URL Normattiva o EUR-Lex. Gestisce codici-allegato (es. Codice Civile =
  R.D. 262/1942:2) e varianti latine degli articoli (bis, ter, quater).

- **`scraper.py`**: client httpx async — `fetch_article()`, `fetch_annotations()`,
  `fetch_normattiva_full_text()`. Il parser Normattiva gestisce 4 scenari di
  struttura HTML (AKN dettagliato, AKN semplice, allegato, fallback).

### `src/lib/italgiure/` — Corte di Cassazione

API Solr su `italgiure.giustizia.it` (pubblica, SSL non valido → `verify=False`).
Cookie anti-bot: GET homepage prima di ogni query POST.

Funzioni principali: `solr_query()`, `build_search_params()`, `build_lookup_params()`,
`build_norma_variants()`, `format_estremi()`, `format_full_text()`.

Archivi: `snciv` (civile, ~186K doc), `snpen` (penale, ~238K doc).
Campo `ocr` = testo completo OCR, troncato a 30.000 caratteri.

### `src/lib/brocardi/` — Brocardi standalone

Client separato (rispetto a `visualex/`) per il parsing strutturato delle massime.
Espone `BrocardiResult` con `massime: list[Massima]` e property `cassazione_references`
(filtra solo massime Cass.). `parse_massime_references()` estrae numero e anno per
`leggi_sentenza()`.

### `src/lib/gpdp/` — Garante Privacy

Scraping Liferay Portal (nessuna API JSON). Ricerca tramite GET su `/web/guest/home/ricerca`
con parametri portlet. Lettura documento via endpoint "stampa" (`/docweb-display/print/{ID}`).
Dataclass `DocResult` con `docweb_id`, `title`, `date`, `tipologia`, `argomenti`, `abstract`.

---

## 6. Prompts e Resources

### `src/prompts.py` — 23 prompt guidati (`@mcp.prompt()`), GENERATED dal corpus

> Dal 2026-08 questo file è generato da `scripts/corpus/generate_prompts.py` a
> partire dai blocchi `prompt:` delle skill in `content/skills/`. Non modificarlo
> a mano — vedi CONTRIBUTING.md § Generated files.

Workflow pre-definiti che l'LLM può attivare: `analisi_sinistro`, `recupero_credito`,
`causa_civile`, `pianificazione_successione`, `parere_legale`, `quantificazione_danni`,
`calcolo_parcella`, `verifica_prescrizione`, `ricerca_normativa`, `analisi_articolo`,
`confronto_norme`, `mappatura_normativa`, `analisi_giurisprudenziale`, `compliance_privacy`,
`orientamento_giurisprudenziale`, `analisi_tributaria`, `analisi_giurisprudenza_amministrativa`,
`analisi_giurisprudenza_europea`, `analisi_costituzionale`, `attuazione_direttiva`,
`ricerca_gazzetta`, `analisi_delibere_consob`, `novita_consob`.

Elenco con parametri e catena di tool in [prompts-resources.md](prompts-resources.md).

### `src/resources.py` — 15 resource statiche (`@mcp.resource("legal://...")`)

Dati di riferimento sempre disponibili:
- `legal://riferimenti/procedura-civile`
- `legal://riferimenti/termini-processuali`
- `legal://riferimenti/contributo-unificato`
- `legal://riferimenti/irpef-detrazioni`
- `legal://riferimenti/interessi-legali`
- `legal://riferimenti/checklist-decreto-ingiuntivo`
- `legal://riferimenti/fonti-diritto-italiano`
- `legal://riferimenti/codici-e-leggi-principali`
- `legal://riferimenti/gdpr-checklist`
- `legal://riferimenti/ricerca-giurisprudenziale`
- `legal://riferimenti/cerdef-giurisprudenza`
- `legal://riferimenti/giustizia-amministrativa`
- `legal://riferimenti/cgue-giurisprudenza`
- `legal://riferimenti/consob-delibere`
- `legal://riferimenti/modelli-atti-catalogo`

---

## 7. Come aggiungere un nuovo tool

**4 passi obbligatori:**

**1. Creare il modulo tool**

```python
# src/tools/nuovo.py
from src.server import mcp

async def _mio_calcolo_impl(valore: float, anno: int) -> str:
    # logica pura
    return f"Risultato: {valore}"

@mcp.tool()
async def mio_calcolo(valore: float, anno: int) -> str:
    """Calcola X in base a Y. Usare quando...

    Args:
        valore: importo in euro
        anno: anno di riferimento (YYYY)
    Returns:
        Stringa formattata con il risultato e la formula applicata.
    """
    return await _mio_calcolo_impl(valore, anno)
```

**2. Registrare in `server.py`**

```python
from src.tools import (
    ...,
    nuovo,  # aggiungere qui
)
```

**3. Aggiornare `instructions` in `server.py`**

Aggiungere una riga nella categoria appropriata (o una nuova categoria):
```
- NUOVA CATEGORIA: mio_calcolo, altro_calcolo
```

**4. Scrivere i test**

```python
# tests/unit/test_nuovo.py
from unittest.mock import patch, AsyncMock
import pytest

@pytest.mark.asyncio
async def test_mio_calcolo_base():
    from src.tools.nuovo import _mio_calcolo_impl
    result = await _mio_calcolo_impl(1000.0, 2024)
    assert "Risultato" in result
```

---

## 8. Navigazione rapida del codebase

| Obiettivo | File |
|-----------|------|
| Aggiungere tool di calcolo | `src/tools/` — modulo per categoria, pattern `_impl` + wrapper |
| Aggiungere codice a Normattiva | `src/lib/visualex/map.py` → `NORMATTIVA_URN_CODICI` |
| Aggiungere codice a Brocardi | `src/lib/visualex/map.py` → `BROCARDI_CODICI` |
| Modificare istruzioni all'LLM | `src/server.py` → parametro `instructions` |
| Debug URL Normattiva | `src/lib/visualex/models.py` → `Norma.url()` |
| Debug parsing HTML Normattiva | `src/lib/visualex/scraper.py` → `_extract_normattiva_article()` |
| Debug query Solr Cassazione | `src/lib/italgiure/client.py` → `solr_query()` |
| Debug scraping GPDP | `src/lib/gpdp/client.py` → `_parse_results()`, `_parse_doc()` |
| Aggiungere prompt guidato | `src/prompts.py` → `@mcp.prompt()` |
| Aggiungere resource statica | `src/resources.py` → `@mcp.resource()` |
| Configurare un profilo | `src/server.py` → `_PROFILES` dict |
