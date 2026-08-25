# mcp-legal-it — Project Context

> MCP server con 218 tool di calcolo legale italiano, consultazione normativa
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
| Framework MCP | FastMCP >= 2.0, < 4 (`@mcp.tool()`, `@mcp.prompt()`, `@mcp.resource()`) |
| HTTP client | httpx >= 0.27 (async) |
| HTML scraping | BeautifulSoup4 + lxml |
| PDF generation | fpdf2 |
| DOCX / XLSX | python-docx, openpyxl |
| Python | >= 3.10, venv in `.venv/` |
| Test | pytest + pytest-asyncio |

## Struttura

```
mcp-legal-it/
├── content/                    # sorgente unico skill/agent/command/reference — vedi scripts/corpus/
│   ├── skills/                 # 30 skill (frontmatter + blocco prompt:)
│   ├── agents/                 # 6 agenti
│   ├── commands/                # 8 comandi
│   ├── references/              # 12 delle 15 risorse legal:// (le altre 3 restano in resources.py)
│   ├── tool-vocabulary.json     # tassonomia tool usata dai generatori
│   └── targets.yaml             # manifest dei target di build (claude-code, claude-web, plugin-zip, mcpb)
├── scripts/
│   ├── build_targets.py         # builder unificato — sostituisce build-all.sh/build-plugin.sh/build-dxt.sh/build-web-skills.py
│   └── corpus/                  # generatori: project_claude.py, generate_prompts.py, extract_references.py, migrate_corpus.py, dump_vocabulary.py
├── plugin/
│   ├── skills/                  # GENERATED — proiezione di content/skills/ (project_claude.py)
│   ├── agents/                  # GENERATED — proiezione di content/agents/ (project_claude.py)
│   └── commands/                 # GENERATED — proiezione di content/commands/ (project_claude.py)
├── src/
│   ├── server.py              # FastMCP entry point — registra tutti i tool
│   ├── prompts.py             # GENERATED — 23 prompt dal corpus (scripts/corpus/generate_prompts.py)
│   ├── resources.py           # 15 risorse statiche (@mcp.resource)
│   ├── data/
│   │   └── references/        # GENERATED — copiato da content/references/ (project_claude.py)
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
│   │   ├── cgue/              # Client CGUE (CELLAR SPARQL + EUR-Lex)
│   │   │   └── client.py      # search_giurisprudenza(), fetch_sentenza_text(), format_*()
│   │   ├── corte_cost/        # Client Corte Costituzionale
│   │   │   └── client.py      # search_pronunce(), fetch_pronuncia(), format_*()
│   │   ├── gazzetta/          # Client Gazzetta Ufficiale (ricerca + RSS)
│   │   │   └── client.py      # search_atti(), fetch_atto(), sommario(), format_*()
│   │   ├── gpdp/              # Client Garante Privacy (Liferay scraper)
│   │   │   └── client.py      # search_provvedimenti(), fetch_provvedimento(), format_*()
│   │   ├── eu_implementation/ # Recepimento direttive UE -> Italia (EUR-Lex)
│   │   │   └── client.py      # get_national_measures(), format_*()
│   │   └── vies/              # Client VIES (validazione P.IVA UE)
│   │       └── client.py      # check_vat(), checksum_partita_iva()
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
│       ├── gazzetta.py       # cerca_gazzetta_ufficiale, leggi_atto_gazzetta, sommario_gazzetta, ultime_gazzette, scarica_pdf_gazzetta
│       ├── corte_cost.py     # cerca_pronuncia_costituzionale, leggi_pronuncia_costituzionale, pronunce_cost_su_norma, ultime_pronunce_cost
│       ├── gpdp.py           # cerca_provvedimenti_garante, leggi_provvedimento_garante, ultimi_provvedimenti_garante
│       ├── orientamento.py   # orientamento_su_norma, orientamento_su_principio, mappa_orientamento
│       ├── eu_implementation.py      # get_italian_implementation, get_eu_basis, elenco_misure_nazionali
│       ├── giurisprudenza_unificata.py # cerca_giurisprudenza_unificata
│       ├── diritto_lavoro.py         # licenziamento, preavviso, NASpI, costo lavoro
│       ├── diritto_societario.py     # quorum, soglie organo di controllo, scadenze societarie
│       ├── crisi_impresa.py          # test crisi, composizione negoziata, concordato, compenso OCC
│       ├── procedura_civile.py       # competenza_giudice, mediazione obbligatoria, gratuito patrocinio
│       ├── modelli_atti.py           # genera_modello_atto, esporta_atto_docx, lista_categorie_atti
│       ├── privacy_gdpr.py
│       ├── procure_quotazioni.py  # genera_procura_liti_docx, genera_quotazione_docx
│       └── analisi_fornitori.py   # verifica_partita_iva_vies, genera_report_fornitori
└── tests/                     # 76 file (46 unit + 30 comparison); per il conteggio
                               # corrente: pytest tests/ --collect-only -q | tail -1
    ├── unit/                  # mock HTTP, nessuna connessione esterna
    │   └── test_<modulo>.py   # un file per modulo tool o lib
    └── comparison/            # valori numerici attesi, senza mock
        └── test_privacy_docs.py
```

