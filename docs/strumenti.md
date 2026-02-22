# Guida agli strumenti

mcp-legal-it espone 146 tool MCP in 15 categorie. Questo documento descrive ogni tool con parametri, uso tipico ed esempio concreto.

## Workflow rapidi

| Compito | Sequenza di tool |
|---------|-----------------|
| Sinistro stradale / sanitario | `danno_biologico_micro` → `danno_non_patrimoniale` → `rivalutazione_monetaria` → `interessi_legali` |
| Recupero credito | `interessi_mora` → `rivalutazione_monetaria` → `decreto_ingiuntivo` → `parcella_avvocato_civile` |
| Causa civile | `contributo_unificato` → `scadenza_processuale` → `scadenze_impugnazioni` → `preventivo_civile` |
| Successione | `calcolo_eredita` → `imposte_successione` → `calcolo_valore_catastale` |
| Analisi norma | `cite_law` → `cerca_brocardi` → `cerca_giurisprudenza` → `leggi_sentenza` |
| Privacy / GDPR | `cite_law` (art. GDPR) → `cerca_provvedimenti_garante` → `leggi_provvedimento_garante` |

---


## 1. Rivalutazioni ISTAT

_Calcola rivalutazioni monetarie, adeguamenti di canoni locativi e TFR usando gli indici FOI ISTAT (base 2015=100, disponibili dal 1947). Da usare ogni volta che si deve aggiornare il valore di un credito, un assegno o un canone nel tempo._

---

### `rivalutazione_monetaria`
_Rivaluta un capitale con indici FOI mese per mese, con o senza interessi legali anno per anno (criterio Cass. SU 1712/1995)._

