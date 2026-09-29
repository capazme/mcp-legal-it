# Audit normativo dei tool di mcp-legal-it

| | |
|---|---|
| Documento | 001_mcp-legal-it_AuditNormativa_RV_SAPG |
| Autore | SAPG |
| Revisione | RV2 (29/09/2026, benchmark completato) |
| Oggetto | Verifica dell'aggiornamento normativo dei tool, con riguardo alla procedura civile e alla riforma Cartabia; esito del benchmark su avvocatoandreani.it, fonti ufficiali e norme; flag per i tool a normativa previgente |

## 1. Sintesi

Il server Model Context Protocol (MCP) espone 227 tool. L'audit ha verificato ogni tool di calcolo e ogni modello di atto contro il testo delle norme che dichiara di applicare, con priorità alla procedura civile riformata dal D.Lgs. 10 ottobre 2022 n. 149 (riforma Cartabia, in vigore dal 28/02/2023) e dal correttivo D.Lgs. 31 ottobre 2024 n. 164.

Esiti principali:

- **Sospensione feriale (L. 7 ottobre 1969 n. 742)**: tutti i tool di scadenze la applicavano con un'aritmetica sbagliata, che in tre situazioni ricorrenti dava date errate anche di dodici giorni. Riscritta con conteggio giorno per giorno; tre tool non la applicavano affatto (impugnazioni, appello, memorie 171-ter in versione riepilogo).
- **Riforma Cartabia**: tre tool dichiarati "post-Cartabia" applicavano in realtà termini previgenti (art. 190 c.p.c. abrogato per conclusionali e repliche; termini del rito ordinario applicati al rito semplificato; comparsa dell'appellato a 20 giorni invece di 70; costituzione dell'appellante a 30 giorni invece di 10). Tutti corretti.
- **Flag per i tool a normativa previgente**: introdotta (`Regime: PREVIGENTE`), applicata a due tool, verificata dall'audit automatico e visibile al modello, all'host e in ogni risposta. Interruttore `LEGAL_PREVIGENTE=off` per nasconderli.
- **Altri errori sostanziali corretti**: formula del danno biologico micropermanente (sottostima fino a un terzo al 9%), minimo impignorabile delle pensioni mai applicato, contributo unificato del lavoro senza la condizione di reddito, decreto ingiuntivo per crediti di lavoro assegnato al giudice di pace, regime della prescrizione penale non dipendente dalla data del fatto, requisiti congiunti dell'impresa minore nel Codice della crisi.
- **Benchmark su avvocatoandreani.it, fonti ufficiali e norme**: eseguito il 25-29/09/2026 su tutti i tool (paragrafo 6). Ha corretto 161 tool (paragrafo 5.1) e lascia aperte le voci del paragrafo 7.2.
- **Voci non verificabili offline**: elencate al paragrafo 7 con il grado di confidenza; i tool corrispondenti sono stati declassati a INDICATIVO o STIMATO con la ragione scritta nel docstring, in modo che il modello lo legga prima di usarli.

## 2. Metodo e limiti

1. Inventario automatico dei 227 tool con le righe `Vigenza:` e `Precisione:` di ciascuno (149 tool con vigenza dichiarata; 78 senza, quasi tutti tool di ricerca online per cui la vigenza non ha senso).
2. Lettura del codice dei 34 moduli, con revisione in parallelo di quattro gruppi tematici (atti giudiziari e modelli; parcelle; danni, penale, lavoro, societario, crisi; fisco, proprietà, interessi).
3. Confronto con il testo delle norme come conosciuto alla data di cutoff delle conoscenze del revisore (giugno 2026). Nessuna fonte esterna è stata consultabile durante la sessione: la policy di rete dell'ambiente cloud ha negato ogni connessione verso `www.avvocatoandreani.it`, `www.normattiva.it`, `www.brocardi.it`, `www.italgiure.giustizia.it`, `eur-lex.europa.eu` e `www.gazzettaufficiale.it`, sia dal container sia dal fetch web di Claude. Per questo ogni correzione riporta l'articolo di legge applicato, ogni dubbio è dichiarato tale, e un test live (`tests/unit/test_cartabia_live.py`) permette di riscontrare sul testo vigente di Normattiva, tramite `cite_law`, tutti i numeri usati dai tool di procedura.
4. Per abilitare il benchmark, aggiungere i domini sopra elencati alla lista dei domini consentiti nelle impostazioni di rete dell'ambiente (menu dell'ambiente cloud nella barra del titolo della sessione, voce Modifica), oppure scegliere un livello di accesso più ampio.

## 3. La flag per i tool a normativa previgente

Un tool che calcola sotto una regola superata non è un tool sbagliato né una tabella scaduta: è giusto per i casi residuali che quella regola ancora governa e sbagliato per tutti gli altri. Il rischio è che il modello lo scelga per un caso attuale senza che nulla nella risposta lo avverta. La flag risolve questo in tre punti, tenuti allineati dall'audit automatico:

| Livello | Meccanismo |
|---|---|
| Dichiarazione | Riga nel docstring: `Regime: PREVIGENTE — <casi residuali>; tool vigenti: <nomi>`. È la prima cosa che il modello legge prima di scegliere il tool. Un tool senza la riga è vigente. |
| Host | Tag `previgente` in `@mcp.tool(tags=...)`, visibile nei metadati di `tools/list` insieme al blocco `mcp-legal-it/regime` (stato, casi residuali, tool vigenti). |
| Risposta | Wrapper `@previgente` (`src/lib/_regime.py`): ogni risposta, dizionario o testo, porta il campo `regime_normativo`; il middleware ripete lo stesso blocco nel `_meta` del risultato. |
| Interruttore | `LEGAL_PREVIGENTE=off` disattiva il gruppo per gli host che non vogliono esporlo; il default li mantiene registrati e marcati, perché un tool marcato è più sicuro di un tool assente. |
| Audit | `scripts/audit_tool_annotations.py` fallisce se la riga, il tag e il wrapper non concordano, se manca la descrizione dei casi residuali, o se un tool vigente indicato non è registrato; genera la mappa `PREVIGENTE` in `tool_annotations.py`. |

Tool marcati:

| Tool | Casi residuali | Tool vigenti |
|---|---|---|
| `termini_183_190_cpc` | cause iscritte a ruolo prima del 28/02/2023 (artt. 183 co. 6 e 190 c.p.c. nel testo anteriore al D.Lgs. 149/2022, art. 35 co. 1) | `termini_memorie_repliche`, `termini_processuali_civili` |
| `equo_indennizzo` | infermità da causa di servizio per fatti anteriori al 06/12/2011 (art. 6 DL 201/2011 conv. L. 214/2011) | nessuno; per gli infortuni dei lavoratori privati `risarcimento_inail` |

Candidati futuri: un eventuale tool per le tabelle forensi anteriori al DM 147/2022, o per la prescrizione penale "Orlando", potrebbero usare la stessa flag. I tool che scelgono il regime dalla data (come `prescrizione_reato` dopo questo intervento) non vanno marcati: sono vigenti e dichiarano il regime applicato nel campo `regime`.

## 4. Procedura civile e riforma Cartabia: scostamenti trovati e corretti

Riferimenti: D.Lgs. 149/2022 (URN Normattiva `urn:nir:stato:decreto.legislativo:2022-10-10;149`), c.p.c. (`urn:nir:stato:regio.decreto:1940-10-28;1443`), L. 742/1969 (`urn:nir:stato:legge:1969-10-07;742`). Gli URN sono indicati per il riscontro, non sono stati aperti in questa sessione.

### 4.1 Sospensione feriale (tutti i tool di `scadenze_termini.py`)

La funzione precedente aggiungeva al termine i soli giorni di agosto compresi nel periodo "grezzo", senza contare che l'allungamento copre a sua volta altri giorni di agosto. Tre errori concreti, verificati contando i giorni sul calendario:

| Caso | Regola | Risultato precedente | Risultato corretto |
|---|---|---|---|
| Notifica 20/07, termine 30 giorni | 21-31 luglio sono 11 giorni, agosto non conta, 1-19 settembre gli altri 19 | 07/09 | 19/09 |
| Udienza 01/10, memoria 40 giorni prima | 30/09-01/09 sono 30 giorni, agosto non conta, 31/07-22/07 gli altri 10 | 12/08 (una scadenza dentro la sospensione) | 22/07 |
| Notifica 10/08, termine 30 giorni | il decorso è differito alla fine della sospensione, il 1° settembre è il primo giorno (art. 1 co. 2 L. 742/1969) | 01/10 | 30/09 |

Il test unitario precedente fissava il valore 12/08 come atteso. Ora il conteggio è giorno per giorno in avanti e a ritroso; per i termini a mesi ogni agosto compreso nel periodo sposta la scadenza di 31 giorni; per un dies a quo in agosto il termine a mesi decorre dal 31 agosto (lettura prudenziale: sei mesi dal 15/08 scadono il 28/02, non il 1° marzo come nella lettura alternativa che fa decorrere dal 1° settembre). Ogni risposta dichiara se la sospensione è stata applicata (`sospensione_feriale_applicata`) e se ha inciso (`sospensione_feriale_incidente`); il parametro va impostato a `False` per le materie escluse dall'art. 3 L. 742/1969 (lavoro, previdenza, alimenti, sfratti, opposizioni esecutive, cautelari).

Tre tool non applicavano la sospensione in nessun caso: `scadenze_impugnazioni` (un termine lungo di sei mesi pubblicato a giugno scadeva a dicembre invece che a gennaio), `termini_deposito_atti_appello`, `termini_memorie_repliche`. Ora hanno il parametro, con default `True`.

### 4.2 `termini_processuali_civili`: art. 189 al posto dell'art. 190 abrogato

Le opzioni `comparsa_conclusionale` e `replica` calcolavano 60 e 80 giorni dopo l'udienza di precisazione delle conclusioni: è lo schema dell'art. 190 c.p.c., abrogato dal D.Lgs. 149/2022. Nel rito riformato l'art. 189 c.p.c. prevede termini a ritroso dall'udienza di rimessione della causa in decisione: note di precisazione delle conclusioni non oltre 60 giorni prima, comparse conclusionali non oltre 30, memorie di replica non oltre 15. Il tool ora calcola questi tre termini (nuova opzione `note_conclusioni`), accetta il termine più breve eventualmente assegnato dal giudice (`giorni`) e dichiara a quale udienza si riferisce la data.

### 4.3 `termini_procedimento_semplificato`: termini del rito sbagliato

