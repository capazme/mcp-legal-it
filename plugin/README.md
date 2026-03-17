# legal-it — Plugin per il Diritto Italiano

Plugin legale italiano per Claude (Cowork e Claude Code): **166 tool** MCP, **19 skill**, **8 slash command**, **5 agenti specializzati** e **Legal Grounding Protocol**.

## Installazione

### Claude Desktop (Cowork)

1. Personalizza → **+** → **Aggiungi marketplace da GitHub**
2. `capazme/mcp-legal-it`
3. Installa **legal-it**

### Claude Code CLI

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
```

## Cosa include

### Server MCP (166 tool)

Il plugin avvia automaticamente il server MCP locale — nessun server remoto richiesto. Al primo avvio crea un virtualenv in `~/.cache/mcp-legal-it/` e installa le dipendenze.

| Categoria | Tool | Esempi |
|-----------|:----:|--------|
| Normativa | 5 | `cite_law`, `cerca_brocardi`, `download_law_pdf` |
| Giurisprudenza Cassazione | 4 | `leggi_sentenza`, `cerca_giurisprudenza` |
| CONSOB | 3 | `cerca_delibere_consob`, `leggi_delibera_consob` |
| Privacy/GDPR | 12 | `genera_informativa_privacy`, `genera_dpia`, `valutazione_data_breach` |
| Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante` |
| Rivalutazione ISTAT | 11 | `rivalutazione_monetaria`, `adeguamento_canone_locazione` |
| Interessi e tassi | 10 | `interessi_legali`, `interessi_mora`, `verifica_usura` |
| Scadenze processuali | 11 | `scadenza_processuale`, `termini_memorie_repliche` |
| Atti giudiziari | 15 | `contributo_unificato`, `decreto_ingiuntivo`, `pignoramento_stipendio` |
| Parcelle avvocati | 11 | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| Parcelle professionisti | 11 | `compenso_ctu`, `spese_mediazione` |
| Risarcimento danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| Diritto penale | 5 | `prescrizione_reato`, `aumenti_riduzioni_pena` |
| Proprieta e successioni | 11 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| Investimenti e fiscalita | 19 | `calcolo_irpef`, `regime_forfettario`, `rendimento_btp` |
| Utilita | 12 | `codice_fiscale`, `verifica_iban`, `scorporo_iva` |

### Skill (19 workflow guidati)

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

### Slash command (8)

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

### Agenti (5 specialisti)

| Agente | Specializzazione |
|--------|------------------|
| `civilista` | Contratti, responsabilita, successioni, obbligazioni, famiglia |
| `penalista` | Reati, pene, prescrizione, misure cautelari |
| `privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante |
| `redattore-atti` | Redazione atti giudiziari e stragiudiziali |
| `ricerca-giurisprudenziale` | Ricerca sistematica su Italgiure |

### Hook (Legal Grounding Protocol)

- **Stop**: verifica che ogni norma citata abbia un `cite_law()` corrispondente
- **SessionStart**: dopo compaction, ricorda il protocollo di citazione

## Esempi d'uso

```
Calcola gli interessi di mora su un credito commerciale di 15.000 scaduto il 01/03/2025
```

```
/legal-it:analisi-articolo art. 2043 c.c.
```

```
/legal-it:parere-legale Il mio cliente ha subito un danno da prodotto difettoso...
```

```
/legal-it:data-breach Accesso non autorizzato al DB clienti con 5.000 record esposti
```

## Requisiti

- Claude Desktop (Cowork) o Claude Code CLI
- Python >= 3.10 (installato automaticamente il virtualenv al primo avvio)

## Licenza

MIT — vedi [LICENSE](LICENSE).