## Tool disponibili (32 moduli, 218 tool)

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
1. Rivalutazione monetaria (12 tool) — ISTAT, TFR, canoni
2. Interessi e tassi (10 tool) — legali, mora, TAEG, ammortamento
3. Scadenze processuali (11 tool) — Cartabia, impugnazioni, esecuzioni
4. Atti giudiziari (23 tool) — contributo unificato, pignoramento, decreto ingiuntivo
5. Parcelle avvocati (12 tool) — D.M. 55/2014, civile, penale, stragiudiziale
6. Parcelle professionisti (11 tool) — CTU, mediazione, compenso orario
7. Risarcimento danni (7 tool) — biologico micro/macro, parentale, INAIL
8. Diritto penale (5 tool) — pena, prescrizione, conversione
9. Proprietà e successioni (12 tool) — eredità, IMU, usufrutto
10. Investimenti (5 tool) — BOT, BTP, buoni postali
11. Dichiarazione redditi (16 tool) — IRPEF, regime forfettario, TFR
12. Varie (12 tool) — codice fiscale, IBAN, ATECO, prescrizione diritti
13. Privacy/GDPR (12 tool) — informative privacy, cookie, DPA, DPIA, data breach, sanzioni
14. Recupero crediti seriale (2 tool) — `genera_procura_liti_docx` (procura art. 83 c.p.c. DOCX pronta-firma), `genera_quotazione_docx` (lettera quotazione D.M. 55/2014: monitorio fase unica / esecuzione / opposizione, con accettazione cliente)
15. Analisi fornitori (2 tool) — `verifica_partita_iva_vies` (VIES), `genera_report_fornitori` (Excel standard screening privacy mastrino)
16. Diritto del lavoro (6 tool) — licenziamento, preavviso, NASpI, costo del lavoro, offerta conciliativa
17. Diritto societario (4 tool) — quorum assembleari, soglie organo di controllo SRL, scadenze societarie, costi di costituzione
18. Crisi d'impresa (4 tool) — test indicatori (art. 3 CCII), composizione negoziata, concordato preventivo, compenso OCC
19. Procedura civile (3 tool) — competenza per valore e materia, mediazione obbligatoria, gratuito patrocinio
20. Modelli di atti (3 tool) — `genera_modello_atto`, `esporta_atto_docx`, `lista_categorie_atti` (100 tipi di atti)

Consultazione e ricerca, oltre alle tabelle sopra: Gazzetta Ufficiale (5),
Corte Costituzionale (4), Garante Privacy (3), orientamenti giurisprudenziali (3),
recepimento UE→IT (3), ricerca giurisprudenziale unificata (1).

Elenco completo e verificato dei 218 tool, con firma e descrizione: `docs/tools-catalog.md`.

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
| `verifica_partita_iva_vies(partita_iva, codice_paese?)` | Verifica P.IVA sul VIES: validità + denominazione/indirizzo registrati |
| `genera_report_fornitori(fornitori, cliente, ...)` | Excel standard dell'analisi privacy del mastrino fornitori (11 colonne + Avvertenze) |

## Prompt guidati (23)

