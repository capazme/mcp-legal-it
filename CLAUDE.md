# mcp-legal-it — Project Context

> MCP server con 140+ tool di calcolo legale italiano, consultazione normativa
> (Normattiva, EUR-Lex, Brocardi) e ricerca giurisprudenziale (Italgiure/Cassazione).

## Confini del progetto — LEGGERE PRIMA

Questo progetto è **autonomo e indipendente** dal SAPG Tech Desk.

| Progetto | Path | Scopo |
|----------|------|-------|
| **mcp-legal-it** (questo) | `/Users/gpuzio/Desktop/CODE/mcp-legal-it/` | Tool legali generici: calcoli, normativa, giurisprudenza |
| SAPG MCP Server | `~/Desktop/CODE/SAPG TECH DESK/sapg-tech-desk/apps/mcp-server/` | Piattaforma compliance: clienti, checklist, task, documenti |

**I tool Italgiure (`leggi_sentenza`, `cerca_giurisprudenza`, ecc.) sono QUI, non in SAPG.**
Se un agente non vede `leggi_sentenza`, è perché sta guardando il server sbagliato.

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Framework MCP | FastMCP >= 2.0 (`@mcp.tool()`, `@mcp.prompt()`, `@mcp.resource()`) |
| HTTP client | httpx >= 0.27 (async) |
| HTML scraping | BeautifulSoup4 + lxml |
| PDF generation | fpdf2 |
| Python | >= 3.10, venv in `.venv/` |
| Test | pytest + pytest-asyncio |

## Struttura

```
mcp-legal-it/
├── src/
│   ├── server.py              # FastMCP entry point — registra tutti i tool
│   ├── prompts.py             # 12 workflow guidati (@mcp.prompt)
│   ├── resources.py           # 8 risorse statiche (@mcp.resource)
│   ├── lib/
│   │   ├── visualex/          # Normattiva + EUR-Lex scraper
│   │   │   ├── scraper.py     # fetch_article(), fetch_annotations(), fetch_normattiva_full_text()
│   │   │   ├── map.py         # BROCARDI_CODICI, ATTI_NOTI, resolve_atto(), find_brocardi_url()
│   │   │   └── models.py      # Norma, NormaVisitata dataclasses
│   │   ├── brocardi/          # Scraper Brocardi standalone
│   │   │   └── client.py      # fetch_brocardi(), BrocardiResult, Massima, parse_massime_references()
│   │   └── italgiure/         # Client Italgiure (Cassazione Solr API)
│   │       └── client.py      # solr_query(), build_*_params(), format_*()
│   └── tools/
│       ├── legal_citations.py # cite_law, fetch_law_article, fetch_law_annotations, cerca_brocardi, download_law_pdf
│       ├── italgiure.py       # leggi_sentenza, cerca_giurisprudenza, giurisprudenza_su_norma, ultime_pronunce
│       ├── rivalutazioni_istat.py
│       ├── tassi_interessi.py
│       ├── scadenze_termini.py
│       ├── atti_giudiziari.py
│       ├── fatturazione_avvocati.py
│       ├── parcelle_professionisti.py
│       ├── risarcimento_danni.py
│       ├── diritto_penale.py
│       ├── proprieta_successioni.py
│       ├── investimenti.py
│       ├── dichiarazione_redditi.py
│       └── varie.py
└── tests/
    ├── unit/
    │   ├── test_calculations.py     # Test calcoli numerici
    │   ├── test_legal_citations.py  # Test cite_law, resolve_act, PDF helpers
    │   └── test_brocardi.py         # Test scraper Brocardi e tool cerca_brocardi
    └── comparison/                  # Test di confronto con valori attesi
```

## Tool disponibili (14 categorie, 144 tool)

### Consultazione Normativa
| Tool | Descrizione |
|------|-------------|
| `cite_law(reference, include_annotations?)` | Testo ufficiale da Normattiva/EUR-Lex. Entry point principale. |
| `fetch_law_article(act_type, article, date?, act_number?)` | Basso livello: parametri espliciti |
| `fetch_law_annotations(act_type, article, ...)` | Solo annotazioni Brocardi |
| `cerca_brocardi(reference)` | Annotazioni complete: ratio, spiegazione, massime strutturate + riferimenti Cassazione |
| `download_law_pdf(reference)` | PDF ufficiale (EUR-Lex) o generato (Normattiva) |

### Giurisprudenza Cassazione (Italgiure)
| Tool | Descrizione |
|------|-------------|
| `leggi_sentenza(numero, anno, sezione?, archivio?)` | **Testo completo** da Italgiure. Usare quando si ha già il numero. |
| `cerca_giurisprudenza(query, archivio?, materia?, ...)` | Ricerca full-text nelle sentenze |
| `giurisprudenza_su_norma(riferimento, archivio?)` | Sentenze che citano un articolo specifico |
| `ultime_pronunce(materia?, sezione?, archivio?)` | Ultime decisioni depositate |

