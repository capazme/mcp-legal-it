# mcp-legal-it — Documentazione

MCP server con 218 tool di calcolo e consultazione per il diritto italiano.
Copre calcoli numerici (danni, interessi, fiscale, parcelle), consultazione normativa
(Normattiva, EUR-Lex, Brocardi, Gazzetta Ufficiale) e ricerca giurisprudenziale
(Cassazione, Corte Costituzionale, tributaria, TAR/CdS, CGUE, Garante Privacy, CONSOB).

---

## Indice

- [Architettura](#architettura)
- [Stack tecnologico](#stack-tecnologico)
- [Indice documenti](#indice-documenti)
- [Quick start](#quick-start)

---

## Architettura

```
Client MCP (Claude Desktop / Claude Code)
        │
        │  protocollo MCP  (stdio o SSE)
        ▼
  run_server.py        Entry point — seleziona transport
        │
        ▼
  src/server.py        FastMCP — inizializzazione e profili
        │
        │  import a livello di modulo → registrazione @mcp.tool()
        ▼
  src/tools/           32 moduli tool (218 tool totali)
  │
  ├─ calcolo (16 moduli)
  │  ├── rivalutazioni_istat     ├── proprieta_successioni
  │  ├── tassi_interessi         ├── investimenti
  │  ├── scadenze_termini        ├── dichiarazione_redditi
  │  ├── atti_giudiziari         ├── varie
  │  ├── fatturazione_avvocati   ├── risarcimento_danni
  │  ├── parcelle_professionisti ├── diritto_penale
  │  ├── diritto_lavoro          ├── crisi_impresa
  │  ├── diritto_societario      └── procedura_civile
  │
  ├─ consultazione e ricerca (12 moduli)
  │  ├── legal_citations         ├── gazzetta
  │  ├── italgiure               ├── corte_cost
  │  ├── cerdef                  ├── giustizia_amm
  │  ├── cgue                    ├── consob
  │  ├── gpdp                    ├── orientamento
  │  └── eu_implementation       └── giurisprudenza_unificata
  │
  └─ documenti e compliance (4 moduli)
     ├── privacy_gdpr            ├── modelli_atti
     ├── procure_quotazioni      └── analisi_fornitori
        │
        │  chiamate HTTP async (httpx)
        ▼
  src/lib/             12 client HTTP e parser
  ├── visualex/        Normattiva + EUR-Lex
  ├── brocardi/        scraper standalone Brocardi
  ├── italgiure/       Solr API Cassazione
  ├── corte_cost/      Corte Costituzionale
  ├── cerdef/          giurisprudenza tributaria (MEF)
  ├── giustizia_amm/   TAR e Consiglio di Stato
  ├── cgue/            CELLAR SPARQL (Corte di Giustizia UE)
  ├── gpdp/            scraping Garante Privacy
  ├── consob/          bollettino delibere CONSOB
  ├── gazzetta/        Gazzetta Ufficiale
  ├── eu_implementation/ recepimento direttive UE → IT
  └── vies/            validazione P.IVA intracomunitaria
        │
        │  HTTPS
        ▼
  Fonti esterne ufficiali
  ├── normattiva.it                  testo vigente norme italiane
  ├── eur-lex.europa.eu              diritto europeo (GDPR, direttive)
  ├── gazzettaufficiale.it           atti pubblicati in GU
  ├── brocardi.it                    dottrina e massime strutturate
  ├── italgiure.giustizia.it         sentenze Cassazione (Solr)
  ├── cortecostituzionale.it         pronunce della Consulta
  ├── def.finanze.it                 giurisprudenza tributaria (CeRDEF)
  ├── giustizia-amministrativa.it    TAR e Consiglio di Stato
  ├── publications.europa.eu         CGUE via CELLAR SPARQL
  ├── garanteprivacy.it              provvedimenti Garante (Liferay)
  ├── consob.it                      bollettino delibere (Liferay)
  └── ec.europa.eu/taxation_customs  VIES (P.IVA UE)
```

---

## Stack tecnologico

Fonte: `pyproject.toml` (`[project].dependencies`).

| Componente | Tecnologia | Versione |
|------------|-----------|---------|
| Framework MCP | FastMCP | >= 2.0, < 4 |
| HTTP client | httpx (async) | >= 0.27 |
| HTML parsing | BeautifulSoup4 + lxml | bs4 >= 4.12, lxml >= 5.0 |
| PDF generation | fpdf2 | >= 2.7 |
| DOCX generation | python-docx | >= 1.0 |
| XLSX generation | openpyxl | >= 3.1 |
| Runtime | Python | >= 3.10 |
| Test | pytest + pytest-asyncio | >= 7.0 / >= 0.21 |

Il vincolo superiore su `fastmcp` è deliberato: l'uscita di una major 4.x
romperebbe la registrazione dei tool senza preavviso.

---

## Indice documenti

| File | Descrizione |
|------|-------------|
| [architecture.md](architecture.md) | Dettaglio layer, pattern `_impl`, profili, come aggiungere tool |
| [tools-catalog.md](tools-catalog.md) | Catalogo dei 218 tool divisi per categoria |
| [strumenti.md](strumenti.md) | Scheda per tool con parametri ed esempi (copertura parziale, vedi nota nel file) |
| [lib-reference.md](lib-reference.md) | Reference delle librerie interne di `src/lib/` (12 moduli, 4 documentati in dettaglio) |
| [prompts-resources.md](prompts-resources.md) | 23 prompt guidati e 15 risorse statiche `legal://` |
| [plugin.md](plugin.md) | Plugin Claude Code: 30 skill, 8 slash command, 6 agenti, hook, installazione |
| [openai.md](openai.md) | Bundle OpenAI (Codex CLI / ChatGPT): 40 skill, AGENTS.md, config MCP, limiti |
| [data-files.md](data-files.md) | 24 file JSON dati: contenuto, fonte normativa, aggiornamento |
| [testing.md](testing.md) | Strategia test, comandi, copertura, come aggiungere test |
| [deployment.md](deployment.md) | install.py, setup manuale, Docker, variabili d'ambiente, troubleshooting |
| [specs/](specs/) | Design e piani delle feature (uno per feature, datati) |

---

## Quick start

### Installazione automatica

```bash
git clone <repo> mcp-legal-it
cd mcp-legal-it
python3 install.py
```

`install.py` crea il virtual environment, installa le dipendenze, configura Claude Desktop
e/o Claude Code, e verifica che il server si avvii correttamente.

Per le opzioni avanzate (flag CLI, Docker, configurazione manuale) vedere
[deployment.md](deployment.md).

### Verifica rapida

```bash
# Avvia il server in stdio (per test)
.venv/bin/python run_server.py

# Conta i tool registrati
.venv/bin/python -c "import asyncio; from src.server import mcp; print(len(asyncio.run(mcp.list_tools())))"
```

### Test

```bash
# Unit test (nessuna connessione di rete)
.venv/bin/pytest tests/unit/ -v

# Tutti i test escluso live
.venv/bin/pytest tests/ -m "not live"
```
