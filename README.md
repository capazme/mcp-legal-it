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

## Skill — 19 workflow guidati

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

### Redazione documenti

| Skill | Descrizione | Tool principali |
|-------|-------------|-----------------|
| `genera-atto` | Generazione atti legali — **100 modelli in 10 categorie** ([dettaglio sotto](#genera-atto--100-modelli-di-atti)) | `genera_modello_atto`, `lista_categorie_atti`, `cite_law` |
| `redazione-contratto` | Supporto contrattuale: verifica norme, clausole tipo da Brocardi, check privacy/DPA se necessario | `cite_law`, `cerca_brocardi`, `analisi_base_giuridica`, `genera_dpa` |

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

## Slash command — 8

| Comando | Descrizione | Logica di routing |
|---------|-------------|-------------------|
| `/legal-it:norma` | Cerca e cita una norma | Fetch testo vigente con `cite_law`, poi offre annotazioni Brocardi o giurisprudenza collegata |
| `/legal-it:sentenza` | Leggi una sentenza di Cassazione | Testo integrale con `leggi_sentenza` se numero+anno noti, altrimenti suggerisce `/ricerca` |
| `/legal-it:ricerca` | Ricerca giurisprudenziale | Routing per contesto: Italgiure, Garante Privacy, CONSOB o normativa |
| `/legal-it:interessi` | Calcolo interessi legali o di mora | Distingue legali (art. 1284 c.c.) da mora commerciale (BCE+8pp, D.Lgs. 231/2002) |
| `/legal-it:parcella` | Calcolo parcella avvocato | Civile/penale/stragiudiziale con dettaglio per fase D.M. 55/2014 (min/medio/max) |
| `/legal-it:codice-fiscale` | Calcolo o decodifica CF | Se riceve un CF lo decodifica, se riceve dati anagrafici lo calcola |
| `/legal-it:scadenza` | Calcolo scadenza processuale | Routing: memorie 183/190, impugnazioni, esecuzioni, prescrizione civile/penale |
| `/legal-it:privacy` | Genera informativa privacy | Routing per tipo: art. 13, cookie, dipendenti, videosorveglianza, DPA, DPIA, data breach |

---

## Agenti — 5 specialisti

| Agente | Specializzazione | Aree coperte |
|--------|------------------|--------------|
| `civilista` | Contratti, responsabilita, successioni, diritti reali, obbligazioni, famiglia | Artt. 1321-1469 c.c. (contratti), art. 2043 ss. (resp. extracontrattuale), artt. 456-768 (successioni), artt. 832-1172 (diritti reali) |
| `penalista` | Reati, pene, prescrizione, misure cautelari, riti alternativi | Gestione automatica regime prescrizione: Bonafede (fatti 2020-2024), Cartabia (dal 2025) |
| `privacy-specialist` | GDPR, Codice Privacy, provvedimenti Garante | Struttura: Quadro normativo &rarr; Analisi &rarr; Rischi e sanzioni &rarr; Raccomandazioni |
| `redattore-atti` | Redazione atti giudiziari, stragiudiziali, procure, relate, attestazioni | Accesso a tutti i 100 modelli di atti + tool di calcolo (CU, interessi, parcelle) |
| `ricerca-giurisprudenziale` | Ricerca sistematica su Italgiure, CONSOB, Garante | Strategia: esplora &rarr; filtra con facets &rarr; cerca con filtri &rarr; leggi decisioni chiave &rarr; Brocardi &rarr; fondamento normativo |

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