- `analisi_sinistro` — danno biologico + rivalutazione + interessi
- `recupero_credito` — interessi mora + decreto ingiuntivo + parcella
- `causa_civile` — contributo unificato + scadenze + preventivo
- `pianificazione_successione` — quote + imposte + adempimenti
- `parere_legale` — struttura rigorosa con cite_law obbligatorio
- `quantificazione_danni` — personalizzazione + attualizzazione
- `calcolo_parcella` — D.M. 55/2014 per attività civile/penale/stragiudiziale
- `verifica_prescrizione` — civile (artt. 2941-2946 c.c.) e penale
- `ricerca_normativa` — fonti primarie + norme collegate + giurisprudenza + CONSOB per settore finanziario
- `ricerca_gazzetta` — atti in Gazzetta Ufficiale: novità per serie, ricerca parametrica, testo as-published + PDF ufficiale
- `analisi_articolo` — testo vigente + ratio + massime + norme collegate
- `confronto_norme` — specialità, gerarchia, coordinamento
- `mappatura_normativa` — mappa completa per settore/attività + fonti autorità vigilanza
- `attuazione_direttiva` — recepimento direttiva UE: atto italiano di attuazione (Normattiva) + giurisprudenza CGUE collegata
- `analisi_giurisprudenziale` — workflow: cerca_giurisprudenza → leggi_sentenza → cite_law → sintesi
- `orientamento_giurisprudenziale` — mappa descrittiva orientamenti di legittimità: conformi vs contrasti, Sezioni Unite, evoluzione temporale
- `analisi_tributaria` — workflow: cerca_giurisprudenza_tributaria → cerdef_leggi_provvedimento → cite_law
- `analisi_giurisprudenza_amministrativa` — workflow: cerca_giurisprudenza_amministrativa → leggi_provvedimento_amm → cite_law
- `analisi_giurisprudenza_europea` — workflow: cerca_giurisprudenza_cgue → leggi_sentenza_cgue → cite_law
- `analisi_costituzionale` — workflow: cerca_pronuncia_costituzionale → leggi_pronuncia_costituzionale → cite_law, con parametri costituzionali invocati
- `compliance_privacy` — workflow GDPR: base giuridica → DPIA → registro → informativa → DPA
- `analisi_delibere_consob` — ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, normativa
- `novita_consob` — ultime delibere CONSOB con sintesi orientamenti per tipologia/argomento

## Risorse statiche (legal://) — 15

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
- `legal://riferimenti/ricerca-giurisprudenziale` — guida Italgiure: strategia esplora→filtra→leggi, sintassi Solr, facets
- `legal://riferimenti/cerdef-giurisprudenza` — guida CeRDEF: enti, criteri di ricerca, norme fiscali principali
- `legal://riferimenti/modelli-atti-catalogo` — catalogo 100 tipi di atti generabili: routing, tool, resource e campi obbligatori
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

## Risoluzione degli estremi normativi — note tecniche

`cite_law()` e i tool che condividono il resolver (`giurisprudenza_su_norma`,
`orientamento_su_norma`, `verifica_citazioni`, `cerca_brocardi`, `fetch_full_act`,
`download_law_pdf`) risolvono il nome dell'atto tramite `resolve_atto()` in
`src/lib/visualex/map.py`. La catena è, in ordine di affidabilità decrescente:

1. `ATTI_NOTI` — nomi comuni e sigle verificati a mano (GDPR, AI Act, TUB, TUF,
   TUIR, trattati UE, atti UE di compliance)
2. `NORMATTIVA_URN_CODICI` — i codici, tramite `extract_codice_details()`
3. `ATTI_DENOMINATI` — ~80 atti citati per nome (Statuto dei lavoratori, legge
   fallimentare, TUEL, TULPS, statuto del contribuente, eponimi come legge
   Gelli-Bianco o legge Cirinnà), ~200 alias
4. `NORMATTIVA_SEARCH` — abbreviazioni → nome esteso, poi di nuovo 1-3
5. pattern di citazione in `_resolve_act()` (`src/tools/legal_citations.py`) —
   forme `D.Lgs. 196/2003`, `legge n. 241 del 1990`, `regolamento (UE) 2016/679`,
   `direttiva 95/46/CE`

**L'ordine è deliberato**: le tabelle verificate a mano precedono `ATTI_DENOMINATI`,
la cui base è stata generata da `BROCARDI_CODICI`. Non invertirlo.

