> ⚠️ **AGGIORNAMENTO 18/06/2026 — questo report è stato SUPERATO dalla risoluzione.**
> La triage è stata completata: i 18 test sono verdi, i dati legali verificati con
> fonte (catastali/IRPEF disabile/disclaimer revocati; GdP/forfettario/curatore/
> conciliazione confermati e test aggiornati). Documento autoritativo finale:
> [`TRIAGE-RESOLUTION.md`](./TRIAGE-RESOLUTION.md). Nota: il §6 qui sotto contiene
> un errore (lettura del symlink `src/`): i 18 fallimenti **erano** causati dalle
> modifiche, non preesistenti.

# Audit mcp-legal-it — Report finale

**Data:** 18 giugno 2026
**Oggetto:** Verifica di coerenza e correttezza di tutto il "contenuto" del server legale (tool di calcolo, schede normative, workflow guidati, comandi e agenti).
**Destinatario:** lo Studio (avvocato titolare). Il linguaggio del corpo del report e non tecnico; i dettagli tecnici sono in appendice.

> AVVISO IMPORTANTE (leggere per primo)
> Questo audit **NON e pronto per essere messo in produzione cosi com'e**. Le correzioni di forma e i nuovi controlli di sicurezza vanno bene, ma alcune modifiche hanno toccato **numeri che pesano su importi e termini di legge** (coefficienti catastali, detrazioni IRPEF, competenza del Giudice di Pace, ecc.). Queste modifiche **non sono ancora state confermate con la fonte normativa** e hanno fatto fallire 18 test automatici. Servono la Sua verifica e la Sua firma prima di rendere effettive quelle parti. I dettagli sono nelle sezioni 3 e 5.

---

## 1. Sintesi per il titolare (Executive summary)

**Cosa e stato verificato.**
E stato passato in rassegna l'intero "sapere" del server legale, controllando che ogni pezzo dica il vero e sia coerente con gli strumenti realmente disponibili:

- **21 skill** (i percorsi guidati tipo "analisi sinistro", "calcolo parcella", "recupero credito");
- **13 comandi** rapidi (es. `/parcella`, `/norma`, `/sentenza`);
- **6 agenti** (assistenti specializzati, es. ricerca giurisprudenziale);
- **23 prompt** e **15 risorse** statiche (schede di riferimento: scaglioni IRPEF, tassi legali, ecc.);
- **30 moduli di strumenti** per un totale di **214 tool** (calcoli, ricerca normativa e giurisprudenziale).

**Cosa e stato corretto in automatico.**
Sono stati modificati **54 file** con circa 250 correzioni applicate. La grande maggioranza sono interventi **a basso rischio**: allineamento dei nomi degli strumenti citati nelle istruzioni, controlli di validazione sugli importi in ingresso (per evitare risultati assurdi), correzioni di refusi e di riferimenti errati. Il dettaglio e nella sezione 2.

**Cosa richiede la Sua firma.**
Tre categorie di interventi **non possono essere accettate senza la Sua conferma**, perche incidono su importi/termini con valore legale e non sono ancora state riscontrate con la fonte ufficiale:

1. **Coefficienti catastali** per il calcolo del valore degli immobili (sezione 3 — la modifica piu pericolosa: tende a **sottostimare** la base imponibile).
2. **Detrazioni IRPEF per figli a carico** (in particolare figlio disabile) e **coefficienti del regime forfettario**.
3. **Soglie di competenza del Giudice di Pace** e alcuni riferimenti normativi (es. articolo della L. 132/2025 nel disclaimer).

Inoltre **164 osservazioni "solo segnalazione"** (sezione 3) riguardano incoerenze nei workflow che la procedura ha scelto di **non** correggere da sola, perche richiedono una decisione di merito.

**Stato del cantiere in una riga:** correzioni di forma OK; **18 test rossi** e modifiche legali non verificate **bloccano il rilascio**. Da NON committare/deployare prima della Sua revisione (sezione 5).

---

## 2. Correzioni applicate automaticamente

Tutte sotto `plugin/`. Raggruppate per tipo. (L'elenco completo file-per-file e nell'inventario — appendice, sezione 6.)

### 2.1 Skill (9 file modificati)
Allineamento dei percorsi guidati agli strumenti realmente esistenti e ai loro nomi corretti.

