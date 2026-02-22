# mcp-legal-it

Server MCP per avvocati e professionisti del diritto italiano: 146 tool di calcolo giuridico-fiscale, consultazione normativa diretta da fonti ufficiali (Normattiva, EUR-Lex, Italgiure, GPDP), 12 prompt workflow e 8 risorse di riferimento statiche.

## Indice

1. [Panoramica](#panoramica)
2. [Installazione](#installazione)
3. [Strumenti — 15 categorie](#strumenti--15-categorie)
4. [Prompt workflow](#prompt-workflow)
5. [Risorse statiche](#risorse-statiche)
6. [Legal Grounding Protocol](#legal-grounding-protocol)
7. [Sviluppo e test](#sviluppo-e-test)
8. [Licenza e disclaimer](#licenza-e-disclaimer)

---

## Panoramica

Il server espone:

- **146 tool di calcolo** organizzati in 15 categorie (rivalutazione monetaria, interessi, scadenze processuali, parcelle, risarcimento danni, diritto penale, successioni, fiscalità, e altro)
- **4 tool di consultazione normativa diretta**: Normattiva, EUR-Lex, Italgiure (Cassazione), Garante Privacy (GPDP)
- **12 prompt workflow** per orchestrare automaticamente i tool su casi d'uso ricorrenti (sinistri, recupero credito, pareri, successioni, ecc.)
- **8 risorse statiche** con tabelle e schemi di riferimento aggiornati

Il server è pensato per essere usato con Claude Desktop o qualsiasi client MCP. I tool di calcolo incorporano già le formule normative: non richiedono chiamate a `cite_law`. I tool di consultazione recuperano il testo ufficiale in tempo reale dalla fonte primaria.

---

## Installazione

**Prerequisiti**: Python >= 3.10

```bash
git clone https://github.com/[owner]/mcp-legal-it
cd mcp-legal-it
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

**Configurazione Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "legal-it": {
      "command": "/path/to/.venv/bin/fastmcp",
      "args": ["run", "/path/to/mcp-legal-it/src/server.py"]
    }
  }
}
```

Sostituire i path con quelli reali del proprio sistema. Riavviare Claude Desktop dopo ogni modifica alla configurazione.

---

## Strumenti — 15 categorie

| # | Categoria | Tool | Esempi |
|---|-----------|:----:|--------|
| 1 | Rivalutazione Monetaria | 11 | `rivalutazione_monetaria`, `adeguamento_canone_locazione`, `rivalutazione_tfr` |
| 2 | Interessi e Tassi | 10 | `interessi_legali`, `interessi_mora`, `verifica_usura` |
| 3 | Scadenze e Termini | 11 | `scadenza_processuale`, `termini_separazione_divorzio`, `scadenze_impugnazioni` |
| 4 | Atti Giudiziari | 23 | `contributo_unificato`, `pignoramento_stipendio`, `decreto_ingiuntivo` |
| 5 | Parcelle Avvocati (D.M. 55/2014) | 12 | `parcella_avvocato_civile`, `parcella_avvocato_penale`, `nota_spese` |
| 6 | Parcelle Altri Professionisti | 11 | `compenso_ctu`, `spese_mediazione`, `compenso_curatore_fallimentare` |
| 7 | Risarcimento Danni | 7 | `danno_biologico_micro`, `danno_biologico_macro`, `danno_parentale` |
| 8 | Diritto Penale | 5 | `prescrizione_reato`, `conversione_pena`, `aumenti_riduzioni_pena` |
| 9 | Proprieta e Successioni | 12 | `calcolo_eredita`, `imposte_successione`, `calcolo_imu` |
| 10 | Investimenti | 5 | `rendimento_bot`, `rendimento_btp`, `confronto_investimenti` |
| 11 | Dichiarazione Redditi | 15 | `calcolo_irpef`, `regime_forfettario`, `ravvedimento_operoso` |
| 12 | Strumenti Vari | 12 | `codice_fiscale`, `verifica_iban`, `prescrizione_diritti` |
| 13 | Consultazione Normativa | 5 | `cite_law`, `fetch_law_article`, `fetch_law_annotations`, `cerca_brocardi`, `download_law_pdf` |
| 14 | Giurisprudenza Cassazione (Italgiure) | 4 | `cerca_giurisprudenza`, `leggi_sentenza`, `giurisprudenza_su_norma`, `ultime_pronunce` |
| 15 | Provvedimenti Garante Privacy | 3 | `cerca_provvedimenti_garante`, `leggi_provvedimento_garante`, `ultimi_provvedimenti_garante` |

**Totale: 146 tool.**

---

## Prompt workflow

| Prompt | Descrizione | Tool principali |
|--------|-------------|-----------------|
| `analisi_sinistro` | Quantifica danno biologico, non patrimoniale e attualizzazione | `danno_biologico_micro`, `danno_biologico_macro`, `rivalutazione_monetaria`, `interessi_legali` |
| `recupero_credito` | Interessi mora + rivalutazione + decreto ingiuntivo + parcella | `interessi_mora`, `decreto_ingiuntivo`, `parcella_avvocato_civile` |
| `causa_civile` | Costi e scadenze di una causa civile | `contributo_unificato`, `scadenza_processuale` |
| `pianificazione_successione` | Quote ereditarie, imposte, adempimenti | `calcolo_eredita`, `imposte_successione` |
| `parere_legale` | Struttura rigorosa con `cite_law` obbligatorio | `cite_law`, `fetch_law_article` |
| `quantificazione_danni` | Personalizza e attualizza le voci di danno | `danno_non_patrimoniale`, `rivalutazione_monetaria` |
| `calcolo_parcella` | Compenso civile, penale o stragiudiziale | `parcella_avvocato_civile`, `parcella_avvocato_penale` |
| `verifica_prescrizione` | Calcola decorso prescrizione civile e penale | `prescrizione_reato`, `prescrizione_diritti` |
| `ricerca_normativa` | Mappa completa di un tema normativo | `cite_law`, `cerca_brocardi`, `cerca_giurisprudenza` |
| `analisi_articolo` | Analisi approfondita di un articolo di legge | `fetch_law_article`, `fetch_law_annotations`, `cerca_brocardi` |
| `confronto_norme` | Compara due norme su uno stesso istituto | `cite_law`, `cerca_giurisprudenza` |
| `mappatura_normativa` | Mappa gerarchica di un settore giuridico | `cite_law`, `cerca_brocardi` |

---

## Risorse statiche

| URI | Contenuto |
|-----|-----------|
| `legal://riferimenti/procedura-civile` | Schema fasi procedura civile post-Cartabia (D.Lgs. 149/2022) |
| `legal://riferimenti/termini-processuali` | Tabella sinottica termini civili 2023-2025 |
| `legal://riferimenti/contributo-unificato` | Scaglioni CU per valore e tipo procedimento (2025) |
| `legal://riferimenti/irpef-detrazioni` | Scaglioni IRPEF 2025-2026 + detrazioni famiglia |
| `legal://riferimenti/interessi-legali` | Storico tassi art. 1284 c.c. dal 2000 al 2026 |
| `legal://riferimenti/checklist-decreto-ingiuntivo` | Presupposti, competenza, opposizione |
| `legal://riferimenti/fonti-diritto-italiano` | Gerarchia fonti, criteri di coordinamento, citazione |
| `legal://riferimenti/codici-e-leggi-principali` | Indice rapido codici, TU, leggi, normativa UE |

---

## Legal Grounding Protocol

Il server applica regole precise su quando e come usare i tool di consultazione. Per chi lo usa tramite LLM:

**Consultazione normativa**

- Prima di citare qualsiasi norma, chiamare `cite_law()` per recuperare il testo vigente da Normattiva o EUR-Lex. Non citare mai norme a memoria.
- Per norme con identificatore noto (es. "art. 2043 c.c.", "Reg. UE 2016/679 art. 17"), passarlo direttamente a `cite_law()`.
- Per approfondire un articolo specifico: `fetch_law_article()`. Per annotazioni dottrinali: `fetch_law_annotations()`. Per la versione PDF: `download_law_pdf()`.

**Giurisprudenza**

- Sentenza Cassazione con numero noto: `leggi_sentenza()` diretto, senza web search.
- Sentenza senza numero: `cerca_giurisprudenza()` per trovare l'identificatore, poi `leggi_sentenza()`.
- Per giurisprudenza su una norma specifica: `giurisprudenza_su_norma()`.

**Provvedimenti Garante Privacy**

- Con docweb noto: `leggi_provvedimento_garante()` diretto.
- Senza docweb: `cerca_provvedimenti_garante()` prima.

**Calcoli**

- I tool di calcolo (categorie 1-12) incorporano già le norme. Non richiedono `cite_law`.
- Il web search e' ammesso solo per la fase di discovery, quando si cerca un identificatore non noto.

**Formati di output**

- Importi: due decimali, separatore migliaia (€ 1.234,56)
- Date: GG/MM/AAAA

---

## Sviluppo e test

```bash
# Installa con dipendenze dev
pip install -e ".[dev]"

# Esegui i test
pytest

# Test live (richiedono connessione internet)
pytest -m live
```

---

## Licenza e disclaimer

Il server si applica esclusivamente alla giurisdizione italiana. I calcoli prodotti dai tool sono indicativi e non sostituiscono il parere di un professionista abilitato. Verificare sempre l'aggiornamento delle norme prima di fare affidamento sui risultati.