Ogni nome viene provato in più varianti (`_candidate_keys`): letterale, normalizzato,
senza articoli/preposizioni iniziali (`art. 111 della Costituzione`), e senza punti
se è un acronimo puntato (`t.u.e.l.` → `tuel`). La variante letterale è sempre la
prima, così la normalizzazione può solo aggiungere risoluzioni, mai cambiarne una.

**`ATTI_DENOMINATI` è dato, non codice generato**: `scripts/generate_atti_denominati.py`
ha prodotto la base una volta sola dagli estremi contenuti nelle chiavi di
`BROCARDI_CODICI`; la tabella committata è la fonte di verità, così un atto sbagliato
si corregge lì senza toccare una label di display. `--check` segnala gli atti Brocardi
che il resolver non sa gestire (deve restare a 94/94).

**Il gate contro il numero sbagliato è `tests/unit/test_atti_denominati_live.py`**
(marker `live`, escluso dalla run di default): interroga Normattiva su ogni atto
della tabella e verifica che data e numero dell'atto restituito coincidano, e
EUR-Lex/CELLAR su ogni CELEX degli atti UE. **Da lanciare prima di ogni release.**
Non intercetta un numero errato che cada su un atto della stessa data: quello lo
vede solo la lettura.

```bash
.venv/bin/pytest tests/unit/test_atti_denominati_live.py -m live -q
```

**`resolve_atto()` non tira mai a indovinare**: un nome non riconosciuto restituisce
`None` e i tool rispondono con un errore che elenca i nomi più vicini
(`_suggest_acts`, `difflib`). Citare l'atto sbagliato in silenzio è peggio che non
citarlo — non introdurre fuzzy matching che *risolve* invece di *suggerire*.

**Trattati UE**: `TUE`, `TFUE` e `CDFUE` hanno come URL citabile la pagina
eur-lex.europa.eu (in `EURLEX`), ma vanno **scaricati da CELLAR** per CELEX
(`EURLEX_TREATY_CELEX`): EUR-Lex risponde alle richieste automatiche con una sfida
WAF (HTTP 202 e corpo vuoto). Vedi `_eurlex_urls()` in `scraper.py`.

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