| File | Correzioni | Cosa / Perche |
|---|---|---|
| `plugin/skills/analisi-giurisprudenziale/SKILL.md` | 2 | Riferimenti a tool/nomi aggiornati alla versione canonica. |
| `plugin/skills/analisi-sinistro/SKILL.md` | 3 | Allineamento passi del workflow agli strumenti corretti. |
| `plugin/skills/calcolo-parcella/SKILL.md` | 1 | Correzione riferimento strumento. |
| `plugin/skills/causa-civile/SKILL.md` | 2 | Allineamento strumenti per scadenze/parcelle. |
| `plugin/skills/genera-atto/SKILL.md` | 3 | Riferimenti a modelli/strumenti aggiornati. |
| `plugin/skills/mappatura-normativa/SKILL.md` | 1 | Correzione riferimento. |
| `plugin/skills/pianificazione-successione/SKILL.md` | 2 | Allineamento strumenti calcolo quote/imposte. |
| `plugin/skills/recupero-credito/SKILL.md` | 2 | Allineamento strumenti interessi/decreto ingiuntivo. |
| `plugin/skills/verifica-prescrizione/SKILL.md` | 1 | Correzione riferimento. |

> Nota: **12 skill su 21 non sono state modificate.** Questo non significa che siano state "approvate": significa solo che la procedura non vi ha applicato modifiche. Vedi sezione 4 (rischi residui sulla copertura).

### 2.2 Comandi (12 file modificati)
Correzione dei nomi degli strumenti invocati dai comandi rapidi, cosi che `/comando` chiami davvero il tool giusto.

`codice-fiscale.md` (1), `digest.md` (1), `giurisprudenza.md` (1), `interessi.md` (4), `norma.md` (2), `parcella.md` (3), `parere.md` (1), `privacy.md` (2), `release.md` (1), `ricerca.md` (1), `scadenza.md` (1), `sentenza.md` (1).
**Perche:** evitare che un comando punti a uno strumento inesistente o rinominato (causa tipica di "il comando non fa nulla").

### 2.3 Agenti (1 file modificato)
`plugin/agents/ricerca-giurisprudenziale.md` (3): allineamento dell'elenco strumenti autorizzati e dei riferimenti interni.

### 2.4 Prompt e Risorse (2 file modificati)
- `plugin/server/src/prompts.py` (2): correzioni nei testi dei prompt guidati.
- `plugin/server/src/resources.py` (4): aggiornamento dei riferimenti nelle schede statiche `legal://`.

### 2.5 Tool — strumenti di calcolo e ricerca (30 moduli esaminati)
Tipologia prevalente di intervento: **controlli di validazione degli input** (es. rifiutare importi negativi, date incoerenti) e correzione di nomi/parametri. Questi interventi **non cambiano il risultato di un calcolo corretto**; impediscono solo output insensati.

Moduli con correzioni applicate (numero modifiche / saltate):
`atti_giudiziari.py` 8/0, `cerdef.py` 2/1, `cgue.py` 2/5, `consob.py` 4/0, `corte_cost.py` 3/0, `crisi_impresa.py` 4/0, `dichiarazione_redditi.py` 10/0, `diritto_lavoro.py` 6/1, `diritto_penale.py` 8/0, `diritto_societario.py` 8/1, `fatturazione_avvocati.py` 4/1, `gazzetta.py` 4/5, `giurisprudenza_unificata.py` 4/0, `giustizia_amm.py` 1/4, `investimenti.py` 5/0, `italgiure.py` 2/0, `legal_citations.py` 3/1, `modelli_atti.py` 5/5, `orientamento.py` 5/0, `parcelle_professionisti.py` 6/0, `privacy_gdpr.py` 8/0, `procedura_civile.py` 3/1, `proprieta_successioni.py` 7/0, `risarcimento_danni.py` 5/0, `rivalutazioni_istat.py` 10/0, `scadenze_termini.py` 12/0, `tassi_interessi.py` 8/0, `varie.py` 8/0.

Moduli **non modificati**: `eu_implementation.py` (0/4), `gpdp.py` (0/4). Vedi sezione 4.

> ATTENZIONE: tra le modifiche "applicate" sopra rientrano anche **alcune che toccano numeri di rilevanza legale** (in `proprieta_successioni.py`, `dichiarazione_redditi.py`, `procedura_civile.py`, `orientamento.py`). Sono state tecnicamente applicate al codice ma **non sono validate**: le ho elencate nella sezione 3 perche richiedono la Sua firma, e sono la causa principale dei test rossi (sezione 5).

---

## 3. Da approvare manualmente (solo segnalazione — richiede la Sua firma)

Questi punti **non sono stati corretti automaticamente**. Per ciascuno indico la fonte/evidenza. Le decisioni di merito spettano a Lei.

### 3.A — Modifiche a numeri di legge gia scritte nel codice ma NON verificate (priorita massima)

