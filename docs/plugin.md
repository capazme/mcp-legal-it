# Claude Code Plugin — mcp-legal-it

> Documentazione del plugin per Claude Code: 17 skills, 3 agenti specializzati, hooks.

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

- **17 skills** invocabili con `/skill-name` — ogni skill orchestra una sequenza di tool MCP
- **3 agenti** configurati come sub-agenti specializzati con istruzioni di sistema e tool preferiti
- **2 hooks** automatici: verifica legal grounding e reminder post-compactação

**Marketplace**: `.claude-plugin/marketplace.json`

```json
{
  "name": "mcp-legal-it",
  "plugins": [{
    "name": "legal-it",
    "source": "./plugin",
    "description": "Plugin legale italiano completo: 161 tool di calcolo, normativa (Normattiva/EUR-Lex), giurisprudenza (Cassazione/Italgiure), compliance GDPR, 17 workflow guidati e 3 agenti specializzati."
  }]
}
```

---

## Struttura del plugin

```
plugin/
├── skills/                     # 17 directory, una per skill
│   ├── sinistro/SKILL.md
│   ├── recupero-credito/SKILL.md
│   ├── causa-civile/SKILL.md
│   └── ... (14 altre)
├── agents/                     # 3 agenti specializzati
│   ├── civilista.md
│   ├── penalista.md
│   └── privacy-specialist.md
├── hooks/
│   └── hooks.json              # Stop hook + SessionStart hook
└── settings.json               # Permessi MCP
```

Ogni skill è una directory con un file `SKILL.md` in formato frontmatter YAML + markdown.

---

## Skills — Workflow guidati

### Tabella delle 17 skills

| Nome | Frasi trigger | Tool principali usati |
|------|--------------|----------------------|
| `sinistro` | "sinistro", "risarcimento danni", "invalidità", "danno biologico" | `danno_biologico_micro/macro`, `danno_non_patrimoniale`, `rivalutazione_monetaria`, `interessi_legali` |
| `recupero-credito` | "recupero credito", "interessi di mora", "decreto ingiuntivo", "creditore" | `interessi_mora`, `rivalutazione_monetaria`, `decreto_ingiuntivo`, `parcella_avvocato_civile` |
| `causa-civile` | "causa civile", "giudizio", "contributo unificato", "scadenze processuali" | `contributo_unificato`, `scadenza_processuale`, `scadenze_impugnazioni`, `preventivo_civile` |
| `pianificazione-successione` | "successione", "eredità", "quote ereditarie", "imposta successione" | `calcolo_eredita`, `imposte_successione`, `imposte_compravendita` |
| `parere-legale` | "parere legale", "opinione giuridica", "analisi giuridica" | `cite_law` (multiplo) |
| `quantificazione-danni` | "quantificazione danno", "danno patrimoniale", "danno morale" | `danno_biologico_micro/macro`, `danno_non_patrimoniale`, `rivalutazione_monetaria`, `interessi_legali` |
| `calcolo-parcella` | "parcella avvocato", "compenso", "nota spese", "D.M. 55/2014" | `parcella_avvocato_civile/penale/stragiudiziale`, `nota_spese` |
| `verifica-prescrizione` | "prescrizione", "termine prescritto", "quando scade" | `prescrizione_diritti`, `prescrizione_reato` |
| `ricerca-normativa` | "normativa su", "quali norme", "quadro normativo", "leggi applicabili" | `cite_law` (multiplo con `include_annotations=true`) |
| `analisi-norma` | "analizza norma", "spiega articolo", "cosa dice l'art." | `cite_law`, `cerca_brocardi` |
| `analisi-articolo` | "analisi approfondita", "ratio legis", "evoluzione storica" | `cite_law`, `cerca_brocardi`, `cite_law` (norme collegate) |
| `analisi-giurisprudenziale` | "giurisprudenza su", "orientamenti Cassazione", "precedenti" | `cerca_giurisprudenza`, `leggi_sentenza`, `cerca_brocardi`, `cite_law` |
| `confronto-norme` | "confronta norme", "quale prevale", "specialità" | `cite_law` × 2 (con annotations) |
| `mappatura-normativa` | "mappa normativa", "normativa di settore", "fonti applicabili" | `cite_law` (per livello gerarchico) |
| `compliance-privacy` | "compliance GDPR", "assessment privacy", "adeguamento GDPR" | `analisi_base_giuridica`, `verifica_necessita_dpia`, `genera_dpia`, `genera_registro_trattamenti`, `genera_informativa_privacy`, `genera_dpa` |
| `data-breach` | "data breach", "violazione dati", "notifica Garante" | `valutazione_data_breach`, `genera_notifica_data_breach`, `calcolo_sanzione_gdpr` |
| `redazione-contratto` | "redigi contratto", "revisione contratto", "clausole" | `cite_law`, `cerca_brocardi`, tool GDPR (se contratto con dati personali) |

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

I 3 agenti sono sub-agenti Claude Code con prompt di sistema specializzati e lista esplicita dei tool preferiti.

### `civilista`

**File**: `plugin/agents/civilista.md`
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

**File**: `plugin/agents/penalista.md`
**Modello**: `sonnet`