> **Portale riorganizzato nel 2026 (issue #32)** — il vecchio path
> `/web/guest/-/ricerca-giurisprudenza` risponde 404 e il vecchio path del testo
> integrale `/mdp/atti/<file>` risponde **200 con una pagina di errore HTML**.
> I test unitari precedenti usavano fixture inventate e non hanno intercettato la
> rottura: le fixture attuali sono copie del markup reale e i test `@pytest.mark.live`
> in `tests/unit/test_giustizia_amm.py` sono il guard-rail contro il prossimo spostamento.

- **Sito**: `https://www.giustizia-amministrativa.it`
- **Ricerca**: `/web/guest/dcsnprr` — POST all'`action` del form `provvedimentiForm`
- **Framework**: Liferay Portal (stesso di CONSOB) — portlet `decisioni_pareri_web_DecisioniPareriWebPortlet_INSTANCE_<hash>`.
  L'id contiene un hash d'istanza che può cambiare: viene **letto a runtime** dalla pagina
  (`_extract_portlet_id`), la costante nel client è solo fallback
- **CSRF**: `p_auth` token nell'URL dell'`action` del form (o input hidden). Il client
  riusa l'action verbatim, così un rename di lifecycle/action continua a funzionare
- **Parametri**: `searchtextProvvedimenti` (query), `sedeProvvedimenti`, `TipoProvvedimentoItem`,
  `pageSize`, `numeroProvvedimenti`. Vanno inviati **tutti** i campi del form
- **Sedi sul filo**: nomi di città (`Roma`, `Milano`), non più codici (`TARLAZ`).
  `SEDI` mappa le chiavi parlanti → città; `_LEGACY_SEDE_CODES` accetta ancora i vecchi codici
- **Filtro anno**: non esiste più lato server se non abbinato al numero
  (`numeroProvvedimenti` = `YYYYNNNNN`, es. `202301234`). Da solo è applicato client-side
- **Risultati**: `<article class="ricerca--item">`; gli attributi `data-sede`/`data-nrg` stanno
  su un `<a>` **interno**, non sull'article. Il footer di paginazione ha la stessa classe ma
  nessun link: richiedere il link lo esclude
- **Testo completo**: `mdp.giustizia-amministrativa.it/visualizza/?schema=<code>&nrg=<nrg>&nomeFile=<file>&subDir=Provvedimenti`
- **Formato**: XML `<GA><Provvedimento>` — le sezioni sono **annidate**, quindi serve `.//`;
  il corpo spesso sta in `<premessa>` (non `<motivazione>`, che può essere vuota) e il testo
  è dentro `<div>` HTML namespaced → estrarre con `itertext()`. Ignorare le varianti `*Ted` (bilingue Bolzano)
- **URL stantii**: rispondono 200 con HTML "404 - Pagina non trovata" → `_is_error_page()`
- **SSL**: `verify=False` nel client — **non più necessario**: dal 2026-08 entrambi i domini
  presentano certificati validi (verificato). Rimuoverlo è un miglioramento di sicurezza pendente
- **Sedi**: 31 (CdS, CGARS, tutti i TAR incl. sezioni staccate Latina/Brescia/Parma)
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

## Setup per provider

Il server MCP supporta tre transport e funziona con Claude, ChatGPT e Manus.

### Compatibilità cross-provider

| Feature | Claude Desktop/Code | ChatGPT | Manus |
|---------|--------------------:|--------:|------:|
| 218 tool di calcolo e ricerca | ✓ | ✓ | ✓ |
| 23 prompt guidati | ✓ | — | — |
| 15 risorse `legal://` | ✓ | — | — |
| 30 skills + 8 comandi + 6 agenti | ✓ (plugin) | — | — |
| Transport stdio (locale) | ✓ | — | — |
| Transport Streamable HTTP | ✓ | ✓ | ✓ |
| Transport SSE (legacy) | ✓ | ✓ | ? |

> I 218 tool funzionano su tutti i provider. Prompt, risorse e plugin (skills/comandi/agenti)
> sono feature Claude-only — gli altri provider li ignorano silenziosamente.

---

### Setup 1 — Claude Desktop (locale, stdio)

Il modo più semplice. Il server gira come subprocess locale, nessun Docker necessario.

**Prerequisito unico: `uv`** (gestisce automaticamente Python 3.12 e le dipendenze,
identico su Windows/macOS/Linux — niente più problemi di `bash`/percorsi venv/Python troppo recente):
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Riavvia il client dopo l'installazione di `uv`. Il primo avvio del server scarica Python 3.12 +
le dipendenze (~1 min); gli avvii successivi sono immediati (cache di `uv`).

**Opzione A — Plugin marketplace (consigliato)**
```
/plugin marketplace add capazme/mcp-legal-it
/plugin install legal-it@mcp-legal-it
```
Include: 218 tool + skills + comandi + agenti + hooks. Il server MCP parte via `uv` (vedi `plugin/.mcp.json`).

**Opzione B — Desktop Extension (.mcpb)**

Scaricare `legal-it-X.Y.Z.mcpb` dalla [GitHub Release](https://github.com/capazme/mcp-legal-it/releases/latest) → doppio click su Mac.

**Opzione C — Configurazione manuale**

In `~/Library/Application Support/Claude/claude_desktop_config.json` (richiede `uv`):
```json
{
  "mcpServers": {
    "legal-it": {
      "command": "uv",
      "args": [
        "run", "--python", "3.12",
        "--with", "fastmcp>=2.0,<4", "--with", "httpx>=0.27",
        "--with", "beautifulsoup4>=4.12", "--with", "lxml>=5.0",
        "--with", "fpdf2>=2.7", "--with", "python-docx>=1.0", "--with", "openpyxl>=3.1",
        "/path/to/mcp-legal-it/plugin/server/run_server.py"
      ]
    }
  }
}
```

---

### Setup 2 — Claude Code (locale, stdio)

**Opzione A — Plugin marketplace**
```bash
/plugin marketplace add capazme/mcp-legal-it
/plugin install legal-it@mcp-legal-it
```

**Opzione B — .mcp.json nel progetto** (richiede `uv`)

Creare `.mcp.json` nella root del progetto:
```json
{
  "mcpServers": {
    "legal-it": {
      "command": "uv",
      "args": [
        "run", "--python", "3.12",
        "--with", "fastmcp>=2.0,<4", "--with", "httpx>=0.27",
        "--with", "beautifulsoup4>=4.12", "--with", "lxml>=5.0",
        "--with", "fpdf2>=2.7", "--with", "python-docx>=1.0", "--with", "openpyxl>=3.1",
        "/path/to/mcp-legal-it/plugin/server/run_server.py"
      ]
    }
  }
}
```

---

### Setup 3 — ChatGPT (remoto, HTTPS obbligatorio)

ChatGPT richiede un endpoint HTTPS pubblico. Due opzioni:

**Opzione A — Server remoto (produzione)**

1. Deployare il server su un host con HTTPS (VPS, Cloud Run, Railway, ecc.):
   ```bash
   docker run -p 8000:8000 mcp-legal-it
   # oppure: docker compose up
   ```
2. Configurare un reverse proxy HTTPS (nginx, Caddy) davanti alla porta 8000.
3. In ChatGPT:
   ```
   Settings → Apps → Developer Mode → Create
   Nome: Legal IT
   URL:  https://tuo-server.example.com/mcp
   ```

**Opzione B — Tunnel locale (sviluppo)**

1. Avviare il server localmente:
   ```bash
   MCP_TRANSPORT=http python run_server.py
   ```
2. Creare un tunnel HTTPS:
   ```bash
   ngrok http 8000
   # oppure: cloudflared tunnel --url http://localhost:8000
   ```
3. In ChatGPT:
   ```
   Settings → Apps → Developer Mode → Create
   Nome: Legal IT
   URL:  https://xxxx.ngrok-free.app/mcp
   ```

> **Nota**: ChatGPT non supporta prompt MCP né risorse. Solo i 218 tool sono visibili.

---

### Setup 4 — Manus (remoto, HTTPS obbligatorio)

Stessa architettura di ChatGPT — serve un endpoint HTTPS pubblico.

1. Deployare il server (vedi Setup 3, Opzione A).
2. In Manus:
   ```
   Settings → Integrations → Custom MCP Servers → Add Server
   Nome:  Legal IT
   URL:   https://tuo-server.example.com/mcp
   Auth:  (nessuna — l'API è pubblica)
   ```

> **Nota**: Manus ha timeout brevi. I tool che interrogano siti governativi lenti
> (Italgiure, CeRDEF) potrebbero andare in timeout su Manus.

---

### Setup 5 — Qualsiasi client MCP (Streamable HTTP)

Per qualsiasi client MCP compatibile con il transport Streamable HTTP:

```bash
# Avviare il server
MCP_TRANSPORT=http MCP_PORT=8000 python run_server.py

# Endpoint: http://localhost:8000/mcp (POST)
```

Configurazione generica per il client:
```json
{
  "url": "http://localhost:8000/mcp",
  "transport": "streamable-http"
}
```

---

## Docker

### Env vars

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio`, `http` (Streamable HTTP) o `sse` (legacy) |
| `MCP_HOST` | `0.0.0.0` | Bind address (solo http/sse) |
| `MCP_PORT` | `8000` | Porta (solo http/sse) |
| `MCP_PATH` | `/mcp` | Path endpoint (solo http) |
| `LEGAL_PROFILE` | `full` | Profilo tool da caricare (vedi tabella sotto) |
| `MCP_CACHE_DIR` | — | Directory cache Brocardi |

### Comandi

```bash
# Build
docker build -t mcp-legal-it .

# Run Streamable HTTP (default Docker, porta 8000)
docker run -p 8000:8000 mcp-legal-it

# Run con docker-compose
docker compose up

# Run con profilo ridotto
docker run -p 8000:8000 -e LEGAL_PROFILE=fiscale mcp-legal-it

# Run legacy SSE (retrocompatibilità)
docker run -p 8000:8000 -e MCP_TRANSPORT=sse mcp-legal-it
```

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
| `cowork` | normativa, giurisprudenza, privacy, parcelle_avv | Sessioni Cowork (set ridotto) |

### Timeout HTTP differenziati

| Client | Timeout | Connect | Note |
|--------|---------|---------|------|
| Italgiure, CONSOB, GA | 30s | 10s | Standard |
| CeRDEF, CGUE | 45s | 15s | Endpoint più lenti |
