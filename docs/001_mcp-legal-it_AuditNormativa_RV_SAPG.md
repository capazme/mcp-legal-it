# Audit normativo dei tool di mcp-legal-it

| | |
|---|---|
| Documento | 001_mcp-legal-it_AuditNormativa_RV_SAPG |
| Autore | SAPG |
| Revisione | RV (bozza di revisione, 24/09/2026) |
| Oggetto | Verifica dell'aggiornamento normativo dei 227 tool, con riguardo alla procedura civile e alla riforma Cartabia; stato del benchmark su avvocatoandreani.it; flag per i tool a normativa previgente |

## 1. Sintesi

Il server Model Context Protocol (MCP) espone 227 tool. L'audit ha verificato ogni tool di calcolo e ogni modello di atto contro il testo delle norme che dichiara di applicare, con priorità alla procedura civile riformata dal D.Lgs. 10 ottobre 2022 n. 149 (riforma Cartabia, in vigore dal 28/02/2023) e dal correttivo D.Lgs. 31 ottobre 2024 n. 164.

Esiti principali:

- **Sospensione feriale (L. 7 ottobre 1969 n. 742)**: tutti i tool di scadenze la applicavano con un'aritmetica sbagliata, che in tre situazioni ricorrenti dava date errate anche di dodici giorni. Riscritta con conteggio giorno per giorno; tre tool non la applicavano affatto (impugnazioni, appello, memorie 171-ter in versione riepilogo).
- **Riforma Cartabia**: tre tool dichiarati "post-Cartabia" applicavano in realtà termini previgenti (art. 190 c.p.c. abrogato per conclusionali e repliche; termini del rito ordinario applicati al rito semplificato; comparsa dell'appellato a 20 giorni invece di 70; costituzione dell'appellante a 30 giorni invece di 10). Tutti corretti.
- **Flag per i tool a normativa previgente**: introdotta (`Regime: PREVIGENTE`), applicata a due tool, verificata dall'audit automatico e visibile al modello, all'host e in ogni risposta. Interruttore `LEGAL_PREVIGENTE=off` per nasconderli.
- **Altri errori sostanziali corretti**: formula del danno biologico micropermanente (sottostima fino a un terzo al 9%), minimo impignorabile delle pensioni mai applicato, contributo unificato del lavoro senza la condizione di reddito, decreto ingiuntivo per crediti di lavoro assegnato al giudice di pace, regime della prescrizione penale non dipendente dalla data del fatto, requisiti congiunti dell'impresa minore nel Codice della crisi.
- **Benchmark su avvocatoandreani.it**: non eseguibile da questo ambiente, la rete blocca il dominio (e anche Normattiva, Brocardi, Italgiure). La suite esistente (31 file in `tests/comparison`) e i nuovi test live vanno lanciati in locale; il comando è al paragrafo 6.
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

## 6. Benchmark su avvocatoandreani.it

La suite `tests/comparison` (31 file, marcati `live`) guida con Playwright i calcolatori del sito e confronta i risultati con i tool: contributo unificato, interessi legali e di mora, rivalutazione, IRPEF, danno biologico, codice fiscale, quote ereditarie, usufrutto, ammortamento, giorni tra date, parcelle. Da questo ambiente non è eseguibile per il blocco di rete. In locale, con Chromium installato per Playwright:

```bash
python -m playwright install chromium
pytest tests/comparison -m live -q
pytest tests/unit/test_cartabia_live.py -m live -q   # riscontro dei numeri dei tool sul testo vigente (Normattiva)
```