Avvocato penalista esperto in reati, pene, prescrizione, misure cautelari, riti alternativi e procedura penale.

**Regola critica**: Usa SEMPRE `prescrizione_reato()` — il regime dipende dalla data del fatto:

| Data fatto | Regime | Norma |
|-----------|--------|-------|
| Fino al 31/12/2019 | Ordinario | artt. 157-161 c.p. |
| 01/01/2020 – 31/12/2024 | Bonafede (sospensione dopo primo grado) | L. 3/2019 |
| Dal 01/01/2025 | Cartabia (improcedibilità per superamento termini) | D.Lgs. 150/2022 |

**Struttura risposte**: FATTO → DIRITTO (norma incriminatrice + elementi) → ANALISI (pena, prescrizione, riti alternativi) → CONCLUSIONI (opzioni strategiche).

**Aree di competenza**: reati contro la persona, reati contro il patrimonio, reati contro la PA, reati societari e tributari, reati informatici.

**Tool principali**: `cite_law`, `prescrizione_reato`, `aumenti_riduzioni_pena`, `pena_concordata`, `conversione_pena`, `fine_pena`, `cerca_giurisprudenza(archivio="penale")`, `leggi_sentenza`, `parcella_avvocato_penale`.

---

### `privacy-specialist`

**File**: `plugin/agents/privacy-specialist.md`
**Modello**: `sonnet`

Specialista in protezione dei dati: GDPR (Reg. UE 2016/679), Codice Privacy (D.Lgs. 196/2003), provvedimenti Garante, normativa ePrivacy.

**Regola critica**: Per i provvedimenti del Garante, usa `cerca_provvedimenti_garante()` per trovare e `leggi_provvedimento_garante()` per leggere — mai citare provvedimenti a memoria.

**Struttura risposte**: QUADRO NORMATIVO → ANALISI (basi giuridiche, obblighi) → RISCHI E SANZIONI (art. 83, precedenti Garante) → RACCOMANDAZIONI.

**Aree di competenza**: basi giuridiche, diritti degli interessati, data breach, DPIA, trasferimenti internazionali, cookie e tracking, AI e profilazione (art. 22), videosorveglianza, marketing.

**Tool principali**: `cite_law` (GDPR + Codice Privacy), `cerca_provvedimenti_garante`, `leggi_provvedimento_garante`, `ultimi_provvedimenti_garante`, `cerca_brocardi`, `cerca_giurisprudenza`, `leggi_sentenza`.

---

## Hooks — Guardrail automatici

**File**: `plugin/hooks/hooks.json`

### Hook `Stop` — Legal Grounding Verifier

Si attiva al termine di ogni risposta Claude.

**Modello**: Haiku (veloce, economico)

**Funzione**: Verifica che ogni norma citata nella risposta abbia una corrispondente chiamata `cite_law()` nel transcript. Se trova norme citate senza verifica, elenca quelle mancanti e chiede di richiamare `cite_law()` prima di finalizzare.

**Ignora**: norme all'interno dei risultati di tool (già verificate), riferimenti generici senza numero di articolo, calcoli numerici (i tool applicano le norme internamente).

**Output**: `"OK"` se tutto verificato, oppure `"ATTENZIONE: le seguenti norme sono state citate senza verifica con cite_law(): [elenco]."`.

---

### Hook `SessionStart` — Context Recovery

Si attiva all'inizio di ogni sessione (inclusa dopo compactazione del contesto).

**Modello**: Haiku

**Funzione**: Inietta il Legal Grounding Protocol dopo la compactazione del contesto, quando le istruzioni originali potrebbero essere state perse:

> "LEGAL GROUNDING PROTOCOL — chiama cite_law() PRIMA di citare qualunque norma. Mai usare la conoscenza pregressa per il contenuto di articoli di legge. Per sentenze con numero noto: leggi_sentenza() DIRETTO, no web search. Per provvedimenti Garante con docweb noto: leggi_provvedimento_garante() DIRETTO."

---

## Permessi

**File**: `plugin/settings.json`

```json
{
  "permissions": {
    "allow": ["mcp__legal-it__*"]
  }
}
```

Il plugin concede permesso automatico a tutti i tool MCP del server `legal-it`. Non sono richieste conferme manuali per le chiamate ai tool durante l'esecuzione delle skills.

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
# → legal-it  v1.x.x  17 skills  3 agents
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

### Template

```bash
mkdir -p plugin/skills/nome-skill
```

Creare `plugin/skills/nome-skill/SKILL.md`:

```markdown
---
name: nome-skill
description: Descrizione concisa (una riga). Seconda frase con le frasi trigger che attivano la skill.
argument-hint: "[param1: opzione1|opzione2] [param2 opzionale]"
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

### Registrazione

La skill viene rilevata automaticamente da Claude Code se si trova nella directory `plugin/skills/`. Non è necessario modificare file di configurazione.

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

- Prompt corrispondenti: `src/prompts.py` — le skills spesso wrappano i prompt MCP
- Tool disponibili: [tools-catalog.md](tools-catalog.md)
- Hooks: modificare `plugin/hooks/hooks.json`
