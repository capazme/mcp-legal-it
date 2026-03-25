# mcp-legal-it — Project Context

> MCP server con 177 tool di calcolo legale italiano, consultazione normativa
> (Normattiva, EUR-Lex, Brocardi), ricerca giurisprudenziale (Italgiure, CeRDEF,
> TAR/CdS, CGUE), delibere CONSOB.

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
│   ├── prompts.py             # 19 workflow guidati (@mcp.prompt)
│   ├── resources.py           # 13 risorse statiche (@mcp.resource)
│   ├── lib/
│   │   ├── visualex/          # Normattiva + EUR-Lex scraper
│   │   │   ├── scraper.py     # fetch_article(), fetch_annotations(), fetch_normattiva_full_text()
│   │   │   ├── map.py         # BROCARDI_CODICI, ATTI_NOTI, resolve_atto(), find_brocardi_url()
│   │   │   └── models.py      # Norma, NormaVisitata dataclasses
│   │   ├── brocardi/          # Scraper Brocardi standalone
│   │   │   └── client.py      # fetch_brocardi(), BrocardiResult, Massima, parse_massime_references()
│   │   ├── italgiure/         # Client Italgiure (Cassazione Solr API)
│   │   │   └── client.py      # solr_query(), build_*_params(), format_*()
│   │   ├── consob/            # Client CONSOB (Liferay Portal scraper)
│   │   │   └── client.py      # search_delibere(), fetch_delibera(), format_*()
│   │   ├── cerdef/            # Client CeRDEF (Giurisprudenza Tributaria MEF)
│   │   │   └── client.py      # search_giurisprudenza(), fetch_provvedimento(), format_*()
│   │   ├── giustizia_amm/     # Client Giustizia Amministrativa (TAR/CdS)
│   │   │   └── client.py      # search_provvedimenti(), fetch_provvedimento_text(), format_*()
│   │   └── cgue/              # Client CGUE (CELLAR SPARQL + EUR-Lex)
│   │       └── client.py      # search_giurisprudenza(), fetch_sentenza_text(), format_*()
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
│       ├── varie.py
│       ├── consob.py          # cerca_delibere_consob, leggi_delibera_consob, ultime_delibere_consob
│       ├── cerdef.py          # cerca_giurisprudenza_tributaria, cerdef_leggi_provvedimento, ultime_sentenze_tributarie
│       ├── giustizia_amm.py   # cerca_giurisprudenza_amministrativa, leggi_provvedimento_amm, giurisprudenza_amm_su_norma, ultimi_provvedimenti_amm
│       ├── cgue.py            # cerca_giurisprudenza_cgue, leggi_sentenza_cgue, giurisprudenza_cgue_su_norma, ultime_sentenze_cgue
│       └── privacy_gdpr.py
└── tests/
    ├── unit/
    │   ├── test_calculations.py     # Test calcoli numerici
    │   ├── test_legal_citations.py  # Test cite_law, resolve_act, PDF helpers
    │   ├── test_brocardi.py         # Test scraper Brocardi e tool cerca_brocardi
    │   ├── test_consob.py          # Test scraper CONSOB e 3 tool delibere
    │   ├── test_privacy_gdpr.py   # Test 12 tool GDPR/Privacy compliance
    │   ├── test_cerdef.py         # Test CeRDEF scraper e 3 tool tributari (88 test)
    │   ├── test_giustizia_amm.py  # Test GA scraper e 4 tool TAR/CdS (90 test)
    │   ├── test_cgue.py           # Test CGUE SPARQL client e 4 tool (76 test)
    │   ├── test_http_retry.py     # Test retry helper con backoff
    │   ├── test_atti_giudiziari.py     # Test 23 tool atti giudiziari (134 test)
    │   ├── test_scadenze_termini.py    # Test 11 tool scadenze processuali (91 test)
    │   ├── test_fatturazione_avvocati.py # Test 12 tool parcelle DM 55/2014 (100 test)
    │   ├── test_dichiarazione_redditi.py # Test 15 tool IRPEF/fiscale (121 test)
    │   ├── test_proprieta_successioni.py # Test 12 tool proprietà/successioni (110 test)
    │   ├── test_rivalutazioni_istat.py   # Test 11 tool rivalutazione ISTAT (70 test)
    │   ├── test_tassi_interessi.py       # Test 10 tool interessi/tassi (59 test)
    │   ├── test_varie.py                 # Test 12 tool utility varie (79 test)
    │   ├── test_parcelle_professionisti.py # Test 11 tool parcelle professionisti (79 test)
    │   ├── test_risarcimento_danni.py    # Test 7 tool risarcimento danni (75 test)
    │   ├── test_investimenti.py          # Test 5 tool investimenti (48 test)
    │   └── test_diritto_penale.py        # Test 5 tool diritto penale (49 test)
    └── comparison/                  # Test di confronto con valori attesi
        └── test_privacy_docs.py   # Test parametri e riferimenti normativi privacy