Queste sono state materialmente applicate, ma vanno **confermate con la fonte o revocate**. Sono il cuore del blocco al rilascio.

1. **Coefficienti catastali — `proprieta_successioni.py` / `calcolo_valore_catastale` — RISCHIO PIU ALTO.**
   I moltiplicatori catastali sono stati abbassati in modo sistematico (es. categoria A compravendita 126→120; C/1 42,84→40,8; A/10 e D/5 63→60). I valori originari incorporano la **rivalutazione del 5%** (art. 3 c. 48 L. 662/1996) e la maggiorazione del 20% per le compravendite (DL 168/2004). La modifica sembra **rimuovere il 5%** e parificare compravendita/successione: il risultato e una **sottostima della base imponibile catastale** in ogni operazione immobiliare.
   *Fonte da verificare:* DL 168/2004 + L. 662/1996 art. 3 c. 48. *Raccomandazione:* **revocare o confermare prima di ogni altra cosa.**

2. **Detrazione figli a carico — `dichiarazione_redditi.py` / `detrazione_figli`.**
   La detrazione IRPEF per figlio disabile e stata abbassata da 1.350€ a 950€ (rendendo il figlio disabile over-21 pari a un figlio normale); modificate anche la soglia (+15.000€ per figlio) e il coefficiente.
   *Fonte da verificare:* art. 12 TUIR (testo vigente).

3. **Regime forfettario + acconti — `dichiarazione_redditi.py` / `irpef_scaglioni.json`.**
   Rimappati i coefficienti di redditivita (es. costruzioni 62→86; commercio ingrosso 47,73→40; professionali 78); introdotta una soglia di acconto in pagamento unico a 257,52€; interesse di rateizzazione 2,0%→4,0%; riferimento assegno unico a "Importi 2026".
   *Fonte da verificare:* allegato L. 190/2014 (coefficienti); disciplina acconti IRPEF; tasso di rateizzazione vigente.

4. **Competenza Giudice di Pace — `procedura_civile.py` / `competenza_giudice`.**
   Soglie alzate: ordinaria 5.000→10.000€; circolazione 20.000→25.000€ (commenti citano Cartabia + D.Lgs. 116/2017 con efficacia differita al 31/10/2026). Plausibile ma **non confermato**: sposta cause da Tribunale a GdP.
   *Fonte da verificare:* art. 7 c.p.c. post-Cartabia + entrata in vigore D.Lgs. 116/2017.

5. **Disclaimer orientamento — `orientamento.py`.**
   Riferimento normativo cambiato da "art. 13, L. 132/2025" a "art. 15, L. 132/2025". Attenzione: questo file e stato gia toccato di proposito nella release 2.6.1 — la modifica potrebbe **contraddire un lavoro precedente** e passa "in silenzio" perche nessun test fissa il numero dell'articolo.
   *Fonte da verificare:* L. 132/2025, articolo corretto del disclaimer.

### 3.B — Incoerenze di workflow segnalate (164 osservazioni "report-only")

La procedura ha registrato **164 segnalazioni** che richiedono una scelta, senza correggere. Le piu rilevanti per la qualita del lavoro:

- **`analisi-sinistro` — doppio conteggio degli interessi legali (gravita ALTA).** Il tool di rivalutazione applica gia, per impostazione predefinita, gli interessi legali anno per anno sul capitale rivalutato (criterio Cass. SU 1712/1995); il workflow poi li ricalcola separatamente e li mostra come riga a parte: **gli interessi finiscono contati due volte.** *Soluzione proposta:* disattivare gli interessi nella rivalutazione (`con_interessi_legali=false`) oppure eliminare il passo separato — scegliere un solo metodo.
  *Evidenza:* `rivalutazioni_istat.py` (default `con_interessi_legali=True`) + `tassi_interessi.py:interessi_legali`.
- **`analisi-sinistro` — sovrapposizione danno biologico/non patrimoniale (MEDIA).** Il tool del danno non patrimoniale ricomprende gia il biologico: usandolo dopo il passo del biologico, l'importo viene gonfiato. *Soluzione:* usare un solo strumento per la componente biologico+morale+esistenziale.
- **`analisi-articolo` — `cite_law` non recupera versioni storiche (MEDIA).** L'istruzione promette di recuperare la versione precedente di un articolo, ma lo strumento restituisce solo il testo **vigente**. *Soluzione:* togliere la promessa; l'evoluzione storica e gia coperta dalle annotazioni Brocardi.
- **`calcolo-parcella` (varie, MEDIA/BASSA).** La tabella Minimo/Medio/Massimo richiede **tre chiamate** allo stesso tool (una per livello), non una sola; il passo "nota spese" richiede di trasformare le fasi in voci tipizzate; il tool `fattura_avvocato` e dichiarato ma mai usato.
- **`causa-civile` — strumento per le scadenze di rito non esistente (ALTA).** Il passo punta a una funzionalita non disponibile per i termini denominati specifici del rito.