### Calcoli (tool numerici, non richiedono cite_law)
1. Rivalutazione monetaria (11 tool) — ISTAT, TFR, canoni
2. Interessi e tassi (10 tool) — legali, mora, TAEG, ammortamento
3. Scadenze processuali (11 tool) — Cartabia, impugnazioni, esecuzioni
4. Atti giudiziari (15 tool) — contributo unificato, pignoramento, decreto ingiuntivo
5. Parcelle avvocati (11 tool) — D.M. 55/2014, civile, penale, stragiudiziale
6. Parcelle professionisti (11 tool) — CTU, mediazione, compenso orario
7. Risarcimento danni (7 tool) — biologico micro/macro, parentale, INAIL
8. Diritto penale (5 tool) — pena, prescrizione, conversione
9. Proprietà e successioni (11 tool) — eredità, IMU, usufrutto
10. Investimenti (5 tool) — BOT, BTP, buoni postali
11. Dichiarazione redditi (14 tool) — IRPEF, regime forfettario, TFR
12. Varie (12 tool) — codice fiscale, IBAN, ATECO, prescrizione diritti

## Prompt guidati (12)

- `analisi_sinistro` — danno biologico + rivalutazione + interessi
- `recupero_credito` — interessi mora + decreto ingiuntivo + parcella
- `causa_civile` — contributo unificato + scadenze + preventivo
- `pianificazione_successione` — quote + imposte + adempimenti
- `parere_legale` — struttura rigorosa con cite_law obbligatorio
- `quantificazione_danni` — personalizzazione + attualizzazione
- `calcolo_parcella` — D.M. 55/2014 per attività civile/penale/stragiudiziale
- `verifica_prescrizione` — civile (artt. 2941-2946 c.c.) e penale
- `ricerca_normativa` — fonti primarie + norme collegate + giurisprudenza
- `analisi_articolo` — testo vigente + ratio + massime + norme collegate
- `confronto_norme` — specialità, gerarchia, coordinamento
- `mappatura_normativa` — mappa completa per settore/attività
- `analisi_giurisprudenziale` — workflow: cerca_giurisprudenza → leggi_sentenza → cite_law → sintesi

## Risorse statiche (legal://)

- `legal://riferimenti/procedura-civile` — fasi e termini post-Cartabia
- `legal://riferimenti/termini-processuali` — quadro sinottico termini
- `legal://riferimenti/contributo-unificato` — tabella scaglioni 2025
- `legal://riferimenti/irpef-detrazioni` — scaglioni IRPEF 2025-2026
- `legal://riferimenti/interessi-legali` — storico tassi 2000-2026
- `legal://riferimenti/checklist-decreto-ingiuntivo` — checklist ricorso
- `legal://riferimenti/fonti-diritto-italiano` — gerarchia fonti + formato citazione
- `legal://riferimenti/codici-e-leggi-principali` — indice ragionato codici e leggi UE

## Convenzioni di sviluppo

### Pattern tool
```python
from src.server import mcp

@mcp.tool()
async def nome_tool(parametro: str) -> str:
    """Docstring visibile all'LLM — descrivere quando usare il tool."""
    ...
```
Poi importare il modulo in `src/server.py` nella lista degli import.

### Pattern lib
- `src/lib/<nome>/client.py` — logica di scraping/query
- `src/lib/<nome>/__init__.py` — re-export delle funzioni pubbliche
- Le lib non dipendono da `src.server` — solo da httpx, bs4, ecc.

### Aggiungere un nuovo tool module
1. Creare `src/tools/nuovo.py` con `@mcp.tool()` decorators
2. Aggiungere `nuovo` nell'import di `src/server.py`
3. Aggiornare la stringa `instructions` in `server.py` (categoria e nome tool)
4. Scrivere test in `tests/unit/test_nuovo.py`

### Legal Grounding Protocol
- **Norme**: usare sempre `cite_law()` — mai citare testo articoli a memoria
- **Sentenze con numero noto**: usare `leggi_sentenza(numero, anno)` — mai web search
- **Sentenze su tema**: `cerca_giurisprudenza()` per trovare, poi `leggi_sentenza()` per leggere
- **Annotazioni**: `cerca_brocardi()` per massime strutturate con riferimenti Cassazione
- I tool di calcolo applicano le norme internamente — non richiedono cite_law

## Test

```bash
# Tutti i test (esclude live)
.venv/bin/pytest tests/ -m "not live"

# Solo unit test
.venv/bin/pytest tests/unit/ -v

# Test live (richiedono connessione)
.venv/bin/pytest tests/ -m "live"
```

- `tests/unit/` — mock HTTP, nessuna connessione esterna
- `tests/comparison/` — valori numerici attesi, eseguiti senza mock
- Marker `@pytest.mark.live` per test che colpiscono server reali

## Git Flow

Questo progetto usa **Git Flow classico**. Le regole sono tassative.