Due avvertenze sui test esistenti: `test_danno_biologico.py` confronta il danno permanente con il sito e con la formula precedente non poteva passare per 5 e 9 punti (sarebbe stato il segnale dell'errore corretto al paragrafo 5); `test_parcelle_prof.py` attendeva la ritenuta sulla rivalsa per un ingegnere, ora distingue il caso della gestione separata (208) da quello della cassa (200).

## 7. Voci non verificate offline (aperte)

Segnalazioni emerse dalla revisione che non è stato possibile riscontrare su una fonte primaria in questa sessione. I tool coinvolti sono stati declassati a INDICATIVO con la ragione nel docstring, salvo dove indicato. Confidenza: alta (regola nota e stabile), media (regola nota, dettagli da riscontrare), bassa (da verificare del tutto).

| Tool | Segnalazione | Confidenza | Stato |
|---|---|---|---|
| `spese_mediazione`, `tariffe_mediazione` | scaglioni e riduzione di un terzo ricalcano il DM 180/2010; il DM 150/2023 (artt. 28 e 30) ha spese di avvio 40/75/110 euro, spese del primo incontro fisse, Tabella A e aumenti per l'accordo | media | declassati; da riscrivere sul DM 150/2023 |
| `compenso_mediatore_familiare` | esiste il DM 27 ottobre 2023 n. 151 sui parametri del compenso (art. 473-bis.10 c.p.c.) | alta sull'esistenza, media sugli importi | declassato; da trascrivere |
| `compenso_curatore_fallimentare` | il DM 30/2012 fissa forbici di percentuali per scaglione (attivo e passivo), non percentuali singole; il passivo calcolato a metà dell'attivo non è del decreto | alta sulla struttura | declassato; da riscrivere sul decreto |
| `compenso_delegati_vendite` | DM 227/2015 come modificato dal DM 104/2021: compensi fissi per fase e scaglione, non percentuali | media | declassato |
| `compenso_ctu` | le tabelle del DM 30 maggio 2002 non sono riprodotte; il TAR Lazio avrebbe imposto l'aggiornamento (2026) | media | già INDICATIVO, docstring esplicito |
| `fattura_enasarco` | massimale e minimale non applicati e non 2026 | media | declassato per quei valori |
| `diritti_copia`, `copie_processo_tributario` | importi degli allegati 6-8 DPR 115/2002 adeguati periodicamente (art. 274); urgenza ex art. 270 non "+50%" | alta sulla struttura, bassa sugli importi | declassati |
| `danno_parentale` | Milano liquida a punti dal 2022 (Cass. 10579/2021); Roma è una stima | alta | declassato |
| `indennita_licenziamento` | dopo Corte cost. 194/2018 nessun automatismo di due mensilità per anno | alta | declassato con spiegazione |
| `costo_lavoro` | IRAP deducibile sul personale a tempo indeterminato dal 2015; INPDAI soppresso | alta | declassato |
| `quorum_assembleari` | s.p.a. non quotate: art. 2368 co. 2; s.r.l.: art. 2479-bis co. 3 | alta | nota nel docstring; valori da riscrivere |
| `test_crisi_impresa`, `compenso_occ` | DSCR a 12 mesi (art. 3 co. 3 CCII); scaglioni OCC non del DM 202/2014 | media | declassati |
| `calcolo_maggior_danno` | Cass. SS.UU. 19499/2008 usa il rendimento dei titoli di Stato, non l'indice FOI | alta | declassato |
| `ravvedimento_operoso` | violazioni anteriori al 01/09/2024 (base 30%) non gestite; riduzione 1/6 | media | declassato |
| `competenza_giudice` | rinvio delle soglie del D.Lgs. 116/2017 al 31/10/2027 (DL 100/2026) | bassa (fonte secondaria) | nota; verificare prima del 31/10/2026 |
| `pignoramento_stipendio` | assegno sociale 2026 di 546,24 euro (circolare INPS) | bassa | parametro passabile; valore 2024 incluso e dichiarato |
| `contributo_unificato` | tributario in Cassazione: scala civile raddoppiata | media | applicato con nota "verificare" in risposta |
| `calcolo_irpef` e detrazioni | maggiorazioni e minimi delle detrazioni (L. 207/2024), figli oltre 30 anni, familiari a carico dal 2025 | media | non modificati; da riscontrare sul TUIR vigente |
| `cedolare_secca`, `imposta_registro_locazioni`, `detrazione_canone_locazione` | 21% per una unità nelle locazioni brevi; canone concordato 2% sul 70%; under 31 al 20% del canone | media | non modificati; da riscontrare |
| `assegno_unico`, `pensione_reversibilita` | importi annuali incorporati senza `_vintage`; ISEE nullo trattato come massimo | media | non modificati; candidati a tabella con vintage |
| `tassi_mora` (2002-2012) | maggiorazione di 7 punti prima del D.Lgs. 192/2012 | alta | non modificato; il tool andrebbe reso dipendente dalla data del contratto |
| `rivalutazione_tfr` | imposta sostitutiva 11% prima del 2015 | alta | non modificato |
| `ricerca_codici_ateco` | classificazione ATECO 2025 | alta | tabella già `da_verificare` |
| `attestazione_conformita` e simili | DM 44/2011 modificato dal DM 217/2023 | media | citazioni PCT aggiornate; DM non riscontrato |

Non ricadono nella flag PREVIGENTE: sono tool vigenti con dati o dettagli da riscontrare, per i quali lo strumento corretto è il grado di precisione e, dove serve, una tabella con `_vintage`.

## 8. Cosa fare dopo

1. Sbloccare la rete e lanciare i due comandi del paragrafo 6; aprire una segnalazione per ogni scostamento residuo.
2. Trascrivere dalla Gazzetta Ufficiale la tabella unica nazionale (DPR 12/2025) per `danno_biologico_macro` e riportarlo a INDICATIVO.
3. Riscrivere i quattro tool di parcelle non riconducibili ai decreti (mediazione, mediatore familiare, curatore, delegati) sui testi dei decreti.
4. Valutare tabelle con `_vintage` per gli importi annuali oggi incorporati nel codice (assegno sociale, assegno unico, trattamento minimo, minimali Enasarco), così che la scadenza del periodo coperto degradi la risposta invece di lasciarla invariata.