> Lettura consigliata: queste 164 voci sono utili come "lista di miglioramenti di qualita". Nessuna e bloccante per la sicurezza, ma alcune (doppio conteggio interessi, sovrapposizione danni) producono **importi sbagliati** se l'assistente segue il workflow alla lettera.

---

## 4. Drift e duplicati (copie obsolete e conteggi non aggiornati)

### 4.1 Copie obsolete in `.claude/` (duplicati che ombreggiano le versioni buone)
Esistono skill duplicate sotto `.claude/skills/` che sono **versioni vecchie** delle skill ufficiali in `plugin/skills/`. Sono tracciate da git e possono **sovrascrivere/oscurare** quelle aggiornate (collisione di nome).

- `.claude/skills/analisi-giurisprudenziale/SKILL.md` (vecchia, 22 feb) vs `plugin/skills/analisi-giurisprudenziale/SKILL.md` (canonica, 31 mar). La vecchia ignora gli strumenti nuovi e il passo obbligatorio "presenta i risultati e chiedi all'utente quali sentenze leggere". **Raccomandazione: ELIMINARE la copia in `.claude/`.**
- `.claude/skills/analisi-norma/SKILL.md` — orfano: la skill ufficiale e stata rinominata `analisi-articolo`. **Raccomandazione: ELIMINARE.**
- `.claude/skills/parere-legale/SKILL.md` — ulteriore duplicato obsoleto. **Raccomandazione: ELIMINARE** (allineare alla versione plugin).

> Perche conta per Lei: con due skill dallo stesso nome registrate, l'assistente potrebbe usare quella **vecchia e meno completa** senza che ce ne accorgiamo.

