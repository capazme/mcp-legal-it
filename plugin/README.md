# legal-it — Plugin Claude Code per il Diritto Italiano

Plugin legale italiano completo per Claude Code: **161 tool** di calcolo, consultazione normativa (Normattiva/EUR-Lex), giurisprudenza (Cassazione/Italgiure), compliance GDPR, **17 workflow guidati** e **3 agenti specializzati**.

## Installazione

```bash
claude plugin add gpuzio/mcp-legal-it
```

Oppure da path locale (per sviluppatori):

```bash
claude plugin add /path/to/mcp-legal-it/plugin
```

## Cosa include

### Server MCP (161 tool)

Il plugin si connette al server MCP `legal-it` via SSE — nessuna installazione Python richiesta. I tool coprono:

| Categoria | Tool | Esempi |
|-----------|------|--------|
| Normativa | 5 | `cite_law`, `cerca_brocardi`, `download_law_pdf` |
| Giurisprudenza | 4 | `leggi_sentenza`, `cerca_giurisprudenza` |
| Rivalutazione ISTAT | 11 | `rivalutazione_monetaria`, `adeguamento_canone_locazione` |
| Interessi e tassi | 10 | `interessi_legali`, `interessi_mora`, `calcolo_taeg` |
| Scadenze processuali | 11 | `scadenza_processuale`, `termini_memorie_repliche` |
| Atti giudiziari | 15 | `contributo_unificato`, `decreto_ingiuntivo`, `pignoramento_stipendio` |
| Parcelle avvocati | 11 | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| Parcelle professionisti | 11 | `compenso_ctu`, `spese_mediazione` |
| Risarcimento danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| Diritto penale | 5 | `prescrizione_reato`, `aumenti_riduzioni_pena` |
| Proprietà e successioni | 11 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| Investimenti | 5 | `rendimento_bot`, `rendimento_btp` |
| Dichiarazione redditi | 14 | `calcolo_irpef`, `regime_forfettario`, `calcolo_tfr` |
| Utilità | 12 | `codice_fiscale`, `verifica_iban`, `scorporo_iva` |
| Privacy/GDPR | 12 | `genera_informativa_privacy`, `genera_dpia`, `valutazione_data_breach` |
| Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante` |

### Skill (17 workflow guidati)

Invocabili con `/legal-it:<nome>`:

| Skill | Descrizione |
|-------|-------------|
| `/legal-it:parere-legale` | Parere legale strutturato con citazioni verificate |
| `/legal-it:analisi-norma` | Analisi approfondita di un articolo di legge |
| `/legal-it:analisi-giurisprudenziale` | Ricerca e sintesi orientamenti giurisprudenziali |
| `/legal-it:recupero-credito` | Workflow completo: interessi → decreto ingiuntivo → parcella |
| `/legal-it:sinistro` | Quantificazione danni da sinistro con rivalutazione |
| `/legal-it:causa-civile` | Pianificazione causa: costi, scadenze, preventivo |
| `/legal-it:pianificazione-successione` | Quote ereditarie, imposte, adempimenti |
| `/legal-it:quantificazione-danni` | Calcolo danno biologico/patrimoniale/morale |
| `/legal-it:calcolo-parcella` | Parcella avvocato con nota spese (D.M. 55/2014) |
| `/legal-it:verifica-prescrizione` | Verifica prescrizione civile o penale |
| `/legal-it:ricerca-normativa` | Ricerca normativa completa su un tema |
| `/legal-it:analisi-articolo` | Analisi singolo articolo: testo, ratio, giurisprudenza |
| `/legal-it:confronto-norme` | Confronto tra due+ norme: prevalenza, coordinamento |
| `/legal-it:mappatura-normativa` | Mappa normativa completa per settore/attività |
| `/legal-it:compliance-privacy` | Assessment GDPR: base giuridica → DPIA → registro → informativa |
| `/legal-it:data-breach` | Gestione data breach: valutazione → notifica → sanzioni |
| `/legal-it:redazione-contratto` | Supporto redazione contrattuale con verifica normativa |

### Agenti (3 specialisti)

Invocabili con `@legal-it:<nome>`:

| Agente | Specializzazione |
|--------|------------------|
| `@legal-it:civilista` | Contratti, responsabilità, successioni, diritti reali, obbligazioni, famiglia |
| `@legal-it:penalista` | Reati, pene, prescrizione, misure cautelari, riti alternativi |
| `@legal-it:privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante, ePrivacy |

### Hook (Legal Grounding Protocol)

Il plugin include due hook che garantiscono l'accuratezza delle citazioni normative:

- **Stop**: verifica che ogni norma citata nella risposta abbia un `cite_law()` corrispondente
- **SessionStart**: dopo compaction, ricorda il protocollo di citazione

## Configurazione avanzata

### Server locale (per sviluppatori)

Per usare un server locale al posto di quello remoto, modifica `plugin/.mcp.json`:

```json
{
  "mcpServers": {
    "legal-it": {
      "command": "uvx",
      "args": ["mcp-legal-it"]
    }
  }
}
```

Oppure con Docker:

```json
{
  "mcpServers": {
    "legal-it": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Profili tool

Per caricare solo un sottoinsieme di tool (utile per ridurre il context window):

```bash
LEGAL_PROFILE=sinistro docker run -p 8000:8000 mcp-legal-it
```

Profili disponibili: `sinistro`, `credito`, `penale`, `fiscale`, `normativa`, `privacy`, `studio`.

## Esempi d'uso

### Calcolo interessi di mora
```
Calcola gli interessi di mora su un credito commerciale di € 15.000 scaduto il 01/03/2025
```

### Analisi di un articolo
```
/legal-it:analisi-norma art. 2043 c.c.
```

### Parere legale
```
/legal-it:parere-legale Il mio cliente ha subìto un danno da prodotto difettoso...
```

### Data breach
```
/legal-it:data-breach Abbiamo scoperto un accesso non autorizzato al DB clienti con 5.000 record esposti
```

### Consulenza con agente specializzato
```
@legal-it:civilista Quali sono i rimedi per l'inadempimento contrattuale del fornitore?
```

## Requisiti

- Claude Code (con supporto plugin)
- Connessione internet (per il server MCP remoto)

## Licenza

MIT — vedi [LICENSE](LICENSE).

## Link utili

- [Repository](https://github.com/gpuzio/mcp-legal-it)
- [Issue tracker](https://github.com/gpuzio/mcp-legal-it/issues)
- [Changelog](CHANGELOG.md)
