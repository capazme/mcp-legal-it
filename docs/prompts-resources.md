# Prompts e Resources — mcp-legal-it

> Documentazione dei 13 workflow guidati (`@mcp.prompt`) e delle 9 risorse statiche (`@mcp.resource`).

## Indice

- [Prompts — Workflow guidati](#prompts--workflow-guidati)
  - [Tabella riepilogativa](#tabella-riepilogativa)
  - [Dettaglio per prompt](#dettaglio-per-prompt)
- [Resources — Risorse statiche](#resources--risorse-statiche)
  - [Tabella risorse](#tabella-risorse)
- [Come usare prompts e resources da un client MCP](#come-usare-prompts-e-resources-da-un-client-mcp)

---

## Prompts — Workflow guidati

**File sorgente**: `src/prompts.py`

I prompt MCP sono workflow strutturati che guidano il modello LLM in sequenze di chiamate ai tool. Ogni prompt riceve parametri utente, li incorpora in un testo di istruzione e definisce l'ordine esatto dei tool da chiamare.

### Tabella riepilogativa

| Nome | Parametri | Descrizione | Sequenza tool |
|------|-----------|-------------|---------------|
| `analisi_sinistro` | `tipo_sinistro`, `percentuale_invalidita`, `eta_vittima` | Quantificazione completa sinistro stradale/sanitario/lavoro | `danno_biologico_micro/macro` → `danno_non_patrimoniale` → `rivalutazione_monetaria` → `interessi_legali` |
| `recupero_credito` | `importo`, `tipo_credito`, `data_scadenza` | Piano di recupero credito con costi procedura | `interessi_mora` → `rivalutazione_monetaria` → `decreto_ingiuntivo` → `parcella_avvocato_civile` |
| `causa_civile` | `valore_causa`, `rito`, `grado` | Pianificazione causa con costi e scadenze | `contributo_unificato` → `scadenza_processuale` → `scadenze_impugnazioni` → `preventivo_civile` |
| `pianificazione_successione` | `valore_asse`, `grado_parentela`, `numero_eredi` | Quote ereditarie, imposte e adempimenti | `calcolo_eredita` → `imposte_successione` → `imposte_compravendita` |
| `parere_legale` | `area_diritto`, `quesito` | Parere strutturato con citazioni normative verificate | `cite_law` (multiplo) |
| `quantificazione_danni` | `tipo_danno`, `importo_o_percentuale`, `eta_vittima` | Quantificazione biologico/patrimoniale/morale | `danno_biologico_micro/macro` o `danno_non_patrimoniale` → `rivalutazione_monetaria` → `interessi_legali` |
| `calcolo_parcella` | `tipo_attivita`, `valore_causa` | Parcella avvocato civile/penale/stragiudiziale con nota spese | `parcella_avvocato_civile/penale/stragiudiziale` → `nota_spese` |
| `verifica_prescrizione` | `tipo`, `descrizione_fatto`, `data_fatto` | Prescrizione civile o penale con stato (PRESCRITTA/IN SCADENZA) | `prescrizione_diritti` o `prescrizione_reato` |
| `ricerca_normativa` | `tema`, `area_diritto` | Ricerca normativa completa con gerarchia fonti | `cite_law` (multiplo, con `include_annotations=true`) |
| `analisi_articolo` | `riferimento_norma` | Analisi approfondita di un articolo: testo, ratio, giurisprudenza | `cite_law` → `cerca_brocardi` → `cite_law` (norme collegate) |
| `confronto_norme` | `norma_1`, `norma_2`, `contesto?` | Confronto due norme: differenze, prevalenza, coordinamento | `cite_law` × 2 (con annotations) |
| `mappatura_normativa` | `settore`, `attivita_specifica?` | Mappa normativa completa per settore: Costituzione → UE → Nazionale → Secondario | `cite_law` (multiplo per livello) |
| `analisi_giurisprudenziale` | `tema`, `archivio?` | Analisi orientamenti giurisprudenziali con lettura sentenze chiave | `cerca_giurisprudenza` → `leggi_sentenza` → `cerca_brocardi` → `cite_law` |
| `compliance_privacy` | `titolare`, `tipo_trattamento`, `contesto` | Assessment GDPR completo | `analisi_base_giuridica` → `verifica_necessita_dpia` → `genera_dpia?` → `genera_registro_trattamenti` → `genera_informativa_privacy` → `genera_dpa?` |

### Dettaglio per prompt

#### `analisi_sinistro`

Workflow per sinistri stradali, sanitari o da lavoro. Seleziona automaticamente `danno_biologico_micro` (IP ≤ 9%) o `danno_biologico_macro` (IP > 9%) in base alla percentuale di invalidità. Output in tabella riepilogativa con voce per voce. Avverte che i valori sono indicativi e non sostituiscono la valutazione medico-legale.

#### `recupero_credito`

Distingue tra crediti commerciali (D.Lgs. 231/2002, tasso BCE + 8 punti) e privati (art. 1284 c.c.). Nota che interessi di mora e rivalutazione non si cumulano (Cass. SS.UU. 16601/2017). Produce tabella riepilogativa delle voci e tabella costi procedura.

#### `causa_civile`

Parametro `rito`: `ordinario` | `sommario` | `lavoro`. Parametro `grado`: `primo` | `appello` | `cassazione`. Include segnalazione sospensione feriale (1-31 agosto) e valutazione mediazione obbligatoria (D.Lgs. 28/2010).

#### `parere_legale`

Struttura rigida con sezioni: FATTO → QUESITO → DIRITTO (quadro normativo + giurisprudenza + dottrina) → ANALISI → CONCLUSIONI. Impone l'uso obbligatorio di `cite_law` per ogni norma citata.

#### `verifica_prescrizione`

Per la **prescrizione civile**: distinzione tra termine ordinario (10 anni, art. 2946 c.c.) e termini brevi (5 anni per risarcimento, 2 anni per assicurazione, 1 anno per trasporti). Per la **prescrizione penale**: applica automaticamente il regime corretto in base alla data del fatto (ordinario pre-2020, Bonafede 2020-2024, Cartabia dal 2025).

#### `analisi_giurisprudenziale`

Workflow in 5 fasi: panoramica (15 risultati) → approfondimento 2-3 decisioni chiave → annotazioni Brocardi → fondamento normativo → sintesi strutturata. Privilegia le Sezioni Unite. Vieta la citazione di numeri di sentenza a memoria.

#### `compliance_privacy`

Assessment GDPR end-to-end. Se `verifica_necessita_dpia` restituisce `dpia_necessaria=true`, esegue il passo 2b (`genera_dpia`). Se ci sono responsabili esterni, aggiunge il passo 5 (`genera_dpa`). Produce checklist operativa finale con tutti gli adempimenti.

---

## Resources — Risorse statiche

**File sorgente**: `src/resources.py`

Le risorse MCP sono documenti di riferimento statici accessibili tramite URI `legal://`. Contengono tabelle, checklist e schemi normativi aggiornati.

### Tabella risorse

| URI | Nome | Contenuto |
|-----|------|-----------|
| `legal://riferimenti/procedura-civile` | Procedura Civile Ordinaria | Schema fasi e termini post-Cartabia (D.Lgs. 149/2022): primo grado, appello, cassazione, sospensione feriale |
| `legal://riferimenti/termini-processuali` | Termini Processuali Chiave | Tabella sinottica: primo grado, impugnazioni, procedimenti speciali, mediazione e negoziazione assistita |
| `legal://riferimenti/contributo-unificato` | Contributo Unificato — Tabella Scaglioni | Scaglioni 2025 per cause ordinarie, impugnazioni (×1,5 appello, ×2 cassazione), procedimenti speciali, esenzioni |
| `legal://riferimenti/irpef-detrazioni` | IRPEF 2025-2026 — Scaglioni e Detrazioni | Scaglioni IRPEF (3 aliquote: 23%, 35%, 43%), detrazioni lavoro dipendente, pensione, carichi di famiglia, no tax area, addizionali |
| `legal://riferimenti/interessi-legali` | Storico Tassi Interessi Legali | Tassi art. 1284 c.c. dal 2000 al 2026, tassi di mora D.Lgs. 231/2002 (BCE + 8pp), note applicative (anatocismo, rivalutazione) |
| `legal://riferimenti/checklist-decreto-ingiuntivo` | Checklist Decreto Ingiuntivo | Presupposti, competenza (GDP/Tribunale), contenuto ricorso, provvisoria esecutività, costi, post-emissione, opposizione |
| `legal://riferimenti/fonti-diritto-italiano` | Gerarchia Fonti del Diritto Italiano | Gerarchia 5 livelli (Costituzione → UE → Primarie → Secondarie → Usi), criteri antinomie, tipi di abrogazione, guida formato citazione |
| `legal://riferimenti/codici-e-leggi-principali` | Codici e Leggi Principali — Riferimento Rapido | Indice ragionato: codici classici, testi unici, leggi fondamentali, normativa UE chiave (GDPR, AI Act, DORA, DSA, NIS2, EHDS) |
| `legal://riferimenti/gdpr-checklist` | GDPR Compliance — Checklist Operativa | 8 sezioni: mappatura trattamenti, basi giuridiche, informative, DPA (art. 28), DPIA, data breach, sanzioni (art. 83), scadenze |

---

## Come usare prompts e resources da un client MCP

### Invocare un prompt

I prompt MCP vanno invocati passando tutti i parametri richiesti. Esempio con il client Python di FastMCP:

```python
# Via Claude Desktop / Claude Code
# Prompt analisi_sinistro:
result = await client.get_prompt(
    "analisi_sinistro",
    arguments={
        "tipo_sinistro": "stradale",
        "percentuale_invalidita": 15.0,
        "eta_vittima": 35,
    }
)

# Prompt compliance_privacy:
result = await client.get_prompt(
    "compliance_privacy",
    arguments={
        "titolare": "Acme S.r.l.",
        "tipo_trattamento": "profilazione utenti e-commerce",
        "contesto": "B2C",
    }
)
```

In Claude Desktop/Code, i prompt sono elencati sotto il menu `/` o nella palette comandi. Si invocano con il nome senza prefisso (es. `analisi_sinistro`).

### Leggere una risorsa

Le risorse sono accessibili tramite il loro URI `legal://`:

```python
# Tramite MCP client
content = await client.read_resource("legal://riferimenti/gdpr-checklist")

# In Claude Desktop/Code: il modello può accedere alle risorse
# semplicemente citando il loro URI nel contesto della conversazione
```

Le risorse sono più utili come contesto di background; i tool di calcolo applicano già le tabelle rilevanti internamente (il tool `contributo_unificato` usa `src/data/contributo_unificato.json`, non la risorsa testuale).

### Quando usare i prompt vs. chiamare i tool direttamente

| Scenario | Approccio consigliato |
|----------|----------------------|
| Analisi complessa multi-step (sinistro, recupero credito) | Prompt — orchestra la sequenza corretta |
| Calcolo singolo (interessi, IRPEF) | Tool diretto |
| Ricerca normativa con giurisprudenza | Prompt `analisi_articolo` o `analisi_giurisprudenziale` |
| Generazione documento GDPR singolo | Tool diretto (`genera_informativa_privacy`) |
| Assessment GDPR completo | Prompt `compliance_privacy` |
| Riferimento rapido tabelle | Resource `legal://riferimenti/...` |

### Link correlati

- Tool di calcolo: vedere [tools-catalog.md](tools-catalog.md)
- Plugin e skills: vedere [plugin.md](plugin.md) — le skills del plugin wrappano i prompt
- Librerie interne usate dai tool: vedere [lib-reference.md](lib-reference.md)
