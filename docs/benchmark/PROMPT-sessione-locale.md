# Prompt per la sessione locale di benchmark (Claude Code, modello Fable, ultracode)

Copiare tutto il blocco che segue nella sessione locale aperta nella cartella del repository.

---

ultracode

Lavora nel repository mcp-legal-it, branch `audit-normativa-cartabia` (`git fetch origin && git checkout audit-normativa-cartabia`). Obiettivo: un controllo completo e rigoroso di tutti i 227 tool del server Model Context Protocol (MCP) contro i calcolatori di https://www.avvocatoandreani.it/ e, dove il sito non offre un calcolatore, contro le fonti ufficiali e il testo vigente delle norme. Nessun tool deve restare senza un verdetto documentato. Il costo in token non è un vincolo: coordina il lavoro con workflow a più agenti (fan-out per tool, verifica avversaria degli scostamenti, critico di completezza) e resta tu nel ciclo tra una fase e l'altra.

## Da leggere prima di iniziare

1. `docs/001_mcp-legal-it_AuditNormativa_RV_SAPG.md`: l'audit di settembre 2026, con le correzioni già fatte (paragrafi 4 e 5) e le voci aperte (paragrafo 7) che il benchmark deve chiudere.
2. `docs/benchmark/piano-benchmark-andreani.md` e la versione strutturata `docs/benchmark/piano-benchmark-andreani.json`: la matrice tool per tool con la strategia di benchmark, la pagina del sito individuata tramite ricerca web (da riscontrare con il browser: le pagine non erano apribili quando la matrice è stata scritta), i casi di prova con valori al limite e le note sui tool corretti o declassati dall'audit. In coda al piano c'è il catalogo delle pagine del sito emerso dalla ricerca.
3. `tests/comparison/conftest.py` (helper Playwright: `goto`, `accept_cookies`, `submit_form`, `parse_euro`, `assert_close`), `docs/testing.md`, `CONTRIBUTING.md` (regole su `@sourced`, riga `Precisione:`, riga `Regime:`, audit e golden).