### 4.2 Conteggi non aggiornati in CLAUDE.md (drift documentale)
Il file `mcp-legal-it/CLAUDE.md` riporta ancora **"177 tool / 19 prompt / 19 skill"**. I conteggi reali su disco (dall'inventario) sono:

| Voce | CLAUDE.md (vecchio) | Reale (inventario) |
|---|---|---|
| Tool | 177 | **214** |
| Moduli tool | — | **30** |
| Prompt | 19 | **23** |
| Risorse | 13–15 | **15** |
| Skill | 19 | **21** |
| Comandi | — | **13** |
| Agenti | — | **6** |

**Raccomandazione:** aggiornare `CLAUDE.md` ai numeri reali. L'audit **non** ha aggiornato questo file (lasciato volutamente alla Sua revisione, perche e il documento piu citato).

### 4.3 `tool-catalog.md`
Il file `plugin/skills/resources/tool-catalog.md` **non e stato controllato** per conteggi/nomi obsoleti: e una probabile seconda sede del vecchio "177". **Raccomandazione:** verificarlo insieme a CLAUDE.md.

---

## 5. Esito test (pytest) e rischi residui

### 5.1 Esito test — GATE ROSSO
```
.venv/bin/pytest tests/ -m "not live"  ->  2305 passati, 18 FALLITI, 0 errori
```
**Verifica chiave:** mettendo da parte le modifiche e ripartendo dalla base pulita, **tutti questi 18 test passano**. Quindi **ognuno dei 18 fallimenti e stato introdotto dalle modifiche** dell'audit. Il lavoro **non e mergiabile in questo stato.**

Test falliti (file -> causa sintetica):
- `test_proprieta_successioni.py` (3) — coefficienti catastali (es. 60,0 != 63,0; 40,8 != 42,84).
- `test_dichiarazione_redditi.py` (2) — detrazione figli (disabile e proporzionale).
- `test_diritto_penale.py` (2) — calcolo pena base e riduzioni combinate.
- `test_modelli_atti.py` (2) — routing tier2/tier4.
- `test_procedura_civile.py` (2) — soglie competenza giudice.
- 1 ciascuno: `test_diritto_lavoro.py`, `test_diritto_societario.py`, `test_giurisprudenza_unificata.py`, `test_legal_citations.py`, `test_parcelle_professionisti.py`, `test_privacy_gdpr.py`, `test_varie.py`.

**Regola d'oro (importante):** NON si devono aggiornare i test "in blocco" per farli combaciare con il nuovo codice. Per le voci di **dati legali**, prima si verifica la fonte; solo se il codice e davvero corretto si aggiorna il test. Altrimenti si "legittimerebbe" una modifica legale non verificata.

### 5.2 Rischi residui (dal piu critico)

1. **CRITICO — Coefficienti catastali (`proprieta_successioni.py`).** Sottostima la base imponibile di ogni operazione immobiliare. Da revocare o confermare con un fiscalista. (Vedi 3.A.1)
2. **ALTO — Detrazioni IRPEF figli + forfettario + acconti (`dichiarazione_redditi.py`).** Numerose modifiche fiscali senza fonte citata. (3.A.2/3)
3. **ALTO — Competenza Giudice di Pace (`procedura_civile.py`).** Re-instrada cause tra GdP e Tribunale; non confermato. (3.A.4)
4. **MEDIO — Disclaimer L. 132/2025 art. 13->15 (`orientamento.py`).** Passa "in silenzio" (nessun test lo fissa) e rischia di contraddire la release 2.6.1. (3.A.5)
5. **MEDIO — Tassi/interessi (`tassi_interessi.py`).** Stato incoerente: l'albero di lavoro mescola "365 fisso" e gestione anno bisestile. Da riconciliare per uniformare il trattamento dell'anno bisestile (incide su importi).
6. **MEDIO — Scraper live modificati (`cerdef` e `corte_cost`).** Cambi alla logica di parsing e alla cache (incluso il caching "negativo" di un anno vuoto, che potrebbe congelare un anno realmente popolato). I test sono basati su simulazioni, non su chiamate reali: serve un giro di **test live** prima di fidarsi.
7. **COPERTURA — moduli/skill non rivisti.** `eu_implementation.py` e `gpdp.py` (3+3 tool) **non hanno ricevuto alcuna modifica**; idem 12 skill. Non c'e evidenza che siano stati "rivisti e trovati a posto" oppure semplicemente saltati. Da dichiarare esplicitamente.
8. **DOCUMENTAZIONE — nessun changelog dell'audit.** Manca un registro scritto di cosa e stato cambiato e perche, con la fonte legale per ogni costante modificata. Per uno strumento di dati legali questo registro e necessario.

### 5.3 Prossimi passi consigliati (in ordine)
1. **Sbloccare i test:** classificare ognuno dei 18 fallimenti come (a) cosmetico -> aggiornare il test, oppure (b) dato legale -> **prima verificare la fonte**, poi revocare il codice o aggiornare il test. Niente aggiornamenti "in blocco".
2. **Verificare e citare la fonte** di ogni numero legale modificato (catastali in testa).
3. **Aggiornare CLAUDE.md** ai conteggi reali e controllare `tool-catalog.md`.
4. **Eliminare** i duplicati obsoleti in `.claude/`.
5. **Riconciliare** la gestione anno bisestile in `tassi_interessi.py`.
6. **Test live** per `cerdef`/`consob`/`corte_cost`.
7. **Scrivere un changelog dell'audit** separando "controlli di sicurezza aggiunti" (basso rischio) da "modifiche a dati/output legali" (richiedono firma).
8. **Sua firma sul gruppo dati-legali** prima di qualsiasi commit/PR (regola dello Studio: mai auto-commit, prima propongo il messaggio e attendo).

---

## 6. Appendice tecnica

- **Inventario completo (autorevole):** [`docs/_audit/inventory.md`](./inventory.md) — mappa file-per-file di tool, prompt, risorse, skill, comandi, agenti, con i conteggi reali (214 tool / 30 moduli / 23 prompt / 15 risorse / 21 skill / 13 comandi / 6 agenti). Supera i conteggi obsoleti di `CLAUDE.md`.
- **Inventario in formato dati:** [`docs/_audit/inventory.json`](./inventory.json).
- **Diff sintetico:** 54 file modificati, +834 / -289 righe, tutto sotto `plugin/server/src/`, `plugin/commands/`, `plugin/skills/`, `plugin/agents/`. **Zero modifiche** sotto l'albero `src/` radice importato dai test — il che conferma che i 18 fallimenti derivano dalle modifiche sotto `plugin/server/src/` (le copie effettivamente eseguite dai test in questi moduli).
- **Comando per riprodurre l'esito test:** `.venv/bin/pytest tests/ -m "not live"`.
- **Comando per i test live (da eseguire prima di fidarsi degli scraper):** `.venv/bin/pytest tests/ -m "live"`.

---

*Report generato a fini di revisione interna. Le sezioni 3 e 5.2 elencano le voci che richiedono la firma del titolare prima della messa in produzione.*