**Parametri**:
- `capitale` (float, obbligatorio) — importo originario in euro.
- `data_inizio` (str, obbligatorio) — data del credito originario (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data di liquidazione (YYYY-MM-DD).
- `con_interessi_legali` (bool, opzionale, default `True`) — se `True` aggiunge interessi legali art. 1284 c.c. sul rivalutato anno per anno.

**Quando usare**: liquidazione di un danno o credito risalente, in sede giudiziale o stragiudiziale.

**Esempio**: `rivalutazione_monetaria(capitale=10000, data_inizio="2015-01-01", data_fine="2025-01-01")` → capitale rivalutato + interessi legali totali con dettaglio anno per anno.

---

### `rivalutazione_mensile`
_Rivaluta singolarmente ogni mensilità di una rata ricorrente (assegno di mantenimento, canone) dalla sua data fino alla data finale._

**Parametri**:
- `importo_mensile` (float, obbligatorio) — importo della singola rata in euro.
- `data_inizio` (str, obbligatorio) — data della prima mensilità (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data finale della rivalutazione (YYYY-MM-DD).

**Quando usare**: calcolo degli arretrati di assegno di mantenimento o canoni non corrisposti con rivalutazione mese per mese.

**Esempio**: `rivalutazione_mensile(importo_mensile=500, data_inizio="2020-03-01", data_fine="2025-01-01")` → totale rivalutato di 58 mensilità con dettaglio mensile.

---

### `adeguamento_canone_locazione`
_Calcola il nuovo canone applicando la variazione FOI nella percentuale prevista dal contratto (75% per concordati, 100% per liberi)._

**Parametri**:
- `canone_annuo` (float, obbligatorio) — canone annuo corrente in euro.
- `data_stipula` (str, obbligatorio) — data di stipula o dell'ultimo adeguamento (YYYY-MM-DD).
- `data_adeguamento` (str, obbligatorio) — data del nuovo adeguamento (YYYY-MM-DD).
- `percentuale_istat` (float, opzionale, default `75.0`) — percentuale della variazione FOI da applicare.

**Quando usare**: aggiornamento annuale del canone ai sensi dell'art. 32 L. 392/1978.

**Esempio**: `adeguamento_canone_locazione(canone_annuo=9600, data_stipula="2020-01-01", data_adeguamento="2025-01-01", percentuale_istat=75.0)` → canone mensile aggiornato con variazione applicata.

---

### `calcolo_inflazione`
_Restituisce la variazione percentuale cumulata e il tasso medio annuo di inflazione FOI tra due date._

**Parametri**:
- `data_inizio` (str, obbligatorio) — data iniziale del periodo (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data finale del periodo (YYYY-MM-DD).

**Quando usare**: relazioni peritali, consulenze economiche, confronti storici di valore.

**Esempio**: `calcolo_inflazione(data_inizio="2000-01-01", data_fine="2025-01-01")` → variazione cumulata ~64%, inflazione media annua ~2.0%.

---

### `rivalutazione_tfr`
_Calcola il TFR maturato con rivalutazione annua ex art. 2120 c.c. (1,5% fisso + 75% variazione FOI) e imposta sostitutiva 17%._

**Parametri**:
- `retribuzione_annua` (float, obbligatorio) — ultima retribuzione annua lorda in euro.
- `anni_servizio` (int, obbligatorio) — anni di servizio.
- `anno_cessazione` (int, obbligatorio) — anno di fine del rapporto di lavoro.

**Quando usare**: stima del TFR in caso di cessazione del rapporto, contenzioso lavorativo o consulenza previdenziale.

**Esempio**: `rivalutazione_tfr(retribuzione_annua=35000, anni_servizio=10, anno_cessazione=2025)` → TFR lordo, rivalutazioni per anno e imposta sostitutiva 17%.

---

### `interessi_vari_capitale_rivalutato`
_Rivaluta FOI e calcola interessi a tasso personalizzato (contrattuale, BOT, ecc.) invece del tasso legale._

**Parametri**:
- `capitale` (float, obbligatorio) — importo originario in euro.
- `data_inizio` (str, obbligatorio) — data del credito (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data di liquidazione (YYYY-MM-DD).
- `tasso_personalizzato` (float, opzionale, default `None`) — tasso annuo in %; se `None` usa il tasso legale vigente.

**Quando usare**: crediti con tasso contrattuale diverso da quello legale, o per confronto tra diversi tassi.

**Esempio**: `interessi_vari_capitale_rivalutato(capitale=20000, data_inizio="2018-01-01", data_fine="2025-01-01", tasso_personalizzato=3.5)` → rivalutato + interessi al 3,5% anno per anno.

---

### `lettera_adeguamento_canone`
_Genera il testo completo della lettera formale di comunicazione dell'adeguamento ISTAT al conduttore._

**Parametri**:
- `locatore` (str, obbligatorio) — nome del locatore (mittente).
- `conduttore` (str, obbligatorio) — nome del conduttore (destinatario).
- `indirizzo_immobile` (str, obbligatorio) — indirizzo completo dell'immobile.
- `canone_attuale` (float, obbligatorio) — canone mensile corrente in euro.
- `data_stipula` (str, obbligatorio) — data di stipula o ultimo adeguamento (YYYY-MM-DD).
- `data_adeguamento` (str, obbligatorio) — data di decorrenza del nuovo canone (YYYY-MM-DD).
- `percentuale_istat` (float, opzionale, default `75.0`) — percentuale della variazione FOI da applicare.

**Quando usare**: invio della comunicazione annuale di adeguamento ISTAT, pronta per la firma e la spedizione.

**Esempio**: `lettera_adeguamento_canone(locatore="Mario Rossi", conduttore="Luigi Bianchi", indirizzo_immobile="Via Roma 1, Milano", canone_attuale=800, data_stipula="2022-01-01", data_adeguamento="2025-01-01")` → testo lettera con calcoli inclusi.

---

### `calcolo_devalutazione`
_Operazione inversa alla rivalutazione: riconduce un importo attuale al suo equivalente in una data passata._

**Parametri**:
- `importo_attuale` (float, obbligatorio) — importo attuale di riferimento in euro.
- `data_attuale` (str, obbligatorio) — data dell'importo attuale (YYYY-MM-DD).
- `data_passata` (str, obbligatorio) — data storica a cui ricondurre il valore (YYYY-MM-DD).

**Quando usare**: confronti storici ("quanto valeva nel 1990 questa somma?"), valutazioni di immobili o beni in termini reali.

**Esempio**: `calcolo_devalutazione(importo_attuale=10000, data_attuale="2025-01-01", data_passata="2000-01-01")` → equivalente passato ~€6.100 con perdita di potere d'acquisto ~39%.

---

### `rivalutazione_storica`
_Rivaluta su base annuale media (senza mese) quando non si conosce il mese esatto dell'obbligazione._

**Parametri**:
- `importo` (float, obbligatorio) — importo originario in euro.
- `anno_partenza` (int, obbligatorio) — anno di partenza.
- `anno_arrivo` (int, obbligatorio) — anno di arrivo.

**Quando usare**: quando si dispone solo dell'anno (non del mese) dell'obbligazione originaria; meno preciso di `rivalutazione_monetaria`.

**Esempio**: `rivalutazione_storica(importo=5000, anno_partenza=2010, anno_arrivo=2025)` → importo rivalutato con coefficiente e dettaglio anno per anno.

---

### `variazioni_istat`
_Tabella delle variazioni percentuali annuali degli indici FOI per un periodo, utile per relazioni peritali._

**Parametri**:
- `anno_inizio` (int, obbligatorio) — anno iniziale del periodo.
- `anno_fine` (int, obbligatorio) — anno finale del periodo.

**Quando usare**: allegare la tavola storica dell'inflazione a una perizia o a una consulenza tecnica.

**Esempio**: `variazioni_istat(anno_inizio=2000, anno_fine=2024)` → tabella anno per anno con media FOI e variazione percentuale annua.

---

### `rivalutazione_annuale_media`
_Rivaluta con la media annua FOI accettando date complete ma usando solo l'anno (alternativa rapida a `rivalutazione_storica`)._

**Parametri**:
- `importo` (float, obbligatorio) — importo originario in euro.
- `data_inizio` (str, obbligatorio) — data iniziale (YYYY-MM-DD; viene usato solo l'anno).
- `data_fine` (str, obbligatorio) — data finale (YYYY-MM-DD; viene usato solo l'anno).

**Quando usare**: quando si ha la data completa ma si vuole un calcolo su base annua media (più rapido, leggermente meno preciso del mensile).

**Esempio**: `rivalutazione_annuale_media(importo=3000, data_inizio="2012-06-15", data_fine="2025-03-10")` → rivalutato con coefficiente basato sulle medie 2012-2025.

---

### `inflazione_titoli_stato`
_Confronta il rendimento nominale di un investimento con l'inflazione FOI dello stesso periodo, calcolando il rendimento reale con l'equazione di Fisher._

**Parametri**:
- `capitale_investito` (float, obbligatorio) — capitale iniziale investito in euro.
- `rendimento_lordo_annuo_pct` (float, obbligatorio) — rendimento lordo annuo in percentuale (es. `3.5`).
- `data_inizio` (str, obbligatorio) — data di inizio investimento (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data di fine investimento (YYYY-MM-DD).

**Quando usare**: valutare se un BTP o un deposito vincolato ha realmente preservato il potere d'acquisto rispetto all'inflazione ISTAT.

**Esempio**: `inflazione_titoli_stato(capitale_investito=50000, rendimento_lordo_annuo_pct=2.5, data_inizio="2015-01-01", data_fine="2025-01-01")` → rendimento reale annuo e confronto con inflazione FOI del periodo.

---

## 2. Tassi e Interessi

_Calcola interessi legali (art. 1284 c.c.), interessi di mora commerciale (D.Lgs. 231/2002), TAEG, ammortamento mutui e verifica di usura. Da usare per quantificare gli oneri finanziari su crediti civili, commerciali o bancari._

---

### `interessi_legali`
_Calcola interessi art. 1284 c.c. tra due date con cambio automatico di tasso per periodo (dies a quo non computatur)._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del capitale in euro.
- `data_inizio` (str, obbligatorio) — data inizio decorrenza (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data fine decorrenza (YYYY-MM-DD).
- `tipo` (str, opzionale, default `"semplici"`) — `"semplici"` o `"composti"`.

**Quando usare**: qualunque credito civile tra privati (risarcimento danni, inadempimento contrattuale) che non rientri nella mora commerciale.

**Esempio**: `interessi_legali(capitale=15000, data_inizio="2019-01-01", data_fine="2025-01-01")` → totale interessi e dettaglio per periodo con tasso vigente.

---

### `interessi_mora`
_Calcola interessi di mora per transazioni commerciali (tasso BCE + 8 pp, D.Lgs. 231/2002), aggiornati semestralmente._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del credito commerciale in euro.
- `data_inizio` (str, obbligatorio) — data di decorrenza della mora (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data di calcolo (YYYY-MM-DD).

**Quando usare**: fatture commerciali insolute tra imprese o tra impresa e PA; non si applica a crediti tra privati.

**Esempio**: `interessi_mora(capitale=25000, data_inizio="2023-07-01", data_fine="2025-01-01")` → totale interessi di mora con dettaglio per semestre BCE.

---

### `interessi_tasso_fisso`
_Calcola interessi a tasso fisso personalizzato (contrattuale o ipotetico), semplici o composti._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del capitale in euro.
- `tasso_annuo` (float, obbligatorio) — tasso annuo percentuale (es. `5.0`).
- `data_inizio` (str, obbligatorio) — data inizio (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data fine (YYYY-MM-DD).
- `tipo` (str, opzionale, default `"semplici"`) — `"semplici"` o `"composti"`.

**Quando usare**: contratti con tasso convenzionale fisso, o proiezioni finanziarie con tasso ipotetico.

**Esempio**: `interessi_tasso_fisso(capitale=8000, tasso_annuo=6.5, data_inizio="2022-01-01", data_fine="2025-01-01")` → interessi €1.560,00 con metodo semplice.

---

### `calcolo_ammortamento`
_Piano di ammortamento completo (francese o italiano) per un mutuo o finanziamento._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del finanziamento in euro.
- `tasso_annuo` (float, obbligatorio) — tasso annuo percentuale nominale.
- `durata_mesi` (int, obbligatorio) — durata in mesi.
- `tipo` (str, opzionale, default `"francese"`) — `"francese"` (rata costante) o `"italiano"` (quota capitale costante).

**Quando usare**: verifica della rata di un mutuo, contenzioso bancario, stima del costo totale del finanziamento.

**Esempio**: `calcolo_ammortamento(capitale=150000, tasso_annuo=3.5, durata_mesi=240, tipo="francese")` → rata mensile ~€869, piano completo 240 rate con quota interessi e capitale.

---

### `verifica_usura`
_Verifica se un tasso applicato supera la soglia di usura ex art. 644 c.p. con formula MEF min(TEGM×1,25+4, TEGM+8)._

**Parametri**:
- `tasso_applicato` (float, obbligatorio) — TAEG effettivo applicato in percentuale (es. `15.5`).
- `tipo_operazione` (str, opzionale, default `"mutuo_prima_casa"`) — categoria: `'mutuo_prima_casa'`, `'credito_personale'`, `'apertura_credito'`, `'leasing'`, `'factoring'`, `'carte_revolving'`, `'cessione_quinto'`, `'mutuo_tasso_variabile'`.
- `trimestre` (str, opzionale, default `None`) — es. `"2024-Q1"`; se `None` usa l'ultimo disponibile.

**Quando usare**: contestazione di contratti bancari o di finanziamento per presunto superamento della soglia usuraria.

**Esempio**: `verifica_usura(tasso_applicato=22.0, tipo_operazione="carte_revolving")` → usurario: True/False con soglia calcolata e margine.

---

### `interessi_acconti`
_Interessi legali con acconti intermedi: ogni pagamento parziale riduce il capitale residuo dal giorno del versamento._

**Parametri**:
- `capitale` (float, obbligatorio) — capitale iniziale in euro.
- `data_inizio` (str, obbligatorio) — data inizio decorrenza (YYYY-MM-DD).
- `acconti` (list[dict], obbligatorio) — lista di dict con `data` (YYYY-MM-DD) e `importo` (float).
- `data_fine` (str, obbligatorio) — data fine decorrenza (YYYY-MM-DD).

**Quando usare**: crediti con pagamenti parziali dilazionati nel tempo (rate, acconti stragiudiziali).

**Esempio**: `interessi_acconti(capitale=10000, data_inizio="2021-01-01", acconti=[{"data":"2022-06-01","importo":3000}], data_fine="2025-01-01")` → interessi calcolati per sub-periodi con capitale residuo post-acconto.

---

### `calcolo_maggior_danno`
_Calcola il maggior danno ex art. 1224 co. 2 c.c.: confronta rivalutazione ISTAT e interessi legali, applica il criterio Cass. SU 19499/2008._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del credito originario in euro.
- `data_inizio` (str, obbligatorio) — data dell'inadempimento (YYYY-MM-DD).
- `data_fine` (str, obbligatorio) — data di liquidazione (YYYY-MM-DD).

**Quando usare**: obbligazioni pecuniarie inadempiute da privati; quando l'inflazione supera gli interessi legali il creditore ha diritto alla differenza.

**Esempio**: `calcolo_maggior_danno(capitale=30000, data_inizio="2015-01-01", data_fine="2025-01-01")` → maggior danno = rivalutazione - interessi legali se positivo; totale dovuto con criterio applicato.

---

### `interessi_corso_causa`
_Applica il tasso di mora D.Lgs. 231/2002 dal giorno della citazione (art. 1284 co. 4 c.c., L. 162/2014), sia in corso di causa sia post-sentenza._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del credito in euro.
- `data_citazione` (str, obbligatorio) — data della domanda giudiziale (YYYY-MM-DD).
- `data_sentenza` (str, obbligatorio) — data di deposito della sentenza (YYYY-MM-DD).
- `data_pagamento` (str, opzionale, default `None`) — data di pagamento effettivo (YYYY-MM-DD); se omessa usa la data sentenza.

**Quando usare**: ogni causa civile introdotta dopo il 28/02/2023 (o ante se si invoca art. 1284 co. 4); produce interessi maggiorati dalla citazione.

**Esempio**: `interessi_corso_causa(capitale=50000, data_citazione="2023-03-01", data_sentenza="2025-01-15")` → interessi in corso di causa al tasso mora BCE+8pp, dettaglio per periodo.

---

### `calcolo_surroga_mutuo`
_Confronta il mutuo attuale con un mutuo surrogato (portabilità gratuita art. 120-quater TUB, Legge Bersani) per valutare il risparmio._

**Parametri**:
- `debito_residuo` (float, obbligatorio) — capitale residuo del mutuo attuale in euro.
- `rata_attuale` (float, obbligatorio) — rata mensile attuale in euro.
- `tasso_attuale` (float, obbligatorio) — tasso annuo attuale in percentuale.
- `tasso_nuovo` (float, obbligatorio) — tasso annuo proposto dalla nuova banca in percentuale.
- `mesi_residui` (int, obbligatorio) — mesi residui del mutuo attuale.

**Quando usare**: consulenza su convenienza della surroga, contenzioso bancario per mancata portabilità.

**Esempio**: `calcolo_surroga_mutuo(debito_residuo=100000, rata_attuale=600, tasso_attuale=4.5, tasso_nuovo=2.8, mesi_residui=180)` → risparmio rata mensile e totale interessi, con flag `conviene: True`.

---

### `calcolo_taeg`
_Calcola il TAEG effettivo con metodo Newton-Raphson, includendo tutte le spese accessorie (direttiva 2008/48/CE)._

**Parametri**:
- `capitale` (float, obbligatorio) — importo del finanziamento erogato in euro.
- `rate` (int, obbligatorio) — numero totale di rate mensili.
- `importi_rate` (float, obbligatorio) — importo nominale di ogni rata in euro.
- `spese_iniziali` (float, opzionale, default `0`) — spese di istruttoria una tantum in euro.
- `spese_periodiche` (float, opzionale, default `0`) — spese per ogni rata (incasso, ecc.) in euro.

**Quando usare**: verifica del TAEG dichiarato in un contratto di credito al consumo; confronto tra prodotti finanziari.

**Esempio**: `calcolo_taeg(capitale=10000, rate=36, importi_rate=310, spese_iniziali=200, spese_periodiche=2)` → TAEG effettivo annualizzato e TAN per confronto.

---

## 3. Scadenze e Termini

_Calcola scadenze processuali civili: termini generici ex art. 155 c.p.c., memorie Cartabia (art. 171-ter c.p.c.), impugnazioni, esecuzioni, famiglia, CTU e contravvenzioni stradali. La proroga festiva è sempre applicata automaticamente._

---

### `scadenza_processuale`
_Calcola una scadenza generica (dies a quo escluso) con proroga automatica al primo giorno feriale successivo se il termine cade in giorno festivo._

**Parametri**:
- `data_evento` (str, obbligatorio) — dies a quo escluso (YYYY-MM-DD).
- `giorni` (int, obbligatorio) — numero di giorni del termine.
- `tipo` (str, opzionale, default `"calendario"`) — `"calendario"` (art. 155 c.p.c.) o `"lavorativi"`.

**Quando usare**: qualunque termine di legge non coperto dagli altri strumenti specifici.

**Esempio**: `scadenza_processuale(data_evento="2025-01-10", giorni=30)` → scadenza 2025-02-09 (o giorno feriale successivo se festivo).

---

### `termini_processuali_civili`
_Calcola un singolo termine ex art. 171-ter c.p.c. (rito post-Cartabia): memoria I (40gg), II (20gg), III (10gg), conclusionale, replica._

**Parametri**:
- `data_udienza` (str, obbligatorio) — data dell'udienza di trattazione (YYYY-MM-DD).
- `tipo_termine` (str, obbligatorio) — `'memoria_I'`, `'memoria_II'`, `'memoria_III'`, `'comparsa_conclusionale'`, `'replica'`.
- `sospensione_feriale` (bool, opzionale, default `True`) — applica sospensione agosto L. 742/1969.

**Quando usare**: calcolare una singola scadenza per un procedimento iscritto a ruolo dopo il 28/02/2023.

**Esempio**: `termini_processuali_civili(data_udienza="2025-09-15", tipo_termine="memoria_I")` → scadenza memoria integrativa con sospensione feriale agosto applicata.

---

### `termini_separazione_divorzio`
_Calcola i termini per divorzio dopo separazione consensuale (6 mesi), giudiziale (12 mesi) o negoziazione assistita (6 mesi)._

**Parametri**:
- `data_evento` (str, obbligatorio) — data dell'omologa o passaggio in giudicato (YYYY-MM-DD).
- `tipo` (str, obbligatorio) — `'separazione_consensuale'`, `'separazione_giudiziale'`, `'negoziazione_assistita'`, `'ricorso_modifica'`.

**Quando usare**: verificare se è maturato il termine per presentare il ricorso di divorzio (divorzio breve L. 55/2015).

**Esempio**: `termini_separazione_divorzio(data_evento="2024-06-01", tipo="separazione_consensuale")` → scadenza per il ricorso di divorzio: 2024-12-01.

---

### `scadenze_impugnazioni`
_Calcola il termine breve (da notifica) o lungo (da pubblicazione) per impugnare una sentenza civile._

**Parametri**:
- `data_pubblicazione` (str, obbligatorio) — data di pubblicazione o notifica della sentenza (YYYY-MM-DD).
- `tipo_impugnazione` (str, obbligatorio) — `'appello_sentenza'`, `'cassazione'`, `'revocazione'`, `'opposizione_terzo'`, `'regolamento_competenza'`.
- `notificata` (bool, opzionale, default `False`) — `True` per termine breve dalla notifica; `False` per termine lungo dalla pubblicazione.

**Quando usare**: calcolare quando scade il termine per proporre appello o ricorso per cassazione dopo una sentenza.

**Esempio**: `scadenze_impugnazioni(data_pubblicazione="2025-01-10", tipo_impugnazione="appello_sentenza", notificata=True)` → scadenza appello entro 30 giorni dalla notifica.

---

### `scadenze_multe`
_Calcola i termini per ricorso al Prefetto (60gg), al Giudice di Pace (30gg), pagamento ridotto (60gg) o con sconto 30% (5gg) dopo notifica di un verbale CdS._

**Parametri**:
- `data_notifica` (str, obbligatorio) — data di notifica del verbale (YYYY-MM-DD).
- `tipo_ricorso` (str, obbligatorio) — `'prefetto'`, `'giudice_pace'`, `'pagamento_ridotto'`, `'pagamento_ridotto_5gg'`.

**Quando usare**: verificare i termini dopo aver ricevuto una multa stradale.

**Esempio**: `scadenze_multe(data_notifica="2025-02-01", tipo_ricorso="giudice_pace")` → scadenza 2025-03-03 con riepilogo di tutte le opzioni.

---

### `termini_memorie_repliche`
_Calcola in un'unica risposta tutte le scadenze per memorie e repliche ex art. 171-ter c.p.c. (memoria 40gg, replica 20gg, prova contraria 10gg)._

**Parametri**:
- `data_udienza` (str, obbligatorio) — data dell'udienza di trattazione (YYYY-MM-DD).

**Quando usare**: ottenere in un colpo solo tutti i termini a ritroso dall'udienza per il rito post-Cartabia.

**Esempio**: `termini_memorie_repliche(data_udienza="2025-10-01")` → tre scadenze (40/20/10gg prima) con proroga festiva applicata.

---

### `termini_procedimento_semplificato`
_Calcola i termini per il procedimento semplificato di cognizione Cartabia (artt. 281-decies ss. c.p.c.): comparsa risposta 70gg, memorie 40/20/10gg prima dell'udienza._

**Parametri**:
- `data_udienza` (str, obbligatorio) — data dell'udienza fissata dal giudice (YYYY-MM-DD).

**Quando usare**: procedimenti semplificati (fatti non controversi, prova documentale, pronta soluzione) iscritti dopo il 28/02/2023.

**Esempio**: `termini_procedimento_semplificato(data_udienza="2025-06-15")` → quattro scadenze a ritroso con rito semplificato Cartabia.

---

### `termini_183_190_cpc`
_Calcola i termini ex art. 183 co. 6 e art. 190 c.p.c. nel testo previgente (cause iscritte prima del 28/02/2023)._

**Parametri**:
- `data_udienza` (str, obbligatorio) — data dell'udienza di trattazione ex art. 183 c.p.c. (YYYY-MM-DD).

**Quando usare**: cause iscritte a ruolo prima della Riforma Cartabia; le memorie decorrono in avanti dall'udienza.

**Esempio**: `termini_183_190_cpc(data_udienza="2025-03-10")` → cinque scadenze: memorie n. 1/2/3 (30/60/80gg), conclusionale (60gg) e replica (80gg).

---

### `termini_esecuzioni`
_Calcola i termini nelle procedure esecutive: finestra utile per pignorare (10-90gg dal precetto) o opposizione agli atti esecutivi (20gg)._

**Parametri**:
- `data_notifica_titolo` (str, obbligatorio) — data di notifica del precetto al debitore (YYYY-MM-DD).
- `tipo` (str, opzionale, default `"pignoramento_mobiliare"`) — `'pignoramento_mobiliare'`, `'pignoramento_immobiliare'`, `'pignoramento_presso_terzi'`, `'opposizione_esecuzione'`.

**Quando usare**: pianificare il pignoramento dopo aver notificato il precetto, o verificare il termine per l'opposizione.

**Esempio**: `termini_esecuzioni(data_notifica_titolo="2025-02-01", tipo="pignoramento_mobiliare")` → finestra utile: dal 11/02 al 02/05/2025.

---

### `termini_deposito_atti_appello`
_Calcola termini per proporre appello (breve 30gg e lungo 6 mesi), iscrizione a ruolo e comparsa di risposta dell'appellato._

**Parametri**:
- `data_notifica_sentenza` (str, opzionale) — data di notifica della sentenza per il termine breve (YYYY-MM-DD).
- `data_pubblicazione` (str, opzionale) — data di pubblicazione per il termine lungo (YYYY-MM-DD).

**Quando usare**: pianificare le scadenze nell'arco temporale del giudizio di appello civile.

**Esempio**: `termini_deposito_atti_appello(data_pubblicazione="2024-07-15")` → termine lungo appello: 2025-01-15.

---

### `termini_deposito_ctu`
_Calcola le scadenze per il deposito della bozza CTU, le osservazioni delle parti (15gg) e la replica CTU definitiva (ulteriori 15gg)._

**Parametri**:
- `data_conferimento` (str, obbligatorio) — data del conferimento dell'incarico al CTU (YYYY-MM-DD).
- `giorni_termine` (int, opzionale, default `60`) — giorni per il deposito della bozza.

**Quando usare**: monitorare le scadenze del procedimento peritale ex art. 195 co. 3 c.p.c.

**Esempio**: `termini_deposito_ctu(data_conferimento="2025-01-20", giorni_termine=60)` → deposito bozza 20/03, osservazioni 04/04, replica definitiva 19/04/2025.

---

## 4. Atti Giudiziari

_Genera bozze di atti processuali (precetto, decreto ingiuntivo, sfratto, procura, note scritte, relata PEC) e calcola spese di giustizia (Contributo Unificato, diritti di copia, pignoramento stipendio, imposta di registro). Copre anche strumenti PCT come hash SHA-256, iscrizione a ruolo e visibilità del fascicolo._

---

### `contributo_unificato`
_Calcola il Contributo Unificato per valore della causa, tipo di procedimento e grado di giudizio._

**Parametri**:
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `tipo_procedimento` (str, opzionale, default `"cognizione"`) — `'cognizione'`, `'esecuzione_immobiliare'`, `'esecuzione_mobiliare'`, `'monitorio'`, `'volontaria_giurisdizione'`, `'separazione_consensuale'`, `'separazione_giudiziale'`, `'divorzio_congiunto'`, `'divorzio_giudiziale'`, `'cautelari'`, `'lavoro'`, `'tributario'`, `'tar'`.
- `grado` (str, opzionale, default `"primo"`) — `'primo'`, `'appello'`, `'cassazione'`.

**Quando usare**: calcolare le spese di iscrizione a ruolo prima di depositare un atto.

**Esempio**: `contributo_unificato(valore_causa=30000, tipo_procedimento="cognizione", grado="primo")` → CU €518.

---

### `diritti_copia`
_Calcola i diritti di copia di atti giudiziari in formato cartaceo o digitale PCT._

**Parametri**:
- `n_pagine` (int, obbligatorio) — numero di pagine dell'atto.
- `tipo` (str, opzionale, default `"semplice"`) — `'semplice'`, `'autentica'`, `'esecutiva'`.
- `formato` (str, opzionale, default `"digitale"`) — `'digitale'` o `'cartaceo'`.
- `urgente` (bool, opzionale, default `False`) — maggiorazione +50% per urgenza (solo cartaceo).

**Quando usare**: quantificare i diritti da anticipare per ottenere copia di atti dal cancelliere.

**Esempio**: `diritti_copia(n_pagine=20, tipo="autentica", formato="digitale")` → tariffa forfettaria €6,48.

---

### `pignoramento_stipendio`
_Calcola la quota pignorabile dello stipendio o pensione ex art. 545 c.p.c. (1/5 ordinario, 1/3 alimentare, scaglioni fiscale)._

**Parametri**:
- `stipendio_netto_mensile` (float, obbligatorio) — stipendio o pensione netta mensile in euro.
- `tipo_credito` (str, opzionale, default `"ordinario"`) — `'ordinario'` (1/5), `'alimentare'` (1/3), `'fiscale'` (scaglioni), `'concorso_crediti'` (1/2).

**Quando usare**: calcolare la quota da trattenere in un pignoramento presso il datore di lavoro o INPS.

**Esempio**: `pignoramento_stipendio(stipendio_netto_mensile=1800, tipo_credito="ordinario")` → importo pignorabile €360/mese, non pignorabile €1.440.

---

### `sollecito_pagamento`
_Genera bozza di lettera di sollecito pagamento con calcolo degli interessi di mora e totale dovuto._

**Parametri**:
- `creditore` (str, obbligatorio) — nome o ragione sociale del creditore.
- `debitore` (str, obbligatorio) — nome o ragione sociale del debitore.
- `importo` (float, obbligatorio) — importo del credito in euro.
- `data_scadenza` (str, obbligatorio) — data di scadenza originale (YYYY-MM-DD).
- `data_sollecito` (str, obbligatorio) — data di emissione del sollecito (YYYY-MM-DD).
- `tasso_mora` (float, opzionale, default `None`) — tasso personalizzato %; se `None` usa D.Lgs. 231/2002.

**Quando usare**: prima di intraprendere vie legali, per mettere in mora formalmente il debitore.

**Esempio**: `sollecito_pagamento(creditore="Alfa Srl", debitore="Beta Srl", importo=5000, data_scadenza="2024-10-01", data_sollecito="2025-02-01")` → lettera pronta con interessi di mora calcolati al tasso BCE del periodo.

---

### `decreto_ingiuntivo`
_Genera bozza di ricorso per decreto ingiuntivo con giudice competente per valore e CU monitorio._

**Parametri**:
- `creditore` (str, obbligatorio) — nome del creditore.
- `debitore` (str, obbligatorio) — nome del debitore.
- `importo` (float, obbligatorio) — importo del credito in euro.
- `tipo_credito` (str, opzionale, default `"ordinario"`) — `'ordinario'`, `'professionale'`, `'condominiale'`, `'cambiale'`.
- `provvisoria_esecuzione` (bool, opzionale, default `False`) — `True` per richiedere clausola art. 642 c.p.c.

**Quando usare**: avviare il procedimento monitorio per crediti certi, liquidi ed esigibili.

**Esempio**: `decreto_ingiuntivo(creditore="Gamma Srl", debitore="Delta Srl", importo=12000, tipo_credito="ordinario", provvisoria_esecuzione=True)` → bozza ricorso con Tribunale competente e CU dimezzato.

---

### `calcolo_hash`
_Calcola l'impronta SHA-256 di un testo per il deposito telematico PCT._

**Parametri**:
- `testo` (str, obbligatorio) — testo o contenuto del documento.

**Quando usare**: generare l'hash da inserire nella busta telematica PCT (DM 44/2011).

**Esempio**: `calcolo_hash(testo="Verbale udienza del 10/01/2025")` → hash SHA-256 a 64 caratteri esadecimali.

---

### `tassazione_atti`
_Calcola l'imposta di registro su atti giudiziari (sentenza, decreto ingiuntivo, verbale di conciliazione, ordinanza)._

**Parametri**:
- `tipo_atto` (str, obbligatorio) — `'sentenza_condanna'`, `'decreto_ingiuntivo'`, `'verbale_conciliazione'`, `'ordinanza'`.
- `valore` (float, obbligatorio) — valore dell'atto in euro.
- `prima_casa` (bool, opzionale, default `False`) — aliquota agevolata 2% per verbale conciliazione prima casa.

**Quando usare**: calcolare l'imposta di registro da versare dopo l'emissione di un provvedimento giudiziale.

**Esempio**: `tassazione_atti(tipo_atto="sentenza_condanna", valore=25000)` → imposta €750 (3% con minimo €200).

---

### `copie_processo_tributario`
_Calcola i diritti di copia specifici per il processo tributario (€0,25/pag semplice, €0,50 autentica)._

**Parametri**:
- `n_pagine` (int, obbligatorio) — numero di pagine dell'atto.
- `tipo` (str, opzionale, default `"semplice"`) — `'semplice'` o `'autentica'`.
- `urgente` (bool, opzionale, default `False`) — maggiorazione +50% per urgenza.

**Quando usare**: quantificare i diritti per copie di atti nel processo tributario.

**Esempio**: `copie_processo_tributario(n_pagine=30, tipo="autentica", urgente=False)` → totale €15,00.

---

### `note_iscrizione_ruolo`
_Genera note per l'iscrizione a ruolo con codici oggetto suggeriti e CU calcolato per il tipo di procedimento._

**Parametri**:
- `tipo_procedimento` (str, obbligatorio) — `'cognizione_ordinaria'`, `'lavoro'`, `'locazione'`, `'condominio'`, `'esecuzione_mobiliare'`, `'esecuzione_immobiliare'`, `'monitorio'`, `'volontaria_giurisdizione'`.
- `valore_causa` (float, opzionale) — valore della causa in euro per calcolare il CU.

**Quando usare**: predisporre le note per il deposito dell'atto introduttivo via PCT.

**Esempio**: `note_iscrizione_ruolo(tipo_procedimento="monitorio", valore_causa=8000)` → CU dimezzato + codici oggetto suggeriti per materia contrattuale.

---

### `codici_iscrizione_ruolo`
_Ricerca il codice oggetto per l'iscrizione a ruolo per keyword di materia._

**Parametri**:
- `materia` (str, obbligatorio) — keyword di ricerca (es. `'locazione'`, `'lavoro'`, `'bancario'`).

**Quando usare**: trovare rapidamente il codice DGSIA corretto prima del deposito telematico.

**Esempio**: `codici_iscrizione_ruolo(materia="locazione")` → elenco codici con descrizione per contratti di locazione.

---

### `fascicolo_di_parte`
_Genera bozza di frontespizio per il fascicolo di parte ex art. 165 c.p.c._

**Parametri**:
- `avvocato` (str, obbligatorio) — nome dell'avvocato difensore.
- `parte` (str, obbligatorio) — nome della parte assistita.
- `controparte` (str, obbligatorio) — nome della controparte.
- `tribunale` (str, obbligatorio) — denominazione completa del tribunale.
- `rg_numero` (str, opzionale) — numero RG se già assegnato.

**Quando usare**: preparare il frontespizio del fascicolo cartaceo per la costituzione in giudizio.

**Esempio**: `fascicolo_di_parte(avvocato="Avv. Rossi", parte="Mario Verdi", controparte="Anna Neri", tribunale="Tribunale di Milano")` → frontespizio pronto con indice documenti.

---

### `procura_alle_liti`
_Genera bozza di procura alle liti ex art. 83 c.p.c., con clausola GDPR e antiriciclaggio._

**Parametri**:
- `parte` (str, obbligatorio) — nome della parte che conferisce la procura.
- `avvocato` (str, obbligatorio) — nome e cognome dell'avvocato.
- `cf_avvocato` (str, obbligatorio) — codice fiscale dell'avvocato.
- `foro` (str, obbligatorio) — foro di appartenenza.
- `oggetto_causa` (str, obbligatorio) — descrizione sintetica dell'oggetto.
- `tipo` (str, opzionale, default `"generale"`) — `'generale'`, `'speciale'`, `'appello'`.

**Quando usare**: allegare la procura all'atto introduttivo o al ricorso; la bozza include già il consenso GDPR.

**Esempio**: `procura_alle_liti(parte="Marco Bianchi", avvocato="Laura Conti", cf_avvocato="CNTLRA75A01F205X", foro="Milano", oggetto_causa="risarcimento danni da sinistro stradale", tipo="speciale")` → testo procura speciale con tutte le clausole di legge.

---

### `attestazione_conformita`
_Genera bozza di attestazione di conformità per il deposito telematico PCT (art. 16-bis co. 9-bis DL 179/2012)._

**Parametri**:
- `avvocato` (str, obbligatorio) — nome e cognome dell'avvocato attestante.
- `tipo_documento` (str, obbligatorio) — descrizione del tipo di documento (es. `"verbale di causa"`).
- `estremi_originale` (str, obbligatorio) — estremi identificativi dell'originale.
- `modalita` (str, opzionale, default `"estratto"`) — `'estratto'`, `'copia_informatica'`, `'duplicato'`.

**Quando usare**: attestare la conformità di copie informatiche o estratti da depositare telematicamente.

**Esempio**: `attestazione_conformita(avvocato="Paolo Ferri", tipo_documento="verbale udienza", estremi_originale="R.G. 1234/2024, pag. 1-3")` → testo attestazione pronto per firma digitale.

---

### `relata_notifica_pec`
_Genera bozza di relata di notificazione a mezzo PEC ex art. 3-bis L. 53/1994._

**Parametri**:
- `avvocato` (str, obbligatorio) — nome dell'avvocato notificante.
- `destinatario` (str, obbligatorio) — nome del destinatario.
- `pec_destinatario` (str, obbligatorio) — indirizzo PEC del destinatario (da INI-PEC/ReGIndE).
- `atto_notificato` (str, obbligatorio) — descrizione dell'atto notificato.
- `data_invio` (str, obbligatorio) — data di invio PEC (YYYY-MM-DD).

**Quando usare**: allegare la relata al deposito telematico dopo una notifica via PEC.

**Esempio**: `relata_notifica_pec(avvocato="Avv. Esposito", destinatario="Beta Srl", pec_destinatario="beta@pec.it", atto_notificato="ricorso per decreto ingiuntivo", data_invio="2025-02-10")` → relata pronta per firma digitale.

---

### `indice_documenti`
_Genera bozza di indice numerato degli allegati per il deposito telematico PCT._

**Parametri**:
- `documenti` (list[dict], obbligatorio) — lista di dict con `numero` (int), `descrizione` (str), `pagine` (int).

**Quando usare**: predisporre l'elenco allegati da includere nella busta PCT.

**Esempio**: `indice_documenti(documenti=[{"numero":1,"descrizione":"Contratto","pagine":5},{"numero":2,"descrizione":"Fattura","pagine":2}])` → indice formattato con totale pagine.

---

### `note_trattazione_scritta`
_Genera bozza di note di trattazione scritta ex art. 127-ter c.p.c. in sostituzione dell'udienza (Riforma Cartabia)._

**Parametri**:
- `avvocato` (str, obbligatorio) — nome dell'avvocato depositante.
- `parte` (str, obbligatorio) — nome della parte assistita.
- `tribunale` (str, obbligatorio) — denominazione del tribunale.
- `rg_numero` (str, obbligatorio) — numero RG del procedimento.
- `giudice` (str, obbligatorio) — nome del giudice istruttore.
- `conclusioni` (str, obbligatorio) — testo delle conclusioni.

**Quando usare**: depositare note scritte quando il giudice sostituisce l'udienza con trattazione scritta (frequente post-Cartabia).

**Esempio**: `note_trattazione_scritta(avvocato="Avv. Ricci", parte="Gamma Spa", tribunale="Tribunale di Roma", rg_numero="567/2025", giudice="Dr. Mancini", conclusioni="Accogliere tutte le domande attrici")` → bozza note pronta per deposito PCT.

---

### `sfratto_morosita`
_Genera bozza di intimazione di sfratto per morosità con citazione per la convalida ex artt. 658 ss. c.p.c._

**Parametri**:
- `locatore` (str, obbligatorio) — nome del locatore.
- `conduttore` (str, obbligatorio) — nome del conduttore moroso.
- `immobile` (str, obbligatorio) — descrizione e indirizzo dell'immobile.
- `canone_mensile` (float, obbligatorio) — canone mensile in euro.
- `mensilita_insolute` (int, obbligatorio) — numero di mensilità non pagate.
- `data_contratto` (str, obbligatorio) — data di stipula del contratto (YYYY-MM-DD).

**Quando usare**: avviare il procedimento di sfratto per morosità del conduttore.

**Esempio**: `sfratto_morosita(locatore="Giuseppe Verdi", conduttore="Lucia Bianchi", immobile="Via Garibaldi 10, Milano", canone_mensile=700, mensilita_insolute=4, data_contratto="2021-03-01")` → bozza intimazione con totale dovuto €2.800.

---

### `atto_di_precetto`
_Genera bozza di atto di precetto ex art. 480 c.p.c. con avvertimento per opposizione e riepilogo importi._

**Parametri**:
- `creditore` (str, obbligatorio) — nome del creditore.
- `debitore` (str, obbligatorio) — nome del debitore.
- `titolo_esecutivo` (str, obbligatorio) — descrizione del titolo (es. sentenza, decreto ingiuntivo esecutivo).
- `importo_capitale` (float, obbligatorio) — capitale in euro.
- `interessi` (float, opzionale, default `0`) — interessi maturati in euro.
- `spese` (float, opzionale, default `0`) — spese legali in euro.

**Quando usare**: dopo il passaggio in giudicato di una sentenza o decreto ingiuntivo, prima di pignorare.

**Esempio**: `atto_di_precetto(creditore="Alfa Srl", debitore="Beta Srl", titolo_esecutivo="sentenza Trib. Milano 123/2024", importo_capitale=10000, interessi=350, spese=800)` → bozza precetto con totale intimato €11.150.

---

### `nota_precisazione_credito`
_Genera bozza di nota di precisazione del credito per procedure esecutive ex art. 547 c.p.c._

**Parametri**:
- `creditore` (str, obbligatorio) — nome del creditore procedente.
- `debitore` (str, obbligatorio) — nome del debitore esecutato.
- `procedura_esecutiva` (str, obbligatorio) — estremi della procedura (es. `"R.G.E. 123/2024"`).
- `capitale` (float, obbligatorio) — capitale in euro.
- `interessi` (float, obbligatorio) — interessi maturati in euro.
- `spese_legali` (float, obbligatorio) — spese legali in euro.
- `spese_esecuzione` (float, obbligatorio) — spese di esecuzione in euro.

**Quando usare**: depositare la nota di precisazione del credito nell'udienza di distribuzione.

**Esempio**: `nota_precisazione_credito(creditore="Alfa Srl", debitore="Beta Srl", procedura_esecutiva="R.G.E. 45/2024", capitale=10000, interessi=400, spese_legali=1200, spese_esecuzione=150)` → bozza nota con totale credito €11.750.

---

### `dichiarazione_553_cpc`
_Genera bozza di dichiarazione del terzo pignorato ex art. 547 c.p.c. (banca, datore di lavoro o generico)._

**Parametri**:
- `terzo_pignorato` (str, obbligatorio) — nome del terzo pignorato (banca, datore di lavoro, ecc.).
- `debitore` (str, obbligatorio) — nome del debitore esecutato.
- `procedura` (str, obbligatorio) — estremi della procedura esecutiva.
- `tipo_rapporto` (str, opzionale, default `"conto_corrente"`) — `'conto_corrente'`, `'stipendio'`, `'altro'`.

**Quando usare**: il terzo pignorato (es. banca) deve dichiarare i rapporti con il debitore prima dell'udienza.

**Esempio**: `dichiarazione_553_cpc(terzo_pignorato="Banca Gamma SpA", debitore="Mario Rossi", procedura="R.G.E. 78/2024", tipo_rapporto="conto_corrente")` → bozza dichiarazione con sezione conto corrente da compilare.

---

### `testimonianza_scritta`
_Genera bozza del modulo per testimonianza scritta ex art. 257-bis c.p.c. con capitoli e ammonizione._

**Parametri**:
- `teste` (str, obbligatorio) — nome e cognome del testimone.
- `capitoli_prova` (list[str], obbligatorio) — lista dei capitoli di prova su cui rispondere.

**Quando usare**: il giudice autorizza la testimonianza scritta; si consegna il modulo al teste da compilare e restituire.

**Esempio**: `testimonianza_scritta(teste="Carlo Neri", capitoli_prova=["È vero che il 10/01/2024 lei era presente in Via Roma 1?"])` → modulo con ammonizione, giuramento e campi risposta per ogni capitolo.

---

### `istanza_visibilita_fascicolo`
_Genera bozza di istanza di visibilità del fascicolo telematico per avvocato non ancora costituito._

**Parametri**:
- `avvocato` (str, obbligatorio) — nome dell'avvocato richiedente.
- `parte` (str, obbligatorio) — nome della parte assistita.
- `tribunale` (str, obbligatorio) — denominazione del tribunale.
- `rg_numero` (str, obbligatorio) — numero RG del procedimento.
- `motivo` (str, opzionale, default `"costituzione"`) — `'costituzione'`, `'consultazione'`, `'intervento'`.

**Quando usare**: l'avvocato non ancora costituito deve visionare gli atti per predisporre la difesa.

**Esempio**: `istanza_visibilita_fascicolo(avvocato="Avv. Marino", parte="Epsilon Srl", tribunale="Tribunale di Napoli, Sezione Prima Civile", rg_numero="2345/2025")` → bozza istanza pronta per deposito PCT.

---

### `cerca_ufficio_giudiziario`
_Cerca il tribunale o il giudice di pace territorialmente competente per un comune italiano._

**Parametri**:
- `comune` (str, obbligatorio) — nome del comune (es. `"Milano"`, `"Brescia"`).
- `tipo` (str, opzionale, default `"tribunale"`) — `'tribunale'` o `'giudice_pace'`.

**Quando usare**: verificare rapidamente la competenza territoriale prima di depositare un atto.

**Esempio**: `cerca_ufficio_giudiziario(comune="Bergamo", tipo="tribunale")` → Tribunale di Bergamo (con nota di verifica sul sito Min. Giustizia per comuni minori).

---

## 5. Fatturazione Avvocati

_Calcola compensi tabellari (DM 55/2014 aggiornato DM 147/2022) per contenzioso civile, penale, stragiudiziale e volontaria giurisdizione; genera preventivi completi con spese generali (15%), CPA (4%) e IVA (22%); struttura fatture e notule. Da usare per quantificare il compenso in qualsiasi fase della gestione della pratica._

---

### `parcella_avvocato_civile`
_Calcola il compenso tabellare per fase nel contenzioso civile (scaglioni per valore della causa)._

**Parametri**:
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `fasi` (list[str], opzionale, default tutte) — sottoinsieme di `['studio', 'introduttiva', 'istruttoria', 'decisionale']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.

**Quando usare**: stimare il compenso professionale in una causa civile o verificare la congruità di una parcella avversaria.

**Esempio**: `parcella_avvocato_civile(valore_causa=50000, fasi=["studio","introduttiva"], livello="medio")` → compenso tabellare per le due fasi con scaglione applicato.

---

### `parcella_avvocato_penale`
_Calcola il compenso tabellare per fase nel procedimento penale in base all'organo giudicante._

**Parametri**:
- `competenza` (str, obbligatorio) — `'giudice_pace'`, `'tribunale_monocratico'`, `'tribunale_collegiale'`, `'corte_assise'`, `'corte_appello'`, `'cassazione'`.
- `fasi` (list[str], opzionale, default tutte applicabili) — sottoinsieme di `['studio', 'introduttiva', 'istruttoria', 'decisionale']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.

**Quando usare**: stimare il compenso per un procedimento penale o elaborare la parcella per il cliente.

**Esempio**: `parcella_avvocato_penale(competenza="tribunale_monocratico", livello="medio")` → compenso tabellare per tutte le fasi applicabili al tribunale monocratico.

---

### `parcella_stragiudiziale`
_Calcola il compenso tabellare per attività stragiudiziale (diffida, trattativa, negoziazione)._

**Parametri**:
- `valore_pratica` (float, obbligatorio) — valore della pratica in euro.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.

**Quando usare**: quantificare il compenso per una diffida, una negoziazione assistita o una mediazione stragiudiziale.

**Esempio**: `parcella_stragiudiziale(valore_pratica=15000, livello="medio")` → compenso tabellare stragiudiziale per la pratica.

---

### `parcella_volontaria_giurisdizione`
_Calcola il compenso tabellare per procedimenti non contenziosi (interdizioni, amministrazioni di sostegno, DAT, ecc.) — Tab. 7 DM 55/2014._

**Parametri**:
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `fasi` (list[str], opzionale, default tutte) — sottoinsieme di `['studio', 'trattazione']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.

**Quando usare**: compenso per procedimenti non contenziosi; NON usare per cause civili contenziose.

**Esempio**: `parcella_volontaria_giurisdizione(valore_causa=5000, livello="medio")` → compenso fasi studio e trattazione con Tab. 7.

---

### `preventivo_volontaria_giurisdizione`
_Genera preventivo completo per volontaria giurisdizione con spese generali (15%), CPA (4%) e IVA (22%)._

**Parametri**:
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `fasi` (list[str], opzionale, default tutte) — `['studio', 'trattazione']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.
- `spese_generali` (bool, opzionale, default `True`) — aggiunge 15% spese generali.
- `cpa` (bool, opzionale, default `True`) — aggiunge CPA 4%.
- `iva` (bool, opzionale, default `True`) — aggiunge IVA 22%.

**Quando usare**: inviare al cliente il preventivo completo per un procedimento di volontaria giurisdizione.

**Esempio**: `preventivo_volontaria_giurisdizione(valore_causa=8000)` → totale onorari con tutti gli accessori fiscali e previdenziali.

---

### `fattura_avvocato`
_Genera la struttura della fattura con CPA (4%), IVA (22%) e ritenuta d'acconto (20%) per regime ordinario, o senza IVA/ritenuta per forfettario._

**Parametri**:
- `imponibile` (float, obbligatorio) — compenso professionale in euro.
- `regime` (str, opzionale, default `"ordinario"`) — `'ordinario'` o `'forfettario'`.
- `cpa` (bool, opzionale, default `True`) — applica CPA 4%.

**Quando usare**: calcolare il netto a pagare da indicare nella fattura professionale.

**Esempio**: `fattura_avvocato(imponibile=2000, regime="ordinario")` → CPA €80, IVA €457,60, ritenuta €400, netto a pagare €2.137,60.

---

### `nota_spese`
_Calcola la nota spese aggregando voci di compenso, spese generali (15%), spese vive e documentate, con CPA (4%) e IVA (22%)._

**Parametri**:
- `voci` (list[dict], obbligatorio) — lista di dict con `descrizione` (str), `importo` (float), `tipo` (`'compenso'`, `'spese_generali_15pct'`, `'spese_vive'`, `'spese_documentate'`).

**Quando usare**: preparare la nota spese da allegare alla parcella con separazione tra compensi e spese vive.

**Esempio**: `nota_spese(voci=[{"descrizione":"Onorari","importo":1500,"tipo":"compenso"},{"descrizione":"CU","importo":237,"tipo":"spese_vive"}])` → totale nota spese con dettaglio accessori fiscali.

---

### `preventivo_civile`
_Genera preventivo completo per causa civile: compensi tabellari, spese generali (15%), CPA (4%), IVA (22%) e spese vive stimate (CU, marca, notifica, ecc.)._

**Parametri**:
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `fasi` (list[str], opzionale, default tutte) — `['studio', 'introduttiva', 'istruttoria', 'decisionale']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.
- `spese_generali` (bool, opzionale, default `True`) — aggiunge 15%.
- `cpa` (bool, opzionale, default `True`) — aggiunge CPA 4%.
- `iva` (bool, opzionale, default `True`) — aggiunge IVA 22%.

**Quando usare**: fornire al cliente un preventivo all-inclusive prima di accettare l'incarico.

**Esempio**: `preventivo_civile(valore_causa=30000, livello="medio")` → preventivo formattato con totale onorari + spese vive stimate.

---

### `preventivo_stragiudiziale`
_Genera preventivo per attività stragiudiziale con spese generali (15%), CPA (4%) e IVA (22%)._

**Parametri**:
- `valore_pratica` (float, obbligatorio) — valore della pratica in euro.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.
- `spese_generali` (bool, opzionale, default `True`) — aggiunge 15%.
- `cpa` (bool, opzionale, default `True`) — aggiunge CPA 4%.
- `iva` (bool, opzionale, default `True`) — aggiunge IVA 22%.

**Quando usare**: preventivare il costo di una diffida o trattativa stragiudiziale al cliente.

**Esempio**: `preventivo_stragiudiziale(valore_pratica=10000, livello="medio")` → totale preventivo con accessori fiscali.

---

### `spese_trasferta_avvocati`
_Calcola indennità di trasferta (10-40% dell'onorario di riferimento per fasce orarie) e rimborso km (€0,30/km per auto)._

**Parametri**:
- `km_distanza` (float, obbligatorio) — distanza andata/ritorno in km.
- `ore_assenza` (float, obbligatorio) — ore di assenza dallo studio.
- `pernottamento` (bool, opzionale, default `False`) — se necessario pernottamento (rimborso a piè di lista).
- `mezzo` (str, opzionale, default `"auto"`) — `'auto'`, `'treno'`, `'aereo'`.

**Quando usare**: aggiungere le spese di trasferta alla parcella per udienze fuori sede.

**Esempio**: `spese_trasferta_avvocati(km_distanza=120, ore_assenza=5, mezzo="auto")` → indennità €108 (20%) + rimborso km €36 = totale €144.

---

### `modello_notula`
_Genera notula completa formattata (compensi + spese vive stimate) per procedimenti tipici di recupero crediti._

**Parametri**:
- `tipo_procedimento` (str, obbligatorio) — `'decreto_ingiuntivo'`, `'precetto'`, `'esecuzione_mobiliare'`, `'esecuzione_immobiliare'`.
- `avvocato` (str, obbligatorio) — nome dell'avvocato.
- `cliente` (str, obbligatorio) — nome del cliente.
- `valore_causa` (float, obbligatorio) — valore della causa in euro.
- `fasi` (list[str], opzionale) — fasi da includere; default: fasi tipiche del procedimento.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.

**Quando usare**: generare una notula pronta per il cliente al termine di un procedimento di recupero crediti.

**Esempio**: `modello_notula(tipo_procedimento="decreto_ingiuntivo", avvocato="Avv. Sala", cliente="Alfa Srl", valore_causa=12000)` → notula formattata con CU dimezzato e totale onorari.

---

### `calcolo_notula_penale`
_Calcola la parcella penale completa con spese generali (15%), CPA (4%) e IVA (22%), equivalente a `parcella_avvocato_penale` ma con totale già calcolato._

**Parametri**:
- `competenza` (str, obbligatorio) — `'giudice_pace'`, `'tribunale_monocratico'`, `'tribunale_collegiale'`, `'corte_assise'`, `'corte_appello'`, `'cassazione'`.
- `fasi` (list[str], opzionale, default tutte applicabili) — `['studio', 'introduttiva', 'istruttoria', 'decisionale']`.
- `livello` (str, opzionale, default `"medio"`) — `'min'`, `'medio'`, `'max'`.
- `spese_generali` (bool, opzionale, default `True`) — aggiunge 15% ex art. 2 DM 55/2014.

**Quando usare**: emettere la parcella finale al cliente per un procedimento penale, già con tutti gli accessori.

**Esempio**: `calcolo_notula_penale(competenza="tribunale_collegiale", livello="medio")` → totale parcella penale con CPA, IVA e spese generali inclusi.

---


---


## 6. Parcelle Altri Professionisti
_Strumenti per calcolare compensi e fatture di professionisti non avvocati: ingegneri, architetti, commercialisti, CTU, agenti di commercio, curatori fallimentari e mediatori. Utile sia per emettere fatture corrette sia per verificare la congruità di un compenso ricevuto._

### `fattura_professionista`
_Calcola l'importo netto a pagare di una fattura professionale con rivalsa INPS, IVA 22% e ritenuta d'acconto._

**Parametri**: `imponibile` (float, obbligatorio) — compenso professionale in €. `tipo` (str, opzionale, default `"ingegnere"`) — categoria: `ingegnere`, `architetto`, `geometra`, `commercialista`, `consulente_lavoro`, `psicologo`, `medico`. `regime` (str, opzionale, default `"ordinario"`) — `"ordinario"` (IVA 22% + ritenuta 20%) o `"forfettario"` (no IVA, no ritenuta, bollo se >€77,47).

**Quando usare**: per emettere o controllare una parcella di un professionista non avvocato, verificando rivalsa e ritenuta corrette.

**Esempio**: `fattura_professionista(imponibile=5000, tipo="commercialista", regime="ordinario")` → netto da pagare €5.264 (rivalsa 4%, IVA 22%, ritenuta 20%).

---

### `compenso_ctu`
_Stima il compenso orientativo del consulente tecnico d'ufficio (CTU) nominato dal giudice, a percentuale sul valore della causa o a tariffa oraria._

**Parametri**: `tipo_incarico` (str, obbligatorio) — `perizia_immobiliare`, `perizia_contabile`, `perizia_medica`, `stima_danni`, `accertamenti_tecnici`. `valore_causa` (float, opzionale) — valore della causa in €. `ore_lavoro` (float, opzionale) — ore effettive lavorate. Almeno uno dei due è obbligatorio.

**Quando usare**: per stimare il compenso di un CTU prima dell'udienza di liquidazione, o per verificare la congruità del decreto del giudice.

**Esempio**: `compenso_ctu(tipo_incarico="perizia_immobiliare", valore_causa=300000)` → range orientativo min/max per la liquidazione.

---

### `spese_mediazione`
_Calcola le indennità dovute all'organismo di mediazione per scaglione di valore della controversia, distinguendo esito positivo e negativo._

**Parametri**: `valore_controversia` (float, obbligatorio) — valore in €. `esito` (str, opzionale, default `"positivo"`) — `"positivo"` (accordo) o `"negativo"` (mancato accordo).

**Quando usare**: per stimare il costo di una procedura di mediazione civile obbligatoria prima di avviarla.

**Esempio**: `spese_mediazione(valore_controversia=30000, esito="positivo")` → indennità per parte, IVA e totale organismo.

---

### `compenso_orario`
_Calcola il compenso professionale a ore con arrotondamento per eccesso al quarto d'ora, alla mezz'ora o all'ora._

**Parametri**: `tariffa_oraria` (float, obbligatorio) — €/ora. `ore` (int, obbligatorio) — ore lavorate. `minuti` (int, opzionale, default `0`) — minuti aggiuntivi (0-59). `arrotondamento` (str, opzionale, default `"mezz_ora"`) — `"quarto_ora"`, `"mezz_ora"`, `"ora"`.

**Quando usare**: quando il professionista fattura a ore e occorre arrotondare il tempo per eccesso all'unità stabilita nel mandato.

**Esempio**: `compenso_orario(tariffa_oraria=120, ore=2, minuti=20, arrotondamento="mezz_ora")` → compenso per 2h 30min = €300.

---

### `ritenuta_acconto`
_Calcola la ritenuta d'acconto su un compenso professionale e mostra i dati per la Certificazione Unica (CU)._

**Parametri**: `compenso_lordo` (float, obbligatorio) — base imponibile in €. `aliquota` (float, opzionale, default `20.0`) — aliquota percentuale (tipicamente 20% o 30%).

**Quando usare**: per compilare il modello F24 o la CU, o per verificare l'importo netto percepito dopo la ritenuta.

**Esempio**: `ritenuta_acconto(compenso_lordo=3000)` → ritenuta €600, netto €2.400, codice tributo F24 1040.

---

### `compenso_curatore_fallimentare`
_Calcola il compenso del curatore fallimentare applicando gli scaglioni progressivi del DM 30/2012 su attivo realizzato e passivo accertato._

**Parametri**: `attivo_realizzato` (float, obbligatorio) — attivo realizzato dalla procedura in €. `passivo_accertato` (float, obbligatorio) — passivo accertato in €.

**Quando usare**: per liquidare o contestare il compenso del curatore in una procedura fallimentare, verificando minimo (€811,31) e massimo (€405.656,80).

**Esempio**: `compenso_curatore_fallimentare(attivo_realizzato=500000, passivo_accertato=800000)` → compenso dettagliato per scaglioni su attivo + metà aliquota su passivo.

---

### `compenso_delegati_vendite`
_Calcola il compenso del professionista delegato alle vendite giudiziarie immobiliari per scaglioni del prezzo di aggiudicazione (DM 227/2015)._

**Parametri**: `prezzo_aggiudicazione` (float, obbligatorio) — prezzo di aggiudicazione in €.

**Quando usare**: per verificare il compenso del notaio o avvocato delegato alle operazioni di vendita in un'esecuzione immobiliare.

**Esempio**: `compenso_delegati_vendite(prezzo_aggiudicazione=250000)` → compenso €4.100 (2,6% su primi €100k + 1,5% su €150k).

---

### `compenso_mediatore_familiare`
_Stima il compenso totale del mediatore familiare calcolando gli incontri a pagamento (il primo informativo è gratuito)._

**Parametri**: `n_incontri` (int, obbligatorio) — numero totale di incontri incluso il primo gratuito. `tariffa_incontro` (float, opzionale, default `120.0`) — tariffa per singolo incontro a pagamento in €.

**Quando usare**: per stimare il costo di un percorso di mediazione familiare prima o durante la separazione.

**Esempio**: `compenso_mediatore_familiare(n_incontri=10, tariffa_incontro=120)` → compenso €1.080 (9 incontri a pagamento).

---

### `fattura_enasarco`
_Calcola la struttura completa della fattura di un agente di commercio con contributo Enasarco (17% totale 2026), IVA e ritenuta d'acconto sulle provvigioni._

**Parametri**: `provvigioni` (float, obbligatorio) — importo provvigioni in €. `tipo_agente` (str, opzionale, default `"monocommittente"`) — `"monocommittente"` o `"pluricommittente"`. `anno` (int, opzionale, default `2026`) — anno di riferimento per le aliquote.

**Quando usare**: per verificare i conteggi di una fattura da agente di commercio o per calcolare quanto versa il preponente con F24.

**Esempio**: `fattura_enasarco(provvigioni=10000, tipo_agente="monocommittente")` → quota agente Enasarco €850, quota preponente €850, IVA €2.200, ritenuta €1.150.

---

### `ricevuta_prestazione_occasionale`
_Genera il testo pronto della ricevuta per una prestazione occasionale con ritenuta 20% e bollo se l'importo supera €77,47._

**Parametri**: `compenso_lordo` (float, obbligatorio) — compenso pattuito in €. `committente` (str, obbligatorio) — nome/ragione sociale del committente. `prestatore` (str, obbligatorio) — nome e cognome del prestatore. `descrizione` (str, obbligatorio) — descrizione sintetica della prestazione.

**Quando usare**: per generare immediatamente la ricevuta da consegnare al committente per lavori saltuari entro €5.000 annui.

**Esempio**: `ricevuta_prestazione_occasionale(compenso_lordo=500, committente="Alfa Srl", prestatore="Mario Rossi", descrizione="Consulenza informatica")` → testo ricevuta completo con ritenuta €100 e bollo €2.

---

### `tariffe_mediazione`
_Restituisce la tabella completa degli scaglioni DM 150/2023 per il valore indicato, includendo spese di avvio (€40) e confronto esito positivo/negativo._

**Parametri**: `valore_controversia` (float, obbligatorio) — valore della controversia in €.

**Quando usare**: quando si vuole un quadro completo dei costi di mediazione (non solo lo scaglione applicabile) con tutte le possibili voci.

**Esempio**: `tariffe_mediazione(valore_controversia=80000)` → scaglione fino a €250.000, spese avvio €40, indennità positivo €1.060/parte, tabella tutti gli scaglioni.

---

## 7. Risarcimento Danni
_Strumenti per quantificare il risarcimento del danno non patrimoniale e patrimoniale: danno biologico micropermanente (art. 139 CdA) e macropermanente (art. 138 CdA), danno parentale, menomazioni plurime, indennizzo INAIL e equo indennizzo per causa di servizio._

### `danno_biologico_micro`
_Calcola il danno biologico per invalidità permanente tra 1% e 9% (micropermanenti) applicando le tabelle DM 18/07/2025, con invalidità temporanea e personalizzazione morale._

**Parametri**: `percentuale_invalidita` (int, obbligatorio, 1-9). `eta_vittima` (int, obbligatorio, 0-120). `giorni_itt` (int, opzionale, default `0`) — giorni ITT al 100%. `giorni_itp75` / `giorni_itp50` / `giorni_itp25` (int, opzionale, default `0`) — giorni ITP al 75%, 50%, 25%. `personalizzazione_pct` (float, opzionale, default `0`) — maggiorazione morale (0-33,33%).

**Quando usare**: per sinistri stradali o sanitari con invalidità permanente da 1% a 9% (RC auto obbligatoria).

**Esempio**: `danno_biologico_micro(percentuale_invalidita=5, eta_vittima=40, giorni_itt=20)` → risarcimento totale con dettaglio per punto e temporanea.

---

### `danno_biologico_macro`
_Calcola il danno biologico per invalidità permanente tra 10% e 100% (macropermanenti) con interpolazione dei punti tabellari e coefficiente età._

**Parametri**: `percentuale_invalidita` (int, obbligatorio, 10-100). `eta_vittima` (int, obbligatorio, 0-120). `personalizzazione_pct` (float, opzionale, default `0`) — maggiorazione morale (0-50%).

**Quando usare**: per invalidità gravi da sinistro o malasanità, dove la tabella unica nazionale ex art. 138 CdA è la base di calcolo.

**Esempio**: `danno_biologico_macro(percentuale_invalidita=30, eta_vittima=35, personalizzazione_pct=25)` → danno base + maggiorazione morale.

---

### `danno_parentale`
_Calcola il risarcimento per perdita del rapporto parentale (morte del congiunto) secondo le tabelle di Milano o Roma, con posizionamento nel range min-max._

**Parametri**: `vittima` (str, obbligatorio) — ruolo del deceduto: `figlio`, `genitore`, `coniuge`, `fratello`, `nipote`, `nonno`. `superstite` (str, obbligatorio) — ruolo del richiedente. `tabella` (str, opzionale, default `"milano"`) — `"milano"` o `"roma"`. `personalizzazione_pct` (float, opzionale, default `50`) — posizione nel range (0=minimo, 100=massimo).

**Quando usare**: per quantificare il danno da perdita del congiunto in un sinistro mortale o in un procedimento civile di responsabilità.

**Esempio**: `danno_parentale(vittima="genitore", superstite="figlio", tabella="milano")` → importo liquidato con range min/max tabelle Milano 2024.

---

### `menomazioni_plurime`
_Calcola l'invalidità complessiva quando il danneggiato presenta più menomazioni distinte, applicando la formula Balthazard (riduzione proporzionale)._

**Parametri**: `percentuali` (list[float], obbligatorio) — lista delle percentuali di invalidità per ciascuna menomazione in ordine decrescente; minimo 2 valori.

**Quando usare**: quando il medico legale ha accertato più menomazioni separate da cumulare correttamente prima di applicare le tabelle biologico.

**Esempio**: `menomazioni_plurime(percentuali=[15, 10, 5])` → invalidità complessiva 27,33% (vs somma aritmetica 30%).

---

### `risarcimento_inail`
_Calcola l'indennizzo INAIL per infortunio sul lavoro o malattia professionale: in capitale (6-15%), rendita (>15%) o indennità temporanea giornaliera._

**Parametri**: `retribuzione_annua` (float, obbligatorio) — RAL del lavoratore in €. `percentuale_invalidita` (float, obbligatorio, 0-100). `tipo` (str, opzionale, default `"permanente"`) — `"permanente"` o `"temporanea"`.

**Quando usare**: per stimare l'indennizzo INAIL spettante dopo il riconoscimento dell'infortunio o della malattia professionale.

**Esempio**: `risarcimento_inail(retribuzione_annua=30000, percentuale_invalidita=20, tipo="permanente")` → rendita annua lorda con quota biologica e patrimoniale.

---

### `danno_non_patrimoniale`
_Prospetto completo del danno non patrimoniale con tutte le componenti in un unico calcolo: biologico (micro/macro automatico), morale, esistenziale e patrimoniale emergente._

**Parametri**: `percentuale_invalidita` (int, obbligatorio, 1-100). `eta_vittima` (int, obbligatorio). `tipo_danno` (str, opzionale, default `"biologico"`). `giorni_itt` (int, opzionale, default `0`). `spese_mediche` (float, opzionale, default `0`). `danno_morale_pct` (float, opzionale, 0-50). `danno_esistenziale_pct` (float, opzionale, 0-50).

**Quando usare**: per predisporre il prospetto risarcitorio completo da allegare all'atto di citazione o alla richiesta stragiudiziale.

**Esempio**: `danno_non_patrimoniale(percentuale_invalidita=12, eta_vittima=45, giorni_itt=30, spese_mediche=2500, danno_morale_pct=25)` → totale con dettaglio per ciascuna voce.

---

### `equo_indennizzo`
_Calcola l'equo indennizzo per causa di servizio per dipendenti pubblici. ATTENZIONE: istituto abrogato per eventi successivi al 06/12/2011._

**Parametri**: `categoria_tabella` (str, obbligatorio) — categoria Tabella A DPR 834/1981 da `"1"` (81-100%) a `"8"` (1-10%). `percentuale_invalidita` (float, obbligatorio). `stipendio_annuo` (float, obbligatorio) — ultimo stipendio annuo lordo in €.

**Quando usare**: esclusivamente per pratiche relative a fatti anteriori al 06/12/2011 di dipendenti pubblici con infermità da causa di servizio.

**Esempio**: `equo_indennizzo(categoria_tabella="5", percentuale_invalidita=35, stipendio_annuo=28000)` → equo indennizzo €29.400 (coefficiente 3,0 cat. 5).

---

## 8. Diritto Penale
_Strumenti per calcolare la pena risultante dopo aggravanti/attenuanti, simulare il patteggiamento, determinare la data di fine pena, verificare la prescrizione del reato e convertire pena detentiva in pecuniaria._

### `aumenti_riduzioni_pena`
_Calcola la pena finale partendo dalla pena base edittale e applicando in sequenza recidiva, aggravanti e attenuanti con i rispettivi aumenti/riduzioni percentuali._

**Parametri**: `pena_base_mesi` (float, obbligatorio) — pena base in mesi. `aggravanti` (list[dict], opzionale) — lista di `{"tipo": str, "aumento_pct": float}`. `attenuanti` (list[dict], opzionale) — lista di `{"tipo": str, "riduzione_pct": float}`. `recidiva` (bool, opzionale, default `False`) — applica +1/3 ex art. 99 c.p.

**Quando usare**: per simulare la pena risultante in udienza di discussione pena, con il dettaglio di ogni step.

**Esempio**: `aumenti_riduzioni_pena(pena_base_mesi=24, aggravanti=[{"tipo": "art. 61 n.7 c.p.", "aumento_pct": 33.33}], attenuanti=[{"tipo": "art. 62 n.6 c.p.", "riduzione_pct": 33.33}])` → pena invariata con dettaglio step.

---

### `conversione_pena`
_Converte pena detentiva in pecuniaria o viceversa al tasso legale di €250 per giorno (art. 135 c.p.)._

**Parametri**: `importo` (float, obbligatorio) — giorni di detenzione (se `detentiva_a_pecuniaria`) oppure importo in € (se `pecuniaria_a_detentiva`). `direzione` (str, opzionale, default `"detentiva_a_pecuniaria"`). `tipo_pena` (str, opzionale, default `"reclusione"`) — `"reclusione"` o `"arresto"`.

**Quando usare**: per verificare l'equivalenza pena-multa in sede di conversione ex art. 135 c.p. o per ragguaglio nell'applicazione dei benefici.

**Esempio**: `conversione_pena(importo=120, direzione="detentiva_a_pecuniaria")` → €30.000 (120 giorni × €250).

---

### `fine_pena`
_Calcola la data di fine pena con liberazione anticipata (45 giorni per semestre) e deducendo i giorni di presofferto in custodia cautelare._

**Parametri**: `data_inizio_pena` (str, obbligatorio, formato `YYYY-MM-DD`). `pena_totale_mesi` (float, obbligatorio). `liberazione_anticipata` (bool, opzionale, default `True`). `giorni_presofferto` (int, opzionale, default `0`).

**Quando usare**: per calcolare la data di espiazione della pena di un detenuto, con e senza il beneficio della liberazione anticipata.

**Esempio**: `fine_pena(data_inizio_pena="2024-03-01", pena_totale_mesi=36, giorni_presofferto=90)` → data fine pena ordinaria e con liberazione anticipata (sconto 270 giorni su 6 semestri).

---

### `prescrizione_reato`
_Calcola il termine di prescrizione del reato e la data di prescrizione, con effetto delle interruzioni (+1/4 del termine base) e sospensioni._

**Parametri**: `pena_massima_anni` (float, obbligatorio) — massimo edittale in anni. `data_commissione` (str, obbligatorio, formato `YYYY-MM-DD`). `interruzioni_giorni` (int, opzionale, default `0`). `sospensioni_giorni` (int, opzionale, default `0`). `tipo_reato` (str, opzionale, default `"delitto"`) — `"delitto"` (minimo 6 anni) o `"contravvenzione"` (minimo 4 anni).

**Quando usare**: per verificare se un reato è già prescritto o per stimare quando maturerà la prescrizione durante il dibattimento.

**Esempio**: `prescrizione_reato(pena_massima_anni=4, data_commissione="2018-05-10", tipo_reato="delitto")` → termine 6 anni, data prescrizione 10/05/2024, già prescritto.

---

### `pena_concordata`
_Simula la pena patteggiata (art. 444 c.p.p.) applicando -1/3 per attenuanti generiche e -1/3 per la diminuente di rito, con verifica del limite di 5 anni per l'ammissibilità._

**Parametri**: `pena_base_mesi` (float, obbligatorio). `attenuanti_generiche` (bool, opzionale, default `True`) — applica -1/3 ex art. 62-bis c.p. `diminuente_rito` (bool, opzionale, default `True`) — applica -1/3 ex art. 444 c.p.p.

**Quando usare**: per valutare la convenienza del patteggiamento e verificare se la pena finale è entro i limiti di ammissibilità e sospensione condizionale.

**Esempio**: `pena_concordata(pena_base_mesi=36)` → pena finale 16 mesi, patteggiamento ammissibile, sospendibile condizionalmente.

---

## 9. Proprietà e Successioni
_Strumenti per gestire le operazioni patrimoniali più frequenti: calcolo delle quote ereditarie, imposte di successione e donazione, IMU, imposte sulla compravendita immobiliare, usufrutto, cedolare secca, imposta di registro sui contratti di locazione, spese condominiali, valore catastale e superficie commerciale._

### `calcolo_eredita`
_Calcola le quote di legittima spettanti a ciascun erede e la quota disponibile testamentariamente, in base alla composizione del nucleo familiare._

**Parametri**: `massa_ereditaria` (float, obbligatorio) — valore totale in €. `eredi` (dict, obbligatorio) — `{"coniuge": bool, "figli": int, "ascendenti": bool, "fratelli": int}`.

**Quando usare**: per verificare se un testamento viola le quote di legittima o per pianificare la distribuzione del patrimonio di famiglia.

**Esempio**: `calcolo_eredita(massa_ereditaria=500000, eredi={"coniuge": True, "figli": 2})` → coniuge €125k (1/4), figlio1 €125k, figlio2 €125k, disponibile €125k.

---

### `imposte_successione`
_Calcola imposta di successione con franchigie e aliquote per grado di parentela, aggiungendo imposte ipotecaria e catastale se sono presenti immobili._

**Parametri**: `valore_beni` (float, obbligatorio) — valore ereditato in €. `parentela` (str, obbligatorio) — `coniuge_linea_retta`, `fratelli_sorelle`, `parenti_fino_4_grado_affini_fino_3`, `altri`. `immobili` (bool, opzionale, default `False`). `prima_casa` (bool, opzionale, default `False`).

**Quando usare**: per stimare il carico fiscale di un'eredità prima della dichiarazione di successione o per pianificazione successoria.

**Esempio**: `imposte_successione(valore_beni=1500000, parentela="coniuge_linea_retta", immobili=True)` → franchigia €1M, imposta 4% su €500k = €20.000 + imposte ipocatastali.

---

### `calcolo_usufrutto`
_Calcola il valore dell'usufrutto e della nuda proprietà in base all'età dell'usufruttuario, usando i coefficienti ufficiali Agenzia delle Entrate._

**Parametri**: `valore_piena_proprieta` (float, obbligatorio) — valore dell'immobile in €. `eta_usufruttuario` (int, obbligatorio) — età in anni compiuti (0-120).

**Quando usare**: per donazioni con riserva di usufrutto, successioni con usufrutto legale del coniuge, o per calcolare l'imposta sulla nuda proprietà.

**Esempio**: `calcolo_usufrutto(valore_piena_proprieta=400000, eta_usufruttuario=70)` → usufrutto €80.000 (20%), nuda proprietà €320.000 (80%).

---

### `calcolo_imu`
_Calcola l'IMU annua e semestrale per un immobile, applicando rivalutazione 5%, moltiplicatore catastale e aliquota comunale. L'abitazione principale è esente salvo A/1, A/8, A/9._

**Parametri**: `rendita_catastale` (float, obbligatorio) — rendita non rivalutata in €. `categoria` (str, obbligatorio) — categoria catastale (es. `"A/2"`, `"C/1"`, `"D/8"`). `aliquota_comunale` (float, opzionale, default `0.86`) — aliquota ‰ espressa in % (es. `0.86` = 8,6‰). `prima_casa` (bool, opzionale, default `False`).

**Quando usare**: per calcolare l'IMU da versare entro le scadenze di giugno e dicembre, o per confrontare il carico fiscale tra immobili.

**Esempio**: `calcolo_imu(rendita_catastale=800, categoria="A/3", aliquota_comunale=0.86)` → IMU annua e semestrale con base imponibile dettagliata.

---

### `imposte_compravendita`
_Calcola tutte le imposte per l'acquisto di un immobile (registro, ipotecaria, catastale o IVA se da costruttore), con supporto al regime prezzo-valore._

**Parametri**: `prezzo` (float, obbligatorio) — prezzo in €. `tipo_immobile` (str, opzionale, default `"abitazione"`) — `"abitazione"`, `"lusso"`, `"terreno_agricolo"`, `"commerciale"`. `prima_casa` (bool, opzionale, default `False`). `da_costruttore` (bool, opzionale, default `False`). `rendita_catastale` (float, opzionale) — abilita il calcolo prezzo-valore.

**Quando usare**: per preventivare il costo complessivo di un acquisto immobiliare prima del rogito.

**Esempio**: `imposte_compravendita(prezzo=250000, tipo_immobile="abitazione", prima_casa=True, rendita_catastale=600)` → registro 2% su base prezzo-valore, imposte fisse ipocatastali.

---

### `pensione_reversibilita`
_Calcola la pensione di reversibilità INPS con le quote per tipologia di beneficiari e la riduzione per cumulo con altri redditi._

**Parametri**: `pensione_de_cuius` (float, obbligatorio) — pensione annua lorda del defunto in €. `beneficiari` (dict, obbligatorio) — `{"coniuge": bool, "figli": int, "figli_minori": int, "genitori": int}`. `reddito_beneficiario` (float, opzionale, default `0`) — per calcolare l'eventuale riduzione.

**Quando usare**: per stimare la pensione di reversibilità spettante al coniuge superstite o ai figli, anche verificando se scatta la riduzione per reddito.

**Esempio**: `pensione_reversibilita(pensione_de_cuius=18000, beneficiari={"coniuge": True, "figli": 1}, reddito_beneficiario=25000)` → quota 80%, riduzione 25% per reddito >3x minimo.

---

### `grado_parentela`
_Calcola il grado di parentela tra due persone e ne indica la rilevanza successoria e fiscale (franchigie e aliquote imposta di successione)._

**Parametri**: `relazione` (str, obbligatorio) — nome della relazione (`"cugino"`, `"zio"`, `"fratello"`, ecc.) oppure catena di passi separati da virgola (`"genitore,figlio"` = fratello).

**Quando usare**: per verificare rapidamente il grado di parentela rilevante ai fini successori o per l'imposta sulle donazioni.

**Esempio**: `grado_parentela(relazione="cugino")` → grado 4, linea collaterale, aliquota 6% senza franchigia.

---

### `calcolo_valore_catastale`
_Calcola il valore catastale rivalutato dell'immobile per successione, compravendita o IMU, applicando la rivalutazione del 5% e il coefficiente corretto per categoria e finalità._

**Parametri**: `rendita_catastale` (float, obbligatorio) — rendita non rivalutata in €. `categoria` (str, obbligatorio) — categoria catastale (es. `"A/2"`, `"D/8"`). `tipo` (str, opzionale, default `"successione"`) — `"successione"`, `"compravendita"`, `"imu"`.

**Quando usare**: per compilare la dichiarazione di successione o verificare la base imponibile per l'imposta di registro usando il criterio catastale.

**Esempio**: `calcolo_valore_catastale(rendita_catastale=700, categoria="A/2", tipo="successione")` → rendita rivalutata €735, valore catastale €88.200 (coeff. 120).

---

### `calcolo_superficie_commerciale`
_Calcola la superficie commerciale dell'immobile applicando i coefficienti DPR 138/1998 (calpestabile 100%, balconi 33%, terrazzi 25%, giardino 10%, cantina 25%, garage 50%)._

**Parametri**: `superficie_calpestabile` (float, obbligatorio) — mq interni. `balconi` (float, opzionale, default `0`) — mq. `terrazzi` (float, opzionale, default `0`) — mq. `giardino` (float, opzionale, default `0`) — mq. `cantina` (float, opzionale, default `0`) — mq. `garage` (float, opzionale, default `0`) — mq.

**Quando usare**: per redigere o verificare un contratto di compravendita o locazione che indica la superficie commerciale come base del prezzo.

**Esempio**: `calcolo_superficie_commerciale(superficie_calpestabile=90, balconi=12, giardino=30)` → superficie commerciale 97,96 mq.

---

### `cedolare_secca`
_Confronta la convenienza tra cedolare secca e IRPEF ordinaria per redditi da locazione, calcolando il risparmio fiscale per ciascuna opzione._

**Parametri**: `canone_annuo` (float, obbligatorio) — canone annuo in €. `tipo_contratto` (str, opzionale, default `"libero"`) — `"libero"` (21%), `"concordato"` (10%), `"brevi"` (26%). `irpef_marginale` (float, opzionale, default `38`) — aliquota marginale IRPEF del locatore.

**Quando usare**: per decidere se optare per la cedolare secca al momento della registrazione del contratto di locazione.

**Esempio**: `cedolare_secca(canone_annuo=12000, tipo_contratto="libero", irpef_marginale=38)` → cedolare €2.520, IRPEF ordinaria €4.560, risparmio €2.040 con cedolare.

---

### `imposta_registro_locazioni`
_Calcola l'imposta di registro dovuta per un contratto di locazione abitativa per l'intera durata contrattuale, con aliquota 2% (libero) o 1% (concordato)._

**Parametri**: `canone_annuo` (float, obbligatorio). `durata_anni` (int, opzionale, default `4`). `tipo_contratto` (str, opzionale, default `"libero"`) — `"libero"` o `"concordato"`. `prima_registrazione` (bool, opzionale, default `True`) — applica il minimo di €67.

**Quando usare**: per calcolare quanto versare all'Agenzia delle Entrate al momento della registrazione di un contratto di affitto.

**Esempio**: `imposta_registro_locazioni(canone_annuo=9600, durata_anni=4, tipo_contratto="libero")` → imposta prima annualità €192, totale 4 anni €576.

---

### `spese_condominiali`
_Calcola la quota condominiale per millesimi e tipo di spesa, con ripartizione proprietario/inquilino se l'immobile è in locazione (L. 392/1978 art. 9)._

**Parametri**: `importo_totale` (float, obbligatorio) — spesa totale in €. `millesimi_proprietario` (float, obbligatorio) — millesimi dell'unità (es. 85,50 su 1000). `tipo_spesa` (str, opzionale, default `"ordinaria"`) — `"ordinaria"`, `"straordinaria"`, `"riscaldamento"`, `"ascensore"`. `piano` (int, opzionale, default `0`) — rilevante solo per ascensore. `immobile_locato` (bool, opzionale, default `False`).

**Quando usare**: per calcolare la quota di un singolo condomino su una spesa deliberata dall'assemblea, o per stabilire chi paga cosa tra locatore e conduttore.

**Esempio**: `spese_condominiali(importo_totale=5000, millesimi_proprietario=120, tipo_spesa="straordinaria", immobile_locato=True)` → quota unità €600, interamente a carico del proprietario.

---

## 10. Investimenti
_Strumenti per calcolare il rendimento netto (dopo imposte) di strumenti finanziari italiani: BOT, BTP, pronti contro termine, buoni fruttiferi postali. Include un comparatore multi-strumento con tassazione corretta (12,5% titoli di Stato, 26% altri strumenti)._

### `rendimento_bot`
_Calcola il rendimento netto annualizzato di un BOT (Buono Ordinario del Tesoro, zero-coupon), deducendo l'imposta sostitutiva 12,5% sulla plusvalenza e le commissioni bancarie._

**Parametri**: `valore_nominale` (float, obbligatorio) — importo rimborsato a scadenza in €. `prezzo_acquisto` (float, obbligatorio) — prezzo pagato in €. `giorni_scadenza` (int, obbligatorio) — giorni residui. `commissione_pct` (float, opzionale, default `0.0`) — commissione bancaria in % sul nominale.

**Quando usare**: per confrontare il rendimento netto effettivo di un BOT con altri strumenti prima dell'acquisto.

**Esempio**: `rendimento_bot(valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=180, commissione_pct=0.1)` → plusvalenza €200, imposta €25, rendimento netto annualizzato.

---

### `rendimento_btp`
_Calcola il rendimento netto di un BTP a cedola fissa, scorporando l'imposta 12,5% su cedole e capital gain, con il flusso cedolare dettagliato._

**Parametri**: `valore_nominale` (float, obbligatorio). `prezzo_acquisto` (float, obbligatorio). `cedola_annua_pct` (float, obbligatorio) — tasso cedolare lordo annuo in %. `anni_scadenza` (int, obbligatorio). `frequenza_cedola` (int, opzionale, default `2`) — cedole per anno (1=annuale, 2=semestrale).

**Quando usare**: per valutare la convenienza di un BTP quotato sotto o sopra la pari rispetto al rendimento netto atteso a scadenza.

**Esempio**: `rendimento_btp(valore_nominale=1000, prezzo_acquisto=950, cedola_annua_pct=3.5, anni_scadenza=5)` → cedole nette totali, plusvalenza netta e rendimento netto annuo.

---

### `pronti_termine`
_Calcola il rendimento netto di un pronti contro termine (PCT) con aliquota 12,5% se sottostante titoli di Stato, 26% per altri strumenti._

**Parametri**: `capitale` (float, obbligatorio) — importo investito in €. `tasso_lordo_pct` (float, obbligatorio) — tasso lordo annuo in %. `giorni` (int, obbligatorio) — durata in giorni. `tipo_sottostante` (str, opzionale, default `"titoli_stato"`) — `"titoli_stato"` (12,5%) o `"altro"` (26%).

**Quando usare**: per confrontare un PCT con altri strumenti a breve termine (BOT, conto deposito) o per verificare il guadagno netto di un'operazione bancaria.

**Esempio**: `pronti_termine(capitale=50000, tasso_lordo_pct=3.2, giorni=90, tipo_sottostante="titoli_stato")` → interessi lordi €394, imposta €49, netti €345.

---

### `rendimento_buoni_postali`
_Calcola il rendimento netto dei buoni fruttiferi postali con capitalizzazione composta a scaglioni d'anno e imposta sostitutiva 12,5%._

**Parametri**: `importo` (float, obbligatorio) — importo sottoscritto in €. `tipo` (str, opzionale, default `"ordinario"`) — `"ordinario"` (max 20 anni), `"3x4"` (max 12), `"4x4"` (max 16), `"dedicato_minori"` (max 18). `anni` (int, opzionale, default `10`) — durata desiderata in anni.

**Quando usare**: per confrontare i buoni postali con BOT/BTP a parità di orizzonte temporale, tenendo conto della capitalizzazione composta.

**Esempio**: `rendimento_buoni_postali(importo=20000, tipo="dedicato_minori", anni=18)` → montante lordo, imposta 12,5%, montante netto e rendimento netto annualizzato.

---

### `confronto_investimenti`
_Confronta il rendimento netto tra più strumenti finanziari applicando la tassazione corretta (12,5% o 26%) e restituisce una classifica dal più al meno conveniente._

**Parametri**: `importo` (float, obbligatorio) — capitale uguale per tutti gli strumenti in €. `investimenti` (list[dict], obbligatorio) — lista di `{"nome": str, "rendimento_lordo_pct": float, "tipo_tassazione": str, "durata_anni": int}`.

**Quando usare**: per prendere una decisione di investimento confrontando BOT, BTP, conto deposito e fondi con orizzonti temporali diversi su base netta omogenea.

**Esempio**: `confronto_investimenti(importo=10000, investimenti=[{"nome": "BTP 5y", "rendimento_lordo_pct": 3.5, "tipo_tassazione": "titoli_stato", "durata_anni": 5}, {"nome": "Fondo obbligazionario", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 5}])` → classifica con montanti netti: BTP €1.531 vs fondo €1.481.


---


## 11. Dichiarazione Redditi e Contributi
_Calcoli fiscali per la dichiarazione dei redditi: IRPEF, regime forfettario, TFR, acconto, ravvedimento e detrazioni. Usare per stimare l'imposta di un contribuente o per calcolare quanto dovuto in caso di ravvedimento operoso._

### `calcolo_irpef`
_Calcola IRPEF lorda/netta con scaglioni 2026, detrazioni da lavoro e addizionali regionali/comunali medie._

**Parametri**: `reddito_complessivo` (float, obbligatorio) — RAL annua in euro; `tipo_reddito` (str, opzionale, default `"dipendente"`) — `"dipendente"`, `"pensionato"` o `"autonomo"`; `deduzioni` (float, opzionale, default `0`) — oneri deducibili; `detrazioni_extra` (float, opzionale, default `0`) — detrazioni aggiuntive.

**Quando usare**: stimare l'imposta netta annua di un lavoratore dipendente, pensionato o autonomo.

**Esempio**: `calcolo_irpef(reddito_complessivo=35000, tipo_reddito="dipendente")` → imposta netta ~5.500€, aliquota effettiva ~15%

---

### `regime_forfettario`
_Simula l'imposta sostitutiva forfettaria e la confronta con l'IRPEF ordinaria (art. 1, commi 54-89, L. 190/2014)._

**Parametri**: `ricavi` (float, obbligatorio) — ricavi annui ≤85.000€; `coefficiente_redditivita` (float, opzionale, default `78`) — da Allegato L. 190/2014 per categoria ATECO; `anni_attivita` (int, opzionale, default `1`) — 1-5 = aliquota startup 5%, >5 = 15%; `contributi_inps` (float, opzionale, default `0`) — contributi INPS deducibili.

**Quando usare**: verificare la convenienza del forfettario rispetto all'IRPEF ordinaria per un professionista o piccolo commerciante.

**Esempio**: `regime_forfettario(ricavi=50000, coefficiente_redditivita=78, anni_attivita=3, contributi_inps=4000)` → imposta sostitutiva ~1.755€ (aliquota startup 5%)

---

### `calcolo_tfr`
_Calcola il TFR lordo e netto con tassazione separata ex artt. 17 e 19 TUIR._

**Parametri**: `retribuzione_annua_lorda` (float, obbligatorio) — RAL in euro; `anni_servizio` (int, obbligatorio) — anni interi positivi; `rivalutazione_media_pct` (float, opzionale, default `2.0`) — indice FOI medio per la rivalutazione.

**Quando usare**: stimare il TFR netto spettante al termine del rapporto di lavoro.

**Esempio**: `calcolo_tfr(retribuzione_annua_lorda=30000, anni_servizio=10)` → TFR lordo ~22.200€, netto ~17.000€

---

### `ravvedimento_operoso`
_Calcola sanzione ridotta e interessi legali per regolarizzare un omesso versamento o dichiarazione tardiva (art. 13 D.Lgs. 472/1997, mod. D.Lgs. 87/2024)._

**Parametri**: `imposta_dovuta` (float, obbligatorio) — importo originario non versato; `giorni_ritardo` (int, obbligatorio) — giorni dalla scadenza; `tipo` (str, opzionale, default `"omesso_versamento"`) — `"omesso_versamento"` (sanzione base 25%) o `"dichiarazione_tardiva"` (120%).

**Quando usare**: calcolare quanto versare per regolarizzare spontaneamente un pagamento omesso o tardivo prima di un accertamento.

**Esempio**: `ravvedimento_operoso(imposta_dovuta=1000, giorni_ritardo=20, tipo="omesso_versamento")` → tipo ravvedimento "breve", sanzione ~6,25€, totale ~1.009€

---

### `assegno_unico`
_Simula l'Assegno Unico Universale (D.Lgs. 230/2021) con maggiorazioni per neonati e nuclei monogenitoriali._

**Parametri**: `isee` (float, obbligatorio) — valore ISEE familiare (0 = massimo importo); `n_figli` (int, obbligatorio) — numero figli a carico; `eta_figli` (list[int], opzionale) — lista età in anni per calcolo maggiorazioni; `genitore_solo` (bool, opzionale, default `False`) — +30% per nucleo monogenitoriale.

**Quando usare**: stimare il sussidio mensile spettante a un nucleo familiare con figli under 21.

**Esempio**: `assegno_unico(isee=20000, n_figli=2, eta_figli=[0, 4])` → totale mensile ~395€ (inclusa maggiorazione neonato)

---

### `detrazione_figli`
_Calcola la detrazione IRPEF per figli a carico con età ≥21 anni (art. 12 TUIR)._

**Parametri**: `reddito_complessivo` (float, obbligatorio); `n_figli_over21` (int, obbligatorio); `n_figli_disabili` (int, opzionale, default `0`) — detrazione maggiorata a 1.350€.

**Quando usare**: determinare la detrazione IRPEF residua per figli maggiorenni non coperti dall'AUU.

**Esempio**: `detrazione_figli(reddito_complessivo=40000, n_figli_over21=1)` → detrazione ~547€

---

### `detrazione_coniuge`
_Calcola la detrazione IRPEF per coniuge a carico per fasce di reddito (art. 12, co. 1, lett. a) TUIR)._

**Parametri**: `reddito_complessivo` (float, obbligatorio) — reddito annuo del contribuente.

**Quando usare**: dichiarazione con coniuge a carico (reddito coniuge ≤2.840,51€).

**Esempio**: `detrazione_coniuge(reddito_complessivo=28000)` → detrazione 690€

---

### `detrazione_altri_familiari`
_Calcola la detrazione IRPEF per altri familiari a carico ex art. 433 c.c. (genitori, fratelli, nonni) — 750€ teorici proporzionati al reddito._

**Parametri**: `reddito_complessivo` (float, obbligatorio); `n_familiari` (int, obbligatorio).

**Quando usare**: dichiarazione con genitori o altri familiari conviventi a carico.

**Esempio**: `detrazione_altri_familiari(reddito_complessivo=30000, n_familiari=1)` → detrazione ~469€

---

### `detrazione_lavoro_dipendente`
_Calcola la detrazione art. 13 TUIR per redditi da lavoro dipendente, proporzionata ai giorni lavorati (scaglioni 2026 ex L. 199/2025)._

**Parametri**: `reddito_complessivo` (float, obbligatorio); `giorni_lavoro` (int, opzionale, default `365`).

**Quando usare**: calcolare la detrazione da lavoro spettante per un'assunzione a tempo parziale o part-year.

**Esempio**: `detrazione_lavoro_dipendente(reddito_complessivo=22000, giorni_lavoro=180)` → detrazione proporzionata ~925€

---

### `detrazione_pensione`
_Calcola la detrazione art. 13, co. 3, TUIR per redditi da pensione, proporzionata ai giorni._

**Parametri**: `reddito_complessivo` (float, obbligatorio); `giorni` (int, opzionale, default `365`).

**Quando usare**: calcolo IRPEF di un pensionato che ha percepito la pensione per una parte dell'anno.

**Esempio**: `detrazione_pensione(reddito_complessivo=15000)` → detrazione ~1.571€

---

### `detrazione_assegno_coniuge`
_Calcola la detrazione IRPEF per assegno periodico percepito dall'ex coniuge (art. 13, co. 5-bis, TUIR); spiega anche la deducibilità per chi lo versa._

**Parametri**: `reddito_complessivo` (float, obbligatorio) — reddito del percipiente.

**Quando usare**: dichiarazione del coniuge separato/divorziato che riceve l'assegno periodico.

**Esempio**: `detrazione_assegno_coniuge(reddito_complessivo=18000)` → detrazione ~807€

---

### `detrazione_canone_locazione`
_Calcola la detrazione IRPEF per inquilino con abitazione principale (art. 16 TUIR): contratto libero, concordato o agevolato giovani under 31._

**Parametri**: `reddito_complessivo` (float, obbligatorio); `tipo_contratto` (str, opzionale, default `"libero"`) — `"libero"`, `"concordato"` o `"giovani_under31"`.

**Quando usare**: dichiarazione di un lavoratore che affitta l'abitazione principale.

**Esempio**: `detrazione_canone_locazione(reddito_complessivo=20000, tipo_contratto="concordato")` → detrazione 495,80€

---

### `acconto_irpef`
_Calcola primo acconto (40%, giugno) e secondo acconto (60%, novembre) IRPEF con soglia di esenzione (art. 17 D.P.R. 435/2001)._

**Parametri**: `imposta_anno_precedente` (float, obbligatorio) — IRPEF netta dal modello Redditi PF (rigo RN34); `metodo` (str, opzionale, default `"storico"`) — `"storico"` o `"previsionale"`.

**Quando usare**: pianificare i versamenti F24 di giugno e novembre.

**Esempio**: `acconto_irpef(imposta_anno_precedente=3000)` → primo acconto 1.200€ (30/06), secondo acconto 1.800€ (30/11)

---

### `acconto_cedolare_secca`
_Calcola gli acconti della cedolare secca con stesse regole e scadenze dell'IRPEF (art. 3, co. 4, D.Lgs. 23/2011)._

**Parametri**: `imposta_anno_precedente` (float, obbligatorio) — cedolare secca dell'anno precedente.

**Quando usare**: proprietario di immobile a uso abitativo in regime di cedolare secca che deve pianificare gli acconti.

**Esempio**: `acconto_cedolare_secca(imposta_anno_precedente=2400)` → primo acconto 960€, secondo acconto 1.440€

---

### `rateizzazione_imposte`
_Calcola il piano di rateizzazione delle imposte IRPEF da dichiarazione (2-7 rate mensili) con interessi pro rata (art. 20 D.Lgs. 241/1997)._

**Parametri**: `importo_totale` (float, obbligatorio); `n_rate` (int, obbligatorio, 2-7); `data_prima_rata` (str, obbligatorio, YYYY-MM-DD) — di norma `"2025-06-30"`; `tasso_interesse_annuo` (float, opzionale, default `2.0`).

**Quando usare**: mostrare al contribuente il dettaglio delle rate mensili con importo capitale e interessi.

**Esempio**: `rateizzazione_imposte(importo_totale=6000, n_rate=6, data_prima_rata="2025-06-30")` → 6 rate da ~1.003€ cadauna con interessi scalari

---

## 12. Strumenti Vari
_Utilità generali per la pratica legale quotidiana: codice fiscale, IBAN, P.IVA, calcoli temporali, prescrizione, IVA, patente e ATECO. Nessun accesso a banche dati esterne — tutto calcolato localmente._

### `codice_fiscale`
_Genera il codice fiscale a 16 caratteri con algoritmo ufficiale (DM 12/03/1974), incluso il carattere di controllo._

**Parametri**: `cognome` (str, obbligatorio); `nome` (str, obbligatorio); `data_nascita` (str, obbligatorio, YYYY-MM-DD); `sesso` (str, obbligatorio, `"M"` o `"F"`); `comune_nascita` (str, obbligatorio) — comune italiano o stato estero (es. `"GERMANIA"`).

**Quando usare**: generare il CF per un contratto, atto notarile o registrazione anagrafica.

**Esempio**: `codice_fiscale(cognome="Rossi", nome="Mario", data_nascita="1985-03-15", sesso="M", comune_nascita="MILANO")` → `RSSMRA85C15F205Z`

---

### `decodifica_codice_fiscale`
_Decodifica un CF a 16 caratteri estraendo sesso, data di nascita stimata, comune catastale e verifica il carattere di controllo._

**Parametri**: `codice_fiscale` (str, obbligatorio) — 16 caratteri.

**Quando usare**: verificare la validità formale di un CF o estrarre i dati anagrafici.

**Esempio**: `decodifica_codice_fiscale(codice_fiscale="RSSMRA85C15F205Z")` → sesso M, nato il 1985-03-15, Milano

---

### `verifica_iban`
_Valida un IBAN italiano (27 caratteri) con algoritmo ISO 7064 mod 97 ed estrae ABI, CAB e numero conto._

**Parametri**: `iban` (str, obbligatorio) — spazi e trattini ignorati.

**Quando usare**: verificare formalmente un IBAN prima di un bonifico o in una perizia bancaria.

**Esempio**: `verifica_iban(iban="IT60 X054 2811 1010 0000 0123 456")` → valido/non valido + componenti ABI/CAB

---

### `verifica_partita_iva`
_Valida formalmente una P.IVA italiana (11 cifre) con algoritmo di controllo (DPR 633/1972)._

**Parametri**: `partita_iva` (str, obbligatorio) — 11 cifre.

**Quando usare**: verificare la validità formale di una P.IVA in un contratto o atto societario.

**Esempio**: `verifica_partita_iva(partita_iva="12345678903")` → valido/non valido + cifra di controllo attesa

---

### `conta_giorni`
_Conta i giorni tra due date: tutti (calendario), lavorativi (esclusi weekend e festivi italiani) o solo festivi._

**Parametri**: `data_inizio` (str, obbligatorio, YYYY-MM-DD); `data_fine` (str, obbligatorio, YYYY-MM-DD); `tipo` (str, opzionale, default `"calendario"`) — `"calendario"`, `"lavorativi"` o `"festivi"`.

**Quando usare**: calcolare termini processuali, scadenze contrattuali o preavvisi in giorni lavorativi.

**Esempio**: `conta_giorni(data_inizio="2025-12-20", data_fine="2026-01-10", tipo="lavorativi")` → 13 giorni lavorativi (esclude Natale, Capodanno, Epifania)

---

### `calcolo_tempo_trascorso`
_Calcola il tempo esatto tra due date in anni, mesi e giorni (o dalla data evento a oggi)._

**Parametri**: `data_inizio` (str, obbligatorio, YYYY-MM-DD); `data_fine` (str, opzionale) — default: oggi.

**Quando usare**: calcolare anzianità lavorativa, durata di un contratto o età al momento del fatto.

**Esempio**: `calcolo_tempo_trascorso(data_inizio="2018-04-01")` → 6 anni, 10 mesi, 21 giorni (al 22/02/2026)

---

### `calcolo_eta_anagrafica`
_Calcola l'età anagrafica esatta con data del prossimo compleanno._

**Parametri**: `data_nascita` (str, obbligatorio, YYYY-MM-DD); `data_riferimento` (str, opzionale) — default: oggi.

**Quando usare**: verificare maggiore età, accesso a prestazioni per fascia d'età, capacità d'agire al momento di un atto.

**Esempio**: `calcolo_eta_anagrafica(data_nascita="2008-06-15")` → 17 anni, 8 mesi, 7 giorni — minorenne

---

### `scorporo_iva`
_Scorporo dell'IVA da un importo ivato, restituendo imponibile e IVA separati._

**Parametri**: `importo_ivato` (float, obbligatorio); `aliquota` (float, opzionale, default `22`) — 4, 5, 10 o 22.

**Quando usare**: calcolare l'imponibile da indicare in una fattura o in un atto di acquisto.

**Esempio**: `scorporo_iva(importo_ivato=12200, aliquota=22)` → imponibile 10.000€, IVA 2.200€

---

### `decurtazione_punti_patente`
_Restituisce punti decurtati, sanzione pecuniaria e sospensione patente per una violazione del Codice della Strada (D.Lgs. 285/1992, agg. D.Lgs. 36/2023)._

**Parametri**: `violazione` (str, obbligatorio) — parola chiave (es. `"cellulare"`, `"eccesso_velocita_10"`, `"guida_ebbra"`).

**Quando usare**: rispondere a domande su punti e sanzioni per violazioni stradali specifiche.

**Esempio**: `decurtazione_punti_patente(violazione="cellulare")` → 5 punti decurtati, ammenda 165-660€

---

### `tasso_alcolemico`
_Calcola il tasso alcolemico teorico con formula di Widmark e indica la fascia sanzionatoria art. 186 CdS._

**Parametri**: `sesso` (str, obbligatorio, `"M"` o `"F"`); `peso_kg` (float, obbligatorio); `unita_alcoliche` (float, obbligatorio) — 1 UA = 12g alcol = 1 birra 33cl; `ore_trascorse` (float, obbligatorio); `stomaco_pieno` (bool, opzionale, default `False`).

**Quando usare**: pareri su guida in stato di ebbrezza o perizie per procedimenti penali ex art. 186 CdS. **Risultato sempre indicativo** — il tasso reale misurato può differire.

**Esempio**: `tasso_alcolemico(sesso="M", peso_kg=75, unita_alcoliche=3, ore_trascorse=1)` → tasso ~0,64 g/l → fascia lett. a) (500-2.000€, sospensione 3-6 mesi)

---

### `prescrizione_diritti`
_Calcola la data di prescrizione di un diritto civile e verifica se è già prescritto._

**Parametri**: `tipo_diritto` (str, obbligatorio) — `"ordinaria"` (10a), `"risarcimento_danni"` (5a), `"risarcimento_rca"` (2a), `"diritti_lavoro"` (5a), `"crediti_professionisti"` (3a), `"canoni_locazione"` (5a), `"contributi_previdenziali"` (5a), `"vizi_vendita"` (1a), `"garanzia_appalto"` (2a); `data_evento` (str, obbligatorio, YYYY-MM-DD).

**Quando usare**: verificare se un credito è prescritto prima di procedere con azioni legali o recupero crediti.

**Esempio**: `prescrizione_diritti(tipo_diritto="risarcimento_danni", data_evento="2019-05-10")` → prescrizione il 2024-05-10 → già prescritto

---

### `ricerca_codici_ateco`
_Ricerca codici ATECO per parola chiave, con coefficiente di redditività per il regime forfettario._

**Parametri**: `keyword` (str, obbligatorio) — parola chiave (es. `"avvocato"`, `"ristorante"`, `"informatica"`).

**Quando usare**: individuare il codice ATECO e il coefficiente di redditività per il calcolo del forfettario.

**Esempio**: `ricerca_codici_ateco(keyword="avvocato")` → codice 69.10.10, coefficiente 78%

---

## 13. Consultazione Normativa
_Recupero del testo ufficiale di leggi italiane e UE da Normattiva ed EUR-Lex, con annotazioni dottrinali e giurisprudenziali da Brocardi.it. Questi tool sostituiscono il web search per il TESTO delle norme: è sempre preferibile leggere la norma dalla fonte ufficiale prima di citarla. Il web search resta utile per trovare numero e anno di un atto sconosciuto (es. "qual è la legge che regola...") o per notizie di attualità normativa._

### `cite_law`
_Punto di ingresso principale: recupera il testo ufficiale di un articolo da Normattiva o EUR-Lex a partire da un riferimento in linguaggio naturale._

**Parametri**: `reference` (str, obbligatorio) — es. `"art. 13 GDPR"`, `"art. 2043 c.c."`, `"art. 6 D.Lgs. 231/2001"`; `include_annotations` (bool, opzionale, default `False`) — include anche le annotazioni Brocardi.

**Quando usare**: SEMPRE prima di citare una norma in un parere o documento legale. Alternativa accettabile al web search solo se il testo è già in context o si tratta di norme molto note.

**Esempio**: `cite_law(reference="art. 2087 c.c.", include_annotations=True)` → testo art. 2087 c.c. + ratio legis e massime Brocardi

---

### `fetch_law_article`
_Recupero a basso livello con parametri espliciti (tipo atto, anno, numero) — usare quando `cite_law` non risolve correttamente l'abbreviazione._

**Parametri**: `act_type` (str, obbligatorio) — es. `"decreto legislativo"`, `"codice civile"`, `"regolamento ue"`; `article` (str, obbligatorio) — es. `"13"`, `"2-bis"`; `date` (str, opzionale) — anno o data (es. `"2003"`); `act_number` (str, opzionale) — numero atto (es. `"196"`).

**Quando usare**: quando l'abbreviazione è ambigua o `cite_law` restituisce l'atto sbagliato.

**Esempio**: `fetch_law_article(act_type="decreto legislativo", article="13", date="2003", act_number="196")` → art. 13 D.Lgs. 196/2003 (Codice Privacy)

---

### `fetch_law_annotations`
_Recupera le annotazioni Brocardi per un articolo (ratio legis, spiegazione dottrinale, massime) con parametri espliciti._

**Parametri**: `act_type` (str, obbligatorio); `article` (str, obbligatorio); `date` (str, opzionale); `act_number` (str, opzionale).

**Quando usare**: approfondire la dottrina su un articolo già recuperato con `cite_law` o `fetch_law_article`.

**Esempio**: `fetch_law_annotations(act_type="codice civile", article="2043")` → ratio legis, spiegazione, massime giurisprudenziali art. 2043 c.c.

---

### `cerca_brocardi`
_Cerca annotazioni Brocardi da un riferimento in linguaggio naturale, restituendo anche i riferimenti strutturati alle sentenze della Cassazione utilizzabili con `leggi_sentenza`._

**Parametri**: `reference` (str, obbligatorio) — es. `"art. 2043 c.c."`, `"art. 575 c.p."`, `"art. 13 Costituzione"`.

**Quando usare**: preferire a `fetch_law_annotations` quando si vuole anche il collegamento diretto alle sentenze della Cassazione citate nelle massime (workflow Brocardi → Italgiure).

**Esempio**: `cerca_brocardi(reference="art. 2043 c.c.")` → annotazioni + lista sentenze Cass. con numero/anno per `leggi_sentenza`

---

### `download_law_pdf`
_Scarica il PDF ufficiale da EUR-Lex (normativa UE) o genera un PDF dal testo Normattiva (leggi italiane)._

**Parametri**: `reference` (str, obbligatorio) — nome atto o riferimento (es. `"GDPR"`, `"D.Lgs. 196/2003"`, `"codice civile"`).

**Quando usare**: quando serve il testo completo dell'atto in formato PDF (allegato a un parere, consultazione offline).

**Esempio**: `download_law_pdf(reference="GDPR")` → PDF EUR-Lex salvato in `/tmp/mcp-legal-it/GDPR.pdf`

---

## 14. Giurisprudenza Cassazione — Italgiure
_Accesso diretto all'archivio ufficiale delle decisioni della Corte di Cassazione tramite l'API Solr di italgiure.giustizia.it. Questi tool sostituiscono completamente il web search per le sentenze della Cassazione: se si conosce numero e anno, usare `leggi_sentenza` direttamente senza cercare altrove. Se non si conosce il numero, usare `cerca_giurisprudenza` o `giurisprudenza_su_norma`. Il web search è alternativa accettabile solo per sentenze di merito (Tribunali, Corti d'Appello) non presenti in Italgiure._

### `leggi_sentenza`
_Legge il testo completo di una specifica sentenza/ordinanza della Cassazione tramite numero e anno._

**Parametri**: `numero` (int, obbligatorio) — numero della decisione; `anno` (int, obbligatorio); `sezione` (str, opzionale) — `"1"`, `"2"`, ..., `"6"`, `"L"` (lavoro), `"T"` (tributaria), `"SU"` (sezioni unite); `archivio` (str, opzionale, default `"tutti"`) — `"civile"`, `"penale"` o `"tutti"`.

**Quando usare**: SEMPRE quando l'utente cita una sentenza con numero e anno noti (es. "Cass. n. 10787/2024"). Non usare web search per sentenze già identificate.

**Esempio**: `leggi_sentenza(numero=10787, anno=2024)` → testo completo Cass. n. 10787/2024

---

### `cerca_giurisprudenza`
_Ricerca full-text nelle decisioni della Cassazione per argomento, con filtri per archivio, materia, sezione e periodo._

**Parametri**: `query` (str, obbligatorio) — testo da cercare; `archivio` (str, opzionale, default `"tutti"`); `materia` (str, opzionale); `sezione` (str, opzionale); `anno_da` (int, opzionale, default `0`); `anno_a` (int, opzionale, default `0`); `max_risultati` (int, opzionale, default `10`, max `50`).

**Quando usare**: trovare sentenze rilevanti su un tema quando non si conosce il numero specifico. Poi usare `leggi_sentenza` per il testo completo.

**Esempio**: `cerca_giurisprudenza(query="responsabilità medica nesso causale", archivio="civile", anno_da=2020)` → lista sentenze con estratti

---

### `giurisprudenza_su_norma`
_Trova sentenze della Cassazione che citano uno specifico articolo di legge._

**Parametri**: `riferimento` (str, obbligatorio) — es. `"art. 2043 c.c."`, `"art. 13 GDPR"`, `"art. 416-bis c.p."`; `archivio` (str, opzionale, default `"tutti"`); `max_risultati` (int, opzionale, default `10`).

**Quando usare**: costruire un quadro giurisprudenziale su una norma (workflow Brocardi→Italgiure: `cerca_brocardi` poi `giurisprudenza_su_norma` per ampliare la ricerca).

**Esempio**: `giurisprudenza_su_norma(riferimento="art. 2051 c.c.", archivio="civile")` → sentenze su custodia e danno da cosa in custodia

---

### `ultime_pronunce`
_Ultime decisioni depositate dalla Cassazione, con filtri per materia, sezione, archivio e tipo provvedimento._

**Parametri**: `materia` (str, opzionale); `sezione` (str, opzionale); `archivio` (str, opzionale, default `"tutti"`); `tipo_provvedimento` (str, opzionale) — `"sentenza"`, `"ordinanza"` o `"decreto"`; `max_risultati` (int, opzionale, default `10`).

**Quando usare**: monitorare le ultime pronunce su una materia (es. aggiornamenti su lavoro, tributario, penale).

**Esempio**: `ultime_pronunce(sezione="T", tipo_provvedimento="sentenza", max_risultati=5)` → ultime 5 sentenze tributarie della Cassazione

---

## 15. Provvedimenti Garante Privacy — GPDP
_Accesso ai provvedimenti, linee guida, ordinanze e pareri del Garante per la Protezione dei Dati Personali (garanteprivacy.it) tramite scraping HTML della fonte ufficiale. Usare questi tool per qualsiasi quesito su GDPR applicato in Italia, sanzioni, cookie, data breach, AI e privacy. Il web search è alternativa accettabile solo per notizie di attualità molto recenti non ancora indicizzate dal Garante, o per provvedimenti di autorità privacy di altri Paesi UE._

### `cerca_provvedimenti_garante`
_Cerca per testo libero nell'archivio del Garante Privacy, con filtri per tipologia e periodo._

**Parametri**: `query` (str, obbligatorio) — es. `"data breach notifica"`, `"cookie consenso"`, `"profilazione"`; `tipologia` (str, opzionale) — `"provvedimento"`, `"ordinanza"`, `"parere"`, `"linee guida"`; `data_da` (str, opzionale, DD/MM/YYYY); `data_a` (str, opzionale, DD/MM/YYYY); `max_risultati` (int, opzionale, default `10`, max `50`).

**Quando usare**: trovare i provvedimenti GPDP su un tema prima di rispondere a domande su privacy e GDPR. Poi usare `leggi_provvedimento_garante` per il testo completo.

**Esempio**: `cerca_provvedimenti_garante(query="videosorveglianza luoghi lavoro", tipologia="provvedimento", data_da="01/01/2022")` → lista provvedimenti con DocWeb ID

---

### `leggi_provvedimento_garante`
_Legge il testo completo di un provvedimento del Garante tramite DocWeb ID._

**Parametri**: `docweb_id` (int, obbligatorio) — ID numerico del documento Garante (riportato nei risultati di `cerca_provvedimenti_garante`).

**Quando usare**: dopo aver trovato il DocWeb ID con la ricerca, per leggere il testo completo di un provvedimento.

**Esempio**: `leggi_provvedimento_garante(docweb_id=9677876)` → testo completo "Linee guida cookie e altri strumenti di tracciamento" (2021)

---

### `ultimi_provvedimenti_garante`
_Ultimi provvedimenti depositati dal Garante Privacy, con filtro opzionale per tipologia._

**Parametri**: `tipologia` (str, opzionale) — `"provvedimento"`, `"ordinanza"`, `"parere"`, `"linee guida"`; `max_risultati` (int, opzionale, default `10`, max `50`).

**Quando usare**: monitorare le ultime decisioni del Garante su temi privacy, o verificare se ci sono provvedimenti recenti su un'area specifica.

**Esempio**: `ultimi_provvedimenti_garante(tipologia="linee guida", max_risultati=5)` → ultime 5 linee guida pubblicate dal GPDP

