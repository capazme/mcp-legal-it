# Piano di benchmark dei tool su avvocatoandreani.it e fonti ufficiali

| | |
|---|---|
| Documento | piano-benchmark-andreani |
| Autore | SAPG |
| Revisione | RV (24/09/2026), generata dal workflow di inventario; RV2 (25/09/2026, SAPG): pagine del sito riscontrate con il browser nella Fase 0 del benchmark (catalogo in `catalogo-andreani.json`) |
| Copertura | 227 tool su 227; strategie: andreani 119, fonte_ufficiale 10, non_applicabile 3, smoke_live 54, solo_norma 15, strutturale 26 (dopo il riscontro della Fase 0 del 25/09/2026) |

Strategie: `andreani` (calcolatore sul sito), `fonte_ufficiale` (tabella o calcolatore di un ente), `solo_norma` (riscontro del testo vigente con `cite_law`), `smoke_live` (chiamata reale su un documento noto), `strutturale` (generatori di documenti: riferimenti normativi del testo), `non_applicabile` (utilità interne). Confidenza: quanto è affidabile la pagina indicata, che nessun agente ha potuto aprire.

## Indice

- [analisi_fornitori.py](#analisi-fornitoripy) (3 tool)
- [atti_giudiziari.py](#atti-giudiziaripy) (23 tool)
- [cerdef.py](#cerdefpy) (3 tool)
- [cgue.py](#cguepy) (4 tool)
- [consob.py](#consobpy) (3 tool)
- [corte_cost.py](#corte-costpy) (4 tool)
- [crisi_impresa.py](#crisi-impresapy) (4 tool)
- [dichiarazione_redditi.py](#dichiarazione-redditipy) (16 tool)
- [diritto_lavoro.py](#diritto-lavoropy) (6 tool)
- [diritto_penale.py](#diritto-penalepy) (5 tool)
- [diritto_societario.py](#diritto-societariopy) (4 tool)
- [eu_implementation.py](#eu-implementationpy) (3 tool)
- [fatturazione_avvocati.py](#fatturazione-avvocatipy) (12 tool)
- [gazzetta.py](#gazzettapy) (5 tool)
- [giurisprudenza_unificata.py](#giurisprudenza-unificatapy) (1 tool)
- [giustizia_amm.py](#giustizia-ammpy) (4 tool)
- [gpdp.py](#gpdppy) (3 tool)
- [investimenti.py](#investimentipy) (5 tool)
- [italgiure.py](#italgiurepy) (5 tool)
- [legal_citations.py](#legal-citationspy) (8 tool)
- [modelli_atti.py](#modelli-attipy) (3 tool)
- [orientamento.py](#orientamentopy) (3 tool)
- [parcelle_professionisti.py](#parcelle-professionistipy) (11 tool)
- [parlamento.py](#parlamentopy) (3 tool)
- [privacy_gdpr.py](#privacy-gdprpy) (12 tool)
- [procedura_civile.py](#procedura-civilepy) (3 tool)
- [procure_quotazioni.py](#procure-quotazionipy) (2 tool)
- [proprieta_successioni.py](#proprieta-successionipy) (12 tool)
- [risarcimento_danni.py](#risarcimento-dannipy) (7 tool)
- [rivalutazioni_istat.py](#rivalutazioni-istatpy) (12 tool)
- [scadenze_termini.py](#scadenze-terminipy) (11 tool)
- [tassi_interessi.py](#tassi-interessipy) (10 tool)
- [tmview.py](#tmviewpy) (3 tool)
- [varie.py](#variepy) (14 tool)

## analisi_fornitori.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `genera_report_fornitori` | documento | strutturale | nessuna pagina del sito | artt. 4 n. 7 e n. 8 e 28 GDPR via cite_law (qualificazioni titolare e responsabile) | Introdotto nella 2.14, non toccato dall'audit di settembre 2026. Il benchmark verifica layout, ordinamento, validazione e la neutralizzazione delle formule nelle celle (dati del mastrino di terzi). |
| `verifica_dpa_fornitore` | ricerca_online | smoke_live | nessuna (media) | sito ufficiale del fornitore (pagina del DPA) | Introdotto nella 2.14, non toccato dall'audit di settembre 2026; grado INDICATIVO: accerta che il fornitore pubblichi un DPA, non che sia richiamato nel contratto del cliente. 'non_trovato', 'bloccato' e 'dominio_irraggiungibile' non valgono come 'no'. Da verificare anche il rifiuto delle destinazioni non pubbliche (IP, nomi riservati), che avviene senza chiamate di rete. |
| `verifica_partita_iva_vies` | ricerca_online | smoke_live | nessuna (alta) | servizio VIES della Commissione europea (API REST check-vat-number) | Introdotto nella 2.14, non toccato dall'audit di settembre 2026. Il benchmark deve documentare che 'valido' in VIES significa iscrizione all'archivio VIES per le operazioni intracomunitarie, non la sola esistenza della P.IVA: una P.IVA italiana attiva ma non iscritta risulta non valida. Il test live va marcato 'live'. |

### `genera_report_fornitori`

Genera l'Excel standard dell'analisi privacy del mastrino fornitori (foglio Avvertenze e 11 colonne), validando i record e la coerenza delle classi.

- Parametri: `fornitori: list[dict] (obbligatori denominazione_mastrino, qualificazione 'responsabile'\|'titolare_autonomo'\|'fuori_perimetro', motivazione, confidenza 'alto'\|'medio'\|'basso', classe_attivita; solo per i responsabili probabilita_responsabile 'alta'\|'media'\|'bassa' e dpa_proprio 'si'\|'no'\|'da_verificare'; opzionali piva_cf, attivita, categorie_dati, fonti, note), cliente: str, data_analisi: str = '' (gg/mm/aaaa, default oggi), file_sorgente: str = '', nome_file: str = ''`
- Fonte normativa dichiarata: artt. 28 e 4 GDPR
- Casi di prova:
  - Lotto valido: `{"fornitori": [{"denominazione_mastrino": "Paghe Srl", "qualificazione": "responsabile", "motivazione": "elaborazione cedolini", "confidenza": "alto", "classe_attivita": "paghe", "probabilita_responsabile": "alta", "dpa_proprio": "no"}, {"denominazione_mastrino": "Cloud Srl", "qualificazione": "responsabile", "motivazione": "hosting", "confidenza": "alto", "classe_attivita": "hosting", "probabilita_responsabile": "alta", "dpa_proprio": "si"}, {"denominazione_mastrino": "Studio Rossi", "qualificazione": "titolare_autonomo", "motivazione": "difesa legale", "confidenza": "alto", "classe_attivita": "legale"}, {"denominazione_mastrino": "=HYPERLINK(\"http://x\")", "qualificazione": "fuori_perimetro", "motivazione": "fornitura carta", "confidenza": "medio", "classe_attivita": "cancelleria"}], "cliente": "Alfa S.r.l.", "nome_file": "bench_report"}` → atteso: fogli 'Avvertenze' e 'Analisi fornitori'; 11 intestazioni nell'ordine fisso; ordine Paghe Srl (responsabile senza DPA), Cloud Srl, Studio Rossi, riga fuori perimetro; la cella '=HYPERLINK(...)' salvata come testo; Avvertenze con 1 nomina da predisporre
  - Classe con qualificazioni incoerenti: `{"fornitori": [{"denominazione_mastrino": "Paghe Srl", "qualificazione": "responsabile", "motivazione": "elaborazione cedolini", "confidenza": "alto", "classe_attivita": "paghe", "probabilita_responsabile": "alta", "dpa_proprio": "no"}, {"denominazione_mastrino": "Cloud Srl", "qualificazione": "responsabile", "motivazione": "hosting", "confidenza": "alto", "classe_attivita": "hosting", "probabilita_responsabile": "alta", "dpa_proprio": "si"}, {"denominazione_mastrino": "Paghe2", "qualificazione": "titolare_autonomo", "motivazione": "x", "confidenza": "alto", "classe_attivita": "paghe"}], "cliente": "Alfa S.r.l."}` → atteso: 'Errore di validazione' sulla classe 'paghe' (responsabile e titolare_autonomo) e nessun file

### `verifica_dpa_fornitore`

Sonda i percorsi convenzionali del dominio di un fornitore per trovare un DPA ex art. 28 GDPR pubblicato; esito in cache per 90 giorni.

- Parametri: `dominio: str (dominio o URL del sito ufficiale), nome_fornitore: str = ''`
- Fonte normativa dichiarata: art. 28 GDPR
- Casi di prova:
  - Documento noto: `{"dominio": "stripe.com", "nome_fornitore": "Stripe"}` → atteso: verdetto dpa_dedicato con url_evidenza https://stripe.com/legal/dpa (da confermare in live; un blocco anti-bot dà 'bloccato', che non è un 'no'); da_cache false alla prima chiamata e true alla seconda entro 90 giorni
  - Indirizzo IP rifiutato: `{"dominio": "127.0.0.1"}` → atteso: verdetto dominio_irraggiungibile, errore 'indirizzo IP invece di un dominio', nessuna richiesta di rete, nulla in cache
  - Nome riservato: `{"dominio": "example.invalid"}` → atteso: verdetto dominio_irraggiungibile, errore 'nome locale o riservato'

### `verifica_partita_iva_vies`

Verifica una partita IVA sul servizio VIES della Commissione europea (validità, denominazione e indirizzo se forniti dallo Stato membro), con checksum locale per le P.IVA italiane.

- Parametri: `partita_iva: str (senza prefisso paese), codice_paese: str = 'IT' (codice dello Stato membro)`
- Fonte normativa dichiarata: Reg. (UE) 904/2010; art. 35 DPR 633/1972 per il checksum
- Casi di prova:
  - Documento noto (Irlanda): `{"partita_iva": "6388047V", "codice_paese": "IE"}` → atteso: disponibile true, valido true, denominazione 'GOOGLE IRELAND LIMITED', indirizzo con 'GORDON HOUSE, BARROW STREET, DUBLIN 4'
  - Checksum italiano errato, nessuna chiamata di rete: `{"partita_iva": "00743110158"}` → atteso: checksum_valido false, valido false, disponibile null, errore 'checksum non valido', VIES non interrogato

## atti_giudiziari.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `attestazione_conformita` | documento | strutturale | https://www.avvocatoandreani.it/servizi/attestazione-conformita.php (media) | Normattiva via cite_law: artt. 196-octies, 196-novies, 196-decies e 196-undecies disp. att. c.p.c. nel testo del correttivo D.Lgs. 164/2024 | Corretto dall'audit (par. 4.6): il testo cita le disposizioni di attuazione in luogo del DL 179/2012; voce aperta al par. 7 (DM 44/2011 modificato dal DM 217/2023, confidenza media). Residui da confermare: il campo riferimento_normativo della risposta cita ancora gli artt. 16-bis co. 9-bis e 16-undecies DL 179/2012; per la modalità 'copia_informatica' il tool cita l'art. 196-decies, che secondo la rubrica riguarda le copie trasmesse con modalità telematiche all'ufficiale giudiziario, mentre la copia informatica di un atto analogico depositata dal difensore dovrebbe rientrare nell'art. 196-novies (potere di certificazione di conformità di copie di atti e di provvedimenti); verificare anche le modifiche del correttivo D.Lgs. 164/2024. Il redattore del sito è aggiornato alla riforma e acquisisce il nome del file: confronto di struttura. |
| `atto_di_precetto` | documento | strutturale | https://www.avvocatoandreani.it/servizi/atto-di-precetto.php (alta) | Normattiva via cite_law: artt. 475, 479, 480, 481, 615 e 617 c.p.c. nel testo del D.Lgs. 164/2024 | Corretto dall'audit (par. 4.6): tolta la formula esecutiva (art. 475 riformato), distinte l'opposizione ex art. 615 (senza termine) e quella ex art. 617 (venti giorni), aggiunto l'avvertimento sul sovraindebitamento (art. 480 co. 2). Da verificare con cite_law sull'art. 480 nel testo del correttivo D.Lgs. 164/2024 (in vigore dal 26/11/2024): il co. 3 richiede l'indicazione del giudice competente per l'esecuzione e la dichiarazione di residenza o l'elezione di domicilio nel comune in cui ha sede (se il precetto è sottoscritto dalla parte, in alternativa l'indirizzo PEC da pubblici elenchi o un domicilio digitale speciale); in mancanza le opposizioni si propongono davanti al giudice del luogo di notifica. Il modello non contiene nessuna di queste indicazioni. Mancano anche il termine di efficacia di novanta giorni (art. 481); la formula sul sovraindebitamento va confrontata con il testo vigente. Il tool non valida importi negativi. Il redattore del sito calcola interessi e compensi e prepara la relata: confronto di struttura. |
| `calcolo_hash` | utilita | andreani | https://www.avvocatoandreani.it/servizi/calcolo-verifica-impronta-hash.php (alta) | NIST, vettori di prova di SHA-256 (FIPS 180-4) | Non toccato dall'audit. Il calcolatore del sito lavora su file, nel browser: per il confronto va caricato un file con gli stessi byte UTF-8 del testo, senza BOM e senza a capo finale. Il tool calcola l'hash di una stringa e non dei byte del PDF da depositare, e 'lunghezza_input' conta i caratteri, non i byte. La riga Vigenza attribuisce al DM 44/2011 l'obbligo di SHA-256: il decreto rinvia alle specifiche tecniche DGSIA, e l'impronta nelle attestazioni di conformità riguarda, secondo la pagina del sito, i casi residui del provvedimento del 28/12/2015 in relazione agli artt. 4 co. 3 e 6 co. 3 del DPCM 13/11/2014 (oggi sostituito dalle Linee guida AgID sul documento informatico): riferimento da riallineare dopo la verifica. Fase 0: pagina confermata. |
| `cerca_ufficio_giudiziario` | utilita | andreani | https://www.avvocatoandreani.it/servizi/ricerca-uffici-giudiziari-per-comune.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/ricerca-uffici-unep.php | Ministero della Giustizia, ricerca degli uffici giudiziari competenti per comune (banca dati degli uffici giudiziari su giustizia.it) | Non citato dall'audit; tabella tribunali_competenti.json con 102 capoluoghi e _vintage 'da_verificare'; grado INDICATIVO. Il sito, con dati ministeriali, restituisce per ogni comune tutti gli uffici competenti. Il benchmark deve confermare i capoluoghi e misurare la copertura: i comuni non capoluogo non sono trovati e la ricerca parziale suggerisce uffici sbagliati quando il nome contiene quello di un capoluogo (Torino di Sangro, Bari Sardo, Lucca Sicula, Romano di Lombardia e Pisano restituiscono i tribunali di Torino, Bari, Lucca, Roma e Pisa); un tipo non valido (per esempio 'corte_appello') restituisce il tribunale senza errore. La riga Vigenza cita il R.D. 12/1941, ma i circondari vigenti derivano dalla revisione della geografia giudiziaria (D.Lgs. 155/2012 e 156/2012 e successive modifiche). Fase 0: pagina confermata. |
| `codici_iscrizione_ruolo` | utilita | andreani | https://www.avvocatoandreani.it/servizi/ricerca-codici-iscrizione-ruolo-cause.php (alta) | Ministero della Giustizia, elenco degli oggetti dei giudizi per materia (copia sul sito: https://www.avvocatoandreani.it/documenti/iscrizione-ruolo/elenco-oggetti-giudizi-per-materia.pdf) | Non citato dall'audit; tabella codici_ruolo.json con _vintage manuale al 19/09/2026 (sottoinsieme delle materie più ricorrenti). Il benchmark deve confermare che ogni codice restituito esista sul sito e nell'elenco ministeriale con la stessa descrizione, e misurare le perdite di risultati: la ricerca è sensibile agli accenti, per cui le parole chiave suggerite dal docstring ('responsabilita', 'proprieta') non trovano i codici delle materie scritte con l'accento. Il sito cerca anche parti di parola, con le opzioni tutte le parole, una qualsiasi e frase esatta. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `contributo_unificato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_contributo_unificato.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabella-contributo-unificato.php | Ministero della Giustizia, prospetto degli importi del contributo unificato (art. 13 DPR 115/2002); per lavoro e tributario in Cassazione anche la tabella del sito https://www.avvocatoandreani.it/servizi/tabella-contributo-unificato.php | Corretto dall'audit (par. 5): esenzione del lavoro subordinata al reddito (art. 9 co. 1-bis), tributario con gli stessi importi in appello (co. 6-quater), nuovi tipi per valore indeterminabile, opposizione a decreto ingiuntivo e agli atti esecutivi, tipo ignoto rifiutato. Voce aperta al par. 7 (confidenza media): tributario in Cassazione sulla scala civile raddoppiata, applicato con nota 'verificare'. Esiste già tests/comparison/test_contributo_unificato.py (solo cognizione di primo grado, quattro valori interni agli scaglioni). Il benchmark deve confermare sul calcolatore: i confini degli scaglioni (1.100, 5.200, 26.000, 52.000, 260.000, 520.000 euro; se il campo del sito accetta solo interi, usare 1.101 per il lato superiore), i moltiplicatori 1,5 e 2, le voci fisse (278, 168, 43 e 139 con soglia 2.500), il lavoro oltre soglia (nei risultati di ricerca la tabella del sito indica la soglia, tre volte l'art. 76, in 40.978,92 euro) e il tributario in Cassazione (la stessa tabella indica la misura dei processi civili). Da segnalare: la nota _vintage di contributo_unificato.json parla di 'due volte' la soglia dell'art. 76, mentre il codice e l'art. 9 co. 1-bis dicono 'tre volte'; il tool accetta combinazioni senza base normativa (tar in Cassazione 1.300 euro; opposizione agli atti esecutivi in appello 252 euro, benché la sentenza ex art. 618 c.p.c. non sia appellabile; esecuzioni in appello); non gestisce il valore non dichiarato (art. 13 co. 6: si presume lo scaglione massimo), l'aumento del co. 3-bis, il raddoppio per le sezioni specializzate (co. 1-ter) né la convalida di sfratto (co. 3: metà, valore pari ai canoni scaduti), opzioni che il calcolatore del sito potrebbe offrire. La L. 207/2024 ha introdotto l'art. 14 co. 3.1 (iscrizione a ruolo solo con almeno 43 euro versati) senza toccare gli importi. Fase 0: pagina confermata; tabella 2026 pubblicata dal sito. |
| `copie_processo_tributario` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_diritti_copia_processo_tributario.php (alta) | Ministero dell'Economia e delle Finanze, Dipartimento della giustizia tributaria: diritti di copia presso le Corti di giustizia tributaria; allegati 6, 7 e 8 DPR 115/2002 nel testo della L. 207/2024 | Declassato a INDICATIVO dall'audit (par. 7, insieme a diritti_copia: tariffe per pagina non riscontrate, urgenza diversa da +50%). Il calcolatore del sito lavora per formato (cartaceo o elettronico), tipo (con o senza certificazione di conformità) e per numero di pagine o dimensione in KB: struttura diversa dal tool, che applica una tariffa fissa per pagina e il +50% per urgenza. Il benchmark deve individuare la fonte degli importi nel processo tributario, verificare se valgono gli allegati 6-8 DPR 115/2002 nel testo in vigore dal 01/01/2025 (fasce di pagine per il cartaceo; per le copie non cartacee forfait di 8 euro per trasmissione telematica e 25 euro per supporto fisico introdotto dalla L. 207/2024) e l'art. 270 (triplo per la copia cartacea urgente). Il tool non valida il tipo: un valore sconosciuto è calcolato come copia semplice. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `decreto_ingiuntivo` | documento | strutturale | https://www.avvocatoandreani.it/servizi/decreto-ingiuntivo.php (media) | Normattiva via cite_law: artt. 7, 409, 413, 633, 636, 637, 641, 642 e 644 c.p.c., art. 63 disp. att. c.c., art. 14 DPR 115/2002; per il CU il calcolatore del contributo unificato | Corretto dall'audit (par. 5): crediti di lavoro sempre al tribunale in funzione di giudice del lavoro (art. 413) e termini degli artt. 641 e 644 nella risposta. Da confermare: (1) soglia del giudice di pace di 10.000 euro (art. 7 co. 1): il modulo procedura_civile indica la decorrenza dell'innalzamento a 30.000 euro del D.Lgs. 116/2017 al 31/10/2026 e una fonte secondaria parla di rinvio al 31/10/2027 (DL 100/2026; par. 4.7 e 7, confidenza bassa): va riscontrata con cite_law prima del 31/10/2026, perché da quella data il tool potrebbe indicare il giudice sbagliato tra 10.000 e 30.000 euro; (2) per il credito 'professionale' la provvisoria esecuzione è motivata con l'art. 642 co. 1, che riguarda solo cambiale, assegni, certificato di liquidazione di borsa e atti ricevuti da notaio o altro pubblico ufficiale: la parcella con il parere del Consiglio dell'Ordine è la prova scritta dell'art. 636 e la provvisoria esecuzione può fondarsi solo sul co. 2 (pericolo di grave pregiudizio o documentazione sottoscritta dal debitore); (3) per 'retribuzioni' il CU indicato (metà scaglione) ignora l'esenzione dell'art. 9 co. 1-bis DPR 115/2002; (4) un tipo_credito sconosciuto è accettato senza errore; (5) il ricorso non contiene la dichiarazione di valore ai fini del CU (art. 14 co. 2 DPR 115/2002) e non ricorda il foro del Consiglio dell'Ordine per i crediti dell'avvocato (art. 637 co. 3). Il redattore del sito lavora su fatture e genera anche decreto e procura: confronto di struttura. |
| `dichiarazione_553_cpc` | documento | strutturale | https://www.avvocatoandreani.it/servizi/modello-dichiarazione-553.php (media) | Normattiva via cite_law: artt. 543, 545, 546, 547, 548 e 553 c.p.c. | Corretto dall'audit (par. 4.6): la mancata dichiarazione è disciplinata dall'art. 548. Mappatura da riscontrare: dai risultati di ricerca la pagina del sito crea una dichiarazione ex art. 553 da notificare al terzo pignorato, cioè un atto diverso dalla dichiarazione del terzo ex art. 547 prodotta dal tool; il confronto con il sito è solo parziale. Da verificare con cite_law: il docstring colloca l'invito a rendere la dichiarazione entro dieci giorni nell'art. 543 co. 2 n. 3, ma il testo vigente lo pone al n. 4; l'art. 547 richiede di specificare i sequestri precedenti e le cessioni notificate o accettate (assenti nella variante 'altro', parziali in 'stipendio'); il modello non indica le modalità di invio al creditore procedente (raccomandata o PEC). |
| `diritti_copia` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_diritti_copia_cancelleria.php (alta) | Ministero della Giustizia, pagina 'Diritto di copia forfettizzato: modifiche apportate dalla Legge di Bilancio 2025 al Testo unico delle spese di giustizia' e tabelle degli allegati 6, 7 e 8 DPR 115/2002 in vigore dal 01/01/2025 pubblicate dagli uffici giudiziari (per esempio Tribunale di Milano, 'Diritti di copia e di certificato') | Declassato a INDICATIVO dall'audit (par. 7: importi degli allegati 6-8 adeguati ex art. 274 e urgenza ex art. 270 diversa da +50%; confidenza alta sulla struttura, bassa sugli importi). Dalla ricerca emergono due elementi che il benchmark deve confermare sul sito e sulla fonte ministeriale: la L. 30 dicembre 2024 n. 207, dal 01/01/2025, ha sostituito l'allegato 8 con un forfait per le copie su supporto non cartaceo (25 euro per supporto fisico, 8 euro per trasmissione telematica) e ha riscritto l'art. 269 (nessun diritto per la copia senza certificazione estratta dal fascicolo informatico dai soggetti abilitati), mentre gli allegati 6 e 7 restano a fasce di pagine (le tabelle degli uffici giudiziari aggiornate al 01/01/2025 li indicano maggiorati del 50% per il cartaceo, in base all'art. 40 co. 1-bis introdotto dal DL 193/2009: va confermato l'ultimo adeguamento ex art. 274, perché l'ultimo decreto trovato dalla ricerca è il DM 9 luglio 2021); l'art. 270 triplica il diritto per la copia cartacea rilasciata entro due giorni e non si applica alle copie non cartacee (circolare del Ministero della Giustizia del 23/04/2014). Il tool usa tariffe per pagina (0,30 e 0,70 euro) invece delle fasce per numero di pagine, fasce digitali da 1,62 a 10,13 euro non riconducibili al nuovo allegato 8, una maggiorazione del 50% e il tipo 'esecutiva' (la formula esecutiva è stata soppressa dall'art. 475 c.p.c. riformato: la copia per l'esecuzione è una copia attestata conforme). Esito atteso: scostamento su quasi tutti i casi cartacei e digitali certificati; il tool va riscritto sul testo vigente con una tabella dotata di _vintage. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `fascicolo_di_parte` | documento | strutturale | https://www.avvocatoandreani.it/servizi/fascicolo-di-parte.php (media) | Normattiva via cite_law: artt. 165 e 166 c.p.c., artt. 74 e 196-quater disp. att. c.p.c. | Non citato dall'audit. Il testo non contiene riferimenti normativi (l'art. 165 compare solo nel campo riferimento_normativo) e presuppone sempre la parte attrice o ricorrente: manca la variante del convenuto (art. 166, costituzione almeno 70 giorni prima dell'udienza nel testo del D.Lgs. 149/2022). Il benchmark deve verificare con cite_law gli artt. 165 e 166 c.p.c. e l'art. 74 disp. att. c.p.c. (atti e documenti in sezioni separate, indice sottoscritto dal cancelliere, indicazioni di copertina) e la coerenza con il deposito telematico obbligatorio (art. 196-quater disp. att.). Il sito crea un fascicolo elettronico riutilizzabile e una copertina: confronto solo di struttura. |
| `indice_documenti` | documento | strutturale | https://www.avvocatoandreani.it/servizi/indice-documenti-allegati.php (media) | Normattiva via cite_law: artt. 74 e 87 disp. att. c.p.c. | Non citato dall'audit. Controllo aritmetico e strutturale: numerazione, totale documenti e totale pagine. Con 'pagine' non numerico il tool solleva ValueError invece di restituire un errore. Il riferimento pertinente all'indice è l'art. 74 disp. att. c.p.c. (atti e documenti in sezioni separate, indice del fascicolo; per le produzioni successive art. 87), non il DM 44/2011, che non prevede un indice. Il sito crea un indice con collegamenti ipertestuali ai file: confronto di struttura. |
| `istanza_visibilita_fascicolo` | documento | strutturale | https://www.avvocatoandreani.it/servizi/istanza-visibilita-fascicolo-telematico.php (media) | Normattiva via cite_law: artt. 76 e 196-quater disp. att. c.p.c., art. 105 c.p.c. | Corretto dall'audit (par. 4.6) solo nella riga Vigenza: il campo riferimento_normativo della risposta cita ancora l'art. 16-bis DL 179/2012 e il testo non contiene riferimenti (salvo l'art. 105 per l'intervento). La base dell'accesso è l'art. 76 disp. att. c.p.c. (parti e difensori muniti di procura possono esaminare gli atti e accedere al fascicolo informatico), da verificare con cite_law insieme all'art. 196-quater. Un motivo non previsto ricade in silenzio su 'costituzione'; l'intestazione 'Al Sig. <tribunale>' va corretta (al Giudice o al Presidente). Il sito genera un'istanza di visibilità temporanea: confronto di struttura. |
| `nota_precisazione_credito` | documento | strutturale | https://www.avvocatoandreani.it/servizi/nota-precisazione-credito.php (media) | Normattiva via cite_law: artt. 510, 553 e 596 c.p.c. e art. 1284 c.c. | Corretto dall'audit (par. 4.6): non è più attribuita all'art. 547. Da verificare: l'art. 543 disciplina la forma del pignoramento presso terzi e non la precisazione; per l'assegnazione presso terzi il riferimento pertinente è l'art. 553, per la distribuzione gli artt. 510 e 596 c.p.c. Il sito calcola in automatico interessi legali o moratori dalla data del precetto e le competenze secondo i parametri forensi; il tool somma soltanto le voci passate (controllo aritmetico) e rinvia al 'tasso legale vigente' anche per i crediti commerciali (art. 1284 co. 4 c.c. o D.Lgs. 231/2002). |
| `note_iscrizione_ruolo` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/note_iscrizione_a_ruolo.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo_contributo_unificato.php | Ministero della Giustizia, tabella dei codici oggetto per l'iscrizione a ruolo | Non citato dall'audit; usa la funzione del contributo unificato corretta al par. 5 ma non passa la condizione di reddito, per cui 'lavoro' dà sempre 0. La pagina omonima del sito (https://www.avvocatoandreani.it/servizi/note_iscrizione_a_ruolo.php) offre solo i modelli delle note in PDF e RTF: il confronto numerico si fa sul calcolatore del CU e quello dei codici su https://www.avvocatoandreani.it/servizi/ricerca-codici-iscrizione-ruolo-cause.php. Da confermare: 'locazione' è calcolato sulla scala piena, mentre la convalida di sfratto è dimezzata e ha per valore i canoni scaduti (art. 13 co. 3); 'esecuzione_mobiliare' senza valore restituisce 43 euro, ma da 2.500 euro il CU è 139 (art. 13 co. 2), quindi il valore andrebbe richiesto; un tipo sconosciuto è calcolato come cognizione senza errore; nessun codice oggetto per esecuzioni e volontaria giurisdizione. Fase 0: pagina dedicata alle note di iscrizione a ruolo presente sul sito. |
| `note_trattazione_scritta` | documento | strutturale | https://www.avvocatoandreani.it/servizi/note-trattazione-scritta.php (alta) | Normattiva via cite_law: art. 127-ter c.p.c. nel testo del D.Lgs. 164/2024 e art. 35 co. 2 D.Lgs. 149/2022 | Corretto dall'audit (par. 4.6) nella riga Vigenza (applicabilità dal 01/01/2023 anche ai pendenti, limiti del correttivo). Da verificare con cite_law sull'art. 127-ter: le note contengono 'le sole istanze e conclusioni' (co. 1), mentre il modello ha una parte argomentativa ('si osserva quanto segue') e la produzione di documenti; il giudice assegna un termine perentorio non inferiore a quindici giorni e ogni parte può opporsi entro cinque giorni (co. 2); il giorno di scadenza del termine è data di udienza a tutti gli effetti. Il testo prodotto cita solo l'art. 127-ter e non richiama il provvedimento del giudice né il termine assegnato. Il redattore del sito riusa il fascicolo di parte. |
| `pignoramento_stipendio` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-pignoramento-stipendio-pensione.php (alta) | INPS, circolare annuale di rinnovo delle pensioni con l'importo 2026 dell'assegno sociale | Corretto dall'audit (par. 5): il minimo impignorabile delle pensioni ora si applica (doppio dell'assegno sociale, minimo 1.000 euro, quota solo sull'eccedenza, art. 545 co. 7). Voce aperta al par. 7 (confidenza bassa): assegno sociale 2026 di 546,24 euro. Nei risultati di ricerca la pagina del sito indica per il 2026 proprio 546,24 euro e un impignorabile di 1.092,48 euro: il benchmark deve confermarlo e, se confermato, il default del tool (534,41 euro, anno 2024) va spostato in una tabella con _vintage, perché senza parametro la risposta sovrastima la quota pignorabile. Da verificare anche: per il credito fiscale su pensione il tool sceglie la fascia dell'art. 72-ter sull'importo lordo e la applica all'eccedenza (l'art. 72-ter parla di stipendi e salari, non di pensioni); l'1/3 per i crediti alimentari è attribuito all'art. 545 co. 3, che rimette la misura al presidente del tribunale (il limite di un terzo compare nell'art. 2 DPR 180/1950 per i dipendenti pubblici); il co. 8 (somme già accreditate su conto, pignorabili oltre il triplo dell'assegno sociale) compare solo in nota; il concorso di crediti (co. 5) è un limite complessivo, non la quota di un singolo pignoramento. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `procura_alle_liti` | documento | strutturale | https://www.avvocatoandreani.it/servizi/procura-alle-liti.php (media) | Normattiva via cite_law: artt. 83, 84 e 365 c.p.c., D.Lgs. 231/2007; Reg. UE 2016/679 artt. 6, 9 e 13 | Non citato dall'audit. Il testo non richiama l'art. 83 c.p.c. (lo fa solo il campo riferimento_normativo). Da verificare con verifica_citazioni: la citazione 'art. 4 co. 3 del D.Lgs. 231/2007' per l'adeguata verifica non sembra corrispondere al testo vigente dopo il D.Lgs. 90/2017, e l'avvocato è esonerato dall'adeguata verifica quando difende o rappresenta il cliente in un procedimento giudiziario; il 'consenso' al trattamento non è la base giuridica del mandato difensivo (art. 6 par. 1 lett. b e art. 9 par. 2 lett. f GDPR); la procura per l'appello deve indicare il provvedimento impugnato (il modello lascia gli spazi); nessun cenno alla firma digitale o alla copia informatica autenticata per il deposito telematico (art. 83 co. 3 c.p.c.). Il redattore del sito adatta genere e numero delle parti: confronto di struttura. |
| `relata_notifica_pec` | documento | strutturale | https://www.avvocatoandreani.it/servizi/relata-notifica-pec.php (alta) | Normattiva via cite_law: artt. 1, 3-bis e 3-ter L. 53/1994 e art. 147 c.p.c. nel testo del D.Lgs. 149/2022 | Corretto dall'audit (par. 4.6): autorizzazione del Consiglio dell'Ordine solo per la notifica a mezzo posta; perfezionamento secondo l'art. 147 co. 3 c.p.c. (ricevute di accettazione e di consegna, regola delle ore 21-7). Da verificare con cite_law: l'art. 3-bis co. 5 L. 53/1994 richiede nella relazione nome, cognome e codice fiscale dell'avvocato notificante, nome e codice fiscale della parte che ha conferito la procura, destinatario, indirizzo PEC, elenco da cui è estratto e, per le copie di atti analogici, l'attestazione di conformità: il modello non ha il codice fiscale del notificante né la parte assistita e indica insieme tre elenchi invece di quello usato. La riga Vigenza cita solo la L. 228/2012: va aggiunta la riforma del D.Lgs. 149/2022 (anche art. 3-ter, obbligo di notifica telematica). Una data inesistente solleva un'eccezione non gestita. Il sito rende obbligatori indirizzo PEC e provenienza. |
| `sfratto_morosita` | documento | strutturale | https://www.avvocatoandreani.it/servizi/sfratto-per-morosita.php (media) | Normattiva via cite_law: artt. 658, 660, 663, 664 e 665 c.p.c., artt. 5 e 55 L. 392/1978 | Non citato dall'audit. Il redattore del sito è aggiornato al correttivo D.Lgs. 164/2024 (in vigore dal 26/11/2024): confronto di struttura. Da verificare con cite_law: art. 658 (intimazione con richiesta di ingiunzione per i canoni scaduti, art. 664: il modello chiede invece una condanna), art. 660 (citazione con termini liberi non minori di venti giorni e avvertimento dell'art. 663: il termine non compare), art. 663 co. 3 (persistenza della morosità attestata in udienza), art. 665 (ordinanza di rilascio), art. 55 L. 392/1978 (termine di grazia non superiore a 90 giorni, applicabile alle sole locazioni abitative secondo Cass. SU 272/1999: il modello lo offre senza distinguere l'uso), art. 5 L. 392/1978 (morosità oltre venti giorni dalla scadenza per l'abitativo). Il totale non è validato (mensilità pari a 0 o canone negativo danno 0 o importi negativi) e il tool non indica il contributo unificato della convalida (metà, sul valore dei canoni scaduti, art. 13 co. 3 DPR 115/2002). |
| `sollecito_pagamento` | documento | andreani | https://www.avvocatoandreani.it/servizi/lettera-sollecito-pagamento.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/interessi_moratori.php | Ministero dell'Economia e delle Finanze, comunicato semestrale in Gazzetta Ufficiale del saggio di interesse per i ritardati pagamenti (tabella tassi_mora.json, copre_fino_a 31/12/2026) | Non citato ai par. 5 e 7, ma usa tassi_mora.json, per cui vale la voce aperta del par. 7 sui tassi 2002-2012 (confidenza alta): per le transazioni concluse prima del 01/01/2013 la maggiorazione è di 7 punti (art. 5 D.Lgs. 231/2002 nel testo anteriore al D.Lgs. 192/2012), mentre la tabella e il tool applicano sempre 8 punti e il tool non ha un parametro per la data del contratto. Il benchmark deve confermare sul calcolatore del sito, a parità di capitale e date, il conteggio per semestri, la decorrenza dal giorno successivo alla scadenza (art. 4 co. 1) e la convenzione sui giorni dell'anno; con tasso convenzionale il tool divide per i giorni dell'anno della scadenza anche quando il periodo cade in un anno bisestile. Difetto da segnalare: oltre la fine della tabella il ciclo si interrompe in silenzio, per cui con un sollecito di gennaio 2027 gli interessi coprono solo dicembre 2026 mentre la lettera dichiara tutti i giorni di ritardo. La lettera non menziona l'importo forfettario di 40 euro per i costi di recupero (art. 6 D.Lgs. 231/2002) e applica il tasso commerciale anche se il debitore è un consumatore (in tal caso art. 1284 c.c.); date non ISO sollevano un'eccezione non gestita. Pagine collegate del sito: redattore della lettera https://www.avvocatoandreani.it/servizi/lettera-sollecito-pagamento.php e tabella dei tassi https://www.avvocatoandreani.it/servizi/tab_interessi_moratori.php (il sito conferma per il secondo semestre 2026 il 2,40% più 8 punti, cioè 10,40%). Fase 0: modello di lettera di sollecito presente sul sito; gli interessi si riscontrano sulla pagina degli interessi moratori. |
| `tassazione_atti` | calcolo | solo_norma | nessuna pagina del sito ; secondarie: https://www.avvocatoandreani.it/utility/tassazione-atti-giudiziari.php | Agenzia delle Entrate: Tariffa parte I allegata al DPR 131/1986 (art. 8 e note) e circolare 30/E del 29/07/2022 sull'art. 46 L. 374/1991; il servizio AdE 'Tassazione del provvedimento' vale solo per provvedimenti reali | Nessun calcolatore sul sito: la ricerca trova solo le imposte su locazioni e compravendite. Non citato dall'audit ma dichiarato ESATTO: il benchmark deve decidere se il grado regge. Da asserire con cite_law: 3% sulle condanne (art. 8 co. 1 lett. b Tariffa parte I) con minimo pari all'imposta fissa di 200 euro (art. 41 DPR 131/1986); 2% prima casa con minimo di 1.000 euro (art. 1 Tariffa parte I). Casi imposti dalla norma e non gestiti: la Nota II all'art. 8 esclude l'imposta proporzionale per la parte di condanna relativa a corrispettivi soggetti a IVA (decreto ingiuntivo su fatture: 200 euro fissi); lett. c (1% sugli accertamenti) e trasferimenti con l'aliquota dell'atto corrispondente (9% per l'immobile non prima casa, mentre il verbale di conciliazione non prima casa è sempre al 3%); art. 46 L. 374/1991 (cause fino a 1.033 euro esenti in ogni grado, circolare 30/E/2022); ordinanze sempre a 200 euro anche se di condanna o ingiunzione (l'ordinanza ex art. 186-ter sconta l'imposta proporzionale; per l'ordinanza di assegnazione presso terzi una notizia del sito indica la misura fissa). Il tool non valida i valori negativi. Se questi casi restano fuori, il grado va portato a INDICATIVO. Fase 0: la pagina del sito e' un redirect al servizio dell'Agenzia delle Entrate (www1.agenziaentrate.it, certificato non valido); resta solo_norma. |
| `testimonianza_scritta` | documento | strutturale | https://www.avvocatoandreani.it/servizi/testimonianza-scritta-257-bis-cpc.php (alta) | Ministero della Giustizia, modello di testimonianza scritta e istruzioni approvati con DM 17/02/2010 (art. 103-bis disp. att. c.p.c.), pagina 'Testimonianza scritta' di giustizia.it | Corretto dall'audit (par. 4.6): tolta l'ammonizione sull'importanza religiosa del giuramento (Corte cost. 149/1995). Il confronto va fatto con il modello ministeriale, che il sito riproduce con le istruzioni (riquadri numerati, dichiarazioni del teste nei riquadri 9 e 10). Scostamenti da confermare: la firma del teste va autenticata su ciascuna facciata da un segretario comunale o dal cancelliere di un ufficio giudiziario, gratuitamente e senza bollo (art. 103-bis co. 3 disp. att.), mentre il modello parla di 'altro pubblico ufficiale' e prevede un'unica autenticazione finale; l'istruzione 'non è possibile deporre su fatti appresi da terzi' va confrontata con le istruzioni ufficiali (nel processo civile la testimonianza de relato non è vietata, rileva la fonte della conoscenza); la sanzione per la mancata restituzione è la pena pecuniaria dell'art. 255 co. 1 (il sito indica da 100 a 1.000 euro). Con una lista di capitoli vuota il modulo è generato comunque. |

### `attestazione_conformita`

Genera l'attestazione di conformità del difensore per copie estratte dal fascicolo informatico, copie informatiche di atti analogici e duplicati.

- Parametri: `avvocato: str; tipo_documento: str; estremi_originale: str; modalita: str = 'estratto' (estratto, copia_informatica, duplicato)`
- Fonte normativa dichiarata: artt. 196-octies, 196-novies, 196-decies e 196-undecies disp. att. c.p.c. (D.Lgs. 149/2022) in luogo degli artt. 16-bis co. 9-bis e 16-undecies DL 179/2012; DM 44/2011 e specifiche DGSIA
- Casi di prova:
  - Copia estratta dal fascicolo informatico: `{"avvocato": "Mario Rossi", "tipo_documento": "sentenza n. 1234/2026", "estremi_originale": "R.G. 5678/2025, pagg. 1-12", "modalita": "estratto"}` → atteso: artt. 196-octies e 196-undecies disp. att. c.p.c. nel testo e nel campo riferimento_normativo, senza richiami al DL 179/2012
  - Copia informatica di un atto analogico: `{"avvocato": "Mario Rossi", "tipo_documento": "contratto di locazione", "estremi_originale": "originale cartaceo del 01/02/2020", "modalita": "copia_informatica"}` → atteso: art. 196-novies (non 196-decies) e art. 196-undecies disp. att. c.p.c.; conformità all'originale analogico
  - Duplicato informatico: `{"avvocato": "Mario Rossi", "tipo_documento": "decreto ingiuntivo n. 321/2026", "estremi_originale": "R.G. 999/2026", "modalita": "duplicato"}` → atteso: art. 196-octies disp. att. c.p.c. (duplicato dal fascicolo informatico) e art. 196-undecies

### `atto_di_precetto`

Genera l'atto di precetto con intimazione a pagare entro dieci giorni, prospetto delle somme e avvertimenti al debitore.

- Parametri: `creditore: str; debitore: str; titolo_esecutivo: str; importo_capitale: float; interessi: float = 0; spese: float = 0`
- Fonte normativa dichiarata: art. 480 c.p.c. (precetto; dieci giorni per pagare, poi il pignoramento)
- Casi di prova:
  - Precetto con capitale, interessi e spese: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "titolo_esecutivo": "decreto ingiuntivo n. 321/2026 del Tribunale di Milano, dichiarato esecutivo", "importo_capitale": 10000, "interessi": 350.25, "spese": 1200}` → atteso: totale_intimato 11.550,25 euro; riferimenti attesi: art. 480 co. 1 (termine non minore di dieci giorni), co. 2 (avvertimento sul sovraindebitamento), co. 3 (giudice dell'esecuzione e residenza o domicilio eletto), artt. 479, 481 (novanta giorni), 615 e 617 (venti giorni) c.p.c.; nessuna 'forma esecutiva'
  - Solo capitale: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "titolo_esecutivo": "decreto ingiuntivo n. 321/2026 del Tribunale di Milano, dichiarato esecutivo", "importo_capitale": 2500, "interessi": 0, "spese": 0}` → atteso: totale_intimato 2.500,00 euro; stessi riferimenti

### `calcolo_hash`

Calcola l'impronta SHA-256 di un testo codificato in UTF-8.

- Parametri: `testo: str`
- Fonte normativa dichiarata: DM 44/2011, specifiche tecniche PCT (algoritmo SHA-256)
- Casi di prova:
  - Vettore standard 'abc': `{"testo": "abc"}` → atteso: ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad (FIPS 180-4); lunghezza_input 3
  - Stringa vuota: `{"testo": ""}` → atteso: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855; lunghezza_input 0
  - Vettore a due blocchi da 448 bit: `{"testo": "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"}` → atteso: 248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1 (FIPS 180-4)
  - Carattere accentato (codifica UTF-8): `{"testo": "è"}` → atteso: 97c916cd94785d7b9b52ae7013c267854f275691ddaae212bc1c07f639b8a0c7 (byte c3 a8); lunghezza_input 1 carattere contro 2 byte
  - A capo finale (come un file di testo salvato con newline): `{"testo": "abc\n"}` → atteso: edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb: il file caricato sul sito deve avere lo stesso a capo finale

### `cerca_ufficio_giudiziario`

Cerca il tribunale o il giudice di pace competente per un comune in una tabella di 102 capoluoghi, con suggerimenti per corrispondenze parziali.

- Parametri: `comune: str; tipo: str = 'tribunale' (tribunale, giudice_pace)`
- Fonte normativa dichiarata: R.D. 30 gennaio 1941 n. 12, ordinamento giudiziario; circondari vigenti
- Casi di prova:
  - Capoluogo presente in tabella: `{"comune": "Monza", "tipo": "tribunale"}` → atteso: Tribunale di Monza (trovato)
  - Giudice di pace di un capoluogo: `{"comune": "Roma", "tipo": "giudice_pace"}` → atteso: Giudice di Pace di Roma
  - Comune il cui nome contiene quello di un capoluogo: `{"comune": "Torino di Sangro", "tipo": "tribunale"}` → atteso: da leggere dal sito (ufficio abruzzese); il tool suggerisce il Tribunale di Torino, certamente errato
  - Altro falso positivo della ricerca parziale: `{"comune": "Bari Sardo", "tipo": "tribunale"}` → atteso: da leggere dal sito (atteso il Tribunale di Lanusei); il tool suggerisce il Tribunale di Bari
  - Comune non capoluogo: `{"comune": "Sesto San Giovanni", "tipo": "tribunale"}` → atteso: da leggere dal sito (atteso il Tribunale di Monza); il tool non trova il comune
  - Tipo di ufficio non ammesso: `{"comune": "Milano", "tipo": "corte_appello"}` → atteso: errore per tipo non ammesso (o Corte d'appello di Milano); il tool restituisce il Tribunale di Milano

### `codici_iscrizione_ruolo`

Cerca per parola chiave i codici oggetto per l'iscrizione a ruolo delle cause civili in una tabella di 89 voci.

- Parametri: `materia: str`
- Fonte normativa dichiarata: provvedimenti DGSIA, codici oggetto per l'iscrizione a ruolo (tabella aggiornata)
- Casi di prova:
  - Parola chiave 'sfratto': `{"materia": "sfratto"}` → atteso: 5 codici: 030001, 030002, 030011, 030012, 030021, con descrizioni identiche a quelle del sito
  - Parola chiave suggerita dal docstring, senza accento: `{"materia": "responsabilita"}` → atteso: 11 codici: gli 8 della materia responsabilità (145001, 145002, 145003, 145011, 145012, 145013, 145021, 145999) più 151110, 152110 e 153110; il tool ne restituisce 6
  - Materia accentata cercata senza accento: `{"materia": "proprieta"}` → atteso: 9 codici della materia proprietà (130001, 130011, 130021, 130031, 130032, 130041, 131002, 131003, 131011); il tool ne restituisce 1
  - Ricerca nella descrizione: `{"materia": "usucapione"}` → atteso: 131002 e 131003, da confermare sul sito

### `contributo_unificato`

Calcola il contributo unificato per valore, tipo di procedimento e grado: scaglioni dell'art. 13 DPR 115/2002, aumento della metà in appello e raddoppio in Cassazione, voci fisse, esenzione condizionata di lavoro e previdenza, tributario e TAR; accetta una tabella sostitutiva fornita dal chiamante.

- Parametri: `valore_causa: float; tipo_procedimento: str = 'cognizione' (cognizione, valore_indeterminabile, valore_indeterminabile_gdp, monitorio, opposizione_decreto_ingiuntivo, opposizione_atti_esecutivi, esecuzione_immobiliare, esecuzione_mobiliare, cautelari, volontaria_giurisdizione, separazione_consensuale, separazione_giudiziale, divorzio_congiunto, divorzio_giudiziale, lavoro, previdenza, tributario, tar); grado: str = 'primo' (primo, appello, cassazione); tabella_contributo_unificato: dict \| None = None; reddito_oltre_soglia_lavoro: bool = False`
- Fonte normativa dichiarata: DPR 115/2002 art. 13 (importi riscontrati su Normattiva il 20/09/2026), art. 9 co. 1-bis (lavoro e previdenza), art. 13 co. 6-quater (tributario)
- Casi di prova:
  - Confine del primo scaglione: valore pari a 1.100 euro: `{"valore_causa": 1100, "tipo_procedimento": "cognizione", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 43,00 euro (art. 13 co. 1 lett. a DPR 115/2002: valore fino a 1.100)
  - Appena sopra il primo confine: `{"valore_causa": 1100.01, "tipo_procedimento": "cognizione", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 98,00 euro (art. 13 co. 1 lett. b); sul sito, se accetta solo interi, 1.101
  - Appena sopra 26.000 euro: `{"valore_causa": 26000.01, "tipo_procedimento": "cognizione", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 518,00 euro (lett. d: oltre 26.000 e fino a 52.000)
  - Ultimo scaglione: `{"valore_causa": 520000.01, "tipo_procedimento": "cognizione", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 1.686,00 euro (lett. g)
  - Appello, scaglione 26.000-52.000: `{"valore_causa": 30000, "tipo_procedimento": "cognizione", "grado": "appello", "reddito_oltre_soglia_lavoro": false}` → atteso: 777,00 euro (518 aumentato della metà, art. 13 co. 1-bis)
  - Cassazione, ultimo scaglione: `{"valore_causa": 600000, "tipo_procedimento": "cognizione", "grado": "cassazione", "reddito_oltre_soglia_lavoro": false}` → atteso: 3.372,00 euro (1.686 raddoppiato, art. 13 co. 1-bis)
  - Monitorio al confine di 5.200 euro: `{"valore_causa": 5200, "tipo_procedimento": "monitorio", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 49,00 euro (98 ridotto alla metà, art. 13 co. 3)
  - Esecuzione mobiliare appena sotto 2.500 euro: `{"valore_causa": 2499.99, "tipo_procedimento": "esecuzione_mobiliare", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 43,00 euro (valore inferiore a 2.500, art. 13 co. 2)
  - Esecuzione mobiliare a 2.500 euro: `{"valore_causa": 2500, "tipo_procedimento": "esecuzione_mobiliare", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 139,00 euro (metà di 278 per gli altri processi esecutivi, art. 13 co. 2)
  - Lavoro, primo grado, reddito oltre tre volte la soglia dell'art. 76: `{"valore_causa": 30000, "tipo_procedimento": "lavoro", "grado": "primo", "reddito_oltre_soglia_lavoro": true}` → atteso: 259,00 euro (art. 9 co. 1-bis e art. 13 co. 3: metà di 518); con reddito_oltre_soglia_lavoro false 0,00
  - Lavoro in Cassazione oltre soglia: `{"valore_causa": 30000, "tipo_procedimento": "lavoro", "grado": "cassazione", "reddito_oltre_soglia_lavoro": true}` → atteso: da leggere dal sito: l'art. 9 co. 1-bis rinvia alla misura dell'art. 13 co. 1 (518); il tool la raddoppia ex co. 1-bis e dà 1.036,00
  - Tributario appena sopra 2.582,28 euro: `{"valore_causa": 2582.29, "tipo_procedimento": "tributario", "grado": "primo", "reddito_oltre_soglia_lavoro": false}` → atteso: 60,00 euro (art. 13 co. 6-quater lett. b)
  - Tributario in appello: `{"valore_causa": 50000, "tipo_procedimento": "tributario", "grado": "appello", "reddito_oltre_soglia_lavoro": false}` → atteso: 250,00 euro (co. 6-quater: stessi importi davanti alle Corti di giustizia tributaria di primo e secondo grado); da confermare sul sito
  - Tributario in Cassazione (voce aperta del par. 7): `{"valore_causa": 50000, "tipo_procedimento": "tributario", "grado": "cassazione", "reddito_oltre_soglia_lavoro": false}` → atteso: da leggere dal sito: il tool applica la scala civile raddoppiata e dà 1.036,00
  - TAR in Cassazione, combinazione senza base normativa: `{"valore_causa": 0, "tipo_procedimento": "tar", "grado": "cassazione", "reddito_oltre_soglia_lavoro": false}` → atteso: errore atteso: la combinazione non corrisponde a nessuna voce dell'art. 13 (contro le decisioni del Consiglio di Stato è ammesso solo il ricorso per motivi di giurisdizione, art. 111 co. 8 Cost.); il tool restituisce 1.300,00

### `copie_processo_tributario`

Calcola i diritti di copia nel processo tributario per numero di pagine, tipo di copia e urgenza.

- Parametri: `n_pagine: int; tipo: str = 'semplice' (semplice, autentica); urgente: bool = False`
- Fonte normativa dichiarata: DPR 115/2002, tariffe del processo tributario (0,25 euro a pagina semplice, 0,50 autentica)
- Casi di prova:
  - Copia semplice, prima fascia: `{"n_pagine": 4, "tipo": "semplice", "urgente": false}` → atteso: da leggere dal sito (fascia 1-4 pagine, copia cartacea senza certificazione); il tool dà 1,00 euro
  - Copia autentica al confine di fascia (5 pagine): `{"n_pagine": 5, "tipo": "autentica", "urgente": false}` → atteso: da leggere dal sito (fascia 5-10 pagine con certificazione); il tool dà 2,50 euro
  - Copia autentica urgente, fascia 21-50: `{"n_pagine": 21, "tipo": "autentica", "urgente": true}` → atteso: da leggere dal sito: triplo della fascia se si applica l'art. 270 DPR 115/2002; il tool dà 15,75 euro (+50%)
  - Tipo non ammesso: `{"n_pagine": 10, "tipo": "esecutiva", "urgente": false}` → atteso: errore per tipo non ammesso; il tool calcola 2,50 euro come copia semplice

### `decreto_ingiuntivo`

Genera la bozza di ricorso per decreto ingiuntivo con giudice competente per valore o per materia, contributo unificato del monitorio, eventuale richiesta di provvisoria esecuzione e termini di opposizione e notifica.

- Parametri: `creditore: str; debitore: str; importo: float; tipo_credito: str = 'ordinario' (ordinario, professionale, condominiale, cambiale, retribuzioni); provvisoria_esecuzione: bool = False`
- Fonte normativa dichiarata: artt. 633-656 c.p.c.; art. 7 c.p.c. nel testo del D.Lgs. 149/2022 (giudice di pace fino a 10.000 euro); art. 413 c.p.c. (crediti di lavoro); DPR 115/2002 art. 13 co. 3 (CU del monitorio a metà)
- Casi di prova:
  - Confine della competenza del giudice di pace (10.000 euro): `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "importo": 10000, "tipo_credito": "ordinario", "provvisoria_esecuzione": false}` → atteso: Giudice di Pace (art. 7 co. 1 c.p.c.); CU 118,50 euro (art. 13 co. 1 lett. c e co. 3 DPR 115/2002); nel testo artt. 633 e ss. c.p.c., nella risposta art. 641 (40 giorni, 50 nell'Unione europea, 60 fuori) e art. 644 (60 giorni, 90 all'estero)
  - Appena sopra la soglia: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "importo": 10000.01, "tipo_credito": "ordinario", "provvisoria_esecuzione": false}` → atteso: Tribunale; CU 118,50 euro
  - Credito retributivo: `{"creditore": "Mario Rossi", "debitore": "Beta S.r.l.", "importo": 8000, "tipo_credito": "retribuzioni", "provvisoria_esecuzione": false}` → atteso: Tribunale in funzione di giudice del lavoro (artt. 409 e 413 c.p.c.); CU 0 se il ricorrente non supera tre volte la soglia dell'art. 76, altrimenti 118,50 euro (art. 9 co. 1-bis DPR 115/2002): il tool indica 118,50 senza condizione
  - Credito professionale con provvisoria esecuzione: `{"creditore": "Avv. Mario Rossi", "debitore": "Beta S.r.l.", "importo": 3000, "tipo_credito": "professionale", "provvisoria_esecuzione": true}` → atteso: il testo non deve fondare la provvisoria esecuzione sull'art. 642 co. 1; riferimenti attesi: art. 636 (parcella con parere del Consiglio dell'Ordine), art. 642 co. 2, art. 637 co. 3 c.p.c.; Giudice di Pace, CU 49,00 euro
  - Credito condominiale sopra soglia con provvisoria esecuzione: `{"creditore": "Condominio Via Roma 1 Milano", "debitore": "Luca Bianchi", "importo": 12000, "tipo_credito": "condominiale", "provvisoria_esecuzione": true}` → atteso: Tribunale; provvisoria esecuzione ex art. 63 disp. att. c.c. (stato di ripartizione approvato dall'assemblea); CU 118,50 euro

### `dichiarazione_553_cpc`

Genera la dichiarazione del terzo pignorato (banca, datore di lavoro o altro debitore) nel pignoramento presso terzi.

- Parametri: `terzo_pignorato: str; debitore: str; procedura: str; tipo_rapporto: str = 'conto_corrente' (conto_corrente, stipendio, altro)`
- Fonte normativa dichiarata: art. 547 c.p.c. (dichiarazione entro dieci giorni, art. 543 co. 2 n. 3 secondo il docstring) e art. 548 c.p.c. (mancata dichiarazione)
- Casi di prova:
  - Banca, conto corrente: `{"terzo_pignorato": "Banca Gamma S.p.A.", "debitore": "Luca Bianchi", "procedura": "R.G.E. 456/2026", "tipo_rapporto": "conto_corrente"}` → atteso: riferimenti attesi: art. 547 c.p.c. (contenuto, compresi sequestri e cessioni), art. 546 (vincolo delle somme), art. 548 (mancata dichiarazione), art. 543 co. 2 n. 4 (dieci giorni, raccomandata o PEC)
  - Datore di lavoro, stipendio: `{"terzo_pignorato": "Delta S.r.l.", "debitore": "Luca Bianchi", "procedura": "R.G.E. 456/2026", "tipo_rapporto": "stipendio"}` → atteso: art. 545 c.p.c. per la quota pignorabile, cessioni e delegazioni preesistenti, sequestri precedenti (art. 547), art. 548
  - Altro rapporto: `{"terzo_pignorato": "Epsilon S.r.l.", "debitore": "Luca Bianchi", "procedura": "R.G.E. 456/2026", "tipo_rapporto": "altro"}` → atteso: anche nella variante generica sequestri precedenti e cessioni notificate o accettate (art. 547); oggi solo 'vincoli' generici

### `diritti_copia`

Calcola i diritti di copia di atti giudiziari per numero di pagine, tipo di copia (semplice, autentica, esecutiva), formato cartaceo o digitale e urgenza.

- Parametri: `n_pagine: int; tipo: str = 'semplice' (semplice, autentica, esecutiva); formato: str = 'digitale' (digitale, cartaceo); urgente: bool = False`
- Fonte normativa dichiarata: DPR 115/2002 artt. 267-270 e allegato 8; DL 90/2014 conv. L. 114/2014 (copia semplice digitale gratuita)
- Casi di prova:
  - Copia semplice cartacea, prima fascia (4 pagine): `{"n_pagine": 4, "tipo": "semplice", "formato": "cartaceo", "urgente": false}` → atteso: da leggere dal sito: fascia 1-4 pagine dell'allegato 6 nel testo in vigore dal 01/01/2025; il tool dà 1,20 euro
  - Copia autentica cartacea al confine tra prima e seconda fascia (5 pagine): `{"n_pagine": 5, "tipo": "autentica", "formato": "cartaceo", "urgente": false}` → atteso: da leggere dal sito: fascia 5-10 pagine dell'allegato 7 (diritto forfettizzato più diritto di certificazione); il tool dà 3,50 euro
  - Copia autentica cartacea urgente, fascia 11-20: `{"n_pagine": 11, "tipo": "autentica", "formato": "cartaceo", "urgente": true}` → atteso: triplo dell'importo della fascia 11-20 dell'allegato 7 (art. 270 DPR 115/2002), da leggere dal sito; il tool dà 11,55 euro (+50%)
  - Copia semplice digitale: `{"n_pagine": 30, "tipo": "semplice", "formato": "digitale", "urgente": false}` → atteso: 0,00 euro: nessun diritto per la copia senza certificazione estratta dal fascicolo informatico dai soggetti abilitati (art. 269 DPR 115/2002 nel testo della L. 207/2024)
  - Copia autentica digitale oltre 100 pagine con urgenza: `{"n_pagine": 101, "tipo": "autentica", "formato": "digitale", "urgente": true}` → atteso: da leggere dal sito: forfait dell'allegato 8 (8 euro per trasmissione telematica, 25 per supporto fisico) più l'eventuale diritto di certificazione, senza maggiorazione d'urgenza (art. 270 solo per il cartaceo); il tool dà 11,75 euro
  - Tipo 'esecutiva' dopo la riforma dell'art. 475 c.p.c.: `{"n_pagine": 3, "tipo": "esecutiva", "formato": "cartaceo", "urgente": false}` → atteso: da leggere dal sito: stesso importo della copia autentica (allegato 7, fascia 1-4 pagine); il tool dà 2,10 euro

### `fascicolo_di_parte`

Genera il frontespizio del fascicolo di parte con ufficio, numero di ruolo, parti, difensore e traccia dell'indice dei documenti.

- Parametri: `avvocato: str; parte: str; controparte: str; tribunale: str; rg_numero: str \| None = None`
- Fonte normativa dichiarata: art. 165 c.p.c. (costituzione dell'attore); specifiche PCT DM 44/2011
- Casi di prova:
  - Frontespizio completo: `{"avvocato": "Mario Rossi", "parte": "Alfa S.r.l.", "controparte": "Beta S.p.A.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2026"}` → atteso: ufficio, 'R.G. n. 12345/2026', parti, difensore e indice; riferimenti attesi: art. 165 c.p.c. (art. 166 per il convenuto) e art. 74 disp. att. c.p.c.
  - Numero di ruolo non ancora assegnato: `{"avvocato": "Mario Rossi", "parte": "Alfa S.r.l.", "controparte": "Beta S.p.A.", "tribunale": "Tribunale di Roma", "rg_numero": null}` → atteso: segnaposto 'R.G. n. ___/____'; stessi riferimenti

### `indice_documenti`

Genera l'indice numerato dei documenti allegati con descrizione, pagine e totali.

- Parametri: `documenti: list[dict] (chiavi numero: int, descrizione: str, pagine: int)`
- Fonte normativa dichiarata: specifiche tecniche PCT, DM 44/2011 (elenco degli allegati al deposito)
- Casi di prova:
  - Tre documenti: `{"documenti": [{"numero": 1, "descrizione": "Contratto di fornitura", "pagine": 12}, {"numero": 2, "descrizione": "Fatture insolute", "pagine": 5}, {"numero": 3, "descrizione": "Diffida", "pagine": 2}]}` → atteso: totale_documenti 3, totale_pagine 19, righe Doc. 1-3 nell'ordine dato; riferimento atteso art. 74 disp. att. c.p.c.
  - Elenco vuoto: `{"documenti": []}` → atteso: totale_documenti 0 e totale_pagine 0, oppure errore per indice vuoto
  - Numero di pagine non numerico: `{"documenti": [{"numero": 1, "descrizione": "Contratto", "pagine": "abc"}]}` → atteso: errore gestito (oggi ValueError)

### `istanza_visibilita_fascicolo`

Genera l'istanza di visibilità del fascicolo telematico per il difensore non ancora costituito (costituzione, consultazione o intervento).

- Parametri: `avvocato: str; parte: str; tribunale: str; rg_numero: str; motivo: str = 'costituzione' (costituzione, consultazione, intervento)`
- Fonte normativa dichiarata: art. 196-quater disp. att. c.p.c. (D.Lgs. 149/2022, già art. 16-bis DL 179/2012); DM 44/2011 e specifiche DGSIA
- Casi di prova:
  - Difensore del convenuto non ancora costituito: `{"avvocato": "Mario Rossi", "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano, Sezione Prima Civile", "rg_numero": "12345/2026", "motivo": "costituzione"}` → atteso: riferimenti attesi: artt. 76 e 196-quater disp. att. c.p.c., anche nel campo riferimento_normativo (non l'art. 16-bis DL 179/2012); mandato allegato
  - Intervento volontario: `{"avvocato": "Mario Rossi", "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2026", "motivo": "intervento"}` → atteso: art. 105 c.p.c. oltre ai riferimenti precedenti
  - Motivo non previsto: `{"avvocato": "Mario Rossi", "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2026", "motivo": "altro"}` → atteso: errore per motivo non ammesso (oggi testo del motivo 'costituzione')

### `nota_precisazione_credito`

Genera la nota di precisazione del credito nelle procedure esecutive con prospetto di capitale, interessi e spese.

- Parametri: `creditore: str; debitore: str; procedura_esecutiva: str; capitale: float; interessi: float; spese_legali: float; spese_esecuzione: float`
- Fonte normativa dichiarata: atto di prassi non tipizzato: artt. 510, 543 e 596 c.p.c. (assegnazione o distribuzione)
- Casi di prova:
  - Nota con tutte le voci: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "procedura_esecutiva": "R.G.E. 123/2026", "capitale": 5000, "interessi": 125.5, "spese_legali": 800, "spese_esecuzione": 150.75}` → atteso: totale_credito 6.076,25 euro; riferimenti attesi: artt. 510 e 596 c.p.c. (distribuzione) e art. 553 (assegnazione presso terzi), nessun richiamo all'art. 547

### `note_iscrizione_ruolo`

Suggerisce i codici oggetto per l'iscrizione a ruolo e calcola il contributo unificato di primo grado per il tipo di procedimento.

- Parametri: `tipo_procedimento: str (cognizione_ordinaria, lavoro, locazione, condominio, esecuzione_mobiliare, esecuzione_immobiliare, monitorio, volontaria_giurisdizione); valore_causa: float \| None = None`
- Fonte normativa dichiarata: DPR 115/2002 (CU); provvedimenti DGSIA sui codici oggetto di iscrizione a ruolo
- Casi di prova:
  - Cognizione ordinaria al confine di 26.000 euro: `{"tipo_procedimento": "cognizione_ordinaria", "valore_causa": 26000}` → atteso: CU 237,00 euro (art. 13 co. 1 lett. c); codici della materia contratto presenti con la stessa descrizione nella tabella ministeriale
  - Locazione: convalida di sfratto o causa ordinaria: `{"tipo_procedimento": "locazione", "valore_causa": 3000}` → atteso: 49,00 euro per la convalida di sfratto (98 ridotto alla metà, valore pari ai canoni scaduti, art. 13 co. 3); 98,00 per la causa locatizia ordinaria: il tool dà 98 senza distinguere
  - Esecuzione mobiliare senza valore: `{"tipo_procedimento": "esecuzione_mobiliare", "valore_causa": null}` → atteso: CU non determinabile senza valore: 43 euro sotto 2.500, 139 da 2.500 (art. 13 co. 2); il tool dà 43
  - Lavoro: `{"tipo_procedimento": "lavoro", "valore_causa": 20000}` → atteso: 0 sotto tre volte la soglia dell'art. 76, 118,50 euro oltre (art. 9 co. 1-bis e art. 13 co. 3): il tool dà 0 senza avviso
  - Monitorio al primo confine: `{"tipo_procedimento": "monitorio", "valore_causa": 1100}` → atteso: 21,50 euro (43 ridotto alla metà, art. 13 co. 3)

### `note_trattazione_scritta`

Genera le note scritte depositate in sostituzione dell'udienza ex art. 127-ter c.p.c. con le conclusioni della parte.

- Parametri: `avvocato: str; parte: str; tribunale: str; rg_numero: str; giudice: str; conclusioni: str`
- Fonte normativa dichiarata: art. 127-ter c.p.c. (D.Lgs. 149/2022; dal 01/01/2023 anche ai procedimenti pendenti, art. 35 co. 2 mod. L. 197/2022); limiti del correttivo D.Lgs. 164/2024
- Casi di prova:
  - Note con istanze istruttorie: `{"avvocato": "Mario Rossi", "parte": "Alfa S.r.l.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2025", "giudice": "dott.ssa Laura Bianchi", "conclusioni": "Si insiste per l'ammissione delle prove orali dedotte nella memoria ex art. 171-ter n. 2 c.p.c."}` → atteso: riferimenti attesi: art. 127-ter c.p.c. con la formula 'note contenenti le sole istanze e conclusioni', richiamo al provvedimento di sostituzione dell'udienza e al termine assegnato (non inferiore a quindici giorni); nessuna parte argomentativa

### `pignoramento_stipendio`

Calcola la quota pignorabile di stipendio o pensione ex art. 545 c.p.c. per tipo di credito (ordinario, alimentare, fiscale dell'agente della riscossione, concorso), applicando alle pensioni il minimo impignorabile.

- Parametri: `stipendio_netto_mensile: float; tipo_credito: str = 'ordinario' (ordinario, alimentare, fiscale, concorso_crediti); pensione: bool = False; assegno_sociale_mensile: float \| None = None`
- Fonte normativa dichiarata: art. 545 c.p.c. (co. 3-5 stipendi; co. 7 pensioni nel testo dell'art. 21-bis DL 115/2022 conv. L. 142/2022; co. 8 somme su conto); art. 72-ter DPR 602/1973
- Casi di prova:
  - Stipendio, credito ordinario: `{"stipendio_netto_mensile": 1500, "tipo_credito": "ordinario", "pensione": false, "assegno_sociale_mensile": null}` → atteso: 300,00 euro (un quinto, art. 545 co. 4 c.p.c.)
  - Pensione con assegno sociale 2026 passato dal chiamante: `{"stipendio_netto_mensile": 1500, "tipo_credito": "ordinario", "pensione": true, "assegno_sociale_mensile": 546.24}` → atteso: 81,50 euro: impignorabile 1.092,48 (doppio di 546,24), base 407,52, un quinto (art. 545 co. 7 e co. 4)
  - Pensione con il default del tool (assegno sociale 2024): `{"stipendio_netto_mensile": 1500, "tipo_credito": "ordinario", "pensione": true, "assegno_sociale_mensile": null}` → atteso: 81,50 euro con l'assegno sociale 2026; il tool usa 534,41 e dà 86,24 euro: scostamento atteso di 4,74 euro
  - Pensione bassa: il minimo di 1.000 euro prevale sul doppio dell'assegno: `{"stipendio_netto_mensile": 1000, "tipo_credito": "ordinario", "pensione": true, "assegno_sociale_mensile": 480}` → atteso: 0,00 euro (2 x 480 = 960, sotto il minimo di 1.000 dell'art. 545 co. 7)
  - Credito fiscale al confine di 2.500 euro: `{"stipendio_netto_mensile": 2500, "tipo_credito": "fiscale", "pensione": false, "assegno_sociale_mensile": null}` → atteso: 250,00 euro (un decimo fino a 2.500, art. 72-ter DPR 602/1973)
  - Credito fiscale appena sopra 2.500 euro: `{"stipendio_netto_mensile": 2500.01, "tipo_credito": "fiscale", "pensione": false, "assegno_sociale_mensile": null}` → atteso: 357,14 euro (un settimo oltre 2.500 e fino a 5.000)
  - Credito fiscale appena sopra 5.000 euro: `{"stipendio_netto_mensile": 5000.01, "tipo_credito": "fiscale", "pensione": false, "assegno_sociale_mensile": null}` → atteso: 1.000,00 euro (un quinto oltre 5.000, art. 72-ter che rinvia all'art. 545 co. 4)
  - Credito fiscale su pensione: `{"stipendio_netto_mensile": 3000, "tipo_credito": "fiscale", "pensione": true, "assegno_sociale_mensile": 546.24}` → atteso: da leggere dal sito: il tool applica un settimo all'eccedenza di 1.907,52 e dà 272,50 euro; con la fascia scelta sull'eccedenza sarebbe un decimo (190,75)

### `procura_alle_liti`

Genera la procura alle liti generale, speciale o per l'appello, con elezione di domicilio, clausole su privacy e antiriciclaggio e autentica della firma.

- Parametri: `parte: str; avvocato: str; cf_avvocato: str; foro: str; oggetto_causa: str; tipo: str = 'generale' (generale, speciale, appello)`
- Fonte normativa dichiarata: art. 83 c.p.c. (testo vigente); clausole GDPR e antiriciclaggio
- Casi di prova:
  - Procura generale: `{"parte": "Giulia Verdi", "avvocato": "Mario Rossi", "cf_avvocato": "RSSMRA80A01F205X", "foro": "Milano", "oggetto_causa": "risarcimento danni da inadempimento contrattuale", "tipo": "generale"}` → atteso: procura per ogni stato e grado con poteri espressi di conciliare, transigere e rinunciare (art. 84 co. 2 c.p.c.) e autentica della firma da parte del difensore (art. 83 co. 3); riferimenti attesi: art. 83 c.p.c., art. 13 Reg. UE 2016/679, D.Lgs. 231/2007 con l'articolo vigente corretto
  - Procura per l'appello: `{"parte": "Giulia Verdi", "avvocato": "Mario Rossi", "cf_avvocato": "RSSMRA80A01F205X", "foro": "Milano", "oggetto_causa": "appello avverso la sentenza n. 100/2026 del Tribunale di Milano", "tipo": "appello"}` → atteso: procura speciale per il grado d'appello (art. 83 co. 4 c.p.c.: senza volontà diversa la procura vale per un solo grado) con gli estremi della sentenza impugnata
  - Procura speciale per il solo giudizio: `{"parte": "Giulia Verdi", "avvocato": "Mario Rossi", "cf_avvocato": "RSSMRA80A01F205X", "foro": "Milano", "oggetto_causa": "opposizione a decreto ingiuntivo n. 321/2026", "tipo": "speciale"}` → atteso: procura limitata al presente giudizio; stessi riferimenti della procura generale

### `relata_notifica_pec`

Genera la relata di notificazione a mezzo PEC dell'avvocato ex L. 53/1994 con le regole di perfezionamento della notifica.

- Parametri: `avvocato: str; destinatario: str; pec_destinatario: str; atto_notificato: str; data_invio: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: art. 3-bis L. 53/1994 (mod. L. 228/2012); perfezionamento con la ricevuta di avvenuta consegna
- Casi di prova:
  - Relata ordinaria: `{"avvocato": "Mario Rossi", "destinatario": "Beta S.p.A.", "pec_destinatario": "beta@pec.it", "atto_notificato": "atto di citazione", "data_invio": "2026-10-05"}` → atteso: riferimenti attesi: artt. 1 e 3-bis L. 53/1994 e art. 147 co. 3 c.p.c. (ore 21-7); elementi dell'art. 3-bis co. 5: codice fiscale del notificante, parte che ha conferito la procura con codice fiscale, destinatario, PEC, elenco pubblico effettivo, attestazione di conformità se copia di atto analogico; data 05/10/2026
  - Data inesistente: `{"avvocato": "Mario Rossi", "destinatario": "Beta S.p.A.", "pec_destinatario": "beta@pec.it", "atto_notificato": "atto di citazione", "data_invio": "2026-02-30"}` → atteso: errore gestito (oggi ValueError non intercettato)

### `sfratto_morosita`

Genera l'intimazione di sfratto per morosità con citazione per la convalida e calcola il totale dei canoni insoluti.

- Parametri: `locatore: str; conduttore: str; immobile: str; canone_mensile: float; mensilita_insolute: int; data_contratto: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: artt. 658-669 c.p.c.; art. 55 L. 392/1978 (termine di grazia fino a 90 giorni)
- Casi di prova:
  - Quattro mensilità insolute: `{"locatore": "Mario Rossi", "conduttore": "Luca Bianchi", "immobile": "Milano, via Roma 1, foglio 10 mappale 20 sub 3", "canone_mensile": 750, "mensilita_insolute": 4, "data_contratto": "2022-03-01"}` → atteso: totale_dovuto 3.000,00 euro; riferimenti attesi: artt. 658, 660 (venti giorni liberi), 663 e 664 c.p.c., art. 55 L. 392/1978 limitato alle locazioni abitative
  - Nessuna mensilità insoluta: `{"locatore": "Mario Rossi", "conduttore": "Luca Bianchi", "immobile": "Milano, via Roma 1, foglio 10 mappale 20 sub 3", "canone_mensile": 750, "mensilita_insolute": 0, "data_contratto": "2022-03-01"}` → atteso: errore per mensilità non positive (oggi totale 0,00)

### `sollecito_pagamento`

Genera la bozza di lettera di sollecito con il calcolo degli interessi di mora per semestri al tasso del D.Lgs. 231/2002 (BCE più 8 punti) o a un tasso convenzionale.

- Parametri: `creditore: str; debitore: str; importo: float; data_scadenza: str (YYYY-MM-DD); data_sollecito: str (YYYY-MM-DD); tasso_mora: float \| None = None`
- Fonte normativa dichiarata: D.Lgs. 231/2002 (tasso BCE più 8 punti, aggiornato semestralmente); tasso convenzionale con tasso_mora
- Casi di prova:
  - Ritardo a cavallo dei due semestri 2026: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.p.A.", "importo": 10000, "data_scadenza": "2026-03-31", "data_sollecito": "2026-09-30", "tasso_mora": null}` → atteso: 515,19 euro: 91 giorni al 10,15% (primo semestre 2026) e 92 giorni al 10,40% (secondo semestre), anno di 365 giorni (artt. 4 e 5 D.Lgs. 231/2002); totale dovuto 10.515,19
  - Contratto anteriore al 01/01/2013 (maggiorazione di 7 punti): `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.p.A.", "importo": 5000, "data_scadenza": "2012-10-15", "data_sollecito": "2012-12-31", "tasso_mora": null}` → atteso: 84,15 euro: BCE 1,00% più 7 punti = 8,00%, 77 giorni su 366 (art. 5 D.Lgs. 231/2002 nel testo anteriore al D.Lgs. 192/2012); il tool applica il 9,00% e dà 94,67
  - Tasso convenzionale su un anno bisestile: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.p.A.", "importo": 10000, "data_scadenza": "2023-12-31", "data_sollecito": "2024-12-31", "tasso_mora": 8.5}` → atteso: da leggere dal sito (convenzione): 366 giorni tutti nel 2024; con divisore 366 850,00 euro, il tool divide per 365 (anno della scadenza) e dà 852,33
  - Sollecito oltre la fine della tabella dei tassi: `{"creditore": "Alfa S.r.l.", "debitore": "Beta S.p.A.", "importo": 10000, "data_scadenza": "2026-11-30", "data_sollecito": "2027-01-31", "tasso_mora": null}` → atteso: 62 giorni di ritardo; il tasso del primo semestre 2027 non è ancora pubblicato, il tool dovrebbe avvisare o rifiutare; a tasso invariato (10,40%) 176,66 euro, mentre il tool calcola solo i 31 giorni di dicembre (88,33)

### `tassazione_atti`

Calcola l'imposta di registro su sentenze di condanna, decreti ingiuntivi, verbali di conciliazione e ordinanze (3% con minimo di 200 euro, 2% prima casa con minimo di 1.000 euro, 200 euro fissi).

- Parametri: `tipo_atto: str (sentenza_condanna, decreto_ingiuntivo, verbale_conciliazione, ordinanza); valore: float; prima_casa: bool = False`
- Fonte normativa dichiarata: DPR 131/1986, testo unico dell'imposta di registro, Tariffa parte I
- Casi di prova:
  - Sentenza di condanna sotto il minimo: `{"tipo_atto": "sentenza_condanna", "valore": 6666, "prima_casa": false}` → atteso: 200,00 euro: il 3% (199,98) è sotto l'imposta fissa (art. 8 co. 1 lett. b Tariffa parte I e art. 41 DPR 131/1986)
  - Sentenza di condanna appena sopra il minimo: `{"tipo_atto": "sentenza_condanna", "valore": 6667, "prima_casa": false}` → atteso: 200,01 euro (3%)
  - Decreto ingiuntivo per 50.000 euro: `{"tipo_atto": "decreto_ingiuntivo", "valore": 50000, "prima_casa": false}` → atteso: 1.500,00 euro se il credito non è soggetto a IVA; 200,00 euro se nasce da fatture con IVA (Nota II all'art. 8 Tariffa parte I e art. 40 DPR 131/1986): il tool dà sempre 1.500
  - Causa di valore non superiore a 1.033 euro: `{"tipo_atto": "sentenza_condanna", "valore": 1000, "prima_casa": false}` → atteso: esente (art. 46 L. 374/1991, circolare AdE 30/E del 29/07/2022); il tool dà 200,00
  - Verbale di conciliazione prima casa sotto il minimo: `{"tipo_atto": "verbale_conciliazione", "valore": 40000, "prima_casa": true}` → atteso: 1.000,00 euro: il 2% (800) è sotto il minimo dell'art. 1 Tariffa parte I; imposte ipotecaria e catastale non calcolate
  - Ordinanza con contenuto di condanna: `{"tipo_atto": "ordinanza", "valore": 20000, "prima_casa": false}` → atteso: da leggere dalla fonte: 200 euro solo per l'ordinanza senza condanna; l'ordinanza-ingiunzione ex art. 186-ter c.p.c. sconta il 3% (600,00 euro)

### `testimonianza_scritta`

Genera il modulo di testimonianza scritta con dati del teste, formula di impegno, capitoli di prova, istruzioni e autenticazione della firma.

- Parametri: `teste: str; capitoli_prova: list[str]`
- Fonte normativa dichiarata: art. 257-bis c.p.c. (testimonianza scritta su autorizzazione del giudice)
- Casi di prova:
  - Due capitoli di prova: `{"teste": "Anna Neri", "capitoli_prova": ["Vero che il 10/01/2026 lei era presente presso il cantiere di via Roma 1 a Milano", "Vero che in quella occasione il sig. Bianchi consegnò le chiavi al sig. Rossi"]}` → atteso: numero_capitoli 2; riferimenti attesi: art. 257-bis c.p.c., art. 251 co. 2 c.p.c. con la formula 'consapevole della responsabilità morale e giuridica' (Corte cost. 149/1995), art. 255 co. 1, art. 103-bis disp. att. c.p.c. e DM 17/02/2010; autenticazione di segretario comunale o cancelliere su ogni facciata
  - Nessun capitolo: `{"teste": "Anna Neri", "capitoli_prova": []}` → atteso: errore per assenza di capitoli (oggi modulo con numero_capitoli 0)

## cerdef.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_giurisprudenza_tributaria` | ricerca_online | smoke_live | nessuna (media) | Dipartimento delle finanze, CeRDEF (def.finanze.it/DocTribFrontend), ricerca avanzata della giurisprudenza | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: formato delle date GG/MM/AAAA; valori di ente e tipo non previsti vengono ignorati in silenzio (nessun filtro applicato); paginazione oltre la prima pagina fino a 250 risultati; criterio 'frase_esatta'. |
| `cerdef_leggi_provvedimento` | ricerca_online | smoke_live | nessuna (media) | CeRDEF, scheda di dettaglio del provvedimento | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) massima e testo della sentenza nota; (b) con un GUID inesistente il dettaglio vuoto produce oggi una risposta di successo con la sola intestazione vuota: deve diventare 'non trovato'. |
| `ultime_sentenze_tributarie` | ricerca_online | smoke_live | nessuna (bassa) | CeRDEF, ricerca avanzata ordinata per data | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: che il portale accetti una ricerca senza parole chiave; ordinamento per data effettivo; ritardo di pubblicazione rispetto al deposito. |

### `cerca_giurisprudenza_tributaria`

Ricerca di sentenze e provvedimenti tributari nella banca dati CeRDEF del Ministero dell'economia e delle finanze (def.finanze.it), con filtri per tipo, ente, numero, date, criterio e ordinamento.

- Parametri: `query: str; tipo_provvedimento: 'sentenza' \| 'ordinanza' \| 'decreto' \| '' = ''; ente: 'corte_suprema' \| 'cgt_primo_grado' \| 'cgt_secondo_grado' \| '' = ''; data_da: str = '' (GG/MM/AAAA); data_a: str = '' (GG/MM/AAAA); numero: str = ''; criterio: 'tutti' \| 'frase_esatta' \| 'almeno_uno' \| 'codice' = 'tutti'; ordinamento: 'rilevanza' \| 'data' = 'rilevanza'; max_risultati: int = 10 (max 250)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CeRDEF, banca dati della giurisprudenza tributaria (def.finanze.it)
- Casi di prova:
  - Sentenza nota delle Sezioni Unite: `{"query": "contraddittorio endoprocedimentale", "ente": "corte_suprema", "tipo_provvedimento": "sentenza", "data_da": "01/12/2015", "data_a": "31/12/2015", "max_risultati": 10}` → atteso: tra i risultati la sentenza della Cassazione a Sezioni Unite n. 24823 del 09/12/2015 (contraddittorio endoprocedimentale obbligatorio in via generale solo per i tributi armonizzati), con estremi, ente, data e GUID
  - Ricerca per numero: `{"query": "", "numero": "24823", "ente": "corte_suprema", "data_da": "01/01/2015", "data_a": "31/12/2015"}` → atteso: la stessa sentenza individuata dal solo numero

### `cerdef_leggi_provvedimento`

Massima e testo integrale di un provvedimento CeRDEF tramite GUID restituito dalla ricerca, troncato a 25000 caratteri.

- Parametri: `guid: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CeRDEF (def.finanze.it)
- Casi di prova:
  - Sentenza nota (GUID dalla ricerca): `{"guid": "<GUID restituito da cerca_giurisprudenza_tributaria per Cass. SS.UU. 24823/2015>"}` → atteso: estremi della sentenza 24823/2015 e sezioni Massima e Testo Integrale sul contraddittorio endoprocedimentale (obbligo generale solo per i tributi armonizzati, con prova di resistenza)
  - GUID inesistente (esempio del docstring): `{"guid": "abc-123-def-456"}` → atteso: segnalazione di provvedimento non trovato; con il codice attuale risposta di successo vuota, da correggere

### `ultime_sentenze_tributarie`

Ultime sentenze e provvedimenti tributari da CeRDEF in ordine di data, con filtri per ente e tipo.

- Parametri: `ente: str = '' (corte_suprema, cgt_primo_grado, cgt_secondo_grado); tipo_provvedimento: str = ''; max_risultati: int = 10 (max 250)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CeRDEF (def.finanze.it)
- Casi di prova:
  - Ultime sentenze di secondo grado: `{"ente": "cgt_secondo_grado", "tipo_provvedimento": "sentenza", "max_risultati": 5}` → atteso: da leggere dalla fonte: cinque sentenze di Corti di giustizia tributaria di secondo grado in ordine di data decrescente, ciascuna con GUID

## cgue.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_giurisprudenza_cgue` | ricerca_online | smoke_live | nessuna (alta) | Corte di giustizia UE, InfoCuria (curia.europa.eu) ed EUR-Lex per CELEX ed ECLI | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) la ricerca è una sottostringa del solo titolo italiano, non del testo; (b) più parole separate da virgola sono in OR e il parametro materia aggiunge altre parole in OR, quindi allarga la ricerca invece di restringerla, cosa che il docstring non dice; (c) il numero di causa è reso con l'anno a quattro cifre (C-311/2018) invece della forma ufficiale C-311/18; (d) compaiono solo le decisioni con titolo in italiano. |
| `giurisprudenza_cgue_su_norma` | ricerca_online | smoke_live | nessuna (media) | EUR-Lex, giurisprudenza per atto interpretato; InfoCuria | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il riferimento è cercato tale e quale come sottostringa del titolo (il commento nel codice promette una normalizzazione che non c'è): i titoli usano 'Articolo 101 TFUE', quindi 'art. 101 TFUE' rischia zero risultati. |
| `leggi_sentenza_cgue` | ricerca_online | smoke_live | nessuna (media) | EUR-Lex, testo italiano della sentenza CELEX 62018CJ0311; InfoCuria | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) l'intestazione della risposta è l'ultimo segmento dell'URI e l'ECLI resta vuoto, quindi la risposta non porta numero di causa né ECLI; (b) soglia di 200 caratteri per riconoscere una pagina vuota; (c) lingua italiana effettiva del testo restituito. |
| `ultime_sentenze_cgue` | ricerca_online | smoke_live | nessuna (media) | Corte di giustizia UE, calendario e ultime sentenze su curia.europa.eu | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: ritardo di CELLAR rispetto alla pronuncia; le decisioni ancora senza titolo italiano non compaiono (la query richiede l'espressione italiana); con materia l'elenco si limita ai titoli che contengono le parole della materia. |

### `cerca_giurisprudenza_cgue`

Ricerca di sentenze, ordinanze e conclusioni della Corte di giustizia dell'Unione europea e del Tribunale nei titoli italiani su CELLAR (interrogazione SPARQL), con filtri per corte, tipo, anni e materia.

- Parametri: `query: str (parole separate da virgola); corte: 'corte_di_giustizia' \| 'tribunale' \| '' = ''; tipo_documento: 'sentenza' \| 'ordinanza' \| 'conclusioni_ag' \| '' = ''; anno_da: str = ''; anno_a: str = ''; materia: 'iva' \| 'concorrenza' \| 'ambiente' \| 'lavoro' \| 'protezione_dati' \| 'appalti' \| 'consumatori' \| '' = ''; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR dell'Ufficio delle pubblicazioni dell'Unione europea (SPARQL)
- Casi di prova:
  - Sentenza nota: `{"query": "Schrems", "tipo_documento": "sentenza", "anno_da": "2020", "anno_a": "2020"}` → atteso: causa C-311/18 (resa come C-311/2018), CELEX 62018CJ0311, ECLI:EU:C:2020:559, data 2020-07-16, titolo con 'Data Protection Commissioner contro Facebook Ireland' e 'Schrems', CELLAR URI
  - Più parole separate da virgola: `{"query": "clausole abusive, ingiunzione", "corte": "corte_di_giustizia", "tipo_documento": "sentenza", "anno_da": "2022", "anno_a": "2022", "max_risultati": 50}` → atteso: comprende la causa C-693/19 SPV Project 1503 del 17/05/2022 (ECLI:EU:C:2022:395 da riscontrare); un numero di risultati non inferiore a quello della sola 'clausole abusive' conferma la semantica OR

### `giurisprudenza_cgue_su_norma`

Decisioni della Corte di giustizia e del Tribunale UE il cui titolo italiano contiene il riferimento normativo indicato (articolo dei Trattati, direttiva, regolamento).

- Parametri: `riferimento: str; corte: 'corte_di_giustizia' \| 'tribunale' \| '' = ''; anno_da: str = ''; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR (SPARQL)
- Casi di prova:
  - Direttiva IVA: `{"riferimento": "direttiva 2006/112", "corte": "corte_di_giustizia", "anno_da": "2025", "max_risultati": 5}` → atteso: decisioni dal 2025 con 'direttiva 2006/112/CE' nel titolo, in ordine di data decrescente, con CELEX, ECLI e CELLAR URI
  - Articolo del Trattato in forma abbreviata: `{"riferimento": "art. 101 TFUE", "anno_da": "2020"}` → atteso: da leggere dalla fonte: confrontare con il riferimento 'Articolo 101 TFUE'; se il primo dà zero risultati e il secondo no, il tool va corretto con la normalizzazione di 'art.'

### `leggi_sentenza_cgue`

Testo integrale in italiano di una decisione della Corte di giustizia UE tramite URI CELLAR (negoziazione del contenuto HTML), troncato a 25000 caratteri.

- Parametri: `cellar_uri: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR (publications.europa.eu)
- Casi di prova:
  - Sentenza nota tramite alias CELEX di CELLAR: `{"cellar_uri": "http://publications.europa.eu/resource/celex/62018CJ0311"}` → atteso: testo italiano della sentenza del 16 luglio 2020 (Grande Sezione), causa C-311/18, con dispositivo: invalidità della decisione di esecuzione (UE) 2016/1250 sullo scudo UE-USA per la privacy e validità della decisione 2010/87/UE sulle clausole contrattuali tipo; se CELLAR non risolve l'alias CELEX, ripetere con il CELLAR URI restituito da cerca_giurisprudenza_cgue

### `ultime_sentenze_cgue`

Ultime decisioni della Corte di giustizia e del Tribunale UE in ordine di data del documento, con filtri per corte, tipo e materia.

- Parametri: `corte: str = ''; tipo_documento: str = ''; materia: str = ''; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR (SPARQL)
- Casi di prova:
  - Ultime sentenze della Corte: `{"corte": "corte_di_giustizia", "tipo_documento": "sentenza", "max_risultati": 5}` → atteso: da leggere dalla fonte: cinque sentenze della Corte con CELEX di tipo CJ ed ECLI:EU:C:2026:..., date decrescenti non successive al giorno della prova; confronto con le ultime sentenze su curia.europa.eu per misurare il ritardo

## consob.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_delibere_consob` | ricerca_online | smoke_live | nessuna (media) | CONSOB, Bollettino, ricerca delle delibere su consob.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) formato delle date: il docstring chiede AAAA-MM-GG, il modulo del Bollettino potrebbe attendere GG/MM/AAAA; se il filtro è ignorato compaiono delibere fuori intervallo; (b) copertura storica del Bollettino online per il 2018; (c) validità degli ID Liferay fissi degli argomenti. |
| `leggi_delibera_consob` | ricerca_online | smoke_live | nessuna (media) | CONSOB, pagina della Delibera n. 20307 del 15 febbraio 2018 nel Bollettino | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) testo e titolo della delibera nota; (b) per un numero inesistente il parser ripiega sul corpo della pagina e può presentare il contenuto del portale come delibera: serve un riconoscimento esplicito del 'non trovato'; (c) troncamento a 8000 caratteri dichiarato. |
| `ultime_delibere_consob` | ricerca_online | smoke_live | nessuna (media) | CONSOB, Bollettino, ultime delibere pubblicate | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il tool non imposta alcun ordinamento e si affida all'ordine predefinito del Bollettino; verificare che sia per data decrescente. |

### `cerca_delibere_consob`

Ricerca di delibere e provvedimenti nel Bollettino della CONSOB (Commissione nazionale per le società e la borsa) per parole chiave, tipologia, argomento e date.

- Parametri: `query: str; tipologia: str = '' (delibere, comunicazioni, provvedimenti_urgenti, altre_decisioni, opa, appendice, tutti); argomento: str = '' (abusi_di_mercato, intermediari, emittenti, mercati, offerte_acquisto, offerte_vendita, gestione_collettiva, servizi_investimento, cripto_attivita, crowdfunding o ID Liferay); data_da: str = '' (AAAA-MM-GG); data_a: str = '' (AAAA-MM-GG); max_risultati: int = 20 (1-100)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CONSOB, Bollettino (consob.it)
- Casi di prova:
  - Delibera nota: `{"query": "regolamento intermediari", "tipologia": "delibere", "data_da": "2018-02-01", "data_a": "2018-02-28", "max_risultati": 20}` → atteso: tra i risultati la Delibera n. 20307 del 15/02/2018 (adozione del Regolamento Intermediari), con link https://www.consob.it/web/area-pubblica/-/delibera-n.-20307
  - Filtro argomento e date: `{"query": "abusi di mercato", "argomento": "abusi_di_mercato", "data_da": "2025-01-01", "data_a": "2025-12-31", "max_risultati": 5}` → atteso: solo delibere con data nel 2025; ogni data fuori intervallo indica che il filtro non è applicato

### `leggi_delibera_consob`

Testo integrale di una delibera CONSOB dal numero (pagina del Bollettino), troncato a 8000 caratteri.

- Parametri: `numero: str (es. '23257', '23256-1')`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CONSOB, Bollettino
- Casi di prova:
  - Delibera nota: `{"numero": "20307"}` → atteso: titolo della delibera n. 20307 del 15 febbraio 2018; testo con 'Regolamento recante norme di attuazione del decreto legislativo 24 febbraio 1998, n. 58 in materia di intermediari'; riga Link alla delibera
  - Numero inesistente: `{"numero": "99999"}` → atteso: segnalazione di delibera non trovata; se il tool restituisce testo del portale come se fosse una delibera, il difetto va corretto

### `ultime_delibere_consob`

Ultime delibere e provvedimenti pubblicati nel Bollettino CONSOB, con filtri per tipologia e argomento.

- Parametri: `tipologia: str = ''; argomento: str = ''; max_risultati: int = 10 (1-100)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CONSOB, Bollettino
- Casi di prova:
  - Ultime delibere: `{"tipologia": "delibere", "max_risultati": 5}` → atteso: da leggere dalla fonte: cinque delibere con numero, titolo e data, in ordine di data decrescente e coincidenti con le ultime pubblicate nel Bollettino

## corte_cost.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_pronuncia_costituzionale` | ricerca_online | smoke_live | nessuna (alta) | Corte costituzionale, scheda della pronuncia su cortecostituzionale.it e open data dati.cortecostituzionale.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: decodifica latin-1 (il termine accentato 'indennità' deve essere trovato); semantica AND dei termini; senza intervallo la ricerca copre solo il 2026 e il messaggio lo dice. |
| `leggi_pronuncia_costituzionale` | ricerca_online | smoke_live | nessuna (alta) | Corte costituzionale, sentenza n. 194 del 2018 su cortecostituzionale.it; Gazzetta Ufficiale, 1a Serie speciale | Assente dai paragrafi 5 e 7 come tool; serve a chiudere la voce indennita_licenziamento del paragrafo 7 (dopo Corte cost. 194/2018 nessun automatismo di due mensilità per anno di servizio). Da confermare: metadati (ECLI, date, presidente, relatore), dispositivo completo entro il troncamento a 25000 caratteri, decodifica degli accenti, messaggio per pronuncia inesistente. |
| `pronunce_cost_su_norma` | ricerca_online | smoke_live | nessuna (media) | Corte costituzionale, archivio delle massime su cortecostituzionale.it e dati.cortecostituzionale.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) copertura dell'archivio delle massime: il codice legge il file CC_M_2001_2015_json.zip e usa il 2015 come anno finale predefinito, quindi le massime successive non sono consultate; verificare se il portale ne pubblica di più recenti; (b) il parser estrae solo articolo e numero dell'atto: 'art. 3 Costituzione' corrisponde a qualunque parametro con articolo 3, anche di atti diversi dalla Costituzione. |
| `ultime_pronunce_cost` | ricerca_online | smoke_live | nessuna (media) | Corte costituzionale, ultime decisioni depositate su cortecostituzionale.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: ritardo del dump open data e della cache di 7 giorni rispetto al sito della Corte; a inizio anno il tool guarda solo l'anno corrente e può restituire zero. |

### `cerca_pronuncia_costituzionale`

Ricerca per parole chiave (in AND) in epigrafe, testo e dispositivo delle pronunce della Corte costituzionale, dal dump open data con cache locale di 7 giorni; senza anni cerca solo l'anno corrente.

- Parametri: `query: str (termini separati da virgola, in AND); tipo: 'sentenza' \| 'ordinanza' \| '' = ''; anno_da: int = 0; anno_a: int = 0; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: open data della Corte costituzionale (dati.cortecostituzionale.it)
- Casi di prova:
  - Pronuncia nota: `{"query": "licenziamento, indennità", "tipo": "sentenza", "anno_da": 2018, "anno_a": 2018}` → atteso: include la Sentenza n. 194/2018, ECLI:IT:COST:2018:194, decisione 26/09/2018, deposito 08/11/2018
  - Senza intervallo di anni: `{"query": "licenziamento"}` → atteso: ricerca limitata all'anno corrente (2026): pronunce del 2026 oppure messaggio che invita a indicare anno_da e anno_a

### `leggi_pronuncia_costituzionale`

Testo di una pronuncia della Corte costituzionale (epigrafe, testo, dispositivo e metadati) da numero e anno, dal dump open data; troncato a 25000 caratteri.

- Parametri: `numero: int; anno: int`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: open data della Corte costituzionale
- Casi di prova:
  - Sentenza nota: `{"numero": 194, "anno": 2018}` → atteso: Sentenza n. 194/2018, ECLI:IT:COST:2018:194, decisione 26/09/2018, deposito 08/11/2018, presidente Lattanzi, relatore Sciarra; dispositivo: illegittimità dell'art. 3 co. 1 D.Lgs. 23/2015 limitatamente alle parole 'di importo pari a due mensilità dell'ultima retribuzione di riferimento per il calcolo del trattamento di fine rapporto per ogni anno di servizio'
  - Prima pronuncia della Corte: `{"numero": 1, "anno": 1956}` → atteso: ECLI:IT:COST:1956:1, tipo sentenza, testo oltre 100 caratteri (caso del test live esistente)
  - Pronuncia inesistente: `{"numero": 9999, "anno": 2018}` → atteso: messaggio 'Pronuncia n. 9999/2018 non trovata', nessun testo

### `pronunce_cost_su_norma`

Pronunce costituzionali le cui massime invocano come parametro una norma (articolo e numero dell'atto), dall'archivio open data delle massime.

- Parametri: `riferimento: str; anno_da: int = 0; anno_a: int = 0; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: open data della Corte costituzionale, archivio delle massime
- Casi di prova:
  - Parametro noto nel 1956: `{"riferimento": "art. 23 legge 87/1953", "anno_da": 1956, "anno_a": 1956}` → atteso: almeno una massima di pronuncia del 1956 con parametro art. 23 L. 87/1953 (caso del test live esistente)
  - Anno successivo al 2015: `{"riferimento": "art. 3 Costituzione", "anno_da": 2018, "anno_a": 2018}` → atteso: da leggere dalla fonte: con l'archivio fermo al 2015 il tool restituisce zero; se il portale pubblica massime del 2018, il limite va rimosso

### `ultime_pronunce_cost`

Ultime pronunce depositate dalla Corte costituzionale nell'anno corrente, in ordine di data di deposito, dal dump open data.

- Parametri: `tipo: 'sentenza' \| 'ordinanza' \| '' = ''; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: open data della Corte costituzionale
- Casi di prova:
  - Ultime sentenze: `{"tipo": "sentenza", "max_risultati": 5}` → atteso: intestazione con l'anno 2026; cinque sentenze con ECLI:IT:COST:2026:N e date di deposito decrescenti; da leggere dalla fonte il divario con l'ultima sentenza pubblicata dalla Corte

## crisi_impresa.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `compenso_occ` | calcolo | solo_norma | https://www.avvocatoandreani.it/servizi/calcolo-compenso-curatore-fallimentare.php (bassa) | Gazzetta Ufficiale o Normattiva: DM Giustizia 24 settembre 2014 n. 202, art. 16 (determinazione dei compensi degli organismi); DM Giustizia 25 gennaio 2012 n. 30 (compensi del curatore) per i parametri richiamati | Declassato dall'audit a INDICATIVO (par. 7, confidenza media): gli scaglioni del tool non sono quelli del DM 202/2014. Il benchmark deve leggere l'art. 16 DM 202/2014 e ricostruire il compenso: secondo il docstring il decreto rinvia ai parametri del curatore (DM 30/2012, percentuali minime e massime su attivo realizzato e passivo accertato) con riduzioni; la pagina del sito sul compenso del curatore (titolo nei risultati: Calcolo Compenso Curatore Fallimentare) serve a calcolare quella base, alla quale applicare a mano le riduzioni del decreto. Da segnalare: il tool usa il solo passivo e ignora l'attivo; i minimi di 1.500 e 2.000 euro non hanno fonte indicata (per il curatore il DM 30/2012 fissa un minimo di 811,35 euro); il riferimento 'art. 15 co. 9 D.Lgs. 14/2019' va riscontrato (il rinvio al regolamento sui compensi degli OCC stava nell'art. 15 L. 3/2012); il docstring affida all'OCC la composizione negoziata, che è condotta dall'esperto con un compenso proprio (art. 25-ter CCII); aliquota_pct mostra 7.000000000000001 per un artefatto di virgola mobile. |
| `composizione_negoziata` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 2, 12, 17, 18, 20, 22, 24, 25-quater e 25-quinquies D.Lgs. 14/2019; decreto dirigenziale del Ministero della giustizia con la lista di controllo e il test pratico (art. 13 co. 2 CCII) | Corretto dall'audit (par. 5): per l'impresa minore i requisiti dell'art. 2 co. 1 lett. d) sono congiunti. Il benchmark (cite_law) deve confermare le soglie di 300.000 euro di attivo, 200.000 di ricavi e 500.000 di debiti ('non superiore', riferite ai tre esercizi precedenti, che il tool non chiede) e la durata di 180 giorni prorogabili di altri 180 (art. 17). Da segnalare: l'art. 25-quater riguarda le imprese sotto soglia, mentre il tool lo attribuisce alle imprese agricole, che accedono ex art. 12 co. 1 (imprenditore commerciale e agricolo); il messaggio 'nessuna soglia rispettata' quando ne manca una sola; il criterio debito/fatturato inferiore a 2 non ha base normativa (il test pratico del decreto dirigenziale rapporta il debito da ristrutturare ai flussi annui liberi al suo servizio); ammissibile è sempre vero per commerciale e agricola senza la condizione di squilibrio che rende probabile la crisi o l'insolvenza con risanamento ragionevolmente perseguibile (art. 12 co. 1) né le cause ostative dell'art. 25-quinquies; il numero di dipendenti non è usato. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `concordato_preventivo` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 84, 85, 109 e 112 D.Lgs. 14/2019 nel testo vigente dopo i correttivi D.Lgs. 83/2022 e D.Lgs. 136/2024 | Non citato ai par. 5 e 7. Il benchmark (cite_law) deve confermare nel concordato liquidatorio la soglia del 20% e l'apporto di risorse esterne che incrementi di almeno il 10% il soddisfacimento rispetto alla liquidazione giudiziale (art. 84 co. 4), e l'assenza di soglia nel concordato in continuità. Da segnalare: il 20% si misura sul complesso dei chirografari e dei privilegiati degradati per incapienza, non sui soli chirografari; il pagamento non integrale dei privilegiati è ammesso nei limiti del valore di realizzo attestato (art. 84 co. 5) e la parte incapiente è trattata come chirografaria, senza una 'degradazione consensuale ex art. 109'; nel concordato in continuità le classi sono obbligatorie (art. 85) e l'approvazione richiede il voto favorevole di tutte le classi salvo ristrutturazione trasversale (artt. 109 e 112), mentre voto_requisito ipotizza l'assenza di classi; nessun controllo su importi negativi. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `test_crisi_impresa` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 3 e 25-novies D.Lgs. 14/2019 nel testo vigente | Declassato dall'audit a INDICATIVO (par. 7, confidenza media): l'art. 3 co. 3 CCII chiede di verificare la sostenibilità dei debiti per almeno i dodici mesi successivi. Il benchmark (cite_law) deve mettere a confronto gli indicatori del tool con i segnali dell'art. 3 co. 4: debiti per retribuzioni scaduti da almeno 30 giorni oltre la metà del monte mensile, debiti verso fornitori scaduti da almeno 90 giorni superiori ai non scaduti, esposizioni bancarie scadute da oltre 60 giorni pari ad almeno il 5% del totale, esposizioni verso i creditori pubblici qualificati dell'art. 25-novies (soglie di importo per INPS, INAIL, Agenzia delle Entrate e Agenzia delle Entrate-Riscossione). Da segnalare: soglia del 5% inclusiva ('almeno') mentre il tool usa 'oltre'; ritardi INPS e Agenzia delle Entrate senza le soglie di importo; DSCR a sei mesi e debiti/attivo all'80% senza base nel testo vigente (derivano dagli indicatori della versione originaria, sostituita dal D.Lgs. 83/2022); mancano retribuzioni e fornitori; i livelli di severità sono prassi. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |

### `compenso_occ`

Stima del compenso dell'organismo di composizione della crisi per scaglioni progressivi sul passivo (ristrutturazione 5, 3, 1%; liquidazione 7, 4, 2%) con minimo di 1.500 o 2.000 euro; scaglioni semplificati, non tratti dal decreto.

- Parametri: `passivo: float (euro, >= 0); tipo: str = 'ristrutturazione' (ristrutturazione, liquidazione)`
- Fonte normativa dichiarata: DM 202/2014 (art. 16, compensi degli OCC); il tool cita l'art. 15 co. 9 D.Lgs. 14/2019 (INDICATIVO)
- Casi di prova:
  - Passivo 100.000, ristrutturazione: fine del primo scaglione: `{"passivo": 100000}` → atteso: da leggere dalla fonte (art. 16 DM 202/2014); il tool dà 5.000 euro (5%)
  - Passivo 100.000,01: inizio del secondo scaglione: `{"passivo": 100000.01}` → atteso: da leggere dalla fonte; il tool dà 5.000,00 euro: controllo di continuità sul confine
  - Passivo 500.000, liquidazione: `{"passivo": 500000, "tipo": "liquidazione"}` → atteso: da leggere dalla fonte, considerando anche l'attivo realizzato che il tool non chiede; il tool dà 23.000 euro (7% su 100.000 più 4% su 400.000)
  - Passivo 20.000, ristrutturazione: minimo: `{"passivo": 20000}` → atteso: da leggere dalla fonte; il tool applica il minimo di 1.500 euro (calcolo 1.000)
  - Passivo 1.000.000, ristrutturazione: terzo scaglione: `{"passivo": 1000000}` → atteso: da leggere dalla fonte; il tool dà 22.000 euro (5.000 + 12.000 + 5.000)

### `composizione_negoziata`

Verifica orientativa dell'accesso alla composizione negoziata della crisi per impresa commerciale, agricola o sotto soglia, con rapporti debito/fatturato e debito/attivo, durata dell'incarico dell'esperto e misure protettive.

- Parametri: `fatturato: float (>= 0); attivo: float (>= 0); dipendenti: int (>= 0); debito_totale: float (>= 0); tipo_impresa: str = 'commerciale' (commerciale, agricola, sotto_soglia)`
- Fonte normativa dichiarata: Artt. 12-25-undecies D.Lgs. 14/2019 (CCII) come modificato dal D.Lgs. 83/2022; art. 2 co. 1 lett. d) per l'impresa minore
- Casi di prova:
  - Impresa sotto soglia con i tre valori pari ai limiti: `{"fatturato": 200000, "attivo": 300000, "dipendenti": 3, "debito_totale": 500000, "tipo_impresa": "sotto_soglia"}` → atteso: impresa minore: i tre requisiti 'non superiore' sono rispettati (art. 2 co. 1 lett. d), accesso ex art. 25-quater
  - Ricavi appena sopra 200.000: `{"fatturato": 200000.01, "attivo": 100000, "dipendenti": 3, "debito_totale": 100000, "tipo_impresa": "sotto_soglia"}` → atteso: non è impresa minore (manca il requisito dei ricavi): accesso ordinario ex art. 12; il tool risponde 'nessuna soglia rispettata' mentre due sono rispettate
  - Impresa agricola: `{"fatturato": 500000, "attivo": 800000, "dipendenti": 10, "debito_totale": 300000, "tipo_impresa": "agricola"}` → atteso: accesso ex art. 12 co. 1 (imprenditore commerciale e agricolo); il tool cita l'art. 25-quater, che riguarda le imprese sotto soglia
  - Debito pari al doppio del fatturato: `{"fatturato": 500000, "attivo": 800000, "dipendenti": 10, "debito_totale": 1000000, "tipo_impresa": "commerciale"}` → atteso: nessuna soglia di legge sul rapporto debito/fatturato: la ragionevole perseguibilità del risanamento si valuta con il test pratico (debito da ristrutturare rispetto ai flussi annui liberi); il tool segna risanamento difficile al rapporto 2
  - Tipo di impresa non gestito: `{"fatturato": 500000, "attivo": 800000, "dipendenti": 10, "debito_totale": 300000, "tipo_impresa": "artigiana"}` → atteso: errore: tipi ammessi commerciale, agricola, sotto_soglia

### `concordato_preventivo`

Verifica orientativa della proposta di concordato preventivo in continuità o liquidatorio: somme offerte a privilegiati e chirografari, soglia del 20% nel liquidatorio, requisiti di voto.

- Parametri: `creditori_privilegiati: float; creditori_chirografari: float; proposta_pct_chirografari: float (0-100); proposta_pct_privilegiati: float = 100.0 (0-100); tipo: str = 'continuita' (continuita, liquidatorio)`
- Fonte normativa dichiarata: Artt. 84-120 D.Lgs. 14/2019 (CCII)
- Casi di prova:
  - Liquidatorio al 20% esatto: `{"creditori_privilegiati": 200000, "creditori_chirografari": 500000, "proposta_pct_chirografari": 20, "tipo": "liquidatorio"}` → atteso: soglia raggiunta (non inferiore al 20%, art. 84 co. 4): 100.000 euro ai chirografari, 300.000 in totale; ammissibile solo con l'apporto esterno di almeno il 10%
  - Liquidatorio al 19,99%: `{"creditori_privilegiati": 200000, "creditori_chirografari": 500000, "proposta_pct_chirografari": 19.99, "tipo": "liquidatorio"}` → atteso: non ammissibile: sotto il 20% (art. 84 co. 4)
  - Continuità al 5%: `{"creditori_privilegiati": 200000, "creditori_chirografari": 500000, "proposta_pct_chirografari": 5, "tipo": "continuita"}` → atteso: nessuna soglia minima (art. 84 co. 2 e 3); classi obbligatorie (art. 85) e approvazione di tutte le classi o ristrutturazione trasversale (artt. 109 e 112); il tool dà ammissibile e un voto a maggioranza senza classi
  - Liquidatorio con privilegiati al 70% e chirografari al 21%: `{"creditori_privilegiati": 200000, "creditori_chirografari": 500000, "proposta_pct_chirografari": 21, "proposta_pct_privilegiati": 70, "tipo": "liquidatorio"}` → atteso: i 60.000 euro incapienti dei privilegiati si sommano ai chirografari: se ricevono anch'essi il 21% la soglia è rispettata (117.600 su 560.000), se non ricevono nulla il soddisfacimento è 105.000 su 560.000, cioè 18,75%, sotto il 20% (art. 84 co. 4 e 5); il tool considera i soli chirografari e dichiara ammissibile
  - Tipo non gestito: `{"creditori_privilegiati": 200000, "creditori_chirografari": 500000, "proposta_pct_chirografari": 25, "tipo": "misto"}` → atteso: errore: tipi ammessi continuita e liquidatorio

### `test_crisi_impresa`

Controllo semplificato di cinque indicatori di crisi (DSCR a sei mesi sotto 1, ritardi INPS e Agenzia delle Entrate oltre 90 giorni, esposizioni bancarie scadute oltre il 5%, debiti oltre l'80% dell'attivo) con livello di severità e raccomandazione.

- Parametri: `dscr: float (>= 0); giorni_ritardo_inps: int = 0; giorni_ritardo_ade: int = 0; esposizioni_scadute_pct: float = 0.0 (0-100); debiti_vs_attivo_pct: float = 0.0`
- Fonte normativa dichiarata: Art. 3 D.Lgs. 14/2019 (CCII) come modificato dal D.Lgs. 83/2022 (INDICATIVO)
- Casi di prova:
  - DSCR pari a 1: `{"dscr": 1.0}` → atteso: nessun segnale dell'art. 3 co. 4 desumibile; il DSCR non è un parametro del testo vigente (art. 3 co. 3 lett. b: sostenibilità dei debiti a dodici mesi)
  - Esposizioni bancarie scadute al 5% esatto: `{"dscr": 1.2, "esposizioni_scadute_pct": 5.0}` → atteso: segnale presente se scadute da oltre 60 giorni: almeno il 5% del totale delle esposizioni (art. 3 co. 4 lett. c); il tool non lo attiva perché richiede oltre il 5%
  - Ritardo INPS di 91 giorni senza importo: `{"dscr": 1.2, "giorni_ritardo_inps": 91}` → atteso: segnale solo se il ritardo oltre 90 giorni riguarda contributi superiori al 30% di quelli dovuti nell'anno precedente e a 15.000 euro (5.000 senza lavoratori dipendenti), art. 25-novies co. 1 lett. a: non determinabile con i soli giorni
  - Ritardo verso l'Agenzia delle Entrate di 120 giorni: `{"dscr": 1.2, "giorni_ritardo_ade": 120}` → atteso: per l'Agenzia delle Entrate il segnale dipende dall'importo del debito IVA scaduto e non versato, non dai giorni (art. 25-novies co. 1 lett. c); per l'agente della riscossione dai crediti affidati scaduti da oltre 90 giorni sopra soglia (lett. d): da riscontrare
  - Tutti gli indicatori del tool attivi: `{"dscr": 0.8, "giorni_ritardo_inps": 100, "giorni_ritardo_ade": 100, "esposizioni_scadute_pct": 6, "debiti_vs_attivo_pct": 85}` → atteso: almeno il segnale bancario (art. 3 co. 4 lett. c); il livello 'critico' e la raccomandazione sono prassi senza base normativa

## dichiarazione_redditi.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `acconto_cedolare_secca` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-acconto-cedolare-secca.php (alta) | Agenzia delle Entrate, istruzioni Redditi PF 2026, quadro LC (cedolare secca, acconti) | Audit settembre 2026: non toccato. Il benchmark deve confermare la misura dell'acconto al 100% e le stesse soglie dell'IRPEF (51,65 e 257,52) con ripartizione 40% e 60%. Il sito mostra anche i codici tributo del versamento: utile riscontro per cerca_codice_tributo (per la cedolare l'Agenzia indica 1840, 1841, 1842). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `acconto_irpef` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-acconto-irpef.php (alta) | Agenzia delle Entrate, istruzioni Redditi PF 2026 (acconti IRPEF, rigo RN34 e seguenti) | Audit settembre 2026: non toccato; il triage di giugno 2026 aveva confermato la soglia di 257,52 euro per il versamento unico. Il benchmark deve confermare le soglie (51,65 senza acconto; fino a 257,52 unica soluzione a novembre; oltre, 40% e 60%) e gli arrotondamenti al centesimo. Il tool non gestisce la ripartizione 50% e 50% dei soggetti ISA (art. 58 DL 124/2019) né eventuali clausole delle leggi di bilancio che impongono di ricalcolare l'imposta dell'anno precedente con le regole previgenti ai fini del metodo storico: il valore passato dal chiamante va quindi controllato a monte. Il metodo previsionale restituisce gli stessi importi dello storico con una nota. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `assegno_unico` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-assegno-unico-universale.php (alta) | INPS, circolare annuale sugli importi dell'Assegno unico 2026 e simulatore INPS dell'Assegno unico | Audit settembre 2026: non modificato; compare nel paragrafo 7 (importi annuali incorporati senza _vintage; ISEE nullo trattato come massimo; confidenza media; candidato a tabella con vintage). Il benchmark deve confermare: (1) gli importi 2026 (soglie e importi minimo e massimo) sulla circolare INPS; (2) che senza ISEE spetti l'importo minimo, non il massimo; (3) le maggiorazioni, che nel tool sono fisse (96,90 per i figli sotto un anno, 34,10 per 1-3 anni) mentre la legge (L. 197/2022) le fissa al 50% dell'importo; (4) l'importo ridotto per i figli maggiorenni fino a 21 anni, che il tool non distingue; (5) le maggiorazioni assenti nel tool (figli successivi al secondo, forfait per quattro o più figli, madre under 21, entrambi i genitori lavoratori, disabilità); (6) la maggiorazione del 30% per genitore solo, che non risulta nel D.Lgs. 230/2021. Verificare anche se l'INPS applica la tabella 1 allegata al decreto a fasce di ISEE invece dell'interpolazione lineare continua del tool. Il docstring cita un 'DPCM 16/02/2023' da riscontrare. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_irpef` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-irpef.php (alta) | Agenzia delle Entrate, istruzioni modello Redditi PF 2026 e 730/2026 (calcolo dell'imposta e tabelle delle detrazioni); testo vigente degli artt. 11 e 13 TUIR e dell'art. 1, commi 4-9, L. 207/2024 via cite_law | Audit settembre 2026: non corretto; compare nel paragrafo 7 (riga 'calcolo_irpef e detrazioni', confidenza media, non modificato, da riscontrare sul TUIR vigente). Il benchmark deve confermare: (1) imposta lorda per anno, impostando sul sito lo stesso anno d'imposta del tool (la pagina 'Modello REDDITI e 730' 2026 riguarda i redditi 2025, quindi 35%: passare anno_fiscale 2025; il test esistente tests/comparison/test_irpef.py è saltato per questo motivo e va riattivato così, non lasciato in skip); (2) le detrazioni, che il tool calcola in modo incompleto: manca la maggiorazione di 65 euro tra 25.000 e 35.000 (art. 13 co. 1.1), quella di 50 euro per le pensioni tra 25.000 e 29.000, la detrazione per lavoro autonomo dell'art. 13 co. 5 (per 'autonomo' il tool applica zero), l'ulteriore detrazione di 1.000 euro tra 20.000 e 32.000 euro dell'art. 1 L. 207/2024, il troncamento del coefficiente alla quarta cifra decimale; (3) la base delle detrazioni: il tool usa il reddito al netto degli oneri deducibili invece del reddito complessivo; (4) un anno assente dalla tabella (per esempio 2023, a quattro scaglioni) ricade in silenzio sugli scaglioni 2026. Da verificare anche la riduzione di 440 euro delle detrazioni per redditi oltre 200.000 euro che la L. 199/2025 avrebbe introdotto a compensazione del 33%. Le addizionali sono medie nazionali e non vanno confrontate. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_tfr` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-tfr.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php | ISTAT, coefficienti di rivalutazione del TFR (anche https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php); art. 2120 c.c. e art. 19 TUIR via cite_law | Audit settembre 2026: non toccato (il paragrafo 7 cita solo rivalutazione_tfr, altro tool, per l'imposta sostitutiva 11% prima del 2015). Il sito chiede date di inizio e fine rapporto, retribuzione anno per anno e usa gli indici ISTAT reali e la clausola di salvaguardia sulle aliquote 2006: il confronto è possibile solo su casi semplici. Il benchmark deve confermare: (1) la quota annua, che per legge è ridotta del contributo dello 0,50% (art. 3 L. 297/1982), non sottratto dal tool; (2) la rivalutazione al netto dell'imposta sostitutiva del 17% (art. 11 co. 3 D.Lgs. 47/2000, mod. L. 190/2014), ignorata dal tool; (3) la tassazione separata dell'art. 19 TUIR, che il tool applica anche alle rivalutazioni già tassate (il docstring parla di aliquota media degli ultimi cinque anni, mentre il codice usa correttamente il reddito di riferimento moltiplicato per 12 e diviso per gli anni). Esiste solo un test aritmetico (tests/comparison/test_acconti.py) senza confronto col sito. Fase 0: pagina confermata. |
| `cerca_codice_tributo` | utilita | fonte_ufficiale | nessuna pagina del sito | Agenzia delle Entrate, 'Tabella codici tributo erariali e regionali' (https://www.agenziaentrate.gov.it/portale/strumenti/codici-attivita-e-tributo/f24-codici-tributo-per-i-versamenti/tabelle-dei-codici-tributo-e-altri-codici-per-il-modello-f24/tabella-codici-tributo-erariali-e-regionali), tabelle dei codici per enti locali (IMU, TARI) e per il modello F24 ELIDE (registro delle locazioni) | Audit settembre 2026: non toccato. Il sito non ha una ricerca dei codici tributo (la ricerca restituisce solo i codici catastali dei comuni); le sue pagine di acconti, ravvedimento e rateizzazione mostrano però i codici da usare e servono da riscontro secondario. Il confronto riga per riga con la tabella AdE deve confermare almeno questi errori del file dati: 1840, 1841 e 1842 sono i codici della cedolare secca (acconto prima rata, acconto seconda rata o unica soluzione, saldo), non del forfettario; il forfettario usa 1790, 1791 e 1792; i codici 1550, 1551 e 1552 attribuiti alla cedolare non risultano al revisore; 3843 è l'acconto e 3844 il saldo dell'addizionale comunale in autotassazione (il file li inverte); manca il 1668 (interessi della rateizzazione), che il sito indica; i codici 1630, 1631 e 1632 (contributo unificato, diritti di copia, marca da bollo) vanno riscontrati. Dopo la correzione aggiornare il blocco _vintage della tabella. |
| `detrazione_altri_familiari` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-familiari-a-carico.php (alta) | Agenzia delle Entrate, istruzioni 730/2026 (altri familiari a carico); art. 12 co. 1 lett. d) TUIR vigente via cite_law | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). Il benchmark deve confermare la formula e il coefficiente a quattro decimali. Dal 2025 la detrazione spetta solo per gli ascendenti conviventi (art. 12 come modificato dalla L. 207/2024) e non per i familiari residenti all'estero non cittadini UE: il docstring elenca ancora fratelli, sorelle, nipoti e gli altri soggetti dell'art. 433 c.c. e va aggiornato. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `detrazione_assegno_coniuge` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-assegno-coniuge.php (alta) | Testo vigente dell'art. 13 co. 5 e 5-bis TUIR via cite_law; Agenzia delle Entrate, istruzioni 730/2026 | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). Il tool applica gli importi del co. 5 (1.265; 500 + 765; 500), cioè quelli previsti per lavoro autonomo e altri redditi. Il revisore non riesce a confermare offline che il co. 5-bis, nel testo successivo alla L. 234/2021, rinvii a quegli importi: nel testo anteriore gli assegni avevano importi propri. Il benchmark deve leggere il co. 5-bis con cite_law e confrontare il sito; se il rinvio è al co. 5, verificare anche la maggiorazione di 50 euro tra 11.000 e 17.000 (co. 5.1) e il coefficiente a quattro decimali. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `detrazione_canone_locazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-canone-locazione.php (alta) | Agenzia delle Entrate, istruzioni 730/2026, quadro E sezione V (detrazioni per canoni di locazione); art. 16 TUIR via cite_law | Audit settembre 2026: non modificato; compare nel paragrafo 7 (riga con cedolare_secca e imposta_registro_locazioni: 'under 31 al 20% del canone', confidenza media, da riscontrare). Il benchmark deve confermare le soglie 15.493,71 e 30.987,41 e gli importi 300/150 e 495,80/247,90; per i giovani tra 20 e 31 anni (art. 16 co. 1-ter, mod. L. 178/2020) la detrazione è 991,60 oppure, se maggiore, il 20% del canone entro 2.000 euro, per i primi quattro anni: il tool restituisce sempre 2.000 senza chiedere il canone. Mancano anche la detrazione per i lavoratori che trasferiscono la residenza (co. 1-bis) e il rapporto al periodo di locazione. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `detrazione_coniuge` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-coniuge-a-carico.php (alta) | Agenzia delle Entrate, istruzioni 730/2026 (detrazione per coniuge a carico); art. 12 co. 1 lett. a) TUIR via cite_law | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). Il benchmark deve confermare le maggiorazioni dell'art. 12 co. 1 lett. a) che il tool non applica: 10 euro tra 29.000 e 29.200, 20 tra 29.200 e 34.700, 30 tra 34.700 e 35.000, 20 tra 35.000 e 35.100, 10 tra 35.100 e 35.200. Il docstring e il campo limite_reddito_coniuge_under24 attribuiscono al coniuge il limite di 4.000 euro, che la L. 205/2017 riserva ai figli fino a 24 anni: errore descrittivo fissato anche da tests/unit/test_dichiarazione_redditi.py. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `detrazione_figli` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-21-anni.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-a-carico.php | Agenzia delle Entrate, istruzioni 730/2026 e Redditi PF 2026 (detrazioni per familiari a carico); art. 12 TUIR vigente via cite_law | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). La ricerca restituisce anche https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-a-carico.php con lo stesso titolo: usare quella che distingue i figli dai 21 anni. Il benchmark deve confermare la soglia incrementata (confermata dal triage di giugno 2026), la maggiorazione di 400 euro per disabilità, il coefficiente troncato alla quarta cifra decimale (il tool usa la precisione piena: differenze di centesimi) e, dal 2025, l'esclusione dei figli di 30 anni o più non disabili (art. 12 come modificato dalla L. 207/2024), che il tool non può verificare perché non riceve l'età. Il test tests/comparison/test_detrazioni.py::test_reddito_30k_2figli attende ancora la soglia di 95.000 con due figli (650,00 per figlio): è in contrasto con l'art. 12 e con il codice e va corretto. Fase 0: pagina confermata; il sito ha anche la pagina generale dei figli a carico. |
| `detrazione_lavoro_dipendente` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-lavoro-dipendente.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-redditi-assimilati.php | Agenzia delle Entrate, istruzioni 730/2026 (detrazioni per redditi di lavoro dipendente); art. 13 TUIR vigente via cite_law | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). La pagina trovata ha titolo 'Calcolo Detrazione Redditi da Lavoro Dipendente 2026' ma indirizzo 'altri-redditi-assimilati': verificare col browser che calcoli l'art. 13 co. 1 e non il co. 5. Il benchmark deve confermare: la maggiorazione di 65 euro tra 25.000 e 35.000 (co. 1.1, assente nel tool); i minimi di 690 euro (1.380 per il tempo determinato) sulla detrazione rapportata ai giorni per redditi fino a 15.000 (assenti); il salto voluto dalla legge da 1.955 a circa 3.100 euro appena sopra 15.000 (il tool lo riproduce correttamente); il coefficiente a quattro decimali (art. 13 co. 6). L'importo di 1.955 deriva dal D.Lgs. 216/2023 e dalla L. 207/2024, non dalla L. 199/2025 citata nel docstring. L'ulteriore detrazione dell'art. 1 L. 207/2024 (1.000 euro tra 20.000 e 32.000) non è parte dell'art. 13 e non è calcolata da nessun tool. Fase 0: la pagina dedicata ai redditi di lavoro dipendente esiste; quella dei redditi assimilati e' distinta. |
| `detrazione_pensione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-pensione.php (alta) | Agenzia delle Entrate, istruzioni 730/2026 (detrazioni per redditi di pensione); art. 13 co. 3 TUIR via cite_law | Audit settembre 2026: non modificato; rientra nella riga 'calcolo_irpef e detrazioni' del paragrafo 7 (maggiorazioni e minimi delle detrazioni, figli oltre 30 anni, familiari a carico dal 2025; confidenza media; da riscontrare sul TUIR vigente). Il benchmark deve confermare la maggiorazione di 50 euro per redditi tra 25.000 e 29.000 (introdotta dalla L. 234/2021, assente nel tool), il minimo di 713 euro sulla detrazione rapportata ai giorni per redditi fino a 8.500 (assente) e il coefficiente a quattro decimali. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rateizzazione_imposte` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-rateizzazione-imposte-irpef.php (alta) | Agenzia delle Entrate, istruzioni Redditi PF 2026, paragrafo sulla rateizzazione con la tabella delle percentuali di interesse per rata (0,33% al mese per i non titolari di partita IVA); codice tributo 1668 per gli interessi | Audit settembre 2026: non toccato; il triage di giugno 2026 aveva confermato il tasso del 4%. Il benchmark deve confermare due scostamenti evidenti dal codice: (1) gli interessi, che per legge maturano su ciascuna rata dal termine della prima rata alla scadenza della rata stessa (0,33% per mese), mentre il tool li calcola sul debito residuo per il numero di mesi e li sovrastima (13,34 invece di 9,90 su 3.000 euro in tre rate; 186,66 invece di 69,30 su 7.000 in sette rate); (2) le date, che il tool sposta al giorno 28 di ogni mese a partire dalla prima rata (30/06 diventa 28/06), mentre le rate scadono alla fine di ciascun mese per i non titolari di partita IVA e il 16 per i titolari. Mancano la distinzione tra titolari e non titolari di partita IVA e la maggiorazione dello 0,40% per il differimento a luglio. Verificare il numero massimo di rate dopo il D.Lgs. 1/2024 (rate fino a dicembre). tests/unit/test_dichiarazione_redditi.py fissa le date al giorno 15 senza verificarne la correttezza. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `ravvedimento_operoso` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-ravvedimento-operoso.php (alta) ; secondarie: https://www.avvocatoandreani.it/utility/calcolo-ravvedimento-operoso.php | Testo vigente dell'art. 13 D.Lgs. 472/1997 e dell'art. 13 D.Lgs. 471/1997 via cite_law; Agenzia delle Entrate, scheda 'Ravvedimento operoso'; DM MEF sul tasso legale (1,6% dal 01/01/2026) | Audit settembre 2026: DECLASSATO a INDICATIVO (paragrafo 7: violazioni anteriori al 01/09/2024 con base 30% non gestite; riduzione a 1/6 da verificare, confidenza media). Il calcolatore del sito richiede un account (tests/comparison/test_ravvedimento.py è saltato per il login): senza credenziali si ripiega sulla norma. Il sito lavora su date, il tool su giorni: usare le date indicate nei casi. Il benchmark deve confermare: (1) le riduzioni 1/10, 1/9, 1/8 e 1/7 sulla sanzione del 25% (12,5% entro 90 giorni, 1/15 per giorno entro 15 giorni); (2) che oltre i due anni, in assenza di schema d'atto o di processo verbale, resti 1/7 e non 1/6 come fa il tool; (3) che la soglia del ravvedimento 'lungo' dipenda dal termine della dichiarazione e non da 365 giorni fissi; (4) gli interessi al tasso legale di ciascun anno (il tool applica l'ultimo tasso a tutto il periodo); (5) il trattamento della dichiarazione tardiva, che il tool calcola come percentuale dell'imposta. Fase 0: pagina confermata (calcolatore 2026); duplicato interno sotto /utility/. |
| `regime_forfettario` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-imposta-regime-forfettario.php (alta) | Agenzia delle Entrate, istruzioni quadro LM del modello Redditi PF 2026 e allegato 4 alla L. 190/2014 (coefficienti di redditività) | Audit settembre 2026: non toccato (paragrafi 5 e 7 non lo citano); il triage di giugno 2026 aveva confermato i coefficienti 40/54/62/67/78/86. Il benchmark deve confermare imposta sostitutiva e reddito imponibile per più coefficienti, il confine dei ricavi a 85.000 euro e il passaggio dal 5% al 15% dopo il quinto anno. Sul sito azzerare o allineare i contributi (il sito può calcolarli da sé, il tool li riceve come dato) e ignorare l'IVA che il sito applica al regime ordinario. La soglia di 85.000 euro e la cessazione immediata oltre 100.000 derivano dalla L. 197/2022, non citata nel docstring; il tool non distingue i due casi. Il confronto con l'ordinario è solo indicativo (nessuna detrazione dell'art. 13 co. 5). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |

### `acconto_cedolare_secca`

Calcola primo e secondo acconto della cedolare secca (100% dell'imposta dell'anno precedente) con soglie e scadenze.

- Parametri: `imposta_anno_precedente: float`
- Fonte normativa dichiarata: Art. 3, co. 4, D.Lgs. 23/2011; acconto 100% della cedolare dell'anno precedente, scadenze IRPEF. Precisione ESATTO.
- Casi di prova:
  - Imposta pari alla soglia di esenzione: `{"imposta_anno_precedente": 51.65}` → atteso: Nessun acconto dovuto.
  - Limite del versamento unico: `{"imposta_anno_precedente": 257.52}` → atteso: Unica soluzione di 257,52 entro il 30 novembre.
  - Un centesimo oltre il limite: `{"imposta_anno_precedente": 257.53}` → atteso: 103,01 entro il 30 giugno e 154,52 entro il 30 novembre.
  - Caso ordinario: `{"imposta_anno_precedente": 2000}` → atteso: 800,00 e 1.200,00.

### `acconto_irpef`

Calcola primo e secondo acconto IRPEF con il metodo storico (100% dell'imposta dell'anno precedente), soglie di esenzione e di versamento unico, scadenze.

- Parametri: `imposta_anno_precedente: float; metodo: str = 'storico' (storico \| previsionale)`
- Fonte normativa dichiarata: Art. 17 DPR 435/2001; art. 4 DL 69/1989; acconto 100% dell'imposta dell'anno precedente (metodo storico). Precisione ESATTO.
- Casi di prova:
  - Imposta pari alla soglia di esenzione: `{"imposta_anno_precedente": 51.65, "metodo": "storico"}` → atteso: Nessun acconto dovuto.
  - Un centesimo oltre la soglia di esenzione: `{"imposta_anno_precedente": 51.66}` → atteso: Acconto unico di 51,66 entro il 30 novembre.
  - Limite del versamento unico: `{"imposta_anno_precedente": 257.52}` → atteso: Unica soluzione di 257,52 entro il 30 novembre.
  - Un centesimo oltre il limite: due rate: `{"imposta_anno_precedente": 257.53}` → atteso: Primo acconto 40% = 103,01 entro il 30 giugno; secondo 60% = 154,52 entro il 30 novembre.
  - Caso ordinario: `{"imposta_anno_precedente": 1000, "metodo": "storico"}` → atteso: 400,00 e 600,00 (per i soggetti ISA sarebbero 500,00 e 500,00: il tool non ha il parametro).

### `assegno_unico`

Simula l'Assegno Unico Universale mensile e annuo per figlio in base all'ISEE, con alcune maggiorazioni per età e per nucleo monogenitoriale.

- Parametri: `isee: float (0 se assente); n_figli: int; eta_figli: list[int] \| None = None; genitore_solo: bool = False`
- Fonte normativa dichiarata: D.Lgs. 230/2021; importi 2026 (soglie ISEE 17.468,51 e 46.582,71; importi 203,80 e 58,30). Precisione INDICATIVO.
- Casi di prova:
  - ISEE non presentato: `{"isee": 0, "n_figli": 1, "eta_figli": [5], "genitore_solo": false}` → atteso: Importo minimo 58,30 euro mensili 2026 (art. 4 D.Lgs. 230/2021: senza ISEE spettano gli importi minimi); il tool restituisce il massimo 203,80.
  - ISEE pari alla soglia inferiore 2026: `{"isee": 17468.51, "n_figli": 1, "eta_figli": [5]}` → atteso: Importo massimo 203,80 mensili (valori 2026 da riscontrare sulla circolare INPS).
  - ISEE pari alla soglia superiore 2026: `{"isee": 46582.71, "n_figli": 1, "eta_figli": [5]}` → atteso: Importo minimo 58,30 mensili.
  - Tre figli di 0, 2 e 10 anni con ISEE 30.000: `{"isee": 30000, "n_figli": 3, "eta_figli": [0, 2, 10]}` → atteso: Da leggere dal sito. Per legge: maggiorazione del 50% per il figlio sotto un anno (circa 70,59 sull'importo base di 141,17) e del 50% per il figlio tra 1 e 3 anni nei nuclei con tre o più figli, più la maggiorazione per il terzo figlio (art. 4 D.Lgs. 230/2021); il tool aggiunge 96,90 e 34,10 fissi e nessuna maggiorazione per il terzo figlio (totale 554,51).
  - Figlio di 19 anni con ISEE 25.000: `{"isee": 25000, "n_figli": 1, "eta_figli": [19]}` → atteso: Importo per figlio maggiorenne fino a 21 anni, inferiore a quello dei minori (85 euro rivalutati al massimo, art. 4 D.Lgs. 230/2021): da leggere dal sito; il tool applica l'importo dei minori (166,16).
  - Due figli minori, genitore solo: `{"isee": 25000, "n_figli": 2, "eta_figli": [4, 8], "genitore_solo": true}` → atteso: Da leggere dal sito: la maggiorazione del 30% per genitore solo non risulta nel D.Lgs. 230/2021 (esiste quella per entrambi i genitori titolari di reddito da lavoro, estesa dall'INPS al genitore vedovo); il tool aggiunge 99,70.

### `calcolo_irpef`

Calcola IRPEF lorda per scaglioni, detrazione da lavoro dipendente o pensione, imposta netta e addizionali stimate con medie nazionali.

- Parametri: `reddito_complessivo: float; tipo_reddito: str = 'dipendente' (dipendente \| pensionato \| autonomo); deduzioni: float = 0; detrazioni_extra: float = 0; anno_fiscale: int = 0 (0 = anno corrente)`
- Fonte normativa dichiarata: Scaglioni IRPEF per anno (2024-2025: 23-35-43%; 2026: 23-33-43%, L. 199/2025); TUIR artt. 11-13. Precisione INDICATIVO (addizionali medie).
- Casi di prova:
  - Dipendente 30.000 euro, anno 2026: secondo scaglione al 33% e maggiorazione di 65 euro: `{"reddito_complessivo": 30000, "tipo_reddito": "dipendente", "deduzioni": 0, "detrazioni_extra": 0, "anno_fiscale": 2026}` → atteso: Imposta lorda 7.100,00 (28.000 x 23% + 2.000 x 33%, art. 11 TUIR come modificato dalla L. 199/2025). Detrazione art. 13 co. 1 lett. c) con coefficiente 0,9090: 1.736,19, più 65 euro (co. 1.1) = 1.801,19; ulteriore detrazione 1.000 euro (art. 1 L. 207/2024, reddito tra 20.000 e 32.000). Imposta netta attesa 4.298,81; il tool restituisce 5.363,64.
  - Autonomo 50.000 euro, anno 2025: confine del secondo scaglione, confronto diretto con la pagina 2026 del sito (redditi 2025): `{"reddito_complessivo": 50000, "tipo_reddito": "autonomo", "anno_fiscale": 2025}` → atteso: Imposta lorda 14.140,00 (6.440 + 22.000 x 35%); con anno_fiscale 2026 13.700,00 (22.000 x 33%). A 50.000 euro la detrazione dell'art. 13 co. 5 è nulla, quindi netta = lorda.
  - Autonomo 30.000 euro, anno 2026: detrazione per redditi di lavoro autonomo: `{"reddito_complessivo": 30000, "tipo_reddito": "autonomo", "anno_fiscale": 2026}` → atteso: Lorda 7.100,00; detrazione art. 13 co. 5 lett. c) TUIR 500 x 0,9090 = 454,50; netta 6.645,50. Il tool non riconosce alcuna detrazione (netta 7.100,00).
  - Oneri deducibili: la detrazione si calcola sul reddito complessivo e non sull'imponibile: `{"reddito_complessivo": 30000, "tipo_reddito": "dipendente", "deduzioni": 2000, "anno_fiscale": 2026}` → atteso: Imponibile 28.000, lorda 6.440,00; detrazioni sul reddito complessivo di 30.000 (art. 13 TUIR): 1.801,19 + 1.000 = 2.801,19; netta 3.638,81. Il tool calcola la detrazione su 28.000 (1.910) e restituisce 4.530,00.
  - Pensionato 27.000 euro, anno 2026: maggiorazione di 50 euro tra 25.000 e 29.000: `{"reddito_complessivo": 27000, "tipo_reddito": "pensionato", "anno_fiscale": 2026}` → atteso: Lorda 6.210,00; detrazione art. 13 co. 3 lett. b) 700 + 1.255 x 0,0512 = 764,26, più 50 euro = 814,26; netta 5.395,74 (tool 5.445,64).
  - Anno assente dalla tabella (2023, quattro scaglioni previgenti): `{"reddito_complessivo": 30000, "tipo_reddito": "autonomo", "anno_fiscale": 2023}` → atteso: Lorda 7.400,00 (15.000 x 23% + 13.000 x 25% + 2.000 x 35%, art. 11 TUIR nel testo vigente nel 2023). Il tool applica gli scaglioni 2026 (7.100,00) pur dichiarando anno_fiscale 2023: atteso un rifiuto o un avviso.

### `calcolo_tfr`

Stima il TFR lordo (quota annua pari a retribuzione diviso 13,5, rivalutata 1,5% più 75% del FOI medio) e il netto con la tassazione separata.

- Parametri: `retribuzione_annua_lorda: float; anni_servizio: int; rivalutazione_media_pct: float = 2.0`
- Fonte normativa dichiarata: Art. 2120 c.c. (accantonamento e rivalutazione); artt. 17 e 19 TUIR (tassazione separata). Precisione INDICATIVO.
- Casi di prova:
  - Un solo anno, nessuna rivalutazione: quota annua e contributo 0,50%: `{"retribuzione_annua_lorda": 27000, "anni_servizio": 1}` → atteso: Quota 27.000 / 13,5 = 2.000,00 (art. 2120 co. 1 c.c.) meno il contributo 0,50% di 135,00 (art. 3 L. 297/1982) = 1.865,00. Reddito di riferimento 1.865 x 12 = 22.380, aliquota 23%, imposta 428,95, netto 1.436,05. Il tool restituisce lordo 2.000,00 e imposta 460,00.
  - Dieci anni con FOI medio 2% (tasso di rivalutazione 3%): `{"retribuzione_annua_lorda": 30000, "anni_servizio": 10, "rivalutazione_media_pct": 2.0}` → atteso: Da leggere dal sito impostando dieci anni di retribuzione costante; il tool dà TFR lordo 25.475,29 senza sottrarre il contributo 0,50% né l'imposta sostitutiva del 17% sulle rivalutazioni, quindi atteso un valore del sito inferiore.
  - Venti anni con FOI nullo: rivalutazione del solo 1,5% fisso: `{"retribuzione_annua_lorda": 60000, "anni_servizio": 20, "rivalutazione_media_pct": 0}` → atteso: Rivalutazione 1,5% (art. 2120 co. 4 c.c.) al netto del 17%; il reddito di riferimento si calcola sul TFR al netto delle rivalutazioni, moltiplicato per 12 e diviso per 20 (art. 19 co. 1 TUIR). Da leggere dal sito; il tool dà lordo 102.771,85 e imposta 31.191,90 calcolata anche sulle rivalutazioni.
  - Anni di servizio nulli: `{"retribuzione_annua_lorda": 30000, "anni_servizio": 0}` → atteso: Errore di validazione (anni di servizio almeno 1).

### `cerca_codice_tributo`

Cerca un codice tributo F24 per codice o descrizione nella tabella locale di 55 codici e restituisce codice, descrizione, sezione e categoria.

- Parametri: `query: str (codice, per esempio '4001', o testo, per esempio 'IMU')`
- Fonte normativa dichiarata: Nessuna riga Vigenza; tabella codici_tributo.json dalle risoluzioni dell'Agenzia delle Entrate, aggiornamento dichiarato 2026. Precisione INDICATIVO.
- Casi di prova:
  - Codice esatto noto: `{"query": "4001"}` → atteso: 4001, IRPEF saldo (tabella AdE).
  - Codice della cedolare secca: `{"query": "1840"}` → atteso: Tabella AdE: cedolare secca, acconto prima rata (1841 seconda rata o unica soluzione, 1842 saldo); il tool lo descrive come saldo del forfettario.
  - Ricerca testuale del regime forfettario: `{"query": "forfettario"}` → atteso: Tabella AdE: 1790 acconto prima rata, 1791 acconto seconda rata o unica soluzione, 1792 saldo; il tool restituisce 1840, 1841, 1842.
  - Ricerca testuale della cedolare: `{"query": "cedolare"}` → atteso: Tabella AdE: 1840, 1841, 1842; il tool restituisce 1550, 1551, 1552.
  - Addizionale comunale in autotassazione: `{"query": "3843"}` → atteso: Tabella AdE: acconto dell'addizionale comunale all'IRPEF in autotassazione (3844 è il saldo); il tool indica saldo.
  - Interessi della rateizzazione: `{"query": "1668"}` → atteso: Tabella AdE: interessi per pagamento dilazionato delle imposte (sezione erario); il tool risponde che il codice non esiste.

### `detrazione_altri_familiari`

Calcola la detrazione IRPEF di 750 euro per ciascun altro familiare a carico, proporzionata al reddito con soglia 80.000 euro.

- Parametri: `reddito_complessivo: float; n_familiari: int`
- Fonte normativa dichiarata: Art. 12, co. 1, lett. d) TUIR; soglia 80.000 euro. Precisione ESATTO.
- Casi di prova:
  - Due familiari, reddito 40.000: `{"reddito_complessivo": 40000, "n_familiari": 2}` → atteso: 750 x 0,5 = 375,00 ciascuno, totale 750,00.
  - Un familiare, reddito 20.000: `{"reddito_complessivo": 20000, "n_familiari": 1}` → atteso: 750 x 0,75 = 562,50.
  - Reddito pari alla soglia: `{"reddito_complessivo": 80000, "n_familiari": 1}` → atteso: 0,00.
  - Un euro sotto la soglia, tre familiari: `{"reddito_complessivo": 79999, "n_familiari": 3}` → atteso: Coefficiente 0,0000 alla quarta cifra decimale: 0,00 (tool 0,03).

### `detrazione_assegno_coniuge`

Calcola la detrazione IRPEF per chi percepisce l'assegno periodico dal coniuge separato o divorziato.

- Parametri: `reddito_complessivo: float`
- Fonte normativa dichiarata: Art. 13, co. 5-bis, TUIR; art. 10, co. 1, lett. c) TUIR; fasce 5.500, 28.000, 50.000 euro. Precisione ESATTO.
- Casi di prova:
  - Limite della prima fascia: `{"reddito_complessivo": 5500}` → atteso: Da leggere dal sito; il tool applica 1.265,00.
  - Fascia intermedia, possibile maggiorazione di 50 euro: `{"reddito_complessivo": 12000}` → atteso: Da leggere dal sito; il tool restituisce 1.044,00 senza la maggiorazione del co. 5.1.
  - Fascia intermedia: `{"reddito_complessivo": 20000}` → atteso: Da leggere dal sito; il tool restituisce 772,00 (771,96 con coefficiente troncato).
  - Terza fascia: `{"reddito_complessivo": 40000}` → atteso: Da leggere dal sito; il tool restituisce 227,27 (227,25 con coefficiente troncato).

### `detrazione_canone_locazione`

Calcola la detrazione IRPEF per l'inquilino dell'abitazione principale secondo il tipo di contratto (libero, concordato, giovani under 31).

- Parametri: `reddito_complessivo: float; tipo_contratto: str = 'libero' (libero \| concordato \| giovani_under31)`
- Fonte normativa dichiarata: Art. 16 TUIR (importi rivalutati; soglie di reddito non aggiornate dal 1997). Precisione ESATTO.
- Casi di prova:
  - Libero, reddito al limite della prima soglia: `{"reddito_complessivo": 15493.71, "tipo_contratto": "libero"}` → atteso: 300,00 (art. 16 co. 01 TUIR).
  - Libero, un centesimo oltre la prima soglia: `{"reddito_complessivo": 15493.72, "tipo_contratto": "libero"}` → atteso: 150,00.
  - Concordato oltre la seconda soglia: `{"reddito_complessivo": 30987.42, "tipo_contratto": "concordato"}` → atteso: 0,00 (art. 16 co. 1).
  - Giovane under 31 con reddito 12.000 (sul sito indicare un canone annuo di 6.000 euro): `{"reddito_complessivo": 12000, "tipo_contratto": "giovani_under31"}` → atteso: Con canone di 6.000 euro: 20% = 1.200,00, superiore a 991,60 e inferiore a 2.000 (art. 16 co. 1-ter TUIR); il tool restituisce 2.000.

### `detrazione_coniuge`

Calcola la detrazione IRPEF per il coniuge a carico nelle tre fasce di reddito dell'art. 12 TUIR.

- Parametri: `reddito_complessivo: float`
- Fonte normativa dichiarata: Art. 12, co. 1, lett. a) TUIR; fasce fino a 15.000, 15.001-40.000, 40.001-80.000 euro. Precisione ESATTO.
- Casi di prova:
  - Prima fascia: `{"reddito_complessivo": 10000}` → atteso: 800 - 110 x 0,6666 = 726,67.
  - Reddito 30.000: maggiorazione di 20 euro: `{"reddito_complessivo": 30000}` → atteso: 690 + 20 = 710,00 (art. 12 co. 1 lett. a TUIR, reddito tra 29.200 e 34.700); il tool restituisce 690.
  - Reddito 34.800: maggiorazione di 30 euro: `{"reddito_complessivo": 34800}` → atteso: 690 + 30 = 720,00; tool 690.
  - Reddito 35.150: maggiorazione di 10 euro: `{"reddito_complessivo": 35150}` → atteso: 690 + 10 = 700,00; tool 690.
  - Terza fascia: `{"reddito_complessivo": 60000}` → atteso: 690 x 20.000 / 40.000 = 345,00.
  - Limite superiore: `{"reddito_complessivo": 80000}` → atteso: 0,00.

### `detrazione_figli`

Calcola la detrazione IRPEF per figli a carico dai 21 anni (950 euro, 1.350 se con disabilità) proporzionata al reddito con soglia 95.000 più 15.000 per ogni figlio successivo al primo.

- Parametri: `reddito_complessivo: float; n_figli_over21: int; n_figli_disabili: int = 0`
- Fonte normativa dichiarata: Art. 12 TUIR (mod. D.Lgs. 230/2021); soglia 95.000 euro aumentata di 15.000 per ogni figlio successivo al primo. Precisione ESATTO.
- Casi di prova:
  - Due figli, reddito 30.000: soglia elevata a 110.000: `{"reddito_complessivo": 30000, "n_figli_over21": 2, "n_figli_disabili": 0}` → atteso: Soglia 110.000 (art. 12 co. 1 lett. c TUIR); coefficiente 0,7272; 950 x 0,7272 = 690,84 per figlio, totale 1.381,68 (tool 1.381,82 con coefficiente non troncato).
  - Un figlio con disabilità, reddito 40.000: `{"reddito_complessivo": 40000, "n_figli_over21": 1, "n_figli_disabili": 1}` → atteso: 1.350 (950 + 400) x 0,5789 = 781,51 circa (tool 781,58).
  - Reddito pari alla soglia: `{"reddito_complessivo": 95000, "n_figli_over21": 1}` → atteso: 0,00.
  - Un euro sotto la soglia di due figli: `{"reddito_complessivo": 109999, "n_figli_over21": 2}` → atteso: Coefficiente 0,0000 alla quarta cifra decimale: detrazione 0,00 (il tool restituisce 0,02).

### `detrazione_lavoro_dipendente`

Calcola la detrazione IRPEF per redditi di lavoro dipendente nelle fasce dell'art. 13 co. 1 TUIR, rapportata ai giorni lavorati.

- Parametri: `reddito_complessivo: float; giorni_lavoro: int = 365 (1-365)`
- Fonte normativa dichiarata: Art. 13, co. 1, TUIR, 'scaglioni 2026 ex L. 199/2025' (importo di 1.955 euro). Precisione ESATTO.
- Casi di prova:
  - Limite della prima fascia: `{"reddito_complessivo": 15000, "giorni_lavoro": 365}` → atteso: 1.955,00 (art. 13 co. 1 lett. a TUIR).
  - Un euro sopra la prima fascia: `{"reddito_complessivo": 15001, "giorni_lavoro": 365}` → atteso: 1.910 + 1.190 x 0,9999 = 3.099,88 con coefficiente troncato (tool 3.099,91): salto previsto dalla legge.
  - Reddito 30.000: maggiorazione di 65 euro: `{"reddito_complessivo": 30000, "giorni_lavoro": 365}` → atteso: 1.910 x 0,9090 = 1.736,19, più 65 (co. 1.1) = 1.801,19; il tool restituisce 1.736,36.
  - Reddito 10.000 per 90 giorni: minimo di legge: `{"reddito_complessivo": 10000, "giorni_lavoro": 90}` → atteso: 1.955 x 90/365 = 482,05, ma la detrazione non può essere inferiore a 690 euro (1.380 per contratti a tempo determinato), art. 13 co. 1 lett. a): atteso 690,00; tool 482,05.
  - Limite di azzeramento: `{"reddito_complessivo": 50000, "giorni_lavoro": 365}` → atteso: 0,00.

### `detrazione_pensione`

Calcola la detrazione IRPEF per redditi di pensione nelle fasce dell'art. 13 co. 3 TUIR, rapportata ai giorni di pensione.

- Parametri: `reddito_complessivo: float; giorni: int = 365 (1-365)`
- Fonte normativa dichiarata: Art. 13, co. 3, TUIR; fasce fino a 8.500, 8.501-28.000, 28.001-50.000 euro. Precisione ESATTO.
- Casi di prova:
  - Limite della prima fascia: `{"reddito_complessivo": 8500, "giorni": 365}` → atteso: 1.955,00.
  - Pensione per 100 giorni: minimo di legge: `{"reddito_complessivo": 8000, "giorni": 100}` → atteso: 1.955 x 100/365 = 535,62, ma non meno di 713 euro (art. 13 co. 3 lett. a): atteso 713,00; tool 535,62.
  - Reddito 27.000: maggiorazione di 50 euro: `{"reddito_complessivo": 27000, "giorni": 365}` → atteso: 700 + 1.255 x 0,0512 = 764,26, più 50 = 814,26; tool 764,36.
  - Terza fascia: `{"reddito_complessivo": 40000, "giorni": 365}` → atteso: 700 x 0,4545 = 318,15 (tool 318,18).

### `rateizzazione_imposte`

Costruisce il piano di rateizzazione mensile delle imposte da dichiarazione con interessi al 4% annuo e date delle rate.

- Parametri: `importo_totale: float; n_rate: int (2-7); data_prima_rata: str (AAAA-MM-GG); tasso_interesse_annuo: float = 4.0`
- Fonte normativa dichiarata: Art. 20 D.Lgs. 241/1997; da 2 a 7 rate mensili da giugno (o luglio con maggiorazione 0,40%); tasso 4% annuo (DM 21/05/2009). Precisione ESATTO.
- Casi di prova:
  - Tre rate da giugno, non titolare di partita IVA: `{"importo_totale": 3000, "n_rate": 3, "data_prima_rata": "2026-06-30", "tasso_interesse_annuo": 4.0}` → atteso: Rate da 1.000 con scadenze 30/06, 31/07, 31/08; interessi 0; 3,30 (0,33%); 6,60 (0,66%); totale 9,90 (art. 20 D.Lgs. 241/1997, tabella AdE). Il tool restituisce 13,34 e scadenze 28/06, 28/07, 28/08.
  - Sette rate, numero massimo: `{"importo_totale": 7000, "n_rate": 7, "data_prima_rata": "2026-06-30"}` → atteso: Interessi 0; 3,30; 6,60; 9,90; 13,20; 16,50; 19,80, totale 69,30, ultima rata a dicembre (da leggere dal sito la data esatta). Il tool restituisce 186,66.
  - Otto rate: `{"importo_totale": 7000, "n_rate": 8, "data_prima_rata": "2026-06-30"}` → atteso: Errore: oltre il numero massimo di rate.
  - Prima rata a luglio con maggiorazione: `{"importo_totale": 6000, "n_rate": 6, "data_prima_rata": "2026-07-30"}` → atteso: Da leggere dal sito: il versamento nei trenta giorni successivi comporta la maggiorazione dello 0,40% (art. 17 co. 2 DPR 435/2001) e gli interessi per rata dello 0,33% al mese; il tool non applica la maggiorazione e sposta le date al giorno 28.

### `ravvedimento_operoso`

Calcola sanzione ridotta e interessi legali del ravvedimento operoso per omesso versamento o dichiarazione tardiva in base ai giorni di ritardo.

- Parametri: `imposta_dovuta: float; giorni_ritardo: int; tipo: str = 'omesso_versamento' (omesso_versamento \| dichiarazione_tardiva)`
- Fonte normativa dichiarata: Art. 13 D.Lgs. 472/1997 (mod. D.Lgs. 87/2024, sanzione base 25%); tasso legale da tassi_legali.json. Precisione INDICATIVO (solo violazioni dal 01/09/2024).
- Casi di prova:
  - Ravvedimento sprint: 5 giorni (sito: scadenza 16/03/2026, versamento 21/03/2026): `{"imposta_dovuta": 1000, "giorni_ritardo": 5, "tipo": "omesso_versamento"}` → atteso: Sanzione 12,5% x 5/15 (art. 13 co. 1 D.Lgs. 471/1997 mod. D.Lgs. 87/2024) ridotta a 1/10 (art. 13 co. 1 lett. a D.Lgs. 472/1997) = 0,4167%, cioè 4,17; interessi 1,6% x 5/365 = 0,22; totale 1.004,39.
  - Quindicesimo giorno: ultimo giorno del ravvedimento sprint: `{"imposta_dovuta": 1000, "giorni_ritardo": 15}` → atteso: 12,5% x 15/15 / 10 = 1,25%, cioè 12,50 (stesso importo del ravvedimento breve); interessi 0,66. Il tool etichetta il caso come 'breve' ma l'importo coincide.
  - 60 giorni (sito: 16/03/2026, versamento 15/05/2026): `{"imposta_dovuta": 1000, "giorni_ritardo": 60}` → atteso: 1/9 di 12,5% = 1,3889%, cioè 13,89 (lett. a-bis); interessi 2,63; totale 1.016,52.
  - 180 giorni (sito: 16/03/2026, versamento 12/09/2026): `{"imposta_dovuta": 1000, "giorni_ritardo": 180}` → atteso: 1/8 di 25% = 3,125%, cioè 31,25 (lett. b, entro il termine della dichiarazione); interessi 7,89; totale 1.039,14.
  - 800 giorni a cavallo di tre anni (sito: scadenza 17/06/2024, versamento 26/08/2026): `{"imposta_dovuta": 1000, "giorni_ritardo": 800}` → atteso: Senza schema d'atto né processo verbale la riduzione attesa è 1/7 (3,5714%, cioè 35,71) e non 1/6 (tool 41,67): da riscontrare con cite_law sulle lettere b-bis e seguenti dell'art. 13 co. 1 D.Lgs. 472/1997. Interessi con i tassi di ciascun anno (2,5% nel 2024, 2,0% nel 2025, 1,6% nel 2026: circa 43,95) contro 35,07 del tool.
  - Dichiarazione presentata con 30 giorni di ritardo: `{"imposta_dovuta": 1000, "giorni_ritardo": 30, "tipo": "dichiarazione_tardiva"}` → atteso: Da leggere dal sito e dalla norma: la dichiarazione presentata entro 90 giorni è valida e sconta una sanzione in misura fissa (250 euro nella prassi, ravvedibile a 1/10) oltre alla sanzione sui versamenti tardivi (art. 1 D.Lgs. 471/1997 vigente). Il tool applica il 6% dell'imposta (60,00).

### `regime_forfettario`

Simula l'imposta sostitutiva del regime forfettario (coefficiente di redditività, contributi deducibili, aliquota 5% o 15%) e la confronta con una stima IRPEF ordinaria.

- Parametri: `ricavi: float; coefficiente_redditivita: float = 78; anni_attivita: int = 1 (1-5 aliquota 5%, oltre 15%); contributi_inps: float = 0`
- Fonte normativa dichiarata: Art. 1, commi 54-89, L. 190/2014 (mod. L. 208/2015 e L. 145/2018); limite ricavi 85.000 euro; aliquota 15%, 5% per i primi cinque anni.
- Casi di prova:
  - Professionista al primo anno, aliquota startup: `{"ricavi": 50000, "coefficiente_redditivita": 78, "anni_attivita": 1, "contributi_inps": 0}` → atteso: Reddito 39.000 (78%); imposta 5% = 1.950,00 (art. 1 co. 64-65 L. 190/2014).
  - Ricavi esattamente al limite, aliquota ordinaria, contributi deducibili: `{"ricavi": 85000, "coefficiente_redditivita": 78, "anni_attivita": 6, "contributi_inps": 8000}` → atteso: Ammesso (limite incluso, co. 54). Reddito 66.300, imponibile 58.300 (contributi dedotti, co. 64), imposta 15% = 8.745,00.
  - Ricavi di un centesimo oltre il limite: `{"ricavi": 85000.01, "coefficiente_redditivita": 78, "anni_attivita": 6}` → atteso: Errore: oltre 85.000 euro (co. 54 come modificato dalla L. 197/2022). Il regime cessa dall'anno successivo; oltre 100.000 cessa nello stesso anno (co. 71): il tool non distingue.
  - Commercio, coefficiente 40%, terzo anno: `{"ricavi": 60000, "coefficiente_redditivita": 40, "anni_attivita": 3, "contributi_inps": 4000}` → atteso: Reddito 24.000, imponibile 20.000, imposta 5% = 1.000,00.
  - Quinto anno ancora agevolato, altre attività 67%: `{"ricavi": 40000, "coefficiente_redditivita": 67, "anni_attivita": 5, "contributi_inps": 3000}` → atteso: Reddito 26.800, imponibile 23.800, imposta 5% = 1.190,00; con anni_attivita 6 l'imposta diventa 3.570,00 (15%).

## diritto_lavoro.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `calcolo_naspi` | calcolo | fonte_ufficiale | nessuna pagina del sito | INPS, circolare annuale sugli importi 2026 delle prestazioni di disoccupazione (retribuzione di riferimento per la soglia e importo massimo mensile NASpI); Normattiva, artt. 3-5 D.Lgs. 22/2015 | Corretto dall'audit (par. 5): la riduzione del 3% decorre dal primo giorno del sesto mese di fruizione (ottavo per chi ha compiuto 55 anni alla domanda), art. 4 co. 3 D.Lgs. 22/2015. Il benchmark deve confermare: soglia e massimale 2026 sulla circolare INPS (sono costanti nel codice, senza tabella con _vintage: dal 2027 resteranno fermi senza avviso); formula sopra soglia; durata pari a metà delle settimane (art. 5) e convenzione del tool (4,33 settimane per mese, durata arrotondata al decimo di mese) rispetto al computo INPS in giorni; riduzione composta mese per mese. Da segnalare: nessun controllo del requisito di almeno 13 settimane nei quattro anni (art. 3 co. 1 lett. b); l'età rilevante è quella alla data della domanda. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `costo_lavoro` | calcolo | fonte_ufficiale | nessuna pagina del sito | Normattiva e Agenzia delle Entrate: artt. 11 e 13 TUIR vigenti e art. 1 co. 4-9 L. 207/2024 (misure del cuneo fiscale); INPS, circolare annuale su aliquote e massimali contributivi 2026; art. 11 co. 4-octies D.Lgs. 446/1997 (IRAP); pagina del sito sulla detrazione per lavoro dipendente: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-redditi-assimilati.php | Declassato dall'audit a INDICATIVO (par. 7, confidenza alta): IRAP deducibile sul personale a tempo indeterminato dal 2015, INPDAI soppresso. La pagina del sito (titolo nei risultati: Calcolo IRPEF con nuove aliquote 2026) copre solo la componente fiscale: il confronto va fatto su irpef_stimata a parità di imponibile (retribuzione meno contributi del dipendente). Il benchmark deve segnalare: detrazione per lavoro dipendente senza l'aumento di 65 euro tra 25.000 e 35.000 (art. 13 co. 1.1 TUIR) e senza le misure dal 2025 (somma esente fino a 20.000 euro e ulteriore detrazione tra 20.000 e 40.000, L. 207/2024), quindi netto sottostimato; IRAP al 3,9% sommata nonostante la deduzione integrale del costo del personale a tempo indeterminato; aliquota dell'apprendista (5,19% nel tool) da riscontrare sulla circolare INPS; contributo aggiuntivo dell'1% oltre la prima fascia pensionabile assente; TFR al 6,91%, quota netta dopo lo 0,50% della L. 297/1982, mentre il costo per l'azienda è 1/13,5 della retribuzione (art. 2120 c.c.); addizionali regionali e comunali assenti. Fase 0: il sito non ha alcun calcolatore del costo del lavoro (la pagina IRPEF indicata non lo copre); strategia portata a fonte_ufficiale: aliquote contributive INPS (circolare annuale) e art. 11 D.Lgs. 446/1997 per l'IRAP. |
| `indennita_licenziamento` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 3, 8 e 9 D.Lgs. 23/2015 nel testo vigente, con le declaratorie di illegittimità di C. Cost. 194/2018 e 118/2025 | Declassato dall'audit a INDICATIVO (par. 7, confidenza alta): dopo C. Cost. 194/2018 non c'è automatismo di due mensilità per anno, il giudice determina l'indennità tra minimo e massimo. Il benchmark (cite_law) deve confermare: 6-36 mensilità (art. 3 co. 1); dimezzamento per i datori sotto soglia senza il tetto di 6 mensilità caduto con C. Cost. 118/2025 (art. 9 co. 1), quindi 3-18; tetto di 12 mensilità del risarcimento con reintegra (art. 3 co. 2). Due scostamenti non rilevati dall'audit: con la reintegra l'indennità è commisurata al periodo tra licenziamento e reintegrazione, dedotto l'aliunde perceptum, e non all'anzianità (il tool usa anni x 2 fino a 12); l'art. 9 co. 1 esclude la reintegra dell'art. 3 co. 2 per i datori sotto soglia, mentre il tool la calcola anche per dimensione piccola. Frazioni d'anno riproporzionate e frazioni di mese di almeno 15 giorni come mese intero (art. 8). Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `indennita_preavviso` | calcolo | fonte_ufficiale | nessuna pagina del sito | CNEL, Archivio nazionale dei contratti collettivi: testi vigenti del CCNL Terziario Confcommercio, del CCNL Metalmeccanici industria e del CCNL Studi professionali (articoli sul preavviso); art. 2121 c.c. per la base di calcolo | Non citato ai par. 5 e 7. La tabella è stata riconciliata con i contratti (CHANGELOG: commercio e metalmeccanici cella per cella, 14 celle corrette negli studi professionali) ma i rinnovi la rendono deperibile, per questo esiste giorni_preavviso. Il benchmark deve confermare sul testo del CCNL vigente nell'archivio CNEL le celle ai confini delle fasce (per il tool 5 e 10 anni esatti ricadono nella fascia inferiore), il divisore 30 per i periodi espressi in giorni di calendario o in mesi, e che con giorni_preavviso la risposta non citi la tabella (dati_forniti_dal_chiamante). Ricordare che la base dell'indennità comprende ogni compenso continuativo, ratei delle mensilità aggiuntive inclusi (art. 2121 c.c.), da comprendere in retribuzione_mensile. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `offerta_conciliativa` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 6, 8 e 9 D.Lgs. 23/2015 nel testo vigente dopo C. Cost. 118/2025 | Non citato ai par. 5 e 7 dell'audit; allineato a C. Cost. 118/2025 in una versione precedente (tetto 13,5 per le piccole imprese), punto rimasto alla firma dell'avvocato secondo il CHANGELOG. Il benchmark (cite_law) deve confermare: una mensilità per anno tra 3 e 27 (art. 6 co. 1 nel testo del DL 87/2018); che la caduta delle parole 'e non può in ogni caso superare il limite di sei mensilità' dell'art. 9 co. 1 valga anche per l'importo dell'art. 6, richiamato nella stessa frase, lasciando il dimezzamento; frazioni d'anno riproporzionate e frazioni di mese di almeno 15 giorni come mese intero (art. 8). Da segnalare: il campo confronto_giudiziale ripete l'automatismo di due mensilità per anno superato da C. Cost. 194/2018; ambito limitato agli assunti dal 07/03/2015. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `scadenze_licenziamento` | calcolo | solo_norma | https://www.avvocatoandreani.it/servizi/calcolo_scadenze_termini_udienze.php (media) | Normattiva: art. 6 L. 604/1966, artt. 2963 e 2964 c.c., art. 3 L. 742/1969 | Corretto dall'audit (par. 5): 180 giorni dall'impugnazione e 60 dal rifiuto della conciliazione (art. 6 co. 2 L. 604/1966), rito Fornero rimosso. Il benchmark (cite_law) deve confermare i tre termini e l'esclusione della sospensione feriale per le controversie di lavoro (art. 3 L. 742/1969); la pagina del sito è il calcolatore generico dei termini (titolo nei risultati: Calcolo Scadenze, Termini Processuali e Giorni tra Date), utile per il conteggio dei giorni con la sospensione feriale disattivata. Punto aperto non trattato dall'audit: il tool non proroga mai la scadenza che cade in giorno festivo, mentre ai termini di decadenza la giurisprudenza estende l'art. 2963 co. 3 c.c. (proroga al primo giorno non festivo; il sabato non è festivo) e per il deposito del ricorso si discute dell'art. 155 c.p.c.: i casi scelti cadono di domenica o prima di una festività. tests/unit/test_diritto_lavoro.py fissa oggi le date non prorogate (2025-03-02, 2025-11-30, 2025-12-07): cambiarle solo con fonte primaria. Da verificare anche se i 180 giorni decorrano dall'invio o dalla ricezione dell'impugnazione. |

### `calcolo_naspi`

Importo e durata della NASpI: 75% della retribuzione media mensile fino alla soglia 2026 più 25% dell'eccedenza, entro il massimale; durata pari a metà delle settimane degli ultimi quattro anni (al massimo 24 mesi) e riduzione del 3% al mese dal sesto mese (ottavo dai 55 anni).

- Parametri: `retribuzione_media_mensile: float (> 0); settimane_contributive: int (> 0, ultimi quattro anni); eta_anni: int`
- Fonte normativa dichiarata: D.Lgs. 22/2015 artt. 4-8; circolare INPS n. 4/2026 (soglia 1.456,72 e massimale 1.584,70 euro scritti nel codice)
- Casi di prova:
  - Sotto soglia, 104 settimane, 40 anni: `{"retribuzione_media_mensile": 1000, "settimane_contributive": 104, "eta_anni": 40}` → atteso: 750,00 euro al mese (75%, art. 4 co. 2); durata 52 settimane, circa 12 mesi (art. 5); dal sesto mese 727,50 (art. 4 co. 3)
  - Retribuzione esattamente pari alla soglia 2026: `{"retribuzione_media_mensile": 1456.72, "settimane_contributive": 52, "eta_anni": 30}` → atteso: 1.092,54 euro (0,75 x 1.456,72); durata 26 settimane, circa 6 mesi
  - Retribuzione che raggiunge esattamente il massimale: `{"retribuzione_media_mensile": 3425.36, "settimane_contributive": 208, "eta_anni": 54}` → atteso: 1.584,70 euro (0,75 x 1.456,72 + 0,25 x 1.968,64 = massimale 2026); durata massima 104 settimane, 24 mesi; riduzione dal sesto mese perché 54 anni
  - 55 anni, massimale e durata massima: `{"retribuzione_media_mensile": 3500, "settimane_contributive": 208, "eta_anni": 55}` → atteso: 1.584,70 euro; riduzione dal primo giorno dell'ottavo mese (art. 4 co. 3); ventiquattresimo mese 944,21 (1.584,70 x 0,97^17)
  - 12 settimane: requisito contributivo non raggiunto: `{"retribuzione_media_mensile": 1200, "settimane_contributive": 12, "eta_anni": 30}` → atteso: nessun diritto: servono almeno 13 settimane nei quattro anni (art. 3 co. 1 lett. b D.Lgs. 22/2015); il tool calcola comunque 900 euro per 1,4 mesi

### `costo_lavoro`

Stima del costo aziendale e del netto annuo del dipendente con aliquote contributive medie (dipendente, apprendista, dirigente), IRPEF sugli scaglioni dell'anno corrente con la sola detrazione per lavoro dipendente, TFR al 6,91% e IRAP al 3,9%.

- Parametri: `retribuzione_lorda_annua: float (> 0); tipo_contratto: str = 'dipendente' (dipendente, apprendista, dirigente); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: DPR 917/1986 (IRPEF, scaglioni per anno dalla tabella irpef_scaglioni: 2026 con il 33% nel secondo scaglione); L. 153/1969 (contributi); D.Lgs. 446/1997 (IRAP); art. 2120 c.c. (TFR); INDICATIVO
- Casi di prova:
  - Dipendente, 30.000 euro: fascia dell'aumento di 65 euro e dell'ulteriore detrazione: `{"retribuzione_lorda_annua": 30000}` → atteso: IRPEF netta 3.221,60 euro: imponibile 27.243 (30.000 meno 9,19%), imposta lorda 6.265,89 (23%, art. 11 TUIR), detrazione 1.979,29 + 65 (art. 13 co. 1 e 1.1), ulteriore detrazione 1.000 (L. 207/2024, da riscontrare); il tool dà 4.286,60. Contributi e costo aziendale da leggere dalla fonte INPS
  - Dipendente, 15.000 euro: somma esente del cuneo fiscale: `{"retribuzione_lorda_annua": 15000}` → atteso: IRPEF netta 1.177,95 (13.621,50 x 23% meno 1.955, art. 13 co. 1) come nel tool, ma al netto si aggiunge la somma non imponibile della L. 207/2024 (5,3% del reddito di lavoro dipendente tra 8.500 e 15.000: 721,94 euro, da riscontrare)
  - Dipendente, 55.000 euro: secondo scaglione 2026: `{"retribuzione_lorda_annua": 55000}` → atteso: imponibile 49.945,50; imposta lorda 13.682,02 (6.440 + 21.945,50 x 33%, scaglioni 2026); detrazione 4,73; IRPEF netta 13.677,29 (il tool 13.677,28 per arrotondamento): confrontare con il sito sul 2026 e, sul 2025 al 35%, verificare la tabella per anno
  - Dirigente, 80.000 euro: `{"retribuzione_lorda_annua": 80000, "tipo_contratto": "dirigente"}` → atteso: da leggere dalla fonte: contribuzione dei dirigenti nel fondo lavoratori dipendenti INPS (INPDAI soppresso dal 2003), IRAP non dovuta sul costo del personale a tempo indeterminato (art. 11 co. 4-octies D.Lgs. 446/1997); il tool somma 3.120 euro di IRAP e cita l'INPDAI
  - Apprendista, 20.000 euro: `{"retribuzione_lorda_annua": 20000, "tipo_contratto": "apprendista"}` → atteso: aliquota a carico dell'apprendista da leggere dalla circolare INPS (5,84% nella disciplina nota, il tool 5,19%); IRPEF da leggere dal sito sullo stesso imponibile

### `indennita_licenziamento`

Indennità per licenziamento illegittimo nelle tutele crescenti: due mensilità per anno come punto di partenza entro 6-36 mensilità (3-18 per i datori sotto soglia), oppure risarcimento fino a 12 mensilità in caso di reintegra.

- Parametri: `anni_servizio: float (> 0); retribuzione_mensile: float (> 0); dimensione_azienda: str = 'grande' (grande oltre 15 dipendenti, piccola fino a 15); tipo: str = 'indennitario' (indennitario, reintegra)`
- Fonte normativa dichiarata: D.Lgs. 23/2015 artt. 3 e 9; C. Cost. 194/2018, 128/2024, 118/2025 (INDICATIVO)
- Casi di prova:
  - Grande, 2 anni: minimo di legge: `{"anni_servizio": 2, "retribuzione_mensile": 2000}` → atteso: non meno di 6 mensilità (art. 3 co. 1): minimo 12.000 euro, fino a 72.000 (36 mensilità) secondo la valutazione del giudice; il tool dà 12.000
  - Grande, 20 anni: tetto di 36 mensilità: `{"anni_servizio": 20, "retribuzione_mensile": 1000}` → atteso: massimo 36 mensilità, 36.000 euro (art. 3 co. 1); il tool lo dà come valore puntuale
  - Piccola, 20 anni: dimezzamento senza il tetto di 6: `{"anni_servizio": 20, "retribuzione_mensile": 1000, "dimensione_azienda": "piccola"}` → atteso: tra 3 e 18 mensilità (art. 9 co. 1 dopo C. Cost. 118/2025): massimo 18.000 euro; nel testo anteriore alla sentenza il massimo era 6.000
  - Piccola, 1 anno: minimo dimezzato: `{"anni_servizio": 1, "retribuzione_mensile": 2000, "dimensione_azienda": "piccola"}` → atteso: 3 mensilità, 6.000 euro (metà di 6, art. 9 co. 1)
  - Reintegra, datore grande, 3 anni: `{"anni_servizio": 3, "retribuzione_mensile": 2000, "tipo": "reintegra"}` → atteso: retribuzioni dal licenziamento alla reintegrazione, dedotto l'aliunde perceptum, entro 12 mensilità (24.000 euro), indipendenti dall'anzianità (art. 3 co. 2); il tool dà 6 mensilità (12.000)
  - Reintegra chiesta per un datore sotto soglia: `{"anni_servizio": 3, "retribuzione_mensile": 2000, "dimensione_azienda": "piccola", "tipo": "reintegra"}` → atteso: reintegra dell'art. 3 co. 2 non applicabile ai datori sotto soglia (art. 9 co. 1): solo tutela indennitaria di 3-18 mensilità; il tool restituisce comunque 12.000 euro

### `indennita_preavviso`

Indennità sostitutiva del preavviso per i CCNL commercio (Terziario Confcommercio), metalmeccanici industria e studi professionali per livello, anzianità e tipo di recesso, oppure sui giorni di preavviso forniti dal chiamante.

- Parametri: `ccnl: str (commercio, metalmeccanici, studi_professionali); livello: str (commercio: quadri_1, 2_3, 4_5, 6_7; metalmeccanici: A1_B2_B3, B1_C2_C3, C1_D1_D2; studi_professionali: 1, 2, 3S_3, 4S_4, 5); anzianita_anni: float (>= 0; fasce fino a 5, oltre 5 fino a 10, oltre 10); retribuzione_mensile: float (> 0); tipo: str = 'licenziamento' (licenziamento, dimissioni); giorni_preavviso: float \| None = None (se passato la tabella non è letta); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: Artt. 2118-2119 c.c.; CCNL di settore (tabella preavviso_ccnl, verifica manuale del 19/09/2026)
- Casi di prova:
  - Commercio 2_3, 5 anni esatti: confine della prima fascia: `{"ccnl": "commercio", "livello": "2_3", "anzianita_anni": 5.0, "retribuzione_mensile": 1800}` → atteso: 30 giorni e 1.800,00 euro (1.800/30 x 30) se 5 anni esatti stanno nella fascia fino a 5 anni: da confermare sul CCNL
  - Commercio 2_3, 5 anni e mezzo: `{"ccnl": "commercio", "livello": "2_3", "anzianita_anni": 5.5, "retribuzione_mensile": 1800}` → atteso: 45 giorni, 2.700,00 euro (fascia oltre 5 fino a 10), da leggere dalla fonte
  - Metalmeccanici B1_C2_C3, 10 anni esatti: `{"ccnl": "metalmeccanici", "livello": "B1_C2_C3", "anzianita_anni": 10.0, "retribuzione_mensile": 2200}` → atteso: 60 giorni, 4.400,00 euro (fascia oltre 5 fino a 10), da leggere dalla fonte
  - Metalmeccanici B1_C2_C3, oltre 10 anni: `{"ccnl": "metalmeccanici", "livello": "B1_C2_C3", "anzianita_anni": 10.5, "retribuzione_mensile": 2200}` → atteso: 75 giorni, 5.500,00 euro, da leggere dalla fonte
  - Studi professionali livello 1, dimissioni con oltre 10 anni: `{"ccnl": "studi_professionali", "livello": "1", "anzianita_anni": 11, "retribuzione_mensile": 3000, "tipo": "dimissioni"}` → atteso: 135 giorni, 13.500,00 euro, da leggere dalla tabella del CCNL vigente
  - Giorni forniti dal chiamante per un CCNL non in tabella: `{"ccnl": "edilizia", "livello": "operaio", "anzianita_anni": 3, "retribuzione_mensile": 2400, "giorni_preavviso": 45}` → atteso: 3.600,00 euro (2.400/30 x 45: indennità pari alla retribuzione del periodo, art. 2118 co. 2 c.c.); nessuna tabella letta né avviso di vintage

### `offerta_conciliativa`

Offerta di conciliazione esente da IRPEF e contributi ex art. 6 D.Lgs. 23/2015: una mensilità per anno di servizio tra 3 e 27 mensilità, dimezzata per i datori sotto soglia (1,5-13,5 dopo C. Cost. 118/2025).

- Parametri: `anni_servizio: float (> 0); retribuzione_mensile: float (> 0); dimensione_azienda: str = 'grande' (grande, piccola)`
- Fonte normativa dichiarata: D.Lgs. 23/2015 artt. 6 e 9; C. Cost. 118/2025
- Casi di prova:
  - Datore grande, 5 anni: `{"anni_servizio": 5, "retribuzione_mensile": 2000}` → atteso: 5 mensilità, 10.000 euro (art. 6 co. 1)
  - Datore grande, 2 anni: minimo: `{"anni_servizio": 2, "retribuzione_mensile": 2000}` → atteso: 3 mensilità, 6.000 euro (minimo dell'art. 6 co. 1)
  - Datore grande, 30 anni: massimo: `{"anni_servizio": 30, "retribuzione_mensile": 1000}` → atteso: 27 mensilità, 27.000 euro (massimo dell'art. 6 co. 1)
  - Datore sotto soglia, 30 anni: tetto dopo C. Cost. 118/2025: `{"anni_servizio": 30, "retribuzione_mensile": 1000, "dimensione_azienda": "piccola"}` → atteso: 13,5 mensilità, 13.500 euro (metà di 27, art. 9 co. 1 senza il tetto di 6); 6.000 euro nel testo anteriore alla sentenza
  - Datore sotto soglia, 1 anno: minimo dimezzato: `{"anni_servizio": 1, "retribuzione_mensile": 2000, "dimensione_azienda": "piccola"}` → atteso: 1,5 mensilità, 3.000 euro (metà di 3)
  - Frazione d'anno: `{"anni_servizio": 3.5, "retribuzione_mensile": 2000}` → atteso: 3,5 mensilità, 7.000 euro (frazione riproporzionata, art. 8)

### `scadenze_licenziamento`

Scadenze di decadenza per impugnare il licenziamento: 60 giorni dalla comunicazione per l'impugnazione stragiudiziale, 180 giorni dall'impugnazione per il ricorso o la richiesta di conciliazione o arbitrato, 60 giorni dal rifiuto o dal mancato accordo; giorni di calendario senza sospensione feriale.

- Parametri: `data_licenziamento: str (YYYY-MM-DD, ricezione della comunicazione); data_impugnazione: str \| None = None (YYYY-MM-DD, invio dell'impugnazione); data_rifiuto_conciliazione: str \| None = None (YYYY-MM-DD)`
- Fonte normativa dichiarata: Art. 6 L. 604/1966 nel testo dell'art. 32 L. 183/2010 e dell'art. 1 co. 38 L. 92/2012; rito Fornero abrogato dal D.Lgs. 149/2022
- Casi di prova:
  - Licenziamento ricevuto il 01/01/2025: 60° giorno di domenica: `{"data_licenziamento": "2025-01-01"}` → atteso: impugnazione entro il 02/03/2025 (domenica), 03/03/2025 se si applica l'art. 2963 co. 3 c.c.; senza data_impugnazione deposito entro il 29/08/2025 (180 giorni dal 60°, agosto computato perché nelle cause di lavoro non c'è sospensione feriale)
  - Impugnazione inviata il 10/06/2025: 180° giorno di domenica seguita dall'Immacolata: `{"data_licenziamento": "2025-06-01", "data_impugnazione": "2025-06-10"}` → atteso: impugnazione entro il 31/07/2025; deposito del ricorso entro il 07/12/2025 (domenica); con proroga festiva il 09/12/2025, perché l'08/12 è festivo
  - Rifiuto della conciliazione il 01/10/2025: `{"data_licenziamento": "2025-06-01", "data_impugnazione": "2025-06-10", "data_rifiuto_conciliazione": "2025-10-01"}` → atteso: deposito entro il 30/11/2025 (domenica; 60 giorni dal rifiuto, art. 6 co. 2); 01/12/2025 con proroga festiva
  - Licenziamento ricevuto il 15/07/2026: termine che attraversa agosto: `{"data_licenziamento": "2026-07-15"}` → atteso: impugnazione entro il 13/09/2026 (domenica; 14/09/2026 con proroga), senza sospensione feriale: con la sospensione sarebbe il 14/10/2026, errore da escludere; deposito senza data_impugnazione entro il 12/03/2027
  - Impugnazione tardiva: `{"data_licenziamento": "2025-06-01", "data_impugnazione": "2025-08-01"}` → atteso: decadenza: impugnazione inviata dopo il 31/07/2025, 60° giorno (art. 6 co. 1); il tool deve avvisare

## diritto_penale.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `aumenti_riduzioni_pena` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-aumenti-riduzioni-pena.php (alta) | Normattiva: artt. 63, 64, 65, 66, 67, 69 e 99 c.p. | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7); grado INDICATIVO. tests/comparison/test_diritto_penale.py contiene solo verifiche aritmetiche senza il sito. Il sito applica fino a quattro variazioni consecutive per frazioni su pena in anni, mesi e giorni: passare percentuali a quattro decimali (33.3333, 66.6667) e confrontare dopo aver convertito i decimali di mese in giorni. Il tool non applica i limiti dell'art. 66 (trent'anni di reclusione, cinque di arresto, triplo del massimo) né dell'art. 67 c.p. (non sotto un quarto con più attenuanti ad effetto comune), non esegue il bilanciamento dell'art. 69 tra circostanze eterogenee, non distingue le circostanze ad effetto speciale (art. 63 co. 3) e l'aumento fisso di un terzo per la recidiva vale solo per l'art. 99 co. 1; manca un parametro sulla specie di pena, necessario per i limiti dell'art. 66. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `conversione_pena` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-conversione-pena-detentiva-pecuniaria.php (alta) | Normattiva: art. 135 c.p.; art. 56-quater L. 689/1981 per la pena pecuniaria sostitutiva | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7). Il benchmark deve confermare il tasso di 250 euro (art. 135 c.p. come modificato dalla L. 94/2009) e la regola della frazione: il tool conta ogni frazione di 250 euro come un giorno, il sito esclude i centesimi ed esprime la pena convertita in anni, mesi e giorni senza frazioni di giorno. Il parametro tipo_pena non incide sul calcolo (corretto per l'art. 135) e non è validato. Il ragguaglio non vale per la pena pecuniaria sostitutiva (art. 56-quater L. 689/1981 dopo il D.Lgs. 150/2022, valore giornaliero tra 5 e 2.500 euro): il docstring dovrebbe dirlo per evitare usi impropri. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `fine_pena` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-fine-pena-liberazione-anticipata.php (alta) | Normattiva: art. 54 L. 354/1975; art. 14 c.p.; norme sull'esecuzione modificate dal DL 92/2024 conv. L. 112/2024 | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7); grado INDICATIVO. Il sito simula fine pena, liberazione anticipata, presofferto e interruzioni e calcola la fine pena virtuale. Punti da confermare: il tool aggiunge i mesi alla data di inizio senza computare il primo giorno come giorno di pena espiata (possibile differenza di un giorno); usa semestri di 180 giorni invece di semestri a calendario comune (art. 14 c.p.); calcola i semestri sull'intera pena nominale, mentre il sito potrebbe contarli solo fino alla fine pena virtuale; converte le frazioni di mese a 30 giorni con arrotondamento bancario; la liberazione anticipata speciale di 75 giorni (DL 146/2013, temporanea) offerta dal sito non ha corrispondente. Verificare con cite_law le modifiche del 2024 all'esecuzione (DL 92/2024 conv. L. 112/2024) sull'indicazione della fine pena con le detrazioni. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `pena_concordata` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-aumenti-riduzioni-pena.php (alta) | Normattiva: art. 444 c.p.p.; artt. 62-bis, 65 e 163 c.p. | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7); grado INDICATIVO. Il sito non ha un calcolatore specifico del patteggiamento: si usa la pagina degli aumenti e riduzioni con due diminuzioni consecutive di un terzo (il sito la indica per patteggiamento e abbreviato). Il benchmark deve confermare i confini: pena finale di 60 mesi ammessa (art. 444 co. 1 c.p.p., pena che non supera cinque anni) e sospensione condizionale fino a 24 mesi (art. 163 co. 1 c.p.). Lacune: la diminuzione del rito è fino a un terzo e il tool applica sempre il massimo, come per le generiche (art. 65 n. 3 c.p.); non considera le esclusioni dal patteggiamento oltre due anni (art. 444 co. 1-bis c.p.p.) né i limiti più alti di sospensione per i minori (tre anni) e per chi ha meno di ventuno o più di settanta anni (due anni e sei mesi, art. 163 co. 2 e 3 c.p.). Fase 0: il sito non ha una pagina dedicata al patteggiamento; resta il calcolatore di aumenti e riduzioni. |
| `prescrizione_reato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-reati.php (alta) | Normattiva: artt. 157, 159, 160, 161 e 161-bis c.p.; art. 344-bis c.p.p.; art. 2 co. 5 L. 134/2021; Cass. SS.UU. n. 20989/2025 e Corte cost. n. 38/2026 sul regime Orlando | Audit settembre 2026: corretto al par. 5 (regime scelto dalla data del fatto: ordinario fino al 02/08/2017, Orlando dal 03/08/2017 al 31/12/2019, dal 01/01/2020 blocco dopo il primo grado ex art. 161-bis c.p. e improcedibilità ex art. 344-bis c.p.p. con 3 anni e 18 mesi per le impugnazioni proposte entro il 31/12/2024; aumento per le interruzioni graduato sulla recidiva); non compare nel par. 7. Il calcolatore del sito richiede la registrazione (tests/comparison/test_prescrizione.py è skippato) e copre solo i regimi ex e ante L. 251/2005: confrontarlo sui casi del regime ordinario e usare solo_norma per gli altri. La ricerca web trova Cass. SS.UU. n. 20989/2025 e Corte cost. n. 38/2026 che confermano le sospensioni Orlando per i fatti 2017-2019, in linea con il tool; il disegno di legge sulla prescrizione approvato dalla Camera il 16/01/2024 risulta ancora all'esame del Senato: verificare che non sia divenuto legge. Fissare LEGAL_TODAY, perché prescritto e giorni_alla_prescrizione dipendono dalla data corrente. Il tool non aumenta il termine base per le aggravanti ad effetto speciale, compresa la recidiva qualificata (art. 157 co. 2 c.p.). Fase 0: pagina confermata dal crawl (era a confidenza bassa). |

### `aumenti_riduzioni_pena`

Applica in sequenza alla pena base in mesi la recidiva semplice (+1/3), le aggravanti e le attenuanti espresse in percentuale, con il dettaglio dei passaggi.

- Parametri: `pena_base_mesi: float (>= 0); aggravanti: list[{'tipo': str, 'aumento_pct': float}] \| None = None; attenuanti: list[{'tipo': str, 'riduzione_pct': float}] \| None = None; recidiva: bool = False`
- Fonte normativa dichiarata: Artt. 63-69 c.p. (aumenti e diminuzioni); art. 99 c.p. (recidiva)
- Casi di prova:
  - Esempio della pagina del sito: 5 anni e 4 mesi aumentati di due terzi: `{"pena_base_mesi": 64, "aggravanti": [{"tipo": "aumento di due terzi", "aumento_pct": 66.6667}]}` → atteso: 106,67 mesi, pari a 8 anni, 10 mesi e 20 giorni (64 più 2/3 di 64)
  - Quattro attenuanti di un terzo: limite dell'art. 67: `{"pena_base_mesi": 12, "attenuanti": [{"tipo": "attenuante 1", "riduzione_pct": 33.3333}, {"tipo": "attenuante 2", "riduzione_pct": 33.3333}, {"tipo": "attenuante 3", "riduzione_pct": 33.3333}, {"tipo": "attenuante 4", "riduzione_pct": 33.3333}]}` → atteso: 3 mesi: con più attenuanti ad effetto comune la pena non può scendere sotto un quarto (art. 67 co. 2 c.p.); il tool restituisce 2,37 mesi (12 x (2/3)^4); il sito, aritmetico, va letto
  - Reclusione con recidiva e due aggravanti: limite dell'art. 66: `{"pena_base_mesi": 240, "aggravanti": [{"tipo": "art. 61 n. 1 c.p.", "aumento_pct": 33.3333}, {"tipo": "aggravante ad effetto speciale", "aumento_pct": 50}], "recidiva": true}` → atteso: 360 mesi: con più aggravanti la reclusione non può superare trent'anni (art. 66 n. 1 c.p.); il tool restituisce 640 mesi (53 anni e 4 mesi)
  - Aggravante e attenuante concorrenti: `{"pena_base_mesi": 36, "aggravanti": [{"tipo": "art. 61 n. 7 c.p.", "aumento_pct": 33.3333}], "attenuanti": [{"tipo": "art. 62-bis c.p.", "riduzione_pct": 33.3333}]}` → atteso: Bilanciamento dell'art. 69 c.p.: 36 mesi se equivalenti, 24 se prevalgono le attenuanti, 48 se prevalgono le aggravanti; il tool applica entrambe in sequenza e dà 32 mesi, corretto solo per circostanze sottratte al bilanciamento; il sito calcola in sequenza: da leggere dal sito

### `conversione_pena`

Ragguaglio tra pena detentiva e pena pecuniaria a 250 euro per giorno, in entrambe le direzioni, con arrotondamento per eccesso della frazione di 250 euro.

- Parametri: `importo: float (>= 0; giorni o euro secondo la direzione); direzione: str = 'detentiva_a_pecuniaria' ['detentiva_a_pecuniaria', 'pecuniaria_a_detentiva']; tipo_pena: str = 'reclusione' ['reclusione', 'arresto'] (non validato, non incide sul calcolo)`
- Fonte normativa dichiarata: Art. 135 c.p., 250 euro per giorno
- Casi di prova:
  - Da detentiva a pecuniaria: `{"importo": 30, "direzione": "detentiva_a_pecuniaria"}` → atteso: 7.500 euro (art. 135 c.p.: 250 euro per ogni giorno)
  - Da pecuniaria a detentiva con frazione: `{"importo": 600, "direzione": "pecuniaria_a_detentiva"}` → atteso: 3 giorni: 250 euro o frazione di 250 euro valgono un giorno (art. 135 c.p.); se il sito tronca la frazione ottiene 2: da leggere dal sito
  - Confine esatto di 250 euro: `{"importo": 250, "direzione": "pecuniaria_a_detentiva"}` → atteso: 1 giorno
  - Importo elevato espresso dal sito in anni, mesi e giorni: `{"importo": 91250, "direzione": "pecuniaria_a_detentiva", "tipo_pena": "arresto"}` → atteso: 365 giorni (tipo_pena non incide); il sito esprime il risultato in anni, mesi e giorni: da leggere dal sito la convenzione di conversione

### `fine_pena`

Data di fine pena dalla data di inizio esecuzione e dalla durata in mesi, sottraendo il presofferto e calcolando la liberazione anticipata di 45 giorni per semestre.

- Parametri: `data_inizio_pena: str (YYYY-MM-DD); pena_totale_mesi: float (>= 0); liberazione_anticipata: bool = True; giorni_presofferto: int = 0`
- Fonte normativa dichiarata: Art. 54 L. 354/1975 (ordinamento penitenziario)
- Casi di prova:
  - Due anni senza liberazione anticipata: `{"data_inizio_pena": "2024-01-01", "pena_totale_mesi": 24, "liberazione_anticipata": false}` → atteso: Il tool dà 2026-01-01; se il giorno di inizio si computa come giorno di pena espiata, come nella prassi degli uffici esecuzione, la fine pena è 2025-12-31: da leggere dal sito
  - Due anni con liberazione anticipata: `{"data_inizio_pena": "2024-01-01", "pena_totale_mesi": 24, "liberazione_anticipata": true}` → atteso: Il tool conta 4 semestri e 180 giorni di detrazione (45 per semestre, art. 54 L. 354/1975): fine con liberazione 2025-07-05; se il sito conta solo i semestri espiati prima della fine pena virtuale ne trova 3 (135 giorni): da leggere dal sito
  - Pena di poco inferiore a tre semestri: `{"data_inizio_pena": "2025-03-10", "pena_totale_mesi": 17.95, "liberazione_anticipata": true}` → atteso: Pena di 17 mesi e 28 giorni: i semestri compiuti a calendario sono 2 (90 giorni, art. 54 L. 354/1975 e art. 14 c.p.); il tool divide 546 giorni per 180, ne conta 3 (135 giorni) e dà fine con liberazione 2026-04-25 invece di 2026-06-09 (fine pena del tool 2026-09-07)
  - Presofferto di 30 giorni: `{"data_inizio_pena": "2024-06-01", "pena_totale_mesi": 12, "liberazione_anticipata": true, "giorni_presofferto": 30}` → atteso: Inizio effettivo 2024-05-02, fine pena 2025-05-02 nel tool, 2 semestri e 90 giorni: fine con liberazione 2025-02-01; il sito verifica anche se il presofferto è utile alla liberazione anticipata: da leggere dal sito

### `pena_concordata`

Simula la pena patteggiata applicando alla pena base le attenuanti generiche (-1/3) e la diminuente del rito (-1/3), con verifica del limite di cinque anni e della sospendibilità entro due anni.

- Parametri: `pena_base_mesi: float (>= 0); attenuanti_generiche: bool = True; diminuente_rito: bool = True`
- Fonte normativa dichiarata: Art. 444 c.p.p.; art. 62-bis c.p.
- Casi di prova:
  - Tre anni con generiche e rito: `{"pena_base_mesi": 36}` → atteso: 16 mesi (36 meno un terzo = 24, meno un terzo = 16: art. 62-bis c.p. e art. 444 c.p.p.), patteggiamento_possibile true, sospendibile true; sul sito 3 anni con due riduzioni di 1/3 = 1 anno e 4 mesi
  - Pena finale esattamente di cinque anni: `{"pena_base_mesi": 135}` → atteso: 60 mesi: patteggiamento_possibile true (la pena non supera cinque anni, art. 444 co. 1 c.p.p.), sospendibile false
  - Pena finale appena sopra cinque anni: `{"pena_base_mesi": 136}` → atteso: 60,44 mesi: patteggiamento_possibile false
  - Pena finale esattamente di due anni: `{"pena_base_mesi": 54}` → atteso: 24 mesi: sospendibile true (pena non superiore a due anni, art. 163 co. 1 c.p.)
  - Solo diminuente del rito: `{"pena_base_mesi": 37, "attenuanti_generiche": false, "diminuente_rito": true}` → atteso: 24,67 mesi: patteggiamento_possibile true, sospendibile false

### `prescrizione_reato`

Termine e data di prescrizione del reato con regime scelto dalla data del fatto (ordinario, Orlando, blocco dopo il primo grado) e, per i fatti dal 2020, termini di improcedibilità dell'impugnazione ex art. 344-bis c.p.p.

- Parametri: `pena_massima_anni: float (>= 0); data_commissione: str (YYYY-MM-DD); interruzioni_giorni: int = 0 (> 0 attiva l'aumento massimo dell'art. 161 co. 2); sospensioni_giorni: int = 0; tipo_reato: str = 'delitto' ['delitto', 'contravvenzione']; recidiva: str = 'nessuna' ['nessuna', 'aggravata', 'reiterata', 'abituale']; data_sentenza_primo_grado: str \| None = None; data_sentenza_appello: str \| None = None; data_impugnazione: str \| None = None`
- Fonte normativa dichiarata: Artt. 157-161 c.p. (L. 251/2005) per i fatti fino al 02/08/2017; art. 159 co. 2 c.p. (L. 103/2017) per i fatti dal 03/08/2017 al 31/12/2019; art. 161-bis c.p. (L. 3/2019 e L. 134/2021) e art. 344-bis c.p.p. per i fatti dal 01/01/2020
- Casi di prova:
  - Delitto con pena massima sotto il minimo, regime ordinario, interruzioni: `{"pena_massima_anni": 5, "data_commissione": "2016-03-10", "interruzioni_giorni": 1}` → atteso: Termine base 6 anni (minimo per i delitti, art. 157 co. 1 c.p.) prolungato di un quarto per le interruzioni (art. 161 co. 2) a 7 anni e 6 mesi: 2023-09-10
  - Ultimo giorno del regime ordinario con sospensioni: `{"pena_massima_anni": 4.5, "data_commissione": "2017-08-02", "sospensioni_giorni": 60}` → atteso: Regime ordinario (la L. 103/2017 vale per i fatti dal 03/08/2017): 6 anni più 60 giorni di sospensione, 2023-10-01
  - Fatto nel periodo Orlando con condanna di primo grado: `{"pena_massima_anni": 6, "data_commissione": "2018-06-01", "interruzioni_giorni": 1, "data_sentenza_primo_grado": "2022-01-10"}` → atteso: 7 anni e 6 mesi: 2025-12-01; dopo la condanna di primo grado il corso è sospeso fino alla sentenza di appello per non oltre 1 anno e 6 mesi (art. 159 co. 2 n. 1 c.p. nel testo della L. 103/2017): al più tardi 2027-06-01
  - Contravvenzione dal 2020 con primo grado e impugnazione nel regime transitorio: `{"pena_massima_anni": 1, "data_commissione": "2021-05-15", "tipo_reato": "contravvenzione", "interruzioni_giorni": 1, "data_sentenza_primo_grado": "2024-02-01", "data_impugnazione": "2024-03-01"}` → atteso: Termine 4 anni (minimo per le contravvenzioni) più un quarto = 5 anni, 2026-05-15, ma la sentenza di primo grado ferma la prescrizione (art. 161-bis c.p.); improcedibilità in appello 3 anni per impugnazione entro il 31/12/2024 (art. 2 co. 5 L. 134/2021) dalla decorrenza stimata 2024-05-16 (15 + 90 giorni, art. 344-bis co. 3 c.p.p.): 2027-05-16
  - Delitto dal 2020 con impugnazione nel regime ordinario di improcedibilità: `{"pena_massima_anni": 10, "data_commissione": "2021-03-01", "interruzioni_giorni": 1, "data_sentenza_primo_grado": "2025-06-30", "data_sentenza_appello": "2027-01-15", "data_impugnazione": "2025-09-15"}` → atteso: Appello 2 anni dal 2025-10-13 = 2027-10-13; Cassazione 1 anno dal 2027-04-30 = 2028-04-30 (art. 344-bis co. 1-3 c.p.p.); data di prescrizione teorica 2033-09-01, cessata con il primo grado
  - Recidiva reiterata con interruzioni: `{"pena_massima_anni": 6, "data_commissione": "2015-05-10", "interruzioni_giorni": 1, "recidiva": "reiterata"}` → atteso: Il tool applica solo l'aumento di due terzi per le interruzioni (art. 161 co. 2): 10 anni, 2025-05-10; se la recidiva reiterata rileva anche come aggravante ad effetto speciale nel termine base (art. 157 co. 2 c.p., orientamento da riscontrare) il termine base sale a 9 anni (aumento della metà, art. 99 co. 4) e il massimo a 15 anni, 2030-05-10: da leggere dal sito, che chiede se ricorre la recidiva

## diritto_societario.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `costi_costituzione` | calcolo | fonte_ufficiale | nessuna pagina del sito | Agenzia delle Entrate: imposta fissa di registro (Tariffa parte I DPR 131/1986) e tassa di concessione governativa sui libri sociali (art. 23 Tariffa DPR 641/1972); Camere di commercio: diritti di segreteria, imposta di bollo e diritto annuale per l'iscrizione al registro delle imprese; Normattiva per gli artt. 2327, 2342, 2463 e 2463-bis c.c. e l'art. 3 DL 1/2012 | Corretto dall'audit (par. 5): 25% dei conferimenti in denaro nella s.p.a. (art. 2342 co. 2, non 3/10) ed esenzione dai diritti di segreteria per la s.r.l.s. (art. 3 co. 3 DL 1/2012). Il benchmark (fonte ufficiale) deve confermare gli importi 2026 di registro (200), bollo (156), diritti di segreteria (90 e 18), bollo della ditta individuale (17,50), diritto annuale e tassa di concessione governativa (309,87 fino a 516.456,90 euro di capitale, 516,46 oltre). Da segnalare: per la s.r.l. il tool cita il D.M. 55/2014 (parametri forensi degli avvocati), estraneo ai costi notarili (parametri notarili DM 265/2012); la s.r.l.s. non ha la tassa di concessione governativa, che il DL 1/2012 non esenta; il diritto annuale è un costo ricorrente presentato come costo di costituzione; gli onorari notarili sono stime non riscontrabili su fonte pubblica e restano INDICATIVO. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `quorum_assembleari` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 2368, 2369, 2479, 2479-bis, 2484, 2487 e 2538 c.c. nel testo vigente | Declassato dall'audit (par. 7, confidenza alta): nota nel docstring, valori da riscrivere su art. 2368 co. 2 per le s.p.a. non quotate e art. 2479-bis co. 3 per le s.r.l. Il benchmark (cite_law) deve confermare le divergenze dei casi: straordinaria di s.p.a. che non fa ricorso al mercato del capitale di rischio approvata con il voto favorevole di più della metà del capitale sociale (art. 2368 co. 2 primo periodo), non con metà presente e due terzi dei presenti (regime delle società aperte); s.r.l. costituita con almeno metà del capitale e delibera a maggioranza assoluta dei presenti, con almeno metà del capitale favorevole nei casi dell'art. 2479 co. 2 n. 4 e 5 (il tool non richiede quorum costitutivo e pretende più della metà del capitale totale); scioglimento di s.r.l. ai due terzi senza base (l'art. 2484 non fissa maggioranze: valgono quelle delle modifiche dell'atto costitutivo, art. 2487 co. 1); seconda convocazione di s.p.a. per lo scioglimento con oltre un terzo del capitale presente e voto favorevole di oltre un terzo (art. 2369 co. 3 e 5), non la metà; cooperative con quorum fissati dall'atto costitutivo e calcolati sui voti (art. 2538). Il tool valuta solo la prima convocazione e ignora le clausole statutarie. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `scadenze_societarie` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 2364 co. 2, 2366, 2429, 2435 co. 1, 2478-bis e 2479-bis c.c. | Non citato ai par. 5 e 7. Il benchmark (cite_law) deve confermare i termini e il computo a giorni di calendario (nell'anno bisestile 120 giorni dal 31/12 scadono il 29/04), il maggior termine di 180 giorni subordinato alla clausola statutaria e alla motivazione nella relazione sulla gestione (art. 2364 co. 2; per le s.r.l. art. 2478-bis co. 1), l'assenza di sospensione feriale. Da segnalare: manca la comunicazione del progetto di bilancio al collegio sindacale e al revisore almeno 30 giorni prima dell'assemblea (art. 2429 co. 1); l'iscrizione del verbale di approvazione è attribuita all'art. 2436, che riguarda le modificazioni dello statuto, mentre il verbale si deposita con il bilancio (art. 2435 co. 1); convenzione sui giorni liberi per le convocazioni; nessuna regola per le scadenze che cadono in giorno festivo. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |
| `soglie_organo_controllo_srl` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: art. 2477 c.c. nel testo vigente; art. 379 D.Lgs. 14/2019 e DL 32/2019 conv. L. 55/2019 | Non citato ai par. 5 e 7. Il benchmark (cite_law) deve confermare nel testo vigente dell'art. 2477 co. 2 lett. c) i limiti di 4 milioni di attivo, 4 milioni di ricavi e 20 dipendenti, introdotti dal DL 32/2019 conv. L. 55/2019 al posto dei 2 milioni, 2 milioni e 10 dipendenti del D.Lgs. 14/2019, e che il recepimento della CSRD (D.Lgs. 125/2024, che ha alzato i limiti degli artt. 2435-bis e 2435-ter) non li abbia toccati; il superamento stretto; il biennio; la cessazione dell'obbligo dopo tre esercizi consecutivi sotto i limiti (co. 3). Da segnalare: il riferimento normativo attribuisce i limiti al D.Lgs. 14/2019; mancano le ipotesi delle lett. a) e b) (bilancio consolidato, controllo di società obbligata alla revisione legale); obbligo_nomina risulta vero già con un solo esercizio sopra soglia. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. |

### `costi_costituzione`

Stima indicativa dei costi di costituzione per s.r.l., s.r.l.s., s.p.a., s.a.s., s.n.c. e ditta individuale (notaio, imposta di registro, bolli, diritti camerali, tassa di concessione governativa) con capitale minimo.

- Parametri: `tipo_societa: str (srl, srls, spa, sas, snc, ditta_individuale)`
- Fonte normativa dichiarata: Artt. 2463, 2463-bis, 2327, 2342 c.c.; DPR 131/1986; DL 1/2012 conv. L. 27/2012; valori 2025-2026 (INDICATIVO; nessuna riga Vigenza)
- Casi di prova:
  - S.r.l. ordinaria: `{"tipo_societa": "srl"}` → atteso: imposta di registro 200 euro (Tariffa parte I DPR 131/1986), tassa di concessione governativa 309,87 (art. 23 Tariffa DPR 641/1972), bollo e diritti da leggere dalla fonte; capitale minimo 1 euro (art. 2463 co. 4); il tool stima 2.375,87-3.375,87 euro
  - S.r.l. semplificata: `{"tipo_societa": "srls"}` → atteso: onorario notarile, bollo e diritti di segreteria esenti (art. 2463-bis c.c., art. 3 co. 3 DL 1/2012), registro 200 dovuto; verificare la tassa di concessione governativa di 309,87, assente nel tool; il tool stima 320 euro
  - S.p.a.: `{"tipo_societa": "spa"}` → atteso: capitale minimo 50.000 euro (art. 2327 c.c.), versamento del 25% dei conferimenti in denaro (art. 2342 co. 2), registro 200, tassa di concessione governativa 309,87; il tool stima 3.375,87-4.875,87
  - Ditta individuale: `{"tipo_societa": "ditta_individuale"}` → atteso: diritti di segreteria 18 euro e bollo 17,50 per l'iscrizione, diritto annuale della sezione speciale da leggere dalla fonte; il tool stima 88,50
  - Tipo non gestito (s.a.p.a.): `{"tipo_societa": "sapa"}` → atteso: errore: tipi ammessi srl, srls, spa, sas, snc, ditta_individuale

### `quorum_assembleari`

Verifica dei quorum costitutivi e deliberativi delle assemblee di s.p.a., s.r.l. e cooperative per delibere ordinarie, straordinarie, modifiche statutarie e scioglimento, sui valori di capitale presente e favorevole forniti.

- Parametri: `tipo_societa: str (spa, srl, cooperativa); tipo_delibera: str (ordinaria, straordinaria, modifica_statuto, scioglimento); capitale_totale: float (> 0; numero di soci per le cooperative); capitale_presente: float = 0; voti_favorevoli: float = 0`
- Fonte normativa dichiarata: Artt. 2368-2369, 2479, 2479-bis, 2484, 2538 c.c. (INDICATIVO; nessuna riga Vigenza)
- Casi di prova:
  - S.p.a. straordinaria: 60% presente, 45% favorevole: `{"tipo_societa": "spa", "tipo_delibera": "straordinaria", "capitale_totale": 100000, "capitale_presente": 60000, "voti_favorevoli": 45000}` → atteso: non approvata per la s.p.a. che non fa ricorso al mercato del capitale di rischio: servono più di 50.000 voti favorevoli (art. 2368 co. 2); il tool la dichiara valida
  - S.p.a. straordinaria: 90% presente, 55% favorevole: `{"tipo_societa": "spa", "tipo_delibera": "straordinaria", "capitale_totale": 100000, "capitale_presente": 90000, "voti_favorevoli": 55000}` → atteso: approvata (55.000 oltre la metà del capitale, art. 2368 co. 2); il tool la dichiara non valida perché sotto i due terzi dei presenti
  - S.p.a. ordinaria: parità esatta tra i presenti: `{"tipo_societa": "spa", "tipo_delibera": "ordinaria", "capitale_totale": 100000, "capitale_presente": 50000, "voti_favorevoli": 25000}` → atteso: assemblea costituita (almeno metà del capitale, art. 2368 co. 1), delibera non approvata: 25.000 su 50.000 non è maggioranza assoluta
  - S.r.l. ordinaria: 60% presente, 40% favorevole: `{"tipo_societa": "srl", "tipo_delibera": "ordinaria", "capitale_totale": 100000, "capitale_presente": 60000, "voti_favorevoli": 40000}` → atteso: approvata: costituita con almeno metà del capitale e maggioranza assoluta dei presenti (40.000 su 60.000), art. 2479-bis co. 3; il tool la dichiara non valida
  - S.r.l. modifica dell'atto costitutivo con esattamente metà del capitale favorevole: `{"tipo_societa": "srl", "tipo_delibera": "modifica_statuto", "capitale_totale": 100000, "capitale_presente": 100000, "voti_favorevoli": 50000}` → atteso: approvata: almeno la metà del capitale sociale (art. 2479-bis co. 3, casi dell'art. 2479 co. 2 n. 4); il tool chiede più della metà e la dichiara non valida
  - S.r.l. scioglimento anticipato con 60% favorevole: `{"tipo_societa": "srl", "tipo_delibera": "scioglimento", "capitale_totale": 100000, "capitale_presente": 100000, "voti_favorevoli": 60000}` → atteso: approvata con la maggioranza delle modifiche dell'atto costitutivo (artt. 2479-bis co. 3 e 2487 co. 1); il tool chiede i due terzi e la dichiara non valida
  - S.p.a. scioglimento anticipato con 40% presente e favorevole: scenario di seconda convocazione: `{"tipo_societa": "spa", "tipo_delibera": "scioglimento", "capitale_totale": 100000, "capitale_presente": 40000, "voti_favorevoli": 40000}` → atteso: non approvata in prima convocazione (serve più della metà del capitale favorevole); approvata in seconda (oltre un terzo presente, due terzi dei presenti, oltre un terzo del capitale favorevole, art. 2369 co. 3 e 5): il tool valuta solo la prima e per la seconda indica la metà del capitale
  - Cooperativa: 40 soci presenti su 100, 30 favorevoli: `{"tipo_societa": "cooperativa", "tipo_delibera": "ordinaria", "capitale_totale": 100, "capitale_presente": 40, "voti_favorevoli": 30}` → atteso: quorum stabiliti dall'atto costitutivo e calcolati sui voti spettanti ai soci (art. 2538 c.c.): esito da leggere sullo statuto; la metà più uno dei soci usata dal tool non è un quorum legale

### `scadenze_societarie`

Scadenze annuali dalla chiusura dell'esercizio: approvazione del bilancio a 120 giorni (180 con clausola statutaria), convocazione dell'assemblea di s.p.a. (15 giorni prima) e di s.r.l. (8 giorni prima), deposito in sede nei 15 giorni precedenti, deposito al registro delle imprese entro 30 giorni dall'approvazione.

- Parametri: `data_chiusura_esercizio: str (YYYY-MM-DD); bilancio_differito: bool = False (maggior termine di 180 giorni ex art. 2364 co. 2)`
- Fonte normativa dichiarata: Artt. 2364, 2366, 2429, 2435, 2436, 2479-bis c.c. (nessuna riga Vigenza)
- Casi di prova:
  - Esercizio chiuso il 31/12/2025: `{"data_chiusura_esercizio": "2025-12-31"}` → atteso: approvazione entro il 30/04/2026 (120 giorni, art. 2364 co. 2); convocazione di s.p.a. entro il 15/04/2026 (15 giorni, art. 2366 co. 2) e di s.r.l. entro il 22/04/2026 (8 giorni, art. 2479-bis co. 1); deposito in sede dal 15/04/2026 (art. 2429 co. 3); deposito al registro delle imprese entro il 30/05/2026 (art. 2435 co. 1)
  - Anno bisestile: chiusura il 31/12/2023: `{"data_chiusura_esercizio": "2023-12-31"}` → atteso: approvazione entro il 29/04/2024 (120 giorni di calendario, compreso il 29 febbraio), deposito entro il 29/05/2024
  - Maggior termine statutario: `{"data_chiusura_esercizio": "2025-12-31", "bilancio_differito": true}` → atteso: approvazione entro il 29/06/2026 (180 giorni, art. 2364 co. 2), deposito entro il 29/07/2026
  - Esercizio non solare chiuso il 30/06/2026: termine che attraversa agosto: `{"data_chiusura_esercizio": "2026-06-30"}` → atteso: approvazione entro il 28/10/2026 con agosto computato (termine sostanziale, nessuna sospensione feriale); convocazione di s.r.l. entro il 20/10/2026; deposito entro il 27/11/2026

### `soglie_organo_controllo_srl`

Verifica dei limiti dell'art. 2477 c.c. (attivo 4 milioni, ricavi 4 milioni, 20 dipendenti medi) che, se superati per due esercizi consecutivi, obbligano la s.r.l. a nominare l'organo di controllo o il revisore.

- Parametri: `ricavi: float (euro, >= 0); attivo: float (euro, >= 0); dipendenti: int (media dell'esercizio, >= 0)`
- Fonte normativa dichiarata: Art. 2477 c.c. (il tool cita le modifiche del D.Lgs. 14/2019; nessuna riga Vigenza)
- Casi di prova:
  - Valori pari ai limiti: `{"ricavi": 4000000, "attivo": 4000000, "dipendenti": 20}` → atteso: nessun limite superato: il limite va superato, non raggiunto (art. 2477 co. 2 lett. c)
  - Ricavi appena sopra il limite: `{"ricavi": 4000000.01, "attivo": 1000000, "dipendenti": 5}` → atteso: limite dei ricavi superato: obbligo solo se superato anche nell'esercizio precedente (due esercizi consecutivi)
  - 21 dipendenti medi: `{"ricavi": 1000000, "attivo": 1000000, "dipendenti": 21}` → atteso: limite dei dipendenti superato, con la stessa condizione del biennio
  - Sopra i limiti originari del D.Lgs. 14/2019, sotto quelli vigenti: `{"ricavi": 3000000, "attivo": 3000000, "dipendenti": 15}` → atteso: nessun limite superato con i limiti vigenti (4 milioni, 4 milioni, 20); con quelli originari del D.Lgs. 14/2019 (2 milioni, 2 milioni, 10) sarebbero superati tutti e tre

## eu_implementation.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `elenco_misure_nazionali` | ricerca_online | smoke_live | nessuna (media) | EUR-Lex, scheda della direttiva 2019/790, misure nazionali di recepimento della Francia | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il codice Paese arriva nella query; l'intestazione della risposta ('Recepimento italiano della direttiva') e il messaggio senza risultati ('misura nazionale italiana') sono fissi e diventano errati per un Paese diverso dall'Italia. |
| `get_eu_basis` | ricerca_online | smoke_live | nessuna (alta) | EUR-Lex, Direttiva (UE) 2019/790 (termine di recepimento all'art. 29) | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: un atto nazionale che recepisce più direttive le elenca tutte; il termine di trasposizione coincide con quello dell'articolo della direttiva. |
| `get_italian_implementation` | ricerca_online | smoke_live | nessuna (alta) | EUR-Lex, scheda della direttiva 2019/790, sezione misure nazionali di recepimento; Normattiva per il D.Lgs. 8 novembre 2021 n. 177 | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: numero dell'atto estratto a massimo sforzo dall'identificativo locale; data di GU dichiarata inaffidabile nel codice (valori che iniziano per 1001 scartati); tutti gli atti di recepimento elencati quando sono più di uno. |

### `elenco_misure_nazionali`

Misure nazionali di recepimento di una direttiva UE in un Paese a scelta (codice ISO a tre lettere), per confrontare il recepimento tra Stati membri.

- Parametri: `direttiva: str; paese: str = 'ITA' (es. 'FRA', 'DEU', 'ESP')`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR (SPARQL)
- Casi di prova:
  - Altro Stato membro: `{"direttiva": "direttiva 2019/790", "paese": "FRA"}` → atteso: misure francesi, tra cui la loi n. 2019-775 del 24/07/2019 sui diritti connessi degli editori di stampa e l'ordonnance n. 2021-580 del 12/05/2021 (da riscontrare); l'intestazione che dice 'italiano' è un difetto
  - Italia: `{"direttiva": "direttiva 2019/790", "paese": "ITA"}` → atteso: stesso risultato di get_italian_implementation (D.Lgs. 177/2021)

### `get_eu_basis`

Direttive UE recepite da un atto italiano (mappatura inversa su CELLAR): CELEX, titolo italiano, termine di trasposizione, CELLAR URI.

- Parametri: `atto: str (atto italiano, es. 'D.Lgs. 177/2021', o CELEX della misura nazionale)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR (SPARQL)
- Casi di prova:
  - Atto italiano noto: `{"atto": "D.Lgs. 177/2021"}` → atteso: direttiva 32019L0790 (diritto d'autore e diritti connessi nel mercato unico digitale), termine di trasposizione 2021-06-07, CELLAR URI
  - CELEX della misura nazionale: `{"atto": "72019L0790ITA_202107973"}` → atteso: 32019L0790 (caso del test live esistente)

### `get_italian_implementation`

Atti italiani che recepiscono una direttiva UE (misure nazionali di attuazione su CELLAR): tipo e numero dell'atto, Gazzetta Ufficiale, entrata in vigore, titolo e CELEX della misura; per i regolamenti spiega che non c'è recepimento.

- Parametri: `direttiva: str (CELEX, es. '32019L0790', o riferimento 'direttiva 2019/790')`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: CELLAR, misure nazionali di attuazione (SPARQL)
- Casi di prova:
  - Direttiva nota: `{"direttiva": "direttiva 2019/790"}` → atteso: Decreto legislativo n. 177 (8 novembre 2021), Gazzetta Ufficiale n. 283 del 27/11/2021, entrata in vigore 12/12/2021, CELEX della misura 72019L0790ITA_202107973, direttiva recepita 32019L0790
  - Regolamento: `{"direttiva": "32016R0679"}` → atteso: nessuna misura: regolamento UE direttamente applicabile, rinvio a cite_law

## fatturazione_avvocati.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `calcolo_notula_penale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-penali-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | DM 147/2022, tabelle penali; art. 2 co. 2 DM 55/2014 | Non toccato dall'audit. Compensi dalla stessa tabella di parcella_avvocato_penale; CPA e IVA sempre applicate, senza parametro per escluderle, e nessuna ritenuta. Confrontare con il risultato del calcolatore penale del sito (Anno 2022) i totali con spese generali, CPA e IVA. Fase 0: pagina confermata. |
| `fattura_avvocato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_fattura_studio_legale.php (alta) | Art. 13 Tariffa parte I DPR 642/1972; art. 1 co. 54-89 e co. 67 L. 190/2014; art. 25 DPR 600/1973 | Corretto dall'audit (paragrafo 5): aggiunto il bollo di 2 euro nel regime forfettario oltre 77,47 euro. Il test esistente tests/comparison/test_fattura_avvocato.py è solo aritmetico. Il benchmark deve confermare sul sito la soglia del bollo (77,47 escluso, 77,48 incluso) calcolata su compenso più CPA, l'assenza di IVA e ritenuta nel forfettario e la ritenuta sul solo compenso (CPA esclusa) nell'ordinario. Attenzione all'etichetta: il campo totale_fattura del tool coincide con netto_a_pagare (1.068,80 nel primo caso), mentre il totale documento prima della ritenuta è 1.268,80; confrontare netto con netto e segnalare l'etichetta. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `modello_notula` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | Art. 13 co. 2 e co. 3 e art. 30 DPR 115/2002 (cite_law); DM 147/2022, Tabella 8 (procedimenti monitori) e tabelle dell'atto di precetto e delle esecuzioni | Non toccato dall'audit. Scostamenti derivabili dalla legge da confermare: (a) il contributo unificato delle esecuzioni è preso dalla tabella di cognizione, mentre l'art. 13 co. 2 DPR 115/2002 prevede importi fissi (43 euro sotto 2.500, 139 da 2.500, 278 per l'immobiliare), già applicati da genera_quotazione_docx dopo l'audit; (b) decreto ingiuntivo, precetto ed esecuzioni sono calcolati con le fasi della tabella di cognizione del tribunale invece che con le tabelle dedicate: per un decreto ingiuntivo di 10.000 euro il tool dà 1.696 euro contro i 567 della fase unica monitoria (valore medio) usata da genera_quotazione_docx; (c) nel precetto aggiunge 27 euro di marca da bollo non dovuti (l'anticipazione forfettaria dell'art. 30 DPR 115/2002 si versa all'iscrizione a ruolo). Pagine del sito da usare: tabelle dei procedimenti monitori, dell'atto di precetto (https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-precetto.html), delle esecuzioni mobiliari (https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-mobiliari.html) e immobiliari (https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-immobiliari.html). La pagina modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php usa il tariffario forense del 2004 e non è confrontabile. Fase 0: l'URL .html del piano non esiste; la pagina delle notule per decreto ingiuntivo, precetto ed esecuzioni e' questa. |
| `nota_spese` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_fattura_studio_legale.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo_nota_spese_avvocati_tariffe_forensi.php | Art. 2 co. 2 DM 55/2014; art. 15 DPR 633/1972 (spese anticipate in nome e per conto del cliente escluse dalla base IVA) | Non toccato dall'audit. Nessun calcolatore del sito replica l'interfaccia per voci: usare il calcolo fattura per avvocati con spese forfettarie 15% e spese esenti. La voce di tipo spese_generali_15pct riceve la base e il tool ne calcola il 15%. Il tool non calcola la ritenuta d'acconto (20% su compensi e spese generali): confrontare i totali prima della ritenuta. Confermare che le spese vive e documentate restino fuori da CPA e IVA. Fase 0: pagina confermata; la pagina 'nota spese con tariffario 2004' e' obsoleta e non pertinente. |
| `parcella_avvocato_civile` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | Ministero della Giustizia, DM 13 agosto 2022 n. 147 (GU Serie Generale n. 236 dell'8/10/2022), tabella dei giudizi ordinari e sommari di cognizione innanzi al tribunale; testo coordinato del DM 55/2014 | Non toccato dall'audit di settembre 2026 (assente dai paragrafi 5 e 7). Il blocco _vintage di parametri_forensi.json dichiara che i valori sono trascritti da avvocatoandreani.it e non dalla Gazzetta Ufficiale: il confronto con il sito verifica la trascrizione, non la norma, e va affiancato dal riscontro sulla tabella in GU. Sul sito selezionare Anno 2022 e Competenza Tribunale (valore 110, come nel test esistente tests/comparison/test_parcella_civile.py, che copre 5 scaglioni con tolleranza di 1 euro da portare a 0,01). Il tool non ha un parametro per il giudice (giudice di pace, corte d'appello, Cassazione): segnalarlo come limite. Da confermare: minimi e massimi pari al medio ridotto o aumentato del 50% (art. 4 co. 1 DM 55/2014 come modificato dal DM 147/2022) con l'arrotondamento all'euro del sito; confini degli scaglioni con i centesimi; valori oltre 520.000 euro, per i quali l'art. 6 prevede un incremento di regola fino al 30% per fascia e il tool applica sempre l'intero 30%, arrotondato fase per fase, anche al livello medio; fascia 'oltre 32.000.000' identica alla precedente. Fase 0: pagina confermata (DM 55/2014); il sito pubblica anche le tabelle e i calcolatori a parametri 2012 e a tariffe 2004, non pertinenti. |
| `parcella_avvocato_penale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-penali-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | DM 147/2022 (GU n. 236 dell'8/10/2022), tabelle dei procedimenti penali; art. 12 co. 1 DM 55/2014 | Non toccato dall'audit. Test esistente tests/comparison/test_parcella_penale.py (3 casi, mappa dei valori Competenza del sito: 500, 570, 580, 590, 600, 630; Anno 2022). Stessa avvertenza sul _vintage (valori trascritti dal sito, da riscontrare in GU). Il tool copre 6 organi: mancano GIP/GUP, tribunale e magistrato di sorveglianza, corte d'assise d'appello e tribunale del riesame, presenti nelle tabelle penali del sito: segnalarli come lacuna di copertura. Da confermare: minimi e massimi pari al medio ridotto o aumentato del 50% e assenza della fase istruttoria in Cassazione. Fase 0: pagina confermata. |
| `parcella_stragiudiziale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | DM 147/2022 (GU n. 236 dell'8/10/2022), tabella dell'attività stragiudiziale | Non toccato dall'audit. Test esistente tests/comparison/test_parcella_stragiudiziale.py (4 casi). Stessa avvertenza sul _vintage. Da confermare: confine 1.100/1.100,01 e trattamento oltre 520.000 euro, per il quale il sito offre due metodi di calcolo mentre il tool restituisce lo stesso valore dello scaglione fino a 520.000 senza incremento (a differenza di parcella_avvocato_civile, che applica l'incremento dell'art. 6). Il tool accetta anche il valore 0 e restituisce il primo scaglione. Fase 0: pagina confermata. |
| `parcella_volontaria_giurisdizione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | DM 147/2022 (GU n. 236 dell'8/10/2022), Tabella 7 | Non toccato dall'audit. Il test esistente tests/comparison/test_volontaria.py è solo aritmetico, senza confronto con il sito. La nota del JSON dichiara un compenso unico per scaglione ripartito 50% studio e 50% trattazione: va confermata sulla Tabella 7 la struttura per fasi (le fonti trovate descrivono fasi di studio, introduttiva, istruttoria o di trattazione e decisionale), l'esistenza di uno scaglione fino a 1.100 euro (il tool parte da 'fino a 5.200') e il valore oltre 520.000 (il tool ripete lo scaglione precedente). Verificare se il calcolatore civile del sito offre la competenza volontaria giurisdizione; altrimenti usare la pagina della tabella. Fase 0: l'URL .html del piano non esiste; verificare se il calcolatore civile offre la volontaria giurisdizione (Tab. 7), altrimenti confrontare con le tabelle DM 55/2014 pubblicate dal sito. |
| `preventivo_civile` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/preventivo-avvocato-civile.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php | Art. 13 co. 1 e art. 30 DPR 115/2002 nel testo vigente (cite_law) | Non toccato dall'audit; il contributo unificato è letto da contributo_unificato.json (vintage 20/09/2026, riscontrato su Normattiva). Confrontare con il preventivo del sito compensi (tribunale, livello medio proposto di default), catena spese generali/CPA/IVA e contributo unificato. Le altre spese vive sono stime senza base normativa (notifica PEC 3,54, notifica dell'ufficiale giudiziario 27, diritti di copia 15) e vanno escluse dal confronto; i 27 euro di iscrizione sono l'anticipazione forfettaria dell'art. 30 DPR 115/2002. Il tool non distingue il giudice (sempre tribunale). Fase 0: pagina confermata. |
| `preventivo_stragiudiziale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/preventivo-avvocato-stragiudiziale.php (alta) | DM 147/2022, tabella dell'attività stragiudiziale | Non toccato dall'audit. Usa la stessa tabella di parcella_stragiudiziale. Da confermare: compenso per scaglione, confine 5.200/5.200,01, trattamento oltre 520.000 (nessun incremento nel tool); la catena spese generali, CPA e IVA è derivabile dalla legge. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `preventivo_volontaria_giurisdizione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php, https://www.avvocatoandreani.it/servizi/preventivo-avvocato-civile.php | DM 147/2022, Tabella 7; art. 2 co. 2 DM 55/2014 (spese generali); art. 11 L. 576/1980 (CPA); art. 16 DPR 633/1972 (IVA) | Non toccato dall'audit. Usa la stessa tabella di parcella_volontaria_giurisdizione: ogni correzione della Tabella 7 si propaga. La catena spese generali 15%, CPA 4% su compensi e spese generali, IVA 22% su compensi, spese generali e CPA è derivabile dalla legge e va asserita al centesimo, anche nel testo_preventivo. Differenza da segnalare rispetto a preventivo_civile: nessuna spesa viva, in particolare manca il contributo unificato della volontaria giurisdizione (98 euro, art. 13 co. 1 lett. b DPR 115/2002). Fase 0: l'URL .html del piano non esiste; stesse pagine della parcella di volontaria giurisdizione. |
| `spese_trasferta_avvocati` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-spese-trasferta-avvocati.php (alta) | Art. 27 DM 55/2014 (testo coordinato); prezzi medi dei carburanti pubblicati dal Ministero delle Imprese e del Made in Italy per l'indennità chilometrica | Docstring riformulato dall'audit (INDICATIVO: importo base e percentuali orarie sono stime), calcolo invariato; non compare nei paragrafi 5 e 7. Scostamenti strutturali attesi rispetto all'art. 27 DM 55/2014: rimborso chilometrico fisso di 0,30 euro/km invece di un quinto del costo del carburante al litro per chilometro; pedaggi e parcheggi documentati assenti; soggiorno senza la maggiorazione del 10% per spese accessorie (limite albergo quattro stelle); indennità di trasferta calcolata al 10/20/40% di un onorario fisso di 540 euro con soglie a 4 e 8 ore che la norma non prevede. Il benchmark deve leggere dal sito come quantifica l'indennità di trasferta e con quale prezzo del carburante, e documentare le differenze senza allineare il tool al sito. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |

### `calcolo_notula_penale`

Parcella penale completa: compensi tabellari con spese generali 15% facoltative, CPA 4% e IVA 22%.

- Parametri: `competenza: str (giudice_pace, tribunale_monocratico, tribunale_collegiale, corte_assise, corte_appello, cassazione); fasi: list[str] \| None = None (studio, introduttiva, istruttoria, decisionale); livello: str = 'medio' (min, medio, max); spese_generali: bool = True`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, parametri forensi penale
- Casi di prova:
  - Tribunale monocratico al medio con spese generali: `{"competenza": "tribunale_monocratico", "fasi": null, "livello": "medio", "spese_generali": true}` → atteso: Compensi 3.592 (da confermare); spese generali 538,80; subtotale 4.130,80; CPA 165,23; imponibile 4.296,03; IVA 945,13; totale 5.241,16.
  - Cassazione al minimo senza spese generali: `{"competenza": "cassazione", "fasi": null, "livello": "min", "spese_generali": false}` → atteso: Compensi 473 + 1.323 + 1.371 = 3.167 (da confermare); CPA 126,68; IVA 724,61; totale 4.018,29.
  - Corte d'assise, due fasi al massimo: `{"competenza": "corte_assise", "fasi": ["studio", "decisionale"], "livello": "max", "spese_generali": true}` → atteso: Compensi 1.134 + 4.253 = 5.387 (da confermare); spese generali 808,05; CPA 247,80; IVA 1.417,43; totale 7.860,28.
  - Fase non disponibile: `{"competenza": "cassazione", "fasi": ["istruttoria"], "livello": "medio", "spese_generali": true}` → atteso: Errore: fase istruttoria non disponibile per la Cassazione.

### `fattura_avvocato`

Struttura della fattura dell'avvocato con CPA 4%, IVA 22% e ritenuta d'acconto 20% nel regime ordinario, bollo di 2 euro nel forfettario.

- Parametri: `imponibile: float; regime: str = 'ordinario' (ordinario, forfettario); cpa: bool = True`
- Fonte normativa dichiarata: L. 190/2014; DPR 633/1972; DPR 600/1973; DPR 642/1972 (bollo di 2 euro oltre 77,47 euro)
- Casi di prova:
  - Regime ordinario con CPA: `{"imponibile": 1000, "regime": "ordinario", "cpa": true}` → atteso: CPA 40,00; imponibile IVA 1.040,00; IVA 228,80; ritenuta 200,00 (20% del compenso, art. 25 DPR 600/1973); totale documento 1.268,80; netto a pagare 1.068,80.
  - Forfettario esattamente sulla soglia del bollo: `{"imponibile": 74.49, "regime": "forfettario", "cpa": true}` → atteso: CPA 2,98; totale 77,47: nessun bollo perché l'importo non supera 77,47 euro (art. 13 Tariffa parte I DPR 642/1972); IVA e ritenuta a zero.
  - Forfettario un centesimo sopra la soglia: `{"imponibile": 74.5, "regime": "forfettario", "cpa": true}` → atteso: CPA 2,98; importo 77,48: bollo 2,00; totale 79,48; nessuna IVA (art. 1 co. 54-89 L. 190/2014) e nessuna ritenuta (art. 1 co. 67).
  - Ordinario senza CPA: `{"imponibile": 1000, "regime": "ordinario", "cpa": false}` → atteso: IVA 220,00; ritenuta 200,00; netto 1.020,00.

### `modello_notula`

Notula formattata per decreto ingiuntivo, precetto, esecuzione mobiliare o immobiliare, con compensi, accessori e spese vive stimate.

- Parametri: `tipo_procedimento: str (decreto_ingiuntivo, precetto, esecuzione_mobiliare, esecuzione_immobiliare); avvocato: str; cliente: str; valore_causa: float; fasi: list[str] \| None = None (studio, introduttiva, istruttoria, decisionale); livello: str = 'medio' (min, medio, max)`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022; contributo unificato DPR 115/2002
- Casi di prova:
  - Decreto ingiuntivo da 10.000 euro al medio: `{"tipo_procedimento": "decreto_ingiuntivo", "avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "valore_causa": 10000, "fasi": null, "livello": "medio"}` → atteso: Contributo unificato 118,50 (237 ridotto alla metà, art. 13 co. 3 DPR 115/2002) e 27 euro di anticipazione forfettaria: corretti. Compenso atteso dalla tabella dei procedimenti monitori, fase unica, scaglione 5.200,01-26.000, valore medio 567 (da confermare sul sito); il tool usa studio 919 + introduttiva 777 = 1.696 e un totale notula di 2.620,17.
  - Esecuzione mobiliare sotto 2.500 euro: `{"tipo_procedimento": "esecuzione_mobiliare", "avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "valore_causa": 2000, "fasi": null, "livello": "medio"}` → atteso: Contributo unificato 43 euro (art. 13 co. 2 DPR 115/2002); il tool indica 98. Compensi dalla tabella delle esecuzioni mobiliari (da leggere dal sito); il tool usa studio, introduttiva e istruttoria della cognizione (1.701).
  - Esecuzione mobiliare sulla soglia di 2.500 euro: `{"tipo_procedimento": "esecuzione_mobiliare", "avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "valore_causa": 2500, "fasi": null, "livello": "medio"}` → atteso: Contributo unificato 139 euro (art. 13 co. 2, da 2.500 in su); il tool indica 98.
  - Esecuzione immobiliare da 100.000 euro: `{"tipo_procedimento": "esecuzione_immobiliare", "avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "valore_causa": 100000, "fasi": null, "livello": "medio"}` → atteso: Contributo unificato 278 euro (art. 13 co. 2); il tool indica 759 più una trascrizione stimata di 300. Compensi dalla tabella delle esecuzioni immobiliari (da leggere dal sito); il tool usa le quattro fasi della cognizione (14.103).
  - Atto di precetto al minimo: `{"tipo_procedimento": "precetto", "avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "valore_causa": 3000, "fasi": null, "livello": "min"}` → atteso: Nessun contributo unificato e nessuna anticipazione forfettaria di 27 euro, solo spese di notifica. Compenso dalla tabella dell'atto di precetto (da leggere dal sito); il tool usa 213 + 213 = 426 e aggiunge 27 di marca e 27 di notifica.

### `nota_spese`

Nota spese dell'avvocato che aggrega voci di compenso, spese generali 15%, CPA 4%, IVA 22% e spese vive o documentate esenti.

- Parametri: `voci: list[dict] (descrizione: str, importo: float, tipo: compenso \| spese_generali_15pct \| spese_vive \| spese_documentate)`
- Fonte normativa dichiarata: DM 55/2014 art. 2 co. 2 (spese generali 15%)
- Casi di prova:
  - Compensi, spese generali e contributo unificato: `{"voci": [{"descrizione": "Fase di studio", "importo": 919, "tipo": "compenso"}, {"descrizione": "Fase introduttiva", "importo": 777, "tipo": "compenso"}, {"descrizione": "Base spese generali", "importo": 1696, "tipo": "spese_generali_15pct"}, {"descrizione": "Contributo unificato", "importo": 237, "tipo": "spese_vive"}]}` → atteso: Compensi 1.696; spese generali 254,40; subtotale 1.950,40; CPA 78,02; imponibile IVA 2.028,42; IVA 446,25; spese esenti 237,00; totale 2.711,67.
  - Solo spese esenti: `{"voci": [{"descrizione": "Contributo unificato", "importo": 98, "tipo": "spese_vive"}, {"descrizione": "Anticipazioni forfettarie art. 30 DPR 115/2002", "importo": 27, "tipo": "spese_documentate"}]}` → atteso: Totale 125,00; CPA e IVA a zero.
  - Compenso con spese generali sulla stessa base: `{"voci": [{"descrizione": "Compenso", "importo": 1000, "tipo": "compenso"}, {"descrizione": "Base spese generali", "importo": 1000, "tipo": "spese_generali_15pct"}]}` → atteso: Spese generali 150,00; subtotale 1.150,00; CPA 46,00; IVA 263,12; totale 1.459,12.
  - Tipo di voce non ammesso: `{"voci": [{"descrizione": "Compenso", "importo": 1000, "tipo": "altro"}]}` → atteso: Errore: tipo voce non valido.

### `parcella_avvocato_civile`

Compenso tabellare dell'avvocato nel contenzioso civile per fasi (studio, introduttiva, istruttoria, decisionale) e livello (minimo, medio, massimo), sempre sulla tabella dei giudizi di cognizione innanzi al tribunale.

- Parametri: `valore_causa: float; fasi: list[str] \| None = None (studio, introduttiva, istruttoria, decisionale); livello: str = 'medio' (min, medio, max)`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, parametri forensi contenzioso civile
- Casi di prova:
  - Confine superiore dello scaglione 5.200,01-26.000, livello medio: `{"valore_causa": 26000, "fasi": null, "livello": "medio"}` → atteso: Valori medi della tabella del tribunale (DM 147/2022): studio 919, introduttiva 777, istruttoria 1.680, decisionale 1.701, totale 5.077 euro (valore attuale del tool); da confermare sul sito.
  - Primo centesimo dello scaglione successivo: `{"valore_causa": 26000.01, "fasi": null, "livello": "medio"}` → atteso: Scaglione 26.000,01-52.000: 1.701 + 1.204 + 1.806 + 2.905 = 7.616 euro (tool); da leggere dal sito.
  - Livello minimo appena sopra la soglia di 1.100 euro: `{"valore_causa": 1100.01, "fasi": null, "livello": "min"}` → atteso: Minimo = medio ridotto del 50% (art. 4 co. 1 DM 55/2014): medi 425/425/851/851, minimi 213/213/426/426, totale 1.278 euro (tool, 212,50 e 425,50 arrotondati per eccesso); verificare l'arrotondamento del sito. A 1.100 esatti il tool restituisce 332 (66+66+100+100).
  - Valore oltre 520.000 euro: `{"valore_causa": 600000, "fasi": null, "livello": "medio"}` → atteso: Art. 6 DM 55/2014: parametri dello scaglione fino a 520.000 (medio totale 22.457) aumentati di regola fino al 30%, al massimo 29.194,10 se applicato al totale; il tool restituisce 29.193 (4.607 + 3.039 + 13.534 + 8.013, arrotondati per fase). Da leggere dal sito quale dei due metodi offerti per il valore oltre 520.000 corrisponde.
  - Sottoinsieme di fasi al livello massimo sul confine 5.200: `{"valore_causa": 5200, "fasi": ["studio", "introduttiva"], "livello": "max"}` → atteso: Massimo = medio aumentato del 50%: 638 + 638 = 1.276 euro; da confermare sul sito selezionando solo le due fasi.

### `parcella_avvocato_penale`

Compenso tabellare dell'avvocato nel procedimento penale per organo giudicante, fasi e livello.

- Parametri: `competenza: str (giudice_pace, tribunale_monocratico, tribunale_collegiale, corte_assise, corte_appello, cassazione); fasi: list[str] \| None = None (studio, introduttiva, istruttoria, decisionale); livello: str = 'medio' (min, medio, max)`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, parametri forensi penale
- Casi di prova:
  - Tribunale monocratico, valori medi, tutte le fasi: `{"competenza": "tribunale_monocratico", "fasi": null, "livello": "medio"}` → atteso: Tool: 473 + 567 + 1.134 + 1.418 = 3.592 euro; da leggere dal sito (Competenza 570).
  - Cassazione al massimo, senza fase istruttoria: `{"competenza": "cassazione", "fasi": null, "livello": "max"}` → atteso: Tre fasi: 1.418 + 3.969 + 4.112 = 9.499 euro, massimi pari ai medi (945, 2.646, 2.741) aumentati del 50%; da leggere dal sito (Competenza 630).
  - Giudice di pace al minimo: `{"competenza": "giudice_pace", "fasi": null, "livello": "min"}` → atteso: Tool: 189 + 237 + 378 + 331 = 1.135 euro (medi 378, 473, 756, 662 ridotti del 50%); da leggere dal sito (Competenza 500).
  - Fase non prevista per l'organo: `{"competenza": "cassazione", "fasi": ["istruttoria"], "livello": "medio"}` → atteso: Errore 'Fasi non disponibili per cassazione'; sul sito il campo della fase istruttoria per la Cassazione deve risultare vuoto.

### `parcella_stragiudiziale`

Compenso tabellare dell'avvocato per attività stragiudiziale (diffide, trattative, negoziazioni) per scaglione di valore.

- Parametri: `valore_pratica: float; livello: str = 'medio' (min, medio, max)`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, parametri forensi stragiudiziali
- Casi di prova:
  - Confine superiore del primo scaglione: `{"valore_pratica": 1100, "livello": "medio"}` → atteso: Primo scaglione: 284 euro (tool); da leggere dal sito.
  - Primo centesimo del secondo scaglione: `{"valore_pratica": 1100.01, "livello": "medio"}` → atteso: Scaglione 1.100,01-5.200: 1.276 euro (tool); da leggere dal sito.
  - Ultimo scaglione tabellare al massimo: `{"valore_pratica": 520000, "livello": "max"}` → atteso: Massimo = medio 6.164 aumentato del 50% = 9.246 euro (tool); da leggere dal sito.
  - Valore oltre 520.000 euro: `{"valore_pratica": 600000, "livello": "medio"}` → atteso: Da leggere dal sito con entrambi i metodi offerti per il valore oltre 520.000; il tool restituisce 6.164, identico allo scaglione precedente.

### `parcella_volontaria_giurisdizione`

Compenso tabellare per i procedimenti di volontaria giurisdizione di natura non contenziosa (Tabella 7), ripartito dal tool in fase di studio e fase di trattazione.

- Parametri: `valore_causa: float; fasi: list[str] \| None = None (studio, trattazione); livello: str = 'medio' (min, medio, max)`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, Tabella 7 volontaria giurisdizione
- Casi di prova:
  - Confine superiore dello scaglione fino a 5.200: `{"valore_causa": 5200, "fasi": null, "livello": "medio"}` → atteso: Tool: 213 + 212 = 425 euro; da leggere dal sito (Tabella 7), comprese fasi e ripartizione.
  - Primo centesimo dello scaglione successivo: `{"valore_causa": 5200.01, "fasi": null, "livello": "medio"}` → atteso: Tool: 709 + 709 = 1.418 euro; da leggere dal sito.
  - Valore sotto 1.100 euro al minimo: `{"valore_causa": 1000, "fasi": null, "livello": "min"}` → atteso: Tool: 106 + 107 = 213 euro (scaglione fino a 5.200); se la Tabella 7 prevede uno scaglione fino a 1.100 il valore atteso è diverso: da leggere dal sito.
  - Valore oltre 520.000 al massimo: `{"valore_causa": 600000, "fasi": null, "livello": "max"}` → atteso: Tool: 3.402 + 3.402 = 6.804 euro, identico allo scaglione fino a 520.000; da leggere dal sito (eventuale incremento dell'art. 6).

### `preventivo_civile`

Preventivo completo per causa civile: compensi del tribunale, spese generali, CPA, IVA e spese vive stimate con il contributo unificato letto dalla tabella condivisa.

- Parametri: `valore_causa: float; fasi: list[str] \| None = None (studio, introduttiva, istruttoria, decisionale); livello: str = 'medio' (min, medio, max); spese_generali: bool = True; cpa: bool = True; iva: bool = True`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022; contributo unificato art. 13 DPR 115/2002
- Casi di prova:
  - Confine 26.000 con tutti gli accessori: `{"valore_causa": 26000, "fasi": null, "livello": "medio", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compensi 5.077; spese generali 761,55; CPA 233,54; IVA 1.335,86; totale onorari 7.407,95; contributo unificato 237 (art. 13 co. 1 lett. c DPR 115/2002); totale preventivo 7.717,49 comprese le stime.
  - Confine 5.200 del contributo unificato: `{"valore_causa": 5200, "fasi": null, "livello": "medio", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compensi 2.552; totale onorari 3.723,67; contributo unificato 98 (lett. b, fino a 5.200); totale preventivo 3.894,21.
  - Primo scaglione al minimo con due fasi: `{"valore_causa": 1100, "fasi": ["studio", "introduttiva"], "livello": "min", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compensi 66 + 66 = 132; totale onorari 192,60; contributo unificato 43 (lett. a, fino a 1.100); totale 308,14.
  - Oltre 520.000 al massimo senza accessori: `{"valore_causa": 520000.01, "fasi": null, "livello": "max", "spese_generali": false, "cpa": false, "iva": false}` → atteso: Compensi 43.791 (fascia oltre 520.000 con incremento del 30%, art. 6 DM 55/2014, da confermare sul sito); contributo unificato 1.686 (lett. g, oltre 520.000); totale 45.549,54.

### `preventivo_stragiudiziale`

Preventivo per attività stragiudiziale con compenso tabellare, spese generali 15%, CPA 4% e IVA 22%.

- Parametri: `valore_pratica: float; livello: str = 'medio' (min, medio, max); spese_generali: bool = True; cpa: bool = True; iva: bool = True`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, parametri stragiudiziali
- Casi di prova:
  - Confine 5.200 al medio: `{"valore_pratica": 5200, "livello": "medio", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compenso 1.276; spese generali 191,40; CPA 58,70; IVA 335,74; totale 1.861,84.
  - Primo centesimo dello scaglione successivo al minimo: `{"valore_pratica": 5200.01, "livello": "min", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compenso 993 (da confermare); spese generali 148,95; CPA 45,68; IVA 261,28; totale 1.448,91.
  - Oltre 520.000 al massimo senza IVA: `{"valore_pratica": 600000, "livello": "max", "spese_generali": true, "cpa": true, "iva": false}` → atteso: Compenso 9.246 (da leggere dal sito per il valore oltre 520.000); spese generali 1.386,90; CPA 425,32; totale 11.058,22.

### `preventivo_volontaria_giurisdizione`

Preventivo per volontaria giurisdizione: compensi della Tabella 7 con spese generali 15%, CPA 4% e IVA 22% attivabili singolarmente.

- Parametri: `valore_causa: float; fasi: list[str] \| None = None (studio, trattazione); livello: str = 'medio' (min, medio, max); spese_generali: bool = True; cpa: bool = True; iva: bool = True`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022, Tabella 7
- Casi di prova:
  - Confine 5.200, tutti gli accessori: `{"valore_causa": 5200, "fasi": null, "livello": "medio", "spese_generali": true, "cpa": true, "iva": true}` → atteso: Compensi 425 (da confermare sul sito); spese generali 63,75; subtotale 488,75; CPA 19,55; imponibile IVA 508,30; IVA 111,83; totale onorari 620,13.
  - Massimo senza spese generali e senza IVA: `{"valore_causa": 26000, "fasi": null, "livello": "max", "spese_generali": false, "cpa": true, "iva": false}` → atteso: Compensi 1.064 + 1.063 = 2.127 (da confermare); CPA 85,08; totale 2.212,08; spese generali e IVA a zero.
  - Minimo senza CPA: `{"valore_causa": 100000, "fasi": null, "livello": "min", "spese_generali": true, "cpa": false, "iva": true}` → atteso: Compensi 833 + 832 = 1.665 (da confermare); spese generali 249,75; imponibile 1.914,75; IVA 421,25; totale 2.336,00.

### `spese_trasferta_avvocati`

Stima di indennità di trasferta e rimborso chilometrico dell'avvocato in base a distanza, ore di assenza, mezzo e pernottamento.

- Parametri: `km_distanza: float; ore_assenza: float; pernottamento: bool = False; mezzo: str = 'auto' (auto, treno, aereo)`
- Fonte normativa dichiarata: DM 55/2014 art. 27 (trasferte)
- Casi di prova:
  - Auto, 200 km, 4 ore: `{"km_distanza": 200, "ore_assenza": 4, "pernottamento": false, "mezzo": "auto"}` → atteso: Art. 27: indennità chilometrica 200 x (prezzo del carburante / 5), per esempio 72,00 euro a 1,80 euro/l, oltre pedaggi e parcheggi; indennità di trasferta da leggere dal sito. Il tool: 60,00 + 54,00 = 114,00.
  - Confine delle 4 ore del tool: `{"km_distanza": 200, "ore_assenza": 4.01, "pernottamento": false, "mezzo": "auto"}` → atteso: Soglia non normativa del tool: indennità 108,00, totale 168,00; da leggere dal sito se e come l'indennità dipende dalla durata.
  - Treno con pernottamento oltre 8 ore: `{"km_distanza": 0, "ore_assenza": 8.01, "pernottamento": true, "mezzo": "treno"}` → atteso: Viaggio e albergo a piè di lista; per l'art. 27 il soggiorno documentato (limite quattro stelle) va maggiorato del 10%; il tool restituisce solo l'indennità di 216,00 (40%). Da leggere dal sito.

## gazzetta.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_gazzetta_ufficiale` | ricerca_online | smoke_live | nessuna (media) | Gazzetta Ufficiale, ricerca atti su gazzettaufficiale.it e permalink ELI (identificatore europeo della legislazione) dell'atto | Assente dai paragrafi 5 e 7 come tool; è lo strumento per chiudere la voce danno_biologico_macro del paragrafo 5 e il punto 2 del paragrafo 8 (trascrizione della tabella unica nazionale, DPR 13 gennaio 2025 n. 12). Da confermare: query usata come alias del titolo con tutte le parole richieste; filtri tipo ed emettitore per descrizione esatta; funzionamento sulle serie speciali. |
| `leggi_atto_gazzetta` | ricerca_online | smoke_live | nessuna (media) | Gazzetta Ufficiale, pagina ELI https://www.gazzettaufficiale.it/eli/id/2022/10/17/22G00158/sg | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) il testo è quello originario pubblicato, non il vigente (per il vigente usare cite_law); (b) il permalink ELI è costruito sempre con '/sg' qualunque sia la serie passata, che incide solo sul menu degli articoli: verificare un atto di una serie speciale; (c) un formato di data errato è riportato come dato non valido. |
| `scarica_pdf_gazzetta` | ricerca_online | smoke_live | nessuna (alta) | Gazzetta Ufficiale, PDF del fascicolo n. 205 del 4 settembre 2018 | Assente dai paragrafi 5 e 7: né corretto né declassato. Il tool non fa chiamate di rete: il benchmark deve scaricare l'URL e controllare che sia il PDF del fascicolo giusto. Da confermare: parametro serie ignorato (sempre '/sg'); un formato di data errato è riportato come 'gazzetta_ufficiale non raggiungibile' invece che come errore di input. |
| `sommario_gazzetta` | ricerca_online | smoke_live | nessuna (media) | Gazzetta Ufficiale, sommario del fascicolo su gazzettaufficiale.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il parametro serie non è usato (l'URL termina sempre con '/sg'), quindi per le serie speciali il sommario è sbagliato o vuoto; inclusione o meno degli atti dei supplementi ordinari. |
| `ultime_gazzette` | ricerca_online | smoke_live | nessuna (media) | Gazzetta Ufficiale, pagina dei feed RSS e ultimo fascicolo di ciascuna serie | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare la mappatura delle serie speciali sui feed: nel codice unione_europea è S1, regioni S2, corte_costituzionale S3, contratti S4, concorsi S5, mentre la numerazione ufficiale è 1a Serie speciale Corte costituzionale, 2a Unione europea, 3a Regioni, 4a Concorsi ed esami, 5a Contratti pubblici; se i codici dei feed seguono la numerazione ufficiale, tutte e cinque le serie speciali sono scambiate (il test unitario verifica il codice, non il contenuto del feed). |

### `cerca_gazzetta_ufficiale`

Ricerca parametrica e a testo pieno degli atti pubblicati in Gazzetta Ufficiale per titolo, testo, tipo, emettitore, materia, serie e anni di pubblicazione.

- Parametri: `query: str = '' (alias di titolo); titolo: str = ''; testo: str = ''; tipo_provvedimento: str = ''; emettitore: str = ''; materia: str = ''; serie: 'serie_generale' \| 'unione_europea' \| 'regioni' \| 'corte_costituzionale' \| 'parte_seconda' \| 'contratti' \| 'concorsi' = 'serie_generale'; anno_da: str = ''; anno_a: str = ''; max_risultati: int = 20 (1-100)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Gazzetta Ufficiale della Repubblica italiana (gazzettaufficiale.it)
- Casi di prova:
  - Decreto legislativo noto: `{"titolo": "processo civile", "tipo_provvedimento": "DECRETO LEGISLATIVO", "anno_da": "2022", "anno_a": "2022"}` → atteso: include il D.Lgs. 10 ottobre 2022 n. 149 (attuazione della L. 206/2021 sull'efficienza del processo civile), GU n. 243 del 17/10/2022, S.O. n. 38; codice redazionale 22G00158 da riscontrare
  - Tabella unica nazionale per danno_biologico_macro: `{"titolo": "menomazioni integrità psicofisica", "anno_da": "2025", "anno_a": "2025"}` → atteso: include il DPR 13 gennaio 2025 n. 12 (tabella delle menomazioni all'integrità psicofisica tra 10 e 100 punti, art. 138 D.Lgs. 209/2005); codice redazionale e data di pubblicazione da leggere dalla fonte

### `leggi_atto_gazzetta`

Metadati ELI (tipo, emettitore, date) e testo integrale, assemblato articolo per articolo, di un atto in Gazzetta Ufficiale da codice redazionale e data di pubblicazione.

- Parametri: `codice_redazionale: str; data_pubblicazione: str (AAAA-MM-GG); serie: str = 'serie_generale'; solo_metadati: bool = False`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Gazzetta Ufficiale, permalink ELI e pagine degli articoli (testo originario)
- Casi di prova:
  - Solo metadati di un atto noto: `{"codice_redazionale": "22G00158", "data_pubblicazione": "2022-10-17", "solo_metadati": true}` → atteso: tipo decreto legislativo, data atto 2022-10-10, pubblicazione 2022-10-17, link ELI https://www.gazzettaufficiale.it/eli/id/2022/10/17/22G00158/sg, nota 'solo metadati'; codice da riscontrare con il caso di cerca_gazzetta_ufficiale
  - Data in formato errato: `{"codice_redazionale": "22G00158", "data_pubblicazione": "17/10/2022"}` → atteso: errore 'data non valida' (formato AAAA-MM-GG richiesto)

### `scarica_pdf_gazzetta`

Restituisce l'URL del PDF ufficiale di un fascicolo di Gazzetta Ufficiale, costruito da numero e data, senza scaricarlo.

- Parametri: `numero_gazzetta: str; data_pubblicazione: str (AAAA-MM-GG); serie: str = 'serie_generale' (accettato ma ignorato)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Gazzetta Ufficiale, PDF del fascicolo (percorso ELI /pdf)
- Casi di prova:
  - Fascicolo noto: `{"numero_gazzetta": "205", "data_pubblicazione": "2018-09-04"}` → atteso: URL https://www.gazzettaufficiale.it/eli/gu/2018/09/04/205/sg/pdf; il download restituisce HTTP 200 con il PDF della GU Serie generale n. 205 del 04/09/2018
  - Data in formato errato: `{"numero_gazzetta": "205", "data_pubblicazione": "04/09/2018"}` → atteso: errore di data non valida; oggi classificato come fonte non raggiungibile, classificazione da correggere
  - Serie speciale: `{"numero_gazzetta": "10", "data_pubblicazione": "2026-02-06", "serie": "concorsi"}` → atteso: URL con '/sg/pdf' nonostante la serie concorsi: parametro ignorato, da gestire o rimuovere

### `sommario_gazzetta`

Sommario (atti con codice redazionale e oggetto) di un fascicolo della Gazzetta Ufficiale da numero e data.

- Parametri: `numero_gazzetta: str; data_pubblicazione: str (AAAA-MM-GG); serie: str = 'serie_generale' (accettato ma ignorato)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Gazzetta Ufficiale, pagina ELI del fascicolo
- Casi di prova:
  - Fascicolo noto: `{"numero_gazzetta": "205", "data_pubblicazione": "2018-09-04"}` → atteso: sommario della GU Serie generale n. 205 del 04/09/2018 con il D.Lgs. 10 agosto 2018 n. 101 (adeguamento al Regolamento (UE) 2016/679); codice redazionale 18G00129 da riscontrare
  - Fascicolo con supplemento ordinario: `{"numero_gazzetta": "243", "data_pubblicazione": "2022-10-17"}` → atteso: da leggere dalla fonte: verificare se compaiono gli atti del S.O. n. 38 (D.Lgs. 149/2022)

### `ultime_gazzette`

Ultimi atti pubblicati in Gazzetta Ufficiale tramite il feed RSS della serie scelta.

- Parametri: `serie: str = 'serie_generale' (serie_generale, unione_europea, regioni, corte_costituzionale, parte_seconda, contratti, concorsi); max_risultati: int = 10 (1-100)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Gazzetta Ufficiale, feed RSS
- Casi di prova:
  - Serie generale: `{"serie": "serie_generale", "max_risultati": 5}` → atteso: cinque atti dell'ultimo fascicolo con codice redazionale che inizia per '26' e data di pubblicazione di pochi giorni precedente la prova; da leggere dalla fonte
  - Serie speciale Corte costituzionale: `{"serie": "corte_costituzionale", "max_risultati": 5}` → atteso: atti della 1a Serie speciale (sentenze, ordinanze e atti di promovimento dei giudizi costituzionali); se compaiono atti regionali o dell'Unione europea la mappatura RSS_CODE è errata

## giurisprudenza_unificata.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_giurisprudenza_unificata` | ricerca_online | smoke_live | nessuna (media) | Stesse ricerche con i tool di fonte singola e sui portali ufficiali | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) per la giustizia amministrativa passa anno=anno_da come anno esatto, filtrato in locale, e ignora anno_a; (b) per la CGUE la query intera diventa una sola sottostringa del titolo, quindi le frasi lunghe danno zero; (c) il riepilogo finale distingue fonte non raggiungibile, zero risultati e criteri ampliati. |

### `cerca_giurisprudenza_unificata`

Ricerca parallela su Cassazione (Italgiure), giurisprudenza tributaria (CeRDEF), giustizia amministrativa e Corte di giustizia UE, con risultati per fonte e riepilogo dello stato di ciascuna.

- Parametri: `query: str; fonti: str = 'tutte' (cassazione, tributaria, amministrativa, ue separate da virgola); anno_da: str = ''; anno_a: str = ''; tipo_provvedimento: str = ''; max_risultati: int = 5 per fonte (1-20)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonti: Italgiure, CeRDEF, Giustizia amministrativa, CELLAR
- Casi di prova:
  - Due fonti con documento noto: `{"query": "clausole abusive", "fonti": "cassazione,ue", "anno_da": "2022", "anno_a": "2022", "tipo_provvedimento": "sentenza", "max_risultati": 20}` → atteso: sezione CGUE con la causa C-693/19 SPV Project 1503 del 17/05/2022; sezione Cassazione con sentenze del 2022; riga 'Fonti consultate' con il conteggio per fonte
  - Filtro anni sulla giustizia amministrativa: `{"query": "concessioni demaniali marittime", "fonti": "amministrativa", "anno_da": "2021", "anno_a": "2021"}` → atteso: da leggere dalla fonte: zero o pochi risultati nonostante le sentenze 17 e 18/2021 dell'Adunanza plenaria, per il filtro per anno applicato in locale; documentare il limite

## giustizia_amm.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_giurisprudenza_amministrativa` | ricerca_online | smoke_live | nessuna (media) | Giustizia amministrativa, ricerca 'Decisioni e pareri' su giustizia-amministrativa.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Il portale è stato riorganizzato nel 2026 (issue #32 citata nel codice). Da confermare: sede, NRG (numero di registro generale) e nome_file validi per leggi_provvedimento_amm; anno più numero individuano il provvedimento esatto (numero composto da anno e cinque cifre), anche per l'Adunanza plenaria che ha numerazione propria; il filtro anno da solo è applicato in locale sui risultati restituiti ed è dichiarato in risposta. |
| `giurisprudenza_amm_su_norma` | ricerca_online | smoke_live | nessuna (bassa) | Giustizia amministrativa, ricerca per estremi normativi su giustizia-amministrativa.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il riferimento è passato come testo libero senza varianti (diversamente da giurisprudenza_su_norma su Italgiure), quindi la precisione va misurata leggendo il testo di tre risultati; anno_da scarta solo i provvedimenti anteriori tra quelli restituiti, ordinati dal più recente. |
| `leggi_provvedimento_amm` | ricerca_online | smoke_live | nessuna (media) | Giustizia amministrativa, pagina del provvedimento sul portale | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: riconoscimento della pagina di errore servita con HTTP 200 dopo la riorganizzazione 2026; accettazione dei vecchi codici sede; un riferimento sbagliato non deve essere riportato come fonte non raggiungibile. |
| `ultimi_provvedimenti_amm` | ricerca_online | smoke_live | nessuna (media) | Giustizia amministrativa, ultimi provvedimenti per sede | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il portale non espone più la data di deposito (campo sempre vuoto nel codice), quindi l'ordine 'più recenti' va verificato su anno e numero; filtro sede effettivo. |

### `cerca_giurisprudenza_amministrativa`

Ricerca di sentenze e provvedimenti dei Tribunali amministrativi regionali (TAR), del Consiglio di Stato e del Consiglio di giustizia amministrativa per la Regione siciliana sul portale della Giustizia amministrativa, con filtri per sede, tipo, anno e numero.

- Parametri: `query: str; sede: str = '' (31 chiavi: consiglio_di_stato, cgars, tar_lazio, tar_lombardia, ...); tipo: 'sentenza' \| 'ordinanza' \| 'decreto' \| 'parere' \| 'adunanza_plenaria' \| 'adunanza_generale' \| '' = ''; anno: str = ''; numero: str = ''; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: portale della Giustizia amministrativa (giustizia-amministrativa.it, decisioni e pareri)
- Casi di prova:
  - Adunanza plenaria nota: `{"query": "concessioni demaniali marittime", "sede": "consiglio_di_stato", "tipo": "adunanza_plenaria", "anno": "2021", "numero": "17"}` → atteso: Consiglio di Stato, Adunanza plenaria, sentenza n. 17/2021 del 9 novembre 2021 (proroga automatica delle concessioni demaniali marittime da non applicare per contrasto con l'art. 12 della direttiva 2006/123/CE), con sede, NRG e nome_file; ECLI da leggere dalla fonte
  - Anno senza numero: `{"query": "silenzio assenso", "sede": "tar_lazio", "anno": "2019"}` → atteso: zero o pochi risultati con la nota sul filtro per anno applicato ai soli risultati restituiti; documentare il limite

### `giurisprudenza_amm_su_norma`

Provvedimenti di TAR e Consiglio di Stato che citano una norma, con ricerca a testo libero del riferimento e filtro anno_da applicato ai risultati restituiti.

- Parametri: `riferimento: str; sede: str = ''; anno_da: str = ''; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: portale della Giustizia amministrativa
- Casi di prova:
  - Norma della L. 241/1990: `{"riferimento": "art. 21-octies L. 241/1990", "sede": "consiglio_di_stato", "anno_da": "2025", "max_risultati": 10}` → atteso: da leggere dalla fonte: provvedimenti del Consiglio di Stato dal 2025; tre su tre, letti con leggi_provvedimento_amm, devono citare l'art. 21-octies della L. 241/1990

### `leggi_provvedimento_amm`

Testo integrale (motivazione e dispositivo) di un provvedimento di TAR o Consiglio di Stato dal sottodominio mdp, con sede, NRG e nome file presi da una ricerca; troncato a 15000 caratteri.

- Parametri: `sede: str (codici cds, tar_rm, tar_mi, vecchi codici CDS, TARLAZ o chiavi estese); nrg: str; nome_file: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: mdp.giustizia-amministrativa.it
- Casi di prova:
  - Provvedimento noto (parametri dalla ricerca): `{"sede": "cds", "nrg": "<nrg restituito da cerca_giurisprudenza_amministrativa per l'Adunanza plenaria n. 17/2021>", "nome_file": "<nome_file dello stesso risultato>"}` → atteso: intestazione con sede Consiglio di Stato (cds) e NRG; testo con motivazione e dispositivo sulle concessioni demaniali marittime; troncamento a 15000 caratteri dichiarato
  - Riferimento inesistente: `{"sede": "cds", "nrg": "202500000", "nome_file": "202500000_01.html"}` → atteso: messaggio di testo non recuperabile (pagina di errore riconosciuta), non 'non raggiungibile'

### `ultimi_provvedimenti_amm`

Ultimi provvedimenti depositati da TAR e Consiglio di Stato, con filtri per sede e tipo.

- Parametri: `sede: str = ''; tipo: str = ''; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: portale della Giustizia amministrativa
- Casi di prova:
  - Ultime sentenze di un TAR: `{"sede": "tar_lombardia", "tipo": "sentenza", "max_risultati": 5}` → atteso: da leggere dalla fonte: cinque sentenze del TAR Lombardia, sede di Milano, dell'anno 2026, con sezione, ECLI e parametri per leggi_provvedimento_amm

## gpdp.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_provvedimenti_garante` | ricerca_online | smoke_live | nessuna (media) | Garante per la protezione dei dati personali, motore di ricerca e schede DocWeb su garanteprivacy.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) i risultati sono ordinati per data anche con una query testuale (ordinamento predefinito 'data'); (b) il filtro tipologia agisce solo sulle prime max_risultati x 3 schede (massimo 50), quindi può restituire meno risultati di quelli esistenti; (c) formato delle date GG/MM/AAAA rispettato dal sito. |
| `leggi_provvedimento_garante` | ricerca_online | smoke_live | nessuna (alta) | Garante per la protezione dei dati personali, scheda DocWeb 9677876 | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) le etichette degli identificativi di esempio nel docstring, che il modello usa come ancore: 9870832 è indicato come 'Linee guida AI 2023' ma dovrebbe essere il provvedimento del 30/03/2023 su ChatGPT, e 10000069 è indicato come 'Provvedimento ChatGPT 2023'; (b) il troncamento a 6000 caratteri, che per le linee guida restituisce solo l'inizio, è dichiarato in risposta; (c) un identificativo inesistente produce un errore e non una pagina vuota. |
| `ultimi_provvedimenti_garante` | ricerca_online | smoke_live | nessuna (media) | Garante per la protezione dei dati personali, documenti più recenti e newsletter su garanteprivacy.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: ordinamento per data effettivo senza query; il filtro tipologia lavora solo sulle prime schede scaricate (fino a 50). |

### `cerca_provvedimenti_garante`

Ricerca di provvedimenti, linee guida e pareri del Garante per la protezione dei dati personali sul sito ufficiale (identificativo DocWeb), con intervallo di date e filtro per tipologia applicato in locale.

- Parametri: `query: str; tipologia: str = ''; data_da: str = '' (GG/MM/AAAA); data_a: str = '' (GG/MM/AAAA); max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Garante per la protezione dei dati personali, ricerca su garanteprivacy.it (DocWeb)
- Casi di prova:
  - Linee guida note: `{"query": "linee guida cookie", "data_da": "01/06/2021", "data_a": "30/06/2021", "max_risultati": 10}` → atteso: tra i risultati DocWeb 9677876, 'Linee guida cookie e altri strumenti di tracciamento' del 10/06/2021, con link https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/docweb/9677876
  - Provvedimento noto con filtro tipologia: `{"query": "OpenAI ChatGPT", "data_da": "01/03/2023", "data_a": "30/04/2023", "tipologia": "provvedimento"}` → atteso: tra i risultati il provvedimento del 30/03/2023 di limitazione provvisoria del trattamento nei confronti di OpenAI (DocWeb 9870832 da riscontrare)

### `leggi_provvedimento_garante`

Testo integrale di un documento del Garante per la protezione dei dati personali tramite identificativo DocWeb (pagina di stampa), troncato a 6000 caratteri.

- Parametri: `docweb_id: int`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: garanteprivacy.it, scheda DocWeb
- Casi di prova:
  - Documento noto: `{"docweb_id": 9677876}` → atteso: titolo 'Linee guida cookie e altri strumenti di tracciamento' del 10 giugno 2021; riga DocWeb con link alla scheda 9677876; testo troncato a 6000 caratteri con la nota di troncamento
  - Identificativo di esempio del docstring: `{"docweb_id": 9870832}` → atteso: provvedimento del 30 marzo 2023 di limitazione provvisoria del trattamento nei confronti di OpenAI (ChatGPT), da riscontrare; se confermato, l'etichetta del docstring va corretta

### `ultimi_provvedimenti_garante`

Ultimi documenti pubblicati dal Garante per la protezione dei dati personali in ordine di data, con filtro per tipologia applicato in locale.

- Parametri: `tipologia: str = ''; max_risultati: int = 10 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: garanteprivacy.it
- Casi di prova:
  - Ultimi documenti senza filtro: `{"max_risultati": 5}` → atteso: da leggere dalla fonte: cinque schede in ordine di data decrescente, nessuna successiva al giorno della prova, ciascuna con DocWeb e link; la prima coincide con l'ultimo documento pubblicato sul sito
  - Filtro tipologia: `{"tipologia": "provvedimento", "max_risultati": 5}` → atteso: solo schede con tipologia che contiene 'provvedimento'; se meno di cinque, documentare l'effetto del filtro locale sulle prime 15 schede

## investimenti.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `confronto_investimenti` | calcolo | solo_norma | nessuna pagina del sito | Testo vigente dell'art. 3 DL 66/2014 e dell'art. 2 D.Lgs. 239/1996 via cite_law | Non toccato dall'audit; gia' INDICATIVO. Nessun calcolatore equivalente sul sito. Si verificano con cite_law le aliquote (12,5% per titoli pubblici ed equiparati, art. 3 co. 2 DL 66/2014; 26% per gli altri redditi di capitale, art. 3 co. 1) e a mano l'aritmetica. Difetti trovati: la classifica e' per rendimento netto annuo e ignora la durata; tipo_tassazione sconosciuto e' tassato al 26% con il solo flag tipo_tassazione_riconosciuto; l'imposta e' calcolata una volta a scadenza sugli interessi composti, mentre cedole e interessi periodici sono tassati all'incasso. |
| `pronti_termine` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-rendimento-pronti-contro-termine.php (alta) | Circolare Agenzia delle Entrate 19/E del 27/06/2014 (aliquote dei proventi da pronti contro termine) | Non toccato dall'audit. Aliquote confermate: 12,5% sui proventi dei pronti contro termine su titoli pubblici (art. 3 co. 2 DL 66/2014, circ. AdE 19/E/2014), 26% negli altri casi (art. 3 co. 1). Il sito chiede capitale, importo rimborsato o rendimento lordo e spese fisse di sottoscrizione e gestione, che il tool non gestisce: confrontare a spese zero. Da confermare la base del sito (365 o 360 giorni). Il tool non gestisce sottostanti misti. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rendimento_bot` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-rendimento-bot.php (alta) | MEF Dipartimento del Tesoro, comunicati d'asta BOT; DM 15/01/2015 sulle commissioni massime | Non toccato dall'audit. L'imposta del 12,5% sui BOT colpisce lo scarto di emissione (prezzo medio ponderato d'asta) ed e' trattenuta alla sottoscrizione (art. 2 D.Lgs. 239/1996; art. 3 co. 2 DL 66/2014); il tool la calcola sulla differenza tra nominale e prezzo di acquisto, corretto solo per la sottoscrizione in asta. Il DM 15/01/2015 fissa le commissioni massime (0,05% a 3 mesi, 0,10% a 6 mesi, 0,15% a 12 mesi) e le azzera con rendimento nullo o negativo: il tool addebita la commissione anche sopra la pari. Da confermare la base del sito (365 o 360 giorni), la base della commissione (nominale o prezzo) e le spese di gestione periodiche che il sito considera. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rendimento_btp` | calcolo | fonte_ufficiale | nessuna pagina del sito | MEF Dipartimento del Tesoro, comunicati sui risultati delle aste BTP (prezzo, cedola, rendimento lordo e netto) | Non toccato dall'audit; gia' INDICATIVO (rendimento semplice senza reinvestimento delle cedole ne' rateo). La ricerca sul sito ha restituito solo BOT e pronti contro termine: nessun calcolatore BTP. Il benchmark verifica l'aliquota del 12,5% su cedole e scarto (art. 2 D.Lgs. 239/1996; art. 3 co. 2 lett. a DL 66/2014), l'aritmetica delle cedole e lo scarto tra rendimento semplice e rendimento effettivo netto a scadenza (TIR) su un'asta MEF reale, per decidere se il grado INDICATIVO basta. Acquisto sopra la pari: nessuna imposta sulla differenza negativa, coerente per il singolo titolo. |
| `rendimento_buoni_postali` | calcolo | fonte_ufficiale | nessuna pagina del sito ; secondarie: https://www.avvocatoandreani.it/utility/calcolo-buoni-postali-fruttiferi.php | Cassa Depositi e Prestiti e Poste Italiane, fogli informativi dei buoni in collocamento (rendimenti per anno di detenzione) | Non toccato dall'audit; gia' INDICATIVO. La pagina e' sotto /utility/ e calcola per tipo di buono, data di sottoscrizione e data di rimborso, applicando il 12,5% e il bollo dello 0,20% oltre 5.000 euro; il tool usa tassi interni non riferiti ad alcuna serie (per il 3x4 in collocamento il foglio informativo 2026 indica il 2,50% lordo a scadenza, il tool arriva al 2% solo al dodicesimo anno) e non applica il bollo. Difetto trovato: per 3x4 e 4x4 gli interessi si maturano solo alla fine di ogni periodo (triennio o quadriennio), il tool capitalizza ogni anno anche nel periodo in corso. Il benchmark deve portare alla riscrittura sulle tabelle CDP per serie. Fase 0: la pagina del sito rimanda al simulatore esterno di Cassa Depositi e Prestiti (services.cdp.it); strategia portata a fonte_ufficiale (CDP, fogli informativi dei buoni). |

### `confronto_investimenti`

Classifica piu' strumenti per rendimento netto annuo con aliquota del 12,5% o del 26% e montante composto a scadenza.

- Parametri: `importo: float, investimenti: list[{nome: str, rendimento_lordo_pct: float, tipo_tassazione: 'titoli_stato' \| 'altro', durata_anni: int}]`
- Fonte normativa dichiarata: Nessuna riga Vigenza (aliquote 12,5% e 26% nel codice)
- Casi di prova:
  - Titolo di Stato contro obbligazione societaria, stessa durata: `{"importo": 100000, "investimenti": [{"nome": "BTP", "rendimento_lordo_pct": 3.5, "tipo_tassazione": "titoli_stato", "durata_anni": 5}, {"nome": "Obbligazione societaria", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 5}]}` → atteso: Netti 3,5 x 0,875 = 3,0625% e 4,0 x 0,74 = 2,96% (art. 3 co. 1 e 2 DL 66/2014); migliore BTP; montanti netti 116.422,55 e 116.032,31.
  - Durate diverse (limite della classifica): `{"importo": 10000, "investimenti": [{"nome": "A", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 10}, {"nome": "B", "rendimento_lordo_pct": 3.1, "tipo_tassazione": "titoli_stato", "durata_anni": 1}]}` → atteso: Classifica per rendimento netto: B (2,7125%) prima di A (2,625%) benche' A guadagni 3.009,27 contro 271,25: limite da documentare.
  - Regime fiscale non riconosciuto: `{"importo": 10000, "investimenti": [{"nome": "Conto deposito", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "esente", "durata_anni": 2}]}` → atteso: Aliquota 26% con tipo_tassazione_riconosciuto false (montante netto 10.450,66); atteso errore o avviso esplicito.

### `pronti_termine`

Rendimento netto di un pronti contro termine con aliquota del 12,5% o del 26% secondo il sottostante.

- Parametri: `capitale: float, tasso_lordo_pct: float, giorni: int, tipo_sottostante: str = 'titoli_stato' ('titoli_stato' 12,5% \| 'altro' 26%)`
- Fonte normativa dichiarata: D.Lgs. 239/1996 (titoli di Stato 12,5%); DL 66/2014 (altri strumenti 26%)
- Casi di prova:
  - Sottostante titoli di Stato, 90 giorni: `{"capitale": 100000, "tasso_lordo_pct": 3.5, "giorni": 90, "tipo_sottostante": "titoli_stato"}` → atteso: Interessi lordi 863,01 (base 365), imposta 12,5% = 107,88, netti 755,14, rendimento netto 3,0625%; su base 360 i lordi sarebbero 875,00: da leggere dal sito.
  - Altro sottostante, 180 giorni: `{"capitale": 50000, "tasso_lordo_pct": 4.0, "giorni": 180, "tipo_sottostante": "altro"}` → atteso: Lordi 986,30, imposta 26% = 256,44, netti 729,86, rendimento netto 2,96%.
  - Sottostante non ammesso: `{"capitale": 50000, "tasso_lordo_pct": 4.0, "giorni": 180, "tipo_sottostante": "misto"}` → atteso: Errore: tipo_sottostante non ammesso.

### `rendimento_bot`

Rendimento lordo e netto annualizzato di un BOT zero coupon con imposta sostitutiva del 12,5% e commissione sul nominale.

- Parametri: `valore_nominale: float, prezzo_acquisto: float, giorni_scadenza: int, commissione_pct: float = 0.0`
- Fonte normativa dichiarata: D.Lgs. 239/1996; imposta sostitutiva 12,5% sullo scarto di emissione
- Casi di prova:
  - BOT a 12 mesi senza commissione: `{"valore_nominale": 10000, "prezzo_acquisto": 9700, "giorni_scadenza": 365, "commissione_pct": 0}` → atteso: Scarto 300; imposta 12,5% = 37,50; netto 262,50; rendimento lordo 3,0928% e netto 2,7062% su base 365 (su base 360 il lordo sarebbe 3,0504%): base del sito da leggere.
  - BOT a 6 mesi con commissione massima: `{"valore_nominale": 10000, "prezzo_acquisto": 9850, "giorni_scadenza": 182, "commissione_pct": 0.10}` → atteso: Commissione massima 0,10% (DM 15/01/2015) = 10,00; netto 150 - 18,75 - 10 = 121,25; rendimento netto 2,4687%; da leggere dal sito.
  - Prezzo sopra la pari (rendimento negativo): `{"valore_nominale": 10000, "prezzo_acquisto": 10020, "giorni_scadenza": 91, "commissione_pct": 0.05}` → atteso: Imposta 0 e commissione azzerata (DM 15/01/2015): netto -20,00, rendimento netto -0,8006%. Il tool addebita 5,00 di commissione (-1,0007%).

### `rendimento_btp`

Rendimento netto semplificato di un BTP a cedola fissa con imposta del 12,5% su cedole e scarto.

- Parametri: `valore_nominale: float, prezzo_acquisto: float, cedola_annua_pct: float, anni_scadenza: int, frequenza_cedola: int = 2 (1 annuale, 2 semestrale)`
- Fonte normativa dichiarata: D.Lgs. 239/1996; imposta sostitutiva 12,5% su cedole e plusvalenza
- Casi di prova:
  - Sotto la pari, cedola semestrale: `{"valore_nominale": 10000, "prezzo_acquisto": 9800, "cedola_annua_pct": 3.0, "anni_scadenza": 5, "frequenza_cedola": 2}` → atteso: Cedole lorde 1.500, imposta 187,50; scarto 200, imposta 25; guadagno netto 1.487,50; rendimento semplice 3,0357%; TIR netto annuo composto circa 3,035% (calcolo a mano sui flussi).
  - Sopra la pari: `{"valore_nominale": 10000, "prezzo_acquisto": 10300, "cedola_annua_pct": 4.0, "anni_scadenza": 3, "frequenza_cedola": 2}` → atteso: Imposta sulla differenza negativa 0; guadagno netto 1.050 - 300 = 750; rendimento semplice 2,4272% contro TIR netto circa 2,47%: scarto da documentare come limite dell'INDICATIVO.
  - Alla pari con cedola annuale (coincidenza col TIR): `{"valore_nominale": 1000, "prezzo_acquisto": 1000, "cedola_annua_pct": 2.5, "anni_scadenza": 10, "frequenza_cedola": 1}` → atteso: Rendimento netto 2,5 x 0,875 = 2,1875%, uguale al TIR.
  - Frequenza cedolare nulla: `{"valore_nominale": 1000, "prezzo_acquisto": 990, "cedola_annua_pct": 2.5, "anni_scadenza": 10, "frequenza_cedola": 0}` → atteso: Errore: frequenza_cedola deve essere positiva.

### `rendimento_buoni_postali`

Montante e rendimento netto di buoni fruttiferi postali con tassi a scaglioni interni e imposta del 12,5%.

- Parametri: `importo: float, tipo: str = 'ordinario' ('ordinario' \| '3x4' \| '4x4' \| 'dedicato_minori'), anni: int = 10 (limitato al massimo del tipo)`
- Fonte normativa dichiarata: D.Lgs. 239/1996; imposta sostitutiva 12,5% (equiparati ai titoli di Stato)
- Casi di prova:
  - 3x4 rimborsato a 7 anni (periodo non concluso): `{"importo": 5000, "tipo": "3x4", "anni": 7}` → atteso: Interessi riconosciuti solo fino al sesto anno (foglio informativo del 3x4): con i tassi del tool il valore corretto e' quello a 6 anni (5.268,29 lordi), il tool restituisce 5.347,31; valore reale da leggere dal sito e dal foglio CDP della serie.
  - Ordinario a 10 anni oltre la soglia del bollo: `{"importo": 10000, "tipo": "ordinario", "anni": 10}` → atteso: Da leggere dal sito e dal foglio informativo della serie in collocamento; imposta 12,5% sugli interessi (D.Lgs. 239/1996) e bollo 0,20% sulla parte oltre 5.000 euro; il tool restituisce montante netto 10.914,85 senza bollo.
  - Durata oltre il massimo del tipo: `{"importo": 10000, "tipo": "ordinario", "anni": 25}` → atteso: Durata limitata a 20 anni: campo anni 20 nel risultato.
  - Tipo non ammesso: `{"importo": 10000, "tipo": "inesistente", "anni": 5}` → atteso: Errore: tipo non valido.

## italgiure.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_giurisprudenza` | ricerca_online | smoke_live | nessuna (media) | Italgiure SentenzeWeb, stessa ricerca eseguita dall'interfaccia web con gli stessi filtri | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) il docstring indica sezione='SU' per le Sezioni Unite, mentre il filtro solo_sezioni_unite usa 'SU OR U' e i tool di orientamento usano U: se sezione='SU' non trova nulla il docstring va corretto; (b) il filtro materia è inserito senza virgolette e un valore con spazi (come l'esempio del docstring) può rompere la query; (c) rilassamento e raffinamento dichiarano in risposta il passaggio applicato; (d) il filtro al 20% del punteggio massimo non scarta la decisione nota. |
| `giurisprudenza_articolo` | ricerca_online | smoke_live | nessuna (bassa) | Brocardi.it (massime dell'articolo) e Italgiure SentenzeWeb | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) i riferimenti diretti anteriori al 2020 sono scartati senza segnalarlo; (b) anno_da e anno_a non si applicano alle decisioni citate nelle massime; (c) i primi 300 caratteri di una massima usati come query producono risultati pertinenti o solo il rilassamento automatico; (d) senza massime il risultato coincide con giurisprudenza_su_norma sugli stessi parametri. |
| `giurisprudenza_su_norma` | ricerca_online | smoke_live | nessuna (media) | Italgiure SentenzeWeb, ricerca per frase esatta del riferimento | Assente dai paragrafi 5 e 7: né corretto né declassato. Punto critico: build_norma_variants mette sempre in OR le varianti nude 'art. N' e 'articolo N' con quelle qualificate dall'atto, quindi per articoli a numero basso (art. 13 GDPR, art. 2 L. 287/1990, art. 3 Cost.) il risultato comprende decisioni che citano lo stesso numero di un altro atto. Il benchmark deve misurare la precisione su un campione di 10 risultati e confrontare il totale con quello di una frase esatta. |
| `leggi_sentenza` | ricerca_online | smoke_live | nessuna (alta) | Italgiure SentenzeWeb (www.italgiure.giustizia.it/sncass) e sito della Corte di cassazione per sezione e data di deposito | Assente dai paragrafi 5 e 7 come tool; serve a chiudere la voce danno_parentale del paragrafo 7 (Cass. 10579/2021). Da confermare: (a) estremi e testo delle decisioni note; (b) numero e anno non sono univoci tra archivio civile e penale e con archivio 'tutti' il tool prende il primo documento; (c) il quarto passaggio non restituisce una decisione che si limita a citare quella richiesta; (d) limite inferiore reale dell'archivio pubblico; (e) troncamento del testo a 30000 caratteri dichiarato in risposta. |
| `ultime_pronunce` | ricerca_online | smoke_live | nessuna (media) | Sito della Corte di cassazione, ultime decisioni delle Sezioni Unite civili; Italgiure SentenzeWeb ordinato per data | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: ordinamento per data di pubblicazione (campo pd) coerente con la data di deposito; ritardo di indicizzazione (differenza tra la data più recente restituita e la data della prova); stesso problema del codice 'SU' di cerca_giurisprudenza per il filtro sezione. |

### `cerca_giurisprudenza`

Ricerca a testo libero nelle decisioni della Cassazione (Italgiure) con filtri strutturati, normalizzazione della query, rilassamento e raffinamento automatici, filtro per punteggio e modalità 'esplora' a sole faccette.

- Parametri: `query: str; archivio: 'civile' \| 'penale' \| 'tutti' = 'tutti'; materia: str = ''; sezione: str = '' (1-6, L, T, SU); anno_da: int = 0; anno_a: int = 0; tipo_provvedimento: 'sentenza' \| 'ordinanza' \| 'decreto' \| '' = ''; solo_sezioni_unite: bool = False; ordinamento: 'rilevanza' \| 'data' = 'rilevanza'; max_risultati: int = 5 (max 50); pagina: int = 0; campo: 'tutto' \| 'dispositivo' = 'tutto'; modalita: 'cerca' \| 'esplora' = 'cerca'`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Italgiure SentenzeWeb (Corte di cassazione)
- Casi di prova:
  - Decisione nota delle Sezioni Unite: `{"query": "fideiussione schema ABI nullità", "archivio": "civile", "solo_sezioni_unite": true, "anno_da": 2021, "anno_a": 2021}` → atteso: tra i risultati Cass. civ. Sezioni Unite n. 41994/2021, dep. 30/12/2021, con dispositivo o estratto
  - Stessa ricerca con sezione 'SU' come da docstring: `{"query": "fideiussione schema ABI nullità", "archivio": "civile", "sezione": "SU", "anno_da": 2021, "anno_a": 2021}` → atteso: stesso risultato del caso precedente; zero risultati o rilassamento automatico indicano che il codice 'SU' del docstring non corrisponde a quello dell'indice
  - Modalità esplora: `{"query": "danno parentale tabella punti", "archivio": "civile", "modalita": "esplora"}` → atteso: solo distribuzione per materia, sezione, anno e tipo, nessun documento; conteggi da leggere dalla fonte

### `giurisprudenza_articolo`

Giurisprudenza su un articolo guidata dalle massime Brocardi: legge su Italgiure le prime tre decisioni della Cassazione citate nelle massime e usa il testo di tre massime come query; senza massime ripiega su giurisprudenza_su_norma.

- Parametri: `riferimento: str; archivio: 'civile' \| 'penale' \| 'tutti' = 'tutti'; anno_da: int = 0; anno_a: int = 0; max_risultati: int = 5 (per tipo di ricerca)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonti: Brocardi.it e Italgiure
- Casi di prova:
  - Articolo con molte massime: `{"riferimento": "art. 2043 c.c.", "archivio": "civile", "anno_da": 2020, "max_risultati": 5}` → atteso: intestazione con il riferimento, riga 'Fonte Brocardi' con il numero di massime, sezioni 'Sentenze con riferimento diretto' (decisioni citate nelle massime e presenti in archivio) e 'Sentenze per principio di diritto'; riferimenti da confrontare con la scheda Brocardi dell'art. 2043 c.c.; da leggere dalla fonte
  - Atto non codicistico, archivio penale: `{"riferimento": "art. 6 D.Lgs. 231/2001", "archivio": "penale", "anno_da": 2021}` → atteso: da leggere dalla fonte; se Brocardi non restituisce massime il risultato deve coincidere con giurisprudenza_su_norma sugli stessi parametri

### `giurisprudenza_su_norma`

Decisioni della Cassazione che citano un articolo di legge, con varianti testuali del riferimento generate automaticamente (art., articolo, sigle e nomi dei codici o dei tipi di atto).

- Parametri: `riferimento: str; archivio: str = 'tutti'; solo_sezioni_unite: bool = False; anno_da: int = 0; anno_a: int = 0; max_risultati: int = 5 (max 50); pagina: int = 0`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Italgiure SentenzeWeb
- Casi di prova:
  - Articolo distintivo, decisione nota: `{"riferimento": "art. 1419 c.c.", "archivio": "civile", "solo_sezioni_unite": true, "anno_da": 2021, "anno_a": 2021, "max_risultati": 20}` → atteso: include Cass. civ. Sezioni Unite n. 41994/2021 (nullità parziale delle fideiussioni conformi allo schema ABI)
  - Articolo a numero basso, precisione: `{"riferimento": "art. 13 GDPR", "archivio": "civile", "anno_da": 2022, "anno_a": 2022}` → atteso: da leggere dalla fonte: totale e campione; almeno 8 decisioni su 10 devono citare l'art. 13 del Regolamento (UE) 2016/679, altrimenti la variante nuda 'art. 13' domina la ricerca

### `leggi_sentenza`

Testo integrale di una decisione della Cassazione da Italgiure per numero e anno, con ricerca in quattro passaggi (numero a cinque cifre con sezione, senza sezione, numero semplice, ricerca nel testo con controllo dell'identità).

- Parametri: `numero: int; anno: int; sezione: str = '' (1-6, L, T, SU); archivio: 'civile' \| 'penale' \| 'tutti' = 'tutti'`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Italgiure SentenzeWeb (Corte di cassazione), archivio dichiarato dal 2020
- Casi di prova:
  - Sezioni Unite civili, documento noto: `{"numero": 41994, "anno": 2021, "archivio": "civile"}` → atteso: intestazione 'Cass. civ.' Sezioni Unite (etichetta 'sez. un.' o 'SS.UU.'), n. 41994/2021, dep. 30/12/2021; testo sulle fideiussioni omnibus conformi allo schema ABI (nullità parziale ex art. 2 co. 2 lett. a) L. 287/1990 e art. 1419 c.c.); sezione Dispositivo presente
  - Sezione semplice con filtro sezione: `{"numero": 10579, "anno": 2021, "sezione": "3", "archivio": "civile"}` → atteso: Cass. civ., sez. III, n. 10579/2021 (ordinanza), dep. 21/04/2021 da riscontrare; testo sul danno da perdita del rapporto parentale e sulla tabella a punti; se non trovata, verificare la finestra temporale dell'archivio
  - Stesso numero senza archivio: `{"numero": 10579, "anno": 2021, "archivio": "tutti"}` → atteso: da leggere dalla fonte: se restituisce una decisione penale con lo stesso numero, documentare l'ambiguità e raccomandare nel docstring di indicare l'archivio

### `ultime_pronunce`

Ultime decisioni depositate dalla Cassazione in ordine di data, con filtri per materia, sezione, archivio, tipo di provvedimento e Sezioni Unite.

- Parametri: `materia: str = ''; sezione: str = '' (1-6, L, T, SU); archivio: str = 'tutti'; tipo_provvedimento: 'sentenza' \| 'ordinanza' \| 'decreto' \| '' = ''; solo_sezioni_unite: bool = False; max_risultati: int = 5 (max 50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Italgiure SentenzeWeb
- Casi di prova:
  - Ultime Sezioni Unite civili: `{"archivio": "civile", "solo_sezioni_unite": true, "max_risultati": 5}` → atteso: da leggere dalla fonte: cinque decisioni delle Sezioni Unite civili in ordine di deposito decrescente, la più recente coincidente con l'ultima pubblicata dalla Corte; nessuna data successiva al giorno della prova
  - Ultime sentenze penali: `{"archivio": "penale", "tipo_provvedimento": "sentenza", "max_risultati": 3}` → atteso: tre decisioni 'Cass. pen.' di tipo sentenza in ordine di deposito decrescente; da leggere dalla fonte

## legal_citations.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_brocardi` | ricerca_online | smoke_live | nessuna (media) | Brocardi.it, scheda dell'art. 2043 c.c.; Italgiure per le decisioni citate | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: numero e anno dei riferimenti Cassazione estratti dalle massime (campione di 5 confrontato con la pagina); i riferimenti anteriori al 2020 non sono leggibili con leggi_sentenza e la risposta non lo dice. |
| `cite_law` | ricerca_online | smoke_live | nessuna (alta) | Normattiva (Istituto Poligrafico e Zecca dello Stato), pagina dell'articolo vigente all'URN urn:nir:stato:...; EUR-Lex, Regolamento (UE) 2016/679 in italiano | Assente dai paragrafi 5 e 7 dell'audit: né corretto né declassato. È lo strumento della strategia solo_norma di tutto il benchmark (tests/unit/test_cartabia_live.py): va validato per primo e in locale, perché l'ambiente cloud blocca Normattiva, Brocardi, Italgiure, EUR-Lex e Gazzetta (paragrafo 2); tutte le prove di questo gruppo vanno marcate live. Da confermare: (a) che il testo sia quello vigente dell'articolo e non l'intera pagina (senza il blocco bodyTesto il ripiego HTML restituisce tutto il testo della pagina); (b) che un atto citato con il solo anno (L. 742/1969) sia risolto: il costruttore dell'URN usa la data 1969-01-01 al posto di 1969-10-07 e il campo urn in JSON la espone; (c) che un articolo abrogato non sia presentato come vigente. Serve a chiudere voci del paragrafo 7: artt. 2368 co. 2 e 2479-bis co. 3 c.c. (quorum_assembleari), art. 3 co. 3 CCII (test_crisi_impresa), TUIR vigente (calcolo_irpef), decorrenza delle soglie del giudice di pace nel D.Lgs. 116/2017 (competenza_giudice, da incrociare con iter_ddl su S.1939), DM 150/2023 artt. 28 e 30 se presente su Normattiva. Nessuna ricerca su avvocatoandreani.it eseguita in questa sessione (budget di ricerca web esaurito); per i 52 tool di ricerca online un calcolatore del sito non è comunque un termine di confronto, quindi pagina_andreani resta vuota per tutto il gruppo. |
| `download_law_pdf` | ricerca_online | smoke_live | nessuna (alta) | EUR-Lex, PDF in italiano del documento CELEX 32016R0679 | Assente dai paragrafi 5 e 7: né corretto né declassato. Tool che scrive file (elenco WRITES_FILES). Da confermare: CELEX costruito con anno e numero a quattro cifre; PDF generato per le norme italiane dichiarato non originale; cancellazione dei PDF più vecchi di un'ora; resa dei caratteri fuori dalla codifica windows-1252. |
| `fetch_act_index` | ricerca_online | smoke_live | nessuna (alta) | Normattiva, albero degli articoli del D.Lgs. 8 giugno 2001 n. 231 | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: numero di voci pari agli articoli dell'atto (articoli bis e ter compresi) e codice redazionale uguale a quello della Gazzetta Ufficiale. Utile al benchmark per individuare la norma di decorrenza del D.Lgs. 116/2017 (voce competenza_giudice del paragrafo 7) prima di leggerla con cite_law. |
| `fetch_full_act` | ricerca_online | smoke_live | nessuna (alta) | Normattiva, testo vigente della L. 7 ottobre 1969 n. 742 | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: risoluzione degli atti citati con il solo anno (l'URN è costruito con la data 01-01); testo vigente e completo; nessuna chiamata per gli atti UE. |
| `fetch_law_annotations` | ricerca_online | smoke_live | nessuna (media) | Brocardi.it, scheda dell'articolo; Normattiva per il testo della norma | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: risoluzione della pagina Brocardi per identità (tipo, numero, anno) anche per atti diversi dai codici; un articolo assente deve produrre un errore e mai la scheda di un altro atto. Il benchmark verifica esistenza e pertinenza della scheda, non l'esattezza della dottrina. |
| `fetch_law_article` | ricerca_online | smoke_live | nessuna (alta) | Normattiva, articolo vigente all'URN urn:nir:stato:legge:1969-10-07;742~art1; EUR-Lex, Regolamento (UE) 2016/679 in italiano | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: con la data completa l'URN è quello ufficiale; i tipi normalizzati senza data e numero (codici, Costituzione) sono risolti; 'regolamento ue' è instradato su EUR-Lex. Il caso della Costituzione verifica che l'URN costruito senza data (urn:nir:stato:costituzione~art24) sia accettato da Normattiva. |
| `verifica_citazioni` | ricerca_online | smoke_live | nessuna (alta) | Italgiure SentenzeWeb (Corte di cassazione) e Normattiva | Assente dai paragrafi 5 e 7: né corretto né declassato; serve a riscontrare citazioni dell'audit (Cass. 10579/2021 per danno_parentale; Cass. SS.UU. 19499/2008 per calcolo_maggior_danno, che deve risultare non verificabile). Da confermare: (a) il limite _ITALGIURE_MIN_YEAR = 2020 rispetto alla copertura reale dell'archivio: se è a finestra mobile, una decisione del 2020 o dei primi mesi del 2021 risulterebbe 'inesistente' invece che 'non verificabile'; (b) con archivio 'tutti' una citazione 'Cass. civ.' può essere confrontata con una decisione penale di stesso numero e anno, perché il tool non legge 'civ.' o 'pen.'; (c) il controllo di comma e lettera scatta solo se il testo numera i commi: su un articolo a comma unico non segnala nulla. |

### `cerca_brocardi`

Annotazioni Brocardi da un riferimento in linguaggio naturale, con i riferimenti strutturati (autorità, numero, anno) alle decisioni della Cassazione citate nelle massime, da leggere poi con leggi_sentenza.

- Parametri: `reference: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Brocardi.it
- Casi di prova:
  - Articolo del codice civile, documento noto: `{"reference": "art. 2043 c.c."}` → atteso: scheda Brocardi dell'art. 2043 c.c. come in fetch_law_annotations, più il blocco 'Riferimenti Cassazione' con autorità, numero e anno delle decisioni citate nelle massime
  - Riferimento senza articolo: `{"reference": "codice civile"}` → atteso: errore: specificare un articolo nel formato 'art. <numero> <atto>', nessuna chiamata di rete

### `cite_law`

Recupera il testo ufficiale di un articolo da un riferimento in linguaggio naturale: Normattiva per le norme italiane (prima l'esportazione Akoma Ntoso, poi la pagina HTML), EUR-Lex per regolamenti, direttive e considerando UE; annotazioni Brocardi facoltative; uscita markdown o JSON con URN.

- Parametri: `reference: str; include_annotations: bool = False; formato: 'markdown' \| 'json' = 'markdown'`
- Fonte normativa dichiarata: Nessuna riga Vigenza (tool di recupero testi); fonte: testo vigente su Normattiva ed EUR-Lex, annotazioni Brocardi
- Casi di prova:
  - Articolo del codice civile, documento noto: `{"reference": "art. 2043 c.c."}` → atteso: Riga Fonte con Normattiva (o Normattiva-Akn) e URL https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043; testo: 'Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno.'
  - Legge citata con il solo anno, uscita JSON (sospensione feriale): `{"reference": "art. 1 L. 742/1969", "formato": "json"}` → atteso: errore null; testo con 'sospeso di diritto dal 1° al 31 agosto di ciascun anno' e 'l'inizio stesso è differito alla fine di detto periodo' (art. 1 L. 742/1969 nel testo modificato dal DL 132/2014); atto.numero_atto '742'; URN ufficiale urn:nir:stato:legge:1969-10-07;742~art1: segnalare se il tool espone 1969-01-01
  - Articolo abrogato dalla riforma Cartabia: `{"reference": "art. 190 c.p.c.", "formato": "json"}` → atteso: testo che indica l'abrogazione (art. 190 c.p.c. abrogato dal D.Lgs. 149/2022) oppure errore esplicito; mai il vecchio schema di 60 e 80 giorni presentato come vigente
  - Considerando di regolamento UE: `{"reference": "considerando 42 GDPR"}` → atteso: Fonte EUR-Lex con URL del Regolamento (UE) 2016/679; testo del considerando 42 che inizia con 'Per i trattamenti basati sul consenso dell'interessato, il titolare del trattamento dovrebbe essere in grado di dimostrare che l'interessato ha acconsentito al trattamento'

### `download_law_pdf`

Scarica il PDF ufficiale da EUR-Lex per regolamenti e direttive UE, oppure genera un PDF dal testo Normattiva per le norme italiane; restituisce percorso, fonte e dimensione del file.

- Parametri: `reference: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: EUR-Lex (PDF ufficiale) e Normattiva (testo)
- Casi di prova:
  - Regolamento UE: `{"reference": "GDPR"}` → atteso: 'PDF scaricato' con file GDPR.pdf nella cartella temporanea mcp-legal-it e fonte https://eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:32016R0679; dimensione maggiore di zero
  - Legge italiana: `{"reference": "L. 742/1969"}` → atteso: 'PDF generato' dal testo Normattiva con la nota che non è il PDF originale; il PDF contiene il testo dell'art. 1

### `fetch_act_index`

Indice strutturato di un atto (elenco degli articoli con rubrica) da Normattiva, con il codice redazionale.

- Parametri: `reference: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Normattiva
- Casi di prova:
  - Decreto legislativo noto: `{"reference": "D.Lgs. 231/2001"}` → atteso: voci con rubrica, tra cui art. 5 'Responsabilità dell'ente' e art. 6 'Soggetti in posizione apicale e modelli di organizzazione dell'ente'; codice redazionale in coda
  - Atto non riconosciuto: `{"reference": "atto inventato 123/2099"}` → atteso: errore 'atto non riconosciuto' con eventuali suggerimenti, nessuna chiamata di rete

### `fetch_full_act`

Testo integrale di un atto italiano da Normattiva, senza troncamenti; per gli atti UE rinvia a download_law_pdf.

- Parametri: `reference: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Normattiva (testo vigente)
- Casi di prova:
  - Legge breve citata con il solo anno: `{"reference": "L. 742/1969"}` → atteso: titolo della legge 7 ottobre 1969 n. 742 (sospensione dei termini processuali nel periodo feriale); testo con l'art. 1 vigente (dal 1° al 31 agosto) e l'art. 3 sulle materie escluse con il rinvio all'art. 92 dell'ordinamento giudiziario; riga Fonte Normattiva e dimensione in caratteri
  - Atto UE: `{"reference": "GDPR"}` → atteso: messaggio che rinvia a download_law_pdf per gli atti UE, nessuna chiamata di rete

### `fetch_law_annotations`

Annotazioni Brocardi per un articolo indicato con parametri espliciti: posizione nel codice, ratio legis, spiegazione, massime giurisprudenziali.

- Parametri: `act_type: str; article: str; date: str = ''; act_number: str = ''`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Brocardi.it (contenuto redazionale di terzi, non fonte ufficiale)
- Casi di prova:
  - Articolo del codice civile, documento noto: `{"act_type": "codice civile", "article": "2043"}` → atteso: Riga Fonte Brocardi con URL https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html; posizione nel Libro IV, Titolo IX (fatti illeciti); rubrica 'Risarcimento per fatto illecito'; sezioni Spiegazione e Massime giurisprudenziali
  - Atto diverso da un codice: `{"act_type": "decreto legislativo", "article": "6", "date": "2001-06-08", "act_number": "231"}` → atteso: scheda Brocardi dell'art. 6 D.Lgs. 231/2001 (soggetti in posizione apicale e modelli di organizzazione dell'ente) oppure errore esplicito di mappatura; mai la scheda di un altro atto

### `fetch_law_article`

Recupero a basso livello di un articolo con parametri espliciti (tipo atto, data, numero) da Normattiva o EUR-Lex, per i casi di abbreviazione ambigua.

- Parametri: `act_type: str; article: str; date: str = '' (anno o AAAA-MM-GG, facoltativa per i codici); act_number: str = '' (facoltativo per i codici)`
- Fonte normativa dichiarata: Nessuna riga Vigenza (tool di recupero testi); fonte: Normattiva ed EUR-Lex
- Casi di prova:
  - Legge con data completa (sospensione feriale): `{"act_type": "legge", "article": "1", "date": "1969-10-07", "act_number": "742"}` → atteso: Riga Fonte Normattiva con URL https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742~art1; testo con 'sospeso di diritto dal 1° al 31 agosto di ciascun anno' (art. 1 L. 742/1969)
  - Regolamento UE: `{"act_type": "regolamento ue", "article": "6", "date": "2016", "act_number": "679"}` → atteso: Fonte EUR-Lex; art. 6 GDPR 'Liceità del trattamento' con le basi giuridiche da a) a f) del paragrafo 1
  - Costituzione senza data e numero: `{"act_type": "costituzione", "article": "24"}` → atteso: testo dell'art. 24 Cost. che inizia con 'Tutti possono agire in giudizio per la tutela dei propri diritti e interessi legittimi.'

### `verifica_citazioni`

Verifica esistenza e coerenza dei metadati di un elenco di citazioni (fino a 20): sentenze della Cassazione su Italgiure (numero, anno, sezione) e norme su Normattiva o EUR-Lex (comma e lettera); non verifica il contenuto.

- Parametri: `citazioni: str (una per riga o separate da virgola, massimo 20); archivio: 'civile' \| 'penale' \| 'tutti' = 'tutti'; formato: 'markdown' \| 'json' = 'markdown'`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonti: Italgiure (archivio dichiarato dal 2020), Normattiva, EUR-Lex
- Casi di prova:
  - Elenco misto con verdetti diversi: `{"citazioni": "Cass. SS.UU. n. 19499/2008\nCass. civ. sez. III n. 10579/2021\nart. 2043 c.c.\nart. 13 comma 9 GDPR", "archivio": "civile", "formato": "json"}` → atteso: quattro voci nell'ordine: 'non verificabile' (decisione del 2008 anteriore all'archivio), 'verificata' (Cass. civ. sez. III n. 10579/2021, se l'archivio copre ancora aprile 2021), 'verificata' con fonte Normattiva, 'metadati discordanti' (l'art. 13 GDPR ha i paragrafi da 1 a 4); troncato false; errore null
  - Sezione sbagliata su una decisione delle Sezioni Unite: `{"citazioni": "Cass. sez. I n. 41994/2021", "archivio": "civile"}` → atteso: 'metadati discordanti': la decisione esiste ma è delle Sezioni Unite
  - Decisione inesistente: `{"citazioni": "Cass. civ. n. 99999/2023", "archivio": "civile"}` → atteso: 'inesistente'

## modelli_atti.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `esporta_atto_docx` | documento | strutturale | nessuna pagina del sito | nessuna fonte normativa: controllo del DOCX prodotto con python-docx | Non toccato dall'audit di settembre 2026. Nessun riferimento normativo da verificare: il benchmark controlla la fedeltà della conversione e i metadati. Nota tecnica: salva in /tmp/mcp-legal-it in modo fisso, mentre analisi_fornitori usa tempfile.gettempdir(). |
| `genera_modello_atto` | documento | strutturale | nessuna pagina del sito | c.p.c. e disp. att. c.p.c. via cite_law; verifica_citazioni sui riferimenti del catalogo | Catalogo corretto dall'audit di settembre 2026 al par. 4.6 (appello aumentato della metà, esenzione lavoro, artt. 481 e 644, DM 150/2023), non ai par. 5 e 7. Scostamento rilevato: le 11 voci della categoria attestazioni citano ancora l'art. 16-bis co. 9-bis o l'art. 16-undecies DL 179/2012, mentre i modelli di atti_giudiziari.py sono passati agli artt. 196-octies ss. disp. att. c.p.c. (art. 16-undecies abrogato dall'art. 11 D.Lgs. 149/2022; le vecchie norme restano per i procedimenti pendenti al 28/02/2023). Il benchmark deve allineare il catalogo. Le pagine di redazione del sito (es. https://www.avvocatoandreani.it/servizi/attestazione-conformita.php) possono servire da confronto sui riferimenti. |
| `lista_categorie_atti` | utilita | non_applicabile | nessuna pagina del sito |  | Utilità interna. Il catalogo sottostante è stato corretto dall'audit al par. 4.6; il conteggio va solo tenuto coerente con genera_modello_atto. |

### `esporta_atto_docx`

Converte un testo Markdown semplice (titoli, grassetto, corsivo, elenchi, citazioni) in un file DOCX salvato in /tmp/mcp-legal-it.

- Parametri: `testo: str (Markdown semplice), titolo: str = 'Atto', autore: str = ''`
- Fonte normativa dichiarata: nessuna riga Vigenza (utilità di formattazione)
- Casi di prova:
  - Conversione completa: `{"testo": "# Atto di citazione\n## Fatto\nIl **sig. Rossi** ha *consegnato* la merce.\n- primo\n- secondo\n1. uno\n2. due\n> nota\n### Diritto\nArt. 1218 c.c.", "titolo": "Citazione Rossi/Bianchi", "autore": "Avv. X"}` → atteso: file .docx con Heading 1/2/3, run in grassetto e in corsivo, stili List Bullet e List Number, citazione in corsivo; proprietà title 'Citazione Rossi/Bianchi' e author 'Avv. X'; nome file sanificato
  - Testo vuoto: `{"testo": "   "}` → atteso: 'Errore: il testo dell'atto è vuoto.' e nessun file

### `genera_modello_atto`

Restituisce i metadati per comporre un atto (struttura, campi, tool di calcolo, riferimenti normativi, avvertenze) da un catalogo di 100 tipi; modalità 'catalogo' e 'cerca'.

- Parametri: `tipo_atto: str (identificativo del catalogo, oppure 'catalogo' o 'cerca'), parametri: dict \| None = None ({'query': ...} con 'cerca'), accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: nessuna riga Vigenza; riferimenti per atto nel catalogo modelli_atti.json
- Casi di prova:
  - Attestazione di copia informatica: `{"tipo_atto": "attestazione_copia_informatica"}` → atteso: riferimenti agli artt. 196-decies e 196-undecies disp. att. c.p.c. per i procedimenti iniziati dal 28/02/2023; oggi il catalogo cita solo l'art. 16-bis co. 9-bis DL 179/2012
  - Ricerca delle nuove norme PCT: `{"tipo_atto": "cerca", "parametri": {"query": "196-octies"}}` → atteso: le voci di attestazione; oggi 0 risultati
  - Atto di precetto: `{"tipo_atto": "atto_di_precetto"}` → atteso: riferimenti artt. 479-481 c.p.c.; avvertenza di inefficacia se l'esecuzione non inizia entro 90 giorni (art. 481); rinvio al tool diretto atto_di_precetto, il cui testo deve contenere l'avvertimento sulla crisi da sovraindebitamento (art. 480 co. 2)
  - Citazione ordinaria: `{"tipo_atto": "citazione_ordinaria"}` → atteso: art. 163 c.p.c. e D.Lgs. 149/2022; termini a comparire di almeno 120 giorni (150 all'estero) ex art. 163-bis

### `lista_categorie_atti`

Restituisce le categorie del catalogo degli atti con il conteggio per ciascuna.

- Parametri: `accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: nessuna riga Vigenza (catalogo interno)
- Casi di prova:
  - Conteggio attuale: `{}` → atteso: 100 atti in 10 categorie: esecuzione 19, preventivi 17, atti_introduttivi 12, attestazioni 11, notifiche 9, stragiudiziale 8, procure 8, privacy 8, istanze 6, pct 2; coerente con totale_tipi di genera_modello_atto(tipo_atto='catalogo')

## orientamento.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `mappa_orientamento` | ricerca_online | smoke_live | nessuna (bassa) | Brocardi.it (massime dell'articolo) e Italgiure SentenzeWeb | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: l'ancoraggio elenca anche decisioni anteriori al 2020, non consultabili su Italgiure, senza segnalarlo; se Brocardi non risponde la mappa è comunque prodotta; stessi punti di orientamento_su_norma sui conteggi. |
| `orientamento_su_norma` | ricerca_online | smoke_live | nessuna (media) | Italgiure SentenzeWeb (conteggi per sezione e anno con gli stessi filtri); Normattiva per l'art. 15 L. 132/2025 | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: (a) somma dei conteggi per anno pari al totale; (b) le varianti nude 'art. N' (vedi giurisprudenza_su_norma) gonfiano i conteggi per gli articoli a numero basso; (c) nessuna parola predittiva nel corpo; (d) leggere con cite_law l'art. 15 L. 132/2025: la norma riserva al magistrato le decisioni nell'attività giudiziaria, mentre il docstring parla di 'giustizia predittiva vietata', formula da allineare al testo. |
| `orientamento_su_principio` | ricerca_online | smoke_live | nessuna (media) | Italgiure SentenzeWeb, stessa ricerca con i filtri corrispondenti | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: il blocco Sezioni Unite ignora il filtro sezione (interroga sempre szdec U); coerenza del codice U con quello indicato altrove ('SU' nel docstring di cerca_giurisprudenza); segnali testuali presentati come conteggi di espressioni e non come classificazione delle decisioni. |

### `mappa_orientamento`

Mappa descrittiva completa su un articolo: ancoraggio alle massime Brocardi (fino a cinque riferimenti Cassazione) seguito dalla mappa di orientamento_su_norma.

- Parametri: `riferimento: str; archivio: str = 'tutti'; anno_da: int = 0`
- Fonte normativa dichiarata: Nessuna riga Vigenza; limite dichiarato: art. 15 L. 132/2025; fonti: Brocardi.it e Italgiure
- Casi di prova:
  - Articolo con massime Brocardi: `{"riferimento": "art. 2043 c.c.", "archivio": "civile", "anno_da": 2020}` → atteso: blocco 'Ancoraggio Brocardi (massime consolidate)' con il numero di massime e fino a cinque riferimenti Cassazione, da confrontare con la scheda Brocardi; di seguito la mappa di orientamento_su_norma con avvertenza L. 132/2025; da leggere dalla fonte

### `orientamento_su_norma`

Mappa descrittiva, non predittiva, degli orientamenti della Cassazione su un articolo: blocco Sezioni Unite, cluster per sezione, andamento per anno e conteggi dei segnali testuali di contrasto o conformità.

- Parametri: `riferimento: str; archivio: str = 'tutti'; anno_da: int = 0; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; limite dichiarato nel modulo: art. 15 L. 132/2025 (decisioni riservate al magistrato); fonte: Italgiure
- Casi di prova:
  - Articolo con Sezioni Unite note: `{"riferimento": "art. 1419 c.c.", "archivio": "civile", "anno_da": 2021, "max_risultati": 10}` → atteso: titolo 'Orientamento giurisprudenziale' con il riferimento; blocco Sezioni Unite con il totale e fino a cinque pronunce (Cass. civ. SS.UU. n. 41994/2021 se tra le cinque più recenti); cluster per sezione; andamento per anno; segnali testuali; piè di pagina con orizzonte dal 2020 e avvertenza art. 15 L. 132/2025
  - Articolo a numero basso: `{"riferimento": "art. 13 GDPR", "archivio": "civile", "anno_da": 2022}` → atteso: da leggere dalla fonte: totale da confrontare con giurisprudenza_su_norma sugli stessi parametri; un totale di decine di migliaia indica che la variante nuda 'art. 13' domina il conteggio

### `orientamento_su_principio`

Mappa descrittiva degli orientamenti della Cassazione su un principio in linguaggio libero (query normalizzata), con blocco Sezioni Unite, cluster per sezione, andamento per anno e segnali testuali.

- Parametri: `principio: str; archivio: str = 'tutti'; anno_da: int = 0; sezione: str = '' (1-7, L, T, U); max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; limite dichiarato: art. 15 L. 132/2025; fonte: Italgiure
- Casi di prova:
  - Principio con Sezioni Unite note: `{"principio": "fideiussione omnibus schema ABI nullità parziale", "archivio": "civile", "anno_da": 2021}` → atteso: blocco Sezioni Unite con Cass. civ. SS.UU. n. 41994/2021, dep. 30/12/2021; cluster per sezione; andamento per anno; avvertenza L. 132/2025
  - Filtro sezione: `{"principio": "fideiussione omnibus schema ABI nullità parziale", "archivio": "civile", "anno_da": 2021, "sezione": "1"}` → atteso: cluster con la sola Sezione I; blocco Sezioni Unite invariato rispetto al caso precedente

## parcelle_professionisti.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `compenso_ctu` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-onorario-ctu-liquidazione-tariffe.php (alta) | Ministero della Giustizia, DM 30 maggio 2002 (tabelle dei compensi di periti e consulenti tecnici); art. 4 L. 319/1980; Corte cost. sent. n. 16/2025; art. 52 DPR 115/2002 | Già INDICATIVO; docstring reso esplicito dall'audit (paragrafo 7, confidenza media): stime di mercato, tabelle del DM 30/05/2002 e vacazioni non riprodotte; l'audit segnala un aggiornamento delle tabelle che il TAR Lazio avrebbe imposto nel 2026, da verificare. Il benchmark deve documentare per tipologia lo scostamento dalla liquidazione del sito e confermare: vacazione di due ore a 14,68 euro, anche per quelle successive alla prima dopo la sentenza della Corte costituzionale n. 16/2025 (prima 8,15); onorari a percentuale per scaglioni e onorari fissi del DM 30/05/2002 per stima di immobili, perizie contabili e accertamenti medico-legali. La nota del tool sulla 'CPA 4%' riguarda gli avvocati: per il CTU vale il contributo della propria cassa. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `compenso_curatore_fallimentare` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-curatore-fallimentare.php (alta) | Ministero della Giustizia, DM 25 gennaio 2012 n. 30 (GU n. 72 del 26/03/2012), art. 1 | Declassato a INDICATIVO dall'audit (paragrafo 7, confidenza alta sulla struttura), da riscrivere sul decreto. Il tool usa percentuali singole estranee al decreto e calcola il passivo a metà delle percentuali dell'attivo. Il DM 30/2012, art. 1, fissa forbici minimo-massimo: attivo 12-14% fino a 16.227,08; 10-12% fino a 24.340,62; 8,50-9,50% fino a 40.567,68; 7-8% fino a 81.135,38; 5,50-6,50% fino a 405.676,89; 4-5% fino a 811.353,79; 0,90-1,80% fino a 2.434.061,37; 0,45-0,90% oltre; passivo 0,19-0,94% sui primi 81.131,38 e 0,06-0,46% oltre; minimo 811,35. Il docstring colloca lo 0,45-0,90% 'oltre 811.313,60' e dichiara un massimo di 405.656,80 euro: entrambi da verificare sul testo. Il sito restituisce minimo, medio e massimo e aggiunge il rimborso forfettario delle spese del 5%, che il tool non calcola. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `compenso_delegati_vendite` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-delegati-vendite-giudiziarie.php (alta) | DM 15 ottobre 2015 n. 227 (GU n. 45 del 24/02/2016) come modificato dal DM 104/2021, art. 2 | Declassato a INDICATIVO dall'audit (paragrafo 7, confidenza media). Il tool applica percentuali (2,6% con minimo 1.100, 1,5%, 0,75%) che non sono nel decreto: il DM 227/2015 prevede compensi fissi per fase (dall'incarico all'avviso di vendita, dall'avviso all'aggiudicazione, trasferimento della proprietà, distribuzione del ricavato) per tre scaglioni di prezzo (fino a 100.000, da 100.000 a 500.000, oltre 500.000), aumenti e riduzioni rideterminati dal DM 104/2021 e rimborso forfettario delle spese generali (10% secondo il docstring). Una fonte secondaria indica 1.000 euro per ciascuna fase nel primo scaglione: da confermare in GU. Confermare sul sito gli importi per fase e i confini di scaglione. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `compenso_mediatore_familiare` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-compenso-mediatore-familiare.php (alta) | Decreto interministeriale 27 ottobre 2023 n. 151 (GU n. 255 del 31/10/2023) | Declassato a INDICATIVO dall'audit (paragrafo 7, confidenza alta sull'esistenza del decreto e media sugli importi), da trascrivere. Il primo incontro informativo gratuito è confermato dalle fonti. Il parametro del decreto è diverso dal tool: 40 euro per ogni incontro effettivamente svolto e per ciascuna parte, moltiplicati per 1, 1,5 o 2 secondo complessità e conflittualità, più il 21% di costi forfettari e gli oneri di legge; il tool usa una tariffa libera per incontro (120 euro di default, riferita all'intero incontro). Nel test annotare che il tool riproduce il decreto solo con tariffa_incontro = 80 x coefficiente x 1,21. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `compenso_orario` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-somma-ore-minuti-compensi-a-tempo.php (alta) |  | Non toccato dall'audit; calcolo aritmetico senza base normativa, precisione ESATTO. Il calcolatore del sito somma ore e minuti e moltiplica per la tariffa senza arrotondamento: coincide con il tool solo quando il tempo è multiplo dell'unità scelta; negli altri casi la differenza è di convenzione e va documentata nel test, non corretta. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `fattura_enasarco` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_fattura_agente_enasarco.php (alta) | Fondazione Enasarco, 'Minimali e massimali 2026' (enasarco.it); art. 25-bis DPR 600/1973 | Declassato dall'audit per massimale e minimale (paragrafo 7, confidenza media): costanti di 443 euro trimestrali e 27.000 euro annui, non applicate al calcolo e non distinte per tipo di mandato; il parametro anno è ignorato e tipo_agente non incide sul risultato. Valori 2026 della Fondazione Enasarco: aliquota 17% (8,5% agente e 8,5% preponente); monomandatari massimale provvigionale 45.717 euro per rapporto (contributo massimo 7.771,89) e minimale 1.026 euro annui (256,50 a trimestre); plurimandatari massimale 30.478 (5.181,26) e minimale 515 (128,75 a trimestre). Confermare anche la ritenuta del 23% sul 20% delle provvigioni per l'agente che si avvale di dipendenti o terzi (art. 25-bis co. 2 DPR 600/1973), non gestita dal tool e selezionabile sul sito. Il riferimento 'D.Lgs. 303/1996' della riga Vigenza va verificato con verifica_citazioni (il D.Lgs. 303/1991 riguarda il contratto di agenzia). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `fattura_professionista` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_fattura_generica_scorporo.php (alta) | Regolamenti di contribuzione delle casse (CIPAG, ENPAP, ENPAM, Inarcassa, CNPADC, ENPACL); art. 10 co. 1 n. 18 DPR 633/1972 per le prestazioni sanitarie | Corretto dall'audit (paragrafo 5): la rivalsa INPS 4% della gestione separata concorre alla base della ritenuta (208 su 1.040, il caso che il calcolatore del sito riproduce), il contributo integrativo di cassa ne è escluso (200); aliquote delle casse dichiarate INDICATIVE. Il test esistente tests/comparison/test_parcelle_prof.py è aritmetico. Scostamenti da confermare sulle fonti delle casse: CIPAG 5% dal 01/01/2015 (4% solo verso le pubbliche amministrazioni del conto consolidato), il tool usa 4%; ENPAP 2%, il tool usa 5% e il test test_psicologo fissa il 5%; ENPAM senza contributo integrativo in fattura ai pazienti privati (il 2% e il 4% riguardano le strutture accreditate); per medici e psicologi le prestazioni sanitarie sono esenti IVA (art. 10 co. 1 n. 18 DPR 633/1972) con bollo di 2 euro, mentre il tool applica sempre l'IVA 22% nel regime ordinario. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `ricevuta_prestazione_occasionale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-ricevuta-prestazione-occasionale.php (alta) | INPS, circolare 2026 sulle aliquote della gestione separata (compensi occasionali oltre 5.000 euro, art. 44 co. 2 DL 269/2003 conv. L. 326/2003) | Non toccato dall'audit. Ritenuta del 20% e soglia del bollo esatte. Da confermare sul sito: soglia del bollo (77,47 escluso, 77,48 incluso); ritenuta dovuta solo se il committente è sostituto d'imposta (il tool la applica sempre); trattamento oltre 5.000 euro annui, che il tool cita come 'limite' senza calcolare i contributi della gestione separata sull'eccedenza (un terzo a carico del prestatore). Controllo strutturale del testo: riferimenti ad art. 2222 c.c., art. 67 co. 1 lett. l) TUIR e art. 5 DPR 633/1972 (fuori campo IVA); gli importi sono formattati con il punto decimale (€77.48) invece della virgola. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `ritenuta_acconto` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-ritenuta-d-acconto.php (alta) | Agenzia delle Entrate, istruzioni della Certificazione Unica 2026, quadro lavoro autonomo (punti 4, 8 e 9) | Non toccato dall'audit. Calcolo esatto: confermare sul sito l'arrotondamento al centesimo e l'aliquota del 30% per i non residenti (art. 25 co. 2 DPR 600/1973). Scostamento da confermare sulle istruzioni della CU: nel quadro lavoro autonomo il punto 4 è l'ammontare lordo, il punto 8 l'imponibile e il punto 9 le ritenute a titolo d'acconto, mentre il tool etichetta punto_8 come ritenute e punto_9 come netto (campo inesistente). Confermare anche la consegna della CU entro il 16 marzo e il codice tributo 1040. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `spese_mediazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-spese-di-mediazione.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-costi-e-tariffe-mediazione-civile.php | Ministero della Giustizia, DM 24 ottobre 2023 n. 150 (GU n. 255 del 31/10/2023), artt. 28-31 e Allegato A (Tabella A) | Declassato a INDICATIVO dall'audit (paragrafo 7, confidenza media), da riscrivere sul DM 150/2023. Lo schema del tool (indennità per scaglione in due colonne positivo e negativo, riduzione di un terzo, nessuna spesa di avvio) ricalca il DM 180/2010. Da confermare: spese di avvio 40/75/110 euro (art. 28), spese di mediazione fisse per il primo incontro, nessun altro importo se al primo incontro non si raggiunge l'accordo, Tabella A con aumento del 10% per l'accordo al primo incontro e del 25% negli incontri successivi (art. 30), IVA. La pagina calcolo-costi-e-tariffe-mediazione-civile.php del sito sembra riferita al regime precedente: verificarlo prima di usarla. Fase 0: pagina confermata; seconda pagina sulle tariffe. |
| `tariffe_mediazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-costi-e-tariffe-mediazione-civile.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-spese-di-mediazione.php | DM 24 ottobre 2023 n. 150 (GU n. 255 del 31/10/2023), art. 28, art. 30 e Tabella A | Declassato a INDICATIVO dall'audit (paragrafo 7). Le spese di avvio di 40/75/110 euro corrispondono all'art. 28 DM 150/2023 (confermato dalle fonti); il resto della tabella ricalca il DM 180/2010. Da confermare: confini 1.000/1.000,01 e 50.000/50.000,01 delle spese di avvio, importi della Tabella A e aumenti dell'art. 30 (10% e 25%), IVA sulle spese di avvio (il tool la calcola solo sull'indennità). Le etichette usano la virgola come separatore delle migliaia ('fino a €1,000'). Fase 0: il sito ha una pagina dedicata alle tariffe della mediazione oltre a quella delle spese. |

### `compenso_ctu`

Stima indicativa del compenso del consulente tecnico d'ufficio a percentuale sul valore e a tariffa oraria per tipologia di incarico.

- Parametri: `tipo_incarico: str (perizia_immobiliare, perizia_contabile, perizia_medica, stima_danni, accertamenti_tecnici); valore_causa: float \| None = None; ore_lavoro: float \| None = None`
- Fonte normativa dichiarata: DPR 115/2002; DM 30/05/2002
- Casi di prova:
  - Perizia medica a ore: `{"tipo_incarico": "perizia_medica", "valore_causa": null, "ore_lavoro": 10}` → atteso: A vacazioni: 10 ore = 5 vacazioni x 14,68 = 73,40 euro (art. 4 L. 319/1980 e DM 30/05/2002 dopo Corte cost. 16/2025; con la regola previgente 14,68 + 4 x 8,15 = 47,28); onorario fisso dell'accertamento medico-legale da leggere dal sito. Il tool: 1.000-2.000 euro.
  - Stima immobiliare a percentuale: `{"tipo_incarico": "perizia_immobiliare", "valore_causa": 100000, "ore_lavoro": null}` → atteso: Onorario a percentuale per scaglioni della tabella del DM 30/05/2002 per la stima di immobili: da leggere dal sito. Il tool: 500-2.000 euro (0,5-2%).
  - Perizia contabile con valore e ore: `{"tipo_incarico": "perizia_contabile", "valore_causa": 500000, "ore_lavoro": 40}` → atteso: Tabella del DM 30/05/2002 per le perizie contabili: da leggere dal sito; a vacazioni 20 x 14,68 = 293,60 euro. Il tool: 5.000-15.000 a percentuale e 2.800-5.200 a ore.
  - Nessun dato di calcolo: `{"tipo_incarico": "stima_danni", "valore_causa": null, "ore_lavoro": null}` → atteso: Errore: specificare almeno valore_causa o ore_lavoro.

### `compenso_curatore_fallimentare`

Compenso del curatore fallimentare su attivo realizzato e passivo accertato per scaglioni progressivi, con minimo e massimo.

- Parametri: `attivo_realizzato: float; passivo_accertato: float`
- Fonte normativa dichiarata: DM 30/2012 (minimo 811,35 e massimo 405.656,80 dichiarati)
- Casi di prova:
  - Confine del primo scaglione, passivo nullo: `{"attivo_realizzato": 16227.08, "passivo_accertato": 0}` → atteso: Art. 1 lett. a: 12-14% = 1.947,25-2.271,79 euro; il tool restituisce 2.271,79 (il massimo).
  - Procedura media: `{"attivo_realizzato": 100000, "passivo_accertato": 200000}` → atteso: Attivo 8.015,20-9.258,60; passivo 225,47-1.309,43; totale 8.240,67-10.568,03. Il tool: 11.226,76, fuori forbice (attivo 6.714,69 sotto il minimo, passivo 4.512,07 oltre il massimo).
  - Procedura piccola, soglia del minimo: `{"attivo_realizzato": 5000, "passivo_accertato": 10000}` → atteso: Attivo 600-700 e passivo 19-94: totale 619-794, portato al minimo di 811,35. Il tool: 1.400,00.
  - Procedura grande, scaglioni alti: `{"attivo_realizzato": 3000000, "passivo_accertato": 5000000}` → atteso: Attivo 58.205,59-83.713,63; passivo 3.105,47-23.389,43; totale 61.311,06-107.103,06. Il tool: 91.536,18 (passivo 40.512,07 oltre il massimo).

### `compenso_delegati_vendite`

Compenso del professionista delegato alle vendite giudiziarie immobiliari in funzione del prezzo di aggiudicazione.

- Parametri: `prezzo_aggiudicazione: float`
- Fonte normativa dichiarata: DM 227/2015 (minimo 1.100 fino a 100.000 dichiarato)
- Casi di prova:
  - Primo scaglione sotto la soglia del minimo del tool: `{"prezzo_aggiudicazione": 40000}` → atteso: Compensi fissi per fase dello scaglione fino a 100.000 (art. 2 DM 227/2015): da leggere dal sito. Il tool: 1.100 (minimo).
  - Ultimo euro del primo scaglione: `{"prezzo_aggiudicazione": 100000}` → atteso: Da leggere dal sito. Il tool: 2.600.
  - Primo centesimo del secondo scaglione: `{"prezzo_aggiudicazione": 100000.01}` → atteso: Da leggere dal sito, atteso un salto dei compensi fissi per fase. Il tool: 2.600, senza salto.
  - Terzo scaglione: `{"prezzo_aggiudicazione": 600000}` → atteso: Scaglione oltre 500.000: da leggere dal sito, più rimborso forfettario delle spese generali. Il tool: 9.350.

### `compenso_mediatore_familiare`

Compenso del mediatore familiare per numero di incontri, con primo incontro informativo gratuito e tariffa per incontro libera.

- Parametri: `n_incontri: int; tariffa_incontro: float = 120.0`
- Fonte normativa dichiarata: DM 27/10/2023 n. 151, art. 473-bis.10 c.p.c. (non trascritto)
- Casi di prova:
  - Solo incontro informativo: `{"n_incontri": 1, "tariffa_incontro": 120.0}` → atteso: Compenso 0: primo incontro informativo gratuito (DM 151/2023).
  - Cinque incontri con la tariffa di default: `{"n_incontri": 5, "tariffa_incontro": 120.0}` → atteso: DM 151/2023 con due parti e 4 incontri a pagamento: 320 x coefficiente + 21% = 387,20 (bassa complessità), 580,80 (media), 774,40 (alta), oltre oneri di legge. Il tool: 480,00.
  - Tariffa equivalente alla bassa complessità: `{"n_incontri": 5, "tariffa_incontro": 96.8}` → atteso: 387,20 euro, pari al valore di bassa complessità del decreto (80 x 1,21 per incontro).
  - Numero di incontri non valido: `{"n_incontri": 0, "tariffa_incontro": 120.0}` → atteso: Errore: numero incontri almeno 1.

### `compenso_orario`

Compenso a tempo con arrotondamento per eccesso al quarto d'ora, alla mezz'ora o all'ora.

- Parametri: `tariffa_oraria: float; ore: int; minuti: int = 0 (0-59); arrotondamento: str = 'mezz_ora' (quarto_ora, mezz_ora, ora)`
- Fonte normativa dichiarata: Nessuna riga Vigenza (calcolo aritmetico)
- Casi di prova:
  - Tempo multiplo della mezz'ora: `{"tariffa_oraria": 100, "ore": 2, "minuti": 30, "arrotondamento": "mezz_ora"}` → atteso: 250,00 euro (2,5 ore esatte): coincide con il sito.
  - Arrotondamento per eccesso alla mezz'ora: `{"tariffa_oraria": 100, "ore": 2, "minuti": 10, "arrotondamento": "mezz_ora"}` → atteso: Tool 250,00 (arrotondato a 2h30); il sito senza arrotondamento 216,67: differenza di convenzione.
  - Un minuto arrotondato all'ora: `{"tariffa_oraria": 80, "ore": 0, "minuti": 1, "arrotondamento": "ora"}` → atteso: Tool 80,00; sito 1,33: differenza di convenzione.
  - Quarti d'ora esatti: `{"tariffa_oraria": 90, "ore": 1, "minuti": 45, "arrotondamento": "quarto_ora"}` → atteso: 157,50 euro sia nel tool sia sul sito.

### `fattura_enasarco`

Fattura dell'agente di commercio con contributo Enasarco ripartito tra agente e preponente, IVA e ritenuta d'acconto sul 50% delle provvigioni.

- Parametri: `provvigioni: float; tipo_agente: str = 'monocommittente' (monocommittente, pluricommittente); anno: int = 2026`
- Fonte normativa dichiarata: D.Lgs. 303/1996, Regolamento Enasarco; aliquota 2026 17% (8,5% + 8,5%)
- Casi di prova:
  - Monomandatario sotto il massimale: `{"provvigioni": 10000, "tipo_agente": "monocommittente", "anno": 2026}` → atteso: Contributo 1.700,00 (850 agente e 850 preponente); IVA 2.200,00; ritenuta 1.150,00 (23% su 5.000, art. 25-bis DPR 600/1973); totale fattura 12.200,00; netto 10.200,00.
  - Monomandatario oltre il massimale 2026: `{"provvigioni": 50000, "tipo_agente": "monocommittente", "anno": 2026}` → atteso: Se 50.000 euro sono le provvigioni annue del rapporto, contributo limitato dal massimale di 45.717: 7.771,89 (quota agente 3.885,95). Il tool: 8.500,00 (quota agente 4.250,00).
  - Plurimandatario oltre il massimale 2026: `{"provvigioni": 40000, "tipo_agente": "pluricommittente", "anno": 2026}` → atteso: Massimale plurimandatari 30.478: contributo massimo 5.181,26 (quota agente 2.590,63). Il tool: 6.800,00.
  - Anno diverso della tabella: `{"provvigioni": 1000, "tipo_agente": "pluricommittente", "anno": 2025}` → atteso: Contributo 170,00; IVA 220,00; ritenuta 115,00; netto 1.020,00; per il 2025 minimale e massimale vanno letti dalle tabelle Enasarco 2025, mentre il tool restituisce le stesse costanti del 2026.

### `fattura_professionista`

Fattura del professionista non avvocato con contributo previdenziale (rivalsa INPS o contributo integrativo di cassa), IVA e ritenuta d'acconto, o regime forfettario con bollo.

- Parametri: `imponibile: float; tipo: str = 'ingegnere' (gestione_separata, ingegnere, architetto, geometra, commercialista, consulente_lavoro, psicologo, medico); regime: str = 'ordinario' (ordinario, forfettario)`
- Fonte normativa dichiarata: DPR 633/1972; art. 25 DPR 600/1973; L. 190/2014; art. 1 co. 212 L. 662/1996; leggi istitutive delle casse
- Casi di prova:
  - Gestione separata, regime ordinario: `{"imponibile": 1000, "tipo": "gestione_separata", "regime": "ordinario"}` → atteso: Rivalsa INPS 40,00; imponibile IVA 1.040,00; IVA 228,80; ritenuta 208,00 (20% su compenso e rivalsa); totale fattura 1.268,80; netto 1.060,80. Coincide con il sito secondo l'audit.
  - Ingegnere con Inarcassa, regime ordinario: `{"imponibile": 1000, "tipo": "ingegnere", "regime": "ordinario"}` → atteso: Contributo integrativo 4% = 40,00, soggetto a IVA ma escluso dalla ritenuta: IVA 228,80; ritenuta 200,00; netto 1.068,80.
  - Geometra, aliquota CIPAG: `{"imponibile": 1000, "tipo": "geometra", "regime": "ordinario"}` → atteso: CIPAG 5%: contributo 50,00; IVA 231,00; ritenuta 200,00; netto 1.081,00 (da leggere dalla fonte). Il tool usa il 4%: contributo 40,00, netto 1.068,80.
  - Psicologo, aliquota ENPAP e regime IVA: `{"imponibile": 1000, "tipo": "psicologo", "regime": "ordinario"}` → atteso: ENPAP 2% = 20,00; per la prestazione sanitaria esente IVA (art. 10 co. 1 n. 18 DPR 633/1972) nessuna IVA e bollo 2,00; ritenuta 200,00 solo se il committente è sostituto d'imposta. Il tool: contributo 50,00, IVA 231,00, netto 1.081,00. Da leggere dalla fonte.
  - Forfettario un centesimo sopra la soglia del bollo: `{"imponibile": 74.5, "tipo": "gestione_separata", "regime": "forfettario"}` → atteso: Rivalsa 2,98; importo 77,48: bollo 2,00; totale 79,48; nessuna IVA e nessuna ritenuta. Con imponibile 74,49 (totale 77,47) il bollo non è dovuto.

### `ricevuta_prestazione_occasionale`

Testo della ricevuta per prestazione occasionale con ritenuta d'acconto del 20% e bollo di 2 euro oltre 77,47 euro.

- Parametri: `compenso_lordo: float; committente: str; prestatore: str; descrizione: str`
- Fonte normativa dichiarata: Art. 2222 c.c.; art. 67 co. 1 lett. l) TUIR; art. 25 DPR 600/1973
- Casi di prova:
  - Importo esattamente sulla soglia del bollo: `{"compenso_lordo": 77.47, "committente": "Beta S.r.l.", "prestatore": "Luca Bianchi", "descrizione": "Traduzione di un contratto"}` → atteso: Ritenuta 15,49; netto 61,98; nessun bollo (importo non superiore a 77,47).
  - Un centesimo sopra la soglia: `{"compenso_lordo": 77.48, "committente": "Beta S.r.l.", "prestatore": "Luca Bianchi", "descrizione": "Traduzione di un contratto"}` → atteso: Ritenuta 15,50; netto 61,98; bollo 2,00 (art. 13 Tariffa parte I DPR 642/1972).
  - Compenso oltre la franchigia contributiva di 5.000 euro: `{"compenso_lordo": 6000, "committente": "Beta S.r.l.", "prestatore": "Luca Bianchi", "descrizione": "Consulenza occasionale"}` → atteso: Ritenuta 1.200,00; netto 4.800,00 prima dei contributi; se nell'anno i compensi occasionali superano 5.000 euro, sui 1.000 eccedenti sono dovuti i contributi della gestione separata (aliquota 2026 da leggere dalla fonte INPS), un terzo a carico del prestatore. Il tool non li calcola.

### `ritenuta_acconto`

Ritenuta d'acconto sui compensi professionali con netto percepito e campi indicativi per la Certificazione Unica.

- Parametri: `compenso_lordo: float; aliquota: float = 20.0`
- Fonte normativa dichiarata: Art. 25 DPR 600/1973
- Casi di prova:
  - Aliquota ordinaria: `{"compenso_lordo": 1000, "aliquota": 20.0}` → atteso: Ritenuta 200,00; netto 800,00; nella CU punto 4 = 1.000,00, punto 8 (imponibile) = 1.000,00, punto 9 (ritenute) = 200,00. Il tool mette 200 nel punto_8 e 800 nel punto_9.
  - Percipiente non residente: `{"compenso_lordo": 1000, "aliquota": 30.0}` → atteso: Ritenuta 300,00; netto 700,00 (art. 25 co. 2 DPR 600/1973).
  - Arrotondamento al centesimo: `{"compenso_lordo": 77.47, "aliquota": 20.0}` → atteso: Ritenuta 15,49 (15,494 arrotondato); netto 61,98.
  - Importo minimo: `{"compenso_lordo": 0.05, "aliquota": 20.0}` → atteso: Ritenuta 0,01; netto 0,04: verificare l'arrotondamento del sito.

### `spese_mediazione`

Indennità di mediazione civile e commerciale per parte e per scaglione, con esito positivo o negativo e riduzione di un terzo.

- Parametri: `valore_controversia: float; esito: str = 'positivo' (positivo, negativo)`
- Fonte normativa dichiarata: DM 150/2023; D.Lgs. 28/2010
- Casi di prova:
  - Primo scaglione con accordo: `{"valore_controversia": 1000, "esito": "positivo"}` → atteso: DM 150/2023: spese di avvio 40 euro (art. 28) più spese di mediazione della Tabella A aumentate del 10% se l'accordo è raggiunto al primo incontro (art. 30), oltre IVA: da leggere dalla fonte e dal sito. Il tool: 120 + IVA 26,40 = 146,40 per parte, senza spese di avvio.
  - Mancato accordo al primo incontro: `{"valore_controversia": 15000, "esito": "negativo"}` → atteso: Spese di avvio 75 euro più spese di mediazione fisse del primo incontro, nessun altro importo (art. 28): da leggere dalla fonte. Il tool: 240 (292,80 con IVA) o 160 ridotta (195,20).
  - Primo centesimo della fascia con spese di avvio di 110 euro: `{"valore_controversia": 50000.01, "esito": "positivo"}` → atteso: Spese di avvio 110 euro (art. 28); importi della Tabella A da leggere dalla fonte. Il tool: 1.060 + IVA = 1.293,20 per parte.

### `tariffe_mediazione`

Tabella delle indennità di mediazione con spese di avvio per scaglione e totali per parte con esito positivo e negativo.

- Parametri: `valore_controversia: float`
- Fonte normativa dichiarata: DM 150/2023; D.Lgs. 28/2010
- Casi di prova:
  - Confine superiore della prima fascia: `{"valore_controversia": 1000}` → atteso: Spese di avvio 40 euro per parte (art. 28 DM 150/2023); il resto da leggere dalla fonte. Il tool: negativo 113,20 per parte, positivo 186,40.
  - Primo centesimo della seconda fascia: `{"valore_controversia": 1000.01}` → atteso: Spese di avvio 75 euro per parte (art. 28).
  - Confine superiore della fascia intermedia: `{"valore_controversia": 50000}` → atteso: Spese di avvio 75 euro per parte (art. 28); Tabella A da leggere dalla fonte. Il tool: negativo 514,20, positivo 953,40 per parte.
  - Primo centesimo della fascia alta: `{"valore_controversia": 50000.01}` → atteso: Spese di avvio 110 euro per parte (art. 28); Tabella A da leggere dalla fonte. Il tool: negativo 756,60, positivo 1.403,20 per parte.

## parlamento.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_ddl` | ricerca_online | smoke_live | nessuna (media) | Senato della Repubblica, scheda del DDL su senato.it; Camera dei deputati, scheda dell'atto su camera.it | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: ricerca sui soli titoli; ordinamento per data dello stato decrescente; filtro solo_pendenti sui sette stati di STATI_PENDENTI; estremi della legge (numero e data) per le fasi concluse. |
| `ddl_su_norma` | ricerca_online | smoke_live | nessuna (media) | Senato della Repubblica, ricerca DDL per titolo su senato.it | Assente dai paragrafi 5 e 7: né corretto né declassato; la L. 177/2024 del caso di prova è citata nel paragrafo 5 (decurtazione_punti_patente) e offre un riscontro incrociato. Da confermare: espansione del riferimento (codici, numero e anno), articolo ignorato, avvertenza sempre presente che l'assenza di risultati non prova l'assenza di riforme. |
| `iter_ddl` | ricerca_online | smoke_live | nessuna (alta) | Senato della Repubblica, scheda DDL S.1939 (XIX legislatura); Camera dei deputati, scheda AC 3053 | Assente dai paragrafi 5 e 7 come tool; serve a chiudere la voce competenza_giudice del paragrafo 7: conferma la conversione del DL 100/2026, indicato da fonte secondaria come veicolo del rinvio delle soglie del D.Lgs. 116/2017 al 31/10/2027 (secondo la fixture tests/fixtures/parlamento/senato_iter.json e il test live esistente: legge n. 145 del 07/08/2026); il contenuto del rinvio va poi letto nel testo vigente con cite_law. Da confermare anche che il fallimento dell'arricchimento Camera non faccia fallire l'iter. |

### `cerca_ddl`

Ricerca di disegni di legge (DDL) per parole nei titoli su dati.senato.it (fasi di entrambi i rami), con filtri per legislatura, ramo, stato e sole fasi pendenti.

- Parametri: `query: str (frasi separate da virgola, in OR); legislatura: int = 19; ramo: 'S' \| 'C' \| '' = ''; stato: str = ''; solo_pendenti: bool = False; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: Senato della Repubblica, dati.senato.it (SPARQL)
- Casi di prova:
  - DDL noto divenuto legge: `{"query": "intelligenza artificiale", "legislatura": 19, "max_risultati": 50}` → atteso: fasi del DDL governativo sull'intelligenza artificiale (S.1146, C.2316 e S.1146-B, numeri da riscontrare), con stato 'appr. definit. Legge' e 'Divenuto legge: n. 132 del 2025-09-23'
  - Solo fasi pendenti: `{"query": "intelligenza artificiale", "legislatura": 19, "solo_pendenti": true, "max_risultati": 20}` → atteso: solo fasi con stato in corso (esame in commissione, all'esame dell'assemblea e simili), nessuna fase approvata

### `ddl_su_norma`

Disegni di legge pendenti o conclusi che citano nel titolo un atto normativo, con espansione del riferimento tramite il resolver; ricerca dichiarata come indicativa perché limitata ai titoli.

- Parametri: `riferimento: str; legislatura: int = 19; max_risultati: int = 10 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: dati.senato.it
- Casi di prova:
  - Codice con riforma nota: `{"riferimento": "codice della strada", "legislatura": 19, "max_risultati": 50}` → atteso: fasi del DDL su sicurezza stradale e revisione del codice della strada (C.1435 e S.1086, numeri da riscontrare) con 'Divenuto legge: n. 177 del 2024-11-25', più l'avvertenza sulla ricerca nei soli titoli
  - Articolo di codice: `{"riferimento": "art. 2043 c.c.", "legislatura": 19}` → atteso: ricerca per atto (codice civile) con l'articolo ignorato; avvertenza sui soli titoli presente anche con zero risultati

### `iter_ddl`

Ricostruisce l'iter (navette) di un disegno di legge: fasi nei due rami con stato datato, estremi della legge, timeline e PDF dello stampato della Camera.

- Parametri: `atto: str (S.1939, C.3053, AS 1939, AC 3053 o idDdl numerico); legislatura: int = 19`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonti: dati.senato.it e dati.camera.it
- Casi di prova:
  - DDL noto dal numero del Senato: `{"atto": "S.1939", "legislatura": 19}` → atteso: titolo 'Conversione in legge del decreto-legge 12 giugno 2026, n. 100' (misure urgenti in materia di giustizia e Patto UE sulla migrazione e l'asilo); idDdl 55442; fase S.1939 'approvato' al 2026-07-30; fase C.3053 'appr. definit. Legge' al 2026-08-05; 'Divenuto legge: n. 145 del 2026-08-07'; timeline e PDF dello stampato della Camera
  - Stesso DDL dal numero della Camera: `{"atto": "AC 3053", "legislatura": 19}` → atteso: stesso iter (idDdl 55442) partendo dal numero della Camera
  - Formato non riconosciuto: `{"atto": "DDL 1939"}` → atteso: errore di formato dell'atto, nessuna chiamata di rete

## privacy_gdpr.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `analisi_base_giuridica` | utilita | solo_norma | nessuna pagina del sito | artt. 6 e 9 GDPR, art. 2-ter e art. 130 D.Lgs. 196/2003, art. 4 L. 300/1970, via cite_law | Non toccato dall'audit di settembre 2026. Difetti rilevati: ogni contesto usa solo la prima voce della matrice (B2C sempre 'marketing', dipendenti sempre 'gestione'), per cui le voci B2C_ecommerce e dipendenti_videosorveglianza (e ricerca_scientifica, antifrode_sicurezza) non sono mai raggiungibili e tipo_trattamento non orienta la scelta; le condizioni art. 9 dette 'più frequenti per il contesto' sono sempre le lettere a), b), c). |
| `calcolo_sanzione_gdpr` | calcolo | fonte_ufficiale | nessuna pagina del sito | EDPB, Linee guida 04/2022 sul calcolo delle sanzioni amministrative pecuniarie (v. 2.1, 24/05/2023); art. 83(4)-(6) GDPR via cite_law | Non toccato dall'audit di settembre 2026 (grado già STIMATO). Il massimale si deriva dalla norma; il range (da massimale x 0,5% x moltiplicatore a massimale x il minore tra 5% x moltiplicatore e 20%, con moltiplicatore = 1 + 0,25 per aggravante - 0,20 per attenuante + 0,50 con precedenti, limitato tra 0,1 e 3) è un'euristica del tool, da confrontare con il metodo EDPB (punto di partenza per gravità bassa 0-10%, media 10-20%, alta 20-100% del massimale, poi correttivi per dimensione dell'impresa). Il massimale percentuale vale solo per le imprese. |
| `genera_dpa` | documento | strutturale | nessuna pagina del sito | art. 28 GDPR via cite_law; clausole contrattuali tipo della Decisione di esecuzione (UE) 2021/915 | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. La checklist clausole_obbligatorie_art28 è fissa a true e non verifica il testo. Manca l'obbligo del responsabile di informare subito il titolare se un'istruzione viola il GDPR (art. 28(3), ultimo periodo). Le 24 ore per segnalare il breach sono una scelta contrattuale (l'art. 33(2) dice 'senza ingiustificato ritardo'). |
| `genera_dpia` | documento | strutturale | nessuna pagina del sito | artt. 35 e 36 GDPR via cite_law; Linee guida WP248 rev.01 (allegato 2, criteri per una DPIA accettabile) | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. Difetto di metodo: il rischio residuo ignora misure_mitigazione (coincide con il rischio inerente), per cui il tool impone la consultazione preventiva anche con misure efficaci; l'art. 36(1) la lega al rischio elevato in assenza di misure, cioè al rischio che resta dopo le misure. Scala del tool: punteggio = probabilità x gravità (1-4); fino a 2 basso, fino a 4 medio, fino a 6 alto, oltre molto alto. |
| `genera_informativa_cookie` | documento | strutturale | nessuna pagina del sito | art. 122 D.Lgs. 196/2003 via cite_law; Linee guida del Garante su cookie e altri strumenti di tracciamento del 10/06/2021 (doc. web 9677876) | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. Il banner suggerito non menziona il comando di chiusura 'X' equivalente al rifiuto, il divieto di considerare lo scroll come consenso e la regola dei 6 mesi prima di riproporre il banner (Linee guida 2021). |
| `genera_informativa_dipendenti` | documento | strutturale | nessuna pagina del sito | artt. 13 e 88 GDPR, artt. 2-quaterdecies, 113 e 114 D.Lgs. 196/2003, art. 4 L. 300/1970, D.Lgs. 81/2008, via cite_law | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. Citazioni da riscontrare: l'art. 111-bis D.Lgs. 196/2003 riguarda i curricula inviati spontaneamente, non il rapporto di lavoro (pertinenti art. 88 GDPR e artt. 113-114 Codice privacy); i 40 anni per la sorveglianza sanitaria sono attribuiti all'art. 25 co. 1 lett. a) D.Lgs. 81/2008, che riguarda la collaborazione del medico competente alla valutazione dei rischi (il termine di 40 anni si ritrova nelle norme su cancerogeni e amianto, artt. 243 e 260, da verificare); 'nomina ad incaricato' va sostituito dalle persone autorizzate ex art. 2-quaterdecies. |
| `genera_informativa_privacy` | documento | strutturale | nessuna pagina del sito | artt. 12, 13, 14 e 77 Reg. UE 2016/679 via cite_law; verifica_citazioni sul testo prodotto | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. Lacune rilevate: mancano gli elementi dell'art. 13(2)(e) (obbligo o facoltà del conferimento e conseguenze del rifiuto) e 13(2)(f) (processo decisionale automatizzato), il legittimo interesse dell'art. 13(1)(d) non ha una voce propria, la numerazione salta da 4 a 7 senza DPO e trasferimenti; per l'art. 14 la fonte dei dati è generica e la checklist segna fonte_dati sempre vera. |
| `genera_informativa_videosorveglianza` | documento | strutturale | nessuna pagina del sito | Linee guida EDPB 3/2019 sui dispositivi video (v. 2.0), FAQ del Garante sulla videosorveglianza (dicembre 2020), art. 4 L. 300/1970 e art. 114 D.Lgs. 196/2003 | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. L'informativa breve non riporta i contatti del DPO e il rinvio esplicito all'informativa di secondo livello previsti dal modello EDPB; manca il richiamo all'art. 114 Codice privacy. |
| `genera_notifica_data_breach` | documento | strutturale | nessuna pagina del sito | art. 33 GDPR via cite_law; provvedimento del Garante del 27/05/2021 sulla procedura telematica obbligatoria dal 1/7/2021; Linee guida EDPB 9/2022 | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. Eseguire con LEGAL_NOW=2026-09-25T12:00:00. Punti rilevati: l'elemento 33(3)(b) è considerato mancante senza DPO, ma la norma ammette 'altro punto di contatto'; le etichette [art. 33(3)(a)] sulla sezione del titolare vanno riscontrate; una data di violazione successiva alla scoperta è accettata senza avviso; indirizzi e-mail in intestazione da riscontrare, perché dal 1/7/2021 la notifica si presenta solo in via telematica. |
| `genera_registro_trattamenti` | documento | strutturale | nessuna pagina del sito | art. 30 GDPR via cite_law; FAQ del Garante sul registro delle attività di trattamento | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione. La voce 30(1)(a) non prevede i contatti di contitolare, rappresentante e DPO; manca il registro del responsabile (art. 30(2)). L'esenzione sotto i 250 dipendenti è descritta correttamente (art. 30(5)). |
| `valutazione_data_breach` | calcolo | fonte_ufficiale | nessuna pagina del sito | EDPB, Linee guida 9/2022 sulla notifica delle violazioni (v. 2.0, 28/03/2023) e Linee guida 01/2021 sugli esempi di notifica; strumento di autovalutazione del Garante nella procedura telematica data breach | Non toccato dall'audit di settembre 2026; docstring senza righe Vigenza e Precisione, e con un refuso ('la cifratura viola l'obbligo di comunicazione' invece di 'esclude'). Soglie proprie del tool (oltre 100.000 interessati +1 livello) non previste dalla norma: vanno documentate come convenzione. La cifratura esclude sempre la comunicazione, anche per violazioni di disponibilità, dove l'art. 34(3)(a) non aiuta. |
| `verifica_necessita_dpia` | calcolo | fonte_ufficiale | nessuna pagina del sito | Garante privacy, elenco delle tipologie di trattamenti soggetti a DPIA (provv. 11/10/2018, doc. web 9058979); Linee guida WP248 rev.01; art. 35(3) GDPR via cite_law | Non toccato dall'audit di settembre 2026. Scostamenti rilevati: il trasferimento extra UE conta come criterio ai fini della soglia, ma non è tra i nove criteri WP248 (un solo criterio più il trasferimento rende la DPIA 'obbligatoria'); i casi dell'art. 35(3) (es. sorveglianza sistematica su larga scala di zone accessibili al pubblico) non sono riconosciuti come obbligatori a prescindere dal conteggio; l'elenco del Garante non ha corrispondenza per i trattamenti biometrici (manca un parametro dedicato). |

### `analisi_base_giuridica`

Suggerisce la base giuridica ex art. 6 GDPR per contesto e, con dati particolari, le condizioni dell'art. 9(2).

- Parametri: `tipo_trattamento: str, contesto: str ('B2C'\|'B2B'\|'dipendenti'\|'pubblica_amministrazione'\|'sanita'\|'profilazione'), finalita: str, dati_particolari: bool = False, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: artt. 6 e 9 GDPR
- Casi di prova:
  - E-commerce B2C: `{"tipo_trattamento": "gestione ordini e-commerce", "contesto": "B2C", "finalita": "esecuzione dell'ordine e consegna"}` → atteso: base consigliata: contratto, art. 6(1)(b); oggi 'consenso' con la nota sul marketing
  - Videosorveglianza sui dipendenti: `{"tipo_trattamento": "videosorveglianza del magazzino", "contesto": "dipendenti", "finalita": "tutela del patrimonio aziendale"}` → atteso: base consigliata: legittimo interesse, art. 6(1)(f), con accordo sindacale o autorizzazione ITL (art. 4 L. 300/1970); oggi 'contratto'
  - Sanità con dati particolari: `{"tipo_trattamento": "cartella clinica", "contesto": "sanita", "finalita": "diagnosi e cura", "dati_particolari": true}` → atteso: condizione art. 9(2)(h) con il segreto professionale dell'art. 9(3) (ed eventualmente 9(2)(i)); oggi indicate come più frequenti le lettere a), b), c)
  - Pubblica amministrazione: `{"tipo_trattamento": "rilascio certificati", "contesto": "pubblica_amministrazione", "finalita": "funzioni istituzionali"}` → atteso: interesse pubblico, art. 6(1)(e), con base nel diritto nazionale (art. 2-ter D.Lgs. 196/2003); legittimo interesse escluso per le autorità pubbliche (art. 6(1), secondo comma)

### `calcolo_sanzione_gdpr`

Calcola il massimale edittale e un range stimato della sanzione GDPR ex art. 83 con modulazione per aggravanti, attenuanti e precedenti.

- Parametri: `tipo_violazione: str ('art83_4'\|'art83_5'\|'art83_6'), fatturato_annuo: float \| None = None, fattori_aggravanti: list[str] \| None = None, fattori_attenuanti: list[str] \| None = None, precedenti: bool = False, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 83 GDPR
- Casi di prova:
  - Art. 83(4) senza fatturato: `{"tipo_violazione": "art83_4"}` → atteso: massimale 10.000.000 euro (art. 83(4)); range da leggere dalla fonte (tool: 50.000-500.000)
  - Art. 83(5), fatturato 1 miliardo: `{"tipo_violazione": "art83_5", "fatturato_annuo": 1000000000}` → atteso: massimale 40.000.000 euro: il 4% supera i 20 milioni (art. 83(5))
  - Art. 83(5), fatturato 500 milioni (confine): `{"tipo_violazione": "art83_5", "fatturato_annuo": 500000000}` → atteso: massimale 20.000.000 euro: il 4% coincide con l'importo fisso
  - Art. 83(5), fatturato 400 milioni: `{"tipo_violazione": "art83_5", "fatturato_annuo": 400000000}` → atteso: massimale 20.000.000 euro: il 4% (16 milioni) è inferiore, si applica l'importo fisso
  - Micro impresa con molte attenuanti: `{"tipo_violazione": "art83_4", "fatturato_annuo": 2000000, "fattori_attenuanti": ["prima violazione", "cooperazione piena", "misure correttive immediate", "danno limitato", "dimensione ridotta"]}` → atteso: massimale 10.000.000 euro; range da leggere dalla fonte (EDPB: riduzione per imprese fino a 2 milioni di fatturato); tool: moltiplicatore 0,1, range 5.000-50.000

### `genera_dpa`

Genera l'accordo di nomina a responsabile del trattamento (Data Processing Agreement) ex art. 28 GDPR.

- Parametri: `titolare: str, responsabile: str, oggetto: str, durata: str, categorie_interessati: list[str], categorie_dati: list[str], misure_sicurezza: list[str], sub_responsabili: list[str] \| None = None`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 28 GDPR
- Casi di prova:
  - Hosting CRM con sub-responsabile: `{"titolare": "Alfa S.r.l.", "responsabile": "Cloud Beta S.r.l.", "oggetto": "hosting e gestione CRM", "durata": "per tutta la durata del contratto di servizio", "categorie_interessati": ["clienti", "prospect"], "categorie_dati": ["dati anagrafici", "dati di contatto"], "misure_sicurezza": ["cifratura AES-256 a riposo", "autenticazione a più fattori", "backup giornalieri"], "sub_responsabili": ["AWS EMEA SARL"]}` → atteso: clausole art. 28(3) lett. a)-h) tutte presenti; obbligo di informare il titolare se un'istruzione viola il GDPR (28(3) ultimo periodo); sub-responsabili con autorizzazione, diritto di opposizione e stessi obblighi (28(2) e 28(4)); oggetto, durata, natura, finalità, tipi di dati e categorie di interessati (28(3) primo periodo)
  - Senza sub-responsabili: `{"titolare": "Alfa S.r.l.", "responsabile": "Paghe Srl", "oggetto": "elaborazione cedolini", "durata": "12 mesi", "categorie_interessati": ["dipendenti"], "categorie_dati": ["dati retributivi"], "misure_sicurezza": ["controllo accessi"]}` → atteso: clausola 4.4 che vieta sub-responsabili senza autorizzazione scritta specifica o generale (art. 28(2))

### `genera_dpia`

Genera la valutazione d'impatto (DPIA) con matrice probabilità per gravità, rischio residuo e indicazione della consultazione preventiva.

- Parametri: `titolare: str, descrizione: str, finalita: str, necessita_proporzionalita: str, rischi: list[dict] ({'desc', 'probabilita', 'gravita'} con 'bassa'\|'media'\|'alta'\|'molto_alta'), misure_mitigazione: list[dict] ({'misura', 'rischio_mitigato', 'efficacia'})`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 35 GDPR, WP248 rev.01
- Casi di prova:
  - Biometria con misura efficace: `{"titolare": "Alfa S.r.l.", "descrizione": "Rilevazione presenze con impronta digitale", "finalita": "controllo accessi e presenze", "necessita_proporzionalita": "alternative meno invasive valutate e scartate", "rischi": [{"desc": "accesso abusivo ai template biometrici", "probabilita": "alta", "gravita": "alta"}], "misure_mitigazione": [{"misura": "template cifrato sul badge in possesso del dipendente", "rischio_mitigato": "accesso abusivo ai template biometrici", "efficacia": "alta"}]}` → atteso: struttura art. 35(7) lett. a)-d); rischio residuo ricalcolato dopo la misura; consultazione preventiva (art. 36, risposta in 8 settimane prorogabili di 6) solo se il rischio resta elevato; oggi punteggio 9, molto alto e consultazione obbligatoria
  - Confini della matrice: `{"titolare": "Alfa S.r.l.", "descrizione": "CRM", "finalita": "vendite", "necessita_proporzionalita": "necessario", "rischi": [{"desc": "r1", "probabilita": "media", "gravita": "alta"}, {"desc": "r2", "probabilita": "molto_alta", "gravita": "media"}, {"desc": "r3", "probabilita": "bassa", "gravita": "media"}], "misure_mitigazione": []}` → atteso: r1 punteggio 6 alto, r2 punteggio 8 molto alto, r3 punteggio 2 basso; rischio residuo molto alto: la scelta del tool va documentata contro WP248

### `genera_informativa_cookie`

Genera la cookie policy con tabella dei cookie e testo del banner di consenso.

- Parametri: `titolare: str, cookie_tecnici: list[str], sito_web: str, cookie_analytics: list[str] \| None = None, cookie_profilazione: list[str] \| None = None`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 122 D.Lgs. 196/2003, Linee guida Garante 10/06/2021, art. 6(1)(a) GDPR
- Casi di prova:
  - Tecnici, analitici e di profilazione: `{"titolare": "Alfa S.r.l.", "cookie_tecnici": ["PHPSESSID", "csrf_token"], "sito_web": "https://www.alfa.it", "cookie_analytics": ["_ga", "_gid"], "cookie_profilazione": ["_fbp", "IDE"]}` → atteso: riferimenti: art. 122 D.Lgs. 196/2003, Linee guida Garante 10/06/2021 (doc. web 9677876), artt. 6(1)(a) e 7 GDPR; tecnici senza consenso; analitici assimilati ai tecnici solo se minimizzati e senza incrocio da parte del fornitore; profilazione previo consenso; banner con 'X' di chiusura = rifiuto, niente scroll come consenso, nessuna riproposizione prima di 6 mesi
  - Solo cookie tecnici: `{"titolare": "Alfa S.r.l.", "cookie_tecnici": ["PHPSESSID"], "sito_web": "https://www.alfa.it"}` → atteso: nessun consenso richiesto (consenso_richiesto_analytics e _profilazione false); sezioni 3 e 4 assenti; riferimento all'art. 122 co. 1 D.Lgs. 196/2003

### `genera_informativa_dipendenti`

Genera l'informativa privacy per dipendenti e collaboratori, con sezioni opzionali su videosorveglianza, geolocalizzazione e strumenti aziendali.

- Parametri: `titolare: str, dpo: str = '', videosorveglianza: bool = False, geolocalizzazione: bool = False, strumenti_aziendali: bool = False`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 13 GDPR, art. 111-bis D.Lgs. 196/2003, art. 4 L. 300/1970, D.Lgs. 81/2008
- Casi di prova:
  - Tutte le sezioni opzionali: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano", "dpo": "dpo@alfa.it", "videosorveglianza": true, "geolocalizzazione": true, "strumenti_aziendali": true}` → atteso: riferimenti attesi: artt. 13 e 88 GDPR, artt. 113 e 114 D.Lgs. 196/2003, art. 4 L. 300/1970 (accordo sindacale o autorizzazione ITL; strumenti di lavoro esclusi al co. 2; utilizzabilità dei dati con adeguata informazione al co. 3), D.Lgs. 81/2008; persone autorizzate ex art. 2-quaterdecies; nessuna citazione dell'art. 111-bis
  - Solo sezioni obbligatorie: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano"}` → atteso: basi 6(1)(b), 6(1)(c), 9(2)(b) e 6(1)(f); diritti artt. 15-18 e 21 con la nota sulla portabilità (art. 20); reclamo al Garante; nessuna sezione su video, GPS e strumenti

### `genera_informativa_privacy`

Genera l'informativa sul trattamento ex art. 13 o 14 GDPR con la checklist degli elementi obbligatori.

- Parametri: `titolare: str, finalita: list[str], basi_giuridiche: list[str], categorie_dati: list[str], destinatari: list[str], periodo_conservazione: str, tipo: str = 'art13' ('art13'\|'art14'), dpo: str = '', diritti_esercitabili: list[str] \| None = None, trasferimento_extra_ue: str = ''`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: artt. 13 e 14 Reg. UE 2016/679
- Casi di prova:
  - Art. 13 con legittimo interesse, senza DPO: `{"titolare": "Alfa S.r.l., Via Roma 1, 20121 Milano, privacy@alfa.it", "finalita": ["gestione del rapporto contrattuale", "marketing diretto"], "basi_giuridiche": ["art. 6(1)(b) GDPR - contratto", "art. 6(1)(a) GDPR - consenso", "art. 6(1)(f) GDPR - legittimo interesse"], "categorie_dati": ["dati anagrafici", "dati di contatto"], "destinatari": ["fornitori IT", "commercialista"], "periodo_conservazione": "10 anni dalla cessazione del contratto", "tipo": "art13"}` → atteso: testo con: identità e contatti del titolare (13(1)(a)), finalità e basi (13(1)(c)), legittimi interessi (13(1)(d)), destinatari (13(1)(e)), conservazione (13(2)(a)), diritti artt. 15-22 (13(2)(b)), revoca del consenso (13(2)(c)), reclamo al Garante (13(2)(d), art. 77), conferimento obbligatorio o facoltativo (13(2)(e)), processi decisionali automatizzati (13(2)(f)), risposta entro un mese (art. 12(3))
  - Art. 14 con DPO e trasferimento extra UE: `{"titolare": "Alfa S.r.l., Via Roma 1, 20121 Milano, privacy@alfa.it", "finalita": ["marketing B2B"], "basi_giuridiche": ["art. 6(1)(f) GDPR - legittimo interesse"], "categorie_dati": ["dati di contatto professionali"], "destinatari": ["agenzia di marketing"], "periodo_conservazione": "24 mesi", "tipo": "art14", "dpo": "dpo@alfa.it", "trasferimento_extra_ue": "server negli Stati Uniti"}` → atteso: in più: categorie di dati (14(1)(d)), fonte specifica dei dati e se pubblica (14(2)(f)), tempi dell'informativa (14(3)), garanzie del trasferimento (artt. 45-46) e modo di ottenerne copia (14(1)(f)), contatti del DPO (14(1)(b))

### `genera_informativa_videosorveglianza`

Genera il cartello (informativa breve) e l'informativa estesa per un impianto di videosorveglianza, con gli adempimenti preventivi.

- Parametri: `titolare: str, finalita: list[str], tempo_conservazione: str, aree_riprese: list[str]`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 13 GDPR, Linee guida EDPB 3/2019, art. 4 L. 300/1970
- Casi di prova:
  - Magazzino aziendale con dipendenti: `{"titolare": "Beta S.p.A., Via Verdi 2, Torino", "finalita": ["sicurezza delle persone", "tutela del patrimonio aziendale"], "tempo_conservazione": "72 ore", "aree_riprese": ["ingresso principale", "magazzino"]}` → atteso: cartello di primo livello con titolare, finalità, conservazione, diritti, contatti del DPO se nominato e dove trovare l'informativa completa; estesa con base art. 6(1)(f), Linee guida EDPB 3/2019, art. 4 L. 300/1970 (accordo sindacale o autorizzazione ITL), art. 114 D.Lgs. 196/2003, conservazione 72 ore, divieto di controllo a distanza dell'attività lavorativa

### `genera_notifica_data_breach`

Genera il modulo di notifica del data breach al Garante (art. 33 GDPR) con il termine delle 72 ore dalla scoperta.

- Parametri: `titolare: str, data_violazione: str (YYYY-MM-DD o YYYY-MM-DDTHH:MM), data_scoperta: str (idem), descrizione: str, categorie_dati: list[str], n_interessati: int, conseguenze: str, misure_adottate: list[str], dpo: str = ''`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 33 GDPR
- Casi di prova:
  - Esattamente 72 ore: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano", "data_violazione": "2026-09-20T22:00", "descrizione": "Accesso abusivo al CRM", "categorie_dati": ["dati anagrafici", "dati di contatto"], "n_interessati": 1200, "conseguenze": "rischio di phishing mirato", "misure_adottate": ["reset delle credenziali", "blocco degli accessi"], "data_scoperta": "2026-09-22T12:00", "dpo": "dpo@alfa.it"}` → atteso: termine 25/09/2026 ore 12:00; scadenza non superata; elementi 33(3) a)-d) presenti
  - Un minuto oltre le 72 ore: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano", "data_violazione": "2026-09-20T22:00", "descrizione": "Accesso abusivo al CRM", "categorie_dati": ["dati anagrafici", "dati di contatto"], "n_interessati": 1200, "conseguenze": "rischio di phishing mirato", "misure_adottate": ["reset delle credenziali", "blocco degli accessi"], "data_scoperta": "2026-09-22T11:59", "dpo": "dpo@alfa.it"}` → atteso: termine 25/09/2026 ore 11:59; scadenza superata con avviso a indicare i motivi del ritardo (art. 33(1))
  - Senza DPO: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano", "data_violazione": "2026-09-20T22:00", "descrizione": "Accesso abusivo al CRM", "categorie_dati": ["dati anagrafici", "dati di contatto"], "n_interessati": 1200, "conseguenze": "rischio di phishing mirato", "misure_adottate": ["reset delle credenziali", "blocco degli accessi"], "data_scoperta": "2026-09-24T10:00"}` → atteso: termine 27/09/2026 ore 10:00; elemento 33(3)(b) soddisfatto anche da un altro punto di contatto: oggi b_contatti_dpo false e tutti_elementi_presenti false
  - Violazione datata dopo la scoperta: `{"titolare": "Alfa S.r.l., Via Roma 1, Milano", "data_violazione": "2026-09-30T10:00", "descrizione": "Accesso abusivo al CRM", "categorie_dati": ["dati anagrafici", "dati di contatto"], "n_interessati": 1200, "conseguenze": "rischio di phishing mirato", "misure_adottate": ["reset delle credenziali", "blocco degli accessi"], "data_scoperta": "2026-09-24T10:00", "dpo": "dpo@alfa.it"}` → atteso: avviso o errore di incoerenza delle date; oggi il modulo viene generato senza segnalazione

### `genera_registro_trattamenti`

Genera la scheda di un trattamento per il registro delle attività di trattamento ex art. 30 GDPR.

- Parametri: `titolare: str, trattamento: str, finalita: str, base_giuridica: str, categorie_interessati: list[str], categorie_dati: list[str], destinatari: list[str], termine_cancellazione: str, misure_sicurezza: list[str]`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 30 GDPR
- Casi di prova:
  - Scheda CRM: `{"titolare": "Alfa S.r.l.", "trattamento": "Gestione clienti CRM", "finalita": "gestione del rapporto commerciale", "base_giuridica": "art. 6(1)(b) GDPR", "categorie_interessati": ["clienti"], "categorie_dati": ["dati anagrafici", "dati di contatto"], "destinatari": ["provider CRM (responsabile art. 28)"], "termine_cancellazione": "10 anni dalla cessazione del rapporto", "misure_sicurezza": ["controllo accessi", "cifratura", "backup"]}` → atteso: voci art. 30(1) lett. a)-g): nome e contatti del titolare e, se presenti, di contitolare, rappresentante e DPO; finalità; categorie di interessati e di dati; destinatari; trasferimenti con garanzie; termini di cancellazione; descrizione generale delle misure dell'art. 32(1)

### `valutazione_data_breach`

Valuta una violazione di dati: livello di rischio, obbligo di notifica al Garante (art. 33) e di comunicazione agli interessati (art. 34), azioni.

- Parametri: `tipo_violazione: str ('confidenzialita'\|'integrita'\|'disponibilita'), categorie_dati: list[str], n_interessati: int, dati_particolari: bool = False, misure_protezione: list[str] \| None = None, impatto: str = 'medio' ('basso'\|'medio'\|'alto'\|'molto_alto')`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: artt. 33, 34 e 4(12) GDPR
- Casi di prova:
  - Rischio improbabile: `{"tipo_violazione": "confidenzialita", "categorie_dati": ["email"], "n_interessati": 100, "impatto": "basso"}` → atteso: nessuna notifica se è improbabile il rischio per i diritti (art. 33(1)); registrazione interna (art. 33(5))
  - Confine dei 100.000 interessati: `{"tipo_violazione": "confidenzialita", "categorie_dati": ["email"], "n_interessati": 100001, "impatto": "medio"}` → atteso: notifica sì; comunicazione da leggere dalla fonte (la norma non fissa soglie numeriche); con 100.000 il tool non comunica, con 100.001 sì: documentare la convenzione
  - Indisponibilità di dati sanitari cifrati: `{"tipo_violazione": "disponibilita", "categorie_dati": ["dati sanitari"], "n_interessati": 50, "dati_particolari": true, "misure_protezione": ["cifratura AES-256"], "impatto": "alto"}` → atteso: notifica sì; comunicazione agli interessati non esclusa dalla cifratura: l'art. 34(3)(a) riguarda l'incomprensibilità dei dati, non la loro perdita (cfr. esempi ransomware delle Linee guida EDPB 01/2021); oggi comunicazione false
  - Riservatezza di dati cifrati: `{"tipo_violazione": "confidenzialita", "categorie_dati": ["dati sanitari"], "n_interessati": 50, "dati_particolari": true, "misure_protezione": ["cifratura AES-256"], "impatto": "alto"}` → atteso: notifica al Garante sì; comunicazione esclusa ex art. 34(3)(a) se la chiave non è compromessa

### `verifica_necessita_dpia`

Verifica se la DPIA è obbligatoria contando i criteri WP248 soddisfatti (soglia 2) e le corrispondenze con l'elenco del Garante.

- Parametri: `tipo_trattamento: str, profilazione: bool = False, dati_sensibili: bool = False, monitoraggio_sistematico: bool = False, larga_scala: bool = False, soggetti_vulnerabili: bool = False, nuove_tecnologie: bool = False, valutazione_scoring: bool = False, incrocio_dataset: bool = False, trasferimento_extra_ue: bool = False, impedimento_diritto: bool = False, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: nessuna riga Vigenza; in risposta: art. 35 GDPR, WP248 rev.01, provv. Garante 11/10/2018 (doc. web 9058979)
- Casi di prova:
  - Larga scala più trasferimento extra UE: `{"tipo_trattamento": "CRM su larga scala con server negli USA", "larga_scala": true, "trasferimento_extra_ue": true}` → atteso: un solo criterio WP248 (larga scala): DPIA non obbligatoria per soglia, salvo elenco del Garante; oggi dpia_necessaria true con 2 criteri
  - Videosorveglianza di un centro commerciale: `{"tipo_trattamento": "videosorveglianza di un centro commerciale", "monitoraggio_sistematico": true, "larga_scala": true}` → atteso: DPIA obbligatoria: art. 35(3)(c) (sorveglianza sistematica su larga scala di una zona accessibile al pubblico) e criteri 3 e 5
  - Newsletter profilata: `{"tipo_trattamento": "newsletter con profilazione", "profilazione": true}` → atteso: 1 criterio: non obbligatoria per soglia, fortemente consigliata
  - Presenze biometriche dei dipendenti: `{"tipo_trattamento": "rilevazione presenze biometrica dei dipendenti", "dati_sensibili": true, "soggetti_vulnerabili": true, "nuove_tecnologie": true}` → atteso: obbligatoria (criteri 4, 7, 8) e corrispondenza con la voce dell'elenco del Garante sui trattamenti sistematici di dati biometrici; oggi la voce biometrica non compare in lista_garante_match

## procedura_civile.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `competenza_giudice` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: artt. 7 e 9 c.p.c. vigenti; artt. 27 e 32 D.Lgs. 116/2017 come modificati dal DL 12 giugno 2026 n. 100 e dalla legge di conversione; art. 27 D.Lgs. 14/2019 | Audit settembre 2026: par. 4.7 (soglie di 10.000 e 25.000 euro vigenti dal 28/02/2023) e par. 7 (rinvio delle soglie di 30.000 e 50.000 euro del D.Lgs. 116/2017 al 31/10/2027 con il DL 100/2026, confidenza bassa, da verificare prima del 31/10/2026). La ricerca web di settembre 2026 trova più fonti secondarie (NT+ Diritto, Giuricivile, La Nuova Procedura Civile) che riportano il DL 12 giugno 2026 n. 100 con il rinvio al 31/10/2027: confermare su Normattiva il testo vigente e la legge di conversione, poi aggiornare il commento del codice che indica ancora il 31/10/2026. Il sito non ha un calcolatore. Scostamenti da confermare, verificati eseguendo il tool: condominio sempre al Tribunale ex art. 9, che però non lo riserva (giudice di pace per i crediti fino a 10.000 euro e per la misura e le modalità d'uso dei servizi condominiali, art. 7 co. 3 n. 2); ogni materia non elencata, per esempio usucapione, è trattata come causa su beni mobili; famiglia con rinvio agli artt. 706 ss. c.p.c., abrogati dal D.Lgs. 149/2022; crisi d'impresa sempre alla sezione specializzata, che l'art. 27 CCII prevede solo per le grandi imprese e i gruppi. |
| `gratuito_patrocinio` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/verifica-requisiti-gratuito-patrocinio.php (alta) | Ministero della Giustizia, pagine Patrocinio a spese dello Stato nei giudizi civili e amministrativi e nei giudizi penali; DM 22 aprile 2025 in GU n. 159 dell'11/07/2025 | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7). Soglia di 13.659,64 euro del DM 22 aprile 2025 (GU n. 159 dell'11/07/2025, confermata da fonti secondarie), valida per le domande successive alla pubblicazione; il prossimo adeguamento biennale ISTAT è atteso nel 2027 (art. 77 DPR 115/2002). Il benchmark deve confermare soglia e maggiorazione penale per familiare convivente (art. 92) sul sito e sulle pagine del Ministero della Giustizia. Lacune da segnalare: manca l'opzione del solo reddito personale (art. 76 co. 4), che il sito offre; i redditi esenti o soggetti a ritenuta a titolo d'imposta si computano (art. 76 co. 3) mentre il parametro chiede l'imponibile; n_familiari_conviventi e redditi_familiari non sono controllati tra loro; verificare l'elenco dei reati del co. 4-ter e se l'ammissione in deroga valga anche nel giudizio civile. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `verifica_mediazione_obbligatoria` | calcolo | solo_norma | nessuna pagina del sito | Normattiva: art. 5 D.Lgs. 28/2010 vigente (con i correttivi successivi al D.Lgs. 149/2022); art. 3 DL 132/2014 per la negoziazione assistita obbligatoria | Audit settembre 2026: par. 4.7 (elenco dell'art. 5 co. 1 D.Lgs. 28/2010 come modificato dal D.Lgs. 149/2022, corrispondente alle materie note); non compare nei par. 5 e 7. Il sito non ha un calcolatore di verifica (solo le spese di mediazione, fuori scopo). Il benchmark deve confermare con cite_law l'elenco vigente e le esclusioni: la tabella omette consulenza tecnica preventiva (art. 696-bis c.p.c.), procedimenti possessori, opposizioni esecutive e azione inibitoria del Codice del consumo, e indica come esclusi i cautelari, che l'art. 5 fa salvi senza escluderli. Scostamenti della ricerca per sottostringa verificati eseguendo il tool: rete dà false (la tabella ha reti_impresa), somministrazione_lavoro dà true, contratti dà true agganciando i contratti assicurativi. |

### `competenza_giudice`

Individua il giudice competente (giudice di pace o tribunale) per valore e materia, con le materie riservate al tribunale a prescindere dal valore.

- Parametri: `valore_causa: float (>= 0); materia: str = 'civile' ['civile', 'circolazione_stradale', 'mobili', 'locazione', 'condominio', 'lavoro', 'famiglia', 'fallimento', 'crisi_impresa'] (valori diversi trattati come 'civile')`
- Fonte normativa dichiarata: Artt. 7-17 c.p.c., soglie aggiornate post-Cartabia (D.Lgs. 149/2022)
- Casi di prova:
  - Soglia esatta del giudice di pace per beni mobili: `{"valore_causa": 10000.0, "materia": "civile"}` → atteso: Giudice di Pace (art. 7 co. 1 c.p.c.: cause relative a beni mobili di valore non superiore a 10.000 euro)
  - Un centesimo sopra la soglia: `{"valore_causa": 10000.01, "materia": "civile"}` → atteso: Tribunale (art. 9 co. 1 c.p.c.)
  - Circolazione stradale alla soglia: `{"valore_causa": 25000.0, "materia": "circolazione_stradale"}` → atteso: Giudice di Pace (art. 7 co. 2 c.p.c.: danni da circolazione di veicoli e natanti fino a 25.000 euro); con 25000.01 Tribunale
  - Credito condominiale di 3.000 euro: `{"valore_causa": 3000.0, "materia": "condominio"}` → atteso: Giudice di Pace (art. 7 co. 1 per un credito fino a 10.000 euro; art. 7 co. 3 n. 2 per la misura e le modalità d'uso dei servizi condominiali); il tool risponde Tribunale ex art. 9, che non riserva il condominio: scostamento da confermare
  - Materia non enumerata: usucapione di immobile: `{"valore_causa": 5000.0, "materia": "usucapione"}` → atteso: Tribunale: le cause su beni immobili non rientrano nell'art. 7 co. 1 e la competenza del giudice di pace sull'usucapione (art. 27 D.Lgs. 116/2017) non è ancora in vigore; il tool risponde Giudice di Pace trattando la materia come civile
  - Famiglia: `{"valore_causa": 50000.0, "materia": "famiglia"}` → atteso: Tribunale (art. 9 co. 2 c.p.c., stato e capacità delle persone; rito unificato artt. 473-bis ss. c.p.c.); il tool cita gli artt. 706 ss. c.p.c., abrogati dal D.Lgs. 149/2022

### `gratuito_patrocinio`

Verifica il requisito reddituale per il patrocinio a spese dello Stato sul reddito del nucleo, con maggiorazione di 1.032,91 euro per familiare convivente in sede penale e ammissione in deroga per le vittime dei reati dell'art. 76 co. 4-ter.

- Parametri: `reddito_richiedente: float (>= 0); n_familiari_conviventi: int = 0 (escluso il richiedente); redditi_familiari: list[float] \| None = None; ambito: str = 'civile' ['civile', 'penale']; vittima_violenza: bool = False`
- Fonte normativa dichiarata: DPR 115/2002 artt. 76 e 92; DM 22 aprile 2025 (soglia 13.659,64 euro)
- Casi di prova:
  - Reddito pari alla soglia: `{"reddito_richiedente": 13659.64}` → atteso: ammesso true, margine 0 (art. 76 co. 1 DPR 115/2002: reddito non superiore a 13.659,64 euro, DM 22 aprile 2025)
  - Un centesimo sopra la soglia: `{"reddito_richiedente": 13659.65}` → atteso: ammesso false, margine -0,01
  - Penale con due familiari conviventi: `{"reddito_richiedente": 7000.0, "n_familiari_conviventi": 2, "redditi_familiari": [5000.0, 3000.0], "ambito": "penale"}` → atteso: ammesso true: reddito del nucleo 15.000 euro (art. 76 co. 2), soglia 13.659,64 + 2 x 1.032,91 = 15.725,46 euro (art. 92), margine 725,46
  - Stesso nucleo in sede civile: `{"reddito_richiedente": 7000.0, "n_familiari_conviventi": 2, "redditi_familiari": [5000.0, 3000.0], "ambito": "civile"}` → atteso: ammesso false: soglia 13.659,64 senza maggiorazione, margine -1.340,36
  - Causa con interessi in conflitto con il coniuge convivente: `{"reddito_richiedente": 9000.0, "n_familiari_conviventi": 1, "redditi_familiari": [30000.0], "ambito": "civile"}` → atteso: Ammesso con il solo reddito personale di 9.000 euro quando gli interessi sono in conflitto con quelli del familiare convivente (art. 76 co. 4 DPR 115/2002); il tool somma 39.000 euro e risponde false perché non ha l'opzione, che il sito offre
  - Persona offesa da reati di violenza: `{"reddito_richiedente": 40000.0, "ambito": "penale", "vittima_violenza": true}` → atteso: ammesso true in deroga ai limiti di reddito (art. 76 co. 4-ter DPR 115/2002 per i reati elencati, tra cui artt. 572, 609-bis e 612-bis c.p.)

### `verifica_mediazione_obbligatoria`

Verifica se la materia rientra tra quelle per cui la mediazione è condizione di procedibilità (art. 5 co. 1 D.Lgs. 28/2010), confrontando l'input per sottostringa con la tabella mediazione_obbligatoria.json.

- Parametri: `materia: str (testo libero, case-insensitive; spazi convertiti in trattino basso)`
- Fonte normativa dichiarata: Art. 5 co. 1 D.Lgs. 28/2010 come modificato dal D.Lgs. 149/2022
- Casi di prova:
  - Responsabilità medica: `{"materia": "responsabilita medica"}` → atteso: obbligatoria true (art. 5 co. 1 D.Lgs. 28/2010: risarcimento del danno da responsabilità medica e sanitaria)
  - Contratto di rete: `{"materia": "rete"}` → atteso: obbligatoria true: l'art. 5 co. 1 elenca il contratto di rete (aggiunto dal D.Lgs. 149/2022); il tool risponde false perché la tabella usa la voce reti_impresa
  - Somministrazione di lavoro: `{"materia": "somministrazione_lavoro"}` → atteso: obbligatoria false per una controversia di lavoro (art. 409 c.p.c.): la somministrazione dell'art. 5 co. 1 è il contratto degli artt. 1559 ss. c.c.; il tool risponde true per corrispondenza di sottostringa: da verificare
  - Sinistro stradale: `{"materia": "circolazione_stradale"}` → atteso: obbligatoria false: la circolazione di veicoli e natanti è uscita dall'elenco con il DL 69/2013 conv. L. 98/2013 ed è soggetta a negoziazione assistita obbligatoria (art. 3 DL 132/2014), che il tool non menziona
  - Input generico: `{"materia": "contratti"}` → atteso: Non determinabile: l'art. 5 co. 1 elenca solo alcuni contratti (assicurativi, bancari, finanziari, comodato, affitto di aziende, opera, rete, somministrazione, subfornitura, franchising, consorzio, associazione in partecipazione); il tool risponde true agganciando i contratti assicurativi

## procure_quotazioni.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `genera_procura_liti_docx` | documento | strutturale | https://www.avvocatoandreani.it/servizi/procura-alle-liti.php (media) | Testo vigente di art. 83 c.p.c., art. 4 co. 3 D.Lgs. 28/2010, art. 2 co. 7 DL 132/2014, art. 13 co. 5 L. 247/2012 e DM 44/2011 come modificato dal DM 217/2023 (cite_law e verifica_citazioni) | Non toccato dall'audit. Verifica strutturale: una sola pagina (convertire in PDF e contare), blocco firma del mandante e autentica per ogni difensore, formula 'congiuntamente e disgiuntamente' solo con più difensori, data in lettere, errori per difensori e controparte mancanti. Riferimenti da verificare con verifica_citazioni: art. 18 co. 5 DM 44/2011 'come sostituito dal DM 48/2013' dopo le modifiche del DM 217/2023 (l'audit, paragrafo 7, segnala le citazioni PCT con confidenza media); art. 83 co. 3 c.p.c. nel testo vigente; il riferimento privacy va scritto 'Regolamento (UE) 2016/679', e la formula 'dati sensibili ... autorizzando il trattamento' è lessico anteriore al GDPR (categorie particolari, art. 9; base giuridica diversa dal consenso). La pagina del sito è un redattore di procure: riferimento di struttura, non numerico. |
| `genera_quotazione_docx` | documento | strutturale | https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | DM 147/2022, Tabella 8 (procedimenti monitori) e tabella delle esecuzioni mobiliari; art. 4 co. 1-bis DM 55/2014; art. 13 co. 2 e co. 3 DPR 115/2002 | Corretto dall'audit (paragrafo 5): contributo unificato dell'esecuzione dalla tabella (43 euro sotto 2.500, 139 da 2.500; l'immobiliare, 278, va passata a mano). Verifica strutturale e aritmetica: catena aumento 30% per atti redatti con tecniche informatiche (art. 4 co. 1-bis DM 55/2014), spese generali 15%, CPA 4%, IVA 22%, ritenuta 20% su compenso e spese generali; il prospetto esecuzione non ha né aumento del 30% né ritenuta per scelta del modello (documentarlo). Riferimenti: 'D.M. 13 agosto 2022, n. 147, pubblicato nella Gazzetta Ufficiale n. 236 dell'8 ottobre 2022 ed in vigore dal 23 ottobre 2022' (confermato dalle fonti), 'art. 4, co. 1 bis', 'art. 645 c.p.c.'. Da confermare sulla tabella dei procedimenti monitori del sito i valori della fase unica (minimo e medio: 237/473, 284/567, 685/1.370, 1.121/2.242, 2.197/4.394) e l'eventuale scaglione fino a 1.100 euro, che il tool assorbe in quello fino a 5.200; per l'esecuzione i default 166/284 sulla tabella delle esecuzioni mobiliari (https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-mobiliari.html). Fase 0: l'URL .html del piano non esiste; riscontro dei compensi sulle notule del sito e sulle tabelle DM 55/2014. |

### `genera_procura_liti_docx`

Genera in DOCX la procura alle liti ex art. 83 co. 3 c.p.c. pronta per la firma, con dichiarazioni su mediazione, negoziazione assistita, preventivo, polizza e privacy.

- Parametri: `mandante_denominazione: str; mandante_sede: str; mandante_cf_piva: str; firmatario_nome: str; firmatario_cf: str; controparte: str; difensori: list[dict] ({nome, cf}); domicilio_studio: str; pec: str; firmatario_qualifica: str = 'legale rappresentante'; fax: str = ''; luogo: str = 'Milano'; data_documento: str = '' (GG/MM/AAAA o testo libero)`
- Fonte normativa dichiarata: Art. 83 c.p.c.; art. 18 co. 5 DM 44/2011
- Casi di prova:
  - Procura con due difensori: `{"mandante_denominazione": "Esempio S.r.l.", "mandante_sede": "via Roma n. 1, 20100 Milano (MI)", "mandante_cf_piva": "01234567890", "firmatario_nome": "Mario Rossi", "firmatario_cf": "RSSMRA70A01F205X", "controparte": "Delta S.r.l., in persona del legale rappresentante pro tempore, con sede in Torino, P.IVA 09876543210", "difensori": [{"nome": "Giulia Bianchi", "cf": "BNCGLI80A41F205Y"}, {"nome": "Paolo Verdi", "cf": "VRDPLA75B02F205Z"}], "domicilio_studio": "corso Esempio n. 10, 20100 Milano (MI)", "pec": "g.bianchi@pec.esempio.it e p.verdi@pec.esempio.it", "firmatario_qualifica": "legale rappresentante", "fax": "", "luogo": "Milano", "data_documento": "25/09/2026"}` → atteso: Il testo deve contenere: 'art. 83, comma 3, c.p.c.'; 'art. 4, co. 3, D.Lgs. n. 28/2010' con 'artt. 17 e 20'; 'art. 2, co. 7, D.L. n. 132/2014, convertito in L. n. 162/2014' e 'art. 3'; 'D.Lgs. n. 196/2003' e il Regolamento (UE) 2016/679; 'art. 18, co. 5, D.M. Giustizia n. 44/2011' (citazione da riscontrare dopo il DM 217/2023); 'congiuntamente e disgiuntamente'; data '25 settembre 2026'; due righe di autentica.
  - Difensore unico con fax: `{"mandante_denominazione": "Esempio S.r.l.", "mandante_sede": "via Roma n. 1, 20100 Milano (MI)", "mandante_cf_piva": "01234567890", "firmatario_nome": "Mario Rossi", "firmatario_cf": "RSSMRA70A01F205X", "controparte": "Delta S.r.l., con sede in Torino, P.IVA 09876543210", "difensori": [{"nome": "Giulia Bianchi", "cf": "BNCGLI80A41F205Y"}], "domicilio_studio": "corso Esempio n. 10, 20100 Milano (MI)", "pec": "g.bianchi@pec.esempio.it", "firmatario_qualifica": "presidente del consiglio di amministrazione e legale rappresentante", "fax": "02 1234567", "luogo": "Torino", "data_documento": "01/08/2026"}` → atteso: Nessuna formula 'congiuntamente e disgiuntamente'; 'il nominato difensore'; recapiti 'fax 02 1234567, PEC g.bianchi@pec.esempio.it'; qualifica riportata per esteso; 'Torino, 1 agosto 2026'; una sola riga di autentica; stessi riferimenti normativi del primo caso.
  - Nessun difensore: `{"mandante_denominazione": "Esempio S.r.l.", "mandante_sede": "via Roma n. 1, 20100 Milano (MI)", "mandante_cf_piva": "01234567890", "firmatario_nome": "Mario Rossi", "firmatario_cf": "RSSMRA70A01F205X", "controparte": "Delta S.r.l.", "difensori": [], "domicilio_studio": "corso Esempio n. 10, 20100 Milano (MI)", "pec": "g.bianchi@pec.esempio.it"}` → atteso: Errore: indicare almeno un difensore; nessun file generato.

### `genera_quotazione_docx`

Genera in DOCX la lettera di quotazione dei compensi per monitorio, esecuzione o opposizione a decreto ingiuntivo, con prospetto di liquidazione, oneri accessori e blocco di accettazione.

- Parametri: `tipo: str (monitorio, esecuzione, opposizione); valore_causa: float; debitore: str; cliente_denominazione: str; cliente_indirizzo: str; difensori: list[str]; livello: str = 'minimi' (minimi, medi); accettazione_denominazione: str = ''; luogo: str = 'Milano'; data_documento: str = ''; contributo_unificato: float = -1 (-1 = automatico); compenso_fase_introduttiva: float = 166; compenso_fase_trattazione: float = 284`
- Fonte normativa dichiarata: DM 55/2014 agg. DM 147/2022; contributo unificato DPR 115/2002 (monitorio ridotto alla metà)
- Casi di prova:
  - Monitorio da 10.000 euro ai minimi: `{"tipo": "monitorio", "valore_causa": 10000, "debitore": "Delta S.r.l.", "cliente_denominazione": "Esempio S.r.l.", "cliente_indirizzo": "via Roma n. 1; 20100 - Milano", "difensori": ["Avv. Giulia Bianchi", "Avv. Paolo Verdi"], "livello": "minimi", "accettazione_denominazione": "", "luogo": "Milano", "data_documento": "25/09/2026", "contributo_unificato": -1, "compenso_fase_introduttiva": 166, "compenso_fase_trattazione": 284}` → atteso: Fase unica minima 284,00; aumento 30% 85,20; compenso totale 369,20; spese generali 55,38; CPA 16,98; imponibile 441,56; IVA 97,14; liquidabile 538,70; ritenuta 84,92; totale documento 453,78; contributo unificato 118,50 (art. 13 co. 3 DPR 115/2002) e marca 27,00; testo con il DM 147/2022 (GU n. 236, in vigore dal 23 ottobre 2022) e l'art. 4, co. 1 bis.
  - Esecuzione sulla soglia di 2.500 euro del contributo unificato: `{"tipo": "esecuzione", "valore_causa": 2500, "debitore": "Delta S.r.l.", "cliente_denominazione": "Esempio S.r.l.", "cliente_indirizzo": "via Roma n. 1; 20100 - Milano", "difensori": ["Avv. Giulia Bianchi"], "livello": "minimi", "accettazione_denominazione": "", "luogo": "Milano", "data_documento": "25/09/2026", "contributo_unificato": -1, "compenso_fase_introduttiva": 166, "compenso_fase_trattazione": 284}` → atteso: Compensi 166 + 284 = 450,00; spese generali 67,50; CPA 20,70; imponibile 538,20; IVA 118,40; liquidabile 656,60; contributo unificato 139,00 (art. 13 co. 2 DPR 115/2002; a 2.499,99 deve essere 43,00); marca 27,00 e forfait 120,00; nessun aumento del 30% e nessuna ritenuta.
  - Opposizione a decreto ingiuntivo da 26.000 euro ai medi: `{"tipo": "opposizione", "valore_causa": 26000, "debitore": "Gamma S.r.l.", "cliente_denominazione": "Esempio S.r.l.", "cliente_indirizzo": "via Roma n. 1; 20100 - Milano", "difensori": ["Avv. Giulia Bianchi", "Avv. Paolo Verdi"], "livello": "medi", "accettazione_denominazione": "", "luogo": "Milano", "data_documento": "25/09/2026", "contributo_unificato": -1, "compenso_fase_introduttiva": 166, "compenso_fase_trattazione": 284}` → atteso: Fasi medie 919 + 777 + 1.680 + 1.701 = 5.077,00; aumento 30% 1.523,10; spese generali 990,02; CPA 303,60; imponibile 7.893,72; IVA 1.736,62; liquidabile 9.630,34; ritenuta 1.518,02; totale documento 8.112,32; testo con 'art. 645 c.p.c.' e contributo unificato a carico dell'opponente.
  - Monitorio sotto 1.100 euro ai medi: `{"tipo": "monitorio", "valore_causa": 1000, "debitore": "Delta S.r.l.", "cliente_denominazione": "Esempio S.r.l.", "cliente_indirizzo": "via Roma n. 1; 20100 - Milano", "difensori": ["Avv. Giulia Bianchi"], "livello": "medi", "accettazione_denominazione": "", "luogo": "Milano", "data_documento": "25/09/2026", "contributo_unificato": -1, "compenso_fase_introduttiva": 166, "compenso_fase_trattazione": 284}` → atteso: Il tool usa la fase unica media 473,00 dello scaglione fino a 5.200 e il contributo unificato 21,50 (43 ridotto alla metà, corretto); se la Tabella 8 ha uno scaglione fino a 1.100 il compenso atteso è diverso: da leggere dal sito.

## proprieta_successioni.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `calcolo_eredita` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_quote_ereditarie.php (alta) | Testo degli artt. 536-548, 565-586 c.c. via cite_law | Audit settembre 2026: non toccato. tests/comparison/test_eredita.py confronta già tre casi (coniuge solo, coniuge e un figlio, coniuge e due figli) sulla sola quota disponibile: estenderlo con ascendenti, tre figli e fratelli, e confrontare anche le singole quote. Usare sul sito la modalità con testamento per le riserve e quella senza testamento per il caso dei fratelli. Il benchmark deve confermare le frazioni degli artt. 537, 538, 540, 542, 544 c.c. e mettere in luce che il tool mescola due piani: con i soli fratelli restituisce le quote della successione legittima (art. 570) e una disponibile pari a zero, mentre nella successione necessaria tutto è disponibile; non gestisce il concorso del coniuge con i fratelli nella successione legittima (art. 582: 2/3 e 1/3), i fratelli unilaterali (metà quota, art. 570 co. 2) né il diritto di abitazione del coniuge (art. 540 co. 2). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_imu` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-imu-nuova-ici.php (alta) ; secondarie: https://www.avvocatoandreani.it/utility/calcolo-ici.php | MEF, Dipartimento delle Finanze, prospetti delle aliquote IMU deliberate dai comuni; art. 1 co. 745-760 L. 160/2019 via cite_law | Audit settembre 2026: non toccato. Il benchmark deve confermare i moltiplicatori del co. 745 (160, 140, 80, 65, 55), la rivalutazione del 5% e la detrazione di 200 euro per A/1, A/8, A/9 abitazione principale (co. 749). Il tool non gestisce la riduzione al 75% per il canone concordato (co. 760, presente sul sito), la riduzione del 50% per comodato ai parenti in linea retta e per fabbricati inagibili o storici (co. 747), la quota statale dello 0,76% sui fabbricati del gruppo D (co. 753), i terreni agricoli e le aree fabbricabili. Il default dello 0,86% non vale per l'abitazione principale di lusso, la cui aliquota di base è 0,5% (co. 748): passare sempre l'aliquota. Fase 0: pagina confermata; /utility/calcolo-ici.php e' un duplicato interno. |
| `calcolo_superficie_commerciale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-superficie-commerciale.php (alta) | DPR 138/1998, allegato C (criteri per la superficie catastale); Agenzia delle Entrate, manuale OMI sulla consistenza degli immobili urbani | Audit settembre 2026: non toccato. I coefficienti del tool non corrispondono all'allegato C del DPR 138/1998: balconi e terrazzi comunicanti 30% fino a 25 mq e 10% oltre (15% e 5% se non comunicanti), aree scoperte 10% fino alla superficie dei vani principali e 2% oltre, pertinenze accessorie 50% se comunicanti e 25% se non comunicanti; il box è di norma unità autonoma. Il DPR misura inoltre la superficie lorda (muri fino a 50 cm, muri in comune al 50%), mentre il tool parte dalla calpestabile: sul sito inserire la superficie dei vani come lorda. Il benchmark deve confermare i coefficienti e le soglie; la precisione ESATTO va rivista. Fase 0: pagina confermata dal crawl. |
| `calcolo_usufrutto` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_usufrutto_nuda_proprieta.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tab_coefficienti_usufrutto.php | Prospetto dei coefficienti allegato al decreto MEF di fine dicembre 2025 per il 2026; tabella del sito https://www.avvocatoandreani.it/servizi/tab_coefficienti_usufrutto.php | Audit settembre 2026: non toccato. tests/comparison/test_usufrutto.py confronta già le età 30, 50, 70 e 85 in modalità vitalizia: aggiungere i confini delle fasce. Il tool usa il tasso del 2,5% con i coefficienti corrispondenti; con il tasso legale 2026 (1,6%) il prospetto ha coefficienti diversi ma le percentuali per fascia restano 95%, 90%, 85% e così via, quindi i valori devono coincidere. Il benchmark deve confermare le percentuali ai confini e la fascia oltre i 99 anni: il prospetto ufficiale si ferma alla fascia 93-99, mentre il tool aggiunge una fascia 100-120 al 5% da riscontrare. La nota della tabella cita il 'D.Lgs. 139/2015' per il tasso minimo del 2,5%: riferimento da verificare. L'usufrutto a termine, che il sito calcola, non è gestito. Fase 0: pagina confermata; tabella dei coefficienti 2026. |
| `calcolo_valore_catastale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-valore-catastale-immobili-asse-ereditario.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabella-categorie-catastali.php | Agenzia delle Entrate, scheda sul calcolo del valore catastale dei fabbricati (moltiplicatori 110, 120, 140, 60, 40,8 sulla rendita rivalutata del 5%) | Audit settembre 2026: non toccato; il triage di giugno 2026 aveva ripristinato i valori 126, 63 e 42,84 (oggi espressi come moltiplicatore di base per 1,05). Il benchmark deve confermare i moltiplicatori di successione e prima casa e soprattutto il ramo 'compravendita': per A/10, B, C/1, D ed E non prima casa il tool aggiunge un ulteriore +20% (A/10 da 63.000 a 75.600 su rendita 1.000), ma i moltiplicatori 120, 60 e 40,8 incorporano già la rivalutazione del 20% dell'art. 1-bis DL 168/2004 (100, 50 e 34 per 1,2) e 140 per il gruppo B deriva dal DL 262/2006: atteso un doppio conteggio. Per il tipo 'imu' la categoria E riceve 120 mentre calcolo_imu la rifiuta (i fabbricati del gruppo E sono esenti). I terreni non sono gestiti. Fase 0: pagina confermata; tabella delle categorie catastali. |
| `cedolare_secca` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-convenienza-cedolare-secca-affitti.php (alta) | Agenzia delle Entrate, scheda sulla cedolare secca; art. 3 D.Lgs. 23/2011 e art. 4 DL 50/2017 via cite_law | Audit settembre 2026: non modificato; compare nel paragrafo 7 ('21% per una unità nelle locazioni brevi', confidenza media, da riscontrare). Il benchmark deve confermare: (1) per le locazioni brevi 21% sull'unità indicata dal contribuente e 26% sulle altre (art. 1 co. 63 L. 213/2023), mentre il tool applica sempre 26%; verificare eventuali modifiche della L. 199/2025; (2) per il concordato la base IRPEF ridotta del 30% (95% x 70%, art. 8 L. 431/1998), mentre il tool usa il 95%; (3) che il 10% spetti solo nei comuni ad alta tensione abitativa. Il sito considera anche imposta di registro, bollo e adeguamento ISTAT evitati con la cedolare: confrontare la sola imposta sostitutiva e l'IRPEF. Il default irpef_marginale 38 non corrisponde a nessuna aliquota vigente (23, 33 o 35, 43). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `grado_parentela` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-grado-di-parentela.php (alta) | Artt. 74-78 c.c. e art. 7 D.Lgs. 346/1990 via cite_law | Audit settembre 2026: non toccato. Il benchmark deve confermare grado e linea (art. 76 c.c.) sul sito, che gestisce anche l'affinità, non gestita dal tool. Scostamenti già visibili dal codice: il campo imposta_successione indica 6% senza franchigia per i parenti in linea retta di secondo grado o oltre (nonno, nipote in linea retta), che invece godono di 4% e franchigia di 1.000.000 (art. 7 TUS, coniuge e parenti in linea retta); con la catena 'genitore,figlio' (fratello) il tool non riconosce la franchigia di 100.000; una catena che scende e poi risale ('figlio,genitore') viene accettata come parentela collaterale di secondo grado invece di essere rifiutata. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `imposta_registro_locazioni` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-imposta-registro-contratto-locazione.php (alta) | Agenzia delle Entrate, scheda 'Registrazione di un nuovo contratto, quanto si paga' (https://www.agenziaentrate.gov.it/portale/schede/fabbricatiterreni/registrazione-di-un-nuovo-contratto/quanto-si-paga-regime-ordinario); art. 17 TUR e art. 8 L. 431/1998 via cite_law | Audit settembre 2026: non modificato; compare nel paragrafo 7 ('canone concordato 2% sul 70%', confidenza media, da riscontrare). Il benchmark deve confermare: (1) per il concordato nei comuni ad alta tensione abitativa l'aliquota 2% sul 70% del canone (art. 8 L. 431/1998, 1,4% effettivo), mentre il tool applica l'1%, valore fissato anche da tests/unit/test_proprieta_successioni.py::test_contratto_concordato_1_pct e da tests/comparison/test_proprieta.py; (2) lo sconto per il pagamento dell'intera durata, pari alla metà del tasso legale per il numero delle annualità (art. 17 co. 3 TUR, 3,2% su quattro anni con il tasso 2026 dell'1,6%), che il tool non applica; (3) il minimo di 67 euro sulla prima annualità. Le locazioni commerciali (1% o 2% secondo il regime IVA del locatore), che il sito calcola, non sono gestite. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `imposte_compravendita` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-imposte-compravendita-immobiliare.php (alta) | Agenzia delle Entrate, guida 'L'acquisto della casa: le imposte'; art. 1 Tariffa parte I TUR e D.Lgs. 347/1990 via cite_law | Audit settembre 2026: non toccato. La pagina del sito è intitolata al regime 2014, che è quello ancora vigente. Il benchmark deve confermare registro 2% e 9% con minimo di 1.000 euro, ipotecaria e catastale 50 + 50, imposte fisse di 200 euro con IVA 4%, 10% e 22%, prezzo-valore con 115,5 e 126. Due scostamenti attesi: (1) per le categorie A/1, A/8 e A/9 l'agevolazione prima casa è esclusa (nota II-bis all'art. 1 Tariffa parte I), ma con tipo 'lusso' e prima_casa true il tool applica il 2%; (2) per un immobile strumentale ceduto da impresa ('commerciale' e da_costruttore) si applicano IVA 22% (se imponibile), registro 200, ipotecaria 3% e catastale 1% (art. 35 co. 10-ter DL 223/2006), mentre il tool applica IVA 10% e imposte fisse. Non è gestito l'acquisto di terreni da parte di coltivatori diretti e IAP. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `imposte_successione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-imposte-di-successione.php (alta) | Agenzia delle Entrate, scheda 'Successioni: imposte' (aliquote, franchigie, ipotecaria e catastale); art. 7 D.Lgs. 346/1990 e D.Lgs. 347/1990 via cite_law | Audit settembre 2026: non toccato; la tabella imposte_successione.json è stata riconciliata il 19/09/2026 con la scheda dell'Agenzia (solo provenienza, valori invariati). Il benchmark deve confermare aliquote, franchigie e minimi di 200 euro delle imposte ipotecaria (2%) e catastale (1%). Nel confronto inserire sul sito un solo erede e un valore interamente immobiliare, perché il tool applica la franchigia al valore passato (che deve essere la quota del singolo erede) e calcola ipotecaria e catastale su tutto valore_beni anche quando non è tutto immobiliare. La franchigia di 1.500.000 per la persona con handicap grave è raggiungibile solo con il parametro aliquote_franchigie. Verificare l'assenza di modifiche alle aliquote dopo il D.Lgs. 139/2024. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `pensione_reversibilita` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-pensione-reversibilita-inps.php (alta) | INPS, circolare di rinnovo delle pensioni 2026 (trattamento minimo); L. 335/1995 art. 1 co. 41 e Tabella F via cite_law | Audit settembre 2026: non modificato; compare nel paragrafo 7 (importi annuali incorporati senza _vintage, confidenza media, candidato a tabella con vintage). Il tool usa il trattamento minimo 2024 (7.781,93 annui). Il benchmark deve confermare: (1) le aliquote per beneficiari (60, 80, 100, 70, 80, 100, 15 per genitore); (2) le soglie di cumulo sul trattamento minimo dell'anno in corso; (3) che la riduzione non si applica se nel nucleo ci sono figli minori, studenti o inabili (art. 1 co. 41 L. 335/1995), mentre il tool la applica sempre e ignora figli_minori; (4) la clausola di salvaguardia della Tabella F (la pensione ridotta sommata al reddito non può scendere sotto quanto spetterebbe con il reddito al limite della fascia precedente), assente nel tool. Nel confronto indicare sul sito l'importo annuo su 13 mensilità. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `spese_condominiali` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-ripartizione-spese-utenze.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/ripartizione_spese_proprietario_inquilino.php | Artt. 1123-1124 c.c. e art. 9 L. 392/1978 via cite_law; tabella degli oneri accessori allegata al DM 16/01/2017; tabella Confedilizia-Sunia-Sicet-Uniat sul sito (https://www.avvocatoandreani.it/servizi/ripartizione_spese_proprietario_inquilino.php) | Audit settembre 2026: non toccato. Il calcolatore del sito ripartisce una spesa generica per millesimi e verifica solo l'aritmetica di base; il resto si verifica sulla norma. Il benchmark deve confermare: (1) la quota per millesimi (art. 1123 c.c.); (2) che la metà della spesa dell'ascensore ripartita per altezza (art. 1124 c.c.) richiede le altezze di tutte le unità: la normalizzazione su 10 piani del tool non è una ripartizione e sopra il decimo piano supera la metà della spesa; (3) la validazione dei millesimi (oltre 1.000 il tool restituisce più della spesa totale); (4) la ripartizione tra locatore e conduttore, che il tool semplifica (ordinarie tutte al conduttore, ascensore a metà), mentre l'art. 9 L. 392/1978 e la tabella degli oneri accessori distinguono voce per voce. Fase 0: nessuna pagina del sito ripartisce per millesimi; la pagina delle utenze e la tabella proprietario/inquilino sono i riscontri parziali. |

### `calcolo_eredita`

Calcola le quote di legittima dei legittimari e la quota disponibile per le combinazioni di coniuge, figli e ascendenti; per i soli fratelli restituisce le quote della successione legittima.

- Parametri: `massa_ereditaria: float; eredi: dict {'coniuge': bool, 'figli': int, 'ascendenti': bool, 'fratelli': int}`
- Fonte normativa dichiarata: Artt. 536 ss. c.c., successione necessaria. Precisione ESATTO.
- Casi di prova:
  - Coniuge e un figlio: `{"massa_ereditaria": 300000, "eredi": {"coniuge": true, "figli": 1, "ascendenti": false, "fratelli": 0}}` → atteso: Coniuge 1/3 = 100.000; figlio 1/3 = 100.000; disponibile 100.000 (art. 542 co. 1 c.c.).
  - Coniuge e tre figli: `{"massa_ereditaria": 400000, "eredi": {"coniuge": true, "figli": 3, "ascendenti": false, "fratelli": 0}}` → atteso: Coniuge 1/4 = 100.000; figli 1/2 in parti uguali, 66.666,67 ciascuno; disponibile 100.000 (art. 542 co. 2).
  - Coniuge e ascendenti senza figli: `{"massa_ereditaria": 120000, "eredi": {"coniuge": true, "figli": 0, "ascendenti": true, "fratelli": 0}}` → atteso: Coniuge 1/2 = 60.000; ascendenti 1/4 = 30.000; disponibile 30.000 (art. 544).
  - Soli ascendenti: `{"massa_ereditaria": 90000, "eredi": {"coniuge": false, "figli": 0, "ascendenti": true, "fratelli": 0}}` → atteso: Ascendenti 1/3 = 30.000; disponibile 60.000 (art. 538).
  - Soli fratelli germani: `{"massa_ereditaria": 100000, "eredi": {"coniuge": false, "figli": 0, "ascendenti": false, "fratelli": 2}}` → atteso: Successione necessaria: nessun legittimario, disponibile 100.000. Successione legittima (sito senza testamento): 50.000 per fratello (art. 570). Il tool restituisce le quote legittime con disponibile 0: incoerenza da segnalare.

### `calcolo_imu`

Calcola l'IMU annua e la rata semestrale da rendita catastale, categoria e aliquota comunale, con esenzione dell'abitazione principale non di lusso e detrazione di 200 euro.

- Parametri: `rendita_catastale: float; categoria: str (per esempio 'A/2', 'C/1', 'D/1'); aliquota_comunale: float = 0.86 (percentuale); prima_casa: bool = False`
- Fonte normativa dichiarata: L. 160/2019, art. 1, co. 738-783. Precisione ESATTO per moltiplicatori e rivalutazione, INDICATIVO per l'aliquota.
- Casi di prova:
  - Abitazione non principale ad aliquota massima: `{"rendita_catastale": 1000, "categoria": "A/2", "aliquota_comunale": 1.06, "prima_casa": false}` → atteso: Base 1.000 x 1,05 x 160 = 168.000 (co. 745); IMU 1.780,80; acconto 890,40.
  - Abitazione principale di lusso: `{"rendita_catastale": 1500, "categoria": "A/1", "aliquota_comunale": 0.6, "prima_casa": true}` → atteso: Base 252.000; 0,6% = 1.512 meno detrazione 200 (co. 749) = 1.312,00.
  - Negozio C/1: `{"rendita_catastale": 800, "categoria": "C/1", "aliquota_comunale": 0.86, "prima_casa": false}` → atteso: Base 840 x 55 = 46.200; IMU 397,32.
  - Capannone D/1: `{"rendita_catastale": 5000, "categoria": "D/1", "aliquota_comunale": 0.86}` → atteso: Base 341.250 (moltiplicatore 65); IMU 2.934,75, di cui 2.593,50 allo Stato (0,76%, co. 753): il tool non separa la quota.
  - Abitazione principale non di lusso: `{"rendita_catastale": 700, "categoria": "A/2", "prima_casa": true}` → atteso: 0,00 (esenzione, co. 740).
  - Pertinenza C/6 non abitazione principale: `{"rendita_catastale": 200, "categoria": "C/6", "aliquota_comunale": 1.06}` → atteso: Base 200 x 1,05 x 160 = 33.600; IMU 356,16.

### `calcolo_superficie_commerciale`

Calcola la superficie commerciale sommando la superficie calpestabile e le pertinenze ponderate con coefficienti fissi.

- Parametri: `superficie_calpestabile: float; balconi: float = 0; terrazzi: float = 0; giardino: float = 0; cantina: float = 0; garage: float = 0`
- Fonte normativa dichiarata: DPR 138/1998, standard dimensionali catastali; coefficienti fissi 1,00, 0,33, 0,25, 0,10, 0,25, 0,50. Precisione ESATTO.
- Casi di prova:
  - Solo vani principali: `{"superficie_calpestabile": 100}` → atteso: 100,00 mq se sul sito si inseriscono 100 mq lordi.
  - Balcone di 30 mq: `{"superficie_calpestabile": 80, "balconi": 30}` → atteso: 80 + 25 x 30% + 5 x 10% = 88,00 mq (DPR 138/1998 all. C); il tool restituisce 89,90.
  - Giardino di 200 mq: `{"superficie_calpestabile": 80, "giardino": 200}` → atteso: 80 + 80 x 10% + 120 x 2% = 90,40 mq; il tool restituisce 100,00.
  - Terrazzo di 20 mq: `{"superficie_calpestabile": 80, "terrazzi": 20}` → atteso: 80 + 20 x 30% = 86,00 mq se comunicante; il tool restituisce 85,00.
  - Cantina e box: `{"superficie_calpestabile": 80, "cantina": 10, "garage": 20}` → atteso: Cantina non comunicante 25% = 2,5 (50% se comunicante); box da leggere dal sito; il tool restituisce 92,50.

### `calcolo_usufrutto`

Calcola il valore dell'usufrutto vitalizio e della nuda proprietà dall'età dell'usufruttuario con i coefficienti del prospetto del TUR.

- Parametri: `valore_piena_proprieta: float; eta_usufruttuario: int (0-120)`
- Fonte normativa dichiarata: DPR 131/1986, prospetto dei coefficienti per l'usufrutto (aggiornato annualmente). Precisione ESATTO.
- Casi di prova:
  - Confine superiore della prima fascia: `{"valore_piena_proprieta": 100000, "eta_usufruttuario": 20}` → atteso: Usufrutto 95.000 (95%), nuda proprietà 5.000.
  - Primo anno della seconda fascia: `{"valore_piena_proprieta": 100000, "eta_usufruttuario": 21}` → atteso: Usufrutto 90.000 (90%), nuda proprietà 10.000.
  - Fascia 70-72: `{"valore_piena_proprieta": 150000, "eta_usufruttuario": 70}` → atteso: Usufrutto 60.000 (40%), nuda proprietà 90.000.
  - Ultima fascia del prospetto: `{"valore_piena_proprieta": 100000, "eta_usufruttuario": 99}` → atteso: Usufrutto 10.000 (10%), nuda proprietà 90.000.
  - Oltre il prospetto: `{"valore_piena_proprieta": 100000, "eta_usufruttuario": 100}` → atteso: Da leggere dalla fonte: il prospetto si ferma a 99 anni; il tool applica 5% (5.000).

### `calcolo_valore_catastale`

Calcola il valore catastale (rendita rivalutata del 5% per il moltiplicatore della categoria) per successione, compravendita o IMU.

- Parametri: `rendita_catastale: float; categoria: str; tipo: str = 'successione' (successione \| compravendita \| imu); prima_casa: bool = False`
- Fonte normativa dichiarata: DPR 131/1986 art. 52; D.Lgs. 346/1990 art. 34; DL 168/2004 art. 1-bis; DL 262/2006 art. 2 co. 45. Precisione ESATTO.
- Casi di prova:
  - Abitazione, successione: `{"rendita_catastale": 1000, "categoria": "A/2", "tipo": "successione", "prima_casa": false}` → atteso: 1.000 x 1,05 x 120 = 126.000,00.
  - Prima casa, compravendita: `{"rendita_catastale": 1000, "categoria": "A/2", "tipo": "compravendita", "prima_casa": true}` → atteso: 1.000 x 1,05 x 110 = 115.500,00.
  - Ufficio A/10, compravendita: `{"rendita_catastale": 1000, "categoria": "A/10", "tipo": "compravendita", "prima_casa": false}` → atteso: 1.000 x 1,05 x 60 = 63.000,00 (il 60 incorpora già il +20% del DL 168/2004); il tool restituisce 75.600,00.
  - Gruppo B, successione: `{"rendita_catastale": 1000, "categoria": "B/1", "tipo": "successione"}` → atteso: 1.000 x 1,05 x 140 = 147.000,00.
  - Negozio C/1, successione: `{"rendita_catastale": 1000, "categoria": "C/1", "tipo": "successione"}` → atteso: 1.000 x 1,05 x 40,8 = 42.840,00.
  - Capannone D/1, IMU: `{"rendita_catastale": 1000, "categoria": "D/1", "tipo": "imu"}` → atteso: 1.000 x 1,05 x 65 = 68.250,00 (co. 745 L. 160/2019).
  - Categoria E, IMU: `{"rendita_catastale": 1000, "categoria": "E/1", "tipo": "imu"}` → atteso: Errore o esenzione (gruppo E esente dall'IMU); il tool restituisce 126.000,00.

### `cedolare_secca`

Confronta la cedolare secca (21%, 10% concordato, 26% brevi) con l'IRPEF ordinaria sul 95% del canone più addizionali stimate al 2%.

- Parametri: `canone_annuo: float; tipo_contratto: str = 'libero' (libero \| concordato \| brevi); irpef_marginale: float = 38`
- Fonte normativa dichiarata: D.Lgs. 23/2011 art. 3; aliquote 21% (libero), 10% (concordato), 26% (brevi). Precisione INDICATIVO per l'IRPEF.
- Casi di prova:
  - Libero, aliquota marginale 35%: `{"canone_annuo": 12000, "tipo_contratto": "libero", "irpef_marginale": 35}` → atteso: Cedolare 21% = 2.520,00 (art. 3 co. 2 D.Lgs. 23/2011); IRPEF sul 95% = 3.990,00 più addizionali; confronto complessivo da leggere dal sito.
  - Concordato, aliquota marginale 23%: `{"canone_annuo": 12000, "tipo_contratto": "concordato", "irpef_marginale": 23}` → atteso: Cedolare 10% = 1.200,00; IRPEF su 12.000 x 95% x 70% = 7.980, imposta 1.835,40 (art. 8 L. 431/1998); il tool calcola 2.622,00 su 11.400.
  - Locazione breve di una sola unità: `{"canone_annuo": 10000, "tipo_contratto": "brevi", "irpef_marginale": 35}` → atteso: 21% = 2.100,00 per l'unità indicata dal contribuente (art. 4 co. 2 DL 50/2017 mod. art. 1 co. 63 L. 213/2023); il tool applica 26% (2.600,00).
  - Libero, aliquota marginale 43%: `{"canone_annuo": 20000, "tipo_contratto": "libero", "irpef_marginale": 43}` → atteso: Cedolare 4.200,00; IRPEF sul 95% = 8.170,00 più addizionali.

### `grado_parentela`

Calcola grado e linea di parentela da una relazione nominata o da una catena di passi, con indicazione della rilevanza successoria e del trattamento fiscale.

- Parametri: `relazione: str (figlio \| genitore \| nipote_figlio \| nonno \| fratello \| sorella \| zio \| nipote_zio \| bisnonno \| pronipote \| cugino \| prozio \| cugino_secondo, oppure catena come 'genitore,figlio')`
- Fonte normativa dichiarata: Artt. 74-77 c.c., parentela e affinità. Precisione ESATTO.
- Casi di prova:
  - Cugino: `{"relazione": "cugino"}` → atteso: Quarto grado in linea collaterale (art. 76 c.c.); imposta 6% senza franchigia.
  - Nonno: `{"relazione": "nonno"}` → atteso: Secondo grado in linea retta; imposta di successione 4% con franchigia di 1.000.000 (art. 7 TUS); il tool indica 6% senza franchigia.
  - Catena che individua un fratello: `{"relazione": "genitore,figlio"}` → atteso: Secondo grado collaterale; franchigia 100.000 e 6%; il tool indica 6% senza franchigia.
  - Settimo grado: `{"relazione": "genitore,genitore,genitore,figlio,figlio,figlio,figlio"}` → atteso: Nessun vincolo di parentela oltre il sesto grado (art. 77 c.c.); imposta 8%.
  - Catena incoerente: `{"relazione": "figlio,genitore"}` → atteso: Errore atteso (la catena non individua un parente); il tool restituisce secondo grado collaterale.

### `imposta_registro_locazioni`

Calcola l'imposta di registro sui contratti di locazione abitativa per prima annualità, annualità successive e intera durata.

- Parametri: `canone_annuo: float; durata_anni: int = 4; tipo_contratto: str = 'libero' (libero \| concordato); prima_registrazione: bool = True`
- Fonte normativa dichiarata: DPR 131/1986, art. 5 Tariffa parte I; aliquota 2% (libero) o 1% (concordato); minimo 67 euro. Precisione ESATTO.
- Casi di prova:
  - Libero, quattro anni, pagamento annuale e per l'intera durata: `{"canone_annuo": 12000, "durata_anni": 4, "tipo_contratto": "libero", "prima_registrazione": true}` → atteso: 240,00 annui; per l'intera durata 960 ridotto del 3,2% (1,6%/2 x 4, art. 17 co. 3 TUR) = 929,28; il tool indica 960,00.
  - Canone basso: minimo sulla prima annualità: `{"canone_annuo": 3000, "durata_anni": 4, "tipo_contratto": "libero"}` → atteso: Prima annualità 67,00 (minimo), successive 60,00; intera durata 240 ridotto del 3,2% = 232,32 (tool 247,00).
  - Concordato in comune ad alta tensione abitativa: `{"canone_annuo": 6000, "durata_anni": 3, "tipo_contratto": "concordato"}` → atteso: 6.000 x 70% x 2% = 84,00 annui (art. 8 L. 431/1998); il tool applica l'1% (60, elevato a 67).
  - Annualità successiva senza minimo: `{"canone_annuo": 12000, "durata_anni": 1, "tipo_contratto": "libero", "prima_registrazione": false}` → atteso: 240,00.

### `imposte_compravendita`

Calcola imposte di registro, ipotecaria, catastale o IVA per l'acquisto di un immobile, con prima casa, acquisto da costruttore e prezzo-valore.

- Parametri: `prezzo: float; tipo_immobile: str = 'abitazione' (abitazione \| lusso \| terreno_agricolo \| commerciale); prima_casa: bool = False; da_costruttore: bool = False; rendita_catastale: float \| None = None; aliquote_registro: dict \| None = None`
- Fonte normativa dichiarata: DPR 131/1986 (TUR, Tariffa parte I art. 1); DPR 633/1972 (IVA). Precisione ESATTO per aliquote e importi fissi, INDICATIVO per il prezzo-valore.
- Casi di prova:
  - Prima casa da privato con prezzo-valore: `{"prezzo": 200000, "tipo_immobile": "abitazione", "prima_casa": true, "da_costruttore": false, "rendita_catastale": 1000}` → atteso: Base 1.000 x 115,5 = 115.500 (art. 1 co. 497 L. 266/2005); registro 2% = 2.310; ipotecaria 50, catastale 50; totale 2.410,00.
  - Seconda casa da privato con prezzo-valore: `{"prezzo": 200000, "tipo_immobile": "abitazione", "prima_casa": false, "rendita_catastale": 1000}` → atteso: Base 126.000; registro 9% = 11.340; totale 11.440,00.
  - Prima casa di basso valore: minimo del registro: `{"prezzo": 30000, "tipo_immobile": "abitazione", "prima_casa": true}` → atteso: 2% = 600 elevato al minimo di 1.000; totale 1.100,00.
  - Prima casa da costruttore: `{"prezzo": 250000, "tipo_immobile": "abitazione", "prima_casa": true, "da_costruttore": true}` → atteso: IVA 4% = 10.000; registro, ipotecaria e catastale 200 ciascuna; totale 10.600,00.
  - Abitazione di lusso da privato dichiarata prima casa: `{"prezzo": 800000, "tipo_immobile": "lusso", "prima_casa": true}` → atteso: Agevolazione esclusa per A/1, A/8, A/9: registro 9% = 72.000, totale 72.100,00; il tool applica il 2% (16.100,00).
  - Strumentale ceduto da impresa: `{"prezzo": 300000, "tipo_immobile": "commerciale", "da_costruttore": true}` → atteso: IVA 22% = 66.000 (se imponibile), registro 200, ipotecaria 3% = 9.000, catastale 1% = 3.000; il tool applica IVA 10% e imposte fisse (30.600,00).
  - Terreno agricolo di basso valore, acquirente non agricoltore: `{"prezzo": 5000, "tipo_immobile": "terreno_agricolo"}` → atteso: 15% = 750 elevato al minimo di 1.000; ipotecaria e catastale 50 + 50; totale 1.100,00.

### `imposte_successione`

Calcola l'imposta di successione per grado di parentela con franchigia e aliquota e, se ci sono immobili, le imposte ipotecaria e catastale.

- Parametri: `valore_beni: float; parentela: str (coniuge_linea_retta \| fratelli_sorelle \| parenti_fino_4_grado_affini_fino_3 \| altri); immobili: bool = False; prima_casa: bool = False; aliquote_franchigie: list[dict] \| None = None`
- Fonte normativa dichiarata: D.Lgs. 346/1990 (TUS); aliquote 4%, 6%, 6%, 8%; franchigie 1.000.000 (coniuge e linea retta), 100.000 (fratelli). Precisione ESATTO.
- Casi di prova:
  - Coniuge, valore oltre la franchigia: `{"valore_beni": 1500000, "parentela": "coniuge_linea_retta", "immobili": false, "prima_casa": false}` → atteso: (1.500.000 - 1.000.000) x 4% = 20.000,00 (art. 7 TUS).
  - Fratello con immobili, nessuna agevolazione: `{"valore_beni": 250000, "parentela": "fratelli_sorelle", "immobili": true, "prima_casa": false}` → atteso: (250.000 - 100.000) x 6% = 9.000; ipotecaria 2% = 5.000; catastale 1% = 2.500; totale 16.500,00 se tutto il valore è immobiliare.
  - Parente entro il quarto grado, valore piccolo: minimi: `{"valore_beni": 5000, "parentela": "parenti_fino_4_grado_affini_fino_3", "immobili": true, "prima_casa": false}` → atteso: Imposta 300,00 (6% senza franchigia); ipotecaria e catastale al minimo di 200 ciascuna; totale 700,00.
  - Estraneo con agevolazione prima casa: `{"valore_beni": 100000, "parentela": "altri", "immobili": true, "prima_casa": true}` → atteso: 8% = 8.000; ipotecaria e catastale fisse 200 + 200; totale 8.400,00.
  - Franchigia per persona con handicap grave tramite override: `{"valore_beni": 2000000, "parentela": "coniuge_linea_retta", "aliquote_franchigie": [{"parentela": "coniuge_linea_retta", "aliquota": 4, "franchigia": 1500000}]}` → atteso: (2.000.000 - 1.500.000) x 4% = 20.000,00 (art. 7 co. 2-bis TUS, franchigia per i soggetti della L. 104/1992).

### `pensione_reversibilita`

Calcola la pensione di reversibilità INPS per quota dei beneficiari e la riduzione per cumulo con i redditi del beneficiario (Tabella F).

- Parametri: `pensione_de_cuius: float (annua lorda); beneficiari: dict {'coniuge': bool, 'figli': int, 'figli_minori': int, 'genitori': int}; reddito_beneficiario: float = 0`
- Fonte normativa dichiarata: L. 335/1995, art. 1 co. 41 e Tabella F (trattamento minimo aggiornato ogni anno). Precisione INDICATIVO.
- Casi di prova:
  - Coniuge solo senza altri redditi: `{"pensione_de_cuius": 20000, "beneficiari": {"coniuge": true, "figli": 0, "genitori": 0}, "reddito_beneficiario": 0}` → atteso: 60% = 12.000,00 annui, 923,08 per 13 mensilità.
  - Coniuge solo con reddito oltre cinque volte il minimo: `{"pensione_de_cuius": 20000, "beneficiari": {"coniuge": true, "figli": 0}, "reddito_beneficiario": 50000}` → atteso: Cumulabilità al 50% (Tabella F): 6.000,00, con verifica della soglia sul trattamento minimo 2026 dalla circolare INPS.
  - Coniuge con figlio minore e reddito alto: `{"pensione_de_cuius": 20000, "beneficiari": {"coniuge": true, "figli": 1, "figli_minori": 1}, "reddito_beneficiario": 50000}` → atteso: Nessuna riduzione per la presenza del figlio minore (art. 1 co. 41 L. 335/1995): 80% = 16.000,00; il tool riduce del 50% (8.000,00).
  - Reddito appena oltre tre volte il minimo 2024: `{"pensione_de_cuius": 20000, "beneficiari": {"coniuge": true}, "reddito_beneficiario": 23500}` → atteso: Con il minimo 2024 la soglia è 23.345,79: riduzione del 25% limitata dalla salvaguardia a una pensione di 11.845,79; con il minimo 2026 la soglia potrebbe non essere superata (12.000,00). Da leggere dal sito; il tool restituisce 9.000,00.
  - Tre figli soli: `{"pensione_de_cuius": 24000, "beneficiari": {"figli": 3}}` → atteso: 100% = 24.000,00.
  - Due genitori: `{"pensione_de_cuius": 30000, "beneficiari": {"genitori": 2}}` → atteso: 15% ciascuno = 9.000,00 complessivi.

### `spese_condominiali`

Ripartisce una spesa condominiale per millesimi (ascensore metà per millesimi e metà per piano) e, se l'immobile è locato, tra proprietario e inquilino.

- Parametri: `importo_totale: float; millesimi_proprietario: float; tipo_spesa: str = 'ordinaria' (ordinaria \| straordinaria \| riscaldamento \| ascensore); piano: int = 0; immobile_locato: bool = False`
- Fonte normativa dichiarata: Artt. 1123-1124 c.c.; L. 392/1978 art. 9. Precisione ESATTO per millesimi, INDICATIVO per l'ascensore (normalizzazione su 10 piani).
- Casi di prova:
  - Spesa ordinaria per millesimi: `{"importo_totale": 10000, "millesimi_proprietario": 85.5, "tipo_spesa": "ordinaria"}` → atteso: 855,00 (art. 1123 co. 1 c.c.).
  - Ascensore, terzo piano: `{"importo_totale": 6000, "millesimi_proprietario": 100, "tipo_spesa": "ascensore", "piano": 3}` → atteso: Metà per millesimi = 300,00 (art. 1124 c.c.); l'altra metà in proporzione all'altezza sulla somma delle altezze dell'edificio, non determinabile senza quei dati; il tool restituisce 1.200,00.
  - Ascensore, dodicesimo piano: `{"importo_totale": 6000, "millesimi_proprietario": 100, "tipo_spesa": "ascensore", "piano": 12}` → atteso: La quota per altezza non può superare 3.000,00 (metà della spesa); il tool attribuisce 3.600,00 per l'altezza e 3.900,00 in totale: errore strutturale.
  - Millesimi oltre 1.000: `{"importo_totale": 10000, "millesimi_proprietario": 1200}` → atteso: Errore di validazione atteso; il tool restituisce 12.000,00.
  - Spesa ordinaria con immobile locato: `{"importo_totale": 10000, "millesimi_proprietario": 85.5, "tipo_spesa": "ordinaria", "immobile_locato": true}` → atteso: Da leggere dalla fonte: secondo l'art. 9 L. 392/1978 e la tabella degli oneri accessori non tutte le voci ordinarie sono a carico del conduttore; il tool attribuisce 855,00 al conduttore.

## risarcimento_danni.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `danno_biologico_macro` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-danno-biologico-macropermanenti-tabella-unica.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tabella-unica-nazionale-danno-biologico.php, https://www.avvocatoandreani.it/servizi/tabelle_danno_biologico_macropermanenti.php | Gazzetta Ufficiale: DPR 13 gennaio 2025 n. 12, tabella unica nazionale delle menomazioni da 10 a 100 punti e dei relativi valori economici (art. 138 co. 1 e 2 Cod. Ass.); Osservatorio sulla giustizia civile di Milano, tabelle per la liquidazione del danno non patrimoniale (edizione vigente) | Declassato dall'audit a STIMATO (par. 5): valori non riconducibili alla tabella unica nazionale (TUN) né a Milano, importi non plausibili oltre il 20%, personalizzazione riportata dal 50 al 30% (art. 138 co. 3). La pagina del sito (titolo nei risultati: Tabelle Danno Biologico Lesioni Macropermanenti 2025 2026 Milano e Roma) espone tabelle di tribunale e va aperta per capire se calcola o solo tabula. Il benchmark deve misurare lo scostamento del tool per 10, 20, 50 e 100 punti a più età e raccogliere dalla Gazzetta i valori della TUN da trascrivere (par. 8 punto 2 dell'audit, dopo di che il tool torna INDICATIVO). Ricordare che la TUN incorpora la componente morale (art. 138 co. 2 lett. e) e riguarda RC auto e responsabilità sanitaria (ambito temporale da riscontrare sul DPR), mentre per gli altri illeciti restano le tabelle di Milano; i coefficienti a gradino per decenni d'età del tool non hanno riscontro nell'art. 138 co. 2 lett. d. Da aggiornare: tests/comparison/test_risarcimento.py (TestDannoBiologicoMacro.test_personalizzazione) usa personalizzazione_pct=50, ora rifiutata: nella suite live fallirà con KeyError. Fase 0: il sito ha il calcolatore con la tabella unica nazionale (DPR 12/2025) e la tabella; la pagina indicata dalla ricerca era quella delle tabelle dei tribunali. |
| `danno_biologico_micro` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_danno_biologico.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tab_danno_biologico_lieve_entita.php, https://www.avvocatoandreani.it/servizi/tabella-menomazioni-punti-invalidita.php | Gazzetta Ufficiale: DM MIMIT 20 luglio 2026 di aggiornamento degli importi dell'art. 139 Cod. Ass. (valore del primo punto e importo giornaliero dell'inabilità temporanea assoluta), estremi da riscontrare | Corretto dall'audit (par. 5): sommava i valori punto dei gradi inferiori; ora valore punto per numero di punti (art. 139 co. 2 lett. a e co. 6), al 9% da 13.937 a 20.461 euro. Provenienza della pagina: l'URL non compare nei risultati di ricerca di questa sessione (budget WebSearch esaurito) ma è quello guidato dal test esistente tests/comparison/test_danno_biologico.py (campi Anno, Punti, Decimali, Eta, GgAss): da riscontrare in fase 0. Il benchmark deve confermare: (1) il danno permanente sui casi del test esistente (1, 3, 5 e 9 punti), che con la formula precedente non potevano passare; (2) l'anno della tabella: il test seleziona Anno 2025 mentre il tool applica il DM 20/07/2026, quindi sul sito va scelto 2026 (con 2025 lo scarto atteso è il 2,6%, 963,40 contro 988,45 euro) e la tolleranza di 1 euro del test va portata a 0,01; (3) gli importi 988,45 e 57,64 sulla Gazzetta Ufficiale; (4) la base della personalizzazione: il tool applica la percentuale a permanente più temporaneo, l'art. 139 co. 3 la riferisce al danno calcolato sulla tabella delle menomazioni; (5) l'arrotondamento del valore punto, che il tool non arrotonda prima di moltiplicare; (6) il confine della riduzione per età (10 e 11 anni). Il tool accetta solo punti interi, il sito ha il campo Decimali. Fase 0: pagina confermata; tabella dei valori punto e tabella delle menomazioni DM 3/7/2003 come riscontro. |
| `danno_non_patrimoniale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_danno_non_patrimoniale.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo_danno_biologico.php | DM MIMIT 20/07/2026 per l'art. 139; DPR 13 gennaio 2025 n. 12 (TUN) per l'art. 138; per i gradi dal 10% la pagina https://www.avvocatoandreani.it/servizi/tabelle_danno_biologico_macropermanenti.php | Non citato ai par. 5 e 7, ma conserva l'errore corretto in danno_biologico_micro: per i gradi 1-9 somma ancora i valori punto dei gradi inferiori (9 punti a 10 anni: 13.937,15 euro contro 20.460,92) e sopra il 9% usa la stima macro dichiarata STIMATO pur restando INDICATIVO. Pagina del sito: stessa provenienza di danno_biologico_micro (test esistente, non risultati di ricerca). Il benchmark deve confermare sul sito la divergenza della componente biologica e indicare la correzione (riuso del calcolo di danno_biologico_micro e, dal 10%, della TUN), poi segnalare: l'inabilità temporanea è esposta come danno patrimoniale emergente mentre è danno biologico temporaneo (art. 139 co. 2 lett. b; art. 138 co. 2 lett. f), con l'importo giornaliero dell'art. 139 applicato anche sopra il 9%; personalizzazioni fino al 50% morale più 50% esistenziale, oltre i tetti del 20% (art. 139 co. 3) e del 30% (art. 138 co. 3) e in contrasto con l'unitarietà del danno non patrimoniale (Cass. SU 26972/2008: il danno esistenziale non è voce autonoma); tipo_danno non incide sul calcolo. Fase 0: calcolatore dedicato del danno non patrimoniale (tabelle Milano e Roma) presente sul sito. |
| `danno_parentale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-danno-perdita-parentale-tribunale-milano.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-risarcimento-danno-perdita-parentale.php | Osservatorio sulla giustizia civile di Milano, tabella a punti per il danno da perdita del rapporto parentale (edizione vigente); Tribunale di Roma, tabella per la perdita del rapporto parentale; seconda pagina del sito per Roma: https://www.avvocatoandreani.it/servizi/calcolo-risarcimento-danno-perdita-parentale.php (titolo nei risultati: Calcolo Danno da Perdita Parentale per Morte del Congiunto - Tabelle 2025 Tribunale di Roma) | Declassato dall'audit a INDICATIVO (par. 7, confidenza alta): Milano liquida a punti dal 2022 (Cass. 10579/2021), Roma è una stima. I range del tool coincidono con i valori a forbice della tabella di Milano (168.250-336.500 euro per genitori, figli e coniuge; 24.350-146.120 per fratelli, nonni e nipoti) moltiplicati per 1,162268: è il sistema a forbice superato. Il calcolatore del sito chiede i dati della tabella a punti (età della vittima e del superstite, convivenza, altri congiunti superstiti, qualità e intensità della relazione) che il tool non riceve: il confronto è di inclusione nel range, non puntuale. Il benchmark deve registrare il valore del sito per configurazioni tipiche, rilevare valore del punto e punteggi dell'edizione vigente e fornire gli elementi per riscrivere il tool sulla tabella a punti (parametri di età, convivenza e superstiti). Per Roma usare la seconda pagina, che nei risultati si presenta come tabelle 2025, mentre il tool dichiara un'edizione 2024 stimata. Fase 0: oltre alla pagina di Milano il sito ha il calcolatore generale del danno da perdita parentale (tabelle 2025-2026). |
| `equo_indennizzo` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-equo-indennizzo-causa-servizio.php (alta) | Normattiva: art. 6 DL 201/2011, DPR 461/2001 e norme sulla misura dell'equo indennizzo, tabelle A e B DPR 834/1981; circolari dei Ministeri della difesa e dell'interno per il comparto sicurezza e difesa | Marcato PREVIGENTE dall'audit (par. 3: tag, riga Regime e wrapper). Punto nuovo da verificare con cite_law: l'art. 6 co. 1 DL 201/2011 esclude dall'abrogazione il personale del comparto sicurezza, difesa, vigili del fuoco e soccorso pubblico, oltre ai procedimenti pendenti o ancora proponibili al 06/12/2011; per quel personale l'istituto è vigente anche per fatti successivi, quindi la riga Regime ('istituto abrogato per eventi successivi', 'nessun tool vigente equivalente') è incompleta. Sul calcolo il benchmark deve confermare la formula legale: la misura dipende dalla categoria della Tabella A (o B) e dallo stipendio tabellare, con le eventuali riduzioni per età previste dalla disciplina, mentre il tool moltiplica anche per la percentuale di invalidità e usa coefficienti (da 0,7 a 8) e fasce percentuali per categoria senza fonte; verificare anche che la pensione privilegiata spetti solo alle categorie 1-5 come afferma il tool. Il test in tests/comparison/test_risarcimento.py verifica solo l'aritmetica interna. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `menomazioni_plurime` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-riduzionistico-menomazioni-plurime.php (alta) | DM Ministero della Sanità 5 febbraio 1992 (tabella indicativa delle percentuali d'invalidità civile), criteri per le menomazioni plurime coesistenti; criteri applicativi della TUN (DPR 12/2025) e della tabella delle micropermanenti (DM 3 luglio 2003) | Non citato ai par. 5 e 7 dell'audit. Formula deterministica verificabile a mano: il benchmark consiste nel riscontro della fonte che prescrive il calcolo riduzionistico (DM 5 febbraio 1992; se Normattiva non lo contiene, Gazzetta Ufficiale) e nei casi di controllo. Da segnalare: il tool applica la formula a ogni combinazione, mentre i barèmes distinguono le menomazioni coesistenti (calcolo riduzionistico) da quelle concorrenti sullo stesso apparato (valutazione complessiva) e l'INAIL usa per le preesistenze la formula di Gabrielli; il docstring chiede l'ordine decrescente, ma il risultato non dipende dall'ordine. Nessuna pagina del sito nei risultati di ricerca disponibili (budget WebSearch della sessione esaurito prima di questo gruppo): da cercare nella ricognizione della fase 0. Fase 0: calcolatore riduzionistico (Balthazard) presente sul sito; strategia portata da solo_norma ad andreani. |
| `risarcimento_inail` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_risarcimento_inail_infortunio_lavoro.php (alta) | INAIL: Tabella indennizzo danno biologico (in capitale e in rendita) e Tabella dei coefficienti del DM 12 luglio 2000 con gli aggiornamenti; decreto annuale di rivalutazione con retribuzione minimale e massimale per le rendite | Non citato ai par. 5 e 7 dell'audit, già INDICATIVO. Il benchmark deve far emergere tre scostamenti strutturali rispetto all'art. 13 D.Lgs. 38/2000: (1) tra 6 e 15% l'indennizzo in capitale dipende da grado, età e sesso secondo la Tabella indennizzo danno biologico, non dalla retribuzione, mentre il tool applica il 7% per grado alla retribuzione annua (al 15% riconosce più di un'annualità); (2) dal 16% la rendita somma una quota biologica tabellare e una quota patrimoniale pari a retribuzione (tra minimale e massimale, art. 116 DPR 1124/1965) per coefficiente della Tabella dei coefficienti per grado, mentre il tool usa il 40% della retribuzione per il grado più il 60% su (grado - 16), azzerando la quota patrimoniale proprio al 16%; (3) nell'inabilità temporanea l'INAIL paga dal quarto giorno successivo all'evento (art. 68 DPR 1124/1965) sulla retribuzione media giornaliera (art. 116), il giorno dell'evento è a carico del datore per intero e i tre giorni di carenza al 60% salvo contratto (art. 73, da riscontrare), mentre il tool divide la retribuzione annua per 365 e indica i primi tre giorni al 100%. Il tool non chiede età e sesso, che il sito probabilmente richiede: annotare i campi. Esito atteso: declassamento a STIMATO o riscrittura sulle tabelle INAIL. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |

### `danno_biologico_macro`

Stima del danno biologico per lesioni da 10 a 100 punti ex art. 138 Cod. Ass. con valori punto indicativi interpolati e coefficiente per fasce decennali d'età, più personalizzazione fino al 30%; non applica la tabella unica nazionale.

- Parametri: `percentuale_invalidita: int (10-100); eta_vittima: int (0-120); personalizzazione_pct: float = 0 (0-30); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: Art. 138 D.Lgs. 209/2005; tabella unica nazionale DPR 13 gennaio 2025 n. 12 non trascritta: valori inclusi indicativi, grado STIMATO
- Casi di prova:
  - 10 punti a 40 anni: primo grado dell'art. 138: `{"percentuale_invalidita": 10, "eta_vittima": 40}` → atteso: da leggere dalla fonte (valore TUN per 10 punti a 40 anni) e dal sito (tabella di Milano); il tool restituisce 32.160 euro (2.680 x 10 x 1,20), stima
  - 20 punti a 30 anni con personalizzazione al tetto del 30%: `{"percentuale_invalidita": 20, "eta_vittima": 30, "personalizzazione_pct": 30}` → atteso: aumento ammesso fino al 30% (art. 138 co. 3); base da leggere dalla fonte e dal sito; il tool dà 132.600 + 39.780 = 172.380 euro
  - 50 punti a 55 anni: `{"percentuale_invalidita": 50, "eta_vittima": 55}` → atteso: da leggere dal sito e dalla TUN; il tool dà 925.000 euro: misurare lo scostamento (sovrastima dichiarata)
  - 100 punti a 20 anni: valore massimo: `{"percentuale_invalidita": 100, "eta_vittima": 20}` → atteso: da leggere dal sito e dalla TUN; il tool dà 10.640.000 euro, scostamento atteso di un ordine di grandezza
  - Personalizzazione al 31%, oltre il tetto: `{"percentuale_invalidita": 20, "eta_vittima": 30, "personalizzazione_pct": 31}` → atteso: errore: l'aumento non può superare il 30% (art. 138 co. 3 Cod. Ass.)

### `danno_biologico_micro`

Danno biologico per lesioni di lieve entità (1-9 punti) ex art. 139 Cod. Ass.: valore del punto (base per coefficiente del grado accertato, ridotto dello 0,5% per ogni anno di età dall'undicesimo) moltiplicato per i punti, inabilità temporanea totale e parziale al 75, 50 e 25%, personalizzazione fino al 20%.

- Parametri: `percentuale_invalidita: int (1-9); eta_vittima: int (0-120); giorni_itt: int = 0; giorni_itp75: int = 0; giorni_itp50: int = 0; giorni_itp25: int = 0; personalizzazione_pct: float = 0 (0-20); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: Art. 139 D.Lgs. 209/2005 (Cod. Ass.); importi del DM MIMIT 20/07/2026 (GU n. 173 del 28/07/2026 secondo il _vintage della tabella), in vigore da aprile 2026: punto base 988,45 euro, inabilità temporanea assoluta 57,64 euro al giorno
- Casi di prova:
  - 9 punti a 10 anni: grado massimo, nessuna riduzione per età: `{"percentuale_invalidita": 9, "eta_vittima": 10}` → atteso: 20.460,92 euro: 988,45 x 2,3 x 9 (art. 139 co. 2 lett. a e co. 6; la riduzione dello 0,5% decorre dall'undicesimo anno). Se il sito arrotonda prima il valore punto a 2.273,44 il totale è 20.460,96: differenza di convenzione da documentare
  - 1 punto a 11 anni con 10 giorni di inabilità assoluta: primo anno di riduzione: `{"percentuale_invalidita": 1, "eta_vittima": 11, "giorni_itt": 10}` → atteso: permanente 983,51 euro (988,45 x 1,0 x 0,995); temporaneo 576,40 (10 x 57,64, art. 139 co. 2 lett. b); totale 1.559,91. A 10 anni il permanente è 988,45 (nessuna riduzione)
  - 5 punti a 30 anni con inabilità parziale al 50% e al 25%; stesso caso con Anno 2025 sul sito: `{"percentuale_invalidita": 5, "eta_vittima": 30, "giorni_itp50": 20, "giorni_itp25": 30}` → atteso: permanente 6.672,04 euro (988,45 x 1,5 x 5 x 0,90); temporaneo 1.008,70 (20 x 28,82 + 30 x 14,41, in proporzione alla percentuale di inabilità, art. 139 co. 2 lett. b); totale 7.680,74. Con la tabella 2025 (963,40) il permanente sarebbe 6.502,95
  - 3 punti a 40 anni, 5 giorni di inabilità assoluta, personalizzazione al tetto del 20%: `{"percentuale_invalidita": 3, "eta_vittima": 40, "giorni_itt": 5, "personalizzazione_pct": 20}` → atteso: permanente 3.024,66 (988,45 x 1,2 x 3 x 0,85); temporaneo 288,20; aumento fino al 20% ex art. 139 co. 3: 604,93 se calcolato sul solo permanente (totale 3.917,79), 662,57 se esteso al temporaneo come fa il tool (totale 3.975,43). Leggere dal sito quale base usa
  - 10 punti: fuori ambito, confine con l'art. 138: `{"percentuale_invalidita": 10, "eta_vittima": 30}` → atteso: errore: dal 10% si applica l'art. 138 Cod. Ass. (tabella unica nazionale), usare danno_biologico_macro

### `danno_non_patrimoniale`

Prospetto del danno non patrimoniale: componente biologica (micropermanenti fino al 9%, stima macro dal 10%), personalizzazioni percentuali per danno morale ed esistenziale, spese mediche e inabilità temporanea totale esposte come danno patrimoniale emergente.

- Parametri: `percentuale_invalidita: int (1-100); eta_vittima: int (0-120); tipo_danno: str = 'biologico' (biologico, morale, esistenziale, patrimoniale_emergente; solo riportato in uscita); giorni_itt: int = 0; spese_mediche: float = 0; danno_morale_pct: float = 0 (0-50); danno_esistenziale_pct: float = 0 (0-50); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: Artt. 138-139 D.Lgs. 209/2005; Tabelle di Milano 2024; Cass. SU 26972/2008 (INDICATIVO)
- Casi di prova:
  - 9 punti a 10 anni: confronto con danno_biologico_micro: `{"percentuale_invalidita": 9, "eta_vittima": 10}` → atteso: componente biologica 20.460,92 euro (988,45 x 2,3 x 9, art. 139 co. 2 lett. a e co. 6); il tool dà 13.937,15 (formula della somma, corretta dall'audit solo nel tool micro): scostamento atteso di 6.523,77
  - 5 punti a 35 anni, 30 giorni di inabilità assoluta, 1.000 euro di spese mediche: `{"percentuale_invalidita": 5, "eta_vittima": 35, "giorni_itt": 30, "spese_mediche": 1000}` → atteso: biologico permanente 6.486,70 (988,45 x 1,5 x 5 x 0,875); biologico temporaneo 1.729,20 (30 x 57,64); danno patrimoniale emergente 1.000; totale 9.215,90. Il tool dà 5.275,85 di biologico e 8.005,05 di totale, con l'inabilità esposta come danno patrimoniale
  - 4 punti a 30 anni con morale ed esistenziale al 50%: `{"percentuale_invalidita": 4, "eta_vittima": 30, "tipo_danno": "morale", "danno_morale_pct": 50, "danno_esistenziale_pct": 50}` → atteso: biologico 4.625,95 (988,45 x 1,3 x 4 x 0,90); aumento massimo del 20% (art. 139 co. 3) pari a 925,19, totale 5.551,14; il tool somma 4.092,18 + 2.046,09 + 2.046,09 = 8.184,37
  - 20 punti a 40 anni con morale al 30%: `{"percentuale_invalidita": 20, "eta_vittima": 40, "danno_morale_pct": 30}` → atteso: biologico dalla TUN per 20 punti a 40 anni, già comprensivo della componente morale (art. 138 co. 2 lett. e), con eventuale personalizzazione fino al 30% (co. 3): da leggere dalla fonte e dal sito; il tool dà 122.400 + 36.720 = 159.120 euro
  - 10 punti a 40 anni con 20 giorni di inabilità assoluta: confine tra 9 e 10: `{"percentuale_invalidita": 10, "eta_vittima": 40, "giorni_itt": 20}` → atteso: biologico permanente dalla TUN (da leggere dalla fonte); inabilità temporanea con i valori dell'art. 138 o del tribunale, non con i 57,64 euro dell'art. 139; il tool dà 32.160 + 1.152,80 = 33.312,80

### `danno_parentale`

Danno da perdita del rapporto parentale per morte del congiunto: importo collocato tra minimo e massimo del range della tabella scelta (Milano o Roma) secondo la posizione indicata in percentuale.

- Parametri: `vittima: str (figlio, genitore, coniuge, fratello, nipote, nonno); superstite: str (stessi valori; coppie ammesse figlio/genitore, genitore/figlio, coniuge/coniuge, fratello/fratello, nipote/nonno, nonno/nipote); tabella: str = 'milano' (milano, roma); personalizzazione_pct: float = 50 (0-100, posizione nel range); accetta_precisione: str \| None = None (INDICATIVO, STIMATO) (aggiunto da @sourced, solo keyword)`
- Fonte normativa dichiarata: Tabelle di Milano e di Roma edizione 2024 (Cass. SU 26972/2008); INDICATIVO: dal 2022 Milano liquida a punti (Cass. 10579/2021), valori di Roma stimati
- Casi di prova:
  - Genitore che perde un figlio, Milano, posizione mediana (default); sul sito vittima di 20 anni, genitore di 50 anni convivente, nessun altro superstite: `{"vittima": "figlio", "superstite": "genitore"}` → atteso: da leggere dal sito; il tool dà 293.327,39 euro (mediana del range 195.551,59-391.103,18): verificare che il valore a punti cada nel range
  - Fratello non convivente, Milano, estremo minimo; sul sito fratelli di 40 e 45 anni non conviventi, con altri congiunti superstiti: `{"vittima": "fratello", "superstite": "fratello", "tabella": "milano", "personalizzazione_pct": 0}` → atteso: da leggere dal sito; il tool dà 28.301,23 euro (minimo del range)
  - Fratello convivente, Milano, estremo massimo; sul sito vittima di 18 anni, fratello di 20 anni convivente, nessun altro superstite: `{"vittima": "fratello", "superstite": "fratello", "tabella": "milano", "personalizzazione_pct": 100}` → atteso: da leggere dal sito; il tool dà 169.830,60 euro (massimo del range)
  - Coniuge, tabella di Roma; sul sito coniugi di 60 anni conviventi: `{"vittima": "coniuge", "superstite": "coniuge", "tabella": "roma"}` → atteso: da leggere dalla pagina del sito sulle tabelle di Roma; il tool dà 285.747,39 euro su valori stimati
  - Coppia non prevista (nonno e fratello): `{"vittima": "nonno", "superstite": "fratello"}` → atteso: errore con l'elenco delle coppie ammesse; annotare sul sito le figure della tabella che il tool non prevede (per esempio convivente o parte dell'unione civile)

### `equo_indennizzo`

Equo indennizzo per infermità da causa di servizio dei dipendenti pubblici (regime previgente): stipendio annuo per coefficiente della categoria della Tabella A DPR 834/1981 per percentuale di invalidità, con indicazione della pensione privilegiata.

- Parametri: `categoria_tabella: str ('1'-'8'; secondo il tool '1' = 81-100%, '8' = 1-10%); percentuale_invalidita: float (0-100); stipendio_annuo: float (euro, non negativo)`
- Fonte normativa dichiarata: Regime PREVIGENTE: DPR 834/1981 Tabella A e DPR 461/2001, per fatti anteriori al 06/12/2011 (art. 6 DL 201/2011 conv. L. 214/2011)
- Casi di prova:
  - Categoria 5, 35%, stipendio 30.000; sul sito età 45 anni, poi 55 per vedere l'eventuale riduzione per età: `{"categoria_tabella": "5", "percentuale_invalidita": 35, "stipendio_annuo": 30000}` → atteso: da leggere dal sito; il tool dà 31.500 euro (30.000 x 3,0 x 0,35)
  - Categoria 1, 90%, stipendio 40.000: massima gravità: `{"categoria_tabella": "1", "percentuale_invalidita": 90, "stipendio_annuo": 40000}` → atteso: da leggere dal sito; il tool dà 288.000 euro (40.000 x 8 x 0,90), oltre sette annualità di stipendio: verificare l'ordine di grandezza
  - Categoria 8, 10%, stipendio 25.000: minima gravità: `{"categoria_tabella": "8", "percentuale_invalidita": 10, "stipendio_annuo": 25000}` → atteso: da leggere dal sito; il tool dà 1.750 euro
  - Categoria 6: confine della pensione privilegiata secondo il tool: `{"categoria_tabella": "6", "percentuale_invalidita": 25, "stipendio_annuo": 28000}` → atteso: da leggere dal sito; il tool dà 17.500 euro e nega la pensione privilegiata (per il tool solo categorie 1-5): da verificare
  - Categoria inesistente: `{"categoria_tabella": "9", "percentuale_invalidita": 10, "stipendio_annuo": 25000}` → atteso: errore: categorie da 1 a 8 della Tabella A DPR 834/1981

### `menomazioni_plurime`

Invalidità complessiva per menomazioni plurime con la formula riduzionistica di Balthazard (100 per 1 meno il prodotto dei residui), con confronto con la somma aritmetica.

- Parametri: `percentuali: list[float] (almeno 2 valori, ciascuno tra 0 e 100)`
- Fonte normativa dichiarata: Formula medico-legale di Balthazard (calcolo riduzionistico), prassi giurisprudenziale; il tool non cita una norma
- Casi di prova:
  - Due menomazioni, 15 e 10: `{"percentuali": [15, 10]}` → atteso: 23,50% (1 - 0,85 x 0,90 = 0,235); somma aritmetica 25
  - Tre menomazioni, 20, 10 e 5: `{"percentuali": [20, 10, 5]}` → atteso: 31,60% (1 - 0,80 x 0,90 x 0,95 = 0,316); somma aritmetica 35
  - Ordine crescente: stesso risultato di [20, 10]: `{"percentuali": [10, 20]}` → atteso: 28,00%: la formula è commutativa
  - Menomazione totale con altra coesistente: valore massimo: `{"percentuali": [100, 50]}` → atteso: 100%: il residuo è nullo, nessuna invalidità ulteriore
  - Micropermanenti plurime: confine tra art. 139 e art. 138: `{"percentuali": [5, 3, 2]}` → atteso: 9,69% (1 - 0,95 x 0,97 x 0,98): resta sotto il 10%, mentre la somma aritmetica (10) porterebbe all'art. 138
  - Una sola percentuale: `{"percentuali": [40]}` → atteso: errore: servono almeno due valori

### `risarcimento_inail`

Stima dell'indennizzo INAIL: inabilità temporanea (60% e 75% della retribuzione giornaliera), danno biologico permanente in capitale tra 6 e 15% e in rendita dal 16% con quota patrimoniale, con coefficienti semplificati non tratti dalle tabelle INAIL.

- Parametri: `retribuzione_annua: float (euro, non negativa); percentuale_invalidita: float (0-100); tipo: str = 'permanente' (permanente, temporanea)`
- Fonte normativa dichiarata: D.Lgs. 38/2000 art. 13; DPR 1124/1965 (testo unico INAIL); tabelle INAIL vigenti (INDICATIVO: coefficienti semplificati)
- Casi di prova:
  - Permanente 5%: franchigia: `{"retribuzione_annua": 30000, "percentuale_invalidita": 5, "tipo": "permanente"}` → atteso: nessun indennizzo: sotto il 6% nessuna prestazione per danno biologico (art. 13 co. 2 lett. a D.Lgs. 38/2000)
  - Permanente 6%: primo grado indennizzato in capitale; sul sito uomo di 40 anni: `{"retribuzione_annua": 30000, "percentuale_invalidita": 6, "tipo": "permanente"}` → atteso: capitale dalla Tabella indennizzo danno biologico per 6 punti, età e sesso, indipendente dalla retribuzione (art. 13 co. 2 lett. a): da leggere dal sito; il tool dà 12.600 euro (42% della retribuzione)
  - Permanente 15%: ultimo grado in capitale; sul sito uomo di 40 anni: `{"retribuzione_annua": 30000, "percentuale_invalidita": 15, "tipo": "permanente"}` → atteso: da leggere dal sito e dalla tabella INAIL; il tool dà 31.500 euro, più della retribuzione annua
  - Permanente 16%: primo grado in rendita: `{"retribuzione_annua": 30000, "percentuale_invalidita": 16, "tipo": "permanente"}` → atteso: rendita con quota biologica tabellare più quota patrimoniale (retribuzione entro il massimale x coefficiente della Tabella dei coefficienti x 16%), art. 13 co. 2 lett. b: da leggere dal sito; il tool dà 1.920 euro annui con quota patrimoniale zero
  - Permanente 50% con retribuzione oltre il massimale: `{"retribuzione_annua": 60000, "percentuale_invalidita": 50, "tipo": "permanente"}` → atteso: quota patrimoniale sulla retribuzione ricondotta al massimale INAIL dell'anno (art. 116 DPR 1124/1965): da leggere dal sito e dal decreto di rivalutazione; il tool usa 60.000 euro e dà 24.240 euro annui
  - Inabilità temporanea: `{"retribuzione_annua": 30000, "percentuale_invalidita": 0, "tipo": "temporanea"}` → atteso: 60% della retribuzione media giornaliera dal quarto giorno al novantesimo, 75% dal novantunesimo (art. 68 DPR 1124/1965); giorno dell'evento a carico del datore per intero, tre giorni di carenza al 60% salvo contratto; il tool dà 49,32 e 61,64 euro al giorno su 30.000/365 e i primi tre giorni al 100%

## rivalutazioni_istat.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `adeguamento_canone_locazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_adeguamento_istat_canone_locazione.php (alta) | Comunicati ISTAT in GU ex art. 81 L. 392/1978 (variazioni annuali e biennali FOI); tabella del sito https://www.avvocatoandreani.it/servizi/variazioni_indici_istat_locazioni.php | Non toccato dall'audit. Dal 2026 usa le variazioni ufficiali in GU per i periodi di 12 e 24 mesi; per periodi che terminano prima del 2026 usa il rapporto non arrotondato degli indici, mentre per l'art. 32 fa fede la variazione pubblicata a un decimale (maggio 2025: +1,4% ufficiale contro 1,4226 del tool): la tabella delle variazioni ufficiali va estesa agli anni precedenti. Da confermare quale mese il sito prende come riferimento (spesso quello precedente la decorrenza) e passare al tool gli stessi mesi. Da precisare nel docstring: il limite del 75% vale per gli usi diversi di durata non superiore a quella dell'art. 27 L. 392/1978 e per i concordati (art. 2 co. 3 L. 431/1998, DM 16/01/2017); per i contratti liberi vale il contratto; con la cedolare secca l'aggiornamento e' sospeso (art. 3 co. 11 D.Lgs. 23/2011). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_devalutazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_devalutazione_monetaria.php (alta) | ISTAT, Rivaluta (coefficiente inverso per la stessa coppia di mesi) | Non toccato dall'audit. Il coefficiente deve essere il reciproco esatto di quello di rivalutazione per la stessa coppia di mesi. Il sito copre dal 1947, il tool dal 1990 (errore sotto quella data): scostamento di copertura da registrare, non di calcolo. Anche qui pesa la serie FOI 2011-2013 da riscontrare. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_inflazione` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-inflazione.php (alta) | ISTAT, Rivaluta; comunicati FOI in GU ex art. 81 L. 392/1978 | Non toccato dall'audit. Il tool calcola sulla serie raccordata e, solo per coppie di 12 o 24 mesi che terminano dal gennaio 2026, espone la variazione ufficiale in GU (variazione_ufficiale_pct); per periodi precedenti non espone la variazione ufficiale arrotondata a un decimale. La media annua usa anni di 365,25 giorni: convenzione da confrontare col sito. Il caso dicembre 2013-dicembre 2023 misura l'errore della serie FOI 2011-2013 (tool 18,07% contro 18,90%). Da confermare mesi e base usati dal sito. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `inflazione_titoli_stato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/grafico-andamento-inflazione-titoli-di-stato.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-inflazione.php | ISTAT, Rivaluta per la variazione FOI del periodo; equazione di Fisher verificata a mano | Non toccato dall'audit. Il sito non ha un calcolatore del rendimento reale (https://www.avvocatoandreani.it/servizi/grafico-andamento-inflazione-titoli-di-stato.php e' un grafico): con calcolo-inflazione.php si confronta solo la componente inflazione; montante nominale e rendimento reale si verificano a mano. Il rendimento e' lordo: l'imposta del 12,5% (D.Lgs. 239/1996) non e' sottratta, quindi il rendimento reale netto e' sovrastimato, da dichiarare nel docstring. Durata in anni di 365,25 giorni. Fase 0: pagina dedicata all'andamento di inflazione e rendimento dei titoli di Stato. |
| `interessi_vari_capitale_rivalutato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-interessi-vari-capitale-rivalutato.php (alta) | ISTAT, Rivaluta per il coefficiente; DM MEF per i tassi legali | Non toccato dall'audit. Il sito offre tasso fisso, legale e moratorio con capitalizzazione; il tool solo tasso fisso o legale senza capitalizzazione: confrontare solo le opzioni comuni e registrare le altre come non coperte. Con tasso_personalizzato null deve coincidere al centesimo con rivalutazione_monetaria con interessi (oggi coincide). Difetti da confermare: l'ultimo anno perde il 1 gennaio (364 giorni per 1/1-31/12) e negli anni bisestili il divisore e' 366; nessun controllo che il tasso personalizzato rispetti la forma scritta dell'art. 1284 co. 3 c.c. e la soglia d'usura. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `lettera_adeguamento_canone` | documento | andreani | https://www.avvocatoandreani.it/servizi/lettera-adeguamento-canone-locazione.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo_adeguamento_istat_canone_locazione.php | Comunicati ISTAT in GU ex art. 81 L. 392/1978 | Non toccato dall'audit. Il sito genera la stessa lettera col nuovo canone mensile: si confronta il canone e si verificano i riferimenti del testo (controllo strutturale). Il testo cita l'art. 1 L. 431/1998, che riguarda l'ambito di applicazione: il riferimento pertinente e' l'art. 2 co. 3 L. 431/1998 con il DM 16/01/2017 per i concordati (per i liberi il contratto). Mancano l'avvertenza sulla cedolare secca (art. 3 co. 11 D.Lgs. 23/2011, aggiornamento sospeso per la durata dell'opzione) e il richiamo alla richiesta del locatore come presupposto (art. 32 co. 1 L. 392/1978). Con indice non ancora pubblicato la lettera riporta in coda l'avvertenza INDICATIVO: comportamento da mantenere. Fase 0: pagina confermata dal crawl. |
| `rivalutazione_annuale_media` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php (alta) | ISTAT, medie annue FOI senza tabacchi (I.Stat) | Non toccato dall'audit. Il sito definisce la variazione annuale media come rapporto tra la media aritmetica gennaio-dicembre e quella dell'anno precedente: il prodotto delle variazioni coincide col rapporto diretto tra medie usato dal tool, salvo arrotondamenti intermedi del sito da verificare; va chiarito se il sito include la variazione dell'anno di partenza. Il mese e' ignorato per costruzione; lo stesso anno da' coefficiente 1. Anni 2011-2013 da riscontrare per la serie. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rivalutazione_mensile` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/rivalutazione_mensile_assegni_importi_dovuti.php (alta) | ISTAT, Rivaluta (coefficienti FOI mese per mese) | Non toccato dall'audit. La pagina del sito calcola rivalutazione e interessi legali su ogni mensilita': si confronta solo la quota di rivalutazione (il tool non calcola interessi, quindi per arretrati di mantenimento non restituisce il credito complessivo e il docstring dovrebbe dirlo). Da confermare la convenzione del sito sull'indice di ogni rata (mese della scadenza nel tool, ultima rata con coefficiente 1) e sul trattamento dei mesi non ancora pubblicati (il tool li sostituisce con agosto 2026 e lo segnala). Per rate negli anni 2011-2013 pesa l'errore della serie FOI descritto in rivalutazione_monetaria. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rivalutazione_monetaria` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/interessi_rivalutazione.php (alta) | ISTAT, Rivaluta e I.Stat (FOI senza tabacchi; raccordo base 2010-2015 pari a 1,071 e base 2025-2015 pari a 1,214); DM MEF sui tassi legali | Non toccato dall'audit di settembre 2026 (ne' par. 5 ne' par. 7). Il sito ha la modalita' con interessi (questa pagina) e quella di sola rivalutazione (https://www.avvocatoandreani.it/servizi/interessi_rivalutazione.php?op=3); accetta date dal 01/01/1947 all'ultimo mese pubblicato (agosto 2026), il tool dal 1990. Il benchmark deve confermare: (1) la serie FOI 2011-2013 della tabella, che non coincide con i valori ufficiali (dicembre 2011, 2012 e 2013 in base 2010: 104,0; 106,5; 107,1, da dividere per 1,071, contro 99,5; 101,0; 100,7 in tabella), errore che si propaga a tutti i tool FOI; (2) il conteggio dei giorni nel ramo con interessi: l'ultimo anno perde il 1 gennaio (364 giorni per 1/1-31/12) e gli anni bisestili usano 366, mentre interessi_legali usa sempre 365; (3) su quale capitale rivalutato il sito calcola gli interessi di ciascun anno (il tool usa l'indice di dicembre dell'anno) e se arrotonda il coefficiente a tre decimali come ISTAT. Il default con_interessi_legali=True espone al doppio conteggio con interessi_legali segnalato in docs/_audit/REPORT.md. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rivalutazione_storica` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/rivalutazione-monetaria-storica.php (alta) | ISTAT, Il valore della moneta in Italia (coefficienti annui per tradurre valori monetari dei periodi passati) e medie annue FOI su I.Stat | Non toccato dall'audit. La pagina del sito lavora su anni dal 1861 al 2026 con importi in lire o euro (conversione 1.936,27); il tool usa solo anni dal 1990, in euro, sulla media annua FOI: confrontare solo anni dal 1990. Da confermare se sito e ISTAT usano medie annue arrotondate a un decimale: per 2015-2023 il tool da' 1,18662, con medie arrotondate 1,187. L'anno in corso e' una media parziale segnalata in avvertenza. Gli anni 2011-2013 risentono dell'errore della serie. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `rivalutazione_tfr` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-tfr.php | ISTAT, coefficienti mensili di rivalutazione del TFR (anche https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php) | Voce aperta del par. 7 dell'audit (imposta sostitutiva all'11% prima del 2015, confidenza alta, non modificato): il tool applica il 17% a tutte le rivalutazioni, mentre il 17% vale dal 01/01/2015 (art. 1 co. 623 L. 190/2014; prima 11%, art. 11 co. 3 D.Lgs. 47/2000). Il controllo ha trovato inoltre: coefficienti 2021-2023 identici a quelli ISTAT (4,359238; 9,974576; 1,944162), ma 2012-2015 diversi (tool 2,63; 1,28; 0,90; 1,58 contro 3,302885; 1,922535; 1,500000; 1,500000) per la serie FOI e perche' con indice in calo la parte variabile deve essere zero (art. 2120 co. 4: 75% dell'aumento), non negativa. Il tool ignora la riduzione dello 0,50% della quota (art. 3 L. 297/1982) e le frazioni d'anno (art. 2120 co. 1 e 5): il confronto col sito va fatto su anni interi. Fase 0: il sito pubblica il coefficiente di rivalutazione del TFR (art. 2120 c.c.) in una pagina dedicata. |
| `variazioni_istat` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/variazioni_indici_istat_rivalutazione.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/variazioni_indici_istat_locazioni.php, https://www.avvocatoandreani.it/servizi/valore-ultimo-indice-istat.php | ISTAT, variazioni medie annue FOI senza tabacchi (comunicati annuali e I.Stat) | Non toccato dall'audit. ISTAT calcola le variazioni medie annue sulle medie arrotondate a un decimale: per il 2022 la variazione ufficiale FOI e' +8,1%, il tool da' 8,01 sulle medie non arrotondate. La tabella 2011-2015 del tool (2,17; 0,24; -0,55; -0,42) si discosta dalle variazioni ufficiali per l'errore della serie FOI. Da confermare quale tabella del sito espone le variazioni medie annue (in alternativa https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php). Se anno_inizio e' fuori serie il primo anno disponibile mostra 0,0 invece di null. Fase 0: pagina confermata; il sito pubblica anche le variazioni annuali e biennali e l'ultimo indice. |

### `adeguamento_canone_locazione`

Aggiornamento ISTAT del canone annuo di locazione con una percentuale della variazione FOI; per i periodi di 12 o 24 mesi che terminano dal 2026 usa la variazione ufficiale in GU.

- Parametri: `canone_annuo: float, data_stipula: str (YYYY-MM-DD), data_adeguamento: str (YYYY-MM-DD), percentuale_istat: float = 75.0 (0-100)`
- Fonte normativa dichiarata: L. 392/1978 art. 32; L. 431/1998; indici FOI ISTAT raccordati (coefficiente 1,214 dal 2026)
- Casi di prova:
  - Dodici mesi con variazione ufficiale in GU, 75%: `{"canone_annuo": 12000, "data_stipula": "2025-05-01", "data_adeguamento": "2026-05-01", "percentuale_istat": 75}` → atteso: Variazione ufficiale maggio 2026 su maggio 2025 +3,0% (GU n. 144 del 24/06/2026); 75% = 2,25%; canone annuo 12.270,00 (art. 32 L. 392/1978).
  - Ventiquattro mesi, 100%: `{"canone_annuo": 12000, "data_stipula": "2024-06-01", "data_adeguamento": "2026-06-01", "percentuale_istat": 100}` → atteso: Variazione biennale ufficiale giugno 2026 +4,4% (GU n. 201 del 31/08/2026); canone annuo 12.528,00.
  - Dodici mesi terminati prima del 2026 (arrotondamento ufficiale): `{"canone_annuo": 12000, "data_stipula": "2024-05-01", "data_adeguamento": "2025-05-01", "percentuale_istat": 75}` → atteso: Variazione ufficiale maggio 2025 +1,4% (comunicato ISTAT ex art. 81 L. 392/1978); 75% = 1,05%; canone 12.126,00. Il tool usa 1,4226% e restituisce 12.128,03.
  - Dodici mesi con comunicato non ancora in GU: `{"canone_annuo": 9600, "data_stipula": "2025-08-01", "data_adeguamento": "2026-08-01", "percentuale_istat": 75}` → atteso: Variazione agosto 2026 +3,4% (ISTAT 16/09/2026); 75% = 2,55%; canone 9.844,80 con nota di comunicato in attesa di pubblicazione in GU.
  - Periodo di 15 mesi a cavallo del ribasamento: `{"canone_annuo": 12000, "data_stipula": "2025-03-01", "data_adeguamento": "2026-06-01", "percentuale_istat": 75}` → atteso: Variazione calcolata 124,8/121,4 - 1 = 2,80%; 75% = 2,10%; canone 12.252,06 con nota di scarto fino a 0,1 punti; da leggere dal sito.
  - Percentuale oltre il massimo: `{"canone_annuo": 12000, "data_stipula": "2025-05-01", "data_adeguamento": "2026-05-01", "percentuale_istat": 100.5}` → atteso: Errore: percentuale_istat deve essere compresa tra 0 e 100.

### `calcolo_devalutazione`

Calcolo inverso della rivalutazione: riconduce un importo attuale al suo valore in una data passata con gli indici FOI.

- Parametri: `importo_attuale: float, data_attuale: str (YYYY-MM-DD), data_passata: str (YYYY-MM-DD, anteriore a data_attuale)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Devalutazione dal 2023 al tratto sospetto del 2013: `{"importo_attuale": 10000, "data_attuale": "2023-12-01", "data_passata": "2013-12-01"}` → atteso: 8.410,43 = 10.000 / 1,189 (coefficiente ISTAT dic. 2013-dic. 2023); il tool oggi restituisce 8.469,30.
  - A cavallo del ribasamento 2025=100: `{"importo_attuale": 10000, "data_attuale": "2026-08-01", "data_passata": "2025-08-01"}` → atteso: 9.674,34 = 10.000 x 121,8 / 125,9 sulla serie raccordata; da leggere dal sito (scarto ammesso fino a 0,1 punti).
  - Data passata fuori serie (prima del 1990): `{"importo_attuale": 1000, "data_attuale": "2026-01-01", "data_passata": "1985-06-01"}` → atteso: Il tool risponde con errore (serie dal 1990); il sito restituisce un valore da leggere: scostamento di copertura.

### `calcolo_inflazione`

Variazione percentuale FOI tra due date con coefficiente di rivalutazione e inflazione media annua; per coppie di 12 o 24 mesi che terminano dal 2026 espone anche la variazione ufficiale in GU.

- Parametri: `data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Periodo decennale che parte dal tratto sospetto della serie: `{"data_inizio": "2013-12-01", "data_fine": "2023-12-01"}` → atteso: +18,90% (coefficiente ISTAT 1,189 = 118,9 x 1,071 / 107,1); il tool oggi restituisce 18,07 per l'indice di dicembre 2013 in tabella (100,7).
  - Dodici mesi a cavallo del ribasamento, comunicato non ancora in GU: `{"data_inizio": "2025-08-01", "data_fine": "2026-08-01"}` → atteso: Variazione ufficiale +3,4% (ISTAT 16/09/2026, comunicato in GU non ancora pubblicato) nel campo variazione_ufficiale_pct; variazione calcolata sulla serie raccordata 3,37 con nota di raccordo.
  - Ventiquattro mesi con variazione biennale ufficiale: `{"data_inizio": "2024-06-01", "data_fine": "2026-06-01"}` → atteso: Variazione biennale ufficiale +4,4% (GU n. 201 del 31/08/2026); variazione calcolata 4,44; inflazione media annua 2,20.
  - Data iniziale fuori serie (prima del 1990): `{"data_inizio": "1989-12-01", "data_fine": "1991-01-01"}` → atteso: Dicembre 1989 fuori serie: il tool usa gennaio 1990 con avvertenza INDICATIVO (6,16%); il sito, con serie dal 1947, restituisce il valore esatto da leggere.

### `inflazione_titoli_stato`

Confronta un rendimento lordo annuo con l'inflazione FOI del periodo e calcola il rendimento reale con l'equazione di Fisher.

- Parametri: `capitale_investito: float, rendimento_lordo_annuo_pct: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Biennio ad alta inflazione (reale negativo): `{"capitale_investito": 10000, "rendimento_lordo_annuo_pct": 3.5, "data_inizio": "2021-01-01", "data_fine": "2023-01-01"}` → atteso: Inflazione FOI 118,3/102,9 - 1 = 14,97% (da confrontare con calcolo-inflazione.php), media annua 7,23%; rendimento reale di Fisher 1,035/1,0723 - 1 = -3,48%; potere d'acquisto non preservato.
  - Biennio a bassa inflazione (reale positivo): `{"capitale_investito": 10000, "rendimento_lordo_annuo_pct": 3.0, "data_inizio": "2024-01-01", "data_fine": "2026-01-01"}` → atteso: Inflazione 121,9/119,3 - 1 = 2,18%, media annua 1,08%; montante nominale 10.609,43; rendimento reale 1,90%.
  - Rendimento pari all'inflazione media (soglia): `{"capitale_investito": 10000, "rendimento_lordo_annuo_pct": 1.08, "data_inizio": "2024-01-01", "data_fine": "2026-01-01"}` → atteso: Reale circa zero; il tool mostra -0,0 e potere_acquisto_preservato false per differenze oltre il secondo decimale: caso di soglia da documentare.

### `interessi_vari_capitale_rivalutato`

Rivaluta un capitale con gli indici FOI e calcola interessi anno per anno sul capitale rivalutato a tasso personalizzato o legale.

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD), tasso_personalizzato: float \| None = None (se None tasso legale vigente per anno)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Coerenza con rivalutazione_monetaria (tasso legale): `{"capitale": 10000, "data_inizio": "2019-03-10", "data_fine": "2023-03-10", "tasso_personalizzato": null}` → atteso: Identico a rivalutazione_monetaria con interessi: totale interessi 324,57, totale dovuto 11.938,74 (valori attuali di entrambi i tool); sul sito opzione interessi legali, da leggere.
  - Tasso fisso personalizzato 3,5%: `{"capitale": 10000, "data_inizio": "2019-03-10", "data_fine": "2023-03-10", "tasso_personalizzato": 3.5}` → atteso: Da leggere dal sito con tasso fisso 3,5% senza capitalizzazione; il tool restituisce interessi 1.485,01 e totale 13.099,18.
  - Anno intero per rilevare il giorno perso nell'ultimo anno: `{"capitale": 10000, "data_inizio": "2024-12-31", "data_fine": "2025-12-31", "tasso_personalizzato": 5}` → atteso: Interessi 2025 su 365 giorni (dies a quo escluso): 10.108,15 x 5% = 505,41; il tool conta 364 giorni e restituisce 504,02.

### `lettera_adeguamento_canone`

Genera la lettera di comunicazione dell'adeguamento ISTAT del canone mensile con dati di calcolo e riferimenti normativi.

- Parametri: `locatore: str, conduttore: str, indirizzo_immobile: str, canone_attuale: float (mensile), data_stipula: str (YYYY-MM-DD), data_adeguamento: str (YYYY-MM-DD), percentuale_istat: float = 75.0 (0-100)`
- Fonte normativa dichiarata: L. 392/1978 art. 32; L. 431/1998; indici FOI ISTAT raccordati (coefficiente 1,214 dal 2026)
- Casi di prova:
  - Dodici mesi con variazione ufficiale, 75%: `{"locatore": "Mario Rossi", "conduttore": "Luca Bianchi", "indirizzo_immobile": "Via Roma 1, 20121 Milano", "canone_attuale": 1000, "data_stipula": "2025-05-01", "data_adeguamento": "2026-05-01", "percentuale_istat": 75}` → atteso: canone_nuovo 1.022,50 (+3,0% al 75%). Il testo deve citare l'art. 32 L. 392/1978, l'indice FOI e la fonte GU Serie Generale n. 144 del 24-06-2026 (comunicato ISTAT 26A03169) ex art. 81 L. 392/1978.
  - Ventiquattro mesi al 100%: riferimenti obbligatori: `{"locatore": "Anna Verdi", "conduttore": "Paolo Neri", "indirizzo_immobile": "Corso Italia 10, 10121 Torino", "canone_attuale": 750, "data_stipula": "2024-06-01", "data_adeguamento": "2026-06-01", "percentuale_istat": 100}` → atteso: canone_nuovo 783,00 (+4,4%, GU n. 201 del 31/08/2026, comunicato 26A04494). Riferimenti che il testo deve contenere: art. 32 L. 392/1978; comunicato ISTAT in GU ex art. 81; richiamo corretto alla L. 431/1998 (art. 2 co. 3, oggi cita l'art. 1); avvertenza sulla cedolare secca (art. 3 co. 11 D.Lgs. 23/2011), oggi assente.
  - Indice di adeguamento non ancora pubblicato: `{"locatore": "Mario Rossi", "conduttore": "Luca Bianchi", "indirizzo_immobile": "Via Roma 1, 20121 Milano", "canone_attuale": 850, "data_stipula": "2025-12-01", "data_adeguamento": "2026-12-01", "percentuale_istat": 100}` → atteso: Dicembre 2026 non pubblicato: la lettera deve riportare in coda l'avvertenza INDICATIVO (presente); il nuovo canone 880,78 e' una stima da non inviare.

### `rivalutazione_annuale_media`

Rivaluta un importo tra due date usando solo l'anno, come rapporto tra le medie annue FOI.

- Parametri: `importo: float, data_inizio: str (YYYY-MM-DD, conta solo l'anno), data_fine: str (YYYY-MM-DD, conta solo l'anno)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990
- Casi di prova:
  - Anni diversi, mesi ignorati: `{"importo": 10000, "data_inizio": "2015-06-15", "data_fine": "2023-03-10"}` → atteso: Rapporto tra medie annue 2023 e 2015: 1,18662 (11.866,20) nel tool; da leggere dal sito, che concatena le variazioni annue medie.
  - Stesso anno (valore minimo): `{"importo": 10000, "data_inizio": "2024-01-10", "data_fine": "2024-11-30"}` → atteso: Coefficiente 1, importo invariato 10.000,00.
  - Anno finale parziale: `{"importo": 10000, "data_inizio": "2025-01-01", "data_fine": "2026-08-31"}` → atteso: Media 2026 parziale (8 mesi): 10.222,08 con avvertenza INDICATIVO; da leggere dal sito se accetta l'anno in corso.

### `rivalutazione_mensile`

Rivaluta ogni mensilita' di un importo ricorrente (assegni di mantenimento, canoni) dal proprio mese fino alla data finale con gli indici FOI.

- Parametri: `importo_mensile: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Dodici mensilita' nel 2022 (anno ad alta inflazione): `{"importo_mensile": 1000, "data_inizio": "2022-01-01", "data_fine": "2022-12-31"}` → atteso: 12 mensilita', totale rivalutato 12.611,11 = somma di 1.000 x 118,2 / FOI del mese (indici 2022 della tabella, coerenti col coefficiente TFR ufficiale 2022; da riscontrare su Rivaluta); quota di rivalutazione del sito da leggere.
  - Mensilita' a cavallo del ribasamento 2025=100: `{"importo_mensile": 500, "data_inizio": "2025-09-01", "data_fine": "2026-08-31"}` → atteso: 12 mensilita', totale 6.131,74 sulla serie raccordata (coefficiente 1,214); da leggere dal sito.
  - Una sola mensilita' (valore minimo): `{"importo_mensile": 800, "data_inizio": "2026-03-01", "data_fine": "2026-03-31"}` → atteso: 1 mensilita', coefficiente 1, differenza 0,00.
  - Data finale oltre l'ultimo indice pubblicato: `{"importo_mensile": 1000, "data_inizio": "2026-01-01", "data_fine": "2026-12-31"}` → atteso: Mesi da settembre a dicembre 2026 non pubblicati: avvertenza INDICATIVO obbligatoria (il tool usa agosto 2026, totale 12.117,76); il sito non accetta la data.

### `rivalutazione_monetaria`

Rivaluta un capitale con gli indici FOI ISTAT tra due date, con o senza interessi legali anno per anno sul capitale rivalutato (criterio Cass. SU 1712/1995).

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD), con_interessi_legali: bool = True`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato; art. 1284 c.c. per gli interessi
- Casi di prova:
  - Solo rivalutazione, periodo pluriennale interno alla serie (pagina op=3): `{"capitale": 10000, "data_inizio": "2015-01-15", "data_fine": "2023-12-15", "con_interessi_legali": false}` → atteso: Da leggere dal sito. Il tool applica FOI dic. 2023 / gen. 2015 = 118,9/99,7 = 1,192578 e restituisce 11.925,78; se sito o ISTAT usano il coefficiente arrotondato a tre decimali (1,193) il risultato e' 11.930,00.
  - Partenza nel tratto sospetto della serie FOI (dicembre 2013): `{"capitale": 10000, "data_inizio": "2013-12-01", "data_fine": "2023-12-01", "con_interessi_legali": false}` → atteso: 11.890,00: coefficiente ISTAT 1,189 = 118,9 x 1,071 / 107,1 (FOI dic. 2023 in base 2015; FOI dic. 2013 in base 2010 = 107,1; raccordo 1,071). Oggi il tool restituisce 11.807,35 perche' la tabella riporta dic. 2013 = 100,7.
  - Con interessi legali su un anno intero (conteggio dei giorni dell'ultimo anno): `{"capitale": 10000, "data_inizio": "2024-12-31", "data_fine": "2025-12-31", "con_interessi_legali": true}` → atteso: Capitale rivalutato 10.108,15 (121,5/120,2); interessi 2025 al 2,0% (art. 1284 c.c., DM MEF di dicembre 2024) su 365 giorni = 202,16, totale 10.310,31. Il tool conta 364 giorni e restituisce 201,61; il criterio del sito sul capitale su cui calcolare gli interessi e' da leggere.
  - A cavallo del ribasamento ISTAT 2025=100: `{"capitale": 10000, "data_inizio": "2025-08-01", "data_fine": "2026-08-31", "con_interessi_legali": false}` → atteso: 10.336,62 sulla serie raccordata (125,9/121,8; coefficiente 1,214, GU n. 144 del 24/06/2026); variazione ufficiale agosto 2026 su agosto 2025 +3,4% (ISTAT 16/09/2026): scarto ammesso rispetto al sito fino a 0,1 punti.
  - Data finale oltre l'ultimo indice pubblicato (valore massimo): `{"capitale": 10000, "data_inizio": "2025-12-01", "data_fine": "2026-12-31", "con_interessi_legali": false}` → atteso: Il tool deve usare agosto 2026 al posto di dicembre 2026 e dichiararlo in avvertenza come INDICATIVO (10.362,14); il sito non accetta date oltre l'ultimo mese pubblicato.

### `rivalutazione_storica`

Rivaluta un importo tra due anni sulla media annua degli indici FOI, senza indicare il mese.

- Parametri: `importo: float, anno_partenza: int, anno_arrivo: int (successivo ad anno_partenza; serie dal 1990)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990
- Casi di prova:
  - Anni completi interni alla serie: `{"importo": 10000, "anno_partenza": 2015, "anno_arrivo": 2023}` → atteso: Media 2023 / media 2015: il tool 1,18662 (11.866,20); con medie arrotondate a un decimale 118,7/100,0 = 1,187 (11.870,00). Da leggere dal sito e dai coefficienti ISTAT.
  - Anno di arrivo parziale (2026, otto mesi): `{"importo": 10000, "anno_partenza": 2020, "anno_arrivo": 2026}` → atteso: Media 2026 parziale su 8 mesi: avvertenza INDICATIVO obbligatoria (12.125,81); da leggere dal sito come tratta l'anno in corso.
  - Anno di partenza fuori serie: `{"importo": 1000, "anno_partenza": 1985, "anno_arrivo": 2025}` → atteso: Errore del tool (anno fuori serie); il sito copre dal 1861: scostamento di copertura, non di calcolo.

### `rivalutazione_tfr`

Calcola il TFR con quota annua pari alla retribuzione divisa per 13,5 e rivalutazione annua 1,5% piu' 75% della variazione FOI dicembre su dicembre, con imposta sostitutiva sulle rivalutazioni.

- Parametri: `retribuzione_annua: float, anni_servizio: int (maggiore di 0), anno_cessazione: int`
- Fonte normativa dichiarata: Art. 2120 c.c.; indici FOI ISTAT raccordati (coefficiente 1,214 dal 2026); variazione dicembre su dicembre ufficiale in GU se pubblicata
- Casi di prova:
  - Tre anni recenti con coefficienti ufficiali noti: `{"retribuzione_annua": 27000, "anni_servizio": 3, "anno_cessazione": 2024}` → atteso: Quote 2.000 (27.000/13,5, art. 2120 co. 1 c.c.); rivalutazioni coi coefficienti ISTAT 2022 (9,974576%) e 2023 (1,944162%): 199,49 e 81,65; TFR lordo 6.281,14; imposta 17% = 47,79. Con la riduzione dello 0,50% (quota 1.865) il lordo e' 5.857,16.
  - Anni 2011-2015: serie FOI, indice in calo e aliquota 11%: `{"retribuzione_annua": 27000, "anni_servizio": 5, "anno_cessazione": 2016}` → atteso: Coefficienti ISTAT 2012 3,302885, 2013 1,922535, 2014 1,500000 (indice in calo: parte variabile zero) e 2015 1,500000: rivalutazioni 359,94, TFR lordo 10.359,94; imposta 11% sulle rivalutazioni fino al 2014 e 17% sul 2015 = 47,01. Oggi il tool restituisce 10.288,09 e 48,97.
  - Rapporto lungo a cavallo del 2015 (aliquota): `{"retribuzione_annua": 30000, "anni_servizio": 12, "anno_cessazione": 2016}` → atteso: Imposta sostitutiva 11% sulle rivalutazioni 2005-2014 e 17% su quella 2015 (art. 1 co. 623 L. 190/2014); il tool applica il 17% a tutte (555,31). Coefficienti annui da leggere dalla fonte ISTAT.
  - Coefficiente di dicembre non ancora pubblicato: `{"retribuzione_annua": 30000, "anni_servizio": 2, "anno_cessazione": 2027}` → atteso: Dicembre 2026 non pubblicato: il tool usa agosto 2026 (variazione 3,62%) e deve segnalarlo come INDICATIVO; valore ufficiale ISTAT atteso a gennaio 2027.

### `variazioni_istat`

Tabella delle medie annue FOI e delle variazioni percentuali annue per un periodo, con variazione cumulata.

- Parametri: `anno_inizio: int, anno_fine: int (successivo ad anno_inizio)`
- Fonte normativa dichiarata: Indici FOI ISTAT base 2015=100 raccordata (dal 2026 base 2025=100, coefficiente 1,214), dal 1990 all'ultimo mese pubblicato
- Casi di prova:
  - Anni 2021-2024 (convenzione di arrotondamento ISTAT): `{"anno_inizio": 2021, "anno_fine": 2024}` → atteso: Variazioni medie annue ufficiali FOI senza tabacchi: 2022 +8,1%, 2023 +5,4%, 2024 +0,8% (medie arrotondate 104,2; 112,6; 118,7; 119,7), da riscontrare su I.Stat; il tool restituisce 8,01; 5,43; 0,88.
  - Anni 2011-2015 (tratto sospetto della serie): `{"anno_inizio": 2011, "anno_fine": 2015}` → atteso: Variazioni ufficiali 2012 +3,0%, 2013 +1,1%, 2014 +0,2%, 2015 -0,1% (da riscontrare su I.Stat); il tool restituisce 2,17; 0,24; -0,55; -0,42.
  - Ultimo anno parziale: `{"anno_inizio": 2024, "anno_fine": 2026}` → atteso: Riga 2026 con mesi_disponibili 8 e nota di media parziale; variazione_cumulata_parziale true; nessun confronto numerico sull'anno parziale.
  - Anno iniziale fuori serie: `{"anno_inizio": 1989, "anno_fine": 1992}` → atteso: La variazione del 1990 deve risultare non disponibile (null), il tool mostra 0,0; variazione cumulata null.

## scadenze_termini.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `scadenza_processuale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_scadenze_termini_udienze.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php | Normattiva: art. 155 c.p.c., art. 1 L. 742/1969, L. 260/1949 come modificata dalla L. 151/2025 (festività del 4 ottobre dal 2026) | Audit settembre 2026: corretto al par. 4.1 (sospensione feriale contata giorno per giorno; parametro sospensione_feriale con default False perché il tool serve anche per termini sostanziali); non compare nei par. 5 e 7. Il benchmark deve confermare i casi della tabella del par. 4.1 (20/07 + 30 giorni = 19/09; dies a quo 10/08 + 30 giorni = 30/09) e il calendario festivo, compreso il 4 ottobre dal 2026. Punti di attenzione: il tool proroga sempre il sabato (art. 155 co. 5 c.p.c.) anche quando è usato per un termine sostanziale, dove vale solo la proroga festiva dell'art. 2963 c.c.; secondo la sua descrizione la pagina del sito considera festivi domeniche e festività nazionali (verificare il sabato) e applica da sola la sospensione emergenziale del 2020 (art. 83 DL 18/2020), che il tool non modella: evitare date del 2020 o registrarle come differenza di convenzione. La pagina https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php offre anche il termine libero e i termini a mesi, senza corrispondente nel tool. Nessun test esistente in tests/comparison. Fase 0: pagina confermata; la pagina dei termini processuali a giorni e mesi (dies a quo, termine libero, prima/dopo, sospensione feriale) e' il secondo benchmark. |
| `scadenze_impugnazioni` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/termini-impugnazioni-civile-amministrativo-tributario.php (alta) | Normattiva: artt. 325, 326, 327 e 47 c.p.c.; art. 1 L. 742/1969 | Audit settembre 2026: corretto ai par. 4.1 (prima non applicava affatto la sospensione feriale: un termine lungo da giugno scadeva a dicembre invece che a gennaio; ora default True e 31 giorni in più per ogni agosto compreso nel termine a mesi) e 4.5 (regolamento di competenza senza termine lungo, art. 47 co. 2); non compare nei par. 5 e 7. Il benchmark deve confermare il conteggio giorno per giorno sui termini brevi, lo slittamento di 31 giorni sul termine lungo e la convenzione per la pubblicazione in agosto: il tool fa decorrere i sei mesi dal 31 agosto (lettura prudenziale), la lettura che parte dal 1° settembre sposta la scadenza di un giorno; riportare entrambe le date senza modificare i valori verificati a mano in tests/unit/test_scadenze_termini.py. Il sito copre anche il processo amministrativo e tributario, che il tool non gestisce. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `scadenze_multe` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/ricorso-pagamento-multa.php (alta) | Normattiva: artt. 202, 203 e 204-bis D.Lgs. 285/1992 vigenti (dopo la L. 177/2024); art. 7 D.Lgs. 150/2011 | Audit settembre 2026: corretto al par. 4.5 (sconto del 30% attribuito all'art. 20 DL 69/2013 conv. L. 98/2013 e non alla L. 120/2010); non compare nei par. 5 e 7. Il tool non applica la sospensione feriale a nessuna opzione: per il ricorso al giudice di pace fonti secondarie riportano l'orientamento della Cassazione che la ritiene applicabile (l'esclusione dell'art. 3 L. 742/1969 riguarda la materia del lavoro, non il rito), quindi un termine che attraversa agosto va confermato sul sito e sulla fonte primaria come possibile scostamento. Il tool proroga al lunedì anche le scadenze di pagamento che cadono di sabato: per un termine non processuale il sabato non è festivo (art. 2963 co. 3 c.c.). Manca l'opzione dei 60 giorni per il ricorrente residente all'estero (art. 7 D.Lgs. 150/2011). Verificare con cite_law gli artt. 202, 203 e 204-bis del Codice della strada dopo la L. 177/2024. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `termini_183_190_cpc` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-memorie-183-comparse-190.php (alta) | Normattiva, multivigenza: artt. 183 e 190 c.p.c. nella versione anteriore al 28/02/2023; art. 35 D.Lgs. 149/2022 | Audit settembre 2026: marcato Regime: PREVIGENTE (par. 3, cause iscritte a ruolo prima del 28/02/2023) e corretto al par. 4.1 (sospensione feriale); non compare nei par. 5 e 7. Il benchmark deve confermare che ogni risposta contiene il blocco regime_normativo con i tool vigenti termini_memorie_repliche e termini_processuali_civili. Il tool conta ogni termine dall'udienza: verificare come il sito tratta i termini successivi quando il precedente è prorogato ex art. 155 (le memorie dell'art. 183 co. 6 sono termini ulteriori di 30 e 20 giorni; la replica dell'art. 190 cade nei 20 giorni successivi alla conclusionale). La pagina del sito dichiara a sua volta i termini abrogati per i procedimenti dal 28/02/2023. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `termini_deposito_atti_appello` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-atti-appello.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/termini-impugnazioni-civile-amministrativo-tributario.php | Normattiva: artt. 165, 166, 325, 327, 343 e 347 c.p.c. vigenti; art. 35 D.Lgs. 149/2022 | Audit settembre 2026: corretto ai par. 4.4 (costituzione dell'appellante 10 giorni e non 30; comparsa dell'appellato 70 giorni prima dell'udienza e non 20) e 4.1 (sospensione feriale aggiunta, prima assente); non compare nei par. 5 e 7. Mappatura: termine breve e lungo sulla pagina delle impugnazioni; i 10 giorni in avanti e i 70 a ritroso su https://www.avvocatoandreani.it/servizi/calcolo_scadenze_termini_udienze.php (somma e sottrazione di giorni con sospensione). La pagina omonima https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-atti-appello.php calcola invece i termini dell'art. 352 c.p.c. (note, conclusionali e repliche non oltre 60, 30 e 15 giorni prima dell'udienza di rimessione in decisione in appello), che nessun tool calcola: da elencare tra i calcolatori del sito senza tool. Con cite_law confermare gli artt. 165, 166 e 347 vigenti (anche dopo il D.Lgs. 164/2024) e che per l'appello il discrimine tra vecchio e nuovo termine è la proposizione dell'impugnazione dopo il 28/02/2023 (art. 35 co. 4 D.Lgs. 149/2022, da riscontrare), non l'iscrizione a ruolo del primo grado come dice la nota del tool. Fase 0: il sito ha una pagina dedicata all'appello ma calcola i termini ex art. 352 c.p.c. (note, conclusionale, replica dall'udienza); i termini di impugnazione e di costituzione del tool si riscontrano sulla pagina delle impugnazioni e sulla norma. |
| `termini_deposito_ctu` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-ctu.php (alta) | Normattiva: artt. 193 e 195 c.p.c. vigenti | Audit settembre 2026: corretto ai par. 4.5 (i termini per osservazioni e deposito definitivo sono fissati dal giudice ex art. 195 co. 3 e ora sono parametri) e 4.1 (sospensione feriale); non compare nei par. 5 e 7. Il benchmark deve confermare le tre scadenze in successione con agosto escluso e la convenzione sul termine successivo quando il precedente cade in un festivo (il tool lo fa decorrere dalla scadenza non prorogata). Il sito usa come data iniziale l'inizio delle operazioni peritali, il tool il conferimento dell'incarico: stesso calcolo con etichetta diversa. Verificare se il sito applica la sospensione feriale ai termini del consulente. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `termini_esecuzioni` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-esecuzioni.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php | Normattiva: artt. 480, 481, 482, 519 e 617 c.p.c.; art. 3 L. 742/1969 e art. 92 R.D. 12/1941 | Audit settembre 2026: non corretto né declassato (assente dai par. 4, 5 e 7). Secondo la descrizione, la pagina del sito calcola i termini dei pignoramenti mobiliari, immobiliari, presso terzi e dei veicoli, probabilmente successivi alla notifica del pignoramento: se non copre i termini del precetto, passare a solo_norma per gli artt. 481, 482 e 617 c.p.c. ed elencare i termini del sito senza tool. Punti da confermare: per l'art. 482 il pignoramento è eseguibile dall'undicesimo giorno dalla notifica del precetto, mentre il tool apre la finestra al decimo e applica la proroga festiva a un termine dilatorio; il termine di 90 giorni dell'art. 481 non è sospeso ad agosto per la sua natura sostanziale (Cass. 3457/1980 e 1125/1971 secondo fonti secondarie), coerente con il tool, ma la proroga del sabato che il tool applica va verificata; il tipo opposizione_esecuzione calcola l'opposizione agli atti esecutivi (art. 617), mentre l'opposizione all'esecuzione (art. 615) non ha termine prima dell'inizio dell'esecuzione. Fase 0: pagina confermata dal crawl (era a confidenza bassa). |
| `termini_memorie_repliche` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-memorie-integrative-comparse-repliche.php (alta) | Normattiva: art. 171-ter c.p.c. vigente | Audit settembre 2026: corretto al par. 4.1 (prima non applicava la sospensione feriale; ora parametro con default True e conteggio a ritroso giorno per giorno); non compare nei par. 5 e 7. Il benchmark deve confermare le tre date a ritroso con agosto escluso, l'anticipazione delle scadenze che cadono di sabato, domenica o festivo e la coerenza con termini_processuali_civili (memoria_I, II e III sulla stessa udienza devono coincidere). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `termini_procedimento_semplificato` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-procedimento-semplificato.php (alta) | Normattiva: artt. 281-undecies e 281-duodecies c.p.c. vigenti, anche dopo il correttivo D.Lgs. 164/2024 | Audit settembre 2026: corretto al par. 4.3 (applicava i 70 giorni e le memorie 40/20/10 del rito ordinario; ora notifica con termini liberi di 40 o 60 giorni, costituzione del convenuto 10 giorni prima, memorie eventuali 20 + 10 giorni e rifiuto dei giorni oltre i massimi); non compare nei par. 5 e 7. Il benchmark deve confermare sul sito i termini a ritroso (ultimo giorno per la notifica con termini liberi, costituzione del convenuto) e verificare se il sito calcola anche le memorie in avanti dall'udienza; con cite_law verificare il comma che fissa la costituzione (il tool cita il co. 3 dell'art. 281-undecies) e le eventuali modifiche del correttivo D.Lgs. 164/2024 agli artt. 281-undecies e 281-duodecies. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `termini_processuali_civili` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-memorie-integrative-comparse-repliche.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php | Normattiva: artt. 171-ter e 189 c.p.c. vigenti (già letti da tests/unit/test_cartabia_live.py) | Audit settembre 2026: corretto ai par. 4.1 (sospensione feriale giorno per giorno anche a ritroso) e 4.2 (art. 189 al posto dell'art. 190 abrogato, nuova opzione note_conclusioni, parametro giorni per il termine più breve assegnato dal giudice); non compare nei par. 5 e 7. Il benchmark deve confermare il conteggio a ritroso con agosto escluso e la convenzione sulla scadenza a ritroso che cade di sabato o in giorno festivo (il tool la anticipa al giorno non festivo precedente). La pagina del sito calcola anche i termini dell'art. 275-bis c.p.c., senza tool corrispondente. È la stessa pagina di termini_memorie_repliche: i due tool devono restituire le stesse date per la stessa udienza. Fase 0: pagina confermata (memorie 171-ter e atti 189 dalla data di udienza); la pagina generica dei termini a giorni e mesi (con elenco per articolo e scelta nuovo/vecchio rito) e' utile per i termini singoli. |
| `termini_separazione_divorzio` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-termini-separazione-divorzio.php (alta) | Normattiva: art. 3 n. 2 lett. b) L. 898/1970 nel testo vigente; artt. 6 e 12 DL 132/2014 conv. L. 162/2014 | Audit settembre 2026: corretto al par. 4.5 (i 6 e 12 mesi decorrono dalla comparizione dei coniugi in udienza e non dall'omologa; nota sul cumulo delle domande ex art. 473-bis.49 c.p.c.); non compare nei par. 5 e 7. Nessun calcolatore pertinente: la pagina https://www.avvocatoandreani.it/servizi/calcolo-termini-separazione-divorzio.php calcola le memorie dell'art. 473-bis.17 e gli atti dell'art. 473-bis.28 c.p.c. del rito unificato, che nessun tool calcola (da elencare tra i calcolatori del sito senza tool); l'aritmetica a mesi si può riscontrare su calcolo-termini-processuali-civili.php con sospensione disattivata. Il benchmark deve leggere con cite_law l'art. 3 n. 2 lett. b) L. 898/1970 vigente (decorrenza dopo il D.Lgs. 149/2022; ipotesi dell'accordo concluso davanti all'ufficiale dello stato civile, art. 12 DL 132/2014, che il tool non offre) e qualificare la data restituita: il tool tratta la durata minima della separazione come una scadenza e le applica la proroga dell'art. 155 c.p.c. Fase 0: il sito ha un calcolatore dedicato (non emerso dalla ricerca web); strategia portata da solo_norma ad andreani, il riscontro sull'art. 3 L. 898/1970 resta come fonte. |

### `scadenza_processuale`

Scadenza generica a giorni di calendario o lavorativi dal dies a quo escluso, con proroga al primo giorno non festivo (sabato compreso) ex art. 155 c.p.c. e sospensione feriale facoltativa.

- Parametri: `data_evento: str (YYYY-MM-DD, dies a quo escluso); giorni: int (>= 1); tipo: str = 'calendario' ['calendario', 'lavorativi']; sospensione_feriale: bool = False`
- Fonte normativa dichiarata: Art. 155 c.p.c. (testo vigente, non modificato dalla riforma Cartabia); L. 742/1969 per la sospensione feriale 1-31 agosto
- Casi di prova:
  - Termine di 30 giorni che finirebbe in agosto, con sospensione feriale (caso della tabella del par. 4.1): `{"data_evento": "2025-07-20", "giorni": 30, "sospensione_feriale": true}` → atteso: 2025-09-19: 21-31 luglio sono 11 giorni, agosto non si conta (art. 1 L. 742/1969), 1-19 settembre gli altri 19; dies a quo escluso (art. 155 co. 1 c.p.c.)
  - Dies a quo in agosto con sospensione feriale: `{"data_evento": "2025-08-10", "giorni": 30, "sospensione_feriale": true}` → atteso: 2025-09-30: il decorso che inizia durante la sospensione è differito alla sua fine (art. 1 L. 742/1969, secondo periodo), il 1° settembre è il primo giorno del termine
  - Scadenza sul 4 ottobre, festività nazionale dal 2026: `{"data_evento": "2027-09-04", "giorni": 30}` → atteso: 2027-10-05: il 30° giorno è lunedì 4 ottobre 2027, festivo per la L. 151/2025 che modifica la L. 260/1949, proroga ex art. 155 co. 4 c.p.c.; un calendario senza il 4 ottobre darebbe 2027-10-04
  - Scadenza di sabato: `{"data_evento": "2025-06-01", "giorni": 6}` → atteso: 2025-06-09 per un termine processuale (sabato 7 giugno prorogato al lunedì, art. 155 co. 5 c.p.c.); per un termine sostanziale il sabato non proroga (art. 2963 co. 3 c.c.) e la scadenza resta 2025-06-07: da leggere dal sito come tratta il sabato
  - Conteggio a giorni lavorativi con Pasqua, Lunedì dell'Angelo e 25 aprile: `{"data_evento": "2025-04-17", "giorni": 5, "tipo": "lavorativi"}` → atteso: 2025-04-28 (giorni utili 18, 22, 23, 24 e 28 aprile 2025); nessuna norma processuale conta a giorni lavorativi, confronto solo aritmetico se il sito offre l'opzione

### `scadenze_impugnazioni`

Termine breve dalla notifica o lungo di sei mesi dalla pubblicazione per appello, ricorso per cassazione, revocazione, opposizione di terzo e regolamento di competenza, con sospensione feriale e proroga festiva.

- Parametri: `data_pubblicazione: str (YYYY-MM-DD; pubblicazione per il termine lungo o notifica con notificata=True); tipo_impugnazione: str ['appello_sentenza', 'cassazione', 'revocazione', 'opposizione_terzo', 'regolamento_competenza']; notificata: bool = False; sospensione_feriale: bool = True`
- Fonte normativa dichiarata: Artt. 325-327 c.p.c. (non modificati dalla riforma Cartabia); art. 47 c.p.c. per il regolamento di competenza; L. 742/1969
- Casi di prova:
  - Appello, termine breve che attraversa agosto (caso del par. 4.1): `{"data_pubblicazione": "2025-07-20", "tipo_impugnazione": "appello_sentenza", "notificata": true}` → atteso: 2025-09-19: 30 giorni dalla notifica (art. 325 co. 1 c.p.c.), 11 in luglio e 19 in settembre
  - Appello, termine lungo con agosto compreso e scadenza festiva: `{"data_pubblicazione": "2025-06-01", "tipo_impugnazione": "appello_sentenza", "notificata": false}` → atteso: 2026-01-02: sei mesi (art. 327 c.p.c.) al 2025-12-01, più 31 giorni di sospensione = 2026-01-01 festivo, proroga al 2 gennaio (art. 155 co. 4 c.p.c.)
  - Cassazione, termine lungo con pubblicazione in agosto: `{"data_pubblicazione": "2027-08-10", "tipo_impugnazione": "cassazione", "notificata": false}` → atteso: Il tool fa decorrere i sei mesi dal 31 agosto e restituisce 2028-02-29 (martedì); con decorrenza dal 1° settembre la scadenza è 2028-03-01: da leggere dal sito e riportare entrambe le date
  - Cassazione, termine breve di 60 giorni che attraversa agosto e cade di domenica: `{"data_pubblicazione": "2025-06-15", "tipo_impugnazione": "cassazione", "notificata": true}` → atteso: 2025-09-15: 46 giorni tra giugno e luglio, agosto escluso, 14 in settembre = domenica 14, proroga a lunedì 15 (art. 325 co. 2 c.p.c.)
  - Regolamento di competenza: `{"data_pubblicazione": "2025-07-10", "tipo_impugnazione": "regolamento_competenza", "notificata": true}` → atteso: 2025-09-09: 30 giorni dalla comunicazione dell'ordinanza (art. 47 co. 2 c.p.c.), 21 in luglio e 9 in settembre; con notificata=false scadenza null (nessun termine lungo)

### `scadenze_multe`

Termini contro i verbali del Codice della strada: ricorso al prefetto (60 giorni), ricorso al giudice di pace (30 giorni), pagamento in misura ridotta (60 giorni) o entro 5 giorni con sconto del 30%, con riepilogo di tutte le opzioni.

- Parametri: `data_notifica: str (YYYY-MM-DD); tipo_ricorso: str ['prefetto', 'giudice_pace', 'pagamento_ridotto', 'pagamento_ridotto_5gg']`
- Fonte normativa dichiarata: D.Lgs. 285/1992 artt. 202, 203 e 204-bis; sconto del 30% dall'art. 20 DL 69/2013 conv. L. 98/2013
- Casi di prova:
  - Ricorso al prefetto e riepilogo delle opzioni: `{"data_notifica": "2025-06-01", "tipo_ricorso": "prefetto"}` → atteso: 2025-07-31: 60 giorni dalla notifica (art. 203 co. 1 D.Lgs. 285/1992); nel riepilogo giudice_pace 2025-07-01 (art. 204-bis; art. 7 D.Lgs. 150/2011) e pagamento_ridotto_5gg 2025-06-06 (art. 202 co. 1)
  - Ricorso al giudice di pace che attraversa agosto: `{"data_notifica": "2025-07-20", "tipo_ricorso": "giudice_pace"}` → atteso: 2025-09-19 se si applica la sospensione feriale, ritenuta applicabile a questo ricorso dalla Cassazione secondo fonti secondarie (11 giorni in luglio, 19 in settembre); il tool dà 2025-08-19 con una nota di verifica: da leggere dal sito
  - Pagamento entro 5 giorni con Natale, Santo Stefano e sabato: `{"data_notifica": "2025-12-20", "tipo_ricorso": "pagamento_ridotto_5gg"}` → atteso: Il quinto giorno è il 25 dicembre e il 26 è festivo: con la sola proroga festiva (art. 2963 co. 3 c.c., il sabato non è festivo) la scadenza è sabato 2025-12-27; il tool estende la regola del sabato dell'art. 155 co. 5 c.p.c. e dà 2025-12-29: da leggere dal sito
  - Pagamento in misura ridotta a 60 giorni che scade il 1° maggio: `{"data_notifica": "2026-03-02", "tipo_ricorso": "pagamento_ridotto"}` → atteso: Il 60° giorno è venerdì 1° maggio 2026, festivo: proroga al primo giorno non festivo, sabato 2026-05-02 (art. 2963 c.c.); il tool dà lunedì 2026-05-04: da leggere dal sito

### `termini_183_190_cpc`

Termini del rito ordinario previgente (cause iscritte prima del 28/02/2023): memorie ex art. 183 co. 6 a 30, 60 e 80 giorni dall'udienza, comparsa conclusionale e replica ex art. 190 a 60 e 80 giorni dall'udienza di precisazione delle conclusioni.

- Parametri: `data_udienza: str (YYYY-MM-DD; udienza ex art. 183 oppure udienza di precisazione delle conclusioni); sospensione_feriale: bool = True`
- Fonte normativa dichiarata: Regime PREVIGENTE: artt. 183 co. 6 e 190 c.p.c. nel testo anteriore al D.Lgs. 149/2022, solo cause iscritte a ruolo prima del 28/02/2023 (art. 35 co. 1 D.Lgs. 149/2022)
- Casi di prova:
  - Prima memoria che scade di sabato prima della Festa della Repubblica: `{"data_udienza": "2025-05-01"}` → atteso: memoria_183_n1 2025-06-03 (31 maggio sabato, 1° giugno domenica, 2 giugno festivo), memoria_183_n2 2025-06-30, memoria_183_n3 2025-07-21, comparsa_conclusionale 2025-06-30, memoria_replica_190 2025-07-21, tutti contati dall'udienza; se il sito fa decorrere i termini successivi dalla scadenza prorogata del precedente ottiene 2025-07-03 e 2025-07-23: da leggere dal sito
  - Udienza del 1° luglio con sospensione feriale: `{"data_udienza": "2025-07-01"}` → atteso: memoria_183_n1 2025-07-31, memoria_183_n2 2025-09-30 (30 giorni in luglio, agosto escluso, 30 in settembre), memoria_183_n3 2025-10-20; comparsa_conclusionale 2025-09-30 e memoria_replica_190 2025-10-20 se la data è l'udienza di precisazione delle conclusioni (art. 190 testo previgente: 60 giorni e 20 successivi); campo regime_normativo presente
  - Stessa udienza senza sospensione: `{"data_udienza": "2025-07-01", "sospensione_feriale": false}` → atteso: memoria_183_n1 2025-07-31, memoria_183_n2 2025-09-01 (30 agosto sabato), memoria_183_n3 2025-09-19

### `termini_deposito_atti_appello`

Termini del giudizio di appello civile: impugnazione breve e lunga, costituzione dell'appellante entro 10 giorni dalla notifica della citazione e comparsa dell'appellato 70 giorni prima dell'udienza.

- Parametri: `data_notifica_sentenza: str \| None = None; data_pubblicazione: str \| None = None; data_notifica_citazione: str \| None = None; data_udienza: str \| None = None; sospensione_feriale: bool = True (almeno una data obbligatoria, formato YYYY-MM-DD)`
- Fonte normativa dichiarata: Artt. 325-327 c.p.c.; artt. 347, 165, 166 e 343 c.p.c. nel testo del D.Lgs. 149/2022 (dal 28/02/2023)
- Casi di prova:
  - Termine breve attraverso agosto e termine lungo con scadenza a Capodanno: `{"data_notifica_sentenza": "2025-07-20", "data_pubblicazione": "2025-06-01"}` → atteso: appello_termine_breve 2025-09-19 (art. 325 co. 1 c.p.c.), appello_termine_lungo 2026-01-02 (art. 327, sei mesi più 31 giorni, 1° gennaio festivo): stessi valori di scadenze_impugnazioni
  - Costituzione dell'appellante e comparsa dell'appellato attraverso agosto: `{"data_notifica_citazione": "2025-07-25", "data_udienza": "2025-10-15"}` → atteso: costituzione_appellante 2025-09-04 (10 giorni, art. 165 via art. 347 c.p.c.: 6 in luglio, 4 in settembre); comparsa_risposta_appellato 2025-07-04 (70 giorni prima, art. 166 via art. 347: 44 tra ottobre e settembre, 26 in luglio fino a domenica 6, anticipata a venerdì 4)
  - Stesse date senza sospensione: `{"data_notifica_citazione": "2025-07-25", "data_udienza": "2025-10-15", "sospensione_feriale": false}` → atteso: costituzione_appellante 2025-08-04; comparsa_risposta_appellato 2025-08-06
  - Comparsa dell'appellato, confronto con il termine previgente: `{"data_udienza": "2025-12-15"}` → atteso: comparsa_risposta_appellato 2025-10-06 (70 giorni prima, lunedì); con il testo previgente dell'art. 166 (20 giorni) sarebbe 2025-11-25, che il tool non calcola

### `termini_deposito_ctu`

Scadenze in successione della consulenza tecnica d'ufficio: trasmissione della bozza alle parti, osservazioni delle parti, deposito della relazione definitiva, sui giorni assegnati dal giudice.

- Parametri: `data_conferimento: str (YYYY-MM-DD); giorni_termine: int = 60; giorni_osservazioni: int = 15; giorni_replica: int = 15; sospensione_feriale: bool = True`
- Fonte normativa dichiarata: Art. 195 co. 3 c.p.c. (testo D.Lgs. 149/2022); termini fissati dal giudice con l'ordinanza ex art. 193, 60/15/15 giorni di prassi
- Casi di prova:
  - Termini di prassi 60/15/15 senza agosto: `{"data_conferimento": "2025-05-01"}` → atteso: deposito_bozza_ctu 2025-06-30, osservazioni_parti 2025-07-15, replica_ctu 2025-07-30 (art. 195 co. 3 c.p.c.)
  - Conferimento a luglio con sospensione feriale: `{"data_conferimento": "2025-07-01"}` → atteso: 2025-09-30 (30 giorni in luglio, agosto escluso, 30 in settembre), 2025-10-15, 2025-10-30
  - Stesso conferimento senza sospensione, con scadenze nel fine settimana: `{"data_conferimento": "2025-07-01", "sospensione_feriale": false}` → atteso: 2025-09-01 (30 agosto sabato), 2025-09-15 (14 settembre domenica), 2025-09-29, con i termini successivi contati dalle scadenze non prorogate
  - Primo termine che cade il 2 giugno: `{"data_conferimento": "2025-04-03"}` → atteso: deposito_bozza_ctu 2025-06-03 (2 giugno festivo); il tool fa decorrere le osservazioni dalla scadenza non prorogata: 2025-06-17 e 2025-07-02; dalla scadenza prorogata sarebbero 2025-06-18 e 2025-07-03: da leggere dal sito
  - Giorni personalizzati dal giudice: `{"data_conferimento": "2025-06-10", "giorni_termine": 90, "giorni_osservazioni": 20, "giorni_replica": 10}` → atteso: 2025-10-09, 2025-10-29, 2025-11-10 (8 novembre sabato)

### `termini_esecuzioni`

Termini legati al precetto: termine dilatorio di 10 giorni e perdita di efficacia a 90 giorni per i pignoramenti, 20 giorni per l'opposizione agli atti esecutivi, senza sospensione feriale.

- Parametri: `data_notifica_titolo: str (YYYY-MM-DD, notifica del precetto); tipo: str = 'pignoramento_mobiliare' ['pignoramento_mobiliare', 'pignoramento_immobiliare', 'pignoramento_presso_terzi', 'opposizione_esecuzione']`
- Fonte normativa dichiarata: Artt. 480-482, 543, 555 e 617 c.p.c. (testo vigente)
- Casi di prova:
  - Pignoramento mobiliare: termine dilatorio ed efficacia del precetto che scade di sabato: `{"data_notifica_titolo": "2025-06-01", "tipo": "pignoramento_mobiliare"}` → atteso: Primo giorno utile per il pignoramento 2025-06-12 (art. 482 c.p.c.: devono essere decorsi dieci giorni dalla notifica, dies a quo escluso), il tool indica la finestra dal 2025-06-11; efficacia: il 90° giorno è sabato 2025-08-30 senza sospensione feriale (art. 481), il tool proroga a lunedì 2025-09-01: da leggere dal sito
  - Pignoramento presso terzi con termine dilatorio che cade a Santo Stefano: `{"data_notifica_titolo": "2025-12-16", "tipo": "pignoramento_presso_terzi"}` → atteso: Dieci giorni decorsi il 26 dicembre: pignoramento eseguibile da sabato 2025-12-27 (la proroga festiva non serve a un termine dilatorio); il tool indica 2025-12-29; efficacia del precetto 2026-03-16 (lunedì)
  - Opposizione agli atti esecutivi contro il precetto, scadenza di sabato: `{"data_notifica_titolo": "2025-06-01", "tipo": "opposizione_esecuzione"}` → atteso: 2025-06-23: 20 giorni dalla notifica del precetto (art. 617 co. 1 c.p.c.), il 21 giugno è sabato (art. 155 co. 5 c.p.c.)
  - Opposizione agli atti esecutivi che attraversa agosto: `{"data_notifica_titolo": "2025-07-20", "tipo": "opposizione_esecuzione"}` → atteso: 2025-08-11 senza sospensione feriale (opposizioni esecutive escluse, art. 3 L. 742/1969 e art. 92 R.D. 12/1941), il 9 agosto è sabato; con la sospensione sarebbe 2025-09-09: verificare che l'esclusione copra l'opposizione agli atti proposta prima dell'esecuzione

### `termini_memorie_repliche`

Le tre memorie integrative ex art. 171-ter c.p.c. (40, 20 e 10 giorni prima dell'udienza ex art. 183) in un'unica risposta, a ritroso con sospensione feriale e anticipazione delle scadenze festive.

- Parametri: `data_udienza: str (YYYY-MM-DD, udienza di comparizione e trattazione ex art. 183); sospensione_feriale: bool = True`
- Fonte normativa dichiarata: Art. 171-ter c.p.c., rito ordinario post-Cartabia (D.Lgs. 149/2022, dal 28/02/2023); L. 742/1969
- Casi di prova:
  - Udienza del 1° ottobre con sospensione feriale: `{"data_udienza": "2025-10-01"}` → atteso: memoria_integrativa 2025-07-22, replica 2025-09-11, prova_contraria 2025-09-19 (40, 20 e 10 giorni a ritroso, art. 171-ter co. 1 c.p.c.; agosto escluso; il 21 settembre è domenica e anticipa a venerdì 19)
  - Stessa udienza senza sospensione (materia esclusa ex art. 3 L. 742/1969): `{"data_udienza": "2025-10-01", "sospensione_feriale": false}` → atteso: memoria_integrativa 2025-08-22, replica 2025-09-11, prova_contraria 2025-09-19
  - Scadenze a ritroso che cadono nel fine settimana: `{"data_udienza": "2025-09-15"}` → atteso: memoria_integrativa 2025-07-04 (domenica 6 luglio anticipata), replica 2025-07-25 (sabato 26 luglio anticipato), prova_contraria 2025-09-05: da leggere dal sito la convenzione sull'anticipazione

### `termini_procedimento_semplificato`

Termini del procedimento semplificato di cognizione: ultimo giorno per notificare ricorso e decreto (40 o 60 giorni liberi), costituzione del convenuto 10 giorni prima, memoria integrativa e replica eventuali (20 + 10 giorni dall'udienza).

- Parametri: `data_udienza: str (YYYY-MM-DD); giorni_memoria: int = 20 (1-20); giorni_replica: int = 10 (1-10); sospensione_feriale: bool = True`
- Fonte normativa dichiarata: Artt. 281-decies, 281-undecies e 281-duodecies c.p.c. introdotti dal D.Lgs. 149/2022 (dal 28/02/2023)
- Casi di prova:
  - Udienza del 1° ottobre con sospensione feriale: `{"data_udienza": "2025-10-01"}` → atteso: notifica_ricorso_italia 2025-07-21 (40 giorni liberi, art. 281-undecies c.p.c.: ultimo giorno 41 giorni prima, agosto escluso), notifica_ricorso_estero 2025-07-01 (60 giorni liberi), costituzione_convenuto 2025-09-19 (10 giorni prima = domenica 21 settembre, anticipata), memoria_integrativa 2025-10-21 e replica_prova_contraria 2025-10-31 (20 + 10 giorni, art. 281-duodecies c.p.c.)
  - Stessa udienza senza sospensione: `{"data_udienza": "2025-10-01", "sospensione_feriale": false}` → atteso: notifica_ricorso_italia 2025-08-21, notifica_ricorso_estero 2025-08-01, costituzione_convenuto 2025-09-19, memoria_integrativa 2025-10-21, replica_prova_contraria 2025-10-31
  - Udienza di luglio con memorie concesse che attraversano agosto: `{"data_udienza": "2025-07-22", "giorni_memoria": 20, "giorni_replica": 10}` → atteso: memoria_integrativa 2025-09-11 (9 giorni in luglio, 11 in settembre), replica_prova_contraria 2025-09-22 (21 settembre domenica, proroga); costituzione_convenuto 2025-07-11 (sabato 12 luglio anticipato); notifica_ricorso_italia 2025-06-11
  - Termine per la memoria oltre il massimo di legge: `{"data_udienza": "2025-10-01", "giorni_memoria": 21}` → atteso: errore: il termine concesso dal giudice non può superare 20 giorni (art. 281-duodecies c.p.c.)

### `termini_processuali_civili`

Singolo termine del rito ordinario post-Cartabia a ritroso dall'udienza: memorie integrative ex art. 171-ter c.p.c. oppure note, comparsa conclusionale e replica ex art. 189 c.p.c., con termine più breve eventualmente assegnato dal giudice.

- Parametri: `data_udienza: str (YYYY-MM-DD; udienza ex art. 183 per le memorie, udienza di rimessione in decisione ex art. 189 per gli altri atti); tipo_termine: str ['memoria_I', 'memoria_II', 'memoria_III', 'note_conclusioni', 'comparsa_conclusionale', 'replica']; sospensione_feriale: bool = True; giorni: int \| None = None`
- Fonte normativa dichiarata: Artt. 171-ter e 189 c.p.c. nel testo del D.Lgs. 149/2022 (dal 28/02/2023); art. 190 c.p.c. abrogato, residuale per le cause iscritte prima del 28/02/2023
- Casi di prova:
  - Memoria integrativa 40 giorni prima, a ritroso attraverso agosto (caso del par. 4.1): `{"data_udienza": "2025-10-01", "tipo_termine": "memoria_I"}` → atteso: 2025-07-22: 30/09-01/09 sono 30 giorni, agosto non si conta, 31/07-22/07 gli altri 10 (art. 171-ter co. 1 n. 1 c.p.c.; L. 742/1969); nel riepilogo memoria_II 2025-09-11 e memoria_III 2025-09-19
  - Scadenza a ritroso che cade di domenica: `{"data_udienza": "2025-09-15", "tipo_termine": "memoria_I"}` → atteso: 2025-07-04: il 40° giorno a ritroso è domenica 6 luglio, anticipato al venerdì per non ridurre il termine a difesa della controparte; se il sito proroga in avanti ottiene 2025-07-07: da leggere dal sito
  - Comparsa conclusionale 30 giorni prima dell'udienza di rimessione in decisione, attraverso agosto: `{"data_udienza": "2026-09-21", "tipo_termine": "comparsa_conclusionale"}` → atteso: 2026-07-22: 20 giorni in settembre, agosto escluso, 10 in luglio (art. 189 co. 1 n. 2 c.p.c.); nel riepilogo note_conclusioni 2026-06-22 (60 giorni, n. 1) e replica 2026-09-04
  - Replica 15 giorni prima che cade di domenica: `{"data_udienza": "2026-09-21", "tipo_termine": "replica"}` → atteso: 2026-09-04: il 15° giorno a ritroso è domenica 6 settembre, anticipato a venerdì 4 (art. 189 co. 1 n. 3 c.p.c.)
  - Termine più breve assegnato dal giudice, materia esclusa dalla sospensione: `{"data_udienza": "2026-09-21", "tipo_termine": "comparsa_conclusionale", "giorni": 20, "sospensione_feriale": false}` → atteso: 2026-09-01: 20 giorni a ritroso senza sospensione (l'art. 189 fissa solo i massimi; art. 3 L. 742/1969 per le materie escluse); giorni_assegnati_dal_giudice true

### `termini_separazione_divorzio`

Data di maturazione dei 6 o 12 mesi di separazione richiesti per la domanda di divorzio (consensuale, giudiziale, negoziazione assistita); nessun termine per il ricorso di modifica delle condizioni.

- Parametri: `data_evento: str (YYYY-MM-DD; comparizione dei coniugi in udienza o data certificata nell'accordo); tipo: str ['separazione_consensuale', 'separazione_giudiziale', 'negoziazione_assistita', 'ricorso_modifica']`
- Fonte normativa dichiarata: Art. 3 n. 2 lett. b) L. 898/1970 (mod. L. 55/2015, divorzio breve); DL 132/2014 conv. L. 162/2014; art. 473-bis.49 c.p.c. per il cumulo delle domande dal 28/02/2023
- Casi di prova:
  - Separazione consensuale, sei mesi: `{"data_evento": "2025-03-15", "tipo": "separazione_consensuale"}` → atteso: 2025-09-15 (lunedì): sei mesi dalla comparizione dei coniugi (art. 3 n. 2 lett. b L. 898/1970), computo a calendario comune (art. 155 co. 2 c.p.c.)
  - Separazione giudiziale, dodici mesi che si compiono di domenica: `{"data_evento": "2025-03-15", "tipo": "separazione_giudiziale"}` → atteso: Compimento il 2026-03-15 (domenica); il tool restituisce 2026-03-16 applicando la proroga dell'art. 155 co. 4 c.p.c. a un termine di durata minima: da qualificare (data di compimento o primo giorno utile per la domanda)
  - Dies a quo il 31 agosto, mese di scadenza senza il giorno corrispondente: `{"data_evento": "2025-08-31", "tipo": "separazione_consensuale"}` → atteso: Compimento il 2026-02-28, ultimo giorno di febbraio (art. 2963 co. 4 c.c.), sabato: il tool restituisce 2026-03-02; nessuna sospensione feriale, trattandosi di termine sostanziale
  - Negoziazione assistita, termine che si compie in agosto: `{"data_evento": "2026-02-10", "tipo": "negoziazione_assistita"}` → atteso: 2026-08-10: sei mesi dalla data certificata nell'accordo (art. 3 n. 2 lett. b L. 898/1970 come modificato dal DL 132/2014); la L. 742/1969 non si applica perché il termine non è processuale
  - Ricorso di modifica delle condizioni: `{"data_evento": "2025-06-01", "tipo": "ricorso_modifica"}` → atteso: scadenza null: la revisione delle condizioni non ha termine (art. 473-bis.29 c.p.c.; art. 9 L. 898/1970)

## tassi_interessi.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `calcolo_ammortamento` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-ammortamento-mutuo.php (alta) | Calcolo a mano con la formula della rata costante | Non toccato dall'audit. Rata costante con tasso periodale TAN/12, verificata a mano; test Playwright esistente in tests/comparison/test_ammortamento.py. Il sito offre anche periodicita' trimestrale e semestrale e durata espressa in rate, non coperte dal tool (solo mensile). Il parametro tipo non e' validato (un valore diverso da francese produce un piano all'italiana) e il tasso negativo e' accettato. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_maggior_danno` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-maggior-danno-obbligazioni-pecuniarie.php (alta) | Banca d'Italia, rendimenti lordi medi dei BOT all'emissione (netti al 12,5%) e Rendistato; DM MEF sui tassi legali | Declassato a INDICATIVO dall'audit (par. 7: Cass. SS.UU. 19499/2008 presume il maggior danno nella differenza tra rendimento medio annuo netto dei titoli di Stato fino a dodici mesi e saggio legale, non nell'indice FOI; confidenza alta). Il sito offre tre criteri (BOT fino a 12 mesi, Rendistato, inflazione ISTAT): col criterio ISTAT si verifica l'aritmetica del tool, col criterio BOT si misura lo scarto dalla regola delle Sezioni Unite e si raccoglie la serie annua dei rendimenti netti per la riscrittura. Il tool confronta la rivalutazione dell'intero periodo con la somma degli interessi, mentre il criterio SU e' anno per anno. Risente anche dell'errore dei tassi legali del 1990 e della serie FOI 2011-2013. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_surroga_mutuo` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-surroga-mutuo.php (alta) | Calcolo a mano con la formula della rata costante | Non toccato dall'audit. Il tool non usa tasso_attuale nei calcoli e non controlla la coerenza tra rata attuale, tasso e mesi residui: con una rata incoerente gli interessi residui risultano negativi. Riferimento: art. 120-quater TUB (inserito dal D.Lgs. 141/2010, che ha sostituito l'art. 8 DL 7/2007), surroga senza penali ne' spese per il cliente, quindi break_even 0 e' corretto. Il titolo della pagina del sito indica anche il taglio della rata: confrontare solo il caso a durata invariata. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `calcolo_taeg` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-taeg.php (alta) ; secondarie: https://www.avvocatoandreani.it/utility/calcolo-taeg-tan.php | Banca d'Italia, Disposizioni di trasparenza, allegato sul calcolo del TAEG (formula dell'all. I Dir. 2008/48/CE) | Non toccato dall'audit; gia' INDICATIVO. L'esempio pubblicato sulla pagina (30.000 euro all'1,5% per 10 anni con 270 euro di spese iniziali: TAEG 1,68%; con 5 euro a rata e 20 euro annui: 2,18%) coincide con 12 volte il tasso mensile (campo tan_pct del tool: 1,6841 e circa 2,186), mentre il TAEG della formula dell'all. I Dir. 2008/48/CE e' un tasso effettivo annuo (1,6971 e circa 2,208, valori del tool): differenza di convenzione del sito da documentare, il tool non va allineato. La pagina cita il DM 8/7/1992, superato. Il tool non ha spese annuali (vanno approssimate come mensili) e tan_pct non e' il TAN contrattuale. Dal 20/11/2026 si applica la Dir. (UE) 2023/2225: verificare il recepimento e aggiornare la riga Vigenza. Fase 0: pagina confermata; duplicato interno sotto /utility/. |
| `interessi_acconti` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-interessi-acconti.php (alta) | DM MEF sui tassi legali; calcolo a mano con imputazione ex art. 1194 c.c. | Non toccato dall'audit. Il sito applica per default l'art. 1194 c.c. (acconto imputato prima agli interessi maturati, poi al capitale) e consente di togliere la spunta per imputare tutto al capitale: il tool imputa sempre al capitale, quindi il confronto va fatto anche con la spunta tolta, e il docstring deve dire che senza consenso del creditore l'imputazione al capitale non e' ammessa (art. 1194 co. 1). Difetti trovati: un acconto nella data finale o anteriore alla data iniziale non riduce il debito ma entra in totale_acconti; un acconto superiore al residuo azzera il capitale e perde l'eccedenza. Il sito gestisce anche crediti che maturano nel tempo (nuove fatture), non coperti. Stessa tabella dei tassi di interessi_legali (errore del 1990). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `interessi_corso_causa` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-interessi-corso-causa.php (alta) | Comunicati MEF semestrali sul tasso BCE (D.Lgs. 231/2002); DM MEF sui tassi legali per i procedimenti anteriori all'11/12/2014 | Non toccato dall'audit. Difetto normativo trovato: l'art. 1284 co. 4 c.c. si applica ai procedimenti iniziati dall'11/12/2014 (art. 17 co. 2 DL 132/2014 conv. L. 162/2014), ma il tool applica il tasso di mora anche a domande anteriori. Il tasso maggiorato vale solo se le parti non hanno pattuito la misura degli interessi e, in esecuzione, se il titolo lo accerta espressamente (Cass. SU 12449/2024: la condanna generica agli interessi legali vale art. 1284 co. 1). La data rilevante e' la proposizione della domanda (notifica della citazione o deposito del ricorso). Il sito calcola anche gli interessi legali prima della domanda: confrontare la sola parte successiva. Oltre il 31/12/2026 il tool smette di contare senza avviso. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `interessi_legali` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/interessi_legali.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tab_interessi_legali.php | DM MEF annuali sul saggio legale in GU (2026: DM 10/12/2025, GU n. 289 del 13/12/2025); L. 353/1990 per il 1990 | Non toccato dall'audit. Errore di dati trovato: tassi_legali.json fa scattare il 10% dal 16/04/1990, mentre la L. 353/1990 lo applica dal 16/12/1990 (5% fino al 15/12/1990); l'errore incide anche su interessi_acconti e calcolo_maggior_danno (stessa tabella). Anno civile di 365 giorni anche nei bisestili, come il sito (test Playwright esistente in tests/comparison/test_interessi_legali.py). Il parametro tipo non e' validato; composti capitalizza al 31/12 e a ogni cambio di tasso, mentre il sito capitalizza a scadenze fisse (trimestrale, semestrale, annuale) e l'anatocismo e' lecito solo nei limiti dell'art. 1283 c.c. Oltre il 31/12/2026 il tool smette di contare senza avviso, mentre l'art. 1284 co. 1 c.c. prevede che senza nuovo decreto entro il 15 dicembre il saggio resti invariato. Fase 0: pagina confermata; tabella storica dei saggi legali. |
| `interessi_mora` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/interessi_moratori.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/tab_interessi_moratori.php | Comunicati MEF semestrali in GU sul tasso di riferimento (art. 5 co. 2 D.Lgs. 231/2002; II semestre 2026: GU n. 163 del 16/07/2026); tabella del sito https://www.avvocatoandreani.it/servizi/tab_interessi_moratori.php | Voce aperta del par. 7 dell'audit (tassi_mora 2002-2012, maggiorazione di 7 punti prima del D.Lgs. 192/2012, confidenza alta, non modificato): la tabella applica +8 anche ai semestri fino al 2012, mentre il D.Lgs. 192/2012 vale per le transazioni concluse dal 01/01/2013 (art. 3); il tool andrebbe reso dipendente dalla data del contratto. Il controllo ha trovato inoltre: per date anteriori al 01/09/2002 il tool applica in silenzio l'ultimo tasso della tabella (10,40%), mentre il D.Lgs. 231/2002 non si applica ai contratti conclusi prima dell'08/08/2002 (art. 11); oltre il 31/12/2026 smette di contare senza avviso. Il sito prevede la maggiorazione per le cessioni di prodotti agricoli e alimentari (art. 62 DL 1/2012 citato dal sito, da riscontrare col D.Lgs. 198/2021), assente nel tool. Anno di 365 giorni anche nei bisestili. Fase 0: pagina confermata; tabella dei tassi di mora. |
| `interessi_tasso_fisso` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/interessi_tasso_fisso.php (alta) | Calcolo a mano con la formula C x S x N / 36500 dichiarata dal sito | Non toccato dall'audit. Il sito dichiara la formula C x S x N / 36500 (anno civile di 365 giorni anche nei bisestili) e la capitalizzazione a date fisse (1/1, 1/4, 1/7, 1/10). Il tool usa come divisore i giorni dell'anno di inizio (366 se bisestile) per tutto il periodo e, per i composti, (1+i)^(giorni/365): scostamenti attesi da documentare; incoerenza 365 contro bisestile gia' segnalata in docs/_audit/REPORT.md. Il parametro tipo non e' validato. Nessun controllo della forma scritta (art. 1284 co. 3 c.c.) ne' della soglia d'usura. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `verifica_usura` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_tasso_usura.php (alta) | DM MEF trimestrali sui TEGM in GU (III trimestre 2026: DM 23/06/2026, GU n. 149) e tabelle Banca d'Italia dei tassi effettivi globali medi e delle soglie | Non toccato dall'audit. Formula conforme all'art. 2 co. 4 L. 108/1996 come modificato dall'art. 8 co. 5 lett. d) DL 70/2011: il tetto di 8 punti prevale quando il TEGM supera il 16%. Il benchmark deve riscontrare i TEGM del III trimestre 2026 sul DM MEF e aggiungere il IV trimestre appena pubblicato. Difetti trovati: tipo_operazione sconosciuto ricade in silenzio su credito_personale (manca la categoria anticipi, sconti e altri finanziamenti alle imprese, e mancano le classi oltre soglia di factoring e leasing strumentale); un trimestre assente (dati dal 2025-Q1) e' sostituito col trimestre corrente senza avviso, mentre l'usura si valuta al momento della pattuizione (art. 1 DL 394/2000 conv. L. 24/2001). I test di tests/comparison/test_tassi_extra.py attendono TEGM 4,41 e 10,78 senza fissare il trimestre: vanno aggiornati. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |

### `calcolo_ammortamento`

Piano di ammortamento mensile completo alla francese (rata costante) o all'italiana (quota capitale costante).

- Parametri: `capitale: float, tasso_annuo: float, durata_mesi: int, tipo: str = 'francese' ('francese' \| 'italiano'; altro valore trattato come italiano)`
- Fonte normativa dichiarata: Nessuna riga Vigenza (calcolo matematico)
- Casi di prova:
  - Francese 20 anni al 3,5%: `{"capitale": 100000, "tasso_annuo": 3.5, "durata_mesi": 240, "tipo": "francese"}` → atteso: Rata 579,96 = C x i / (1 - (1+i)^-n) con i = 3,5%/12; interessi totali 39.190,33; debito residuo finale 0.
  - Italiano 15 anni al 4%: `{"capitale": 200000, "tasso_annuo": 4.0, "durata_mesi": 180, "tipo": "italiano"}` → atteso: Quota capitale 1.111,11; prima rata 1.777,78; interessi totali 200.000 x (0,04/12) x 181/2 = 60.333,33.
  - Tasso zero (valore minimo): `{"capitale": 12000, "tasso_annuo": 0, "durata_mesi": 12, "tipo": "francese"}` → atteso: Rata 1.000,00, interessi 0.
  - Metodo non ammesso: `{"capitale": 10000, "tasso_annuo": 5, "durata_mesi": 12, "tipo": "tedesco"}` → atteso: Atteso errore per tipo non ammesso; il tool restituisce un piano all'italiana con rata iniziale 875,00.

### `calcolo_maggior_danno`

Maggior danno ex art. 1224 co. 2 c.c. calcolato come differenza tra rivalutazione FOI e interessi legali del periodo.

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: Art. 1224 co. 2 c.c.; Cass. SU 19499/2008; indici FOI ISTAT raccordati dal 1990
- Casi di prova:
  - Biennio 2022-2023 (inflazione alta, rendimenti BOT sotto il tasso legale): `{"capitale": 10000, "data_inizio": "2022-01-01", "data_fine": "2024-01-01"}` → atteso: Da leggere dal sito col criterio BOT: con rendimenti netti dei BOT 2023 intorno al 3% contro un saggio legale del 5% il maggior danno presunto SU per il 2023 e' nullo. Il tool (criterio FOI) restituisce 451,72; col criterio ISTAT del sito il valore deve coincidere.
  - Anno 2011 (rendimenti BOT sopra il tasso legale dell'1,5%): `{"capitale": 10000, "data_inizio": "2011-01-01", "data_fine": "2012-01-01"}` → atteso: Maggior danno positivo col criterio SU, importo da leggere dal sito (criterio BOT); il tool (FOI) restituisce 127,50 su una serie FOI 2011 da riscontrare.
  - Anno di deflazione FOI (2020): `{"capitale": 10000, "data_inizio": "2020-01-15", "data_fine": "2020-12-15"}` → atteso: FOI da 102,7 a 102,3: rivalutazione negativa, maggior danno 0; spettano gli interessi legali 4,59 (0,05%, DM MEF di dicembre 2019); da confrontare col sito, criterio ISTAT.

### `calcolo_surroga_mutuo`

Confronta rata e interessi residui del mutuo attuale con quelli del mutuo surrogato (ammortamento alla francese) per valutare la portabilita'.

- Parametri: `debito_residuo: float, rata_attuale: float, tasso_attuale: float, tasso_nuovo: float, mesi_residui: int`
- Fonte normativa dichiarata: Art. 120-quater TUB; DL 7/2007 conv. L. 40/2007
- Casi di prova:
  - Surroga conveniente con rata attuale coerente: `{"debito_residuo": 150000, "rata_attuale": 948.97, "tasso_attuale": 4.5, "tasso_nuovo": 3.0, "mesi_residui": 240}` → atteso: Rata al 3%: 831,90; risparmio mensile 117,07; risparmio totale 28.097,66 (formula della rata costante).
  - Tasso nuovo zero (valore minimo): `{"debito_residuo": 60000, "rata_attuale": 579.36, "tasso_attuale": 3.0, "tasso_nuovo": 0, "mesi_residui": 120}` → atteso: Rata 500,00, interessi residui 0; risparmio 79,36 al mese e 9.523,20 in totale.
  - Rata attuale incoerente col tasso: `{"debito_residuo": 100000, "rata_attuale": 500, "tasso_attuale": 2.0, "tasso_nuovo": 3.5, "mesi_residui": 120}` → atteso: Al 2% su 120 mesi la rata e' 920,13: atteso errore o avviso; il tool restituisce interessi residui -40.000.

### `calcolo_taeg`

TAEG di un finanziamento a rate mensili costanti con spese iniziali e periodiche, come tasso interno annualizzato.

- Parametri: `capitale: float, rate: int, importi_rate: float, spese_iniziali: float = 0, spese_periodiche: float = 0`
- Fonte normativa dichiarata: Art. 121 TUB; Dir. 2008/48/CE
- Casi di prova:
  - Esempio pubblicato dal sito, sole spese iniziali: `{"capitale": 30000, "rate": 120, "importi_rate": 269.37, "spese_iniziali": 270}` → atteso: TAEG 1,70% (1,6971) con la formula dell'all. I Dir. 2008/48/CE (art. 121 co. 1 lett. m TUB); la pagina riporta 1,68%, pari al tasso nominale 12 x r (1,6841).
  - Esempio del sito con spese di incasso e annuali: `{"capitale": 30000, "rate": 120, "importi_rate": 269.37, "spese_iniziali": 270, "spese_periodiche": 6.67}` → atteso: Con 5 euro a rata e 20 euro annui (approssimati in 1,67 al mese) TAEG circa 2,21% (2,2081; 2,2065 con le spese annue alla loro data); la pagina riporta 2,18%.
  - Tasso zero senza spese (valore minimo): `{"capitale": 1200, "rate": 12, "importi_rate": 100}` → atteso: TAEG 0,00 e costo totale del credito 0.
  - Spese iniziali pari al capitale: `{"capitale": 1200, "rate": 12, "importi_rate": 100, "spese_iniziali": 1200}` → atteso: Errore: netto erogato nullo.

### `interessi_acconti`

Interessi legali art. 1284 c.c. con acconti intermedi che riducono il capitale residuo alla loro data.

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), acconti: list[{data: str (YYYY-MM-DD), importo: float}], data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: Art. 1284 c.c.; tassi legali vigenti per ciascun anno
- Casi di prova:
  - Un acconto: art. 1194 contro imputazione al capitale: `{"capitale": 10000, "data_inizio": "2023-01-01", "acconti": [{"data": "2023-07-01", "importo": 5000}], "data_fine": "2024-01-01"}` → atteso: Art. 1194 c.c.: l'acconto copre 247,95 di interessi e 4.752,05 di capitale; residuo 5.247,95; interessi successivi 131,92; dovuto 5.379,86 (sito con spunta). Imputazione al capitale (spunta tolta): interessi 373,63, dovuto 5.373,63, valore attuale del tool.
  - Acconto nella data finale (confine): `{"capitale": 10000, "data_inizio": "2025-01-01", "acconti": [{"data": "2025-12-31", "importo": 2000}], "data_fine": "2025-12-31"}` → atteso: Interessi 199,45 (364 giorni al 2%); l'acconto estingue gli interessi e 1.800,55 di capitale: dovuto 8.199,45. Il tool non riduce il capitale e restituisce 10.199,45.
  - Due acconti a cavallo del cambio di tasso 2025-2026: `{"capitale": 10000, "data_inizio": "2025-06-30", "acconti": [{"data": "2025-10-01", "importo": 2000}, {"data": "2026-02-15", "importo": 1000}], "data_fine": "2026-06-30"}` → atteso: Imputazione al capitale: interessi 148,41, dovuto 7.148,41 (valore del tool). Art. 1194: capitale residuo 7.107,34, interessi residui 42,06, dovuto 7.149,40.

### `interessi_corso_causa`

Interessi dalla domanda giudiziale al tasso del D.Lgs. 231/2002 ex art. 1284 co. 4 c.c., in corso di causa e dopo la sentenza.

- Parametri: `capitale: float, data_citazione: str (YYYY-MM-DD), data_sentenza: str (YYYY-MM-DD), data_pagamento: str \| None = None (se None coincide con data_sentenza)`
- Fonte normativa dichiarata: Art. 1284 co. 4 c.c. (L. 162/2014); D.Lgs. 231/2002
- Casi di prova:
  - Causa 2022-2024 con salti del tasso BCE: `{"capitale": 50000, "data_citazione": "2022-01-01", "data_sentenza": "2024-06-01"}` → atteso: 12.236,99: tasso D.Lgs. 231/2002 dal giorno successivo alla domanda (8,00% nel 2022, 10,50% e 12,00% nel 2023, 12,50% fino al 01/06/2024); art. 1284 co. 4 c.c.
  - Procedimento iniziato prima dell'11/12/2014: `{"capitale": 10000, "data_citazione": "2014-06-03", "data_sentenza": "2016-06-03"}` → atteso: Saggio legale dell'art. 1284 co. 1 (1,0% nel 2014, 0,5% nel 2015, 0,2% nel 2016) = 116,30 (art. 17 co. 2 DL 132/2014). Il tool applica la mora e restituisce 1.618,73.
  - Primo giorno di applicazione della norma (confine): `{"capitale": 10000, "data_citazione": "2014-12-11", "data_sentenza": "2015-12-11"}` → atteso: Procedimento iniziato l'11/12/2014: tasso di mora (8,15% fino al 31/12/2014, 8,05% nel 2015) = 805,55.
  - Fase post sentenza a cavallo del semestre 2026: `{"capitale": 20000, "data_citazione": "2025-03-10", "data_sentenza": "2026-02-20", "data_pagamento": "2026-09-30"}` → atteso: In corso di causa 1.991,26 e dopo la sentenza 1.247,29 (11,15%, 10,15%, 10,40%): totale 3.238,55.

### `interessi_legali`

Interessi legali art. 1284 c.c. tra due date con cambio automatico di tasso per periodo, semplici o composti.

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD), tipo: str = 'semplici' ('semplici' \| 'composti'; valore diverso trattato come semplici)`
- Fonte normativa dichiarata: Art. 1284 c.c.; tassi aggiornati annualmente con DM MEF (dal 1 gennaio)
- Casi di prova:
  - Cambio di tasso al 1 gennaio 2026 (2,0% e 1,6%): `{"capitale": 10000, "data_inizio": "2025-07-01", "data_fine": "2026-06-30", "tipo": "semplici"}` → atteso: 179,62: 183 giorni al 2,0% (DM MEF di dicembre 2024) = 100,27 piu' 181 giorni all'1,6% (DM MEF 10/12/2025) = 79,34; art. 1284 co. 1 c.c., dies a quo escluso, divisore 365.
  - Anno 1990 con cambio di tasso infrannuale: `{"capitale": 10000, "data_inizio": "1990-01-01", "data_fine": "1990-12-31", "tipo": "semplici"}` → atteso: 520,55: 5% fino al 15/12/1990 (348 giorni = 476,71) e 10% dal 16/12/1990 (16 giorni = 43,84), L. 353/1990. Il tool oggi restituisce 854,79 perche' applica il 10% dal 16/04/1990.
  - Anno bisestile (convenzione del divisore): `{"capitale": 10000, "data_inizio": "2023-12-31", "data_fine": "2024-12-31", "tipo": "semplici"}` → atteso: 366 giorni al 2,5%: 250,68 con anno civile di 365 giorni (convenzione di sito e tool), 250,00 con divisore 366: convenzione da documentare, la norma non la fissa.
  - Interessi composti su piu' anni: `{"capitale": 50000, "data_inizio": "2021-01-01", "data_fine": "2026-01-01", "tipo": "composti"}` → atteso: Con capitalizzazione annuale al 31/12: 5.586,55 (valore del tool); da leggere dal sito con capitalizzazione annuale; legittimita' dell'anatocismo ex art. 1283 c.c.
  - Data finale oltre la copertura della tabella (2027): `{"capitale": 10000, "data_inizio": "2026-07-01", "data_fine": "2027-06-30", "tipo": "semplici"}` → atteso: Tasso 2027 non ancora fissato: senza decreto entro il 15/12/2026 resta l'1,6% (art. 1284 co. 1 c.c.), stima 80,22 + 79,34 = 159,56 da dichiarare provvisoria. Il tool oggi restituisce 80,22 senza avviso.

### `interessi_mora`

Interessi di mora nelle transazioni commerciali al tasso BCE maggiorato di 8 punti, per semestri.

- Parametri: `capitale: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: D.Lgs. 231/2002 (Dir. 2011/7/UE); tasso BCE semestrale (gennaio e luglio)
- Casi di prova:
  - Cambio di semestre 2026 (10,15% e 10,40%): `{"capitale": 10000, "data_inizio": "2026-03-31", "data_fine": "2026-09-30"}` → atteso: 515,19: 91 giorni al 10,15% (BCE 2,15% + 8) e 92 giorni al 10,40% (BCE 2,40% + 8, comunicato MEF GU n. 163 del 16/07/2026); art. 5 D.Lgs. 231/2002.
  - Contratto anteriore al 2013 (maggiorazione 7 punti): `{"capitale": 10000, "data_inizio": "2012-01-01", "data_fine": "2012-12-31"}` → atteso: Per una transazione conclusa prima del 01/01/2013: BCE 1,00% + 7 = 8,00% per 365 giorni = 800,00 (art. 5 D.Lgs. 231/2002 nel testo anteriore al D.Lgs. 192/2012). Il tool applica +8 e restituisce 900,00.
  - Anno 2023 con salti del tasso BCE: `{"capitale": 10000, "data_inizio": "2023-01-01", "data_fine": "2024-01-01"}` → atteso: 1.126,16: 180 giorni al 10,50%, 184 al 12,00%, 1 al 12,50%.
  - Periodo anteriore all'ambito del D.Lgs. 231/2002: `{"capitale": 10000, "data_inizio": "2001-01-01", "data_fine": "2002-12-31"}` → atteso: Periodo in gran parte anteriore all'ambito del decreto (contratti dall'08/08/2002, art. 11): atteso errore o avviso. Il tool applica il 10,40% dell'ultima riga e restituisce 2.077,15.
  - Anno bisestile (convenzione del divisore): `{"capitale": 10000, "data_inizio": "2024-01-01", "data_fine": "2024-12-31"}` → atteso: 1.237,40 con divisore 365 (12,50% e 12,25%), 1.234,02 con 366: convenzione da leggere dal sito.

### `interessi_tasso_fisso`

Interessi semplici o composti a un tasso fisso fornito tra due date.

- Parametri: `capitale: float, tasso_annuo: float, data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD), tipo: str = 'semplici' ('semplici' \| 'composti')`
- Fonte normativa dichiarata: Nessuna riga Vigenza (calcolo matematico sul tasso fornito)
- Casi di prova:
  - Inizio in anno bisestile (divisore): `{"capitale": 10000, "tasso_annuo": 5, "data_inizio": "2024-01-01", "data_fine": "2025-01-01", "tipo": "semplici"}` → atteso: 366 giorni: 501,37 con la formula del sito (C x S x N / 36500); il tool divide per 366 e restituisce 500,00.
  - Inizio in anno non bisestile, periodo che include il 29 febbraio: `{"capitale": 10000, "tasso_annuo": 5, "data_inizio": "2023-07-01", "data_fine": "2024-07-01", "tipo": "semplici"}` → atteso: 366 giorni / 365: 501,37 (tool e sito concordano).
  - Interessi composti su due anni: `{"capitale": 10000, "tasso_annuo": 5, "data_inizio": "2024-01-01", "data_fine": "2026-01-01", "tipo": "composti"}` → atteso: Da leggere dal sito con capitalizzazione annuale alle date fisse; il tool, con (1,05)^(731/365), restituisce 1.026,47.
  - Periodo breve infrannuale: `{"capitale": 25000, "tasso_annuo": 3.5, "data_inizio": "2025-03-15", "data_fine": "2025-09-15", "tipo": "semplici"}` → atteso: 184 giorni: 25.000 x 3,5 x 184 / 36500 = 441,10.

### `verifica_usura`

Calcola il tasso soglia di usura dal TEGM del trimestre e categoria e verifica se il tasso applicato lo supera.

- Parametri: `tasso_applicato: float, tipo_operazione: str = 'mutuo_prima_casa' (mutuo_prima_casa \| credito_personale \| apertura_credito \| leasing \| factoring \| carte_revolving \| cessione_quinto \| mutuo_tasso_variabile; in tabella anche apertura_credito_oltre_5000, cessione_quinto_oltre_15000, credito_finalizzato, leasing_immobiliare_fisso, leasing_immobiliare_variabile, leasing_auto, scoperti_senza_affidamento), trimestre: str \| None = None ('AAAA-Qn')`
- Fonte normativa dichiarata: Art. 644 c.p.; L. 108/1996; DL 70/2011 conv. L. 106/2011; TEGM trimestrale
- Casi di prova:
  - Mutuo a tasso fisso appena sotto la soglia: `{"tasso_applicato": 9.26, "tipo_operazione": "mutuo_prima_casa", "trimestre": "2026-Q3"}` → atteso: TEGM 4,21% (da riscontrare sul DM MEF): soglia min(4,21 x 1,25 + 4; 4,21 + 8) = 9,2625%; 9,26 non usurario.
  - Mutuo a tasso fisso appena sopra la soglia: `{"tasso_applicato": 9.27, "tipo_operazione": "mutuo_prima_casa", "trimestre": "2026-Q3"}` → atteso: Soglia 9,2625%: 9,27 usurario (confine al millesimo).
  - Credito revolving con tetto di 8 punti: `{"tasso_applicato": 24.22, "tipo_operazione": "carte_revolving", "trimestre": "2026-Q3"}` → atteso: TEGM 16,21%: soglia min(24,2625; 24,21) = 24,21% (prevale il tetto); 24,22 usurario.
  - Credito revolving con formula prevalente (TEGM sotto 16%): `{"tasso_applicato": 23.72, "tipo_operazione": "carte_revolving", "trimestre": "2026-Q1"}` → atteso: TEGM 15,77%: soglia min(23,7125; 23,77) = 23,7125%; 23,72 usurario.
  - Categoria non gestita: `{"tasso_applicato": 10, "tipo_operazione": "anticipi_sconti", "trimestre": "2026-Q3"}` → atteso: Atteso errore per categoria non gestita; il tool usa in silenzio Prestiti personali (soglia 18,60%).
  - Trimestre della pattuizione non in tabella: `{"tasso_applicato": 10, "tipo_operazione": "credito_personale", "trimestre": "2024-Q1"}` → atteso: TEGM del I trimestre 2024 da leggere dalla fonte (DM MEF di dicembre 2023); il tool usa il 2026-Q3 senza avviso.

## tmview.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `cerca_marchi` | ricerca_online | smoke_live | nessuna (media) | TMview (www.tmdn.org/tmview) e banca dati marchi dell'Ufficio italiano brevetti e marchi | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: filtri ufficio e classi; mappatura degli stati sui codici TMview (solo 'Registered' verificato dal vivo secondo il codice); risposta alla protezione anti-bot (invito a riprovare) con chiamate distanziate di almeno un secondo. |
| `leggi_marchio` | ricerca_online | smoke_live | nessuna (alta) | TMview, scheda del marchio IT502013902128590; banca dati dell'Ufficio italiano brevetti e marchi | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: campi della scheda rispetto all'ufficio d'origine; messaggio per un ST13 inesistente (non trovato, non 'non raggiungibile'). |
| `verifica_anteriorita_marchio` | ricerca_online | smoke_live | nessuna (media) | TMview, stessa ricerca con gli stessi filtri; banca dati dell'Ufficio italiano brevetti e marchi | Assente dai paragrafi 5 e 7: né corretto né declassato. Da confermare: la normalizzazione (solo lettere e cifre, minuscole) che rende identici 'FUORI CORSO' e 'FUORICORSO'; avvertenza finale sempre presente, anche con zero risultati, che il tool tratta come esito positivo. |

### `cerca_marchi`

Ricerca di marchi registrati o depositati su TMview (Ufficio dell'Unione europea per la proprietà intellettuale e rete europea dei marchi): Ufficio italiano brevetti e marchi, EUIPO, OMPI e circa 75 uffici, con filtri per ufficio, classi di Nizza e stato.

- Parametri: `query: str; uffici: str = '' (codici separati da virgola: IT, EM, WO, ...); classi_nizza: str = '' (1-45 separate da virgola); stato: 'registrato' \| 'depositato' \| 'scaduto' \| 'terminato' \| '' = ''; max_risultati: int = 20 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: TMview (tmdn.org)
- Casi di prova:
  - Marchio noto: `{"query": "FUORI CORSO", "uffici": "IT", "max_risultati": 20}` → atteso: almeno un marchio italiano con ST13 che inizia per 'IT', titolare, classi e date; se compare FUORICORSO, ST13 IT502013902128590 in classe 25
  - Classe di Nizza non valida: `{"query": "FUORI CORSO", "classi_nizza": "46"}` → atteso: errore di validazione: classe di Nizza non valida (1-45), nessuna chiamata di rete

### `leggi_marchio`

Scheda completa di un marchio da TMview tramite ST13: titolare, rappresentante, prodotti e servizi per classe di Nizza, pubblicazioni, date e stato.

- Parametri: `st13: str`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: TMview (tmdn.org)
- Casi di prova:
  - Marchio noto: `{"st13": "IT502013902128590"}` → atteso: scheda 'FUORICORSO', ufficio italiano, titolare presente, classe 25 tra prodotti e servizi, date di deposito e registrazione (caso del test live esistente)
  - ST13 inesistente: `{"st13": "IT500000000000000"}` → atteso: messaggio di marchio non trovato su TMview; se riportato come fonte non raggiungibile, la classificazione va corretta

### `verifica_anteriorita_marchio`

Verifica preliminare di anteriorità su TMview: separa i marchi identici (denominazione uguale ignorando maiuscole, spazi e punteggiatura) dai simili, con avvertenza che non valuta somiglianza fonetica, concettuale o grafica.

- Parametri: `nome: str; classi_nizza: str = ''; uffici: str = ''; max_risultati: int = 50 (1-50)`
- Fonte normativa dichiarata: Nessuna riga Vigenza; fonte: TMview
- Casi di prova:
  - Nome con marchio identico noto: `{"nome": "FUORI CORSO", "classi_nizza": "25", "uffici": "IT"}` → atteso: FUORICORSO (IT502013902128590) nella sezione dei marchi identici a rischio alto; eventuali marchi contenenti il termine tra i simili; avvertenza finale sulla verifica preliminare
  - Nome senza anteriorità: `{"nome": "ZXQWVJ KRTPLM", "classi_nizza": "25", "uffici": "IT"}` → atteso: nessun marchio anteriore trovato nella classe 25, con l'avvertenza che la verifica non sostituisce una ricerca professionale

## varie.py

| Tool | Tipo | Strategia | Pagina del sito (confidenza) | Fonte alternativa | Note |
|---|---|---|---|---|---|
| `backlog_riconciliazione` | utilita | non_applicabile | nessuna pagina del sito |  | Utilità interna, non toccata dall'audit di settembre 2026. Utile come controllo incrociato: allo stato attuale elenca codici_ateco, la tabella della voce aperta nel par. 7 dell'audit. |
| `calcolo_eta_anagrafica` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-eta-anagrafica.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php | artt. 2 e 2963 c.c. (maggiore età e computo ad anni e mesi), via cite_law | Non toccato dall'audit di settembre 2026. Nessun calcolatore dell'età tra i risultati di ricerca raccolti nella sessione; la ricerca mirata non è stata possibile (budget di ricerca esaurito): verificare in Fase 0; il contagiorni del sito permette di riscontrare i giorni al prossimo compleanno e, se la mostra, la differenza in anni, mesi e giorni; i punti critici si decidono sulla norma. Difetti rilevati: giorni negativi come in calcolo_tempo_trascorso (stesso codice); per i nati il 29 febbraio l'età e il prossimo_compleanno sono incoerenti (il 28/02 dell'anno non bisestile il tool dice 17 anni ma indica il prossimo compleanno all'anno seguente). Fase 0: calcolatore dell'eta' anagrafica (da data di nascita o codice fiscale) presente sul sito. |
| `calcolo_tempo_trascorso` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php (alta) | art. 2963 co. 4-5 c.c. (computo a mesi e ad anni), via cite_law | Non toccato dall'audit di settembre 2026. Pagina emersa dalla ricerca 'site:avvocatoandreani.it/servizi calcolo giorni tra date': confronta con certezza i giorni totali; la scomposizione in anni, mesi e giorni va letta dal sito se presente. Difetto rilevato: giorni negativi quando il giorno finale è minore di quello iniziale e il mese precedente è più corto (31/01 -> 01/03 dà '1 mesi, -1 giorni'). Il benchmark deve confermare la correzione secondo il computo civile dell'art. 2963 c.c. Fase 0: pagina confermata; la pagina 'tempo trascorso tra ore' del sito riguarda le ore, non le date. |
| `codice_fiscale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo_codice_fiscale.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/ricerca-codici-catastali-comuni.php | Agenzia delle Entrate: regole di calcolo del codice fiscale (DM 12/03/1974 e DM 23/12/1976, omocodia e carattere di controllo) ed elenco ISTAT dei codici catastali | Non toccato dall'audit di settembre 2026 (né par. 5 né par. 7); la tabella comuni è stata riconciliata con l'elenco ISTAT nella 2.14 (143 codici catastali corretti; 643 comuni più 52 stati esteri). La pagina del sito emersa dalle ricerche della sessione è la ricerca dei codici catastali (query 'site:avvocatoandreani.it/servizi codici tributo F24 ricerca'): serve a riscontrare il segmento comune (posizioni 12-15), il resto si verifica sull'algoritmo. Il calcolatore completo guidato dalla suite esistente (path calcolo_codice_fiscale.php in tests/comparison/test_codice_fiscale.py) non è emerso dalle ricerche e il budget di ricerca è esaurito: riscontrarlo in Fase 0 e, se confermato, usarlo come pagina principale. Difetti rilevati eseguendo il tool: KeyError con vocali accentate (nome Nicolò) perché la lettera accentata è trattata come consonante; omocodia non gestita in generazione. Il benchmark deve confermare la correzione delle vocali accentate e i codici dei comuni corretti nella 2.14 (es. Ercolano H243). Fase 0: il calcolatore completo del codice fiscale esiste (come nella suite esistente); la ricerca dei codici catastali resta per il segmento comune. |
| `conta_giorni` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-giorni-lavorativi-festivi.php (alta) | art. 2 L. 260/1949 e L. 8 ottobre 2025 n. 151 (festa del 4 ottobre dal 2026), via cite_law | Non toccato dall'audit di settembre 2026. Pagine emerse dalla ricerca 'site:avvocatoandreani.it/servizi calcolo giorni tra date': questa per lavorativi e festivi, https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php per il tipo calendario (già guidata da tests/comparison/test_conta_giorni.py). La tabella festività include San Francesco dal 2026: la L. 8 ottobre 2025 n. 151 (GU n. 236 del 10/10/2025) è emersa dalle ricerche della sessione, da riscontrare con cite_law. Punti da documentare: il sabato è non lavorativo; 'festivi' conta solo le festività (Pasqua compresa) e non le domeniche, mentre l'art. 2 L. 260/1949 considera festive tutte le domeniche; nessuna festa patronale. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `decodifica_codice_fiscale` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/decodifica_codice_fiscale.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/ricerca-codici-catastali-comuni.php | Agenzia delle Entrate (DM 12/03/1974, DM 23/12/1976: carattere di controllo e tabella di omocodia) ed elenco ISTAT dei codici catastali | Non toccato dall'audit di settembre 2026. La pagina del sito (emersa dalle ricerche della sessione) riscontra la decodifica codice catastale -> comune, che è la parte dipendente dalla tabella; carattere di controllo, sesso e data si verificano sull'algoritmo. Difetto rilevato: l'euristica del secolo (00-29 -> 2000) produce date di nascita future rispetto alla data di riferimento (anno 29 -> 2029). Il benchmark deve confermare l'omocodia (lettere L-V al posto delle cifre) e la decodifica dei codici corretti nella 2.14. Fase 0: pagina di decodifica (codice fiscale inverso) presente sul sito. |
| `decurtazione_punti_patente` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/tabella-decurtazione-punti-patente.php (alta) | tabella allegata all'art. 126-bis e artt. 142, 145, 173, 186 D.Lgs. 285/1992 nel testo vigente dopo la L. 177/2024, via cite_law | Corretto dall'audit di settembre 2026, par. 5: la riforma era attribuita al D.Lgs. 36/2023 (codice dei contratti pubblici), ora L. 25 novembre 2024 n. 177. Tabella violazioni_patente riconciliata il 20/09/2026 (precedenza 5, stop 6, sorpasso 3, assicurazione 5, distanza e contromano sui commi base, velocità per commi 7-9-bis). Nessuna pagina sui punti patente tra i risultati di ricerca raccolti nella sessione; la ricerca mirata non è stata possibile (budget di ricerca esaurito): verificare in Fase 0. Il benchmark deve confermare i punti sulla tabella vigente e il testo delle sanzioni accessorie: per 'cellulare' il dataset indica 'sospensione 1-3 mesi, recidiva 3-6 mesi', da riscontrare sull'art. 173 co. 3-bis come riscritto dalla L. 177/2024 e sulla sospensione breve introdotta dalla stessa legge (art. 218-ter, da verificare); importi pecuniari soggetti all'aggiornamento biennale dell'art. 195 co. 3. Fase 0: il sito pubblica la tabella 2026 dei punti (non un calcolatore); i punteggi del tool si confrontano con la tabella, la norma resta la fonte. |
| `prescrizione_diritti` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-diritti.php (alta) | artt. 2934-2969 c.c., in particolare art. 2963 (computo), via cite_law | Non toccato dall'audit di settembre 2026. Pagina 'Calcolo Prescrizione Diritti' emersa dalle ricerche della sessione (per es. 'site:avvocatoandreani.it/servizi calcolo prescrizione reati'); tests/comparison/test_prescrizione.py riguarda invece prescrizione_reato ed è saltato per il login. Difetto rilevato: il tool non applica l'art. 2963 co. 3 c.c. (termine che scade in giorno festivo prorogato al giorno seguente non festivo). Per la prescrizione sostanziale non opera la sospensione feriale (la L. 742/1969 riguarda i termini processuali) e il sabato non è festivo. Eseguire con LEGAL_TODAY=2026-09-25 per il campo 'prescritto'. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `ricerca_codici_ateco` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/ricerca-codici-ateco.php (alta) | ISTAT, classificazione ATECO 2025 e raccordo ATECO 2007-2025; Allegato 4 L. 190/2014 (testo L. 208/2015) per i coefficienti, via cite_law | Voce aperta nell'audit di settembre 2026, par. 7 (classificazione ATECO 2025, confidenza alta; tabella già da_verificare): la risposta degrada a STIMATO. Pagina 'Ricerca Codice ATECO 2025' emersa dalla ricerca 'site:avvocatoandreani.it/servizi calcolo regime forfettario'. Il benchmark deve riconciliare i codici con ATECO 2025 sul sito e su ISTAT e i coefficienti con l'Allegato 4: sette voci divergono dai gruppi di settore (01.11.10: 40 invece di 67; 25.11.00: 86 invece di 67; 45.20.10: 67 invece di 40; 68.20.02: 40 invece di 86; 77.11.00: 40 invece di 67; 79.11.00: 40 invece di 67; 88.91.00: 67 invece di 78). Dopo la riconciliazione aggiornare il blocco _vintage. Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |
| `scorporo_iva` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/scorporo-iva-calcoli-percentuali-frequenti.php (alta) ; secondarie: https://www.avvocatoandreani.it/servizi/calcolatrice_scorporo.php | artt. 13 e 16 DPR 633/1972 e Tabella A (aliquote), via cite_law | Non toccato dall'audit di settembre 2026. Pagina 'Scorporo IVA e Calcolo IVA Inversa' emersa dalla ricerca 'site:avvocatoandreani.it/servizi calcolo fattura avvocato ritenuta cassa iva'. La suite esistente (tests/comparison/test_scorporo_iva.py) non guida il sito e verifica solo l'aritmetica: ora il confronto diretto è possibile. Convenzione del tool: imponibile arrotondato, IVA per differenza (somma sempre pari all'importo ivato); verificare la convenzione di arrotondamento del sito. Fase 0: pagina confermata; seconda pagina di scorporo per la fatturazione. |
| `tasso_alcolemico` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/calcolo-tasso-alcolemico-teorico.php (alta) ; secondarie: https://www.avvocatoandreani.it/utility/etilometro-online.php | art. 186 co. 2 D.Lgs. 285/1992 via cite_law (fasce 'superiore a ... e non superiore a ...' e sanzioni) | Non toccato dall'audit di settembre 2026. Nessuna pagina sul tasso alcolemico tra i risultati di ricerca raccolti nella sessione; la ricerca mirata non è stata possibile (budget di ricerca esaurito): verificare in Fase 0. La stima di Widmark (coefficienti 0,70/0,60, eliminazione 0,15 g/l/h, -30% a stomaco pieno) non è una regola di legge: il benchmark verifica fasce e sanzioni. Difetto rilevato: i confini delle fasce sono invertiti rispetto all'art. 186 co. 2 (il tool usa 'minore di'): 0,5 finisce in lett. a), 0,8 in lett. b), 1,5 in lett. c). Non gestisce l'art. 186-bis (neopatentati, conducenti under 21 e professionali: tasso superiore a zero). Fase 0: calcolatore presente sul sito (formula di Widmark); strategia portata da solo_norma ad andreani, le fasce dell'art. 186 C.d.S. restano da riscontrare con cite_law. |
| `verbale_mensile` | utilita | non_applicabile | nessuna pagina del sito |  | Utilità interna, non toccata dall'audit di settembre 2026: nessun riscontro normativo. Basta un controllo di forma con LEGAL_TODAY fissato. |
| `verifica_iban` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/verifica-codice-iban-nazionale-estero.php (alta) ; secondarie: https://www.avvocatoandreani.it/utility/calcolo-cin-iban.php | SWIFT IBAN Registry (autorità di registrazione ISO 13616: struttura IT = 2 cifre di controllo + CIN + ABI + CAB + conto) e algoritmo ISO 7064 mod 97-10; CIN secondo le regole ABI/CBI | Non toccato dall'audit di settembre 2026. Nessuna pagina IBAN del sito tra i risultati di ricerca raccolti nella sessione; la ricerca mirata non è stata possibile (budget di ricerca esaurito): verificare in Fase 0. Il CIN non è verificato separatamente (l'errore emerge solo dal mod 97) e gli IBAN non italiani sono respinti per progetto: il benchmark deve documentare entrambe le scelte. Fase 0: il sito ha un verificatore IBAN interno; strategia portata da fonte_ufficiale ad andreani (il registro SWIFT resta la fonte per la struttura). |
| `verifica_partita_iva` | calcolo | andreani | https://www.avvocatoandreani.it/servizi/verifica-partita-iva.php (alta) | Agenzia delle Entrate, servizio di verifica della partita IVA; art. 35 DPR 633/1972 e DM 23/12/1976 (7 cifre di matricola, 3 di codice ufficio, 1 di controllo) | Non toccato dall'audit di settembre 2026. Pagina emersa dalle ricerche della sessione (query 'site:avvocatoandreani.it/servizi calcolo fattura agenti di commercio Enasarco'). Difetti rilevati: il campo codice_ufficio restituisce le prime due cifre invece delle cifre 8-10; nessun controllo sul codice ufficio, per cui 00000000000 e 12345678903 risultano valide. Il benchmark deve confermare come il sito tratta i codici ufficio non attribuiti (python-stdnum ammette 001-100, 120, 121, 888, 999: elenco da riscontrare sulla fonte). Fase 0: pagina aperta con Playwright e confermata (calcolatore con modulo). |

### `backlog_riconciliazione`

Elenca le tabelle dati non verificate o scadute, ordinate per quanto bloccano (uso statico e rifiuti osservati).

- Parametri: `nessun parametro`
- Fonte normativa dichiarata: fonte dati: blocchi _vintage di src/data/*.json; nessuna norma
- Casi di prova:
  - Stato attuale del backlog: `{}` → atteso: 2 tabelle non_verificata: codici_ateco e tribunali_competenti, ciascuna con fonte, uso statico e azione; verbale_rifiuti con disponibile false se il ledger è spento

### `calcolo_eta_anagrafica`

Calcola l'età anagrafica in anni, mesi e giorni e la data del prossimo compleanno.

- Parametri: `data_nascita: str (YYYY-MM-DD), data_riferimento: str \| None = None (se omessa: oggi da _clock)`
- Fonte normativa dichiarata: nessuna riga Vigenza (calcolo di calendario)
- Casi di prova:
  - Nato il 29 febbraio, anno di riferimento non bisestile: `{"data_nascita": "2008-02-29", "data_riferimento": "2026-02-28"}` → atteso: 18 anni compiuti il 28/02/2026 se si applica per analogia l'art. 2963 co. 5 c.c. (maggiore età, art. 2 c.c.); in ogni caso prossimo_compleanno coerente con l'età; oggi il tool dà 17 anni, 11 mesi, 30 giorni con prossimo compleanno 2027-02-28
  - Mese precedente più corto: `{"data_nascita": "1990-01-31", "data_riferimento": "2025-03-01"}` → atteso: 35 anni, 1 mese, 1 giorno (mese compiuto il 28/02/2025); oggi il tool restituisce -2 giorni
  - Vigilia della maggiore età: `{"data_nascita": "2008-09-25", "data_riferimento": "2026-09-24"}` → atteso: 17 anni, 11 mesi, 30 giorni; prossimo compleanno 2026-09-25 (1 giorno): maggiore età dal 25/09/2026 (art. 2 c.c.)

### `calcolo_tempo_trascorso`

Calcola il tempo trascorso tra due date in anni, mesi e giorni e il totale dei giorni.

- Parametri: `data_inizio: str (YYYY-MM-DD), data_fine: str \| None = None (se omessa: oggi da _clock)`
- Fonte normativa dichiarata: nessuna riga Vigenza (calcolo di calendario)
- Casi di prova:
  - Da fine gennaio a marzo, anno bisestile: `{"data_inizio": "2024-01-31", "data_fine": "2024-03-01"}` → atteso: 0 anni, 1 mese, 1 giorno (il mese dal 31/01 si compie il 29/02/2024, art. 2963 co. 5 c.c.); 30 giorni totali; oggi il tool restituisce -1 giorni
  - Da fine gennaio a marzo, anno non bisestile: `{"data_inizio": "2023-01-31", "data_fine": "2023-03-01"}` → atteso: 0 anni, 1 mese, 1 giorno (mese compiuto il 28/02/2023); 29 giorni totali; oggi il tool restituisce -2 giorni
  - Dal 29 febbraio al 28 febbraio dell'anno dopo: `{"data_inizio": "2020-02-29", "data_fine": "2021-02-28"}` → atteso: 1 anno esatto secondo l'art. 2963 co. 5 (manca il 29 febbraio: si compie l'ultimo giorno del mese); 365 giorni totali; il tool dà 0 anni, 11 mesi, 30 giorni: documentare la convenzione del sito
  - Dieci anni con due anni bisestili: `{"data_inizio": "2016-09-25", "data_fine": "2026-09-25"}` → atteso: 10 anni, 0 mesi, 0 giorni; 3652 giorni totali (29/02/2020 e 29/02/2024)

### `codice_fiscale`

Genera il codice fiscale di 16 caratteri (cognome, nome, data e sesso, codice catastale, carattere di controllo).

- Parametri: `cognome: str, nome: str, data_nascita: str (YYYY-MM-DD), sesso: str ('M'\|'F'), comune_nascita: str, codice_catastale: str \| None = None, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: DM 12/03/1974 (Agenzia delle Entrate); tabella comuni e stati esteri
- Casi di prova:
  - Caso base maschile, Roma: `{"cognome": "Rossi", "nome": "Mario", "data_nascita": "1985-06-15", "sesso": "M", "comune_nascita": "ROMA"}` → atteso: RSSMRA85H15H501D (giugno = H, Roma = H501, carattere di controllo D ricalcolato con le tabelle dispari/pari)
  - Femminile: giorno più 40, gennaio: `{"cognome": "Bianchi", "nome": "Maria", "data_nascita": "1990-01-01", "sesso": "F", "comune_nascita": "MILANO"}` → atteso: BNCMRA90A41F205J (giorno 01 + 40 = 41, gennaio = A, Milano = F205)
  - Nome con vocale accentata: `{"cognome": "Rossi", "nome": "Nicolò", "data_nascita": "1985-06-15", "sesso": "M", "comune_nascita": "ROMA"}` → atteso: RSSNCL85H15H501M (la o accentata è una vocale: consonanti N, C, L); oggi il tool solleva KeyError
  - Cognome corto, 29 febbraio, nato all'estero: `{"cognome": "Fo", "nome": "Ugo", "data_nascita": "2000-02-29", "sesso": "M", "comune_nascita": "GERMANIA"}` → atteso: FOXGUO00B29Z112N (cognome completato con X, nome con consonanti e poi vocali, Germania = Z112)
  - Comune fuori dal sottoinsieme incluso, poi codice passato dal chiamante: `{"cognome": "Rossi", "nome": "Mario", "data_nascita": "1980-01-01", "sesso": "M", "comune_nascita": "Monte San Pietro"}` → atteso: senza codice_catastale: errore 'non trovato nel database'; con il codice letto dalla ricerca codici catastali del sito il CF è RSSMRA80A01 + codice + carattere di controllo ricalcolato (codice da leggere dal sito)

### `conta_giorni`

Conta i giorni tra due date (dies a quo escluso): di calendario, lavorativi (lunedì-venerdì esclusi i festivi) o festivi.

- Parametri: `data_inizio: str (YYYY-MM-DD), data_fine: str (YYYY-MM-DD), tipo: str = 'calendario' ('calendario'\|'lavorativi'\|'festivi'), accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: L. 260/1949 e ss. (festività nazionali vigenti)
- Casi di prova:
  - Calendario a cavallo di agosto: `{"data_inizio": "2026-07-31", "data_fine": "2026-09-01", "tipo": "calendario"}` → atteso: 32 giorni (31 luglio escluso: 31 di agosto più 1 settembre)
  - Lavorativi a cavallo di agosto, Ferragosto di sabato: `{"data_inizio": "2026-07-31", "data_fine": "2026-09-01", "tipo": "lavorativi"}` → atteso: 22 (21 giorni feriali in agosto 2026, il 15 agosto cade di sabato, più martedì 1 settembre)
  - 4 ottobre prima dell'istituzione della festa: `{"data_inizio": "2024-10-01", "data_fine": "2024-10-08", "tipo": "lavorativi"}` → atteso: 5 (2, 3, 4, 7 e 8 ottobre: il 4 ottobre 2024 è un venerdì lavorativo)
  - 4 ottobre festivo di lunedì (L. 151/2025): `{"data_inizio": "2027-10-01", "data_fine": "2027-10-08", "tipo": "lavorativi"}` → atteso: 4 (5, 6, 7 e 8 ottobre: il 4 ottobre 2027 è lunedì festivo)
  - Festivi di un anno intero: `{"data_inizio": "2026-01-01", "data_fine": "2026-12-31", "tipo": "festivi"}` → atteso: secondo l'art. 2 L. 260/1949 (domeniche più festività) 61 = 52 domeniche + 9 festività infrasettimanali; il tool restituisce 12 (sole festività, comprese quelle di domenica); convenzione del sito da leggere dal sito
  - Lavorativi a cavallo di Pasqua: `{"data_inizio": "2026-04-01", "data_fine": "2026-04-10", "tipo": "lavorativi"}` → atteso: 6 (2, 3, 7, 8, 9 e 10 aprile: Pasqua 5 aprile e Lunedì dell'Angelo 6 aprile esclusi)

### `decodifica_codice_fiscale`

Decodifica un codice fiscale: validità del carattere di controllo, sesso, data di nascita (anno stimato), comune dal codice catastale, omocodia.

- Parametri: `codice_fiscale: str (16 caratteri, spazi ignorati), mappa_comuni: dict \| None = None, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: DM 12/03/1974 (Agenzia delle Entrate)
- Casi di prova:
  - CF ordinario valido: `{"codice_fiscale": "RSSMRA85H15H501D"}` → atteso: carattere di controllo valido; sesso M; nascita 1985-06-15; comune ROMA (H501)
  - CF omocodico (cifra 1 sostituita da M): `{"codice_fiscale": "RSSMRA85H15H50MV"}` → atteso: valido (controllo V calcolato sulla stringa omocodica); comune H501 ROMA dopo la de-omocodia; nascita 1985-06-15
  - Anno a due cifre ambiguo: `{"codice_fiscale": "RSSMRA29A01H501P"}` → atteso: nascita 1929-01-01: il 2029 sarebbe successivo alla data di riferimento (25/09/2026); oggi il tool restituisce 2029-01-01
  - Codice catastale corretto nella 2.14: `{"codice_fiscale": "RSSMRA80A01H243X"}` → atteso: valido; comune ERCOLANO (H243), da riscontrare sulla ricerca codici catastali del sito

### `decurtazione_punti_patente`

Restituisce punti decurtati, sanzione pecuniaria e sanzioni accessorie per una violazione del Codice della Strada (ricerca per chiave o parola).

- Parametri: `violazione: str (chiave o parola chiave, es. 'cellulare', 'eccesso_velocita_40'), tabella_violazioni: dict \| None = None, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: art. 126-bis D.Lgs. 285/1992 e tabella allegata, testo L. 25 novembre 2024 n. 177
- Casi di prova:
  - Velocità oltre 60 km/h: `{"violazione": "eccesso_velocita_oltre_60"}` → atteso: 10 punti (art. 142 co. 9-bis nella tabella dell'art. 126-bis); sospensione 6-12 mesi; sanzione 845-3.382 euro, importi da leggere dalla fonte
  - Ricerca per parola chiave sulle quattro fasce di velocità: `{"violazione": "velocita"}` → atteso: quattro voci: co. 7 (fino a 10 km/h, 0 punti), co. 8 (oltre 10 e fino a 40, 3 punti), co. 9 (oltre 40 e fino a 60, 6 punti), co. 9-bis (oltre 60, 10 punti)
  - Uso del telefono alla guida dopo la riforma: `{"violazione": "cellulare"}` → atteso: punti, sanzione pecuniaria e sospensione da leggere dalla fonte (art. 173 co. 3-bis nel testo L. 177/2024 e tabella art. 126-bis); il dataset indica 5 punti
  - Mancata precedenza generica e stop: `{"violazione": "precedenza"}` → atteso: 5 punti (art. 145 co. 10); la voce 'stop' (art. 145 co. 5) vale 6 punti
  - Violazione assente dal dataset: `{"violazione": "monopattino"}` → atteso: errore 'non trovata' con l'elenco delle chiavi disponibili

### `prescrizione_diritti`

Calcola la data di prescrizione di un diritto civile per tipo e data del fatto e indica se è già prescritto.

- Parametri: `tipo_diritto: str ('ordinaria'\|'risarcimento_danni'\|'risarcimento_rca'\|'diritti_lavoro'\|'crediti_professionisti'\|'canoni_locazione'\|'contributi_previdenziali'\|'vizi_vendita'\|'garanzia_appalto'), data_evento: str (YYYY-MM-DD)`
- Fonte normativa dichiarata: artt. 2946, 2947, 2948, 2956, 1495, 1667 c.c.; art. 3 co. 9 L. 335/1995
- Casi di prova:
  - Scadenza di domenica, festa di San Francesco: `{"tipo_diritto": "ordinaria", "data_evento": "2016-10-04"}` → atteso: 2026-10-05: il 04/10/2026 è domenica e festa nazionale, proroga ex art. 2963 co. 3 c.c.; oggi il tool restituisce 2026-10-04
  - Scadenza a Ferragosto di domenica, nessuna sospensione feriale: `{"tipo_diritto": "risarcimento_danni", "data_evento": "2022-08-15"}` → atteso: 2027-08-16 (15/08/2027 domenica e festivo: art. 2963 co. 3; la sospensione feriale non si applica); oggi il tool restituisce 2027-08-15
  - Termine biennale RCA dal 29 febbraio: `{"tipo_diritto": "risarcimento_rca", "data_evento": "2024-02-29"}` → atteso: 2026-02-28 (art. 2947 co. 2; manca il 29 febbraio: ultimo giorno del mese, art. 2963 co. 5; sabato non festivo); prescritto: sì alla data 25/09/2026
  - Scadenza di sabato: `{"tipo_diritto": "canoni_locazione", "data_evento": "2021-09-26"}` → atteso: 2026-09-26 (art. 2948 n. 3; il sabato non proroga la prescrizione: la regola dell'art. 155 co. 5 c.p.c. vale per i termini processuali); prescritto: no, 1 giorno mancante al 25/09/2026
  - Prescrizione presuntiva triennale: `{"tipo_diritto": "crediti_professionisti", "data_evento": "2023-09-25"}` → atteso: 2026-09-25 (art. 2956 n. 2); non prescritto il 25/09/2026, si compie allo spirare del giorno (art. 2963 co. 2)

### `ricerca_codici_ateco`

Cerca codici ATECO per parola chiave con il coefficiente di redditività del regime forfettario.

- Parametri: `keyword: str, accetta_precisione: str \| None = None ('INDICATIVO'\|'STIMATO', aggiunto da @sourced)`
- Fonte normativa dichiarata: ATECO 2007 (agg. 2022); Allegato 4 L. 190/2014 per i coefficienti
- Casi di prova:
  - Affitto di immobili propri: `{"keyword": "affitto"}` → atteso: coefficiente 86% (gruppo 'Costruzioni e attività immobiliari', divisioni 41-42-43 e 68); oggi 40; codice ATECO 2025 da leggere dal sito
  - Asili nido: `{"keyword": "asili"}` → atteso: coefficiente 78% (divisioni 86-87-88 nel gruppo delle attività professionali, sanitarie e di istruzione); oggi 67
  - Agenzie di viaggio: `{"keyword": "viaggio"}` → atteso: coefficiente 67% (divisione 79 in 'Altre attività economiche'); oggi 40
  - Avvocati: `{"keyword": "avvocat"}` → atteso: 69.10.10, coefficiente 78% (confermato); descrizione e codice ATECO 2025 da leggere dal sito
  - Commercio elettronico: `{"keyword": "e-commerce"}` → atteso: coefficiente 40% (47.9, commercio) confermato; il codice 47.91.10 va riscontrato perché ATECO 2025 ha ristrutturato la classe: da leggere dal sito

### `scorporo_iva`

Scorpora l'IVA da un importo ivato restituendo imponibile e imposta, arrotondati al centesimo.

- Parametri: `importo_ivato: float, aliquota: float = 22 (4\|5\|10\|22)`
- Fonte normativa dichiarata: DPR 633/1972, aliquote 4, 5, 10 e 22%
- Casi di prova:
  - Aliquota ordinaria, importo tondo: `{"importo_ivato": 122, "aliquota": 22}` → atteso: imponibile 100,00; IVA 22,00
  - Aliquota ordinaria con arrotondamento: `{"importo_ivato": 1000, "aliquota": 22}` → atteso: imponibile 819,67 (1000/1,22 = 819,672); IVA 180,33
  - Aliquota minima 4%: `{"importo_ivato": 100, "aliquota": 4}` → atteso: imponibile 96,15; IVA 3,85
  - Aliquota 5% (Tabella A parte II-bis): `{"importo_ivato": 105, "aliquota": 5}` → atteso: imponibile 100,00; IVA 5,00
  - Aliquota 10% con decimali: `{"importo_ivato": 1234.56, "aliquota": 10}` → atteso: imponibile 1.122,33; IVA 112,23
  - Importo minimo: `{"importo_ivato": 0.01, "aliquota": 22}` → atteso: imponibile 0,01; IVA 0,00 (da confrontare con l'arrotondamento del sito)
  - Aliquota non prevista: `{"importo_ivato": 100, "aliquota": 21}` → atteso: errore: aliquota non tra 4, 5, 10, 22

### `tasso_alcolemico`

Stima il tasso alcolemico con la formula di Widmark e indica la fascia sanzionatoria dell'art. 186 CdS.

- Parametri: `sesso: str ('M'\|'F'), peso_kg: float, unita_alcoliche: float (1 UA = 12 g), ore_trascorse: float, stomaco_pieno: bool = False`
- Fonte normativa dichiarata: art. 186 D.Lgs. 285/1992, soglie 0,5 / 0,8 / 1,5 g/l
- Casi di prova:
  - Esattamente 0,5 g/l: `{"sesso": "M", "peso_kg": 60, "unita_alcoliche": 1.75, "ore_trascorse": 0}` → atteso: tasso 0,50 g/l (21 g / (60 x 0,70)); nessuna fascia: la lett. a) richiede un tasso superiore a 0,5; oggi il tool indica lett. a)
  - Esattamente 0,8 g/l: `{"sesso": "M", "peso_kg": 60, "unita_alcoliche": 2.8, "ore_trascorse": 0}` → atteso: tasso 0,80 g/l: lett. a) (non superiore a 0,8): illecito amministrativo, sospensione 3-6 mesi; oggi il tool indica lett. b)
  - Esattamente 1,5 g/l: `{"sesso": "M", "peso_kg": 60, "unita_alcoliche": 5.25, "ore_trascorse": 0}` → atteso: tasso 1,50 g/l: lett. b) (ammenda 800-3.200 euro, arresto fino a 6 mesi, sospensione 6 mesi-1 anno); oggi il tool indica lett. c)
  - Donna, un'ora dopo: `{"sesso": "F", "peso_kg": 60, "unita_alcoliche": 3, "ore_trascorse": 1}` → atteso: picco 1,00 g/l (36 g / 36), attuale 0,85 g/l: lett. b)

### `verbale_mensile`

Report mensile dei rifiuti e delle accettazioni registrati dal verbale LEGAL_REFUSAL_LEDGER, con confronto mese su mese.

- Parametri: `months: int = 6 (1-24, valori fuori intervallo ricondotti ai limiti)`
- Fonte normativa dichiarata: fonte dati: refusals.jsonl del verbale; nessuna norma
- Casi di prova:
  - Verbale spento: `{"months": 6}` → atteso: {'disponibile': false} con il motivo 'impostare LEGAL_REFUSAL_LEDGER=on'
  - Finestra oltre il massimo con verbale attivo: `{"months": 30}` → atteso: con LEGAL_REFUSAL_LEDGER=on e LEGAL_TODAY=2026-09-25: 24 righe da 2024-10 a 2026-09, i mesi senza eventi a zero

### `verifica_iban`

Valida formalmente un IBAN italiano (27 caratteri, ISO 7064 mod 97) ed estrae CIN, ABI, CAB e conto.

- Parametri: `iban: str (27 caratteri IT; spazi e trattini ignorati)`
- Fonte normativa dichiarata: ISO 13616, formato IT a 27 caratteri
- Casi di prova:
  - IBAN di esempio valido: `{"iban": "IT60X0542811101000000123456"}` → atteso: valido; cifre di controllo 60 (mod 97 = 1); CIN X (ricalcolato); ABI 05428, CAB 11101, conto 000000123456
  - Stesso IBAN con spazi: `{"iban": "IT60 X054 2811 1010 0000 0123 456"}` → atteso: identico al caso precedente (spazi ignorati)
  - Cifre di controllo alterate: `{"iban": "IT61X0542811101000000123456"}` → atteso: non valido (le cifre di controllo corrette sono 60)
  - CIN alterato: `{"iban": "IT60Y0542811101000000123456"}` → atteso: non valido: CIN atteso X; il tool lo rileva solo tramite il mod 97, senza indicare il CIN
  - IBAN di San Marino (fuori ambito): `{"iban": "SM86U0322509800000000270100"}` → atteso: respinto perché non inizia con IT (scelta del tool); il mod 97 della stringa è comunque 1

### `verifica_partita_iva`

Valida formalmente una partita IVA italiana di 11 cifre con l'algoritmo di controllo.

- Parametri: `partita_iva: str (11 cifre)`
- Fonte normativa dichiarata: art. 35 DPR 633/1972 (struttura e algoritmo di controllo)
- Casi di prova:
  - P.IVA valida: `{"partita_iva": "00743110157"}` → atteso: valida (cifra di controllo 7); codice ufficio = cifre 8-10 = 015; oggi il tool restituisce '00'
  - Cifra di controllo errata: `{"partita_iva": "00743110158"}` → atteso: non valida: cifra di controllo attesa 7, presente 8
  - Checksum corretto ma codice ufficio non attribuito: `{"partita_iva": "12345678903"}` → atteso: non valida: codice ufficio 890 non attribuito (il solo checksum non basta); oggi il tool la dichiara valida
  - Tutti zeri: `{"partita_iva": "00000000000"}` → atteso: non valida (matricola nulla, codice ufficio 000); oggi il tool la dichiara valida


## Riscontro della Fase 0 (25/09/2026)

Con Playwright sono state aperte 252 pagine raggiungibili dalla home del sito (cartelle `/servizi/` e `/utility/`): 166 di tipo calcolatore, 11 di tipo pagina_informativa, 67 di tipo link_esterno, 4 di tipo duplicato_interno, 4 di tipo non_raggiungibile. Le pagine `link_esterno` rimandano a servizi di terzi (Agenzia delle Entrate, INPS, Cassa Depositi e Prestiti, iban.com, ACI) e non sono un calcolatore del sito. Per ogni calcolatore il catalogo `docs/benchmark/catalogo-andreani.json` registra URL, campi del modulo (nome, tipo, opzioni, etichetta), pulsante di invio ed etichette dei risultati ottenute con un invio a valori predefiniti.

Strategie dopo il riscontro: strutturale 26, smoke_live 54, andreani 119, solo_norma 15, fonte_ufficiale 10, non_applicabile 3.

### Voci del piano corrette

| Tool | Strategia prima | Strategia dopo | Pagina prima | Pagina verificata |
|---|---|---|---|---|
| `termini_separazione_divorzio` | solo_norma | andreani | nessuna | https://www.avvocatoandreani.it/servizi/calcolo-termini-separazione-divorzio.php |
| `menomazioni_plurime` | solo_norma | andreani | nessuna | https://www.avvocatoandreani.it/servizi/calcolo-riduzionistico-menomazioni-plurime.php |
| `tasso_alcolemico` | solo_norma | andreani | nessuna | https://www.avvocatoandreani.it/servizi/calcolo-tasso-alcolemico-teorico.php |
| `decurtazione_punti_patente` | solo_norma | andreani | nessuna | https://www.avvocatoandreani.it/servizi/tabella-decurtazione-punti-patente.php |
| `verifica_iban` | fonte_ufficiale | andreani | nessuna | https://www.avvocatoandreani.it/servizi/verifica-codice-iban-nazionale-estero.php |
| `costo_lavoro` | andreani | fonte_ufficiale | https://www.avvocatoandreani.it/servizi/calcolo-irpef.php | nessuna (il sito non ha un calcolatore) |
| `rendimento_buoni_postali` | andreani | fonte_ufficiale | https://www.avvocatoandreani.it/utility/calcolo-buoni-postali-fruttiferi.php | nessuna (il sito non ha un calcolatore) |
| `termini_deposito_atti_appello` | andreani | andreani | https://www.avvocatoandreani.it/servizi/termini-impugnazioni-civile-amministrativo-tributario.php | https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-atti-appello.php |
| `note_iscrizione_ruolo` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo_contributo_unificato.php | https://www.avvocatoandreani.it/servizi/note_iscrizione_a_ruolo.php |
| `sollecito_pagamento` | andreani | andreani | https://www.avvocatoandreani.it/servizi/interessi_moratori.php | https://www.avvocatoandreani.it/servizi/lettera-sollecito-pagamento.php |
| `danno_non_patrimoniale` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo_danno_biologico.php | https://www.avvocatoandreani.it/servizi/calcolo_danno_non_patrimoniale.php |
| `danno_biologico_macro` | andreani | andreani | https://www.avvocatoandreani.it/servizi/tabelle_danno_biologico_macropermanenti.php | https://www.avvocatoandreani.it/servizi/calcolo-danno-biologico-macropermanenti-tabella-unica.php |
| `detrazione_lavoro_dipendente` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-redditi-assimilati.php | https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-lavoro-dipendente.php |
| `codice_fiscale` | andreani | andreani | https://www.avvocatoandreani.it/servizi/ricerca-codici-catastali-comuni.php | https://www.avvocatoandreani.it/servizi/calcolo_codice_fiscale.php |
| `decodifica_codice_fiscale` | andreani | andreani | https://www.avvocatoandreani.it/servizi/ricerca-codici-catastali-comuni.php | https://www.avvocatoandreani.it/servizi/decodifica_codice_fiscale.php |
| `calcolo_eta_anagrafica` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php | https://www.avvocatoandreani.it/servizi/calcolo-eta-anagrafica.php |
| `modello_notula` | andreani | andreani | https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-procedimenti-monitori.html | https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php |
| `genera_quotazione_docx` | strutturale | strutturale | https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-procedimenti-monitori.html | https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php |
| `parcella_volontaria_giurisdizione` | andreani | andreani | https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-volontaria-giurisdizione.html | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php |
| `preventivo_volontaria_giurisdizione` | andreani | andreani | https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-volontaria-giurisdizione.html | https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php |
| `tariffe_mediazione` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo-spese-di-mediazione.php | https://www.avvocatoandreani.it/servizi/calcolo-costi-e-tariffe-mediazione-civile.php |
| `rivalutazione_tfr` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo-tfr.php | https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php |
| `inflazione_titoli_stato` | andreani | andreani | https://www.avvocatoandreani.it/servizi/calcolo-inflazione.php | https://www.avvocatoandreani.it/servizi/grafico-andamento-inflazione-titoli-di-stato.php |

Le altre voci toccate dal riscontro conservano pagina e strategia e ricevono solo pagine secondarie (tabelle pubblicate dal sito, duplicati interni) o la conferma della pagina: il dettaglio e' nel campo `riscontro_fase0` del file JSON.

### Calcolatori del sito senza tool corrispondente

Elencati come possibili nuovi tool, non da implementare in questo benchmark:

| Pagina | Titolo |
|---|---|
| https://www.avvocatoandreani.it/servizi/calcolatore-frazioni.php | Calcolatrice per Frazioni |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-ministeriali-civili.php | Compensi Avvocati 2012, Parametri Forensi Civili |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-ministeriali-penali.php | Compensi Avvocati 2012, Parametri Forensi Penali |
| https://www.avvocatoandreani.it/servizi/calcolo-ora-inizio-fine-attivita.php | Calcolo ora di inizio o fine attività in base alla durata. |
| https://www.avvocatoandreani.it/servizi/calcolo-percentuale.php | Calcolo Percentuale di un numero, percentuale inversa e molti altri calcoli correlati |
| https://www.avvocatoandreani.it/servizi/calcolo-proporzione.php | Calcolo Termine Incognito di una Proporzione |
| https://www.avvocatoandreani.it/servizi/calcolo-rimborso-chilometrico.php | Calcolo Rimborso Chilometrico Aci |
| https://www.avvocatoandreani.it/servizi/calcolo-tempo-trascorso-differenza-ore.php | Calcolo del tempo trascorso tra due o più ore (passato e futuro) |
| https://www.avvocatoandreani.it/servizi/calcolo-variazione-media-giornaliera.php | Calcolo Variazione Fatturato con Media Giornaliera e Proiezione |
| https://www.avvocatoandreani.it/servizi/calcolo_interessi_mora_appalti_opere_pubbliche.php | Calcolo Interessi di Mora Appalti Lavori Pubblici 2026 |
| https://www.avvocatoandreani.it/servizi/calcolo_parcella_penale_avvocati_tariffario_forense.php | Calcolo Parcella Penale con Tariffario Forense 2004 |
| https://www.avvocatoandreani.it/servizi/calcolo_percentuali_quote.php | Calcolo Percentuali da Valori Numerici |
| https://www.avvocatoandreani.it/servizi/calcolo_preventivo_online.php | Calcolo Preventivo Online |
| https://www.avvocatoandreani.it/servizi/cerca-app.php | Cerca la tua applicazione sul sito AvvocatoAndreani.it |
| https://www.avvocatoandreani.it/servizi/codice-della-strada.php | Codice della Strada aggiornato al 2026 - Consultazione Rapida |
| https://www.avvocatoandreani.it/servizi/codice-procedura-civile.php | Codice di Procedura Civile aggiornato al 2026 - Consultazione Rapida |
| https://www.avvocatoandreani.it/servizi/codice-procedura-penale.php | Codice di Procedura Penale aggiornato al 2026 - Consultazione Rapida |
| https://www.avvocatoandreani.it/servizi/conversione-ore-minuti-in-centesimi.php | Conversione minuti e secondi in centesimi |
| https://www.avvocatoandreani.it/servizi/conversione-unita-di-misura.php | Conversione Unità di Misura |
| https://www.avvocatoandreani.it/servizi/deposito-telematico-documenti.php | Modello per il Deposito Telematico di Documenti nel PCT |
| https://www.avvocatoandreani.it/servizi/fattura-elettronica-avvocati.php | Fattura Elettronica Gratis per Avvocati e Studi Legali |
| https://www.avvocatoandreani.it/servizi/fattura-elettronica.php | Fattura Elettronica per Professionisti e Lavoratori Autonomi |
| https://www.avvocatoandreani.it/servizi/ricerca-comuni-italiani.php | Ricerca dei Comuni Italiani (dati statistici e territoriali) |
| https://www.avvocatoandreani.it/servizi/tariffe_forensi_civili_online.php | Tariffe Forensi 2004 per Calcolo Parcelle Avvocati |
| https://www.avvocatoandreani.it/servizi/visualizza-messaggi-sdi.php | Visualizza i messaggi dell'SDI (fatturazione elettronica) |
| https://www.avvocatoandreani.it/servizi/visualizzatore-fattura-elettronica.php | Visualizzatore di Fatture Elettroniche |

Non pertinenti a un tool di calcolo: la calcolatrice, il cronometro, le pagine di consultazione dei codici, il visualizzatore di fatture elettroniche e la ricerca delle applicazioni. I calcolatori a parametri 2012 (DM 140/2012) e a tariffe 2004 sono superati dal DM 55/2014 e non vanno replicati.

## Catalogo delle pagine del sito emerso dalla ricerca web

| URL | Titolo | Tema |
|---|---|---|
| https://www.avvocatoandreani.it/servizi/interessi_legali.php | Calcolo Interessi Legali 2026 - Interesse Legale | Interessi: interessi legali ex art. 1284 c.c. |
| https://www.avvocatoandreani.it/servizi/interessi_moratori.php | Calcolo Interessi Moratori 2026 - Interessi di Mora | Interessi: interessi moratori nelle transazioni commerciali (D.Lgs. 231/2002) |
| https://www.avvocatoandreani.it/servizi/calcolo-interessi-corso-causa.php | Calcolo interessi legali/moratori ex Art. 1284 c.c. | Interessi: interessi legali e moratori in corso di causa (art. 1284 comma 4 c.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo-interessi-acconti.php | Calcolo interessi con acconti a scalare | Interessi: interessi con acconti e pagamenti parziali a scalare |
| https://www.avvocatoandreani.it/servizi/interessi_tasso_fisso.php | Calcolo Interessi a Tasso Fisso - AvvocatoAndreani.it | Interessi: interessi a tasso fisso convenzionale |
| https://www.avvocatoandreani.it/servizi/calcolo-interessi-vari-capitale-rivalutato.php | Calcolo interessi a tasso fisso, legali e moratori sul capitale rivalutato annualmente | Interessi e rivalutazione: interessi a tasso fisso, legali o moratori su capitale rivalutato annualmente |
| https://www.avvocatoandreani.it/servizi/calcolo-maggior-danno-obbligazioni-pecuniarie.php | Calcolo Maggior Danno Obbligazioni Pecuniarie | Interessi: maggior danno nelle obbligazioni pecuniarie (art. 1224 comma 2 c.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo_interessi_mora_appalti_opere_pubbliche.php | Calcolo Interessi di Mora Appalti Lavori Pubblici 2026 | Interessi: interessi di mora negli appalti di lavori pubblici |
| https://www.avvocatoandreani.it/servizi/calcolo_tasso_usura.php | Calcolo Tasso di Usura basato sui TEGM Terzo Trimestre 2026 | Usura: tasso soglia dai TEGM trimestrali (L. 108/1996) |
| https://www.avvocatoandreani.it/servizi/interessi_rivalutazione.php | Calcolo Rivalutazione Monetaria Istat con Interessi Legali | Rivalutazione monetaria ISTAT (indice FOI) con interessi legali; nei risultati compare anche la variante interessi_rivalutazione.php?op=3 (titolo: Calcolo Rivalutazione Monetaria Istat (Giugno 2026)) per la sola rivalutazione |
| https://www.avvocatoandreani.it/servizi/calcolo_devalutazione_monetaria.php | Calcolo Devalutazione Monetaria Istat | Rivalutazione: devalutazione monetaria ISTAT |
| https://www.avvocatoandreani.it/servizi/rivalutazione-monetaria-storica.php | Rivalutazione Monetaria Storica - AvvocatoAndreani.it Risorse ... | Rivalutazione: rivalutazione monetaria storica |
| https://www.avvocatoandreani.it/servizi/rivalutazione_mensile_assegni_importi_dovuti.php | Rivalutazione Monetaria Assegni Mensili | Rivalutazione: rivalutazione ISTAT di importi mensili (assegni di mantenimento) |
| https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php | Calcolo rivalutazione annuale media | Rivalutazione: rivalutazione annuale media ISTAT |
| https://www.avvocatoandreani.it/servizi/calcolo-inflazione.php | Calcolo inflazione e perdita del potere di acquisto | Inflazione: perdita del potere d'acquisto |
| https://www.avvocatoandreani.it/servizi/grafico-andamento-inflazione-titoli-di-stato.php | Andamento Inflazione e Rendimento Titoli di Stato (BOT) | Inflazione: grafico dell'inflazione e del rendimento dei titoli di Stato (anche con ?i=true) |
| https://www.avvocatoandreani.it/servizi/variazioni_indici_istat_rivalutazione.php | Variazioni Percentuali Indici Istat per la Rivalutazione | Indici ISTAT: tabella delle variazioni percentuali per la rivalutazione |
| https://www.avvocatoandreani.it/servizi/variazioni_indici_istat_locazioni.php | Variazioni Annuali e Biennali Indice Istat FOI | Indici ISTAT: tabella delle variazioni annuali e biennali FOI per le locazioni |
| https://www.avvocatoandreani.it/servizi/valore-ultimo-indice-istat.php | Valore Ultimo Indice Istat - Agosto 2026 | Indici ISTAT: ultimo indice FOI pubblicato |
| https://www.avvocatoandreani.it/servizi/tab_interessi_legali.php | Tasso di Interesse Legale 2024 - AvvocatoAndreani.it | Tabella: saggi dell'interesse legale per periodo |
| https://www.avvocatoandreani.it/servizi/tab_interessi_moratori.php | Tabella Interessi Moratori 2026 | Tabella: tassi semestrali degli interessi moratori |
| https://www.avvocatoandreani.it/servizi/tabella_interessi_mora_appalti_pubblici.php | Interessi Moratori Appalti Pubblici - AvvocatoAndreani.it | Tabella: tassi di mora negli appalti pubblici |
| https://www.avvocatoandreani.it/servizi/calcolo-ammortamento-mutuo.php | Calcolo Rata del Mutuo e Piano di Ammortamento | Mutuo: rata e piano di ammortamento |
| https://www.avvocatoandreani.it/servizi/calcolo-surroga-mutuo.php | Calcolo surroga mutuo e taglio della rata | Mutuo: surroga e riduzione della rata |
| https://www.avvocatoandreani.it/servizi/calcolo-taeg.php | Calcolo TAEG | Credito: TAEG |
| https://www.avvocatoandreani.it/servizi/calcolo-rendimento-bot.php | Calcolo Rendimento BOT 3 mesi, 6 mesi e 12 mesi | Investimenti: rendimento netto dei BOT a 3, 6 e 12 mesi |
| https://www.avvocatoandreani.it/servizi/calcolo-rendimento-pronti-contro-termine.php | Calcolo Rendimento Pronti Contro Termine | Investimenti: rendimento dei pronti contro termine |
| https://www.avvocatoandreani.it/utility/calcolo-buoni-postali-fruttiferi.php | Buoni Fruttiferi Postali: Calcolo Rendimento e Interessi \| CDP | Investimenti: rendimento dei buoni fruttiferi postali (pagina fuori da /servizi/, nella sezione /utility/) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php | Parametri Avvocati 2026, Calcolo Compensi Forensi Civili DM 55/2014 | Parcella avvocato: parametri forensi civili DM 55/2014 (aggiornato DM 147/2022) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-penali-2014.php | Parametri Avvocati 2026, Calcolo Compensi Forensi Penali DM 55/2014 | Parcella avvocato: parametri forensi penali DM 55/2014 |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php | Parametri Avvocati 2026, Calcolo Compensi Forensi Stragiudiziali DM 55/2014 | Parcella avvocato: attività stragiudiziale DM 55/2014 |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-ministeriali-civili.php | Compensi Avvocati 2012, Parametri Forensi Civili | Parcella avvocato: parametri civili DM 140/2012 (regime previgente) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-ministeriali-penali.php | Compensi Avvocati 2012, Parametri Forensi Penali | Parcella avvocato: parametri penali DM 140/2012 (regime previgente) |
| https://www.avvocatoandreani.it/servizi/calcolo_nota_spese_avvocati_tariffe_forensi.php | Calcolo Nota Spese per Studi Legali con Tariffario Forense 2004 | Parcella avvocato: nota spese civile con tariffa forense 2004 (DM 127/2004, abrogata) |
| https://www.avvocatoandreani.it/servizi/calcolo_parcella_penale_avvocati_tariffario_forense.php | Calcolo Parcella Penale con Tariffario Forense 2004 | Parcella avvocato: parcella penale con tariffa forense 2004 (abrogata) |
| https://www.avvocatoandreani.it/servizi/tariffe_forensi_civili_online.php | Tariffe Forensi 2004 per Calcolo Parcelle Avvocati | Parcella avvocato: tariffe forensi 2004 |
| https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php | Nota Spese Avvocati: Decreto Ingiuntivo, Precetto, Esecuzione Mobiliare, Esecuzione Immobiliare, ... | Parcella avvocato: modelli di notula per decreto ingiuntivo, precetto, esecuzione mobiliare e immobiliare |
| https://www.avvocatoandreani.it/servizi/preventivo-avvocato-civile.php | Preventivo scritto per avvocati e studi legali (cause civili) | Preventivo scritto dell'avvocato: cause civili |
| https://www.avvocatoandreani.it/servizi/preventivo-avvocato-stragiudiziale.php | Preventivo scritto per avvocati (affari stragiudiziali e mediazione) | Preventivo scritto dell'avvocato: affari stragiudiziali e mediazione |
| https://www.avvocatoandreani.it/servizi/calcolo_preventivo_online.php | Calcolo Preventivo Online | Preventivo: calcolo preventivo online (oggetto non precisato dal titolo) |
| https://www.avvocatoandreani.it/servizi/calcolo-spese-trasferta-avvocati.php | Calcolo Spese di Trasferta per Avvocati e Studi Legali (parametri 2026) | Parcella avvocato: spese di trasferta (art. 27 DM 55/2014) |
| https://www.avvocatoandreani.it/servizi/calcolo-rimborso-chilometrico.php | Calcolo Rimborso Chilometrico Aci | Spese: rimborso chilometrico secondo le tabelle ACI |
| https://www.avvocatoandreani.it/servizi/calcolo-somma-ore-minuti-compensi-a-tempo.php | Calcolo Somma Ore e Minuti e Compensi a Tempo | Compenso orario: somma di ore e minuti e compenso a tempo |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-onorario-ctu-liquidazione-tariffe.php | Calcolo Parcella CTU: Onorari a Tariffa e a Vacazione | CTU: onorari a percentuale e a vacazione (DM 30 maggio 2002) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-curatore-fallimentare.php | Calcolo Compenso Curatore Fallimentare | Procedure concorsuali: compenso del curatore fallimentare (DM 30/2012) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-delegati-vendite-giudiziarie.php | Calcolo Compenso Delegati Alla Vendita | Esecuzioni: compenso del professionista delegato alla vendita (DM 227/2015) |
| https://www.avvocatoandreani.it/servizi/calcolo-compenso-mediatore-familiare.php | Calcolo del Compenso per il Mediatore Familiare | Mediazione familiare: compenso del mediatore familiare |
| https://www.avvocatoandreani.it/servizi/calcolo-spese-di-mediazione.php | Calcolo Spese di Mediazione (nuove tariffe 2023) | Mediazione civile: spese e indennità con le tariffe 2023 (DM 150/2023) |
| https://www.avvocatoandreani.it/servizi/calcolo-costi-e-tariffe-mediazione-civile.php | Calcolo Tariffe Mediazione Civile e Commerciale Obbligatoria | Mediazione civile: costi e tariffe della mediazione obbligatoria |
| https://www.avvocatoandreani.it/servizi/calcolo_fattura_studio_legale.php | Calcolo Fattura per Avvocati e Studi Legali | Fatturazione avvocati: spese generali, CPA, IVA e ritenuta d'acconto |
| https://www.avvocatoandreani.it/servizi/calcolatrice_scorporo.php | Scorporo Importi Fatturazione Avvocati - Calcolo Fattura Inversa | Fatturazione avvocati: scorporo degli importi e fattura inversa |
| https://www.avvocatoandreani.it/servizi/calcolo_fattura_generica_scorporo.php | Calcolo Fattura Professionisti e Fattura Inversa con IVA, Ritenuta d'Acconto e Cassa di Previdenza | Fatturazione professionisti: fattura e fattura inversa con cassa di previdenza, IVA e ritenuta |
| https://www.avvocatoandreani.it/servizi/calcolo_fattura_agente_enasarco.php | Calcolo Fattura Agente Enasarco | Fatturazione: agenti di commercio con contributo Enasarco |
| https://www.avvocatoandreani.it/servizi/calcolo-ritenuta-d-acconto.php | Calcolo Ritenuta d'Acconto - AvvocatoAndreani.it Risorse Legali | Fatturazione: ritenuta d'acconto |
| https://www.avvocatoandreani.it/servizi/calcolo-ricevuta-prestazione-occasionale.php | Calcolo Ricevuta per Prestazione Occasionale | Fatturazione: ricevuta per prestazione occasionale |
| https://www.avvocatoandreani.it/servizi/scorporo-iva-calcoli-percentuali-frequenti.php | Scorporo IVA e Calcolo IVA Inversa | IVA: scorporo e calcolo dell'IVA inversa |
| https://www.avvocatoandreani.it/servizi/fattura-elettronica-avvocati.php | Fattura Elettronica Gratis per Avvocati e Studi Legali | Fatturazione: fattura elettronica per avvocati |
| https://www.avvocatoandreani.it/servizi/fattura-elettronica.php | Fattura Elettronica per Professionisti e Lavoratori Autonomi | Fatturazione: fattura elettronica per professionisti e lavoratori autonomi |
| https://www.avvocatoandreani.it/servizi/calcolo_contributo_unificato.php | Calcolo Contributo Unificato 2026 | Spese di giustizia: contributo unificato (art. 13 DPR 115/2002) |
| https://www.avvocatoandreani.it/servizi/tabella-contributo-unificato.php | Tabella Contributo Unificato 2026 | Spese di giustizia: tabella del contributo unificato |
| https://www.avvocatoandreani.it/servizi/calcolo_diritti_copia_cancelleria.php | Calcolo Diritti di Copia 2026 | Spese di giustizia: diritti di copia di cancelleria (DPR 115/2002) |
| https://www.avvocatoandreani.it/servizi/calcolo_diritti_copia_processo_tributario.php | Calcolo Diritti di Copia nel Processo Tributario 2026 | Spese di giustizia: diritti di copia nel processo tributario |
| https://www.avvocatoandreani.it/servizi/verifica-requisiti-gratuito-patrocinio.php | Patrocinio gratuito: verifica reddito e requisiti | Patrocinio a spese dello Stato: verifica del limite di reddito e dei requisiti |
| https://www.avvocatoandreani.it/servizi/calcolo_scadenze_termini_udienze.php | Calcolo Scadenze, Termini Processuali e Giorni tra Date | Termini processuali: calcolo delle scadenze e dei giorni tra date |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php | Calcolo Termini Processuali Civili a Giorni e a Mesi | Termini processuali civili a giorni e a mesi (art. 155 c.p.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-memorie-integrative-comparse-repliche.php | Calcolo Termini per Memorie Integrative 171-ter e Comparse 189 cpc | Termini: memorie integrative art. 171-ter e comparse art. 189 c.p.c. (rito dopo la riforma Cartabia) |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-memorie-183-comparse-190.php | Calcolo Termini Processuali Memorie 183 cpc, Comparse Conclusionali e Memorie di Replica 190 cpc | Termini: memorie art. 183 e comparse e repliche art. 190 c.p.c. (rito previgente) |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-procedimento-semplificato.php | Calcolo Termini Procedimento Semplificato ex art. 281-duodecies cpc | Termini: procedimento semplificato di cognizione (art. 281-duodecies c.p.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-separazione-divorzio.php | Calcolo Termini Processuali per le udienze di Separazione e Divorzio | Termini: udienze di separazione e divorzio |
| https://www.avvocatoandreani.it/servizi/termini-impugnazioni-civile-amministrativo-tributario.php | Calcolo termini per le Impugnazioni (Appello, Cassazione, Revocazione e Opposizione di Terzo) in Civile, Amministrativo e Tributario | Termini di impugnazione: appello, cassazione, revocazione e opposizione di terzo in civile, amministrativo e tributario |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-atti-appello.php | Calcolo Termini per Deposito di Atti ex art. 352 cpc | Termini: deposito degli atti in appello (art. 352 c.p.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-ctu.php | Calcolo Termini per il Deposito della CTU | Termini: deposito della relazione del CTU |
| https://www.avvocatoandreani.it/servizi/calcolo-termini-esecuzioni.php | Calcolo Termini nelle Procedure Esecutive | Termini: procedure esecutive |
| https://www.avvocatoandreani.it/servizi/ricorso-pagamento-multa.php | Calcolo termini per contestare o pagare una multa: ricorso al prefetto e al giudice di pace | Multe: termini per il pagamento e per il ricorso al prefetto o al giudice di pace |
| https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-diritti.php | Calcolo Prescrizione Diritti | Prescrizione civile dei diritti |
| https://www.avvocatoandreani.it/servizi/calcolo-giorni-lavorativi-festivi.php | Calcolo Giorni Lavorativi e Festivi 2026 | Date: giorni lavorativi e festivi |
| https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php | Contagiorni: calcolo giorni tra due date con feste e ricorrenze | Date: giorni tra due date con feste e ricorrenze |
| https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-reati.php | Calcolo Prescrizione Reati (Ex/Ante Legge Cirielli) | Penale: prescrizione dei reati (prima e dopo la legge Cirielli) |
| https://www.avvocatoandreani.it/servizi/calcolo-aumenti-riduzioni-pena.php | Calcolo Aumento e Riduzione della Pena | Penale: aumenti e riduzioni di pena |
| https://www.avvocatoandreani.it/servizi/calcolo-conversione-pena-detentiva-pecuniaria.php | Conversione tra Pena Detentiva e Pena Pecuniaria | Penale: ragguaglio tra pena detentiva e pena pecuniaria (art. 135 c.p.) |
| https://www.avvocatoandreani.it/servizi/calcolo-fine-pena-liberazione-anticipata.php | Calcolo Fine Pena con Liberazione Anticipata | Penale: fine pena con liberazione anticipata |
| https://www.avvocatoandreani.it/servizi/calcolo-irpef.php | Calcolo IRPEF con nuove aliquote 2026 - Modello REDDITI e 730 | Fisco: IRPEF con le aliquote vigenti |
| https://www.avvocatoandreani.it/servizi/calcolo-acconto-irpef.php | Calcolo Acconto IRPEF 2026 | Fisco: acconto IRPEF |
| https://www.avvocatoandreani.it/servizi/calcolo-rateizzazione-imposte-irpef.php | Calcolo Rateizzazione imposte 2026: IRPEF, interessi e Modello F24 | Fisco: rateizzazione delle imposte, interessi e F24 |
| https://www.avvocatoandreani.it/servizi/calcolo-ravvedimento-operoso.php | Calcolo del Ravvedimento Operoso 2026 | Fisco: ravvedimento operoso |
| https://www.avvocatoandreani.it/servizi/calcolo-imposta-regime-forfettario.php | Calcolo Imposta Nuovo Regime Forfettario 2026 | Fisco: imposta sostitutiva del regime forfettario |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-redditi-assimilati.php | Calcolo Detrazione Redditi da Lavoro Dipendente 2026, modello REDDITI e 730 | Detrazioni: redditi di lavoro dipendente e assimilati |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-pensione.php | Calcolo Detrazione Redditi da Pensione 2026, modello REDDITI e 730 | Detrazioni: redditi da pensione |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-coniuge-a-carico.php | Calcolo Detrazione per Coniuge a Carico 2026, modello REDDITI e 730 | Detrazioni: coniuge a carico |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-a-carico.php | Calcolo Detrazione Figli a Carico 2026, modello REDDITI e 730 | Detrazioni: figli a carico |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-21-anni.php | Calcolo Detrazione Figli a Carico 2026, modello REDDITI e 730 | Detrazioni: figli a carico di almeno 21 anni |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-familiari-a-carico.php | Calcolo Detrazione Altri Familiari a Carico 2026, modello REDDITI e 730 | Detrazioni: altri familiari a carico |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-assegno-coniuge.php | Calcolo Detrazione per l'Assegno di Mantenimento versato al Coniuge 2026, modello REDDITI e 730 | Detrazioni: assegno di mantenimento versato al coniuge |
| https://www.avvocatoandreani.it/servizi/calcolo-detrazione-canone-locazione.php | Calcolo Detrazione per Canone di Locazione 2026, modello REDDITI e 730 | Detrazioni: canone di locazione |
| https://www.avvocatoandreani.it/servizi/calcolo-assegno-unico-universale.php | Calcolo Assegno Unico Universale Figli 2026 | Famiglia: assegno unico universale per i figli |
| https://www.avvocatoandreani.it/servizi/calcolo-imu-nuova-ici.php | Calcolo IMU 2026 Prima Casa Seconda Casa e Terreni | Immobili: IMU su prima casa, seconda casa e terreni |
| https://www.avvocatoandreani.it/servizi/calcolo-imposte-compravendita-immobiliare.php | Calcolo Imposte di Compravendita Immobiliare 2014: acquisto prima e seconda casa | Immobili: imposte sulla compravendita (prima e seconda casa) |
| https://www.avvocatoandreani.it/servizi/calcolo-valore-catastale-immobili-asse-ereditario.php | Calcolo Valore Catastale Immobili (prima e seconda casa) - Calcolo dell'Asse Ereditario | Immobili: valore catastale e asse ereditario |
| https://www.avvocatoandreani.it/servizi/calcolo-superficie-commerciale.php | Calcolo Superficie Commerciale Immobili | Immobili: superficie commerciale |
| https://www.avvocatoandreani.it/servizi/tabella-categorie-catastali.php?gruppo=C | Gruppo Catastale C: Immobili commerciali e pertinenze | Catasto: tabella delle categorie catastali per gruppo (nei risultati anche ?gruppo=D, ?gruppo=E e ?gruppo=F) |
| https://www.avvocatoandreani.it/servizi/calcolo_adeguamento_istat_canone_locazione.php | Adeguamento Istat Canone di Locazione Agosto 2026 | Locazioni: adeguamento ISTAT del canone |
| https://www.avvocatoandreani.it/servizi/lettera-adeguamento-canone-locazione.php | Creazione gratuita della lettera di adeguamento del canone di locazione | Locazioni: lettera di adeguamento del canone |
| https://www.avvocatoandreani.it/servizi/calcolo-imposta-registro-contratto-locazione.php | Calcolo Imposta di Registro per Contratti di Locazione Commerciale e Abitativa | Locazioni: imposta di registro sui contratti di locazione abitativa e commerciale |
| https://www.avvocatoandreani.it/servizi/calcolo-convenienza-cedolare-secca-affitti.php | Calcolo Convenienza Cedolare Secca Affitti | Locazioni: convenienza della cedolare secca |
| https://www.avvocatoandreani.it/servizi/calcolo-acconto-cedolare-secca.php | Calcolo Acconto Cedolare Secca 2026 | Locazioni: acconto della cedolare secca |
| https://www.avvocatoandreani.it/servizi/ripartizione_spese_proprietario_inquilino.php | Ripartizione Spese Proprietario e Inquilino Tabella Confedilizia Sunia-Sicet-Uniat 2014 | Locazioni: ripartizione degli oneri tra proprietario e inquilino (tabella Confedilizia Sunia Sicet Uniat 2014) |
| https://www.avvocatoandreani.it/servizi/calcolo-ripartizione-spese-utenze.php | Calcolo Ripartizione Utenze e Spese Condominiali | Condominio: ripartizione di utenze e spese condominiali |
| https://www.avvocatoandreani.it/servizi/calcolo_quote_ereditarie.php | Eredità e Successioni, Calcolo Quote Ereditarie | Successioni: quote ereditarie |
| https://www.avvocatoandreani.it/servizi/calcolo-imposte-di-successione.php | Calcolo delle Imposte di Successione | Successioni: imposte di successione |
| https://www.avvocatoandreani.it/servizi/calcolo_usufrutto_nuda_proprieta.php | Calcolo Usufrutto e Nuda Proprietà 2026 | Usufrutto: valore dell'usufrutto e della nuda proprietà |
| https://www.avvocatoandreani.it/servizi/tab_coefficienti_usufrutto.php | Tabelle Coefficienti Usufrutto e Nuda Proprietà 2026 | Usufrutto: tabelle dei coefficienti (anni precedenti con ?anno=2002, ?anno=2010, ?anno=2019) |
| https://www.avvocatoandreani.it/servizi/calcolo-grado-di-parentela.php | Calcolo del Grado di Parentela e di Affinità | Famiglia: grado di parentela e di affinità |
| https://www.avvocatoandreani.it/servizi/calcolo-tfr.php | Calcolo TFR online | Lavoro: trattamento di fine rapporto |
| https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php | Calcolo Coefficiente di Rivalutazione del TFR (ultimo aggiornamento: Agosto 2026) | Lavoro: coefficiente di rivalutazione del TFR |
| https://www.avvocatoandreani.it/servizi/calcolo-pensione-reversibilita-inps.php | Calcolo Pensione di Reversibilità Inps | Previdenza: pensione di reversibilità INPS |
| https://www.avvocatoandreani.it/servizi/calcolo-pignoramento-stipendio-pensione.php | Calcolo somma pignorabile dello stipendio o della pensione | Esecuzioni: quota pignorabile di stipendio e pensione (art. 545 c.p.c.) |
| https://www.avvocatoandreani.it/servizi/calcolo_risarcimento_inail_infortunio_lavoro.php | Calcolo Risarcimento INAIL | Infortuni sul lavoro: indennizzo INAIL |
| https://www.avvocatoandreani.it/servizi/calcolo-equo-indennizzo-causa-servizio.php | Calcolo Equo Indennizzo per Cause di Servizio | Pubblico impiego: equo indennizzo per causa di servizio |
| https://www.avvocatoandreani.it/servizi/tabelle_danno_biologico_macropermanenti.php | Tabelle Danno Biologico Lesioni Macropermanenti 2025 2026 Milano e Roma | Danno biologico: tabelle delle macropermanenti di Milano e Roma |
| https://www.avvocatoandreani.it/servizi/calcolo-danno-perdita-parentale-tribunale-milano.php | Calcolo Danno da Perdita del Rapporto Parentale (Tribunale di Milano) | Danno da perdita del rapporto parentale: tabelle del Tribunale di Milano |
| https://www.avvocatoandreani.it/servizi/calcolo-risarcimento-danno-perdita-parentale.php | Calcolo Danno da Perdita Parentale per Morte del Congiunto - Tabelle 2025 Tribunale di Roma | Danno da perdita del rapporto parentale: tabelle del Tribunale di Roma |
| https://www.avvocatoandreani.it/servizi/atto-di-precetto.php | Creazione dell'Atto di Precetto con relata di notifica e nuova formula | Atti: atto di precetto con relata di notifica |
| https://www.avvocatoandreani.it/servizi/decreto-ingiuntivo.php | Modello per creare il Ricorso per Decreto Ingiuntivo su Fattura | Atti: ricorso per decreto ingiuntivo su fattura |
| https://www.avvocatoandreani.it/servizi/sfratto-per-morosita.php | Creazione Guidata dello Sfratto per Morosità | Atti: intimazione di sfratto per morosità |
| https://www.avvocatoandreani.it/servizi/procura-alle-liti.php | Procura alle Liti Telematica e Cartacea con Redattore Online | Atti: procura alle liti telematica e cartacea |
| https://www.avvocatoandreani.it/servizi/relata-notifica-pec.php | Creazione della relata di notifica in proprio tramite PEC | Notifiche: relata di notifica in proprio via PEC (L. 53/1994) |
| https://www.avvocatoandreani.it/servizi/attestazione-conformita.php | Creazione guidata dell'Attestazione di Conformità | PCT: attestazione di conformità delle copie |
| https://www.avvocatoandreani.it/servizi/istanza-visibilita-fascicolo-telematico.php | Creazione guidata dell'Istanza per la Visibilità del Fascicolo Telematico | PCT: istanza di visibilità del fascicolo telematico |
| https://www.avvocatoandreani.it/servizi/deposito-telematico-documenti.php | Modello per il Deposito Telematico di Documenti nel PCT | PCT: modello per il deposito telematico di documenti |
| https://www.avvocatoandreani.it/servizi/indice-documenti-allegati.php | Creazione dell’Indice Allegati con Collegamenti Ipertestuali | PCT: indice degli allegati con collegamenti ipertestuali |
| https://www.avvocatoandreani.it/servizi/calcolo-verifica-impronta-hash.php | Calcolo e Verifica dell'Impronta Hash | PCT: calcolo e verifica dell'impronta hash |
| https://www.avvocatoandreani.it/servizi/fascicolo-di-parte.php | Creazione del Fascicolo di Parte - AvvocatoAndreani.it ... | Atti: fascicolo di parte |
| https://www.avvocatoandreani.it/servizi/note-trattazione-scritta.php | Redattore delle Note di Trattazione Scritta | Atti: note di trattazione scritta (art. 127-ter c.p.c.) |
| https://www.avvocatoandreani.it/servizi/testimonianza-scritta-257-bis-cpc.php | Testimonianza Scritta 257 CpC - Modelli e Istruzioni | Atti: testimonianza scritta (art. 257-bis c.p.c.) |
| https://www.avvocatoandreani.it/servizi/nota-precisazione-credito.php | Creazione della nota di Precisazione del Credito nei Pignoramenti | Esecuzioni: nota di precisazione del credito |
| https://www.avvocatoandreani.it/servizi/modello-dichiarazione-553.php | Creazione dichiarazione ex art. 553 cpc per il terzo pignorato | Esecuzioni: dichiarazione del terzo pignorato |
| https://www.avvocatoandreani.it/servizi/lettera-sollecito-pagamento.php | Modello di lettera per solleciti di pagamento (non solo per avvocati) | Lettere: sollecito di pagamento |
| https://www.avvocatoandreani.it/servizi/note_iscrizione_a_ruolo.php | Note Iscrizione a Ruolo Uffici Giudiziari: Tribunale, Giudice di Pace, Appello, Cassazione... | Iscrizione a ruolo: note di iscrizione per ufficio giudiziario |
| https://www.avvocatoandreani.it/servizi/ricerca-codici-iscrizione-ruolo-cause.php | Ricerca Codici di Iscrizione a Ruolo | Iscrizione a ruolo: codici oggetto |
| https://www.avvocatoandreani.it/servizi/ricerca-uffici-giudiziari-per-comune.php | Ricerca uffici giudiziari per competenza (Comune) | Competenza: uffici giudiziari per comune |
| https://www.avvocatoandreani.it/servizi/ricerca-uffici-unep.php | Competenza Uffici UNEP per Comune | Competenza: uffici UNEP per comune |
| https://www.avvocatoandreani.it/servizi/ricerca-codici-catastali-comuni.php | Ricerca Codici Catastali dei Comuni per Modello F24 | Codici catastali dei comuni (F24) |
| https://www.avvocatoandreani.it/servizi/ricerca-comuni-italiani.php | Ricerca dei Comuni Italiani (dati statistici e territoriali) | Comuni italiani: dati statistici e territoriali |
| https://www.avvocatoandreani.it/servizi/ricerca-codici-ateco.php | Ricerca Codice ATECO 2025 | Codici ATECO 2025 |
| https://www.avvocatoandreani.it/servizi/verifica-partita-iva.php | Verifica Partita IVA - AvvocatoAndreani.it Risorse Legali | Verifica della partita IVA |
| https://www.avvocatoandreani.it/servizi/calcolo-tempo-trascorso-differenza-ore.php | Calcolo del tempo trascorso tra due o più ore (passato e futuro) | Tempo: tempo trascorso tra due o più orari |
| https://www.avvocatoandreani.it/servizi/calcolo-ora-inizio-fine-attivita.php | Calcolo ora di inizio o fine attività in base alla durata. | Tempo: ora di inizio o di fine in base alla durata |
| https://www.avvocatoandreani.it/servizi/conversione-ore-minuti-in-centesimi.php | Conversione Ore, Minuti e Secondi in formato decimale | Tempo: conversione di ore, minuti e secondi in formato decimale |
| https://www.avvocatoandreani.it/servizi/calcolo_percentuali_quote.php | Calcolo Percentuali da Valori Numerici | Percentuali e quote da valori numerici |
| https://www.avvocatoandreani.it/servizi/tabelle-parametri-forensi.php | Tabelle Parametri Ministeriali Forensi 2026 (DM 55/2014) | Parametri forensi: indice delle tabelle DM 55/2014 |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-giudice-di-pace-civile.html | Tabelle Parametri Forensi DM 55/2014: Giudice di pace civile | Parametri forensi, tabella: giudice di pace civile |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-giudizi-cognizione-tribunale.html | Tabelle Parametri Forensi DM 55/2014: Giudizi di cognizione innanzi al tribunale | Parametri forensi, tabella: giudizi di cognizione davanti al tribunale |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-cassazione-civile-magistrature-superiori.html | Tabelle Parametri Forensi DM 55/2014: Corte di Cassazione Civile, Magistrature superiori | Parametri forensi, tabella: Cassazione civile e magistrature superiori |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-procedimenti-monitori.html | Tabelle Parametri Forensi DM 55/2014: Procedimenti monitori | Parametri forensi, tabella: procedimenti monitori (decreto ingiuntivo) |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-precetto.html | Tabelle Parametri Forensi DM 55/2014: Atto di precetto | Parametri forensi, tabella: atto di precetto |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-mobiliari.html | Tabelle Parametri Forensi DM 55/2014: Esecuzioni mobiliari | Parametri forensi, tabella: esecuzioni mobiliari |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-immobiliari.html | Tabelle Parametri Forensi DM 55/2014: Esecuzioni immobiliari | Parametri forensi, tabella: esecuzioni immobiliari |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-esecuzioni-presso-terzi.html | Tabelle Parametri Forensi DM 55/2014: Esecuzioni presso terzi, per consegna e rilascio | Parametri forensi, tabella: esecuzioni presso terzi, per consegna e rilascio |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-procedimenti-cautelari.html | Tabelle Parametri Forensi DM 55/2014: Procedimenti cautelari | Parametri forensi, tabella: procedimenti cautelari |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-istruzione-preventiva.html | Tabelle Parametri Forensi DM 55/2014: Procedimenti di istruzione preventiva | Parametri forensi, tabella: procedimenti di istruzione preventiva |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-volontaria-giurisdizione.html | Tabelle Parametri Forensi DM 55/2014: Volontaria giurisdizione | Parametri forensi, tabella: volontaria giurisdizione |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-lavoro.html | Tabelle Parametri Forensi DM 55/2014: Cause di lavoro | Parametri forensi, tabella: cause di lavoro |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-previdenza.html | Tabelle Parametri Forensi DM 55/2014: Cause di previdenza | Parametri forensi, tabella: cause di previdenza |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-accertamento-del-passivo.html | Tabelle Parametri Forensi DM 55/2014: Accertamento del passivo (fallimento e liquidazione giudiziale) | Parametri forensi, tabella: accertamento del passivo (fallimento e liquidazione giudiziale) |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-commissione-tributaria-provinciale.html | Tabelle Parametri Forensi DM 55/2014: Corte di Giustizia Tributaria di primo grado | Parametri forensi, tabella: Corte di giustizia tributaria di primo grado |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-consiglio-di-stato.html | Tabelle Parametri Forensi DM 55/2014: Consiglio di Stato | Parametri forensi, tabella: Consiglio di Stato |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-corte-dei-conti.html | Tabelle Parametri Forensi DM 55/2014: Corte dei Conti | Parametri forensi, tabella: Corte dei conti |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-mediazione-negoziazione-assistita.html | Tabelle Parametri Forensi DM 55/2014: Mediazione e Negoziazione assistita | Parametri forensi, tabella: mediazione e negoziazione assistita |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-assistenza-stragiudiziale.html | Tabelle Parametri Forensi DM 55/2014: Assistenza stragiudiziale | Parametri forensi, tabella: assistenza stragiudiziale |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-giudice-di-pace-penale-indagini-preliminari-difensive-cautelari-personali-reali.html | Tabelle Parametri Forensi DM 55/2014: Penale: Tabella I | Parametri forensi, tabella penale I: giudice di pace penale, indagini preliminari e difensive, cautelari personali e reali |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-gip-gup-tribunale-monocratico-collegiale-corte-assise.html | Tabelle Parametri Forensi DM 55/2014: Penale: Tabella II | Parametri forensi, tabella penale II: GIP, GUP, tribunale monocratico e collegiale, corte d'assise |
| https://www.avvocatoandreani.it/servizi/tabella-parametri-forensi-corte-appello-penale-tribunale-sorveglianza-corte-assise-appello-cassazione-penale-magistrature-superiori.html | Tabelle Parametri Forensi DM 55/2014: Penale: Tabella III | Parametri forensi, tabella penale III: corte d'appello, sorveglianza, assise d'appello, Cassazione penale |
| https://www.avvocatoandreani.it/servizi/utility_varie.php | Utility disponibili in Rete a cura di AvvocatoAndreani.it Risorse Legali | Indice: elenco di utility (pagina elenco, non un calcolatore) |
| https://www.avvocatoandreani.it/servizi/codice_per_sito.php | Utility di Calcolo per Studi Legali - Codice per il Tuo Sito | Widget: codice per inserire le utility di calcolo in un altro sito (non un calcolatore) |
| https://www.avvocatoandreani.it/servizi/risultato_interessi_legali.php | Calcolo Interessi Legali | Interessi legali: pagina dei risultati di interessi_legali.php |
| https://www.avvocatoandreani.it/servizi/risultato_interessi_moratori.php | Calcolo Interessi Moratori - AvvocatoAndreani.it Risorse Legali | Interessi moratori: pagina dei risultati di interessi_moratori.php |
| https://www.avvocatoandreani.it/servizi/risultato_interessi_rivalutazione.php | Calcolo Rivalutazione Monetaria Istat | Rivalutazione monetaria: pagina dei risultati di interessi_rivalutazione.php |
| https://www.avvocatoandreani.it/servizi/risultato_rivalutazione_mensile_assegni.php | Calcolo Rivalutazione Mensile Importi Dovuti | Rivalutazione di importi mensili: pagina dei risultati di rivalutazione_mensile_assegni_importi_dovuti.php |
| https://www.avvocatoandreani.it/servizi/risultato_calcolo_adeguamento_istat_canone_locazione.php | Adeguamento Istat Canone di Locazione Aprile 2026 | Locazioni: pagina dei risultati dell'adeguamento ISTAT del canone |
| https://www.avvocatoandreani.it/servizi/risultato-calcolo-ammortamento-mutuo.php | Calcolo Piano di Ammortamento Mutuo | Mutuo: pagina dei risultati del piano di ammortamento |
| https://www.avvocatoandreani.it/servizi/risultato-calcolo-compenso-avvocati-parametri-ministeriali-civili.php | Calcolo Compenso Avvocati in ambito Civile | Parcella avvocato civile: pagina dei risultati (parametri ministeriali) |
| https://www.avvocatoandreani.it/servizi/risultato-calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php | Calcolo Compenso Avvocati in ambito Stragiudiziale | Parcella avvocato stragiudiziale: pagina dei risultati (versione PDF con ?p=1&pdf=1) |
| https://www.avvocatoandreani.it/servizi/risultato-calcolo-compenso-onorario-ctu-liquidazione-tariffe.php | Calcolo Onorario CTU | CTU: pagina dei risultati dell'onorario |
| https://www.avvocatoandreani.it/servizi/risultato-calcolo-ripartizione-spese-utenze.php | Calcolo Ripartizione Spese e Utenze - Studio Legale Andreani | Condominio: pagina dei risultati della ripartizione di spese e utenze |
| https://www.avvocatoandreani.it/servizi/risultato_calcolatrice_scorporo.php | Scorporo Importi Fatturazione Avvocati | Fatturazione avvocati: pagina dei risultati dello scorporo |
| https://www.avvocatoandreani.it/servizi/risultato_calcolo_fattura_generica_scorporo.php | Calcolo Fattura Professionisti con Scorporo | Fatturazione professionisti: pagina dei risultati della fattura con scorporo |
| https://www.avvocatoandreani.it/servizi/risultato_calcolo_nota_spese_civile.php | Calcolo Notula Civile | Notula civile: pagina dei risultati |
| https://www.avvocatoandreani.it/servizi/risultato_calcolo_nota_spese_modelli.php | Calcolo Notula | Notula da modelli: pagina dei risultati |
| https://www.avvocatoandreani.it/servizi/risultato-attestazione-conformita.php | Risultato Creazione guidata dell'Attestazione di Conformità | PCT: pagina dei risultati dell'attestazione di conformità |
| https://www.avvocatoandreani.it/servizi/risultato-relata-notifica-pec.php | Relata di Notifica del 12/12/2025 | Notifiche PEC: pagina dei risultati della relata |

