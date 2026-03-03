# mcp-legal-it — Documentazione

MCP server con 161 tool di calcolo e consultazione per il diritto italiano.
Copre calcoli numerici (danni, interessi, fiscale, parcelle), consultazione normativa
(Normattiva, EUR-Lex, Brocardi) e ricerca giurisprudenziale (Italgiure/Cassazione).

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
  src/tools/           16 moduli tool (161 tool totali)
  ├── rivalutazioni_istat     ├── proprieta_successioni
  ├── tassi_interessi         ├── investimenti
  ├── scadenze_termini        ├── dichiarazione_redditi
  ├── atti_giudiziari         ├── varie
  ├── fatturazione_avvocati   ├── legal_citations
  ├── parcelle_professionisti ├── italgiure
  ├── risarcimento_danni      ├── gpdp
  ├── diritto_penale          └── privacy_gdpr
        │
        │  chiamate HTTP async (httpx)
        ▼
  src/lib/             4 client HTTP e parser
  ├── visualex/        Normattiva + EUR-Lex + Brocardi
  ├── italgiure/       Solr API Cassazione
  ├── brocardi/        scraper standalone Brocardi
  └── gpdp/            scraping Garante Privacy
        │
        │  HTTPS
        ▼
  Fonti esterne ufficiali
  ├── normattiva.it            testo vigente norme italiane
  ├── eur-lex.europa.eu        diritto europeo (GDPR, direttive)
  ├── brocardi.it              dottrina e massime strutturate
  ├── italgiure.giustizia.it   sentenze Cassazione (Solr)
  └── garanteprivacy.it        provvedimenti Garante (Liferay)
```

---

## Stack tecnologico

| Componente | Tecnologia | Versione |
|------------|-----------|---------|
| Framework MCP | FastMCP | >= 2.0.0 |
| HTTP client | httpx (async) | >= 0.27 |
| HTML parsing | BeautifulSoup4 + lxml | bs4 >= 4.12, lxml >= 5.0 |
| PDF generation | fpdf2 | >= 2.7 |
| Runtime | Python | >= 3.10 |
| Test | pytest + pytest-asyncio | >= 7.0 / >= 0.21 |

---

## Indice documenti

| File | Descrizione |
|------|-------------|
| [architecture.md](architecture.md) | Dettaglio layer, pattern `_impl`, profili, come aggiungere tool |
| [tools-catalog.md](tools-catalog.md) | Catalogo completo dei 161 tool divisi per 16 categorie |
| [lib-reference.md](lib-reference.md) | Reference delle 4 librerie interne (visualex, brocardi, italgiure, gpdp) |
| [prompts-resources.md](prompts-resources.md) | 13 prompt guidati e 9 risorse statiche `legal://` |
| [plugin.md](plugin.md) | Plugin Claude Code: 17 skill, 3 agenti, hook, installazione |
| [data-files.md](data-files.md) | 20 file JSON dati: contenuto, fonte normativa, aggiornamento |
| [testing.md](testing.md) | Strategia test, comandi, copertura, come aggiungere test |
| [deployment.md](deployment.md) | install.py, setup manuale, Docker, variabili d'ambiente, troubleshooting |

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
