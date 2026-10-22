<p align="center">
  <strong>mcp-legal-it</strong>
</p>

<p align="center">
  Server MCP + plugin per il diritto italiano
</p>

<p align="center">
  <a href="https://github.com/capazme/mcp-legal-it/releases"><img src="https://img.shields.io/github/v/release/capazme/mcp-legal-it?style=flat-square" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-3776ab?style=flat-square" alt="Python">
  <a href="https://github.com/capazme/mcp-legal-it/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/capazme/mcp-legal-it/ci.yml?branch=develop&style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/tool-228-green?style=flat-square" alt="Tools">
</p>

<p align="center">
  <a href="https://capazme.github.io/mcp-legal-it/"><strong>Guida all'installazione per Claude Desktop (Mac e Windows) →</strong></a>
</p>


---

## Cos'e mcp-legal-it

Un avvocato che usa Claude non dovrebbe cercare manualmente testi di legge, ricalcolare interessi o compilare informative privacy a mano. **mcp-legal-it** e un server [Model Context Protocol](https://modelcontextprotocol.io/) che mette a disposizione **228 tool** di calcolo legale, consultazione normativa, ricerca giurisprudenziale e compliance — tutti accessibili direttamente da Claude.

- **Normativa verificata** — testi vigenti da Normattiva, EUR-Lex e Brocardi (no allucinazioni)
- **Giurisprudenza Cassazione** — ricerca full-text e testo sentenze da Italgiure
- **Giurisprudenza Tributaria** — sentenze CTP/CTR/CGT e Cassazione tributaria da CeRDEF (def.finanze.it)
- **Giustizia Amministrativa** — sentenze TAR e Consiglio di Stato (giustizia-amministrativa.it)
- **Giurisprudenza CGUE** — sentenze Corte di Giustizia UE e Tribunale UE via CELLAR SPARQL
- **Delibere CONSOB** — ricerca e testo integrale dal Bollettino ufficiale
- **Calcoli giuridici** — interessi, rivalutazione ISTAT, parcelle, contributo unificato, IRPEF, successioni, danni e altro
- **GDPR compliance** — informative, DPIA, DPA, registro trattamenti, data breach, sanzioni
- **30 skill + 6 agenti** — workflow guidati per pareri, cause civili, sinistri, recupero crediti
- **Legal Grounding Protocol** — hook che verificano che ogni norma citata sia supportata da `cite_law()`

---

## Installazione

> **Prima volta?** La [guida passo passo](https://capazme.github.io/mcp-legal-it/) porta da zero a Legal IT funzionante in Claude Desktop, su Mac e Windows, anche senza Python installato.

> **Prerequisito unico: [`uv`](https://docs.astral.sh/uv/).** Gestisce automaticamente
> Python 3.12 e le dipendenze, identico su Windows/macOS/Linux.
> macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` ·
> Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
> Dopo l'installazione di `uv` **chiudi Claude del tutto** (⌘Q su macOS, non basta chiudere la finestra) e riaprilo: un'app già aperta non vede il nuovo `PATH`. Il primo avvio scarica Python 3.12 + dipendenze (~1 min).
>
> **Per il marketplace di Claude Code serve anche `git`** (clona il repository del plugin). Su macOS: `xcode-select --install`; su Windows: [Git for Windows](https://git-scm.com/download/win). Il file `.mcpb` per Claude Desktop non lo richiede.

> [!IMPORTANT]
> **Claude Desktop "Cowork" (l'agente cloud) non è supportato.** Da giugno 2026 Cowork esegue i plugin in una VM cloud che non può avviare server MCP locali, quindi il marketplace lo rifiuta (`failed_content: local/stdio server`). Per Claude Desktop usa il file **`.mcpb`** qui sotto (gira in locale; l'unico prerequisito è `uv`). Per l'agente Cowork servirebbe un server remoto HTTPS.

### Claude Desktop — file `.mcpb` (consigliato)

1. Installa `uv` (vedi sopra).
2. Scarica **`legal-it-X.Y.Z.mcpb`** dall'ultima [Release](https://github.com/capazme/mcp-legal-it/releases/latest).
3. In Claude Desktop: **doppio click sul file** — oppure **Impostazioni → Estensioni → Impostazioni avanzate → Sviluppatore estensioni → Installa file `.mcpb`**.
4. Riavvia Claude. I 228 tool girano in locale.

> **Il primo avvio è lento** (~1 min: scarica Python 3.12 e le dipendenze) e Claude Desktop
> può mostrare il server come *disconnesso* mentre sta ancora scaricando. Attendi un minuto
> e riavvia Claude: al secondo avvio parte in pochi secondi.

<details>
<summary><strong>Il server resta "disconnesso"</strong></summary>

I log stanno in `~/Library/Logs/Claude/` (macOS) — file `mcp-server-*.log` — e
`%APPDATA%\Claude\logs\` (Windows). Cerca l'ultima riga di errore:

| Nel log compare | Causa | Rimedio |
|---|---|---|
| `spawn uv ENOENT` / `uv: command not found` | `uv` non installato | Installa `uv` (vedi sopra) e riavvia Claude con ⌘Q |
| `Failed to build cryptography` + `Could not find directory of OpenSSL` | Mac Intel (x86_64) con `mcp-legal-it` ≤ 2.11.0: `cryptography` ≥ 49 non pubblica più wheel per macOS Intel e prova a compilarsi dai sorgenti | Aggiorna alla versione ≥ 2.11.1, che pinna `cryptography < 49` sui soli Mac Intel |
| `notifications/cancelled` dopo ~60 s, senza errori | Timeout del primo avvio mentre scarica | Riavvia Claude: la cache di `uv` è già popolata |

</details>

> **MCP Registry**: questo server dichiara la propria identità in [`server.json`](server.json)
> (`io.github.capazme/mcp-legal-it`, trasporto stdio). Il manifest segue lo schema ufficiale
> del [MCP Registry](https://registry.modelcontextprotocol.io); il marker verificabile per gli
> aggregatori è `mcp-name: io.github.capazme/mcp-legal-it`.

### Claude Code CLI

```bash
claude plugin marketplace add capazme/mcp-legal-it
claude plugin install legal-it@mcp-legal-it
```

Richiede `uv` e `git` (vedi sopra). Il primo avvio può essere lento: vedi la tabella qui sotto.

<details>
<summary><strong>Claude Code: il server non si connette</strong></summary>

| Sintomo | Causa | Rimedio |
|---|---|---|
| `connection timed out after 30000ms` al primo avvio | `uv` sta ancora scaricando Python: Claude Code aspetta 30 s e rinuncia (le librerie, invece, si scaricano dopo la connessione, senza limite di tempo) | Riprova da `/mcp` → *reconnect* (la cache è già popolata). Oppure avvia Claude Code con `MCP_TIMEOUT=120000 claude` |
| `CONNECTION_CLOSED` | Il processo del server è terminato subito: di solito `uv` non è installato | Installa `uv` (vedi sopra; scarica da solo Python 3.12), apri un nuovo terminale e riavvia `claude` |
| `marketplace add` fallisce subito | `git` mancante | `xcode-select --install` (macOS) e riprova |

</details>

### Claude.ai (web e mobile)

**Al momento non esiste un connettore supportato per claude.ai web o mobile.** Il server gira in locale (stdio): le app web e mobile non possono avviarlo, e il plugin non è installabile da lì. Usa Claude Desktop (`.mcpb`) o Claude Code.

### Archivio `legal-it-plugin-X.Y.Z.zip`

Ogni Release pubblica, oltre al `.mcpb`, anche `legal-it-plugin-X.Y.Z.zip` (generato da `scripts/build-plugin.sh`): una copia autonoma del **plugin per Claude Code** — skill, comandi, agenti, hook e codice del server — pensata per chi non può usare il marketplace (per esempio senza `git`). Si carica, per la sola sessione, con `claude --plugin-dir legal-it-plugin-X.Y.Z.zip` (accetta lo zip o la cartella estratta). Al primo avvio serve comunque la rete: `uv` scarica Python e le dipendenze. **Non** è un file da caricare in Claude Desktop (per quello c'è il `.mcpb`) né in claude.ai.


Ogni Release pubblica anche `legal-it-skills-X.Y.Z.zip`: le 30 skill in formato `.zip`, una per file, da caricare su claude.ai (**Impostazioni → Funzionalità → Skill**). Senza il server MCP le skill che usano gli strumenti di Legal IT non hanno i dati: servono soprattutto come guida di metodo.

### Docker

```bash
docker build -t mcp-legal-it .
docker run -p 8000:8000 mcp-legal-it    # Streamable HTTP su porta 8000, endpoint /mcp
```

Client MCP:

```json
{
  "mcpServers": {
    "legal-it": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Qualunque client MCP — entry point (richiede `uv`)

Il pacchetto espone il comando `mcp-legal-it` (stdio di default; `MCP_TRANSPORT=http|sse` con `MCP_HOST`, `MCP_PORT`, `MCP_PATH`):

```bash
uvx --from git+https://github.com/capazme/mcp-legal-it@main mcp-legal-it
```

Il server dichiara la propria versione ai client MCP (`serverInfo.version`). Le release vanno agganciate a un tag (`@vX.Y.Z`) invece che a `@main`.

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

### Codex CLI / ChatGPT

Il server MCP funziona anche fuori da Claude — ma Codex CLI e ChatGPT non
leggono i prompt guidati né le risorse `legal://`. Al posto delle skill del
plugin Claude Code, usa il **bundle OpenAI** generato dallo stesso corpus:

1. Scarica **`legal-it-openai-skills-X.Y.Z.zip`** dall'ultima [Release](https://github.com/capazme/mcp-legal-it/releases/latest) — contiene 42 skill (`.agents/skills/`), `AGENTS.md` e `config.toml.example`.
2. **Codex CLI**: estrai `.agents/skills/` in `$HOME/.agents/skills/` (globale) o nella root del progetto; copia `AGENTS.md`; aggiungi il blocco `config.toml.example` a `~/.codex/config.toml` (server MCP separato, via `uv`).
3. **ChatGPT**: carica `.agents/skills/` nella Skills UI; i 228 tool richiedono un connector Developer Mode su un endpoint HTTPS self-hosted (vedi Docker sopra).

Guida completa (naming del server, verifica `/mcp`, limiti rispetto al plugin Claude Code): [`docs/openai.md`](docs/openai.md).

### Canale beta

| Canale | Tag | Dove | Cosa ottieni |
|---|---|---|---|
| **Stabile** | `vX.Y.Z` | [`releases/latest`](https://github.com/capazme/mcp-legal-it/releases/latest), marketplace Claude Code | La linea in uso oggi (2.x) |
| **Beta** | `vX.Y.Z-beta.N` | [Releases](https://github.com/capazme/mcp-legal-it/releases) marcate **Pre-release** | Anteprima della prossima major/minor (es. 3.0.0) prima del rilascio definitivo |

`releases/latest` e il marketplace continuano a servire sempre la linea stabile: una beta non li tocca mai.

Per provare una beta:

1. Scarica gli artefatti dalla release Pre-release specifica (`.mcpb`, plugin zip, bundle OpenAI — stessa build della release stabile, versione beta stampata dentro) dalla pagina [Releases](https://github.com/capazme/mcp-legal-it/releases).
2. In alternativa, da sorgente: `git checkout vX.Y.Z-beta.N`.

---

## Tool disponibili — 228 tool, 34 moduli

| # | Categoria | Tool | Esempi |
|---|-----------|:----:|--------|
| 1 | Consultazione normativa | 8 | `cite_law`, `cerca_brocardi`, `verifica_citazioni` |
| 2 | Giurisprudenza Cassazione (Italgiure) | 5 | `leggi_sentenza`, `cerca_giurisprudenza`, `giurisprudenza_articolo` |
| 3 | Giurisprudenza tributaria (CeRDEF) | 3 | `cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento` |
| 4 | Giustizia amministrativa (TAR/CdS) | 4 | `cerca_giurisprudenza_amministrativa`, `leggi_provvedimento_amm` |
| 5 | Giurisprudenza CGUE | 4 | `cerca_giurisprudenza_cgue`, `leggi_sentenza_cgue` |
| 6 | Corte Costituzionale | 4 | `cerca_pronuncia_costituzionale`, `leggi_pronuncia_costituzionale` |
| 7 | Ricerca unificata e orientamenti | 4 | `cerca_giurisprudenza_unificata`, `orientamento_su_norma`, `mappa_orientamento` |
| 8 | Gazzetta Ufficiale | 5 | `cerca_gazzetta_ufficiale`, `leggi_atto_gazzetta`, `ultime_gazzette` |
| 9 | Iter parlamentare (DDL) | 3 | `cerca_ddl`, `iter_ddl`, `ddl_su_norma` |
| 10 | Recepimento UE → Italia | 3 | `get_italian_implementation`, `get_eu_basis` |
| 11 | Delibere CONSOB | 3 | `cerca_delibere_consob`, `leggi_delibera_consob` |
| 12 | Provvedimenti Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante` |
| 13 | Privacy/GDPR | 12 | `genera_informativa_privacy`, `genera_dpia`, `valutazione_data_breach` |
| 14 | Analisi fornitori (privacy) | 3 | `verifica_partita_iva_vies`, `verifica_dpa_fornitore`, `genera_report_fornitori` |
| 15 | Marchi (TMview) | 3 | `cerca_marchi`, `leggi_marchio`, `verifica_anteriorita_marchio` |
| 16 | Rivalutazione monetaria | 12 | `rivalutazione_monetaria`, `adeguamento_canone_locazione` |
| 17 | Interessi e tassi | 10 | `interessi_legali`, `interessi_mora`, `verifica_usura` |
| 18 | Scadenze e termini | 11 | `scadenza_processuale`, `termini_memorie_repliche`, `termini_processuali_civili` (artt. 171-ter e 189 c.p.c., sospensione feriale contata giorno per giorno) |
| 19 | Atti giudiziari | 23 | `contributo_unificato`, `decreto_ingiuntivo`, `pignoramento_stipendio` |
| 20 | Parcelle avvocati | 12 | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| 21 | Parcelle professionisti | 11 | `compenso_ctu`, `spese_mediazione` |
| 22 | Risarcimento danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| 23 | Diritto penale | 5 | `prescrizione_reato`, `aumenti_riduzioni_pena` |
| 24 | Proprietà e successioni | 12 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| 25 | Investimenti | 5 | `rendimento_bot`, `rendimento_btp`, `rendimento_buoni_postali` |
| 26 | Dichiarazione dei redditi | 16 | `calcolo_irpef`, `regime_forfettario`, `calcolo_tfr` |
| 27 | Diritto del lavoro | 6 | `indennita_licenziamento`, `calcolo_naspi`, `costo_lavoro` |
| 28 | Diritto societario | 4 | `quorum_assembleari`, `soglie_organo_controllo_srl` |
| 29 | Crisi d'impresa | 4 | `test_crisi_impresa`, `composizione_negoziata`, `compenso_occ` |
| 30 | Procedura civile | 3 | `competenza_giudice`, `verifica_mediazione_obbligatoria`, `gratuito_patrocinio` |
| 31 | Modelli di atti | 3 | `genera_modello_atto`, `esporta_atto_docx`, `lista_categorie_atti` |
| 32 | Recupero crediti seriale (DOCX) | 2 | `genera_procura_liti_docx`, `genera_quotazione_docx` |
| 33 | Utilità e provenienza dei dati | 14 | `codice_fiscale`, `verifica_iban`, `verbale_mensile` |

---

## Skill — 30 workflow guidati

Invocabili con `/legal-it:<nome>` o attivati automaticamente da Claude in base al contesto.

### Analisi normativa e giurisprudenziale

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `parere-legale` | Parere strutturato: Fatto, Diritto, Analisi, Conclusioni — ogni norma verificata con `cite_law` | `cite_law`, `cerca_giurisprudenza`, `leggi_sentenza` |
| `analisi-articolo` | Testo vigente + ratio legis + annotazioni Brocardi + giurisprudenza + norme collegate | `cite_law`, `cerca_brocardi`, `leggi_sentenza` |
| `analisi-giurisprudenziale` | Ricerca Italgiure con modalita esplora, lettura 2-4 decisioni chiave, sintesi orientamenti | `cerca_giurisprudenza`, `leggi_sentenza`, `cerca_brocardi`, `cite_law` |
| `ricerca-normativa` | Fonti primarie e secondarie ordinate per gerarchia + giurisprudenza + provvedimenti autorita | `cite_law`, `cerca_brocardi`, `cerca_giurisprudenza`, `cerca_delibere_consob`, `cerca_provvedimenti_garante` |
| `confronto-norme` | Confronto sistematico tra norme: differenze, sovrapposizioni, criteri di specialita/posteriorita/gerarchia | `cite_law`, `cerca_brocardi`, `cerca_giurisprudenza` |
| `mappatura-normativa` | Mappa normativa completa per settore con fonti per livello gerarchico e matrice adempimenti | `cite_law`, `cerca_delibere_consob`, `cerca_provvedimenti_garante`, `cerca_brocardi` |
| `verifica-prescrizione` | Termine prescrizione civile (artt. 2941-2946 c.c.) o penale con sospensione/interruzione | `prescrizione_diritti`, `prescrizione_reato`, `cite_law` |
| `orientamento-giurisprudenziale` | Mappa descrittiva dell'orientamento di legittimità: conformi vs contrasti, interventi delle Sezioni Unite, evoluzione nel tempo | `orientamento_su_norma`, `orientamento_su_principio`, `mappa_orientamento`, `leggi_sentenza` |
| `ricerca-gazzetta` | Cosa è uscito in Gazzetta Ufficiale: novità per serie, ricerca parametrica, testo as-published e PDF ufficiale | `cerca_gazzetta_ufficiale`, `leggi_atto_gazzetta`, `sommario_gazzetta`, `scarica_pdf_gazzetta` |
| `attuazione-direttiva` | Recepimento di una direttiva UE: atto italiano di attuazione, base giuridica europea, giurisprudenza CGUE collegata | `get_italian_implementation`, `get_eu_basis`, `giurisprudenza_cgue_su_norma`, `cite_law` |

### Contenzioso e calcoli

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `recupero-credito` | Workflow completo: interessi mora BCE+8pp, rivalutazione ISTAT, bozza decreto ingiuntivo, parcella e CU | `interessi_mora`, `rivalutazione_monetaria`, `decreto_ingiuntivo`, `parcella_avvocato_civile` |
| `causa-civile` | Pianificazione causa: CU per valore/tipo, scadenze post-Cartabia, termini impugnazione, preventivo | `contributo_unificato`, `scadenza_processuale`, `scadenze_impugnazioni`, `preventivo_civile` |
| `analisi-sinistro` | Quantificazione danno biologico (micro/macro in base a %), personalizzazione, rivalutazione, interessi | `danno_biologico_micro`, `danno_biologico_macro`, `rivalutazione_monetaria`, `interessi_legali` |
| `quantificazione-danni` | Calcolo risarcimento con personalizzazione per eta/attivita/condizioni e attualizzazione | `danno_biologico_micro`, `danno_biologico_macro`, `danno_non_patrimoniale`, `rivalutazione_monetaria` |
| `calcolo-parcella` | Parcella D.M. 55/2014 per fase (studio, introduttiva, trattazione, decisionale) con nota spese e fattura | `parcella_avvocato_civile`, `parcella_avvocato_penale`, `parcella_stragiudiziale`, `nota_spese`, `fattura_avvocato` |
| `pianificazione-successione` | Quote legittime e disponibili, grado parentela, imposte con franchigie, donazioni, adempimenti | `calcolo_eredita`, `imposte_successione`, `grado_parentela`, `imposte_compravendita` |

### Privacy e compliance

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `compliance-privacy` | Assessment GDPR completo: base giuridica, check DPIA, registro, informativa, DPA, data breach | tutti i 12 tool GDPR + `cite_law` |
| `data-breach` | Gestione incidente: valutazione rischio, modulo notifica Garante entro 72h, stima sanzioni art. 83 | `valutazione_data_breach`, `genera_notifica_data_breach`, `calcolo_sanzione_gdpr`, `cite_law` |
| `analisi-fornitori` | Screening privacy del mastrino fornitori: identificazione via web e VIES, ruolo art. 28, DPA pubblicato dal fornitore, report Excel e bozze di nomina | `verifica_partita_iva_vies`, `verifica_dpa_fornitore`, `genera_report_fornitori`, `genera_dpa` |
| `cookie-audit` | Audit forense di cookie, pixel e tracciamento di un sito e delle sue newsletter (pre/post consenso, CMP, GTM tag per tag, pixel Meta, `.eml` delle newsletter) con report Word e remediation — Provv. Garante 10/06/2021 e Linee guida sui tracking pixel nelle e-mail 17/04/2026 | `genera_informativa_cookie`, `cite_law` (+ strumenti browser di Claude) |

### Redazione documenti

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `genera-atto` | Generazione atti legali — **100 modelli in 10 categorie** ([dettaglio sotto](#genera-atto--100-modelli-di-atti)) | `genera_modello_atto`, `lista_categorie_atti`, `cite_law` |
| `redazione-contratto` | Supporto contrattuale: verifica norme, clausole tipo da Brocardi, check privacy/DPA se necessario | `cite_law`, `cerca_brocardi`, `analisi_base_giuridica`, `genera_dpa` |
| `procure-quotazioni` | Procure alle liti e lettere di quotazione D.M. 55/2014 in serie da Excel di posizioni, con rilevamento fase (monitorio/esecuzione/opposizione) | `genera_procura_liti_docx`, `genera_quotazione_docx` |
| `esporta-documento` | Esporta in DOCX o PDF il documento prodotto (informative, DPA, DPIA, registro, notifica) | `genera_informativa_privacy`, `genera_dpa`, `genera_dpia`, `genera_registro_trattamenti`, `genera_notifica_data_breach` |

### Giurisprudenza specializzata

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `analisi-tributaria` | Ricerca giurisprudenza tributaria CeRDEF, lettura provvedimenti, quadro normativo fiscale | `cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento`, `cite_law` |
| `analisi-giurisprudenza-amministrativa` | Ricerca TAR/CdS, lettura sentenze, quadro CPA/L.241 | `cerca_giurisprudenza_amministrativa`, `leggi_provvedimento_amm`, `cite_law` |
| `analisi-giurisprudenza-europea` | Ricerca CGUE via CELLAR SPARQL, lettura sentenze, quadro TFUE/direttive | `cerca_giurisprudenza_cgue`, `leggi_sentenza_cgue`, `cite_law` |
| `analisi-costituzionale` | Ricerca e lettura delle pronunce della Consulta, parametri costituzionali invocati, quadro normativo | `cerca_pronuncia_costituzionale`, `leggi_pronuncia_costituzionale`, `pronunce_cost_su_norma`, `cite_law` |

### CONSOB

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `analisi-delibere-consob` | Ricerca delibere CONSOB su un tema, lettura testo, quadro TUF/MiFID, sintesi orientamenti | `cerca_delibere_consob`, `leggi_delibera_consob`, `cite_law` |
| `novita-consob` | Ultime delibere pubblicate con sintesi orientamenti per tipologia/argomento | `ultime_delibere_consob`, `leggi_delibera_consob`, `cite_law` |

---

## Genera Atto — 100 modelli di atti

La skill `genera-atto` supporta **100 modelli** in **10 categorie**. Il workflow: identificazione tipo atto &rarr; raccolta campi obbligatori &rarr; calcoli automatici (CU, interessi, parcelle) &rarr; generazione &rarr; verifica norme con `cite_law` &rarr; output con checklist allegati.

<details>
<summary><strong>Atti introduttivi</strong> (12 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `decreto_ingiuntivo_ordinario` | Ricorso per DI — credito ordinario |
| `decreto_ingiuntivo_professionale` | Credito professionale (parcella vidimata) |
| `decreto_ingiuntivo_condominiale` | Credito condominiale |
| `decreto_ingiuntivo_cambiale` | Credito cambiario |
| `decreto_ingiuntivo_fatture` | Credito da fatture commerciali |
| `decreto_ingiuntivo_retribuzioni` | Crediti retributivi (sezione lavoro) |
| `sfratto_morosita` | Intimazione di sfratto per morosita |
| `citazione_ordinaria` | Atto di citazione — rito ordinario Tribunale |
| `ricorso_giudice_pace` | Ricorso al Giudice di Pace (fino a 10.000 euro) |
| `ricorso_semplificato` | Rito semplificato di cognizione (art. 281-decies c.p.c.) |
| `atto_appello` | Citazione in appello |
| `opposizione_decreto_ingiuntivo` | Citazione in opposizione a DI |

</details>

<details>
<summary><strong>Esecuzione</strong> (19 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `atto_di_precetto` | Atto di precetto |
| `pignoramento_presso_terzi` | Pignoramento presso terzi |
| `pignoramento_immobiliare` | Pignoramento immobiliare |
| `nota_precisazione_credito` | Nota di precisazione del credito |
| `dichiarazione_553_cpc` | Dichiarazione del terzo ex art. 553 c.p.c. |
| `ricerca_beni_492bis` | Ricerca beni con modalita telematiche (art. 492-bis) |
| `avviso_543_5_cpc` | Avviso ex art. 543 co. 5 c.p.c. |
| `cessazione_obbligo_custodia` | Cessazione obbligo di custodia |
| `ordinanza_assegnazione_somme` | Ordinanza di assegnazione somme |
| `ordinanza_assegnazione_crediti` | Ordinanza di assegnazione crediti |
| `ordinanza_assegnazione_543_cpc` | Ordinanza di assegnazione ex art. 543 c.p.c. |
| `proroga_567_cpc` | Proroga termini ex art. 567 c.p.c. |
| `vendita_mobili` | Istanza di vendita beni mobili |
| `vendita_immobili` | Istanza di vendita beni immobili |
| `rinuncia_esecuzione` | Rinuncia all'esecuzione |
| `rinuncia_intervento` | Rinuncia all'intervento |
| `perdita_efficacia_pignoramento` | Dichiarazione perdita efficacia pignoramento |
| `assegnazione_510_cpc` | Assegnazione ex art. 510 c.p.c. |
| `termine_efficacia_titolo` | Verifica termine efficacia titolo esecutivo |

</details>

<details>
<summary><strong>Preventivi</strong> (17 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `preventivo_civile` | Preventivo causa civile ordinaria |
| `preventivo_stragiudiziale` | Preventivo attivita stragiudiziale |
| `preventivo_volontaria_giurisdizione` | Preventivo volontaria giurisdizione |
| `preventivo_mediazione` | Preventivo procedura di mediazione |
| `preventivo_decreto_ingiuntivo` | Preventivo ricorso per DI |
| `preventivo_opposizione_di` | Preventivo opposizione a DI |
| `preventivo_precetto` | Preventivo atto di precetto |
| `preventivo_pignoramento` | Preventivo pignoramento |
| `preventivo_esecuzione_mobiliare` | Preventivo esecuzione mobiliare |
| `preventivo_esecuzione_immobiliare` | Preventivo esecuzione immobiliare |
| `preventivo_atp` | Preventivo accertamento tecnico preventivo |
| `preventivo_giudice_pace` | Preventivo causa Giudice di Pace |
| `preventivo_cautelari` | Preventivo procedimenti cautelari |
| `preventivo_lavoro` | Preventivo causa di lavoro |
| `preventivo_appello` | Preventivo giudizio di appello |
| `preventivo_penale` | Preventivo difesa penale |
| `preventivo_sfratto` | Preventivo procedimento di sfratto |

</details>

<details>
<summary><strong>Attestazioni di conformita</strong> (11 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `attestazione_estratto` | Attestazione di estratto |
| `attestazione_copia_informatica` | Attestazione copia informatica |
| `attestazione_duplicato` | Attestazione duplicato informatico |
| `attestazione_margine_fascicolo` | Attestazione a margine — fascicolo telematico |
| `attestazione_separata_fascicolo` | Attestazione separata — fascicolo telematico |
| `attestazione_margine_scanner` | Attestazione a margine — documento scansionato |
| `attestazione_separata_scanner` | Attestazione separata — documento scansionato |
| `attestazione_archivio_zip` | Attestazione archivio ZIP |
| `attestazione_stampe_pec` | Attestazione stampe PEC |
| `attestazione_composito_di` | Attestazione composito — decreto ingiuntivo |
| `attestazione_composito_decreto` | Attestazione composito — decreto |

</details>

<details>
<summary><strong>Notifiche e relate</strong> (9 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `relata_pec_generica` | Relata di notifica PEC generica |
| `relata_pec_decreto_ingiuntivo` | Relata PEC — decreto ingiuntivo |
| `relata_pec_opposizione_di` | Relata PEC — opposizione a DI |
| `relata_pec_appello` | Relata PEC — atto di appello |
| `relata_pec_sentenza_giudicato` | Relata PEC — sentenza passata in giudicato |
| `relata_pec_penale` | Relata PEC — atto penale |
| `relata_posta` | Relata di notifica a mezzo posta |
| `relata_unep` | Relata di notifica tramite UNEP |
| `relata_pat` | Relata di notifica PAT (giustizia amministrativa) |

</details>

<details>
<summary><strong>Procure</strong> (8 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `procura_generale` | Procura alle liti generale |
| `procura_speciale` | Procura speciale alle liti |
| `procura_appello` | Procura per giudizio di appello |
| `procura_mediazione` | Procura per mediazione |
| `procura_mediazione_sostanziale` | Procura per mediazione con poteri sostanziali |
| `procura_negoziazione` | Procura per negoziazione assistita |
| `procura_arbitrato` | Procura per arbitrato |
| `procura_incarico_professionale` | Procura e incarico professionale |

</details>

<details>
<summary><strong>Stragiudiziale</strong> (8 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `sollecito_pagamento` | Sollecito di pagamento |
| `sollecito_formale_mora` | Sollecito formale con costituzione in mora |
| `sollecito_prima_richiesta` | Sollecito — prima richiesta bonaria |
| `sollecito_post_sentenza` | Sollecito post-sentenza |
| `invito_negoziazione` | Invito a negoziazione assistita |
| `adesione_negoziazione` | Adesione a negoziazione assistita |
| `lettera_adeguamento_istat` | Lettera adeguamento canone ISTAT |
| `richiesta_nominativi_morosi` | Richiesta nominativi morosi al condominio |

</details>

<details>
<summary><strong>Privacy</strong> (8 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `informativa_privacy_art13` | Informativa ex art. 13 GDPR |
| `informativa_cookie` | Cookie policy con tabella e banner |
| `informativa_dipendenti` | Informativa privacy dipendenti |
| `informativa_videosorveglianza` | Cartello EDPB + informativa estesa |
| `dpa_art28` | Contratto responsabile trattamento art. 28 GDPR |
| `registro_trattamenti` | Scheda registro ex art. 30 GDPR |
| `dpia` | Valutazione d'impatto sulla protezione dati |
| `notifica_data_breach` | Modulo notifica violazione al Garante |

</details>

<details>
<summary><strong>Istanze</strong> (6 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `istanza_esecutorieta` | Istanza di esecutorieta |
| `certificato_giudicato` | Richiesta certificato di passaggio in giudicato |
| `istanza_giudicato` | Istanza di giudicato |
| `ricorso_intervento` | Ricorso per intervento |
| `avviso_impugnazione` | Avviso di impugnazione |
| `avviso_opposizione_di` | Avviso di opposizione a decreto ingiuntivo |

</details>

<details>
<summary><strong>PCT</strong> (2 modelli)</summary>

| Modello | Descrizione |
|---------|-------------|
| `nota_deposito_pct` | Nota di deposito telematico PCT |
| `nomina_ctp` | Nomina consulente tecnico di parte |

</details>

---

## Slash command — 9

| Comando | Descrizione | Logica di routing |
|---------|-------------|-------------------|
| `/legal-it:norma` | Cerca e cita una norma | Fetch testo vigente con `cite_law`, poi offre annotazioni Brocardi o giurisprudenza collegata |
| `/legal-it:sentenza` | Leggi una sentenza di Cassazione | Testo integrale con `leggi_sentenza` se numero e anno sono noti, altrimenti `cerca_giurisprudenza` |
| `/legal-it:interessi` | Calcolo interessi legali o di mora | Distingue legali (art. 1284 c.c.) da mora commerciale (BCE+8pp, D.Lgs. 231/2002) |
| `/legal-it:codice-fiscale` | Calcolo o decodifica CF | Se riceve un CF lo decodifica, se riceve dati anagrafici lo calcola |
| `/legal-it:scadenza` | Calcolo scadenza processuale | Routing: memorie 183/190, impugnazioni, esecuzioni, prescrizione civile/penale |
| `/legal-it:privacy` | Genera documenti GDPR | Routing per tipo: informativa art. 13, cookie, dipendenti, videosorveglianza, DPA, registro, DPIA, data breach |
| `/legal-it:digest` | Briefing giuridico settimanale | Ultime novità da tutte le fonti (Cassazione, tributario, TAR/CdS, CGUE, Garante, CONSOB), raggruppate per fonte; pianificabile come cron |
| `/legal-it:dati` | Stato delle tabelle dati | Freschezza e provenienza di ogni tabella del server e backlog di riconciliazione ordinato per quanto ha bloccato |
| `/legal-it:verbale` | Verbale mensile dei rifiuti | Report mese su mese dei calcoli rifiutati o degradati per tabelle scadute o non verificate (`verbale_mensile`) |

---

## Agenti — 6 specialisti

| Agente | Specializzazione | Aree coperte |
|--------|------------------|--------------|
| `civilista` | Contratti, responsabilita, successioni, diritti reali, obbligazioni, famiglia | Artt. 1321-1469 c.c. (contratti), art. 2043 ss. (resp. extracontrattuale), artt. 456-768 (successioni), artt. 832-1172 (diritti reali) |
| `digest-giuridico` | Briefing giuridico settimanale: ultime novita da tutte le fonti, raggruppate per fonte | Cassazione, tributario (CeRDEF), TAR/CdS, CGUE, Garante Privacy, CONSOB — workflow: raccolta &rarr; deduplica &rarr; top 3 in evidenza &rarr; norme citate |
| `penalista` | Reati, pene, prescrizione, misure cautelari, riti alternativi | Regime di prescrizione scelto dalla data del fatto: ordinario (fino al 02/08/2017), Orlando (2017-2019), blocco dopo il primo grado e improcedibilità ex art. 344-bis c.p.p. (fatti dal 2020) |
| `privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante | Struttura: Quadro normativo &rarr; Analisi &rarr; Rischi e sanzioni &rarr; Raccomandazioni |
| `redattore-atti` | Redazione atti giudiziari, stragiudiziali, procure, relate, attestazioni | Accesso a tutti i 100 modelli di atti + tool di calcolo (CU, interessi, parcelle) |
| `ricerca-giurisprudenziale` | Ricerca sistematica su Italgiure, CeRDEF, TAR/CdS, CGUE, CONSOB, Garante | Strategia: esplora &rarr; filtra con facets &rarr; cerca con filtri &rarr; leggi decisioni chiave &rarr; Brocardi &rarr; fondamento normativo |

---

## Tool a normativa previgente

Due tool calcolano sotto una disciplina che non regola più i casi nuovi e servono solo per i
casi residuali che ancora governa: `termini_183_190_cpc` (memorie ex artt. 183 co. 6 e 190
c.p.c. nel testo anteriore alla Riforma Cartabia, per le cause iscritte a ruolo prima del
28/02/2023) ed `equo_indennizzo` (DPR 834/1981, per i fatti anteriori al 06/12/2011). Sono
marcati con una flag dichiarata una volta nel docstring e applicata in tre punti:

| Dove | Cosa |
|------|------|
| Docstring | riga `Regime: PREVIGENTE — <casi residuali>; tool vigenti: <nomi>`, la prima cosa che il modello legge prima di scegliere |
| `tools/list` | tag `previgente` e blocco `mcp-legal-it/regime` in `_meta` (stato, casi residuali, tool vigenti) |
| Ogni risposta | campo `regime_normativo` nel corpo e lo stesso blocco in `_meta` |

Per impostazione predefinita i tool restano registrati e marcati; `LEGAL_PREVIGENTE=off` li
nasconde del tutto. L'audit (`scripts/audit_tool_annotations.py`) fallisce se un tool dichiara
il regime senza tag o senza wrapper `@previgente`, o se indica come tool vigente un nome non
registrato. Dettagli in `mcp_legal_it/lib/_regime.py`.

## Legal Grounding Protocol

Il plugin include hook che garantiscono l'accuratezza delle citazioni normative:

- **Stop hook** — verifica che ogni norma citata nella risposta abbia un `cite_law()` corrispondente

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
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio`, `http` (Streamable HTTP, endpoint `/mcp`; default nell'immagine Docker) o `sse` (legacy) |
| `MCP_HOST` | `0.0.0.0` | Bind address (solo http/sse) |
| `MCP_PORT` | `8000` | Porta (solo http/sse) |
| `LEGAL_PROFILE` | `full` | Profilo tool da caricare |
| `LEGAL_PREVIGENTE` | `on` | `off` nasconde i tool a normativa previgente (tag `previgente`) |
| `LEGAL_BROCARDI` | `on` | `off` spegne Brocardi: nessuna richiesta a brocardi.it, tool `solo_brocardi` non esposti |
| `MCP_CACHE_DIR` | — | Directory cache Brocardi |

### Profili disponibili

Un profilo espone i tool che hanno almeno una delle sue etichette; prompt e risorse restano
sempre disponibili. Etichette e regole: [docs/tool-tags.md](docs/tool-tags.md).

| Profilo | Tool | Contenuto |
|---------|------|-----------|
| `full` | 228 | Tutti i tool |
| `sinistro` | 79 | Danni, rivalutazione, interessi + norme e giurisprudenza |
| `credito` | 89 | Interessi, rivalutazione, parcelle, recupero crediti + norme e giurisprudenza |
| `penale` | 51 | Diritto penale + norme e giurisprudenza |
| `fiscale` | 66 | Fisco, immobili, società, crisi, investimenti, CeRDEF, CONSOB |
| `normativa` | 70 | Tutte le fonti: norme, ogni giurisprudenza, Garante e CONSOB, registri, privacy |
| `privacy` | 64 | GDPR + Garante + norme e giurisprudenza |
| `studio` | 76 | Scadenze, atti giudiziari, parcelle, investimenti, lavoro |
| `redattore` | 76 | Atti, procedura, parcelle, scadenze + norme |
| `cowork` | 77 | Norme, giurisprudenza, privacy, parcelle (set ridotto) |

Ogni profilo include i tre tool di diagnostica (`stato_server`, `verbale_mensile`,
`backlog_riconciliazione`).

### Senza Brocardi

Brocardi.it è l'unica fonte privata del server (note dottrinali e massime, mai il testo di una
norma) ed è attiva per impostazione predefinita. Per usare il server senza Brocardi:

```bash
LEGAL_BROCARDI=off mcp-legal-it
```

Con l'interruttore spento `cerca_brocardi` e `fetch_law_annotations` non sono esposti (226 tool
invece di 228), nessuna richiesta parte verso brocardi.it, e `cite_law(include_annotations=True)`,
`giurisprudenza_articolo` e `mappa_orientamento` rispondono senza Brocardi e lo dichiarano.
In codice: `crea_server(brocardi=False)` (vedi sotto) o, per chi chiama direttamente gli scraper,
`mcp_legal_it.lib._brocardi_switch.disabled()`. Uno *spento* impostato nell'ambiente non può essere
riacceso dal codice.

### Un server con una parte dei tool

```python
from mcp_legal_it.server import crea_server

fonti = crea_server(include_tags={"normativa", "giurisprudenza"}, brocardi=False)
fonti.run()                                   # oppure: il_mio_server.mount(fonti)
```

I tool esclusi non compaiono in `list_tools`; quelli inclusi restano identici a quelli del
server standard. Parametri ed esempi: [docs/tool-tags.md](docs/tool-tags.md#un-server-con-una-parte-dei-tool-crea_server).

### Come libreria Python: `mcp_legal_it.api`

```python
import asyncio
from mcp_legal_it import api

t = asyncio.run(api.testo_articolo("art. 2043 c.c.", canale="html"))
print(t.esito, t.norma_data.urn)
print(t.article_text)
```

Funzioni `async` con risultati tipizzati (dataclass), senza Markdown: norme (riferimento, testo
dell'articolo, indice, testo dell'atto, Brocardi) e giurisprudenza (Cassazione, Corte costituzionale,
CeRDEF, TAR/CdS, CGUE, ricerca unificata). Gli errori sono dati (`esito`, `errore`), non eccezioni.
Importare `mcp_legal_it.api` non carica FastMCP né il server e non apre connessioni; client HTTP,
cache e Brocardi si iniettano con `api.configurazione(...)`. È l'unica superficie stabile del
pacchetto (semver): riferimento completo in [docs/api.md](docs/api.md).

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

[Mozilla Public License 2.0](LICENSE) — Copyright 2025-2026 [capazme](https://github.com/capazme).
Fino alla linea 2.x il progetto era distribuito con licenza Apache-2.0: vedi [NOTICE](NOTICE).

### Codice da VisuaLex

Con la 3.0 i lettori delle fonti di [VisuaLex](https://github.com/capazme/VisuaLexAPI)
(MPL-2.0, degli stessi autori) confluiscono in mcp-legal-it, che VisuaLex usa poi
come dipendenza. Ogni file importato porta l'intestazione MPL-2.0 e la riga
«Imported from VisuaLex (MPL-2.0), `<percorso>` at `<commit>`»; le parti
riscritte da zero dicono nel commento da quale file di VisuaLex vengono. Finora:
le regole di rete per fonte (`mcp_legal_it/core/_http.py`, da `http_client.py` e
`circuit_breaker.py`); la tabella dei suffissi degli articoli
(`mcp_legal_it/lib/visualex/article_suffixes.py`, importata così com'è); le righe
delle tabelle dei tipi d'atto e `normalize_act_type`; la convenzione delle fonti
`golden.json` come fixture dei test (`tests/fixtures/visualex/`); il lettore del testo
degli articoli dalla pagina di Normattiva (`mcp_legal_it/lib/visualex/normattiva_html.py`);
il lettore dell'export Akoma Ntoso (`mcp_legal_it/lib/visualex/akn_parser.py`, unito al nostro)
e i suoi test (`tests/unit/test_akn_parser_visualex.py`); l'albero degli articoli di Normattiva
e il controllo d'esistenza (`mcp_legal_it/lib/visualex/albero_normattiva.py`); il lettore della vigenza dichiarata
dalla pagina (`mcp_legal_it/lib/visualex/normattiva_validity.py`) e i suoi test; il lettore del testo
degli articoli UE, Gazzetta ufficiale e versioni consolidate (`mcp_legal_it/lib/visualex/eurlex_text.py`)
con i suoi test e le pagine EUR-Lex di prova (`tests/fixtures/visualex/eurlex/`). L'inventario della migrazione è in
[`docs/migration/visualex-inventory.md`](docs/migration/visualex-inventory.md).

[![MCP Badge](https://lobehub.com/badge/mcp/capazme-mcp-legal-it)](https://lobehub.com/mcp/capazme-mcp-legal-it)
---

> I calcoli sono indicativi e non sostituiscono il parere di un professionista abilitato. Verificare sempre l'aggiornamento delle norme.