### Branch permanenti

| Branch | Scopo | Protetto |
|--------|-------|----------|
| `main` | Produzione — codice stabile e rilasciato | Sì — solo merge da `release/*` e `hotfix/*` |
| `develop` | Integrazione — raccoglie le feature completate | Sì — solo merge da `feature/*`, `release/*`, `hotfix/*` |

### Branch temporanei

| Prefisso | Da | Merge verso | Scopo |
|----------|----|-------------|-------|
| `feature/<nome>` | `develop` | `develop` | Nuova funzionalità o miglioramento |
| `fix/<nome>` | `develop` | `develop` | Bug fix non urgente |
| `release/<versione>` | `develop` | `main` + `develop` | Preparazione rilascio (bump version, changelog, fix finali) |
| `hotfix/<nome>` | `main` | `main` + `develop` | Fix critico in produzione |

### Regole operative

1. **Mai committare direttamente su `main`** — sempre via `release/*` o `hotfix/*`
2. **Mai committare direttamente su `develop`** — sempre via `feature/*` o `fix/*`
3. **Branch di lavoro**: creare sempre da `develop` (tranne hotfix, da `main`)
4. **Merge**: usare `--no-ff` per mantenere la storia dei branch nel grafo
5. **Naming**: `feature/add-solr-facets`, `fix/brocardi-404`, `release/1.2.0`, `hotfix/eurlex-waf`
6. **Pulizia**: eliminare il branch dopo il merge (locale e remote)
7. **Tag**: creare tag `vX.Y.Z` su `main` dopo ogni merge da `release/*`

### Workflow per Claude Code

```bash
# Nuova feature
git checkout develop
git pull origin develop
git checkout -b feature/<nome>
# ... lavoro ...
git push -u origin feature/<nome>
# PR: feature/<nome> → develop

# Hotfix urgente
git checkout main
git pull origin main
git checkout -b hotfix/<nome>
# ... fix ...
git push -u origin hotfix/<nome>
# PR: hotfix/<nome> → main (poi merge main → develop)

# Release
git checkout develop
git checkout -b release/X.Y.Z
# ... bump version, fix finali ...
# PR: release/X.Y.Z → main (poi merge main → develop, tag vX.Y.Z)
```

### Versioning

Segue [Semantic Versioning](https://semver.org/):
- **MAJOR** (X): breaking change nelle API dei tool (signature, output format)
- **MINOR** (Y): nuovi tool, nuove feature, nuovi scraper
- **PATCH** (Z): bug fix, miglioramenti interni, aggiornamenti dati

## Italgiure — note tecniche

- **API**: Solr REST su `https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr`
- **Collezioni**: `snciv` (civile, ~186K doc) e `snpen` (penale, ~238K doc)
- **SSL**: certificato non valido → `verify=False` in httpx (hardcoded, necessario)
- **Autenticazione**: nessuna — API pubblica
- **Campi chiave**: `numdec` (numero), `anno`, `datdep` (data deposito), `szdec` (sezione), `ocr` (testo), `ocrdis` (dispositivo)
- **OCR troncato** a 30000 caratteri per evitare saturazione context window

## Brocardi — note tecniche

- **Navigazione in due passi**: URL base del codice → trova pagina articolo → scraping
- **Cache persistente JSON** degli URL degli articoli (`~/.cache/mcp-legal-it/brocardi_urls.json`)
- **Massime strutturate**: parsing regex per autorità (Cass., Trib., Cons. Stato, CGUE, CEDU)
- **`parse_massime_references()`**: estrae riferimenti Cassazione per `leggi_sentenza()`
- **`BrocardiResult.cassazione_references`**: property che filtra solo massime Cass.

## Workflow Brocardi → Italgiure

```
cerca_brocardi("art. 2043 c.c.")
  └─> BrocardiResult.massime = [Massima(autorita="Cass. civ.", numero="100", anno="2024"), ...]
  └─> parse_massime_references(massime) = [{"numero": 100, "anno": 2024}, ...]
  └─> leggi_sentenza(100, 2024)  ← testo completo da Italgiure
```

## Docker

Il server supporta due transport: **stdio** (default, per Claude Desktop/Code) e **SSE** (HTTP, per deployment remoti).

### Env vars

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` o `sse` |
| `MCP_HOST` | `0.0.0.0` | Bind address (solo SSE) |
| `MCP_PORT` | `8000` | Porta (solo SSE) |
| `LEGAL_PROFILE` | `full` | Profilo tool da caricare |
| `MCP_CACHE_DIR` | — | Directory cache Brocardi |

### Comandi

```bash
# Build
docker build -t mcp-legal-it .

# Run SSE (porta 8000)
docker run -p 8000:8000 mcp-legal-it

# Run con docker-compose
docker compose up

# Test endpoint SSE
curl http://localhost:8000/sse
```

### Configurazione client MCP (SSE)

```json
{
  "mcpServers": {
    "legal-it": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```
