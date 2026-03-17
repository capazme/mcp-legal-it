# mcp-legal-it

Server MCP + plugin per il diritto italiano: **166 tool** di calcolo giuridico-fiscale, consultazione normativa (Normattiva, EUR-Lex, Brocardi), giurisprudenza (Cassazione/Italgiure), delibere CONSOB, compliance GDPR, **19 skill**, **8 slash command**, **5 agenti specializzati** e **Legal Grounding Protocol**.

## Installazione

### Claude Desktop (Cowork) — consigliato

1. Apri Claude Desktop → **Personalizza** → **+**
2. **Aggiungi marketplace da GitHub** → `capazme/mcp-legal-it`
3. Installa il plugin **legal-it**

### Claude Code CLI

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
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

## Cosa include

### Tool MCP — 166 tool in 16 categorie

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

### Risorse statiche — 10

| URI | Contenuto |
|-----|-----------|
| `legal://riferimenti/procedura-civile` | Fasi procedura civile post-Cartabia |
| `legal://riferimenti/termini-processuali` | Quadro sinottico termini civili |
| `legal://riferimenti/contributo-unificato` | Scaglioni CU 2025 |
| `legal://riferimenti/irpef-detrazioni` | Scaglioni IRPEF 2025-2026 |
| `legal://riferimenti/interessi-legali` | Storico tassi 2000-2026 |
| `legal://riferimenti/checklist-decreto-ingiuntivo` | Checklist ricorso |
| `legal://riferimenti/fonti-diritto-italiano` | Gerarchia fonti + citazione |
| `legal://riferimenti/codici-e-leggi-principali` | Indice ragionato codici e leggi UE |
| `legal://riferimenti/gdpr-checklist` | Checklist compliance GDPR |
| `legal://riferimenti/consob-delibere` | Guida tool CONSOB |

---

## Legal Grounding Protocol

Il plugin include hook che garantiscono l'accuratezza delle citazioni:

- **Stop hook**: verifica che ogni norma citata abbia un `cite_law()` corrispondente
- **SessionStart hook**: dopo compaction, ricorda il protocollo di citazione

**Regole per l'LLM**:

- Prima di citare qualsiasi norma → `cite_law()` per il testo vigente
- Sentenza con numero noto → `leggi_sentenza()` diretto, no web search
- Sentenza senza numero → `cerca_giurisprudenza()` poi `leggi_sentenza()`
- I tool di calcolo incorporano le norme — non richiedono `cite_law`

---

## Sviluppo

```bash
# Setup
git clone https://github.com/capazme/mcp-legal-it
cd mcp-legal-it
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Test (senza connessione)
pytest tests/ -m "not live"

# Test live (richiedono internet)
pytest tests/ -m "live"
```

### Docker

```bash
docker build -t mcp-legal-it .
docker run -p 8000:8000 mcp-legal-it    # SSE su porta 8000
```

---

## Licenza

MIT — vedi [LICENSE](LICENSE).

I calcoli sono indicativi e non sostituiscono il parere di un professionista abilitato. Verificare sempre l'aggiornamento delle norme.