Il tool applicava al rito semplificato di cognizione la comparsa a 70 giorni e le memorie a 40/20/10 giorni, che sono i termini del rito ordinario (artt. 166 e 171-ter). Nel rito semplificato: tra notificazione del ricorso e udienza devono intercorrere termini liberi non minori di 40 giorni (60 all'estero, art. 281-undecies co. 2); il convenuto si costituisce non oltre 10 giorni prima dell'udienza (co. 3); le memorie esistono solo se il giudice le concede, entro un termine non superiore a 20 giorni e un ulteriore termine non superiore a 10 (art. 281-duodecies co. 3). Il tool ora calcola queste cinque scadenze e rifiuta giorni oltre i massimi di legge.

### 4.4 `termini_deposito_atti_appello`: costituzione delle parti

L'appellante si costituisce entro 10 giorni dalla notifica della citazione (art. 165 c.p.c., richiamato dall'art. 347), non entro 30; l'appellato deve costituirsi almeno 70 giorni prima dell'udienza (art. 166 nel testo del D.Lgs. 149/2022, richiamato dall'art. 347), proponendo nella comparsa l'appello incidentale a pena di decadenza (art. 343); i 20 giorni erano il termine previgente. Entrambi i termini sono ora calcolati dalle date passate dal chiamante.

### 4.5 Altri scostamenti nel modulo scadenze

- `scadenze_impugnazioni`: il regolamento di competenza non ha termine lungo di sei mesi (art. 47 co. 2: trenta giorni dalla comunicazione).
- `scadenze_multe`: lo sconto del 30% per il pagamento entro cinque giorni è dell'art. 20 DL 69/2013 conv. L. 98/2013 (era attribuito alla L. 120/2010).
- `termini_separazione_divorzio`: i 6 e 12 mesi decorrono dalla comparizione dei coniugi in udienza (art. 3 n. 2 lett. b L. 898/1970), non dall'omologa come diceva la documentazione; nota sul cumulo delle domande ex art. 473-bis.49 c.p.c.
- `termini_deposito_ctu`: i termini per osservazioni e deposito definitivo sono fissati dal giudice (art. 195 co. 3), i 15 giorni sono prassi: ora sono parametri.

### 4.6 Modelli di atti (`atti_giudiziari.py`, `modelli_atti.json`)

- Attestazioni di conformità e istanza di visibilità citavano gli artt. 16-bis e 16-undecies DL 179/2012, sostituiti per i procedimenti dal 28/02/2023 dagli artt. 196-quater e 196-octies-undecies disp. att. c.p.c.
- Note di trattazione scritta: l'art. 127-ter si applica dal 01/01/2023 anche ai procedimenti pendenti (art. 35 co. 2 D.Lgs. 149/2022, come modificato dalla L. 197/2022), non dal 28/02/2023; segnalati i limiti del correttivo D.Lgs. 164/2024.
- Precetto: eliminato "notificato in forma esecutiva" (la formula esecutiva non esiste più, art. 475); l'avvertimento confondeva l'opposizione ex art. 615 (senza termine) con quella ex art. 617 (venti giorni); aggiunto l'avvertimento sul sovraindebitamento ex art. 480 co. 2.
- Relata PEC: l'autorizzazione del Consiglio dell'Ordine serve solo per la notifica a mezzo posta; perfezionamento secondo l'art. 147 co. 3 c.p.c. (ricevute di accettazione e consegna, regola delle ore 21-7).
- Dichiarazione del terzo: la mancata dichiarazione è disciplinata dall'art. 548, non dal "co. 3 dell'art. 547"; la nota di precisazione del credito non è l'art. 547.
- Testimonianza scritta: l'ammonizione sull'"importanza religiosa" del giuramento è caduta con Corte cost. 149/1995.
- Catalogo modelli: il contributo unificato in appello è aumentato della metà, non raddoppiato; l'esenzione lavoro "sotto 1.033 euro" non esiste più; confusione fra art. 481 e art. 644; riferimento al DM 180/2010 sostituito dal DM 150/2023.

### 4.7 Competenza e mediazione (`procedura_civile.py`)

`competenza_giudice` applica le soglie del giudice di pace vigenti dal 28/02/2023 (10.000 e 25.000 euro, art. 7 c.p.c.); l'innalzamento a 30.000 e 50.000 euro del D.Lgs. 116/2017 è stato più volte differito e non risulta in vigore. Il codice indicava come decorrenza il 31/10/2026; una fonte secondaria letta da un revisore parla di un ulteriore rinvio al 31/10/2027 (DL 100/2026): non verificato, da riscontrare con `cite_law` sull'art. 27 D.Lgs. 116/2017 prima di quella data. `verifica_mediazione_obbligatoria` riporta l'elenco dell'art. 5 co. 1 D.Lgs. 28/2010 come modificato dal D.Lgs. 149/2022, che corrisponde alle materie note.

## 5. Altri scostamenti corretti

| Tool | Problema | Correzione e riferimento |
|---|---|---|
| `danno_biologico_micro` | sommava i valori punto dei gradi inferiori | valore punto (base per coefficiente del grado accertato, ridotto per età) per il numero di punti, art. 139 co. 2 lett. a) e co. 6 D.Lgs. 209/2005; al 9% il risultato passa da 13.937 a 20.461 euro |
| `danno_biologico_macro` | valori punto non riconducibili alla tabella unica nazionale; importi non plausibili oltre il 20%; personalizzazione fino al 50% | grado STIMATO con avvertenza in risposta; tetto 30% (art. 138 co. 3); la tabella unica nazionale (DPR 13 gennaio 2025 n. 12) resta da trascrivere dalla Gazzetta Ufficiale |
| `contributo_unificato` | lavoro sempre esente; importi di appello lavoro non riconducibili al DPR 115/2002; tipi ignoti calcolati come cognizione | art. 9 co. 1-bis (esenzione fino a tre volte la soglia dell'art. 76, oltre 43 euro previdenza e metà scaglione lavoro), art. 13 co. 6-quater (tributario, stessi importi in appello), nuovi tipi per valore indeterminabile, opposizione a decreto ingiuntivo e agli atti esecutivi; tipo ignoto rifiutato |
| `pignoramento_stipendio` | minimo impignorabile delle pensioni indicato ma mai applicato | art. 545 co. 7 c.p.c. nel testo dell'art. 21-bis DL 115/2022 conv. L. 142/2022: doppio dell'assegno sociale, minimo 1.000 euro, quota solo sull'eccedenza; assegno sociale passabile dal chiamante (il valore incluso è quello 2024) |
| `decreto_ingiuntivo` | crediti di lavoro fino a 10.000 euro assegnati al giudice di pace | art. 413 c.p.c.: sempre tribunale in funzione di giudice del lavoro; termini artt. 641 e 644 in risposta |
| `prescrizione_reato` | un solo regime per ogni data; documentazione che attribuiva le riforme al D.Lgs. 150/2022 | regime scelto dalla data del fatto: ordinario fino al 02/08/2017; L. 103/2017 dal 03/08/2017; dal 01/01/2020 art. 161-bis c.p. (L. 3/2019 e L. 134/2021) e improcedibilità ex art. 344-bis c.p.p. (3 anni/18 mesi per impugnazioni entro il 31/12/2024, poi 2 anni/1 anno); aumento per interruzioni graduato sulla recidiva (art. 161 co. 2) |
| `composizione_negoziata` | impresa minore con un solo requisito sotto soglia | art. 2 co. 1 lett. d CCII: requisiti congiunti |
| `costi_costituzione` | "3/10" del conferimento in denaro; diritti di segreteria alla SRLS | art. 2342 co. 2 c.c.: 25%; art. 3 co. 3 DL 1/2012: esenzione |
| `scadenze_licenziamento` | 180 giorni contati dal 60° giorno; 60 giorni dal deposito; rito Fornero | art. 6 co. 2 L. 604/1966: 180 giorni dall'impugnazione, 60 dal rifiuto della conciliazione; rito Fornero abrogato dal D.Lgs. 149/2022 |
| `calcolo_naspi` | riduzione dal settimo mese | art. 4 co. 3 D.Lgs. 22/2015: dal primo giorno del sesto mese |
| `fattura_professionista` | ritenuta sempre sul solo compenso | rivalsa INPS della gestione separata soggetta a ritenuta; contributo integrativo di cassa escluso; nuovo tipo `gestione_separata` (il caso che il calcolatore di avvocatoandreani.it riproduce con ritenuta 208 su 1.040) |
| `fattura_avvocato` | forfettario senza bollo | bollo di 2 euro oltre 77,47 euro (DPR 642/1972) |
| `genera_quotazione_docx` | contributo unificato dell'esecuzione fisso a 139 euro | dalla tabella: 43 euro sotto 2.500 (art. 13 co. 2 DPR 115/2002) |
| `decurtazione_punti_patente` | riforma del Codice della Strada attribuita al D.Lgs. 36/2023 (codice dei contratti pubblici) | L. 25 novembre 2024 n. 177 |

### 5.1 Scostamenti corretti dal benchmark (RV2)

Il benchmark del paragrafo 6 ha portato alla correzione di 161 tool, ciascuno con un test che fissa il valore verificato sulla fonte primaria. Per area:

| Area | Tool corretti | Esempi di correzione e riferimento |
|---|---|---|
| Termini e scadenze | `scadenze_multe` | ricorso al giudice di pace con sospensione feriale (art. 1 L. 742/1969, art. 7 D.Lgs. 150/2011, Cass. 30427/2022) e proroga del sabato (art. 155 co. 5 c.p.c.); il sabato festivo passa al lunedì (art. 155 co. 4) |
| Costi giudiziari | `diritti_copia`, `copie_processo_tributario`, `note_iscrizione_ruolo`, `codici_iscrizione_ruolo`, `pignoramento_stipendio`, `gratuito_patrocinio`, `sollecito_pagamento`, `tassazione_atti` | fasce del D.I. 9 luglio 2021, condizione di reddito dell'art. 9 co. 1-bis DPR 115/2002, 40 euro forfettari solo dal 2013 (art. 6 D.Lgs. 231/2002), classificazione per contenuto degli atti (Tariffa parte I art. 8) |
| Parcelle e fatture | `modello_notula`, `parcella_avvocato_civile`, `parcella_stragiudiziale`, `nota_spese`, `fattura_avvocato`, `spese_trasferta_avvocati`, `compenso_ctu`, `compenso_curatore_fallimentare`, `compenso_delegati_vendite`, `spese_mediazione`, `tariffe_mediazione`, `fattura_enasarco`, `fattura_professionista` | Tabella 8 dei monitori, art. 6 DM 55/2014 oltre 520.000 euro, arrotondamento commerciale (art. 5 Reg. CE 1103/97), DM 150/2023, DM 30/2012, DM 227/2015 |
| Imposte sul reddito | `detrazione_coniuge`, `detrazione_assegno_coniuge`, `detrazione_pensione`, `detrazione_lavoro_dipendente`, `detrazione_figli`, `calcolo_irpef`, `acconto_irpef`, `ravvedimento_operoso`, `rateizzazione_imposte`, `calcolo_tfr`, `assegno_unico` | maggiorazioni degli artt. 12 e 13 TUIR (10-30, 50 e 65 euro), minimo di 713 euro, quoziente troncato a quattro decimali (art. 12 co. 4, art. 13 co. 6), art. 13 co. 5-bis per gli assegni al coniuge |
| Immobili e successioni | `calcolo_valore_catastale`, `imposte_compravendita`, `calcolo_imu`, `pensione_reversibilita`, `costi_costituzione` | gruppo B a 168 in ogni caso (art. 309 co. 6 lett. b D.Lgs. 141/2026), tassa di concessione governativa della SRLS |
| Interessi e rivalutazione | `interessi_legali`, `interessi_mora`, `interessi_acconti`, `interessi_corso_causa`, `verifica_usura`, serie FOI (7 tool), `rivalutazione_tfr` | 10% dal 16/12/1990 (art. 1 L. 353/1990), 7 o 8 punti secondo la data del contratto, saggio legale per le domande anteriori all'11/12/2014 (art. 17 co. 2 DL 132/2014), serie FOI ricostruita dal 1990, art. 2120 co. 4 c.c. |
| Diritto penale e utilità | `aumenti_riduzioni_pena`, `fine_pena`, `tasso_alcolemico`, `codice_fiscale`, `decurtazione_punti_patente`, `prescrizione_diritti` | confini delle fasce dell'art. 186 co. 2, tabella dell'art. 126-bis C.d.S. |
| Lavoro, società, crisi | `costo_lavoro`, `calcolo_naspi`, `indennita_licenziamento`, `indennita_preavviso`, `quorum_assembleari`, `soglie_organo_controllo_srl`, `test_crisi_impresa`, `concordato_preventivo`, `compenso_occ` | art. 3 co. 2 D.Lgs. 23/2015, art. 3 co. 4 CCII, art. 84 e 109 CCII, art. 16 DM 202/2014, art. 2369 c.c. |
| Ricerca e fonti online | CeRDEF, CONSOB, Corte costituzionale, TAR e Consiglio di Stato, Garante, Gazzetta Ufficiale, CGUE, Italgiure, `cite_law` e le altre funzioni di consultazione (41 tool) | portali cambiati, troncamento del dispositivo, date del Garante in AAAA-MM-GG, serie speciali della Gazzetta, filtri CELEX della CGUE |
| Generatori di documenti | informative e registri GDPR, DPA, DPIA, atti giudiziari (precetto, decreto ingiuntivo, sfratto, relata PEC, testimonianza scritta), modelli di atti, quotazione (22 tool) | artt. 13, 14, 28, 30, 33 GDPR; artt. 480, 543, 553, 660, 257-bis c.p.c.; art. 3-bis L. 53/1994 |

L'elenco completo con la voce di changelog per ciascun tool è nel `CHANGELOG.md`, sezione Unreleased.

## 6. Benchmark su avvocatoandreani.it, fonti ufficiali e norme (RV2, 29/09/2026)

### 6.1 Metodo

Il benchmark ha riguardato tutti i 228 tool registrati (i 227 del piano più `stato_server`, introdotto nella 2.14.1). Per ogni tool è stata scelta una delle strategie del piano `docs/benchmark/piano-benchmark-andreani.md`, dopo aver aperto con il browser le 252 pagine raggiungibili del sito (catalogo in `docs/benchmark/catalogo-andreani.json`, 119 tool con un calcolatore sul sito).

| Strategia | Tool | Che cosa è stato fatto |
|---|---|---|
| sito | 119 | il calcolatore del sito è guidato con Playwright e confrontato con il tool su casi del piano e casi al limite; ogni scostamento è giudicato sulla fonte primaria |
| fonte ufficiale | 10 | confronto con la tabella dell'ente (Agenzia delle Entrate, INPS, CNEL, MEF, EDPB e Garante) |
| norma | 15 | i numeri usati dal tool sono asseriti sul testo vigente letto con `cite_law` |
| chiamata reale | 54 | una chiamata su un documento noto con verifica dei metadati |
| documento | 26 | struttura dei generatori e verifica dei riferimenti normativi prodotti |
| non applicabile | 4 | utilità interne senza riferimento esterno |

Regole seguite: il sito è un benchmark e non una fonte, quindi nessun tool è stato allineato al sito senza la norma che lo giustifica; un verdetto "tool errato" vale solo se cita l'articolo o la tabella ufficiale; le differenze di convenzione (arrotondamento, divisore 365 o 366, troncamento del quoziente alla quarta cifra, dies a quo) sono documentate nei test e non modificano il tool. Tolleranze: 0,01 euro sugli importi, date esatte.

Ogni scostamento è stato esaminato da agenti indipendenti: per i tool senza calcolatore da tre verificatori con lenti diverse (norma, convenzione, test) e verdetto a maggioranza; per i tool con calcolatore da un agente che rilegge la fonte primaria e da un revisore che la riverifica. Le correzioni sono state applicate in worktree isolati, con un test unitario che fissa il valore verificato e il riferimento normativo, e integrate dopo la rigenerazione di annotazioni e golden.

### 6.2 Esito complessivo

| Esito | Tool |
|---|---|
| corretto | 160 |
| corretto con riserva | 1 |
| coincide | 31 |
| convenzione | 17 |
| sito errato | 5 |
| test errato | 1 |
| da chiarire | 7 |
| errato, non corretto | 2 |
| non applicabile | 4 |

File di test prodotti: 140 file in `tests/comparison` (uno per ogni tool con calcolatore, più i preesistenti) e 34 file live in `tests/unit` (`test_norme_live_*`, `test_fonte_*_live`, `test_<fonte>_live`, `test_strutturale_*_live`, più l'helper `_norme_live.py`). Casi eseguiti nelle matrici: 1857. La suite predefinita passa (4153 test, `pytest tests/ -m "not live"`), come `scripts/audit_tool_annotations.py --check` e `scripts/update-data.py --strict`.

### 6.3 Matrice per tool

Nella colonna "Esito": corretto = errore del tool accertato sulla fonte primaria e corretto; convenzione = scelta difendibile, documentata; sito errato = il tool è conforme alla norma; da chiarire = non decidibile con una fonte primaria (voci del paragrafo 7). I valori mostrano il caso di scostamento più rappresentativo.

| Tool | Strategia | Casi | Valore del tool | Valore del sito o della fonte | Esito | Causa e azione |
|---|---|---|---|---|---|---|
| `acconto_cedolare_secca` | sito | 10 | acconto_dovuto=False (nessun acconto: imposta… | Unico versamento 52,00 (cod. 1841) entro il 3… | corretto | Fixed acconto_cedolare_secca: single payment now stops at 257.51 (first instalment not above euro 103, art. 17 c. 3 D.P.R. 435/2001, applied via art.… |
| `acconto_irpef` | sito | 12 | acconto_dovuto=False (nessun acconto: imposta… | Unico versamento (4034) EUR 52,00 entro 30 no… | corretto | Fixed acconto_irpef: single payment now stops at 257.51, since the first instalment (40%) must not exceed euro 103 (art. 17 c. 3 D.P.R. 435/2001); at… |
| `adeguamento_canone_locazione` | sito | 9 | var 1,42% (1,4167 non arrotondata); applicata… | var 1,4%; 75% = 1,05%; canone 12.126,00 | corretto | fix(adeguamento_canone_locazione): the 12/24-month FOI variation is rounded to one decimal as published by ISTAT in the GU (art. 81 L. 392/1978) befo… |
| `assegno_unico` | sito | 8 | 203,80 mensili (importo massimo) | 57,00 mensili, cioè l'importo minimo della ta… | corretto | assegno_unico: without ISEE the minimum amounts apply (art. 4 c. 9 D.Lgs. 230/2021), +50% of the base for under-1 and (up to the upper ISEE threshold… |
| `aumenti_riduzioni_pena` | sito | 10 | 2.37 mesi = 71,1 giorni (passaggi 360 / 240 /… | 2 mesi, 10 giorni = 70 giorni (passaggi 1 ann… | corretto | Fixed aumenti_riduzioni_pena: the art. 67 co. 2 c.p. floor (not below a quarter with several ordinary attenuanti) is now applied; 12 months with four… |
| `calcolo_ammortamento` | sito | 8 |  |  | coincide |  |
| `calcolo_devalutazione` | sito | 7 | 8469.30 (FOI 118.9/100.7, coefficiente 0.8469… | 8410.43 (indici 118,9 in base 2015 e 107,1 in… | corretto | fix(calcolo_devalutazione): corrected through the rebuilt ISTAT FOI series (e.g. 10,000 euro of Dec 2023 back to Dec 2013 is 8,410.43 instead of 8,46… |
| `calcolo_eredita` | sito | 12 |  |  | coincide |  |
| `calcolo_eta_anagrafica` | sito | 10 | 17 anni, 11 mesi, 30 giorni; prossimo complea… | 17 anni, 11 mesi e 28 giorni | corretto | calcolo_eta_anagrafica: age in years/months/days now follows the common calendar with the art. 2963 c.c. last-day-of-month rule (no negative days, co… |
| `calcolo_hash` | sito | 13 |  |  | coincide |  |
| `calcolo_imu` | sito | 21 | 0,86%, IMU 1.444,80 | 7,6 per mille, IMU 1.276,80 | corretto | fix(calcolo_imu): default rate for the A/1, A/8, A/9 principal residence is 0.5% (art. 1 co. 748 L. 160/2019) instead of 0.86%; 0.86% (co. 754) remai… |
| `calcolo_inflazione` | sito | 12 | 18,0735% (-> 18,1); FOI 100,7 -> 118,9 | 18,9% | corretto | fix(calcolo_inflazione): FOI series 1990-2025 rebuilt from the ISTAT indices in their original bases and spliced with the official ISTAT coefficients… |
| `calcolo_irpef` | sito | 11 | imponibile 30.000,00; lorda 7.100,00; detrazi… | imponibile 30.000,00; lorda 7.100,00 (aliquot… | corretto | fix(calcolo_irpef): art. 13 TUIR: deductions computed on total income with ratios truncated to four decimals (c. 6, 6-bis), 65 euro increase for empl… |
| `calcolo_maggior_danno` | sito | 5 | maggior_danno 451,72 (rivalutazione 1077,07; … | maggior danno 723,12 annuale (824,99 mensile)… | da chiarire |  |
| `calcolo_notula_penale` | sito | 10 | fasi 237+284+567 = 1088,00; SG 163,20; CPA 50… | fasi 237+284+567 = 1088,00; SG 163,20; CPA 50… | corretto | Fixed calcolo_notula_penale: half-cent ties are rounded up on exact decimals (art. 5 Reg. CE 1103/97); 1,301.25 taxable now gives IVA 286.28 and tota… |
| `calcolo_superficie_commerciale` | sito | 7 | 89,90 mq | 88,00 mq | corretto | fix(calcolo_superficie_commerciale): coefficients aligned to DPR 138/1998 allegato C (balconi and terrazze 30% up to 25 mq then 10%, garden 10% up to… |
| `calcolo_surroga_mutuo` | sito | 8 | rata nuova 884,17; interessi nuovi 14534,15; … | rata nuova 884,17; interessi nuovi 14534,15; … | convenzione | Rata attuale arrotondata al centesimo (tool) vs rata ricostruita non arrotondata (sito). Commento in tests/comparison/test_calcolo_surroga_mutuo.py. |
| `calcolo_taeg` | sito | 12 | 1.6975 | 1.68 | sito errato |  |
| `calcolo_tempo_trascorso` | sito | 13 | 0 anni, 1 mesi, -1 giorni | sito non calcola; art. 2963: 0a 1m 1g | corretto | calcolo_tempo_trascorso: years/months/days now follow art. 2963 c.c. (month completed on the matching day or the last day of the month), no more nega… |
| `calcolo_tfr` | sito | 13 | lordo 2.000,00; RR 24.000,00; aliquota 23%; i… | fondo 2.000,00; RR 24.000,00; aliquota 23%; i… | corretto | calcolo_tfr: TFR net of the 17% (11% up to 2014) imposta sostitutiva on revaluations, revaluations excluded from taxable base and reference income (a… |
| `calcolo_usufrutto` | sito | 9 |  |  | coincide |  |
| `calcolo_valore_catastale` | sito | 13 | 75.600,00 (coeff 72 = 60 x 1,2) | 63.000,00 (moltiplicatore 60) | corretto | fix(calcolo_valore_catastale): removed the double 20% uplift (art. 1-bis co. 7 DL 168/2004) on A/10, C/1, D and E in compravendita, whose base multip… |
| `cedolare_secca` | sito | 6 | cedolare 1.200,00; IRPEF+addizionali 2.850,00… | cedolare 1.200,00; convenienza anno 2: 719,00… | corretto | fix(cedolare_secca): for concordato contracts the ordinary IRPEF comparison uses 66.5% of the rent (95% x 70%), applying the further 30% reduction of… |
| `cerca_ufficio_giudiziario` | sito | 15 | trovato=False, nessun ufficio_competente; sug… | Tribunale di VASTO | corretto | cerca_ufficio_giudiziario: no more wrong tribunal suggestions for comuni whose name contains a capoluogo's (Torino di Sangro, Bari Sardo...), tipo va… |
| `codice_fiscale` | sito | 9 | KeyError('Ò') (eccezione, nessun CF) | RSSNCL85H15H501M | corretto | codice_fiscale: accented vowels are folded to the plain vowel (Nicolò = NICOLO) instead of raising KeyError; non-Latin letters give an explicit error. |
| `codici_iscrizione_ruolo` | sito | 9 | 6 codici: 145011, 145012, 145013, 145021, 145… | 11 codici presenti nella tabella del tool: 14… | corretto | Fixed codici_iscrizione_ruolo: keyword search now ignores accents and apostrophes, so 'responsabilita', 'responsabilita'' and 'responsabilità' return… |
| `compenso_ctu` | sito | 10 | calcolo_orario 1.000,00-2.000,00 | 73,40 (5 vacazioni x 14,68; periodo 01-15/09/… | corretto | compenso_ctu: computes the DM 30/05/2002 tables (arts. 2, 3, 11, 13, 21, minimum 145.12 euro) and the art. 4 L. 319/1980 vacazioni at 14.68 euro (Cor… |
| `compenso_curatore_fallimentare` | sito | 6 | 2.271,79 | min 1.947,25 / medio 2.109,52 / max 2.271,79 | corretto | compenso_curatore_fallimentare: applies the DM 30/2012 art. 1 min-max percentages per bracket on assets and liabilities (0.19-0.94% / 0.06-0.46%), th… |
| `compenso_delegati_vendite` | sito | 9 | 1100.00 | 4000.00 (4 x 1.000) + spese generali 400 | corretto | compenso_delegati_vendite: applies the DM 227/2015 art. 2 fixed amount per phase (1,000/1,500/2,000 euro x 4), 10% general expenses, the 40% cap and … |
| `compenso_mediatore_familiare` | sito | 7 | 480,00 | 580,80 (2 x 290,40, 4 incontri media) | test errato | compenso_mediatore_familiare: applies the DM 151/2023 art. 8 parameters (40 euro per meeting and party x 1/1.5/2 by complexity), adds the 21% flat ex… |
| `compenso_orario` | sito | 13 |  |  | coincide |  |
| `conta_giorni` | sito | 12 | 4 | 5 | sito errato | Il tipo 'festivi' conta le sole festivita (anche in domenica), non le domeniche. |
| `contributo_unificato` | sito | 51 |  |  | coincide |  |
| `conversione_pena` | sito | 11 | 3 giorni | 2 giorni | sito errato |  |
| `copie_processo_tributario` | sito | 14 | 1,00 | 1,50 | corretto | Fixed copie_processo_tributario: rights now follow DM 27 December 2011 annex 1 per-band amounts plus the EUR 9 conformity fee (art. 2(2)), with the i… |
| `danno_biologico_macro` | sito | 7 | 32160.00 | 21466.92 (biologico TUN 2026: 2656,80 x 10 x … | errato, non corretto |  |
| `danno_biologico_micro` | sito | 8 | personalizzazione 662,57; totale 3.975,43 | danno morale 604,93; totale 3.917,79 (radio '… | convenzione | Base della personalizzazione ex art. 139 co. 3. Il tool la applica su permanente+temporaneo (604,93 sul solo permanente contro 662,57 su entrambi). I… |
| `danno_non_patrimoniale` | sito | 7 | biologico 13.937,15; totale 13.937,15 | permanente 20.460,92; totale 20.460,92 (tabel… | corretto | danno_non_patrimoniale: micropermanent damage now applies the grade coefficient to each point (art. 139 co. 1 lett. a and co. 6 Cod. Ass.) instead of… |
| `danno_parentale` | sito | 8 | 391.103,18 | 391.103,00 | convenzione | danno_parentale: output now carries an avvertenza stating that the Milano 2024 minimum is the old forbice floor and not a limit (the points table sta… |
| `decodifica_codice_fiscale` | sito | 10 | 2029-01-01 (anno_nascita_stimato 2029) | 01/01/1929 | corretto | decodifica_codice_fiscale: the century of the birth year is now the most recent one that does not put the birth date in the future (year 29 decodes t… |
| `decurtazione_punti_patente` | sito | 26 | solo 5 punti | 5 e 10 punti (secondo periodo: 10) | corretto | decurtazione_punti_patente: art. 173 c.3-bis recidiva within two years now 10 points (new cellulare_recidiva entry and punti_recidiva_biennio), suspe… |
| `detrazione_altri_familiari` | sito | 12 | 0.03 (0.01 per familiare) | 0,00 (quoziente 0: 0,0000125 troncato alla qu… | corretto | fix(detrazione_altri_familiari): art. 12 c. 1 lett. d) and c. 4 TUIR: ratio truncated to four decimals, no deduction when the ratio equals one, docst… |
| `detrazione_assegno_coniuge` | sito | 12 | 1265.00 (co. 5 lett. a) | 1955.00 misura fissa (RN7 1.955) | corretto | detrazione_assegno_coniuge: apply art. 13 co. 5-bis TUIR (measure of co. 3: 1,955 up to 8,500, 700 + 1,255 x q, 700 x q) instead of the co. 5 amounts… |
| `detrazione_canone_locazione` | sito | 11 | 2.000,00 | 991,60 (teorica; RN12 989,00 con 364 giorni) | corretto | fix(detrazione_canone_locazione): art. 16 c. 1-ter TUIR: young tenants get 991.60 euro or, if higher, 20% of the rent capped at 2,000 (new canone_ann… |
| `detrazione_coniuge` | sito | 16 | 690.00 | 710.00 (base 690 + maggiorazione 20; RN6 710,… | corretto | detrazione_coniuge: apply the art. 12 co. 1 lett. b) TUIR surcharges (10-30 euro between 29,000 and 35,200), truncate ratios to four decimals (art. 1… |
| `detrazione_figli` | sito | 9 | 1381.82 | 1381.67 (quoziente 0,7272; RN6 1.382,00) | corretto | fix(detrazione_figli): art. 12 c. 1 lett. c) and c. 4 TUIR: ratio truncated to four decimals, no deduction when the ratio equals one, and no 400 euro… |
| `detrazione_lavoro_dipendente` | sito | 15 | 1736.36 | 1801.00 | corretto | detrazione_lavoro_dipendente: add the art. 13 co. 1.1 TUIR surcharge of 65 euro (25,000-35,000), the co. 1 lett. a) minimums of 690/1,380 euro (new t… |
| `detrazione_pensione` | sito | 17 | 535.62 | 713.00 | corretto | detrazione_pensione: add the art. 13 co. 3 lett. a) minimum of 713 euro, the co. 3-bis surcharge of 50 euro (25,000-29,000) and ratios truncated to f… |
| `diritti_copia` | sito | 11 | 1,20 EUR (0,30 x 4) | 1,47 EUR | corretto | Fixed diritti_copia: paper copy rights now follow the fixed per-band amounts of DPR 115/2002 annexes 6 and 7 (D.I. 9 July 2021, +50% art. 4(5) DL 193… |
| `equo_indennizzo` | sito | 8 | 31500.00 | 26400.00 | corretto | equo_indennizzo: amount now follows Tabella 1 of L. 662/1996 (2 x tabular salary x category percentage 100/92/75/61/44/27/12/6), art. 49 DPR 686/1957… |
| `fattura_avvocato` | sito | 9 | CPA 40,01; imponibile IVA 1.040,25; IVA 228,8… | CPA 40,01; Totale imponibile 1.040,25; IVA 22… | corretto | Fixed fattura_avvocato: VAT, CPA and withholding are rounded half-up on exact decimals (art. 5 Reg. CE 1103/97); compensation 1,000.24 now gives IVA … |
| `fattura_enasarco` | sito | 9 | quota agente 4.250,00 (contributo 8.500); net… | quota agente 3.885,95 (fattura 45.717 con Ena… | corretto | fattura_enasarco: applies the annual commission ceiling per agency relationship (Enasarco RAI art. 5; 2026: 45,717 mono / 30,478 pluri), the year-spe… |
| `fattura_professionista` | sito | 9 | contributo 40,01; imponibile IVA 1040,25; IVA… | contributo 40,01; imponibile IVA 1040,25; IVA… | corretto | fattura_professionista: rounds every amount to the cent half-up on Decimal instead of binary float round(), which sent half-cent amounts (e.g. 22% x … |
| `fine_pena` | sito | 17 | 4 semestri, 180 giorni, data_fine_con_liberaz… | Giorni di detrazione spettanti: 135; Fine pen… | corretto | Fixed fine_pena: liberazione anticipata (art. 54 co. 1 L. 354/1975) now counts only the semesters served before release instead of nominal days // 18… |
| `grado_parentela` | sito | 17 |  |  | coincide |  |
| `gratuito_patrocinio` | sito | 9 | ammesso false, nucleo 39.000,00, margine -25.… | rispettato, reddito 9.000,00 (familiare in co… | corretto | gratuito_patrocinio: added diritti_personalita and interessi_in_conflitto parameters, counting only the applicant's own income (art. 76 co. 4 DPR 115… |
| `imposta_registro_locazioni` | sito | 9 | opzione_intera_durata 960,00 | imposta 960,00 - sconto 3,2% (30,72) = 929,00… | corretto | imposta_registro_locazioni: concordato contracts taxed at 2% on 70% of the rent (art. 8 c. 1 L. 431/1998), single-payment option reduced by half the … |
| `imposte_compravendita` | sito | 13 | IVA 10000; 200+200+200; totale 10600 | IVA 10.000; 200+200+200; bollo 230; diritti d… | corretto | fix(imposte_compravendita): luxury dwellings (A/1, A/8, A/9) declared as prima casa are taxed at 9% registro, since the 2% rate is excluded by nota I… |
| `imposte_successione` | sito | 11 |  |  | coincide |  |
| `inflazione_titoli_stato` | sito | 8 |  |  | coincide |  |
| `interessi_acconti` | sito | 10 | dovuto 5373,63 (interessi 373,63) | dovuto 5379,87 (interessi 379,87; residuo 524… | corretto | Fixed interessi_acconti: payments are now imputed first to accrued interest (art. 1194 c.c.), with imputazione='capitale' for imputation with the cre… |
| `interessi_corso_causa` | sito | 0 |  |  | corretto | Saggio legale per domande anteriori all'11/12/2014 (art. 17 co. 2 DL 132/2014); oltre il 31/12/2026 il tool non estende il tasso (aperto) |
| `interessi_legali` | sito | 9 |  |  | corretto | 10% dal 16/12/1990 (art. 1 L. 353/1990, art. 92 co. 1); tassi_legali.json |
| `interessi_mora` | sito | 14 | 900.00 (9,00%) | 800.00 (8,00%) | corretto | Fixed interessi_mora: transactions concluded before 1/1/2013 now use BCE + 7 points (art. 5 c.1 D.Lgs. 231/2002 original text, art. 3 c.1 D.Lgs. 192/… |
| `interessi_tasso_fisso` | sito | 10 | 500.00 | 501.37 | convenzione | Divisore 366 (anno di inizio bisestile) del tool contro 365 del sito; capitalizzazione esponenziale continua contro annuale a date fisse. |
| `interessi_vari_capitale_rivalutato` | sito | 6 | capitale rivalutato 11.614,17; interessi 324,… | capitale rivalutato 11.510,00; interessi 321,… | corretto | fix(interessi_vari_capitale_rivalutato): last-year segment now counts 1 January (art. 2963 c.c., dies a quo excluded only at the start: 365 days for … |
| `lettera_adeguamento_canone` | sito | 9 | 1010.82 (variazione piena 1.08%, metodo 'calc… | 1011.00 (+1,1%) | corretto | fix(lettera_adeguamento_canone): variation used in the letter rounded to one decimal as in the ISTAT communiques (art. 81 L. 392/1978), same as adegu… |
| `menomazioni_plurime` | sito | 10 |  |  | coincide |  |
| `modello_notula` | sito | 14 | compensi 1.696,00 (studio 919 + introduttiva … | compenso 567,00 (fase unica, scaglione 5.201-… | corretto | Fixed: modello_notula now pays each procedure on its own DM 55/2014 table (Tab. VIII monitorio, VI precetto, XVI esecuzione mobiliare, XVII presso te… |
| `nota_spese` | sito | 10 | SG 150,01; CPA 46,00; imponibile 1.196,11; IV… | SG 150,02; CPA 46,00; imponibile 1.196,12; IV… | corretto | Fixed nota_spese: every line is rounded to the cent half-up on exact decimals (art. 5 Reg. CE 1103/97), so half-cent ties no longer depend on float b… |
| `note_iscrizione_ruolo` | sito | 20 | 98.00 | 49,00 (con riduzione 50%) | corretto | Fixed note_iscrizione_ruolo: convalida di sfratto now halves the contributo unificato (art. 13(3) DPR 115/2002), labour cases can flag income above t… |
| `parcella_avvocato_civile` | sito | 15 | 17.107 + 11.284 + 50.250 + 29.753 = 108.394 (… | Scaglione 130 + ValoreCausa 32000000,01: 22.2… | corretto | Fixed: parcella_avvocato_civile (and preventivo_civile) above 32 million euro now applies the art. 6 co. 1 DM 55/2014 +30% for each further doubling … |
| `parcella_avvocato_penale` | sito | 11 |  |  | coincide |  |
| `parcella_stragiudiziale` | sito | 17 | 6164 EUR | 18000 EUR (3% del valore, metodo F) | corretto | Fixed: parcella_stragiudiziale above 520,000 euro now applies the decreasing percentage of Tab. 25 (art. 22 DM 55/2014: 3% up to 2 million ... 0.25% … |
| `parcella_volontaria_giurisdizione` | sito | 12 | 6804 (3.402 + 3.402; lo scaglione 'oltre 5200… | 8846 (scaglione 'Da € 520.001 a € 1.000.000',… | convenzione | Oltre 520.000: ultimo scaglione senza aumento (art. 6 e' facoltativo, 'fino al 30%'), contro il 30% pieno del sito e di parcella_avvocato_civile. Rip… |
| `pena_concordata` | sito | 9 | 5.44 mesi (163,2 gg); passaggi 12,23 -> 8,16 … | 1 anno, 7 giorni -> 8 mesi, 4 giorni (244 gg)… | convenzione | Sito: troncamento della frazione di giorno a ogni passaggio; tool: mesi continui a due decimali, nessun troncamento. |
| `pensione_reversibilita` | sito | 12 | 8.000,00 | 10.000,00 (coniuge 6.000 ridotto + figlio 4.0… | corretto | fix(pensione_reversibilita): added the Tabella F safeguard clause (art. 1 co. 41 L. 335/1995), no cumulation reduction for households with minor, stu… |
| `pignoramento_stipendio` | sito | 17 | pignorabile 86,24; minimo 1.068,82 (assegno 2… | pignorabile 81,50; minimo 1.092,48 (assegno 2… | corretto | pignoramento_stipendio: default assegno sociale updated to 2026 (546,24, INPS circular 153/2025, art. 545 co. 7 c.p.c.) and pignorabile rounded half-… |
| `prescrizione_diritti` | sito | 10 | 2026-10-04 | 2026-10-05 | corretto | prescrizione_diritti: a limitation period expiring on a Sunday or national holiday is extended to the next non-holiday day (art. 2963 c. 3 c.c.); new… |
| `prescrizione_reato` | sito | 17 |  |  | coincide |  |
| `preventivo_civile` | sito | 17 |  |  | coincide |  |
| `preventivo_stragiudiziale` | sito | 9 | compenso 9246; SG 1386,90; CPA 425,32; totale… | pagina secondaria di liquidazione, tabelle 20… | corretto | Fixed: preventivo_stragiudiziale above 520,000 euro now uses the Tab. 25 decreasing percentage (art. 22 DM 55/2014) instead of the last fixed band; m… |
| `preventivo_volontaria_giurisdizione` | sito | 8 | compensi 4.536; totale onorari 6.618,57 | compenso 5.897 (4.536 x 1,3 = 5.896,80, arrot… | convenzione | Oltre 520.000 senza aumento art. 6, dichiarato in docstring. |
| `pronti_termine` | sito | 5 | lordi 863,01; imposta 107,88; netti 755,14; n… | lordi 863,01; ritenuta 107,88; netti 755,14; … | sito errato |  |
| `rateizzazione_imposte` | sito | 10 | scadenze 28/06, 28/07, 28/08; capitale 1000 x… | scadenze 30/06, 16/07, 20/08; capitale 1000 x… | corretto | Fixed rateizzazione_imposte: interest on each instalment (AdE table 0.18% then +0.33% per month) instead of on the residual balance, instalments on t… |
| `ravvedimento_operoso` | sito | 13 | sanzione 4,17 (0,4167%); interessi 0,22 (1,6%… | sanzione 4,20 ('1/15 x 1,25% x 5 giorni = 0,4… | corretto | Fixed ravvedimento_operoso: new optional data_scadenza; lett. b threshold is the dichiarazione deadline (31 Oct of the following year, art. 13 c. 1 D… |
| `regime_forfettario` | sito | 13 | reddito 4.000,00; reddito_imponibile 0 (max(.… | imponibile 4.000,00; imponibile al netto dei … | convenzione | Eccedenza contributi: tool imponibile 0, sito -1.000 (deducibile dal reddito complessivo, art. 10 TUIR). |
| `rendimento_bot` | sito | 5 | scarto 300,00; imposta 37,50; netto 262,50; l… | capital gain 300,00; ritenuta 37,50; netto 26… | corretto | rendimento_bot: net yield now computed on the real outlay (price + substitute tax + commission, tax withheld at subscription, MEF BOT sheet), commiss… |
| `ricerca_codici_ateco` | sito | 9 |  |  | da chiarire | Coefficienti da riconciliare con l'Allegato 4 L. 190/2014 e con ATECO 2025 (tabella da_verificare): fonte non riletta |
| `ricevuta_prestazione_occasionale` | sito | 9 | ritenuta 1.200,00; netto 4.800,00 | ritenuta 1.200,00; ritenuta INPS a carico del… | corretto | ricevuta_prestazione_occasionale: now computes the worker's third of the INPS Gestione separata contribution on the excess over 5,000 euro a year (ar… |
| `risarcimento_inail` | sito | 8 | 12600.00 (42% della retribuzione) | 8178.02 (punto 1.682,72 x 6 x (1 - 19% riduzi… | errato, non corretto | risarcimento_inail: rendita patrimoniale quota now retribuzione x coefficient of the D.M. 12/07/2000 table x grade (art. 13 co. 2 lett. b D.Lgs. 38/2… |
| `ritenuta_acconto` | sito | 7 |  |  | coincide |  |
| `rivalutazione_annuale_media` | sito | 8 | 11866.20 (coeff. 1,18662) | 11878.71 | corretto | fix(rivalutazione_annuale_media): annual means now come from the rebuilt ISTAT FOI series (2011 to 2013 gives 10,417.79 instead of 10,241.66; 2005 to… |
| `rivalutazione_mensile` | sito | 5 | 12 mens., riv. 611,11, tot. 12.611,11 | 12 mens., riv. 625,39, tot. 12.625,39 | corretto | fix(rivalutazione_mensile): FOI series 1996-2019 rebuilt from the ISTAT monthly series (SDMX, senza tabacchi); the old table was wrong in 1990-2019 a… |
| `rivalutazione_monetaria` | sito | 8 | 11925.78 (da 99,7 a 118,9; coefficiente 1,192… | 11960.00 (indice di gen. 2015 = 106,5 in base… | corretto | fix(rivalutazione_monetaria): FOI indices for 1996-2019 taken from the ISTAT monthly series with the official linking coefficients 1,373 (1995->2010)… |
| `rivalutazione_storica` | sito | 8 | 11866.20 (coeff 1,18662; media 2015 = 100,02) | 11870.00 (coeff 1,187; indice storico 7649,81… | corretto | fix(rivalutazione_storica): annual means now computed on the corrected ISTAT FOI series (e.g. 2000->2020 coefficient 1.342967 instead of 1.237529); c… |
| `rivalutazione_tfr` | sito | 6 | rivalutazioni 2022: 199,49; 2023: 81,64; tota… | coefficienti 9,974576 e 1,944163; rivalutazio… | corretto | fix(rivalutazione_tfr): revaluation computed on the fund net of the substitute tax charged each year (art. 11 co. 4 D.Lgs. 47/2000), tax 11% up to 20… |
| `scadenza_processuale` | sito | 14 | 2027-10-05 | 2027-10-04 | sito errato |  |
| `scadenze_impugnazioni` | sito | 17 |  |  | coincide |  |
| `scadenze_multe` | sito | 10 | 2025-08-19 | 2025-09-19 | corretto | Fixed scadenze_multe: the giudice di pace appeal now applies the August feriale suspension (art. 1 L. 742/1969, art. 7 D.Lgs. 150/2011, Cass. 30427/2… |
| `scorporo_iva` | sito | 10 | imponibile 0.12; iva 0.01 | imponibile 0,13; iva 0,01 | convenzione | Tool: imponibile arrotondato e IVA per differenza (somma = importo ivato); sito: half-up indipendente su ciascuna cifra. Sui mezzi centesimi esatti i… |
| `sollecito_pagamento` | sito | 13 | 94,67 (9,00% = BCE 1,00 + 8 punti, 77 gg, div… | 84,38 (8,00% = BCE 1,00 + 7 punti, 77 gg, div… | corretto | sollecito_pagamento: BCE + 7 points for transactions concluded by 31/12/2012 (new data_contratto parameter, art. 5 D.Lgs. 231/2002 pre D.Lgs. 192/201… |
| `spese_condominiali` | sito | 9 | 12000.00 (nessun errore) | rifiuto: 'La somma dei millesimi è superiore … | corretto | fix(spese_condominiali): reject millesimi above 1000; lift expense split over the sum of building heights as per art. 1124 c.c. (was normalised on a … |
| `spese_mediazione` | sito | 8 | totale_per_parte 146,40 (120 + IVA 26,40) | TOTALE GENERALE 202,52 (avvio 40 + primo inco… | corretto | spese_mediazione: rebuilt on DM 150/2023 (arts. 28, 30, 31, Tabella A with 12 brackets): avvio 40/75/110, first-meeting fee 60/120/170, +10%/+25% sur… |
| `spese_trasferta_avvocati` | sito | 5 | rimborso_km 60,00 (0,30 euro/km); indennita 5… | Rimborso chilometrico 72,00 (200 x 1,80 x 20%) | corretto | Fixed spese_trasferta_avvocati: kilometric allowance is now one fifth of the fuel price per litre (art. 27 DM 55/2014) via the new prezzo_carburante_… |
| `tariffe_mediazione` | sito | 7 | avvio 40; indennità neg 60; indennità pos 120… | avvio 40; primo incontro 60; Tabella A (valor… | corretto | tariffe_mediazione: rebuilt on the DM 150/2023 Tabella A (12 brackets, min/max/mean), first-meeting fee and the four outcome scenarios with the art. … |
| `tasso_alcolemico` | sito | 7 |  |  | corretto | Confini delle fasce come da art. 186 co. 2 ('superiore a', 'non superiore a'); il picco Widmark resta una stima (convenzione) |
| `termini_183_190_cpc` | sito | 11 | n1 2025-06-03, n2 2025-06-30, n3 2025-07-21 | n1 2025-06-03, n2 2025-07-03, n3 2025-07-23 | convenzione | Decorrenza dei termini successivi: dall'udienza (tool, 30/60/80 e 60/80 giorni, prudenziale) contro a catena dalla scadenza precedente prorogata ex a… |
| `termini_deposito_atti_appello` | sito | 10 | 2025-07-04 | 2025-07-05 | convenzione | Termine a ritroso con data grezza di domenica: venerdi (tool, prudenziale) contro sabato (sito). Caso appellante di sabato: tool corretto per art. 15… |
| `termini_deposito_ctu` | sito | 7 | 2025-09-01, 2025-09-15, 2025-09-29 | 2025-09-01, 2025-09-16, 2025-10-01 | convenzione | Dies a quo dei termini successivi: scadenza non prorogata (tool) contro scadenza prorogata (sito). Commento aggiunto in tests/comparison/test_termini… |
| `termini_esecuzioni` | sito | 14 | 2025-08-18 | 2025-08-16 | da chiarire | Doppia proroga (festivo poi sabato) contro proroga singola. Commento aggiunto in tests/comparison/test_termini_esecuzioni.py. |
| `termini_memorie_repliche` | sito | 8 |  |  | coincide |  |
| `termini_procedimento_semplificato` | sito | 11 | 2025-10-27 / 2025-11-04 | 2025-10-27 / 2025-11-06 | convenzione | Fix statute references in termini_procedimento_semplificato: 10-day filing term is art. 281-undecies co. 2, 20+10 day briefs are art. 281-duodecies c… |
| `termini_processuali_civili` | sito | 9 |  |  | coincide |  |
| `termini_separazione_divorzio` | sito | 9 | 2025-12-29 | 2025-12-27 | da chiarire | Doppia proroga festivo poi sabato (tool: 2025-12-29) contro singola (sito: 2025-12-27). Commento aggiunto in tests/comparison/test_termini_separazion… |
| `variazioni_istat` | sito | 5 | 2022 8,01; 2023 5,43; 2024 0,88 (cumulata 14,… | 2022 +8,1; 2023 +5,4; 2024 +0,8 | corretto | fix(variazioni_istat): annual FOI variations recomputed on the corrected ISTAT series (2009 +0.68 instead of -0.65); first year of the series has a n… |
| `verifica_iban` | sito | 8 | valido=False (non inizia con IT) | valido=True | convenzione | Ambito volutamente limitato agli IBAN italiani; San Marino formalmente valido ma fuori ambito |
| `verifica_partita_iva` | sito | 10 | codice_ufficio='00' | Ufficio=015 Milano, Lodi | corretto | verifica_partita_iva: codice_ufficio now reads digits 8-10 (was digits 1-2), new matricola field; the office code list is still not validated. |
| `verifica_usura` | sito | 31 | nessun errore; cade su Prestiti personali: TE… | Anticipi su crediti e sconti: TEGM 8,12; sogl… | corretto | verifica_usura: leasing strumentale 2025-Q1 TEGM corrected from 7.44 to 9.75 (MEF decree Allegato A, 1 Jan-31 Mar 2025, threshold 16.1875); threshold… |
| `calcolo_naspi` | fonte ufficiale | 7 | 900.00 al mese per 1,4 mesi (totale 1.260,00) | Art. 3 co. 1 lett. b D.Lgs. 22/2015: servono … | corretto | calcolo_naspi: below 13 weeks of contribution the outcome is 'non_spettante' with no amount (art. 3 co. 1 lett. b D.Lgs. 22/2015); the 3% monthly red… |
| `calcolo_sanzione_gdpr` | fonte ufficiale | 9 | lettere a)-j) (10 elementi) | art. 83(2) vigente: lettere a)-k); k) 'eventu… | corretto | calcolo_sanzione_gdpr: art. 83(2) criteria now list letters a) to k) (k added), the range follows the EDPB Guidelines 04/2022 v2.1 method (new `gravi… |
| `cerca_codice_tributo` | fonte ufficiale | 12 | 1840 / Imposta sostitutiva regime forfettario… | 1840: imposta sostitutiva sui canoni di locaz… | corretto | Fixed `cerca_codice_tributo`: re-read src/data/codici_tributo.json on the AdE code tables of 23/09/2026 (erariali e regionali) and 27/07/2026 (F24 EL… |
| `costi_costituzione` | fonte ufficiale | 7 | Da 2.375,87 a 3.375,87 euro: notaio 1.500-2.5… | Registro 200, bollo 156, diritti 90, diritto … | corretto | Fixed costi_costituzione: SRLS now includes the concession tax (EUR 309.87, art. 3 co. 3 DL 1/2012 does not exempt it; total 629.87), SAS/SNC include… |
| `costo_lavoro` | fonte ufficiale | 9 | irpef_stimata 4.286,60; netto_stimato 22.956,… | Imponibile 27.243; imposta lorda 6.265,89. De… | corretto | costo_lavoro: apprentice worker share 5.84% (INPS circ. 128/2012), +1% above the first pensionable band (art. 3-ter DL 384/1992, INPS circ. 6/2026), … |
| `indennita_preavviso` | fonte ufficiale | 15 | 733,33 euro (2.200/30 x 10 giorni) | Art. 1, seconda tabella: 'Fino a 5 anni', liv… | corretto | indennita_preavviso: importo without intermediate rounding (art. 2118 co. 2 c.c., 150 days on 1.000 euro = 5.000,00); metalmeccanici C1_D1_D2 use the… |
| `rendimento_btp` | fonte ufficiale | 8 | rendimento netto 5,1481% (5,1120% con anni_sc… | lordo MEF 4,61% (TIR lordo ricostruito 4,6102… | convenzione | Aliquota (12,5%) e aritmetica di cedole e scarto coincidono con la norma. La formula del rendimento pero' e' semplice, non composta: rendimento_netto… |
| `rendimento_buoni_postali` | fonte ufficiale | 13 | lordo 10.050,00; netto 10.043,75 | coefficienti 1,00750000 / 1,00656250 -> 10.07… | corretto | rendimento_buoni_postali: rewritten on the CDP fogli informativi coefficients per series (new table buoni_postali, @sourced: ordinario TF120A250624 T… |
| `valutazione_data_breach` | fonte ufficiale | 6 | livello molto probabile; notifica True; comun… | art. 34(3)(a): misure che rendono i dati inco… | corretto | valutazione_data_breach: the art. 34(3)(a) exemption from communicating to data subjects now applies only to confidentiality breaches with encryption… |
| `verifica_necessita_dpia` | fonte ufficiale | 11 | dpia_necessaria True; n_criteri 2 (criterio 5… | nove criteri WP248 del provv. 467/2018 senza … | corretto | verifica_necessita_dpia: the transfer outside the EU no longer counts as a WP248 criterion (provv. Garante 467/2018); the DPIA is now also required b… |
| `analisi_base_giuridica` | norma | 13 | base_consigliata='consenso' (Art. 6(1)(a)), a… | Art. 6(1)(b) GDPR: 'il trattamento è necessar… | corretto | Fixed analisi_base_giuridica: the matrix entry is now chosen from the processing (order execution rests on art. 6(1)(b) GDPR, employee video surveill… |
| `compenso_occ` | norma | 6 | 5.000,00 (5%) | Art. 16 co. 2 e co. 4 D.M. 202/2014, con l'ar… | corretto | compenso_occ: fee now computed as the range of art. 16 D.M. 202/2014 (attivo and passivo with the D.M. 30/2012 curatore percentages, reduced by 15-40… |
| `competenza_giudice` | norma | 13 | Tribunale, 'Art. 9 c.p.c. - materia riservata… | Giudice di Pace: art. 7 co. 1 (credito fino a… | corretto con riserva | Fixed competenza_giudice: condominio is no longer treated as reserved to the Tribunale (art. 7 co. 1 and co. 3 n. 2 c.p.c.), art. 9 co. 2 exclusive m… |
| `composizione_negoziata` | norma | 7 | ammissibile false, 'nessuna soglia rispettata… | Non e' impresa minore: manca solo il requisit… | corretto | Il tool attribuisce l'accesso dell'impresa agricola all'art. 25-quater, che riguarda le imprese sotto soglia. Per il tipo sotto_soglia il messaggio e… |
| `concordato_preventivo` | norma | 7 | nota: apporto esterno 'che incrementi di alme… | Art. 84 co. 4 vigente: 'un apporto di risorse… | corretto | concordato_preventivo: the 20% threshold now covers chirografari plus privileged creditors degraded for incapienza (art. 84 co. 4-5 CCII), external-r… |
| `confronto_investimenti` | norma | 8 | imposta -25,93; montante lordo 9.900,25; mont… | Art. 45 co. 1 TUIR: il reddito di capitale è … | corretto | confronto_investimenti: substitute tax clipped at zero on negative yields (art. 45 co. 1 TUIR, art. 3 co. 1 D.L. 66/2014, art. 2 co. 1 D.Lgs. 239/199… |
| `indennita_licenziamento` | norma | 7 | 6 mensilita', 12.000 euro presentato come 'ri… | art. 3 co. 2: indennita' 'corrispondente al p… | corretto | indennita_licenziamento: with tipo='reintegra' the ceiling is 12 mensilita whatever the seniority (art. 3 co. 2 D.Lgs. 23/2015, was min(anni x 2, 12)… |
| `offerta_conciliativa` | norma | 6 |  |  | coincide |  |
| `quorum_assembleari` | norma | 10 | delibera valida (45.000 su 60.000 = 75%, supe… | non approvata. Art. 2368 co. 2, primo periodo… | corretto | fix(quorum_assembleari): quorums rewritten on artt. 2368-2369, 2479-bis co. 3, 2487, 2538 c.c.; new parameters convocazione and ricorso_mercato_capit… |
| `scadenze_licenziamento` | norma | 5 |  |  | da chiarire | Il computo dei tre termini (60/180/60 giorni di calendario, dies a quo escluso, senza sospensione feriale) e la decorrenza dei 180 giorni dall'invio … |
| `scadenze_societarie` | norma | 5 | 30/05/2026, con citazione dell'art. 2436 c.c. | il verbale di approvazione si deposita insiem… | corretto | fix(scadenze_societarie): verbale filed under art. 2435 co. 1 (not art. 2436), added the art. 2429 co. 1 communication to sindaci and weekend warnings |
| `soglie_organo_controllo_srl` | norma | 5 | superato il limite dei ricavi, obbligo_nomina… | limite superato, ma l'obbligo nasce solo con … | corretto | fix(soglie_organo_controllo_srl): obbligo_nomina no longer asserted on a single esercizio (art. 2477 co. 2 lett. c c.c.); optional previous-esercizio… |
| `tassazione_atti` | norma | 14 | 1500.00 | 200.00 in misura fissa (Nota II all'art. 8 Ta… | corretto | tassazione_atti: taxes judicial acts by content (DPR 131/1986 Tariffa I art. 8 lett. a-c with Notes I and II, art. 40, art. 41 co. 2), exempts causes… |
| `test_crisi_impresa` | norma | 7 | indicatore 'servizio del debito nei 6 mesi' | Art. 3 co. 3 lett. b): 'almeno per i dodici m… | corretto | Il tool riprende gli indicatori della versione originaria (DSCR a 6 mesi, debiti/attivo, ritardi misurati a giorni), non piu' vigente dopo il D.Lgs. … |
| `verifica_mediazione_obbligatoria` | norma | 10 | obbligatoria=false (la tabella usa la voce 'r… | true: art. 5 co. 1 '... franchising, opera, r… | corretto | Fixed verifica_mediazione_obbligatoria: exact/alias matching with accent normalisation instead of substring (rete, contratto di rete, responsabilita … |
| `cerca_brocardi` | chiamata reale | 3 | 204 riferimenti su 500 sono decisioni del 200… | L'indice Italgiure contiene solo decisioni da… | corretto | cerca_brocardi: Cassazione references older than the Italgiure archive (a moving window, from 27/01/2021 penal and 17/02/2021 civil on 2026-09-28) ar… |
| `cerca_ddl` | chiamata reale | 2 |  |  | coincide |  |
| `cerca_delibere_consob` | chiamata reale | 4 | '### Delibera n. 14' (titolo 'Richiamo di att… | Link reali: /-/richiamo-di-attenzione-n-14-25… | corretto | CONSOB Bollettino: results that are not delibere (Comunicazione n. 13/25, Richiamo di attenzione n. 14/25, protocol-numbered comunicazioni, unnumbere… |
| `cerca_gazzetta_ufficiale` | chiamata reale | 3 | Nessun atto trovato in Gazzetta Ufficiale per… | Il sito trova un solo atto e reindirizza a ca… | corretto | Fixed cerca_gazzetta_ufficiale: a search with a single hit (the site redirects to the atto page) is no longer reported as 'no results', result pages … |
| `cerca_giurisprudenza` | chiamata reale | 4 | «Nessuna decisione trovata con la query origi… | Nell'indice le Sezioni Unite hanno codice U: … | corretto | build_search_params inserisce sezione così com'è (fq szdec:{sezione}). Il docstring e _SEZIONI del client usano SU e T, codici che l'indice non conti… |
| `cerca_giurisprudenza_amministrativa` | chiamata reale | 3 | Nessuna data nella risposta: data_deposito è … | 09/11/2021, da <dataPubblicazione> dell'XML u… | corretto | cerca_giurisprudenza_amministrativa no longer promises a date the portal search page does not carry (date of publication, art. 89 c.p.a., is read by … |
| `cerca_giurisprudenza_cgue` | chiamata reale | 6 | C-311/2018 | C-311/18 | corretto | cerca_giurisprudenza_cgue: the corte filter compares the CELEX type through STR() (CELLAR stores it as xsd:string, so it returned nothing), one entry… |
| `cerca_giurisprudenza_tributaria` | chiamata reale | 3 | Nessun provvedimento CeRDEF trovato per: _con… | Stessa ricerca sul portale con il modulo attu… | corretto | cerca_giurisprudenza_tributaria: already fixed by the 2.14.2 CeRDEF search-form rewrite (#46); no further change in this phase. |
| `cerca_giurisprudenza_unificata` | chiamata reale | 12 | 20 blocchi per 10 decisioni distinte: ogni se… | CELLAR SPARQL (2026-09-25): 15 sentenze disti… | corretto | Fixed cerca_giurisprudenza_unificata: the all-words fallback for multi-word CGUE queries now calls the CGUE library with required_terms, so 'clausole… |
| `cerca_marchi` | chiamata reale | 3 |  |  | coincide |  |
| `cerca_pronuncia_costituzionale` | chiamata reale | 4 | intestazione '**Trovate 1 pronunce della Cort… | il piano si aspetta pronunce del 2026 e un me… | convenzione | _cerca_pronuncia_costituzionale_impl (src/tools/corte_cost.py) indica il perimetro della ricerca solo nel ramo no_results; l'intestazione dei risulta… |
| `cerca_provvedimenti_garante` | chiamata reale | 4 | Nessun provvedimento trovato per: _linee guid… | The same dates sent to the portal as AAAA-MM-… | corretto | cerca_provvedimenti_garante: dates given as GG/MM/AAAA (as documented) are converted to AAAA-MM-GG, the only format the Garante portal's <input type=… |
| `cerdef_leggi_provvedimento` | chiamata reale | 2 | '# ': 2 caratteri, intestazione vuota, succes… | xmlDettaglio con estremi 'Sentenza del 09/12/… | corretto | cerdef_leggi_provvedimento: an unknown GUID is now reported as 'provvedimento non trovato o GUID non valido' (not_found, no retries) instead of a sou… |
| `cite_law` | chiamata reale | 5 | urn 'urn:nir:stato:legge:1969-01-01;742~art1'… | URN ufficiale urn:nir:stato:legge:1969-10-07;… | corretto | cite_law: recitals of EU acts return the whole text (number cell + text cell of div#rct_N on CELLAR, Reg. (UE) 2016/679 recital 42), an act cited wit… |
| `ddl_su_norma` | chiamata reale | 3 |  |  | coincide |  |
| `download_law_pdf` | chiamata reale | 3 | '**Errore** download PDF EUR-Lex: EUR-Lex did… | Il PDF ufficiale in italiano del CELEX 32016R… | corretto | download_law_pdf: EU acts are downloaded from CELLAR by content negotiation (Accept application/pdf;type=pdfa1a with pdfa2a/pdf1x/pdfx fallbacks, Acc… |
| `elenco_misure_nazionali` | chiamata reale | 5 | **Recepimento italiano della direttiva 32019L… | misure francesi | corretto | elenco_misure_nazionali names the requested Member State in the heading and in the no-measures message ("Recepimento in Francia (FRA)", "Nessuna misu… |
| `fetch_act_index` | chiamata reale | 2 |  |  | coincide |  |
| `fetch_full_act` | chiamata reale | 3 | '# Normattiva - Il portale della legge vigent… | LEGGE 7 ottobre 1969, n. 742 - Sospensione de… | corretto | fetch_full_act: short acts no longer fall back to the HTML walker (AKN export validated by structure instead of a 40,000-byte floor; L. 742/1969 expo… |
| `fetch_law_annotations` | chiamata reale | 3 | Nessuna sezione '## Testo dell'articolo'; rub… | Brocardi mostra il testo dell'articolo ('Qual… | corretto | fetch_law_annotations: the article text ('Testo dell'articolo', Brocardi div.corpoDelTesto.dispositivo, art. 2043 c.c.) is no longer dropped silently… |
| `fetch_law_article` | chiamata reale | 3 |  |  | coincide |  |
| `get_eu_basis` | chiamata reale | 5 | Nessuna base giuridica UE trovata per D.Lgs. … | 32002L0058: la notizia 72002L0058ITA_117422 e… | corretto | get_eu_basis now finds acts whose CELLAR notice has no resource_legal_id_local (e.g. D.Lgs. 196/2003 -> directive 2002/58/CE, MNE 72002L0058ITA_11742… |
| `get_italian_implementation` | chiamata reale | 3 | Entrata in vigore: 2021-11-27 | 12/12/2021 secondo Normattiva, cioè 27/11/202… | corretto | get_italian_implementation no longer prints CELLAR's copy of the Gazzetta Ufficiale date as "Entrata in vigore" (D.Lgs. 177/2021: GU 27/11/2021, in f… |
| `giurisprudenza_amm_su_norma` | chiamata reale | 2 |  |  | coincide |  |
| `giurisprudenza_articolo` | chiamata reale | 3 | 10 decisioni elencate, 4 citano l'art. 2043. … | OCR delle 10 decisioni: art. 2043 presente in… | corretto | _safe_search passa i primi 300 caratteri della massima a _cerca_giurisprudenza_impl. Con più di 50 risultati questa applica _auto_refine, e il passag… |
| `giurisprudenza_cgue_su_norma` | chiamata reale | 3 | 'Nessuna sentenza CGUE trovata per la norma: … | decisioni della Corte dal 2025 con 'direttiva… | corretto | giurisprudenza_cgue_su_norma: the reference is normalised (art./artt./articolo -> 'articolo N', 'direttiva 2006/112/CE' -> '2006/112', GDPR -> 2016/6… |
| `giurisprudenza_su_norma` | chiamata reale | 3 | «Trovate 12920 decisioni». Le prime 10 citano… | Decisioni civili 2022 con 'art. 13' e un marc… | corretto | build_norma_variants mette sempre in OR le varianti nude "art. N" e "articolo N" con quelle qualificate. Per sigle che non sono né codici né tipi di … |
| `iter_ddl` | chiamata reale | 4 |  |  | coincide |  |
| `leggi_atto_gazzetta` | chiamata reale | 5 | Intestazione '# Atto 22G00158', senza oggetto… | h2.consultazione: 'DECRETO LEGISLATIVO 10 ott… | corretto | Fixed leggi_atto_gazzetta: the atto page is read with the ELI segment of its series (s1..s5, p2), the header now reports estremi, oggetto and GU refe… |
| `leggi_delibera_consob` | chiamata reale | 2 |  |  | coincide |  |
| `leggi_marchio` | chiamata reale | 2 | **Errore**: tmview non raggiungibile. Server … | TMview risponde sempre (3 esecuzioni su 3) HT… | corretto | leggi_marchio: an unknown ST13 (TMview HTTP 500 "Can't get trademark/design detail") is now reported as no_results ("ST13 inesistente o scheda moment… |
| `leggi_pronuncia_costituzionale` | chiamata reale | 5 | 25.225 caratteri, con '*[Testo troncato a 250… | dispositivo del dump (5.840 caratteri): '1) d… | corretto | leggi_pronuncia_costituzionale: the dispositivo and the epigrafe are always returned in full and only the reasons are cut to the 25,000-character bud… |
| `leggi_provvedimento_amm` | chiamata reale | 5 | Nessun «P.Q.M.»: il testo si ferma al caratte… | Il P.Q.M. inizia al carattere 104.513: dichia… | corretto | leggi_provvedimento_amm no longer hands PDF bytes over as full text (PDF-only provvedimenti get an explicit message with the official URL), always ke… |
| `leggi_provvedimento_garante` | chiamata reale | 3 | Title '# Linee guida cookie e altri strumenti… | DocWeb 9677876: Linee guida cookie of 10 June… | corretto | leggi_provvedimento_garante: an unavailable DocWeb id (portal page 'Il contenuto o il file richiesto non e' disponibile') is now an explicit error in… |
| `leggi_sentenza` | chiamata reale | 5 | Manca la sezione '## Dispositivo', perché all… | Il principio di diritto («…parzialmente nulli… | corretto | format_full_text tiene solo i primi _MAX_OCR_LENGTH=30000 caratteri dell'OCR, e nelle decisioni lunghe il principio di diritto e il P.Q.M. stanno in … |
| `leggi_sentenza_cgue` | chiamata reale | 2 | testo troncato a 25.000 caratteri su 189.410;… | il dispositivo, che contiene l'invalidità del… | corretto | leggi_sentenza_cgue: over 25000 characters the text keeps its beginning and the operative part from the last 'Per questi motivi' (art. 87(i) Rules of… |
| `mappa_orientamento` | chiamata reale | 2 | contrasto/difformità 64 (17 + 2 + 45); consol… | Italgiure, decisioni distinte: contrasto 63, … | corretto | L'ancoraggio Brocardi è corretto. La mappa però è prodotta da _orientamento_su_norma_impl e ne eredita tutti i difetti: varianti nude per gli atti no… |
| `orientamento_su_norma` | chiamata reale | 6 | 61.173 decisioni per 'art. 13 GDPR'; 985 pron… | Italgiure, civile dal 2022: decisioni che cit… | corretto | (a) build_norma_variants (src/lib/italgiure/client.py) aggiunge sempre le varianti nude '"art. N"' e '"articolo N"'. Quando l'atto non è un codice ri… |
| `orientamento_su_principio` | chiamata reale | 3 | 1.595 decisioni; 14 pronunce SS.UU., mostrate… | Italgiure: SS.UU. n. 41994/2021 dep. 30/12/20… | corretto | Sia _fetch_ss_uu sia la query principale usano edismax con mm '2<75% 5<60%': con 6 termini ne bastano 3, e 'schema', 'nullità' e 'parziale' fanno ent… |
| `pronunce_cost_su_norma` | chiamata reale | 4 | 10 massime, tutte del 2015 (pronunce 1, 3, 10… | la docstring dice che il valore predefinito '… | corretto | pronunce_cost_su_norma: with no years the search now runs from the current year down to 1956 (the massime bundle named 2001_2015 holds every year up … |
| `scarica_pdf_gazzetta` | chiamata reale | 3 | **Errore**: gazzetta_ufficiale non raggiungib… | Errore di input (formato AAAA-MM-GG), senza a… | corretto | Fixed scarica_pdf_gazzetta: the PDF URL uses the ELI segment of the requested series (.../s4/pdf for Concorsi, not .../sg/pdf which the site redirect… |
| `sommario_gazzetta` | chiamata reale | 4 | Solo gli estremi ('DECRETO 9 agosto 2018', 'C… | Ogni span.risultato ha un secondo link con l'… | corretto | Fixed sommario_gazzetta: the sommario now reads estremi, issuer and oggetto of each atto (two anchors per span.risultato, shared parser with the sear… |
| `ultime_delibere_consob` | chiamata reale | 2 | 'Delibera n. 0117520' (Comunicazione n. 01175… | Nel Bollettino sono comunicazioni, con link d… | corretto | Same CONSOB Bollettino fix (shared parser and formatter): unnumbered Avvisi and Orientamenti are no longer silently dropped, non-delibere carry their… |
| `ultime_gazzette` | chiamata reale | 3 | 26R00166, 26R00167, 26R00168, 26R00169 (Provi… | /rss/S1 è la 1a Serie speciale Corte costituz… | corretto | Fixed ultime_gazzette: RSS_CODE follows the official numbering of the special series (S1 Corte costituzionale, S2 Unione europea, S3 Regioni, S4 Conc… |
| `ultime_pronunce` | chiamata reale | 4 | «Nessuna decisione recente trovata con i filt… | Codice indice U (3046 decisioni civili delle … | corretto | fq szdec:{sezione} con il valore così com'è: il docstring documenta SU e T, codici che nell'indice non esistono (ci sono U e 5). format_estremi non i… |
| `ultime_pronunce_cost` | chiamata reale | 1 |  |  | coincide |  |
| `ultime_sentenze_cgue` | chiamata reale | 2 | 'Nessuna sentenza CGUE recente trovata.' | sentenze della Corte del 24/09/2026 presenti … | corretto | ultime_sentenze_cgue: corte filter now returns the latest decisions of the Court or of the General Court (STR on the CELEX type), each decision once,… |
| `ultime_sentenze_tributarie` | chiamata reale | 1 | Nessuna sentenza tributaria recente trovata s… | Portale: 50 risultati su 5 pagine, in ordine … | corretto | ultime_sentenze_tributarie: already fixed by the 2.14.2 CeRDEF search-form rewrite (#46); the publication delay is already declared in the docstring. |
| `ultimi_provvedimenti_amm` | chiamata reale | 2 |  |  | coincide |  |
| `ultimi_provvedimenti_garante` | chiamata reale | 2 | Nessun provvedimento recente trovato. | The portal has recent provvedimenti: 10297334… | corretto | ultimi_provvedimenti_garante: tipologia is applied server-side through the portal's idsTipologia ('provvedimento' = Provvedimenti 10533 plus descenda… |
| `verifica_anteriorita_marchio` | chiamata reale | 2 |  |  | coincide |  |
| `verifica_citazioni` | chiamata reale | 5 | 'inesistente' - 'Decisione n. 10579/2021 non … | La decisione esiste: ordinanza del 21/04/2021… | corretto | verifica_citazioni: the Italgiure archive start is read from the archive (moving window, 17/02/2021 civil and 27/01/2021 penal on 2026-09-28) instead… |
| `verifica_dpa_fornitore` | chiamata reale | 4 | verdetto 'non_trovato', url_evidenza null, ma… | DPA dedicato pubblicato a https://stripe.com/… | corretto | verifica_dpa_fornitore: the probe now sends Accept-Language en-US and the judge recognises Italian DPA titles and plural duty wording (art. 28 paras … |
| `verifica_partita_iva_vies` | chiamata reale | 2 |  |  | coincide |  |
| `attestazione_conformita` | documento | 4 | testo: art. 196-octies e art. 196-undecies; r… | art. 196-octies co. 2 (estrazione e attestazi… | corretto | attestazione_conformita: cites art. 196-novies (not 196-decies) for the copy of an analog act filed by the lawyer and drops the repealed artt. 16-bis… |
| `atto_di_precetto` | documento | 6 | titolo 'ritualmente notificato' senza data; a… | art. 480 co. 2: indicazione, a pena di nullit… | corretto | atto_di_precetto: template now states the date of notification of the title (art. 480 co. 2 c.p.c., null if missing), the full over-indebtedness warn… |
| `decreto_ingiuntivo` | documento | 9 | Tribunale - Sezione Lavoro; CU 118.50 senza c… | art. 413 co. 1; art. 9 co. 1-bis: il CU è dov… | corretto | decreto_ingiuntivo: labour credits pay no contributo unificato unless income exceeds three times the art. 76 threshold (art. 9 co. 1-bis DPR 115/2002… |
| `dichiarazione_553_cpc` | documento | 6 | rapporti, vincolo ex art. 546, sequestri e ce… | art. 547 co. 1: dichiarazione 'a mezzo raccom… | corretto | dichiarazione_553_cpc: the third party declaration now states, in every variant, the debts and when payment or delivery is due, seizures and assignme… |
| `esporta_atto_docx` | documento | 8 | Word mostra 1, 2, 3, 4, 5. Tutti i paragrafi … | 1, 2 / 1, 2 / 10: i numeri scritti nel testo,… | da chiarire | Il convertitore lavora riga per riga con espressioni regolari. I marcatori inline vengono interpretati solo nei paragrafi normali, non nei titoli. La… |
| `fascicolo_di_parte` | documento | 3 |  |  | coincide |  |
| `genera_dpa` | documento | 3 | Presenti il primo periodo dell'art. 28(3) e l… | Art. 28(3), secondo comma: 'informa immediata… | corretto | Il testo del DPA e' fisso: omette l'ultimo periodo dell'art. 28(3) e attenua l'art. 28(4). La checklist clausole_obbligatorie_art28 vale sempre True … |
| `genera_dpia` | documento | 5 | Punteggio 9, molto_alto; consultazione preven… | Art. 36(1) e considerando 94: la consultazion… | corretto | Il rischio residuo deriva solo dalla matrice dei rischi inerenti: misure_mitigazione non entra nel calcolo. La consultazione ex art. 36 e' imposta so… |
| `genera_informativa_cookie` | documento | 3 | Il banner dice 'accettare, rifiutare o person… | X di chiusura = impostazioni di default; 'il … | corretto | genera_informativa_cookie: the banner now warns that closing it with the X keeps the default settings (Garante cookie guidelines 10/06/2021, par. 7.1… |
| `genera_informativa_dipendenti` | documento | 3 | Sezioni opzionali presenti. Cita l'art. 111-b… | Art. 111-bis riguarda solo i 'curricula spont… | corretto | genera_informativa_dipendenti: the ITL authorisation is cited to art. 4(1) L. 300/1970 (not 4(2)), tools of work to art. 4(2)-(3); the notice rests o… |
| `genera_informativa_privacy` | documento | 3 | Presenti: titolare, finalita'/basi, destinata… | Art. 13(1)(d), 13(2)(e) e 13(2)(f); art. 12(3… | corretto | genera_informativa_privacy now carries the legitimate interests (art. 13(1)(d) / 14(2)(b) GDPR), the nature of the provision of data (13(2)(e)), auto… |
| `genera_informativa_videosorveglianza` | documento | 3 | Titolare, finalita', 72 ore e diritti present… | FAQ 4: rinvio al testo completo 'indicando co… | corretto | Fixed genera_informativa_videosorveglianza: the sign now carries the DPO contacts and the pointer to the full notice (EDPB 3/2019, Garante FAQ), the … |
| `genera_modello_atto` | documento | 19 | riferimenti_normativi = ['art. 16-bis co. 9-b… | L'art. 16-bis DL 179/2012 è stato abrogato da… | corretto | fix(genera_modello_atto): catalogue realigned to the vigente text: PCT attestations cite arts. 196-octies to 196-undecies disp. att. c.p.c. (DL 179/2… |
| `genera_notifica_data_breach` | documento | 7 | Termine '27/09/2026 ore 10:00' corretto; b_co… | Art. 33(3)(b): DPO 'o di altro punto di conta… | corretto | Il calcolo del termine e' corretto. Il modello pero' lega la lett. b) al solo DPO, etichetta male la sezione dei contatti, omette le registrazioni, n… |
| `genera_procura_liti_docx` | documento | 9 | 'Regolamento UE n. 679/2016' | 'Regolamento (UE) 2016/679': numerazione UE '… | convenzione | La clausola privacy è rimasta al lessico e alle citazioni anteriori al GDPR. Cita 'Regolamento UE n. 679/2016' invece di 'Regolamento (UE) 2016/679' … |
| `genera_quotazione_docx` | documento | 10 | fase unica 284,00; aumento 85,20; totale 369,… | Tabella 8, scaglione 5.200,01-26.000: medio 5… | corretto | fix(genera_quotazione_docx): minimum fees are exactly half of the medio (art. 4 co. 1 D.M. 55/2014, no euro rounding), execution defaults come from T… |
| `genera_registro_trattamenti` | documento | 3 | Voci a)-g) etichettate. La lett. a) contiene … | Art. 30(1)(a): nome e dati di contatto del ti… | corretto | Fixed genera_registro_trattamenti: entry 1 now carries contacts of controller, joint controller, representative and DPO (art. 30(1)(a) GDPR), the leg… |
| `genera_report_fornitori` | documento | 10 | Eccezione non gestita di openpyxl: IllegalCha… | Contratto del tool: un errore di validazione … | corretto | genera_report_fornitori: control characters forbidden by XML 1.0 s.2.2 (U+0000-0008, 000B-000C, 000E-001F) are stripped from every received text and … |
| `indice_documenti` | documento | 4 | ValueError non gestito | errore restituito nella chiave 'errore' | da chiarire | Il campo 'pagine' non è validato: un valore non numerico solleva un'eccezione. Il riferimento al DM 44/2011 non riguarda l'indice dei documenti. |
| `istanza_visibilita_fascicolo` | documento | 4 | riferimento_normativo 'Art. 16-bis DL 179/201… | art. 76 co. 2 disp. att.; art. 16-bis DL 179/… | corretto | istanza_visibilita_fascicolo: cites art. 76 co. 2 and art. 196-quater disp. att. c.p.c. instead of the repealed art. 16-bis DL 179/2012, rejects unkn… |
| `nota_precisazione_credito` | documento | 2 | 'Artt. 510, 543 e 596 c.p.c.' | art. 543 = forma del pignoramento; art. 553 =… | corretto | nota_precisazione_credito: cite art. 553 c.p.c. (assegnazione di crediti) instead of art. 543 (form of the garnishment deed). |
| `note_trattazione_scritta` | documento | 3 | 'si osserva quanto segue' e 'Si producono i s… | art. 127-ter co. 1: note 'contenenti le sole … | corretto | note_trattazione_scritta: only istanze and conclusioni, no argumentative part or document production, recalls the substituting order and the perempto… |
| `procura_alle_liti` | documento | 4 | ogni stato e grado; poteri di disposizione; a… | artt. 83 co. 3 e 84 co. 2 rispettati; l'art. … | corretto | procura_alle_liti: anti-money-laundering clause now refers to arts. 17 ff. D.Lgs. 231/2007 (art. 4 repealed by D.Lgs. 90/2017), privacy clause rests … |
| `relata_notifica_pec` | documento | 4 | manca il CF del notificante; manca la parte c… | art. 3-bis co. 5 lett. a, c, f, g e co. 6 | corretto | relata_notifica_pec: relata now carries the content of art. 3-bis co. 5-6 L. 53/1994 (lawyer and party tax codes, source list, conformity attestation… |
| `sfratto_morosita` | documento | 5 | assente | art. 660 co. 3: avvertimento sulla possibilit… | corretto | sfratto_morosita: adds the art. 660 co. 3 c.p.c. legal-aid warning, asks for an injunction to pay (arts. 658, 664) instead of a condemnation, validat… |
| `testimonianza_scritta` | documento | 7 | 'importanza morale del giuramento' | Corte cost. 149/1995: 'avverte il testimone d… | corretto | testimonianza_scritta: form rebuilt on art. 103-bis disp. att. c.p.c. and art. 257-bis (truth warning per Corte cost. 149/1995, direct/indirect knowl… |
| `backlog_riconciliazione` | n.a. | 0 |  |  | non applicabile |  |
| `lista_categorie_atti` | n.a. | 0 |  |  | non applicabile |  |
| `stato_server` | n.a. | 0 |  |  | non applicabile | diagnostica interna del server (2.14.1), nessun riferimento esterno |
| `verbale_mensile` | n.a. | 0 |  |  | non applicabile |  |

## 7. Voci aperte dopo il benchmark

### 7.1 Voci del paragrafo 7 precedente chiuse dal benchmark

Corretti o riscontrati sulla fonte primaria: `spese_mediazione` e `tariffe_mediazione` (DM 150/2023), `compenso_curatore_fallimentare` e `compenso_delegati_vendite` (decreti citati), `compenso_ctu`, `fattura_enasarco` (massimali 2026 riletti), `diritti_copia` e `copie_processo_tributario`, `indennita_licenziamento`, `costo_lavoro`, `quorum_assembleari`, `test_crisi_impresa`, `compenso_occ`, `ravvedimento_operoso`, `pignoramento_stipendio`, `contributo_unificato` (coincide con il sito su 47 casi), `calcolo_irpef` e le detrazioni, `cedolare_secca`, `imposta_registro_locazioni`, `assegno_unico`, `pensione_reversibilita`, `interessi_mora`, `rivalutazione_tfr`, `attestazione_conformita`. `compenso_mediatore_familiare` risulta un errore del test e `danno_parentale` una differenza di convenzione.

### 7.2 Voci ancora aperte

| Tool | Che cosa manca per chiuderla |
|---|---|
| `danno_biologico_macro` | trascrivere dalla Gazzetta Ufficiale la tabella unica nazionale (DPR 13 gennaio 2025 n. 12): valore punto per grado 10-100 e coefficienti d'età; il tool resta STIMATO |
| `risarcimento_inail` | riscrivere sulle tabelle INAIL: capitale per il grado 6-15% (DM 23/04/2019) e rendita per il grado dal 16%; la quota biologica è semplificata |
| `calcolo_maggior_danno` | decidere fra indice FOI, criterio annuale e rendimento dei titoli di Stato (Cass. SS.UU. 19499/2008) |
| `termini_esecuzioni`, `termini_separazione_divorzio` | una fonte giurisprudenziale per la doppia proroga festivo e sabato e per la natura sostanziale o processuale del termine di 6 e 12 mesi |
| `competenza_giudice` | corretto con riserva: servitù e condominio sopra 10.000 euro rispetto all'art. 7 co. 3 e 4 nel testo dal 31/10/2027; prima di quella data rendere il tool sensibile alla data e verificare le soglie di 30.000 e 50.000 euro (DL 100/2026) |
| `ricerca_codici_ateco` | rileggere l'Allegato 4 alla L. 190/2014 e riconciliare la tabella con ATECO 2025: circa 45 codici ATECO 2007 non esistono più o hanno un altro significato; quattro coefficienti sembrano errati (25.11.00, 68.20.02, 79.11.00, 88.91.00) ma la fonte non è stata riletta |
| `esporta_atto_docx` | difetti di conversione dei marcatori inline e permessi dei file temporanei: lavoro di prodotto, non un errore normativo |
| `interessi_legali`, `interessi_mora`, `interessi_corso_causa` | oltre il 31/12/2026 i tool si fermano: estendere col saggio in vigore con avviso di stima (art. 1284 co. 1 c.c.) |
| `termini_183_190_cpc`, `termini_deposito_atti_appello` | convenzione da valutare: il sito fa decorrere i termini successivi dalla scadenza precedente già prorogata, il tool conta dall'udienza (data più anticipata) |
| `fattura_avvocato` (forfettario) | 0,08 euro per fattura: CPA calcolata o no sul bollo riaddebitato (chiarimento dell'Agenzia delle Entrate) |
| `detrazione_assegno_coniuge` | se l'art. 13 co. 5-bis rinvii anche alla maggiorazione di 50 euro del co. 3-bis; il tool non la applica |
| `cedolare_secca`, `detrazione_canone_locazione` | locazioni brevi al 21% sulla prima unità (L. 213/2023); art. 16 co. 1-bis TUIR per i lavoratori trasferiti |
| Tabelle con costanti nel codice | `pignoramento_stipendio` (assegno sociale), `costi_costituzione` (importi), `assegno_unico`: portarle in `src/data` con `_vintage` |

Calcolatori del sito senza un tool corrispondente (possibili nuovi tool, non implementati): compensi 2012 e tariffe 2004 (superati dal DM 55/2014), interessi di mora negli appalti pubblici, rimborso chilometrico ACI, deposito telematico dei documenti, lettera di sollecito e tabelle di consultazione (elenco completo in `docs/benchmark/piano-benchmark-andreani.md`, sezione "Riscontro della Fase 0").

## 8. Cosa fare dopo

1. Chiudere le voci del paragrafo 7.2, in ordine di impatto: tabella unica nazionale del danno biologico, tabelle INAIL, estensione dei tassi oltre il 2026, ATECO 2025.
2. Trasformare in tabelle con `_vintage` gli importi ancora incorporati nel codice, così che la scadenza del periodo coperto degradi la risposta.
3. Lanciare periodicamente `pytest tests/comparison -m live` e i file live di norme e fonti (paragrafo 6.2): ogni scostamento nuovo va giudicato sulla fonte primaria prima di toccare un tool.
4. Valutare i calcolatori del sito senza tool corrispondente come possibili nuovi tool.