```

## Tool disponibili (19 categorie, 177 tool)

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

### CONSOB (Bollettino delibere)
| Tool | Descrizione |
|------|-------------|
| `cerca_delibere_consob(query, tipologia?, argomento?, data_da?, data_a?)` | Ricerca delibere/provvedimenti nel bollettino CONSOB |
| `leggi_delibera_consob(numero)` | **Testo completo** della delibera. Usare quando si ha già il numero. |
| `ultime_delibere_consob(tipologia?, argomento?)` | Ultime delibere pubblicate dalla CONSOB |

### Giurisprudenza Tributaria (CeRDEF — def.finanze.it)
| Tool | Descrizione |
|------|-------------|
| `cerca_giurisprudenza_tributaria(query, tipo_provvedimento?, ente?, data_da?, data_a?, numero?, criterio?, ordinamento?)` | Ricerca nel CeRDEF — IVA, IRES, accertamento, riscossione |
| `cerdef_leggi_provvedimento(guid)` | **Testo completo** tramite GUID. Usare dopo la ricerca. |
| `ultime_sentenze_tributarie(ente?, tipo_provvedimento?)` | Ultime pronunce tributarie depositate |

### Giustizia Amministrativa (TAR/CdS — giustizia-amministrativa.it)
| Tool | Descrizione |
|------|-------------|
| `cerca_giurisprudenza_amministrativa(query, sede?, tipo?, anno?)` | Ricerca TAR/CdS — appalti, urbanistica, PA, accesso atti |
| `leggi_provvedimento_amm(sede, nrg, nome_file)` | **Testo completo** da mdp subdomain. Usare dopo la ricerca. |
| `giurisprudenza_amm_su_norma(riferimento, sede?, anno_da?)` | Sentenze che citano un articolo specifico |
| `ultimi_provvedimenti_amm(sede?, tipo?)` | Ultimi provvedimenti depositati |

### Giurisprudenza CGUE (CELLAR SPARQL — publications.europa.eu)
| Tool | Descrizione |
|------|-------------|
| `cerca_giurisprudenza_cgue(query, corte?, tipo_documento?, anno_da?, anno_a?, materia?)` | Ricerca sentenze Corte di Giustizia UE e Tribunale UE |
| `leggi_sentenza_cgue(cellar_uri)` | **Testo completo** via CELLAR content negotiation. Usare dopo la ricerca. |
| `giurisprudenza_cgue_su_norma(riferimento, corte?, anno_da?)` | Sentenze che citano una norma UE (TFUE, direttive, regolamenti) |
| `ultime_sentenze_cgue(corte?, tipo_documento?, materia?)` | Ultime decisioni CGUE depositate |

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
13. Privacy/GDPR (12 tool) — informative privacy, cookie, DPA, DPIA, data breach, sanzioni

### Privacy/GDPR Compliance
| Tool | Descrizione |
|------|-------------|
| `genera_informativa_privacy(titolare, finalita[], ...)` | Informativa completa art. 13 o 14 GDPR con checklist elementi obbligatori |
| `genera_informativa_cookie(titolare, cookie_tecnici[], sito_web)` | Cookie policy con tabella cookie e testo banner suggerito |
| `genera_informativa_dipendenti(titolare, ...)` | Informativa privacy per i dipendenti (art. 13 GDPR + Statuto Lavoratori) |
| `genera_informativa_videosorveglianza(titolare, finalita[], ...)` | Cartello EDPB + informativa estesa per videosorveglianza |
| `genera_dpa(titolare, responsabile, ...)` | Contratto art. 28 GDPR con checklist 8 clausole obbligatorie |
| `genera_registro_trattamenti(titolare, trattamento, ...)` | Scheda art. 30 GDPR formattata |
| `genera_dpia(titolare, descrizione, rischi[], ...)` | DPIA completa con matrice rischi e rischio residuo |
| `analisi_base_giuridica(tipo_trattamento, contesto, finalita)` | Analisi basi giuridiche applicabili con raccomandazione motivata |
| `verifica_necessita_dpia(tipo_trattamento, ...)` | Verifica 9 criteri WP248 — ≥2 → DPIA obbligatoria |
| `valutazione_data_breach(tipo_violazione, ...)` | Valutazione rischio e obblighi di notifica/comunicazione |
| `calcolo_sanzione_gdpr(tipo_violazione, ...)` | Stima range sanzioni con analisi criteri art. 83(2) |
| `genera_notifica_data_breach(titolare, ...)` | Modulo notifica al Garante con scadenza 72h |

## Prompt guidati (19)

- `analisi_sinistro` — danno biologico + rivalutazione + interessi
- `recupero_credito` — interessi mora + decreto ingiuntivo + parcella
- `causa_civile` — contributo unificato + scadenze + preventivo
- `pianificazione_successione` — quote + imposte + adempimenti
- `parere_legale` — struttura rigorosa con cite_law obbligatorio
- `quantificazione_danni` — personalizzazione + attualizzazione
- `calcolo_parcella` — D.M. 55/2014 per attività civile/penale/stragiudiziale
- `verifica_prescrizione` — civile (artt. 2941-2946 c.c.) e penale
- `ricerca_normativa` — fonti primarie + norme collegate + giurisprudenza + CONSOB per settore finanziario
- `analisi_articolo` — testo vigente + ratio + massime + norme collegate
- `confronto_norme` — specialità, gerarchia, coordinamento
- `mappatura_normativa` — mappa completa per settore/attività + fonti autorità vigilanza
- `analisi_giurisprudenziale` — workflow: cerca_giurisprudenza → leggi_sentenza → cite_law → sintesi
- `analisi_tributaria` — workflow: cerca_giurisprudenza_tributaria → cerdef_leggi_provvedimento → cite_law
- `analisi_giurisprudenza_amministrativa` — workflow: cerca_giurisprudenza_amministrativa → leggi_provvedimento_amm → cite_law
- `analisi_giurisprudenza_europea` — workflow: cerca_giurisprudenza_cgue → leggi_sentenza_cgue → cite_law
- `compliance_privacy` — workflow GDPR: base giuridica → DPIA → registro → informativa → DPA
- `analisi_delibere_consob` — ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, normativa
- `novita_consob` — ultime delibere CONSOB con sintesi orientamenti per tipologia/argomento

## Risorse statiche (legal://) — 13

- `legal://riferimenti/procedura-civile` — fasi e termini post-Cartabia
- `legal://riferimenti/termini-processuali` — quadro sinottico termini
- `legal://riferimenti/contributo-unificato` — tabella scaglioni 2025
- `legal://riferimenti/irpef-detrazioni` — scaglioni IRPEF 2025-2026
- `legal://riferimenti/interessi-legali` — storico tassi 2000-2026
- `legal://riferimenti/checklist-decreto-ingiuntivo` — checklist ricorso
- `legal://riferimenti/fonti-diritto-italiano` — gerarchia fonti + formato citazione
- `legal://riferimenti/codici-e-leggi-principali` — indice ragionato codici e leggi UE
- `legal://riferimenti/gdpr-checklist` — checklist compliance GDPR con tool disponibili
- `legal://riferimenti/consob-delibere` — guida tool CONSOB: tipologie, argomenti, normativa mercati finanziari
- `legal://riferimenti/cerdef-giurisprudenza` — guida CeRDEF: enti, criteri di ricerca, norme fiscali principali
- `legal://riferimenti/giustizia-amministrativa` — guida TAR/CdS: 28 sedi, tipi provvedimento, norme amministrative
- `legal://riferimenti/cgue-giurisprudenza` — guida CGUE: corti, materie, formato CELEX/ECLI, workflow SPARQL

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
- **Sentenze Cassazione con numero noto**: usare `leggi_sentenza(numero, anno)` — mai web search
- **Sentenze Cassazione su tema**: `cerca_giurisprudenza()` per trovare, poi `leggi_sentenza()` per leggere
- **Sentenze tributarie**: `cerca_giurisprudenza_tributaria()` per trovare, poi `cerdef_leggi_provvedimento(guid)` per leggere
- **Sentenze TAR/CdS**: `cerca_giurisprudenza_amministrativa()` per trovare, poi `leggi_provvedimento_amm(sede, nrg, nome_file)` per leggere
- **Sentenze CGUE**: `cerca_giurisprudenza_cgue()` per trovare, poi `leggi_sentenza_cgue(cellar_uri)` per leggere
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

