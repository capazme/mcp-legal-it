# legal-it — Plugin per il Diritto Italiano

Plugin legale italiano per Claude Code e Claude Desktop: **227 tool** MCP, **30 skill**, **10 slash command**, **6 agenti specializzati** e **Legal Grounding Protocol**.

## Installazione

### Claude Desktop (file `.mcpb`)

> L'agente **Cowork** (cloud) non supporta i server MCP locali: usa il `.mcpb`, che gira in locale.

1. Installa [`uv`](https://docs.astral.sh/uv/).
2. Scarica `legal-it-X.Y.Z.mcpb` dall'ultima [Release](https://github.com/capazme/mcp-legal-it/releases/latest).
3. Doppio click sul file (o **Impostazioni → Estensioni → Impostazioni avanzate → Installa `.mcpb`**).

### Claude Code CLI

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
```

## Cosa include

### Server MCP (227 tool)

Il plugin avvia automaticamente il server MCP locale — nessun server remoto richiesto. Al primo avvio crea un virtualenv in `~/.cache/mcp-legal-it/` e installa le dipendenze.

| Categoria | Tool | Esempi |
|-----------|:----:|--------|
| Consultazione normativa | 8 | `cite_law`, `cerca_brocardi`, `verifica_citazioni` |
| Giurisprudenza Cassazione (Italgiure) | 5 | `leggi_sentenza`, `cerca_giurisprudenza`, `giurisprudenza_articolo` |
| Giurisprudenza tributaria (CeRDEF) | 3 | `cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento` |
| Giustizia amministrativa (TAR/CdS) | 4 | `cerca_giurisprudenza_amministrativa`, `leggi_provvedimento_amm` |
| Giurisprudenza CGUE | 4 | `cerca_giurisprudenza_cgue`, `leggi_sentenza_cgue` |
| Corte Costituzionale | 4 | `cerca_pronuncia_costituzionale`, `leggi_pronuncia_costituzionale` |
| Ricerca unificata e orientamenti | 4 | `cerca_giurisprudenza_unificata`, `orientamento_su_norma`, `mappa_orientamento` |
| Gazzetta Ufficiale | 5 | `cerca_gazzetta_ufficiale`, `leggi_atto_gazzetta`, `ultime_gazzette` |
| Iter parlamentare (DDL) | 3 | `cerca_ddl`, `iter_ddl`, `ddl_su_norma` |
| Recepimento UE → Italia | 3 | `get_italian_implementation`, `get_eu_basis` |
| Delibere CONSOB | 3 | `cerca_delibere_consob`, `leggi_delibera_consob` |
| Provvedimenti Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante` |
| Privacy/GDPR | 12 | `genera_informativa_privacy`, `genera_dpia`, `valutazione_data_breach` |
| Analisi fornitori (privacy) | 3 | `verifica_partita_iva_vies`, `verifica_dpa_fornitore`, `genera_report_fornitori` |
| Marchi (TMview) | 3 | `cerca_marchi`, `leggi_marchio`, `verifica_anteriorita_marchio` |
| Rivalutazione monetaria | 12 | `rivalutazione_monetaria`, `adeguamento_canone_locazione` |
| Interessi e tassi | 10 | `interessi_legali`, `interessi_mora`, `verifica_usura` |
| Scadenze e termini | 11 | `scadenza_processuale`, `termini_memorie_repliche` |
| Atti giudiziari | 23 | `contributo_unificato`, `decreto_ingiuntivo`, `pignoramento_stipendio` |
| Parcelle avvocati | 12 | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| Parcelle professionisti | 11 | `compenso_ctu`, `spese_mediazione` |
| Risarcimento danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| Diritto penale | 5 | `prescrizione_reato`, `aumenti_riduzioni_pena` |
| Proprietà e successioni | 12 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| Investimenti | 5 | `rendimento_bot`, `rendimento_btp`, `rendimento_buoni_postali` |
| Dichiarazione dei redditi | 16 | `calcolo_irpef`, `regime_forfettario`, `calcolo_tfr` |
| Diritto del lavoro | 6 | `indennita_licenziamento`, `calcolo_naspi`, `costo_lavoro` |
| Diritto societario | 4 | `quorum_assembleari`, `soglie_organo_controllo_srl` |
| Crisi d'impresa | 4 | `test_crisi_impresa`, `composizione_negoziata`, `compenso_occ` |
| Procedura civile | 3 | `competenza_giudice`, `verifica_mediazione_obbligatoria`, `gratuito_patrocinio` |
| Modelli di atti | 3 | `genera_modello_atto`, `esporta_atto_docx`, `lista_categorie_atti` |
| Recupero crediti seriale (DOCX) | 2 | `genera_procura_liti_docx`, `genera_quotazione_docx` |
| Utilità e provenienza dei dati | 14 | `codice_fiscale`, `verifica_iban`, `verbale_mensile` |

### Skill (30 workflow guidati)

Invocabili con `/legal-it:<nome>` o attivati automaticamente da Claude.

| Skill | Descrizione |
|-------|-------------|
| `parere-legale` | Parere strutturato con citazioni verificate |
| `analisi-articolo` | Analisi approfondita di un articolo di legge |
| `analisi-giurisprudenziale` | Ricerca e sintesi degli orientamenti della Cassazione |
| `orientamento-giurisprudenziale` | Orientamento consolidato o contrasto: conformi, Sezioni Unite, evoluzione |
| `analisi-costituzionale` | Sentenze e ordinanze della Consulta, parametri invocati |
| `analisi-tributaria` | Giurisprudenza tributaria (CeRDEF) e Cassazione tributaria |
| `analisi-giurisprudenza-amministrativa` | Sentenze TAR e Consiglio di Stato |
| `analisi-giurisprudenza-europea` | Sentenze CGUE e Tribunale UE |
| `ricerca-normativa` | Ricerca normativa completa su un tema |
| `ricerca-gazzetta` | Atti pubblicati in Gazzetta Ufficiale, testo e PDF ufficiale |
| `confronto-norme` | Confronto tra norme: prevalenza, coordinamento |
| `mappatura-normativa` | Mappa normativa per settore/attività |
| `attuazione-direttiva` | Recepimento di una direttiva UE: atto italiano e giurisprudenza CGUE |
| `recupero-credito` | Interessi mora + decreto ingiuntivo + parcella |
| `analisi-sinistro` | Quantificazione danni da sinistro con rivalutazione |
| `causa-civile` | Pianificazione causa: costi, scadenze, preventivo |
| `quantificazione-danni` | Calcolo danno biologico/patrimoniale/morale |
| `calcolo-parcella` | Parcella avvocato D.M. 55/2014 |
| `verifica-prescrizione` | Prescrizione civile o penale |
| `pianificazione-successione` | Quote ereditarie, imposte, adempimenti |
| `compliance-privacy` | Assessment GDPR completo |
| `data-breach` | Gestione data breach: valutazione + notifica |
| `cookie-audit` | Audit forense dei cookie di un sito e conformità al Provvedimento Garante 2021 |
| `analisi-fornitori` | Screening privacy del mastrino fornitori (art. 28), DPA pubblicati, report Excel e nomine |
| `redazione-contratto` | Supporto redazione contrattuale |
| `genera-atto` | Generazione atti giudiziari (100 modelli) |
| `procure-quotazioni` | Procure alle liti + quotazioni D.M. 55/2014 in serie (DOCX) |
| `esporta-documento` | Esporta il lavoro in DOCX/PDF |
| `analisi-delibere-consob` | Ricerca e analisi delibere CONSOB |
| `novita-consob` | Ultime delibere CONSOB |

### Slash command (10)

| Comando | Descrizione |
|---------|-------------|
| `/legal-it:norma` | Cerca e cita una norma |
| `/legal-it:sentenza` | Leggi una sentenza di Cassazione |
| `/legal-it:interessi` | Calcolo interessi legali o di mora |
| `/legal-it:codice-fiscale` | Calcolo o decodifica CF |
| `/legal-it:scadenza` | Calcolo scadenza processuale |
| `/legal-it:privacy` | Genera documenti GDPR |
| `/legal-it:digest` | Briefing giuridico settimanale |
| `/legal-it:dati` | Stato delle tabelle dati |
| `/legal-it:verbale` | Verbale mensile dei rifiuti |
| `/legal-it:release` | Rilascio del plugin |

### Agenti (6 specialisti)

| Agente | Specializzazione |
|--------|------------------|
| `civilista` | Contratti, responsabilita, successioni, obbligazioni, famiglia |
| `digest-giuridico` | Briefing settimanale delle novita da tutte le fonti |
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

[Apache License 2.0](LICENSE) — Copyright 2025-2026 [capazme](https://github.com/capazme).
