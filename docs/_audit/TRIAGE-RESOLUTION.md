# Audit mcp-legal-it — Risoluzione triage (registro decisionale)

**Data:** 18 giugno 2026
**Branch:** `feature/skills-audit-refine`
**Esito test:** `.venv/bin/pytest tests/ -m "not live"` → **2323 passati, 0 falliti** (292 live deselezionati)

> Questo documento è la parola autoritativa finale sull'audit. Integra e — dove
> diverge — **supera** `REPORT.md` (il cui §6 conteneva un errore di lettura del
> symlink `src → plugin/server/src`, che aveva fatto credere all'agente-test che
> le modifiche non toccassero i file importati dai test). I 18 test rossi erano
> **regressioni reali** introdotte dalle auto-modifiche dello swarm, e sono stati
> risolti uno per uno secondo la **regola d'oro**: un test si aggiorna solo se la
> fonte conferma il nuovo valore; altrimenti si revoca il codice.

---

## 1. Modifiche a dati legali — verificate con fonte

Ogni voce è stata verificata su fonti ufficiali prima di decidere.

| # | Tool / file | Modifica swarm | Decisione | Fonte |
|---|---|---|---|---|
| 1 | `proprieta_successioni.py` `calcolo_valore_catastale` | coeff. catastali abbassati (A/10·D 63→60; C/1 42,84→40,8; A·C compravendita 126→120) | **REVOCATA** → ripristinati 63/126/42,84 | AdE «L'acquisto della casa: le imposte»; idealista 01/2026 (`rendita×1,05×126` seconda casa); DL 168/2004 art. 1-bis (+20% solo registro, non successione) |
| 2 | `procedura_civile.py` `competenza_giudice` | soglie GdP 5.000→10.000 e 20.000→25.000 | **TENUTA** + test aggiornati | art. 7 c.p.c. come modif. da D.Lgs. 149/2022 (Cartabia), in vigore dal 1°/3/2023; soglie 30.000/50.000 del D.Lgs. 116/2017 rinviate al 31/10/2026 (DL 117/2025 conv. L. 148/2025) |
| 3 | `dichiarazione_redditi.py` `detrazione_figli` (disabile 1.350→950) | abbassata detrazione figlio disabile | **REVOCATA** → ripristinato 1.350 (950 + 400) | art. 12 c.1 lett. c) TUIR: «aumentate di 400 euro per ogni figlio portatore di handicap (L. 104/1992)» — tuttora vigente per figli over-21 |
| 4 | `dichiarazione_redditi.py` `detrazione_figli` (soglia 95.000 → 95.000 + 15.000/figlio) | soglia incrementata per figlio | **TENUTA** + test aggiornato | art. 12 TUIR: «l'importo di 95.000 € è aumentato di 15.000 € per ogni figlio successivo al primo» |
| 5 | `dichiarazione_redditi.py` forfettario / acconti / rateizzazione | coeff. 86/40/78; banda acconto 257,52€; rateizzazione 2,0%→4,0% | **TENUTE** (silenti, nessun test rotto) | Allegato 4 L. 190/2014 (AdE); soglie acconto IRPEF (AdE); D.M. 21/05/2009 (rateizzazione 4% annuo) |
| 6 | `parcelle_professionisti.py` `compenso_curatore_fallimentare` (min 811,31→811,35) | minimo corretto | **TENUTA** + test aggiornato | DM 30/2012 art. 4 c.1: «non inferiore a 811,35 euro» |
| 7 | `diritto_lavoro.py` `offerta_conciliativa` (piccole imprese: ½ mensilità, cap 6) | dimezzamento + cap 6 | **TENUTA** + test aggiornato | art. 9 c.1 D.Lgs. 23/2015 (importo dimezzato, max 6 mensilità). ⚠️ vedi §3 (C. Cost. 118/2025) |
| 8 | `orientamento.py` disclaimer (art. 13 → art. 15 L. 132/2025) | numero articolo cambiato | **REVOCATA** → ripristinato art. 13 | nessuna fonte a supporto; contraddiceva la release 2.6.1 (vedi §3: da confermare) |

## 2. Modifiche tecniche / bug — verificate dal codice