## CONSOB — note tecniche

- **Sito**: `https://www.consob.it/web/area-pubblica/bollettino/ricerca`
- **Portlet**: `it_consob_BollettinoRicercaPortlet` (Liferay Portal)
- **Autenticazione**: nessuna — ricerca pubblica GET
- **URL delibera**: `/web/area-pubblica/-/delibera-n.-{numero}` (es. `delibera-n.-23257`)
- **Numero delibera**: stringa (es. "23257", "23256-1" per varianti)
- **Date ricerca**: formato `YYYY-MM-DD` (campo HTML5 date)
- **Date risultati**: formato `DD/MM/YYYY`
- **Tipologie**: `delibera`, `comunicazione`, `provvedimento` + combinazioni con pipe
- **Argomenti**: 10 top categorie con ID Liferay (es. `4989535` = Abusi di mercato)
- **Max text**: 8000 caratteri (delibere più lunghe dei provvedimenti GPDP)
- **Tag MCP**: `"consob"` — incluso nei profili `"fiscale"` e `"normativa"`

## CeRDEF — note tecniche

- **Sito**: `https://def.finanze.it/DocTribFrontend/`
- **Ricerca**: POST a `executeAdvancedGiurisprudenzaSearch.do` con form params
- **Risultati**: XML embeddato in `var xmlResult = '...'` nella pagina HTML (richiede unescape `\/`, `\uXXXX`)
- **Dettaglio**: GET a `getGiurisprudenzaDetail.do?id={GUID}` → XML in `var xmlDettaglio`
- **Paginazione**: session cookie-based (`paginatorXml.do?paginaRichiesta=N`), max 250 risultati
- **Autenticazione**: nessuna — API pubblica, SSL standard
- **Enti**: Corte Suprema di Cassazione, CGT I grado, CGT II grado
- **Criteri ricerca**: tutti (T), frase_esatta (E), almeno_uno (O), codice (C)
- **Max text**: 25000 caratteri
- **Tag MCP**: `"giurisprudenza"`, `"fiscale"` — inclusi nei profili `fiscale` e `normativa`

