# legal-it — Plugin per il Diritto Italiano

Plugin legale italiano per Claude Code e Claude Desktop: **234 tool** MCP, **30 skill**, **9 slash command**, **6 agenti specializzati** e **Legal Grounding Protocol**.

## Installazione

Il plugin funziona in **Claude Code**: nel terminale, nelle estensioni per IDE e nella scheda **Code** dell'app Claude Desktop.

**Prerequisito: [`uv`](https://docs.astral.sh/uv/)**, che scarica da solo Python 3.12 e le librerie del server. Python non va installato a parte.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Dopo l'installazione di `uv`, chiudi del tutto Claude (o il terminale) e riaprilo.

**Dal marketplace del progetto** (serve anche `git`; su macOS `xcode-select --install`):

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
```

Gli aggiornamenti automatici dei marketplace di terzi sono spenti per default: attivali da `/plugin` → **Marketplaces** → `mcp-legal-it` → **Enable auto-update**.

**Non installare insieme anche l'estensione `.mcpb`**: Claude Desktop la avvia pure nelle sessioni Code, e gli stessi strumenti comparirebbero due volte.

### Primo avvio

Al primo avvio `uv` scarica Python 3.12 (circa 25 MB); il server si collega appena Python è pronto e, in background, scarica le versioni esatte delle librerie fissate in `server/uv.lock` (circa 40 MB, senza limite di tempo). Gli strumenti compaiono da soli quando il download finisce; se nel frattempo ne chiedi uno, Claude riceve il messaggio «Legal IT si sta preparando». Gli avvii successivi richiedono meno di un secondo.

| Sintomo | Rimedio |
|---|---|
| `connection timed out` al primo avvio | La rete è così lenta che anche il solo Python ha superato i 30 secondi: `/mcp` → *reconnect* (il download riprende da dove era). Oppure avvia Claude Code con `MCP_TIMEOUT=120000 claude` |
| `CONNECTION_CLOSED` o `uv: command not found` | `uv` manca: installalo, apri un nuovo terminale e riavvia Claude |

## Rete e dati

Il server gira **sul tuo computer** e non invia telemetria. Contatta soltanto:

- **al primo avvio e a ogni nuova versione**: i server di `uv` per scaricare Python 3.12 (python-build-standalone, su GitHub) e PyPI per le librerie elencate in `server/uv.lock`;
- **quando un tool lo richiede**, le fonti pubbliche che consulta per rispondere:
  - legislazione: Normattiva (`www.normattiva.it`), Gazzetta Ufficiale (`www.gazzettaufficiale.it`);
  - giurisprudenza: Corte di cassazione (`www.italgiure.giustizia.it`), giustizia amministrativa (`www.giustizia-amministrativa.it`, `mdp.giustizia-amministrativa.it`), Corte costituzionale (`dati.cortecostituzionale.it`), CeRDEF del MEF (`def.finanze.it`), Corte dei conti (`banchedati.corteconti.it` e il servizio di ricerca `corteconti-iit.almawave.cloud`, gestito dal fornitore Almawave, con le credenziali pubbliche che il sito dà a ogni visitatore);
  - Parlamento: `dati.senato.it`, `dati.camera.it`;
  - autorità: Garante privacy (`www.garanteprivacy.it`, `servizi.gpdp.it`), CONSOB (`www.consob.it`), ANAC (`www.anticorruzione.it`);
  - Unione europea: EUR-Lex (`eur-lex.europa.eu`), Ufficio delle pubblicazioni (`publications.europa.eu`), VIES della Commissione (`ec.europa.eu`), TMview (`www.tmdn.org`);
  - fonte privata: Brocardi.it (`www.brocardi.it`), solo annotazioni e massime, mai il testo delle norme;
  - `verifica_dpa_fornitore`: il sito pubblico del fornitore indicato dall'utente (solo indirizzi pubblici, verificati prima della richiesta).

A queste fonti arrivano solo i parametri della ricerca (per esempio il numero di un articolo, le parole cercate, una partita IVA da verificare con VIES). L'elenco degli host è verificato dai test del progetto (`_egress.py`).

**Sul disco** il server scrive solo cache di testi pubblici in `~/.cache/mcp-legal-it` (`MCP_CACHE_DIR`; `LEGAL_CACHE=off` le disattiva) e i documenti che chiedi di generare. L'hook delle citazioni legge in locale la trascrizione della sessione e quelle dei suoi subagenti, mai di altre sessioni, e non le invia da nessuna parte.

Le skill `esporta-documento` e `cookie-audit` usano Node.js con il pacchetto `docx`, se presente; la skill `cookie-audit` usa anche gli strumenti del browser di Claude, quando disponibili.

Informativa privacy: <https://capazme.github.io/mcp-legal-it/privacy.html>. Assistenza: <https://github.com/capazme/mcp-legal-it/issues>.

## Il controllo delle citazioni

Alla fine di ogni risposta, e di ogni subagente, un hook controlla che le norme e le sentenze citate siano state **lette con un tool** nella sessione (Legal Grounding Protocol). Se ne trova di non lette, chiede una volta di leggerle prima di chiudere; non blocca mai la sessione.

- **Norme**: conta un risultato di `cite_law` o `fetch_law_article` che ha restituito proprio quell'articolo, o un testo di `fetch_full_act` che lo contiene. Un errore, o un articolo diverso da quello chiesto, non conta.
- **Sentenze** (Cassazione, Corte costituzionale, TAR e Consiglio di Stato, Corte di giustizia UE): conta un risultato dei tool di quella corte (`leggi_*`, `cerca_*`, `*_su_norma`, `ultime_*`) che riporta numero e anno nella sua intestazione: i precedenti citati dentro una sentenza letta non contano, vanno letti a loro volta. **Una massima di Brocardi o una sintesi di orientamento non basta**: riassume la decisione, non è la decisione. Per questo il controllo chiede di leggerla, per esempio con `leggi_sentenza`.
- **Fonti che nessun tool copre** (CEDU, codice deontologico forense, allegati UE): basta scrivere «fuori copertura» sulla stessa riga.

Controlla che la fonte sia stata letta, non che la risposta ne riporti correttamente il contenuto: quello resta al giudizio dell'avvocato.

## Cosa include

### Server MCP (234 tool)

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
| Atti ANAC | 3 | `cerca_atti_anac`, `leggi_atto_anac`, `ultimi_atti_anac` |
| Corte dei conti (deliberazioni di controllo) | 3 | `cerca_deliberazioni_corte_conti`, `leggi_deliberazione_corte_conti`, `ultime_deliberazioni_corte_conti` |
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
| `cookie-audit` | Audit forense di cookie, pixel e tracciamento di sito e newsletter (Provv. Garante 2021, Linee guida tracking pixel nelle e-mail 2026) |
| `analisi-fornitori` | Screening privacy del mastrino fornitori (art. 28), DPA pubblicati, report Excel e nomine |
| `redazione-contratto` | Supporto redazione contrattuale |
| `genera-atto` | Generazione atti giudiziari (100 modelli) |
| `procure-quotazioni` | Procure alle liti + quotazioni D.M. 55/2014 in serie (DOCX) |
| `esporta-documento` | Esporta il lavoro in DOCX/PDF |
| `analisi-delibere-consob` | Ricerca e analisi delibere CONSOB |
| `novita-consob` | Ultime delibere CONSOB |

### Slash command (9)

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

### Agenti (6 specialisti)

| Agente | Specializzazione |
|--------|------------------|
| `civilista` | Contratti, responsabilita, successioni, obbligazioni, famiglia |
| `digest-giuridico` | Briefing settimanale delle novita da tutte le fonti |
| `penalista` | Reati, pene, prescrizione, misure cautelari |
| `privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante |
| `redattore-atti` | Redazione atti giudiziari e stragiudiziali |
| `ricerca-giurisprudenziale` | Ricerca sistematica su Italgiure |
| `digest-giuridico` | Briefing giuridico settimanale: ultime novità da tutte le fonti (Cassazione, tributario, TAR/CdS, CGUE, Garante, CONSOB) raggruppate per fonte |

### Hook (Legal Grounding Protocol)

- **Stop**: a fine risposta segnala le norme citate senza un `cite_law()` che le abbia verificate (locale, deterministico; gira nell'ambiente `uv` del server)

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

- Claude Code (terminale, IDE o scheda Code di Claude Desktop)
- [`uv`](https://docs.astral.sh/uv/): installa da solo Python 3.12 e le librerie

## In English

legal-it is a Claude Code plugin for Italian law: a local MCP server with 234 tools (statutes from Normattiva and EUR-Lex, case law from the Italian Supreme Court, administrative courts, Constitutional Court and CJEU, legal calculations, GDPR documents), 23 skills, 9 commands and 6 agents. The server runs on the user's machine through `uv run --frozen` with the versions pinned in `server/uv.lock`, sends no telemetry, and contacts only the public sources listed under «Rete e dati», with the parameters of each query.

## Licenza

[Mozilla Public License 2.0](LICENSE) — Copyright 2025-2026 [capazme](https://github.com/capazme). Fino alla linea 2.x: Apache-2.0.