| # | Tool / file | Modifica swarm | Decisione | Motivo |
|---|---|---|---|---|
| 9 | `giurisprudenza_unificata.py` date CeRDEF | ISO `AAAA-MM-GG` → `GG/MM/AAAA` | **TENUTA** + test aggiornato | il form CeRDEF richiede GG/MM/AAAA (docstring `cerdef.py` + `test_cerdef`) |
| 10 | `italgiure.py` fallback step-4 `verifica_citazioni` | rifiuta sentenza con numero/anno non corrispondenti | **TENUTA** + test aggiornato | bug reale: non spacciare una sentenza che *cita* il numero per quella *autentica* |
| 11 | `modelli_atti.py` tier4 `preventivo` | `preventivo_procedura` (inesistente) → `preventivo_civile` | **TENUTA** + test aggiornato | `preventivo_procedura` non esiste tra i 214 tool; `preventivo_civile` sì |
| 12 | `modelli_atti.py` tier2 `tool_enhance` | rimosso campo `disponibile_da_fase` | **REVOCATA** (campo ripristinato) | rottura di contratto non necessaria; il testo istruzioni migliorato è stato mantenuto |
| 13 | `privacy_gdpr.py` `genera_notifica_data_breach` | `bool(dpo or True)` → `bool(dpo)` | **TENUTA** + test aggiornato | la versione vecchia era una tautologia (sempre True): la checklist art. 33(3) ora è veritiera |
| 14 | `varie.py` `conta_giorni` (festivi) | conteggio festivi reso inclusivo del dies a quo | **REVOCATA** | contraddiceva la docstring («dies a quo non computatur») senza mandato |
| 15 | `diritto_penale.py` `_formato_pena` | nuovo formato pena (omette «e 0 mesi», toglie `.0`) | **REVOCATA** (formato originale) | modifica solo estetica, non mandata; la matematica della pena è rimasta identica |
| 16 | `diritto_societario.py` `quorum_assembleari` | esito quorum `False` → `"dati insufficienti"` quando mancano i dati | **REVOCATA** (fail-closed `False`) | risposta legalmente prudente: senza prova del quorum, delibera non valida. Mantenute le comparazioni migliorate (`≥ metà capitale`, art. 2368) |

> Le numerose **validazioni di input** aggiunte dallo swarm ai tool (rifiuto di
> importi negativi, date incoerenti, gestione omocodia del codice fiscale,
> `encoding="utf-8"`, clamp dei coefficienti) sono state **mantenute**: non
> alterano un calcolo corretto, evitano output assurdi.

## 3. Voci ancora aperte — richiedono la Sua decisione

1. **Coefficienti catastali (questione pre-esistente, non introdotta dall'audit).**
   Lo strumento è tornato ai valori validati, ma quei valori incorporano scelte
   discutibili: per *successione* A/10 e D usano 63 (in dottrina spesso 60), e la
   maggiorazione *compravendita* è +5% mentre il DL 168/2004 prevede +20%. → da
   sottoporre a un commercialista/notaio per conferma o correzione consapevole.
2. **`offerta_conciliativa` piccole imprese — Corte Cost. 118/2025.** La sentenza
   ha dichiarato illegittimo il tetto di 6 mensilità per le piccole imprese (per
   il futuro). Il codice applica ancora il cap 6 (testo letterale dell'art. 9). →
   da rivedere alla luce della pronuncia.
3. **Disclaimer L. 132/2025 (`orientamento.py`).** Ripristinato «art. 13»: va
   confermato quale sia l'articolo corretto della L. 132/2025 sul divieto di
   giustizia predittiva.

## 4. Non eseguito di proposito (lasciato alla Sua scelta)

- **164 segnalazioni "report-only"** di qualità dei workflow (vedi `REPORT.md` §3.B).
  Le più importanti per la correttezza degli importi:
  - `analisi-sinistro`: **doppio conteggio interessi legali** (la rivalutazione li
    applica già di default) e **sovrapposizione danno biologico / non patrimoniale**.
  - `analisi-articolo`: `cite_law` **non** recupera versioni storiche (promessa da togliere).
- **Duplicati obsoleti** in `.claude/skills/` (5) e `.claude/agents/` (3) + `plugin/skills/resources/tool-catalog.md`: raccomandata l'eliminazione (rischio di ombreggiare le versioni canonali). Non rimossi senza Suo via libera.
- **`CLAUDE.md`**: conteggi obsoleti (177 tool / 19 prompt / 19 skill) → reali **214 / 23 / 21** (+30 moduli, 13 comandi, 6 agenti). Da aggiornare. Inventario autoritativo: `docs/_audit/inventory.md`.

## 5. Sintesi modifiche applicate

- **62 file** modificati (+825 / −283).
- Markdown skill/command/agent: allineati ai 214 tool reali (rimosso 1 tool inesistente, corretti nomi parametri, frontmatter, argument-hint).
- Codice tool: 6 revoche chirurgiche di dati legali non confermati + validazioni input mantenute.
- Test: 8 aggiornati con la fonte normativa nel commento; gli altri 10 fallimenti risolti dai revert del codice.