## Giustizia Amministrativa — note tecniche

- **Sito**: `https://www.giustizia-amministrativa.it`
- **Framework**: Liferay Portal (stesso di CONSOB) — portlet `decisioni_pareri_web_WAR_decisioni_pareri_webportlet`
- **CSRF**: `p_auth` token da estrarre con GET iniziale (input hidden o form action URL)
- **Risultati**: HTML `<article class="ricerca--item">` con attributi `data-sede`, `data-nrg`, `nomeFile`
- **Testo completo**: sottodominio `mdp.giustizia-amministrativa.it` — XML strutturato `<GA>` con `<epigrafe>`, `<motivazione>`, `<dispositivo>`
- **SSL**: `verify=False` necessario (come Italgiure)
- **Sedi**: 28 (CdS, CGARS, tutti i TAR regionali)
- **Max text**: 15000 caratteri (motivazioni CdS molto lunghe)
- **Tag MCP**: `"giurisprudenza_amm"`, `"normativa"`

## CGUE — note tecniche

- **Metadati**: SPARQL endpoint `https://publications.europa.eu/webapi/rdf/sparql` (POST, JSON response)
- **Ontologia**: CDM (`http://publications.europa.eu/ontology/cdm#`) — FRBR-compliant
- **Testo completo**: content negotiation su URI CELLAR expression (`Accept: text/html`) — bypassa WAF EUR-Lex
- **CELEX case law**: `6{anno}{codice_corte}{numero}` (es. `62024CJ0008` = sentenza CdG, causa C-8/2024)
- **Codici corte**: `CJ` (sentenza CdG), `CC` (ordinanza CdG), `CO` (conclusioni AG), `TJ` (sentenza Tribunale), `TO` (ordinanza Tribunale)
- **ECLI**: `ECLI:EU:C:YYYY:NNN` (Corte) o `ECLI:EU:T:YYYY:NNN` (Tribunale)
- **Titolo IT**: expression con lingua ITA, separatore `#` o `##` tra header/parti/materia
- **IMPORTANTE**: CELEX literals in SPARQL richiedono `^^xsd:string` type annotation
- **Autenticazione**: nessuna — endpoint pubblico
- **Max text**: 25000 caratteri
- **Tag MCP**: `"giurisprudenza_ue"`, `"normativa"`

