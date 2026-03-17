<p align="center">
  <strong>mcp-legal-it</strong>
</p>

<p align="center">
  Server MCP + plugin per il diritto italiano
</p>

<p align="center">
  <a href="https://github.com/capazme/mcp-legal-it/releases"><img src="https://img.shields.io/github/v/release/capazme/mcp-legal-it?style=flat-square" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-3776ab?style=flat-square" alt="Python">
  <a href="https://github.com/capazme/mcp-legal-it/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/capazme/mcp-legal-it/ci.yml?branch=develop&style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/tool-166-green?style=flat-square" alt="Tools">
</p>

---

## Cos'e mcp-legal-it

Un avvocato che usa Claude non dovrebbe cercare manualmente testi di legge, ricalcolare interessi o compilare informative privacy a mano. **mcp-legal-it** e un server [Model Context Protocol](https://modelcontextprotocol.io/) che mette a disposizione **166 tool** di calcolo legale, consultazione normativa, ricerca giurisprudenziale e compliance — tutti accessibili direttamente da Claude.

- **Normativa verificata** — testi vigenti da Normattiva, EUR-Lex e Brocardi (no allucinazioni)
- **Giurisprudenza Cassazione** — ricerca full-text e testo sentenze da Italgiure
- **Delibere CONSOB** — ricerca e testo integrale dal Bollettino ufficiale
- **Calcoli giuridici** — interessi, rivalutazione ISTAT, parcelle, contributo unificato, IRPEF, successioni, danni e altro
- **GDPR compliance** — informative, DPIA, DPA, registro trattamenti, data breach, sanzioni
- **19 skill + 5 agenti** — workflow guidati per pareri, cause civili, sinistri, recupero crediti
- **Legal Grounding Protocol** — hook che verificano che ogni norma citata sia supportata da `cite_law()`

---

## Installazione

### Claude Desktop (Cowork) — consigliato

1. Apri Claude Desktop &rarr; **Personalizza** &rarr; **+**
2. **Aggiungi marketplace da GitHub** &rarr; `capazme/mcp-legal-it`
3. Installa il plugin **legal-it**

### Claude Code CLI

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
```

### Docker

```bash
docker build -t mcp-legal-it .
docker run -p 8000:8000 mcp-legal-it    # SSE su porta 8000
```

Client MCP:

```json
{
  "mcpServers": {
    "legal-it": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Manuale (sviluppatori)

```bash
git clone https://github.com/capazme/mcp-legal-it
cd mcp-legal-it
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Configurazione in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "legal-it": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/mcp-legal-it/run_server.py"]
    }
  }
}
```

---

## Tool disponibili — 166 tool, 16 categorie

| # | Categoria | Tool | Esempi |
|---|-----------|:----:|--------|
| 1 | Consultazione Normativa | 5 | `cite_law`, `cerca_brocardi`, `download_law_pdf` |
| 2 | Giurisprudenza Cassazione | 4 | `leggi_sentenza`, `cerca_giurisprudenza`, `ultime_pronunce` |
| 3 | Delibere CONSOB | 3 | `cerca_delibere_consob`, `leggi_delibera_consob` |
| 4 | Privacy/GDPR | 12 | `genera_informativa_privacy`, `genera_dpia`, `valutazione_data_breach` |
| 5 | Provvedimenti Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante` |
| 6 | Rivalutazione Monetaria | 11 | `rivalutazione_monetaria`, `adeguamento_canone_locazione` |
| 7 | Interessi e Tassi | 10 | `interessi_legali`, `interessi_mora`, `verifica_usura` |
| 8 | Scadenze e Termini | 11 | `scadenza_processuale`, `termini_memorie_repliche` |
| 9 | Atti Giudiziari | 15 | `contributo_unificato`, `decreto_ingiuntivo`, `pignoramento_stipendio` |
| 10 | Parcelle Avvocati | 11 | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| 11 | Parcelle Professionisti | 11 | `compenso_ctu`, `spese_mediazione` |
| 12 | Risarcimento Danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| 13 | Diritto Penale | 5 | `prescrizione_reato`, `aumenti_riduzioni_pena` |
| 14 | Proprieta e Successioni | 11 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| 15 | Investimenti e Fiscalita | 19 | `calcolo_irpef`, `regime_forfettario`, `rendimento_btp` |
| 16 | Utilita | 12 | `codice_fiscale`, `verifica_iban`, `prescrizione_diritti` |

---

## Skill, Command, Agenti

### Skill — 19 workflow guidati

Invocabili con `/legal-it:<nome>` o attivati automaticamente da Claude.

| Skill | Descrizione |
|-------|-------------|
| `parere-legale` | Parere strutturato con citazioni verificate |
| `analisi-articolo` | Analisi approfondita di un articolo di legge |
| `analisi-giurisprudenziale` | Ricerca e sintesi orientamenti giurisprudenziali |
| `recupero-credito` | Interessi mora + decreto ingiuntivo + parcella |
| `analisi-sinistro` | Quantificazione danni da sinistro con rivalutazione |
| `causa-civile` | Pianificazione causa: costi, scadenze, preventivo |
| `pianificazione-successione` | Quote ereditarie, imposte, adempimenti |
| `quantificazione-danni` | Calcolo danno biologico/patrimoniale/morale |
| `calcolo-parcella` | Parcella avvocato D.M. 55/2014 |
| `verifica-prescrizione` | Prescrizione civile o penale |
| `ricerca-normativa` | Ricerca normativa completa su un tema |
| `confronto-norme` | Confronto tra norme: prevalenza, coordinamento |
| `mappatura-normativa` | Mappa normativa per settore/attivita |
| `compliance-privacy` | Assessment GDPR completo |
| `data-breach` | Gestione data breach: valutazione + notifica |
| `redazione-contratto` | Supporto redazione contrattuale |
| `genera-atto` | Generazione atti giudiziari (100 modelli) |
| `analisi-delibere-consob` | Ricerca e analisi delibere CONSOB |
| `novita-consob` | Ultime delibere CONSOB |

### Slash command — 8

| Comando | Descrizione |
|---------|-------------|
| `/legal-it:norma` | Cerca e cita una norma |
| `/legal-it:sentenza` | Leggi una sentenza di Cassazione |
| `/legal-it:ricerca` | Ricerca giurisprudenziale full-text |
| `/legal-it:interessi` | Calcolo interessi legali o di mora |
| `/legal-it:parcella` | Calcolo parcella avvocato |
| `/legal-it:codice-fiscale` | Calcolo o decodifica codice fiscale |
| `/legal-it:scadenza` | Calcolo scadenza processuale |
| `/legal-it:privacy` | Genera informativa privacy |

### Agenti — 5 specialisti

| Agente | Specializzazione |
|--------|------------------|
| `civilista` | Contratti, responsabilita, successioni, obbligazioni, famiglia |
| `penalista` | Reati, pene, prescrizione, misure cautelari |
| `privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante |
| `redattore-atti` | Redazione atti giudiziari e stragiudiziali |
| `ricerca-giurisprudenziale` | Ricerca sistematica su Italgiure |

---

## Legal Grounding Protocol

Il plugin include hook che garantiscono l'accuratezza delle citazioni normative:

- **Stop hook** — verifica che ogni norma citata nella risposta abbia un `cite_law()` corrispondente
- **SessionStart hook** — dopo compaction, ricorda il protocollo di citazione

**Regole per l'LLM**:

| Situazione | Azione |
|------------|--------|
| Citare una norma | `cite_law()` per il testo vigente |
| Sentenza con numero noto | `leggi_sentenza()` diretto |
| Sentenza senza numero | `cerca_giurisprudenza()` poi `leggi_sentenza()` |
| Tool di calcolo | Incorporano le norme — non richiedono `cite_law` |

---

## Configurazione

### Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` o `sse` |
| `MCP_HOST` | `0.0.0.0` | Bind address (solo SSE) |
| `MCP_PORT` | `8000` | Porta (solo SSE) |
| `LEGAL_PROFILE` | `full` | Profilo tool da caricare |
| `MCP_CACHE_DIR` | — | Directory cache Brocardi |

### Profili disponibili

| Profilo | Tool caricati |
|---------|---------------|
| `full` | Tutti i 166 tool |
| `calcoli` | Solo tool di calcolo (nessuna connessione HTTP) |
| `normativa` | Normattiva + EUR-Lex + Brocardi + Italgiure + CONSOB |
| `fiscale` | Calcoli fiscali + IRPEF + investimenti + CONSOB |
| `privacy` | Tool GDPR/Privacy + Garante |

---

## Sviluppo

```bash
git clone https://github.com/capazme/mcp-legal-it
cd mcp-legal-it
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -m "not live"
```

Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per la guida completa allo sviluppo.

---

## Contributing

Contributi benvenuti! Leggi [CONTRIBUTING.md](CONTRIBUTING.md) per i dettagli su:

- Come aggiungere un nuovo tool (calcolo o con HTTP)
- Pattern `_impl` + wrapper per la testabilita
- Convenzioni di output (importi, date, precisione)
- Checklist pre-PR

---

## Licenza

[Apache License 2.0](LICENSE) — Copyright 2025-2026 [capazme](https://github.com/capazme).

---

> I calcoli sono indicativi e non sostituiscono il parere di un professionista abilitato. Verificare sempre l'aggiornamento delle norme.
