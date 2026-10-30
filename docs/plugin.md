# Claude Code Plugin — mcp-legal-it

> Documentazione del plugin per Claude Code: 30 skills, 9 slash command, 6 agenti specializzati, hooks.

## Indice

- [Panoramica](#panoramica)
- [Struttura del plugin](#struttura-del-plugin)
- [Skills — Workflow guidati](#skills--workflow-guidati)
- [Agenti — Specialisti legali](#agenti--specialisti-legali)
- [Hooks — Guardrail automatici](#hooks--guardrail-automatici)
- [Permessi](#permessi)
- [Installazione](#installazione)
- [Creare una nuova skill](#creare-una-nuova-skill)

---

## Panoramica

Il plugin `legal-it` aggiunge a Claude Code:

- **30 skills** invocabili con `/skill-name` — ogni skill orchestra una sequenza di tool MCP
- **6 agenti** configurati come sub-agenti specializzati con istruzioni di sistema e tool preferiti
- **9 slash command** (`/norma`, `/sentenza`, `/interessi`, `/scadenza`, `/privacy`, `/codice-fiscale`, `/digest`, `/dati`, `/verbale`)
- **1 hook** automatico (`Stop`): gate deterministico sulle citazioni normative a fine risposta

**Marketplace**: `.claude-plugin/marketplace.json`

```json
{
  "name": "mcp-legal-it",
  "plugins": [{
    "name": "legal-it",
    "source": "./plugin",
    "description": "Plugin legale italiano completo: 234 tool di calcolo e ricerca, normativa (Normattiva/EUR-Lex/Brocardi/Gazzetta Ufficiale), giurisprudenza (Cassazione, Corte Costituzionale, CeRDEF tributario, TAR/CdS, CGUE, Corte dei conti), orientamenti e contrasti, recepimento UE→IT, verifica citazioni, CONSOB, compliance GDPR, diritto del lavoro, crisi d'impresa, societario, export DOCX/PDF. 30 skill, 9 slash command, 6 agenti specializzati."
  }]
}
```

---

## Struttura del plugin

```
plugin/
├── skills/                     # 30 directory, una per skill (proiezione di content/skills/)
│   ├── analisi-sinistro/SKILL.md
│   ├── recupero-credito/SKILL.md
│   ├── causa-civile/SKILL.md
│   └── ... (27 altre)
├── commands/                   # 9 slash command
│   ├── norma.md
│   ├── sentenza.md
│   └── ... (7 altri: interessi, scadenza, privacy, codice-fiscale, digest, dati, verbale)
├── agents/                     # 6 agenti specializzati
│   ├── civilista.md
│   ├── penalista.md
│   ├── privacy-specialist.md
│   ├── ricerca-giurisprudenziale.md
│   ├── redattore-atti.md
│   └── digest-giuridico.md
├── server/                     # server MCP (mcp_legal_it/, run_server.py)
├── hooks/
│   ├── hooks.json              # registra lo hook su Stop e SubagentStop
│   └── citation-gate.py        # implementazione del gate citazioni
└── server/uv.lock              # versioni esatte installate da `uv run --frozen`
```

Ogni skill è una directory con un file `SKILL.md` in formato frontmatter YAML + markdown.

---

## Skills — Workflow guidati

### Tabella delle 30 skills

Fonte: `content/skills/*/SKILL.md` (una directory per skill; `plugin/skills/` è una proiezione generata).

| Nome | Frasi trigger | Tool principali usati |
|------|--------------|----------------------|
| `analisi-sinistro` | "sinistro", "risarcimento danni", "invalidità", "danno biologico" | `danno_biologico_micro/macro`, `danno_non_patrimoniale`, `rivalutazione_monetaria`, `interessi_legali` |
| `recupero-credito` | "recupero credito", "interessi di mora", "decreto ingiuntivo", "creditore" | `interessi_mora`, `rivalutazione_monetaria`, `decreto_ingiuntivo`, `parcella_avvocato_civile` |
| `causa-civile` | "causa civile", "giudizio", "contributo unificato", "scadenze processuali" | `contributo_unificato`, `scadenza_processuale`, `scadenze_impugnazioni`, `preventivo_civile` |
| `pianificazione-successione` | "successione", "eredità", "quote ereditarie", "imposta successione" | `calcolo_eredita`, `imposte_successione`, `imposte_compravendita` |
| `parere-legale` | "parere legale", "opinione giuridica", "analisi giuridica" | `cite_law` (multiplo) |
| `quantificazione-danni` | "quantificazione danno", "danno patrimoniale", "danno morale" | `danno_biologico_micro/macro`, `danno_non_patrimoniale`, `rivalutazione_monetaria`, `interessi_legali` |
| `calcolo-parcella` | "parcella avvocato", "compenso", "nota spese", "D.M. 55/2014" | `parcella_avvocato_civile/penale/stragiudiziale`, `nota_spese` |
| `verifica-prescrizione` | "prescrizione", "termine prescritto", "quando scade" | `prescrizione_diritti`, `prescrizione_reato` |
| `ricerca-normativa` | "normativa su", "quali norme", "quadro normativo", "leggi applicabili" | `cite_law` (multiplo con `include_annotations=true`) |
| `analisi-articolo` | "analisi approfondita", "ratio legis", "spiega l'articolo" | `cite_law`, `cerca_brocardi`, `cite_law` (norme collegate) |
| `analisi-giurisprudenziale` | "giurisprudenza su", "orientamenti Cassazione", "precedenti" | `cerca_giurisprudenza`, `leggi_sentenza`, `cerca_brocardi`, `cite_law` |
| `confronto-norme` | "confronta norme", "quale prevale", "specialità" | `cite_law` × 2 (con annotations) |
| `mappatura-normativa` | "mappa normativa", "normativa di settore", "fonti applicabili" | `cite_law` (per livello gerarchico) |
| `compliance-privacy` | "compliance GDPR", "assessment privacy", "adeguamento GDPR" | `analisi_base_giuridica`, `verifica_necessita_dpia`, `genera_dpia`, `genera_registro_trattamenti`, `genera_informativa_privacy`, `genera_dpa` |
| `data-breach` | "data breach", "violazione dati", "notifica Garante" | `valutazione_data_breach`, `genera_notifica_data_breach`, `calcolo_sanzione_gdpr` |
| `redazione-contratto` | "redigi contratto", "revisione contratto", "clausole" | `cite_law`, `cerca_brocardi`, tool GDPR (se contratto con dati personali) |
| `genera-atto` | "redigi atto", "prepara ricorso", "citazione", "precetto", "relata" | `genera_modello_atto`, `esporta_atto_docx`, `lista_categorie_atti` |
| `esporta-documento` | "esporta in word", "salva in pdf", "genera docx" | `esporta_atto_docx` |
| `procure-quotazioni` | "procure e quotazioni", "quotazioni monitori", "preventivi decreti ingiuntivi" | `genera_procura_liti_docx`, `genera_quotazione_docx` |
| `analisi-fornitori` | "mastrino fornitori", "screening fornitori GDPR", "nomina responsabile art. 28" | `verifica_partita_iva_vies`, `genera_report_fornitori`, `genera_dpa` |
| `cookie-audit` | "analisi cookie", "audit cookie", "banner consenso", "che cookie usa il sito", "pixel di Meta", "tracking pixel nelle newsletter", "mappatura strumenti di tracciamento" | browser + script della skill + `genera_informativa_cookie` |
| `analisi-delibere-consob` | "delibere CONSOB", "provvedimenti mercati finanziari", "sanzioni CONSOB" | `cerca_delibere_consob`, `leggi_delibera_consob`, `cite_law` |
| `novita-consob` | "ultime novità CONSOB", "delibere recenti" | `ultime_delibere_consob`, `leggi_delibera_consob` |
| `analisi-tributaria` | "giurisprudenza tributaria", "sentenze IVA/IRES", "accertamento e riscossione", "contenzioso fiscale CGT" | `cerca_giurisprudenza`, `cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento`, `cite_law` |
| `analisi-giurisprudenza-amministrativa` | "sentenze TAR o CdS", "appalti pubblici", "urbanistica ed edilizia", "accesso agli atti" | `cerca_giurisprudenza_amministrativa`, `cite_law`, `giurisprudenza_amm_su_norma`, `leggi_provvedimento_amm` |
| `analisi-giurisprudenza-europea` | "sentenze CGUE", "rinvio pregiudiziale", "interpretazione direttive/regolamenti UE", "conclusioni Avvocato generale" | `cerca_giurisprudenza_cgue`, `cite_law`, `giurisprudenza_cgue_su_norma`, `leggi_sentenza_cgue` |
| `analisi-costituzionale` | "sentenze della Consulta", "legittimità costituzionale", "pronunce additive/interpretative" | `cerca_pronuncia_costituzionale`, `cite_law`, `leggi_pronuncia_costituzionale`, `pronunce_cost_su_norma` |
| `ricerca-gazzetta` | "cosa è uscito in Gazzetta", "testo di un decreto pubblicato", "estremi di pubblicazione", "sommario della GU" | `cerca_gazzetta_ufficiale`, `cite_law`, `leggi_atto_gazzetta`, `scarica_pdf_gazzetta`, `sommario_gazzetta`, `ultime_gazzette` |
| `orientamento-giurisprudenziale` | "orientamento consolidato", "contrasto in Cassazione", "evoluzione della giurisprudenza" | `cite_law`, `leggi_sentenza`, `mappa_orientamento`, `orientamento_su_norma`, `orientamento_su_principio` |
| `attuazione-direttiva` | "recepimento di una direttiva UE", "atto italiano di attuazione", "base UE di un atto nazionale" | `cite_law`, `get_eu_basis`, `get_italian_implementation`, `giurisprudenza_cgue_su_norma` |

### Formato SKILL.md

```markdown
---
name: nome-skill
description: Descrizione una riga. Seconda frase con frasi trigger.
argument-hint: "[param1] [param2 opzionale]"
---

# Titolo Skill

## Step 1 — ...
Istruzioni per il primo step con tool da chiamare.

## Step 2 — ...
...
```

Il frontmatter YAML è obbligatorio. Il campo `description` è usato per il matching contestuale. Il `argument-hint` viene mostrato all'utente come suggerimento.

---

## Agenti — Specialisti legali

I 6 agenti sono sub-agenti Claude Code con prompt di sistema specializzati e lista esplicita dei tool preferiti:
`civilista`, `penalista`, `privacy-specialist`, `ricerca-giurisprudenziale`, `redattore-atti`, `digest-giuridico`.

### `civilista`

**File**: `content/agents/civilista.md`
**Modello**: `sonnet`

Avvocato civilista esperto in contratti, responsabilità civile, successioni, diritti reali, obbligazioni e famiglia.

**Regole fondamentali**:
1. Chiama `cite_law()` prima di citare qualsiasi norma
2. Usa `cerca_giurisprudenza(archivio="civile")` → `leggi_sentenza()` per i precedenti
3. Usa `cerca_brocardi()` per ratio legis e massime

**Struttura risposte**: FATTO → DIRITTO → ANALISI → CONCLUSIONI

**Aree di competenza**: contrattualistica (artt. 1321-1469 c.c.), responsabilità civile (artt. 2043, 1218 c.c.), successioni (artt. 456-768 c.c.), diritti reali (artt. 832-1172 c.c.), obbligazioni (artt. 1173-1320 c.c.), famiglia.

**Tool principali**: `cite_law`, `cerca_brocardi`, `cerca_giurisprudenza(archivio="civile")`, `leggi_sentenza`, `danno_biologico_micro/macro`, `danno_non_patrimoniale`, `interessi_legali`, `rivalutazione_monetaria`, `decreto_ingiuntivo`, `parcella_avvocato_civile`.

---

### `penalista`

**File**: `content/agents/penalista.md`
**Modello**: `sonnet`

Avvocato penalista esperto in reati, pene, prescrizione, misure cautelari, riti alternativi e procedura penale.

**Regola critica**: Usa SEMPRE `prescrizione_reato()` — il regime dipende dalla data del fatto:

| Data fatto | Regime | Norma |
|-----------|--------|-------|
| Fino al 02/08/2017 | Ordinario (decorre in ogni grado) | artt. 157-161 c.p. (L. 251/2005) |
| 03/08/2017 – 31/12/2019 | Orlando (sospensione fino a 18 mesi dopo condanna di primo grado e di appello) | art. 159 co. 2 c.p. (L. 103/2017) |
| Dal 01/01/2020 | Blocco dopo il primo grado e improcedibilità in appello/Cassazione (2 anni / 1 anno; 3 anni / 18 mesi per impugnazioni entro il 31/12/2024) | art. 161-bis c.p. e art. 344-bis c.p.p. (L. 3/2019, L. 134/2021) |

**Struttura risposte**: FATTO → DIRITTO (norma incriminatrice + elementi) → ANALISI (pena, prescrizione, riti alternativi) → CONCLUSIONI (opzioni strategiche).

**Aree di competenza**: reati contro la persona, reati contro il patrimonio, reati contro la PA, reati societari e tributari, reati informatici.

**Tool principali**: `cite_law`, `prescrizione_reato`, `aumenti_riduzioni_pena`, `pena_concordata`, `conversione_pena`, `fine_pena`, `cerca_giurisprudenza(archivio="penale")`, `leggi_sentenza`, `parcella_avvocato_penale`.

---

### `privacy-specialist`

**File**: `content/agents/privacy-specialist.md`
**Modello**: `sonnet`

Specialista in protezione dei dati: GDPR (Reg. UE 2016/679), Codice Privacy (D.Lgs. 196/2003), provvedimenti Garante, normativa ePrivacy.

**Regola critica**: Per i provvedimenti del Garante, usa `cerca_provvedimenti_garante()` per trovare e `leggi_provvedimento_garante()` per leggere — mai citare provvedimenti a memoria.

**Struttura risposte**: QUADRO NORMATIVO → ANALISI (basi giuridiche, obblighi) → RISCHI E SANZIONI (art. 83, precedenti Garante) → RACCOMANDAZIONI.

**Aree di competenza**: basi giuridiche, diritti degli interessati, data breach, DPIA, trasferimenti internazionali, cookie e tracking, AI e profilazione (art. 22), videosorveglianza, marketing.

**Tool principali**: `cite_law` (GDPR + Codice Privacy), `cerca_provvedimenti_garante`, `leggi_provvedimento_garante`, `ultimi_provvedimenti_garante`, `cerca_brocardi`, `cerca_giurisprudenza`, `leggi_sentenza`.

---

## Hooks — Guardrail automatici

**File**: `plugin/hooks/hooks.json`

### Hook `Stop` e `SubagentStop` — gate sulle citazioni

Si attiva al termine di ogni risposta di Claude e di ogni subagente (lo stesso script
sui due eventi: la citazione non letta di un subagente si ferma dove è stata scritta).

**Tipo**: hook `command` — esegue `hooks/citation-gate.py` (Python 3, nessun modello:
deterministico e senza costo) con il Python 3.12 di `uv`, così non dipende da un
`python3` di sistema (su Windows spesso è l'alias del Microsoft Store). Non apre
l'ambiente del server e parte dalla cartella del plugin, mai da quella aperta
dall'utente: un ambiente Python o una configurazione `uv` di quella cartella non vengono
né usati né letti. Legge le citazioni con il codice del server (`mcp_legal_it.core.citazioni` e
`core.riferimenti`, sola libreria standard: nessuno stack HTTP a ogni turno); se
quell'import fallisce, un lettore ridotto interno allo script tiene in piedi il gate.

**Cosa legge**: il turno, cioè tutto quello che l'assistente ha scritto dall'ultimo
prompt dell'utente: ogni blocco di testo (non solo l'ultimo), il testo scritto con
Write/Edit/MultiEdit in file di prosa (`.md`, `.txt`, `.html`…; il codice sorgente cita,
non afferma) e gli input dei tool documentali (`esporta_atto_docx`, `genera_*`).

**Come riconosce una citazione**: l'atto è risolto con lo stesso resolver di
`cite_law` e identificato dall'URL che `cite_law` interrogherebbe, quindi alias diversi
dello stesso atto coincidono («codice privacy» e «D.Lgs. 196/2003») e atti diversi no
(«art. 2 Cost.» non è «art. 2 c.p.»). La chiave è (atto, articolo con suffisso). L'atto
può stare dopo l'articolo («art. 6, par. 1, lett. f), del Regolamento (UE) 2016/679»)
o prima («D.Lgs. 196/2003, art. 13», «il TUF all'art. 21»); liste e intervalli
(«artt. 1218 e 1223 c.c.») valgono articolo per articolo. Le decisioni sono
(corte, numero, anno): Cassazione, Corte costituzionale, TAR/Consiglio di Stato,
cause CGUE (`C-311/18`).

**Quando una citazione è coperta** (in qualunque punto della sessione, subagenti della
stessa sessione compresi, mai transcript di altre sessioni):
- una norma: un risultato di `cite_law` o `fetch_law_article` che ha restituito proprio
  quell'articolo (non un errore, non un altro articolo; il formato JSON di `cite_law` si
  legge dai suoi `atto` e `articolo`), oppure un risultato di `fetch_full_act` che lo
  contiene;
- una decisione: un risultato `leggi_*`/`cerca_*` (o `*_su_norma`, `ultime_*`) della
  stessa corte che riporta quel numero e quell'anno **nella sua intestazione** (la
  decisione che un lettore ha servito, i risultati che una ricerca ha elencato): i
  precedenti e gli atti citati nel corpo di una sentenza letta non contano, e un numero
  d'atto («D.Lgs. 196/2003») non diventa mai una decisione; un «non trovata» non copre nulla,
  le massime di Brocardi e le mappe di orientamento nemmeno (una massima non è la
  decisione); la ricerca unificata accredita ogni numero alla corte indicata accanto.
  In un elenco («Cass. nn. 500/1999, 600/2000») ogni numero va letto;
- norme e decisioni passate a un dossier di VisuaLex (`omnilex_crea_dossier`, con
  qualunque prefisso del connettore): le righe di `riferimenti` e `sentenze`, che VisuaLex
  ha verificato sulle fonti, tolte quelle che la risposta elenca in `non_entrate` (una
  riga di `sentenze` conta solo se nomina una sola decisione; una risposta fuori dal
  contratto non copre nulla). Se la
  risposta ha `errore`, le liste indicate in `in_sospeso` non contano; un `errore` senza
  `in_sospeso` (VisuaLex precedente alla 1.10.7) non copre nulla. VisuaLex verifica
  l'articolo, non il comma: un dossier non copre i commi di un articolo letto solo in parte
  con `cite_law`, ma senza letture parziali copre il comma così come è scritto (limite noto).

**Ignora**: blocchi di codice e span inline, articoli di documenti che non sono atti
(«art. 5 del contratto», «l'atto di costituzione all'art. 3»), atti citati senza
articolo, il contenuto dei risultati dei tool.

**Via d'uscita**: per una fonte che nessun tool copre (CEDU, codice deontologico
forense, allegati UE…) basta scrivere «fuori copertura» sulla stessa riga.

**Output**: nessun messaggio se tutto è coperto, altrimenti un avviso con le citazioni
non lette e il tool da usare. Consultivo e fail-open: al più un blocco per turno
(`stop_hook_active`), e qualunque errore interno lascia passare la risposta. Su un
transcript di 40 MB gira in circa 0,25 s (timeout 120 s). L'enforcement forte resta sul
gate pre-export delle skill e sul giudizio dell'avvocato.

**Disattivarlo**: la variabile d'ambiente `LEGAL_CITATION_GATE=off` (anche `0`, `false`,
`no`, maiuscole comprese) spegne solo questo hook, senza disabilitare il plugin e i suoi
tool: lo script esce subito, senza leggere il transcript. È pensata per le sessioni di
sviluppo software, dove il gate scatta su codice e documentazione; per il lavoro legale
va lasciato acceso. Per esempio, nel `.claude/settings.local.json` del progetto:
`{"env": {"LEGAL_CITATION_GATE": "off"}}`.

**Per cartella**: `LEGAL_IT_GATE_SKIP_PATHS` elenca le cartelle (percorsi assoluti,
separati da `:` su macOS/Linux, `;` su Windows, oppure da virgole) le cui sessioni il gate
non controlla: se la `cwd` della sessione (dall'input dell'hook, altrimenti quella del
processo) è una di esse o vi è contenuta, l'hook esce subito. Così le sessioni di sviluppo
sotto, ad esempio, `~/CODE` non vengono bloccate, mentre il lavoro legale altrove resta
controllato. È una lista di esclusione: una cartella non elencata resta controllata, le voci
relative sono ignorate e `/a/CODE2` non è dentro `/a/CODE`. I percorsi vanno scritti con
le stesse maiuscole che hanno sul disco, e una cartella con una virgola nel nome non si può
elencare (la virgola separa le voci). Per esempio, nel
`~/.claude/settings.json`: `{"env": {"LEGAL_IT_GATE_SKIP_PATHS": "/path/to/CODE"}}`.

---

Il plugin non registra altri hook: `hooks.json` dichiara solo `Stop` e `SubagentStop`.

---

## Permessi

Il plugin non porta un `settings.json`: in un plugin Claude Code carica solo le chiavi
`agent` e `subagentStatusLine`, e un blocco `permissions` verrebbe ignorato. Ogni comando
dichiara invece i propri `allowed-tools` nel frontmatter, sotto entrambi i prefissi:
`mcp__plugin_legal-it_legal-it__` è il nome che Claude Code dà ai tool quando il server
arriva dal plugin; `mcp__legal-it__` vale per chi lo registra a mano con il nome
`legal-it` (`.mcp.json`, Claude Desktop).

---

## Installazione

### Prerequisiti

1. Server MCP `mcp-legal-it` avviato e configurato in Claude Code (vedere [deployment.md](deployment.md))
2. Claude Code installato

### Installazione da marketplace

```bash
# Dalla root del repo
claude plugin install .claude-plugin/marketplace.json
```

### Installazione manuale

Copia la directory `plugin/` nella configurazione del plugin di Claude Code:

```bash
cp -r plugin/ ~/.claude/plugins/legal-it/
```

Verifica l'installazione:

```bash
claude plugin list
# → legal-it  v2.x.x  30 skills  6 agents
```

### Utilizzo delle skills

```
# In una sessione Claude Code:
/sinistro stradale 15% invalidità, vittima 35 anni
/recupero-credito 50000 2023-06-15 impresa
/compliance-privacy "Acme S.r.l." "marketing email" B2C
/analisi-norma "art. 2043 c.c."
/data-breach confidenzialità 500 "indirizzi email"
```

---

## Creare una nuova skill

Dalla consolidazione del corpus (v3), `content/` è la sorgente unica: `plugin/skills/`,
`plugin/agents/` e `plugin/commands/` sono proiezioni **generate** da
`scripts/corpus/project_claude.py` e vengono ricreate da zero (`rmtree` + rigenerazione)
a ogni esecuzione — qualunque modifica fatta a mano dentro `plugin/skills/` viene persa
alla prossima proiezione. La skill si crea e si modifica sempre sotto `content/skills/`.

### Template

```bash
mkdir -p content/skills/nome-skill
```

Creare `content/skills/nome-skill/SKILL.md`:

```markdown
---
name: nome-skill
description: Descrizione concisa (una riga). Seconda frase con le frasi trigger che attivano la skill.
tools: [nome_tool, altro_tool]
---

# Nome Skill — Titolo

Breve introduzione al workflow.

## Step 1 — Nome step

Istruzione per il modello. Specifica il tool da chiamare:

Chiama `nome_tool(param1=..., param2=...)` con i dati forniti dall'utente.

Se mancano dati essenziali (param1, param2), chiedi all'utente prima di procedere.

## Step 2 — Nome step

Chiama `altro_tool(...)` con il risultato del passo precedente.

## Output

Presenta i risultati in formato tabellare:

| Voce | Valore |
|------|--------|
| ... | ... |

## Note

- Avvertenza 1
- Avvertenza 2
```

Il campo `tools:` elenca i nomi bare (senza prefisso `legal-it:`) dei tool MCP usati dalla
skill: il projector li verifica contro `content/tool-vocabulary.json` e aggiunge il prefisso
`mcp__legal-it__` solo alle proiezioni generate, mai al corpus sorgente.

### Proiezione e commit

Dopo aver scritto o modificato `content/skills/nome-skill/SKILL.md`, rigenerare le
proiezioni:

```bash
python scripts/corpus/project_claude.py
```

Il comando rigenera `plugin/skills/`, `plugin/agents/`, `plugin/commands/` e
`plugin/server/mcp_legal_it/data/references/` da `content/`. Committare **sia** il file sorgente
sotto `content/skills/` **sia** l'intero output rigenerato sotto `plugin/` nello stesso
commit — la CI verifica che le due copie siano allineate.

### Registrazione

La skill viene rilevata automaticamente da Claude Code se si trova (dopo la proiezione)
nella directory `plugin/skills/`. Non è necessario modificare file di configurazione.

### Test manuale

```
/nome-skill argomenti di test
```

Verificare che la skill:
1. Riconosca correttamente i parametri dall'input dell'utente
2. Chieda i dati mancanti se necessario
3. Chiami i tool nell'ordine corretto
4. Produca l'output nel formato atteso

### Link correlati

- Prompt corrispondenti: `mcp_legal_it/prompts.py` — le skills spesso wrappano i prompt MCP
- Tool disponibili: [tools-catalog.md](tools-catalog.md)
- Hooks: modificare `plugin/hooks/hooks.json`