## Workflow CeRDEF → Italgiure

```
cerca_giurisprudenza_tributaria("IVA soggettività passiva")
  └─> [ProvvedimentoResult(guid="abc-123", estremi="Sent. n. 1234/2024", ente="Corte Suprema")]
  └─> cerdef_leggi_provvedimento("abc-123") ← massima + testo integrale
  └─> Se Cassazione: leggi_sentenza(1234, 2024) ← testo completo da Italgiure
```

## Workflow Giustizia Amministrativa

```
cerca_giurisprudenza_amministrativa("appalto pubblico esclusione")
  └─> [ProvvedimentoResult(sede="CDS", nrg="202301234", nome_file="202301234_11.xml")]
  └─> leggi_provvedimento_amm("CDS", "202301234", "202301234_11.xml") ← testo completo da mdp
```

## Workflow CGUE

```
cerca_giurisprudenza_cgue("imposta sul valore aggiunto")
  └─> [CaseResult(celex="62024CJ0008", case_number="C-8/2024", cellar_uri="http://...")]
  └─> leggi_sentenza_cgue("http://publications.europa.eu/resource/cellar/...") ← testo IT
  └─> cite_law("art. 168 direttiva 2006/112/CE") ← norma UE citata nella sentenza
```

## Docker

Il server supporta due transport: **stdio** (default, per Claude Desktop/Code) e **SSE** (HTTP, per deployment remoti).

### Env vars

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` o `sse` |
| `MCP_HOST` | `0.0.0.0` | Bind address (solo SSE) |
| `MCP_PORT` | `8000` | Porta (solo SSE) |
| `LEGAL_PROFILE` | `full` | Profilo tool da caricare (vedi tabella sotto) |
| `MCP_CACHE_DIR` | — | Directory cache Brocardi |

### Profili disponibili

| Profilo | Tag inclusi | Uso tipico |
|---------|------------|------------|
| `full` | tutti | Claude Code con Tool Search |
| `sinistro` | danni, rivalutazione, interessi, normativa, giurisprudenza, sinistro | Risarcimento danni |
| `credito` | interessi, rivalutazione, parcelle_avv, normativa, giurisprudenza, credito | Recupero crediti |
| `penale` | penale, normativa, giurisprudenza | Procedimenti penali |
| `fiscale` | fiscale, proprieta, utility, consob, investimenti | Consulenza fiscale |
| `normativa` | normativa, giurisprudenza, giurisprudenza_amm, giurisprudenza_ue, privacy, consob | Ricerca normativa |
| `privacy` | privacy, normativa, giurisprudenza | GDPR/Privacy |
| `studio` | scadenze, giudiziario, parcelle_avv, parcelle_prof, investimenti | Studio legale generico |
| `redattore` | atti, giudiziario, parcelle_avv, scadenze, normativa | Redazione atti giudiziari |

### Timeout HTTP differenziati

| Client | Timeout | Connect | Note |
|--------|---------|---------|------|
| Italgiure, CONSOB, GA | 30s | 10s | Standard |
| CeRDEF, CGUE | 45s | 15s | Endpoint più lenti |

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