## Ambiente

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m playwright install chromium
.venv/bin/pytest tests/ -m "not live" -q            # deve essere verde prima di toccare qualcosa
.venv/bin/pytest tests/comparison -m live -q          # stato di partenza della suite esistente
.venv/bin/pytest tests/unit/test_cartabia_live.py -m live -q
```

Verifica che la rete raggiunga `www.avvocatoandreani.it` e `www.normattiva.it`; senza rete il lavoro non ha senso.

## Fasi

Fase 0, ricognizione del sito (inline, prima di ogni fan-out). Con Playwright apri l'indice dei servizi del sito e ogni pagina di calcolo raggiungibile da lì; per ciascuna registra URL, campi del modulo (nome, tipo, opzioni), etichette dei risultati. Salva il catalogo in `docs/benchmark/catalogo-andreani.json` e riconcilia la colonna "pagina del sito" del piano: correggi gli URL sbagliati, aggiungi i calcolatori non mappati, segnala i tool per cui il sito non ha nulla. Questa fase è il lavoro preparatorio da cui dipendono le altre: non spawnare agenti prima di averla chiusa.

Fase 1, confronto con il sito (pipeline, un agente per tool con strategia "andreani", circa un centinaio). Ogni agente: legge il tool (docstring, parametri, tabella in `src/data` con il suo blocco `_vintage`), scrive o aggiorna `tests/comparison/test_<tool>.py` con i casi del piano più i casi di confine che individua (date che attraversano agosto, confini degli scaglioni, anni diversi delle tabelle, opzioni enumerate), guida il calcolatore del sito, esegue il tool e restituisce per ogni caso: argomenti, valore del tool, valore del sito, differenza, esito. Non modifica il tool. Per i tool con tabelle annuali, sul sito seleziona lo stesso anno della tabella del tool.

Fase 2, verifica avversaria degli scostamenti (tre agenti indipendenti per ogni scostamento, con lenti diverse: il primo legge la norma con `cite_law()` e ricava il valore corretto; il secondo cerca una differenza di convenzione, arrotondamento, dies a quo, anno della tabella, proroga festiva; il terzo controlla il test, i selettori e il parsing della pagina). Verdetto a maggioranza tra: tool errato, sito errato, differenza di convenzione, test errato. Un verdetto "tool errato" deve citare l'articolo o la tabella ufficiale che lo dimostra: senza fonte primaria il verdetto resta "da chiarire" e va nel report.

Fase 3, correzioni (un agente per tool errato, in worktree isolati se lavorano in parallelo sugli stessi moduli). Ogni correzione: codice, riga `Vigenza:` e `Precisione:` del docstring, test unitario con il valore verificato a mano e il riferimento normativo nel commento, voce nel CHANGELOG, poi `python scripts/audit_tool_annotations.py --write`, `GOLDEN_UPDATE=1 pytest tests/unit/test_golden_calcoli.py -q`, `pytest tests/ -m "not live" -q`. Un tool che va riportato da INDICATIVO a ESATTO lo diventa solo se i valori coincidono con il decreto, non solo con il sito. Le differenze di convenzione si documentano nel test (commento) e nel report, senza modificare il tool. Gli errori del sito si riportano soltanto.

Fase 4, tool senza calcolatore sul sito. Strategia "fonte_ufficiale": confronto con la tabella o il calcolatore dell'ente indicato nel piano (Agenzia delle Entrate, INPS, Banca d'Italia per i tassi effettivi globali medi, Ministero dell'Economia, ISTAT, Ministero della Giustizia, Enasarco) e riconciliazione del blocco `_vintage` della tabella in `src/data` con `scripts/update-data.py`. Strategia "solo_norma": lettura del testo vigente con `cite_law()` e asserzione dei numeri che il tool usa, estendendo `tests/unit/test_cartabia_live.py` o creando `tests/unit/test_norme_live.py` (marcatore `live`). Strategia "smoke_live" (tool di ricerca online): una chiamata reale su un documento noto con verifica dei metadati attesi, in un file live per fonte. Strategia "strutturale" (generatori di documenti): generazione e controllo dei riferimenti normativi del testo prodotto con `verifica_citazioni()`.

Fase 5, completezza a esaurimento. Un agente critico confronta l'elenco dei 227 tool (`READ_ONLY | WRITES_FILES` in `plugin/server/src/tool_annotations.py`) con i verdetti raccolti e con il catalogo del sito: tool senza verdetto, calcolatori del sito senza tool corrispondente (da elencare come possibili nuovi tool, non da implementare), casi di confine non coperti. Quello che trova alimenta un nuovo giro delle fasi 1-4; fermati dopo due giri consecutivi senza nulla di nuovo.

Fase 6, report e consegna. Aggiorna il paragrafo 6 di `docs/001_mcp-legal-it_AuditNormativa_RV_SAPG.md` con la matrice completa (una riga per tool: strategia, casi eseguiti, valore tool, valore sito o fonte, esito, causa, azione), sposta nel paragrafo 5 le voci del paragrafo 7 che risultano chiuse e lascia nel 7 quelle ancora aperte con quanto manca per chiuderle. Aggiorna `docs/testing.md` con i nuovi file di test. Un commit per fase, con messaggi che citano gli articoli applicati; prima di ogni commit `python scripts/audit_tool_annotations.py --check` e `pytest tests/ -m "not live" -q` devono passare. Push su `audit-normativa-cartabia`.

## Regole vincolanti

- Il sito è un benchmark, non una fonte: un tool non si allinea mai al sito senza la norma che lo giustifica.
- Tolleranze: 0,01 euro sugli importi, date esatte, quattro decimali sulle percentuali; ogni tolleranza più ampia va motivata nel test.
- I valori già verificati a mano nei test unitari (in particolare quelli della sospensione feriale in `tests/unit/test_scadenze_termini.py`) si cambiano solo con una fonte primaria: se il sito adotta una convenzione diversa (per esempio fa decorrere dal 1° settembre il termine a mesi che inizia in agosto, dove il tool usa la lettura prudenziale dal 31 agosto) riporta entrambe le date nel report.
- I test che parlano con la rete restano marcati `live`; nulla di ciò che dipende dalla rete entra nella suite predefinita.
- Non modificare le tabelle in `src/data` senza aggiornare il blocco `_vintage` (fonte, data, verifica) e senza rigenerare il golden.
- Nessun trattino lungo nei documenti; le revisioni dei documenti sono marcate SAPG; nessun acronimo senza scioglimento alla prima occorrenza.
- Non committare artefatti del browser, screenshot o cache.

## Criteri di accettazione

1. Ogni tool dei 227 ha una riga nella matrice del paragrafo 6 con un verdetto e, per gli scostamenti, causa e azione.
2. `pytest tests/comparison -m live` copre ogni tool con strategia "andreani" con almeno tre casi, di cui uno al limite.
3. I file live per norme, fonti ufficiali e ricerche online esistono, girano e sono documentati in `docs/testing.md`.
4. Ogni correzione ai tool cita l'articolo o la tabella ufficiale nel docstring, nel test e nel CHANGELOG.
5. `python scripts/audit_tool_annotations.py --check` e `pytest tests/ -m "not live" -q` passano sull'ultimo commit.
6. Il messaggio finale riporta: numero di tool per strategia ed esito, tabella degli scostamenti con verdetto, elenco delle voci ancora aperte con ciò che manca per chiuderle, elenco dei calcolatori del sito senza tool corrispondente.
