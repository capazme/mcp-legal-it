"""MCP Resources — 8 static legal reference documents."""

from src.server import mcp


@mcp.resource(
    "legal://riferimenti/procedura-civile",
    name="Procedura Civile Ordinaria",
    description="Schema fasi e termini della procedura civile post-Cartabia (D.Lgs. 149/2022)",
)
def procedura_civile() -> str:
    return """PROCEDURA CIVILE ORDINARIA (post Riforma Cartabia, D.Lgs. 149/2022)
Entrata in vigore: 28 febbraio 2023 (per procedimenti instaurati dal 1° marzo 2023)

═══════════════════════════════════════════════════════════
PRIMO GRADO — Tribunale (artt. 163 ss. c.p.c.)
═══════════════════════════════════════════════════════════

1. FASE INTRODUTTIVA
   - Atto di citazione (art. 163 c.p.c.)
     • Contenuto: vocatio in ius + editio actionis
     • Termine a comparire: minimo 120 giorni (Italia) / 150 giorni (estero)
   - Notifica e iscrizione a ruolo (entro 10 giorni dalla notifica)
   - Comparsa di risposta (art. 167 c.p.c.)
     • Termine: 70 giorni prima dell'udienza
     • Domande riconvenzionali, eccezioni di rito e di merito, chiamata di terzo

2. FASE DI TRATTAZIONE (art. 171-bis / 171-ter c.p.c.)
   - Verifiche preliminari del giudice (art. 171-bis)
     • Entro 15 giorni dalla scadenza per la costituzione del convenuto
     • Provvedimenti su questioni rilevabili d'ufficio
   - Memorie integrative (art. 171-ter):
     • Prima memoria: 40 giorni prima dell'udienza — nuove domande, eccezioni, prove
     • Seconda memoria: 20 giorni prima — repliche, prove contrarie
     • Terza memoria: 10 giorni prima — sole indicazioni di prova contraria
   - Prima udienza di comparizione e trattazione
     • Verifica della regolarità del contraddittorio
     • Decisione sulle istanze istruttorie
     • Tentativo di conciliazione

3. FASE ISTRUTTORIA
   - Assunzione prove (testimoni, CTU, esibizione documenti)
   - Eventuale ordinanza ex art. 183-ter (accoglimento/rigetto parziale)
   - Rimessione in decisione

4. FASE DECISORIA
   - Precisazione delle conclusioni
   - Scambio comparse conclusionali (60 giorni) e repliche (30 giorni)
   - Sentenza: deposito in cancelleria

═══════════════════════════════════════════════════════════
SECONDO GRADO — Corte d'Appello (artt. 339 ss. c.p.c.)
═══════════════════════════════════════════════════════════

- Atto d'appello (citazione)
- Termini: 30 giorni (breve, dalla notifica sentenza) / 6 mesi (lungo, dal deposito)
- Costituzione appellante e appellato
- Filtro di inammissibilità (art. 348-bis): ragionevole probabilità di accoglimento
- Istruttoria: limitata a prove indispensabili (art. 345 c.p.c.)
- Decisione: sentenza

═══════════════════════════════════════════════════════════
CASSAZIONE — Corte Suprema (artt. 360 ss. c.p.c.)
═══════════════════════════════════════════════════════════

- Ricorso per cassazione: 60 giorni (breve) / 6 mesi (lungo)
- Motivi tassativi (art. 360 c.p.c.): 5 motivi di legittimità
- Controricorso: 40 giorni dalla notifica del ricorso
- Udienza pubblica o camera di consiglio (art. 380-bis)
- Decisione: accoglimento (rinvio o decisione nel merito) / rigetto / inammissibilità

═══════════════════════════════════════════════════════════
SOSPENSIONE FERIALE
═══════════════════════════════════════════════════════════
- Periodo: 1 agosto — 31 agosto (L. 742/1969 mod. D.L. 132/2014)
- I termini processuali sono sospesi (non decorrono)
- Eccezioni: procedimenti cautelari, alimenti, sfratti, procedimenti penali con detenuti
"""


@mcp.resource(
    "legal://riferimenti/termini-processuali",
    name="Termini Processuali Chiave",
    description="Tabella dei principali termini processuali civili post-Cartabia",
)
def termini_processuali() -> str:
    return """TERMINI PROCESSUALI CIVILI — QUADRO SINOTTICO
(Riforma Cartabia, D.Lgs. 149/2022 — procedimenti dal 1° marzo 2023)

═══════════════════════════════════════════════════════════
PRIMO GRADO
═══════════════════════════════════════════════════════════

| Adempimento | Termine | Norma |
|-------------|---------|-------|
| Termine a comparire (citazione) | 120 gg (Italia) / 150 gg (estero) | art. 163-bis |
| Iscrizione a ruolo | 10 gg dalla notifica | art. 165 |
| Comparsa di risposta | 70 gg prima dell'udienza | art. 166 |
| Verifiche preliminari giudice | 15 gg da scadenza cost. convenuto | art. 171-bis |
| Prima memoria integrativa | 40 gg prima dell'udienza | art. 171-ter, co. 1 |
| Seconda memoria (repliche) | 20 gg prima dell'udienza | art. 171-ter, co. 2 |
| Terza memoria (prove contrarie) | 10 gg prima dell'udienza | art. 171-ter, co. 3 |
| Deposito CTU | termine fissato dal giudice | art. 195 |
| Osservazioni alla CTU | 30 gg dal deposito CTU (salvo diverso) | art. 195, co. 3 |
| Comparse conclusionali | 60 gg da rimessione | art. 190 |
| Memorie di replica | 30 gg successivi | art. 190 |
| Deposito sentenza | 30 gg (rito semplificato) / 60 gg (ordinario) | art. 275 |

═══════════════════════════════════════════════════════════
IMPUGNAZIONI
═══════════════════════════════════════════════════════════

| Impugnazione | Termine breve | Termine lungo | Norma |
|--------------|---------------|---------------|-------|
| Appello | 30 gg da notifica sent. | 6 mesi da deposito | art. 325-327 |
| Cassazione | 60 gg da notifica sent. | 6 mesi da deposito | art. 325-327 |
| Revocazione (straord.) | 30 gg da scoperta | — | art. 326-327 |
| Opposizione di terzo | non soggetta a termine | — | art. 404 |
| Regolamento di competenza | 30 gg da notifica/comunic. | — | art. 47 |

═══════════════════════════════════════════════════════════
PROCEDIMENTI SPECIALI
═══════════════════════════════════════════════════════════

| Procedimento | Termine | Norma |
|--------------|---------|-------|
| Opposizione a decreto ingiuntivo | 40 gg dalla notifica | art. 641 |
| Reclamo cautelare | 15 gg dalla pronuncia/comunic. | art. 669-terdecies |
| Opposizione all'esecuzione | prima del compimento | art. 615 |
| Opposizione agli atti esecutivi | 20 gg dal compimento | art. 617 |
| Ricorso per sfratto (convalida) | udienza non prima di 20 gg | art. 660 |

═══════════════════════════════════════════════════════════
MEDIAZIONE E NEGOZIAZIONE ASSISTITA
═══════════════════════════════════════════════════════════

| Adempimento | Termine | Norma |
|-------------|---------|-------|
| Primo incontro mediazione | 30 gg dalla domanda | D.Lgs. 28/2010, art. 8 |
| Durata max mediazione | 3 mesi (prorogabili di 3) | D.Lgs. 28/2010, art. 6 |
| Invito negoziazione assistita | risposta entro 30 gg | D.L. 132/2014, art. 4 |
| Durata max negoziazione | da accordo (min. 1 mese, max 3 mesi) | D.L. 132/2014, art. 2 |
"""


@mcp.resource(
    "legal://riferimenti/contributo-unificato",
    name="Contributo Unificato — Tabella Scaglioni",
    description="Scaglioni del contributo unificato per valore causa e tipo procedimento (aggiornato 2025)",
)
def contributo_unificato() -> str:
    return """CONTRIBUTO UNIFICATO — TABELLA SCAGLIONI
(D.P.R. 115/2002 e successive modifiche — aggiornamento 2025)

═══════════════════════════════════════════════════════════
PROCESSI CIVILI ORDINARI (art. 13, co. 1)
═══════════════════════════════════════════════════════════

| Valore causa | CU |
|--------------|-----|
| Fino a € 1.100 | € 43,00 |
| Da € 1.100,01 a € 5.200 | € 98,00 |
| Da € 5.200,01 a € 26.000 | € 237,00 |
| Da € 26.000,01 a € 52.000 | € 518,00 |
| Da € 52.000,01 a € 260.000 | € 759,00 |
| Da € 260.000,01 a € 520.000 | € 1.214,00 |
| Oltre € 520.000 | € 1.686,00 |
| Valore indeterminabile (bassa complessità) | € 518,00 |
| Valore indeterminabile (alta complessità) | € 1.686,00 |

═══════════════════════════════════════════════════════════
IMPUGNAZIONI (art. 13, co. 1-bis)
═══════════════════════════════════════════════════════════

| Grado | Maggiorazione |
|-------|---------------|
| Appello | CU × 1,5 (50% in più) |
| Cassazione | CU × 2 (raddoppio) |
| Riassunzione dopo cassazione con rinvio | come primo grado |

═══════════════════════════════════════════════════════════
PROCEDIMENTI SPECIALI (art. 13, co. 1 e 3)
═══════════════════════════════════════════════════════════

| Procedimento | CU |
|--------------|-----|
| Decreto ingiuntivo | 50% del CU ordinario (dimezzato) |
| Opposizione a decreto ingiuntivo | CU pieno per valore |
| Procedimenti cautelari autonomi | € 98,00 |
| Volontaria giurisdizione | € 98,00 |
| Procedimenti di sfratto | € 98,00 |
| Procedimenti esecutivi immobiliari | € 278,00 |
| Procedimenti esecutivi mobiliari | CU per valore (min. € 43) |
| Separazione/divorzio consensuale | € 43,00 |
| Separazione/divorzio giudiziale | € 98,00 (se senza domande economiche) |

═══════════════════════════════════════════════════════════
ESENZIONI E RIDUZIONI
═══════════════════════════════════════════════════════════

| Fattispecie | Regime |
|-------------|--------|
| Cause di lavoro e previdenza (< € 2.500) | Esente |
| Cause di lavoro e previdenza (> € 2.500) | Esente (solo primo grado) |
| Procedimenti in materia tavolare | € 98,00 |
| Controversie ex art. 615 c.p.c. (opp. esecuzione) | CU per valore |
| Controversie previdenziali | Esente (salvo impugnazioni) |
| Separazione/divorzio negoziazione assistita | Esente |

═══════════════════════════════════════════════════════════
NOTE
═══════════════════════════════════════════════════════════
- Marca da bollo per iscrizione a ruolo: € 27,00 (sempre dovuta)
- Diritti di copia: variano per tipo e numero di pagine
- In caso di dichiarazione di valore mancante: CU come valore indeterminabile
- Sanzione per omesso/insufficiente pagamento: recupero con ingiunzione del funzionario
"""


@mcp.resource(
    "legal://riferimenti/irpef-detrazioni",
    name="IRPEF 2025-2026 — Scaglioni e Detrazioni",
    description="Schema IRPEF vigente: scaglioni, aliquote e principali detrazioni",
)
def irpef_detrazioni() -> str:
    return """IRPEF 2025-2026 — SCAGLIONI, ALIQUOTE E DETRAZIONI PRINCIPALI
(D.Lgs. 216/2023 — Riforma fiscale, confermato dalla Legge di Bilancio 2025)

═══════════════════════════════════════════════════════════
SCAGLIONI E ALIQUOTE (dal 2024)
═══════════════════════════════════════════════════════════

| Scaglione di reddito | Aliquota | Imposta su scaglione |
|----------------------|----------|---------------------|
| Fino a € 28.000 | 23% | max € 6.440 |
| Da € 28.001 a € 50.000 | 35% | max € 7.700 |
| Oltre € 50.000 | 43% | — |

Imposta lorda = 23% su primi € 28.000 + 35% su fascia € 28.001-50.000 + 43% sull'eccedente

Esempio: reddito € 60.000
→ € 6.440 + € 7.700 + 43% × € 10.000 = € 6.440 + € 7.700 + € 4.300 = € 18.440

═══════════════════════════════════════════════════════════
DETRAZIONI PER LAVORO DIPENDENTE (art. 13 TUIR)
═══════════════════════════════════════════════════════════

| Reddito complessivo | Detrazione |
|---------------------|-----------|
| Fino a € 15.000 | € 1.955 (min. € 690 / € 1.380 tempo det.) |
| Da € 15.001 a € 28.000 | € 1.910 + € 1.190 × (€ 28.000 - reddito) / € 13.000 |
| Da € 28.001 a € 50.000 | € 1.910 × (€ 50.000 - reddito) / € 22.000 |
| Oltre € 50.000 | Nessuna |

+ € 65 aggiuntivi se reddito tra € 25.001 e € 35.000

═══════════════════════════════════════════════════════════
DETRAZIONI PER PENSIONE (art. 13 TUIR)
═══════════════════════════════════════════════════════════

| Reddito complessivo | Detrazione |
|---------------------|-----------|
| Fino a € 8.500 | € 1.955 (min. € 713) |
| Da € 8.501 a € 28.000 | € 700 + € 1.255 × (€ 28.000 - reddito) / € 19.500 |
| Da € 28.001 a € 50.000 | € 700 × (€ 50.000 - reddito) / € 22.000 |
| Oltre € 50.000 | Nessuna |

═══════════════════════════════════════════════════════════
DETRAZIONI PER CARICHI DI FAMIGLIA (art. 12 TUIR)
═══════════════════════════════════════════════════════════

| Familiare | Detrazione | Note |
|-----------|-----------|------|
| Coniuge (no separato) | € 800 (variabile per reddito) | Decresce sopra € 15.000 |
| Figli < 21 anni | Assegno Unico (non più detrazione) | ISEE-based |
| Figli ≥ 21 anni a carico | € 950 × (€ 95.000 - reddito) / € 95.000 | Reddito figlio < € 2.840,51 |
| Figli disabili ≥ 21 | € 1.350 × formula | Idem |
| Altri familiari a carico | € 750 × (€ 80.000 - reddito) / € 80.000 | Reddito < € 2.840,51 |

Limite reddito "a carico": € 2.840,51 (€ 4.000 per figli fino a 24 anni)

═══════════════════════════════════════════════════════════
NO TAX AREA
═══════════════════════════════════════════════════════════

| Categoria | Soglia esenzione |
|-----------|-----------------|
| Lavoro dipendente | € 8.500 |
| Pensione | € 8.500 |
| Lavoro autonomo | € 5.500 (circa) |

═══════════════════════════════════════════════════════════
ADDIZIONALI
═══════════════════════════════════════════════════════════

| Tipo | Aliquota |
|------|----------|
| Addizionale regionale | 1,23% — 3,33% (variabile per regione) |
| Addizionale comunale | 0% — 0,8% (delibera comunale) |
"""


@mcp.resource(
    "legal://riferimenti/interessi-legali",
    name="Storico Tassi Interessi Legali",
    description="Tassi di interesse legale dal 2000 al 2026 (art. 1284 c.c.)",
)
def interessi_legali() -> str:
    return """INTERESSI LEGALI — STORICO TASSI (art. 1284 c.c.)
Decreto ministeriale annuale del Ministero dell'Economia e delle Finanze

═══════════════════════════════════════════════════════════
TASSI ANNUALI
═══════════════════════════════════════════════════════════

| Anno | Tasso | Decreto |
|------|-------|---------|
| 2000 | 2,50% | D.M. 10/12/1999 |
| 2001 | 3,50% | D.M. 11/12/2000 |
| 2002 | 3,00% | D.M. 11/12/2001 |
| 2003 | 3,00% | — (invariato) |
| 2004 | 2,50% | D.M. 01/12/2003 |
| 2005 | 2,50% | — (invariato) |
| 2006 | 2,50% | — (invariato) |
| 2007 | 2,50% | — (invariato) |
| 2008 | 3,00% | D.M. 12/12/2007 |
| 2009 | 3,00% | — (invariato) |
| 2010 | 1,00% | D.M. 04/12/2009 |
| 2011 | 1,50% | D.M. 07/12/2010 |
| 2012 | 2,50% | D.M. 12/12/2011 |
| 2013 | 2,50% | — (invariato) |
| 2014 | 1,00% | D.M. 12/12/2013 |
| 2015 | 0,50% | D.M. 11/12/2014 |
| 2016 | 0,20% | D.M. 11/12/2015 |
| 2017 | 0,10% | D.M. 07/12/2016 |
| 2018 | 0,30% | D.M. 13/12/2017 |
| 2019 | 0,80% | D.M. 12/12/2018 |
| 2020 | 0,05% | D.M. 12/12/2019 |
| 2021 | 0,01% | D.M. 11/12/2020 |
| 2022 | 1,25% | D.M. 13/12/2021 |
| 2023 | 5,00% | D.M. 13/12/2022 |
| 2024 | 2,50% | D.M. 11/12/2023 |
| 2025 | 2,00% | D.M. 10/12/2024 |
| 2026 | 1,60% | D.M. 10/12/2025 |

═══════════════════════════════════════════════════════════
INTERESSI DI MORA (D.Lgs. 231/2002 — transazioni commerciali)
═══════════════════════════════════════════════════════════

Tasso = tasso BCE + 8 punti percentuali (art. 5, D.Lgs. 231/2002)

| Semestre | Tasso BCE | Tasso mora |
|----------|-----------|------------|
| II sem. 2024 | 4,50% | 12,50% |
| I sem. 2025 | 3,40% | 11,40% |
| II sem. 2025 | 2,65% | 10,65% |
| I sem. 2026 | da definire | da definire |

═══════════════════════════════════════════════════════════
NOTE APPLICATIVE
═══════════════════════════════════════════════════════════

- Art. 1284, co. 1 c.c.: tasso legale per obbligazioni pecuniarie
- Art. 1284, co. 4 c.c.: dal 2014, se il debitore è inadempiente il tasso
  per le transazioni commerciali si applica anche ai crediti giudiziari
  (salvo diversa pattuizione)
- Interessi composti: vietato l'anatocismo (art. 1283 c.c.)
  salvo usi normativi e domanda giudiziale
- Rivalutazione vs. interessi: non cumulabili sullo stesso importo
  (Cass. SS.UU. 16601/2017) — il creditore sceglie la via più favorevole
"""


@mcp.resource(
    "legal://riferimenti/checklist-decreto-ingiuntivo",
    name="Checklist Decreto Ingiuntivo",
    description="Checklist operativa per il ricorso per decreto ingiuntivo (artt. 633 ss. c.p.c.)",
)
def checklist_decreto_ingiuntivo() -> str:
    return """CHECKLIST — RICORSO PER DECRETO INGIUNTIVO (artt. 633 ss. c.p.c.)

═══════════════════════════════════════════════════════════
PRESUPPOSTI (art. 633 c.p.c.)
═══════════════════════════════════════════════════════════

☐ Il credito è:
  ☐ una somma liquida di denaro, OPPURE
  ☐ una determinata quantità di cose fungibili, OPPURE
  ☐ la consegna di una cosa mobile determinata

☐ Prova scritta del credito (art. 634-635 c.p.c.):
  ☐ Contratto / scrittura privata
  ☐ Fatture (per crediti commerciali, sufficienti ex art. 634, co. 2)
  ☐ Estratto autentico delle scritture contabili (imprenditori)
  ☐ Parcella vistata dall'Ordine (per professionisti)
  ☐ Atto ricognitivo di debito
  ☐ Certificazione del credito PA

═══════════════════════════════════════════════════════════
COMPETENZA (artt. 637-638 c.p.c.)
═══════════════════════════════════════════════════════════

☐ Giudice di Pace: crediti fino a € 5.000 (beni mobili fino a € 20.000)
☐ Tribunale: crediti oltre € 5.000 o materie riservate
☐ Foro competente:
  ☐ Foro del debitore (residenza/domicilio) — regola generale
  ☐ Foro dell'obbligazione (luogo di adempimento) — alternativo
  ☐ Foro eletto contrattualmente

═══════════════════════════════════════════════════════════
RICORSO — CONTENUTO
═══════════════════════════════════════════════════════════

☐ Indicazione delle parti (ricorrente e intimato)
☐ Codice fiscale e PEC delle parti (obbligatori)
☐ Oggetto della domanda (somma precisa con calcolo interessi)
☐ Causa petendi (titolo del credito)
☐ Prova scritta allegata
☐ Indicazione del valore della causa
☐ Procura alle liti (se avvocato)
☐ Eventuale richiesta di provvisoria esecutività (art. 642 c.p.c.)

═══════════════════════════════════════════════════════════
PROVVISORIA ESECUTIVITÀ (art. 642 c.p.c.)
═══════════════════════════════════════════════════════════

☐ Richiedere se il credito è fondato su:
  ☐ Cambiale, assegno, certificato di liquidazione camerale
  ☐ Atto ricevuto da notaio
  ☐ Scrittura privata autenticata
  ☐ Pericolo di grave pregiudizio nel ritardo (motivare)
  ☐ Documentazione sottoscritta dal debitore comprovante il diritto

═══════════════════════════════════════════════════════════
COSTI
═══════════════════════════════════════════════════════════

☐ Contributo unificato: 50% del CU ordinario per scaglione
  | Valore | CU (dimezzato) |
  |--------|---------------|
  | Fino a € 1.100 | € 21,50 |
  | € 1.100-5.200 | € 49,00 |
  | € 5.200-26.000 | € 118,50 |
  | € 26.000-52.000 | € 259,00 |
  | € 52.000-260.000 | € 379,50 |
  | € 260.000-520.000 | € 607,00 |
  | Oltre € 520.000 | € 843,00 |

☐ Marca da bollo: € 27,00
☐ Diritti di notifica (a carico dell'intimato se accolta)

═══════════════════════════════════════════════════════════
POST-EMISSIONE
═══════════════════════════════════════════════════════════

☐ Notifica del decreto all'intimato
☐ Termine per la notifica: 60 giorni dall'emissione (art. 644 c.p.c.)
  — decorso il termine il decreto perde efficacia
☐ Termine per opposizione: 40 giorni dalla notifica (art. 641 c.p.c.)

═══════════════════════════════════════════════════════════
FORMULA ESECUTIVA
═══════════════════════════════════════════════════════════

☐ Se non opposto: dichiarazione di esecutività (art. 647 c.p.c.)
  — Istanza alla cancelleria dopo i 40 giorni
☐ Se provvisoriamente esecutivo: procedere direttamente
☐ Apposizione formula esecutiva (art. 475 c.p.c.)
☐ Notifica titolo esecutivo + precetto (art. 479-480 c.p.c.)
  — Termine per adempiere: minimo 10 giorni dalla notifica del precetto

═══════════════════════════════════════════════════════════
OPPOSIZIONE (artt. 645-656 c.p.c.)
═══════════════════════════════════════════════════════════

☐ Se l'intimato fa opposizione:
  ☐ Si apre giudizio ordinario di cognizione
  ☐ L'opponente è attore in senso formale, convenuto in senso sostanziale
  ☐ Onere della prova resta sul creditore (intimante)
  ☐ Possibilità di chiedere la sospensione della provvisoria esecuzione (art. 649 c.p.c.)
  ☐ Se l'opposizione è rigettata: il decreto acquista efficacia di sentenza
"""


@mcp.resource(
    "legal://riferimenti/fonti-diritto-italiano",
    name="Gerarchia Fonti del Diritto Italiano",
    description="Sistema delle fonti, gerarchia normativa, criteri di risoluzione antinomie e formato citazione",
)
def fonti_diritto_italiano() -> str:
    return """FONTI DEL DIRITTO ITALIANO — GERARCHIA E FORMATO CITAZIONE

═══════════════════════════════════════════════════════════
GERARCHIA DELLE FONTI
═══════════════════════════════════════════════════════════

1. COSTITUZIONE E LEGGI COSTITUZIONALI
   - Costituzione della Repubblica Italiana (1° gennaio 1948)
   - Leggi di revisione costituzionale (art. 138 Cost.)
   - Leggi costituzionali
   → Citazione: "art. 3 Cost." / "art. 117, co. 2, lett. l) Cost."

2. FONTI EUROPEE (primato UE — Costa v. ENEL, 1964)
   - Trattati (TUE, TFUE, Carta dei Diritti Fondamentali)
   - Regolamenti UE: direttamente applicabili, prevalgono su legge nazionale
   - Direttive UE: vincolanti nel risultato, richiedono recepimento
   - Decisioni UE: vincolanti per i destinatari
   → Citazione Regolamento: "art. 6 Reg. UE 2016/679" o "art. 6 GDPR"
   → Citazione Direttiva: "art. 5 Dir. 2001/29/CE"

3. FONTI PRIMARIE STATALI
   - Leggi ordinarie (L.): approvate dal Parlamento
   - Decreti legislativi (D.Lgs.): delegati dal Parlamento al Governo (art. 76 Cost.)
   - Decreti legge (D.L.): urgenza, convertiti entro 60 giorni (art. 77 Cost.)
   → Citazione: "art. 5 L. 241/1990" / "art. 13 D.Lgs. 196/2003" / "art. 1 D.L. 18/2020"

4. FONTI SECONDARIE
   - Regolamenti governativi (D.P.R.)
   - Decreti ministeriali (D.M.)
   - Regolamenti autorità indipendenti (Garante, AGCM, Consob, IVASS)
   → Citazione: "art. 3 D.M. 55/2014" / "D.P.R. 115/2002"

5. CONSUETUDINI (usi normativi)
   - Solo se richiamate dalla legge (praeter legem)
   - Mai contro la legge (contra legem)

═══════════════════════════════════════════════════════════
CRITERI DI RISOLUZIONE DELLE ANTINOMIE
═══════════════════════════════════════════════════════════

| Criterio | Regola | Fondamento |
|----------|--------|------------|
| Gerarchia | Lex superior derogat inferiori | Fonte di grado superiore prevale |
| Cronologia | Lex posterior derogat priori | Norma successiva abroga la precedente |
| Specialità | Lex specialis derogat generali | Norma speciale prevale sulla generale |
| Competenza | Materia riservata | Riserve di legge, competenze regionali |

Ordine di applicazione: Gerarchia > Competenza > Specialità > Cronologia

═══════════════════════════════════════════════════════════
TIPI DI ABROGAZIONE (art. 15 disp. prel. c.c.)
═══════════════════════════════════════════════════════════

| Tipo | Meccanismo |
|------|-----------|
| Espressa | La nuova legge dichiara l'abrogazione |
| Tacita | Incompatibilità tra nuova e vecchia norma |
| Per nuova disciplina | La nuova legge regola l'intera materia |
| Referendum | Abrogazione popolare (art. 75 Cost.) |

═══════════════════════════════════════════════════════════
FORMATO CITAZIONE — GUIDA RAPIDA
═══════════════════════════════════════════════════════════

| Tipo atto | Formato | Esempio |
|-----------|---------|---------|
| Costituzione | art. N Cost. | art. 32 Cost. |
| Codice Civile | art. N c.c. | art. 2043 c.c. |
| Codice Penale | art. N c.p. | art. 640 c.p. |
| Cod. Proc. Civile | art. N c.p.c. | art. 163 c.p.c. |
| Cod. Proc. Penale | art. N c.p.p. | art. 405 c.p.p. |
| Legge | art. N L. NNN/AAAA | art. 7 L. 241/1990 |
| D.Lgs. | art. N D.Lgs. NNN/AAAA | art. 13 D.Lgs. 196/2003 |
| D.L. | art. N D.L. NNN/AAAA | art. 1 D.L. 18/2020 |
| D.P.R. | art. N D.P.R. NNN/AAAA | art. 4 D.P.R. 380/2001 |
| D.M. | art. N D.M. NNN/AAAA | art. 2 D.M. 55/2014 |
| Reg. UE | art. N Reg. UE AAAA/NNN | art. 6 Reg. UE 2016/679 |
| Dir. UE | art. N Dir. AAAA/NNN/UE | art. 5 Dir. 2001/29/CE |
| Comma | co. N | art. 1, co. 3, L. 190/2012 |
| Lettera | lett. a) | art. 6, co. 1, lett. a) GDPR |

═══════════════════════════════════════════════════════════
COME RECUPERARE IL TESTO DI UNA NORMA
═══════════════════════════════════════════════════════════

Usare SEMPRE il tool `cite_law` per ottenere il testo vigente di qualsiasi norma.
NON cercare su siti web esterni — cite_law interroga direttamente le fonti ufficiali.

cite_law accetta riferimenti in linguaggio naturale:
- "art. 13 GDPR" → Reg. UE 2016/679, art. 13
- "art. 2043 c.c." → Codice Civile, art. 2043
- "art. 6 D.Lgs. 231/2001" → D.Lgs. 231/2001, art. 6
- "art. 117 Costituzione" → Costituzione, art. 117
- "art. 33 GDPR" con include_annotations=true → testo + giurisprudenza + dottrina

Supporta: Codice Civile, Penale, Proc. Civile, Proc. Penale, Costituzione,
GDPR, D.Lgs. 196/2003, D.Lgs. 231/2001, TUF, TUIR, e molti altri.
"""


@mcp.resource(
    "legal://riferimenti/codici-e-leggi-principali",
    name="Codici e Leggi Principali — Riferimento Rapido",
    description="Indice ragionato dei principali codici, testi unici e leggi italiane ed europee con ambito e citazione",
)
def codici_e_leggi_principali() -> str:
    return """CODICI E LEGGI PRINCIPALI — INDICE RAPIDO PER LA RICERCA NORMATIVA

═══════════════════════════════════════════════════════════
CODICI
═══════════════════════════════════════════════════════════

| Codice | Abbreviazione | Anno | Articoli chiave |
|--------|---------------|------|-----------------|
| Codice Civile | c.c. | 1942 | 1-2969 — obbligazioni, contratti, proprietà, famiglia, successioni |
| Codice Penale | c.p. | 1930 | 1-734 — reati, pene, circostanze, concorso |
| Cod. Procedura Civile | c.p.c. | 1940 | 1-840 — giurisdizione, processo, esecuzione |
| Cod. Procedura Penale | c.p.p. | 1988 | 1-746 — indagini, dibattimento, impugnazioni |
| Codice della Navigazione | c.nav. | 1942 | navigazione marittima e aerea |
| Codice della Strada | C.d.S. | D.Lgs. 285/1992 | circolazione, sanzioni, patente |

═══════════════════════════════════════════════════════════
TESTI UNICI E CODICI DI SETTORE
═══════════════════════════════════════════════════════════

| Nome | Riferimento | Citazione | Materia |
|------|-------------|-----------|---------|
| Cod. Assicurazioni Private | D.Lgs. 209/2005 | art. N CdA | RC auto, danno biologico (artt. 138-139) |
| Cod. del Consumo | D.Lgs. 206/2005 | art. N Cod. Cons. | tutela consumatore, pratiche commerciali |
| Cod. Privacy | D.Lgs. 196/2003 | art. N D.Lgs. 196/2003 | protezione dati personali (integrativo GDPR) |
| Cod. Amministrazione Digitale | D.Lgs. 82/2005 | art. N CAD | PEC, firma digitale, documento informatico |
| TU Edilizia | D.P.R. 380/2001 | art. N TUE | permesso costruire, SCIA, abusi |
| TU Imposte sui Redditi | D.P.R. 917/1986 | art. N TUIR | IRPEF, IRES, deduzioni, detrazioni |
| TU Spese di Giustizia | D.P.R. 115/2002 | art. N DPR 115/2002 | contributo unificato, patrocinio |
| TU Enti Locali | D.Lgs. 267/2000 | art. N TUEL | comuni, province, organi, bilancio |
| Cod. Contratti Pubblici | D.Lgs. 36/2023 | art. N Cod. Appalti | appalti, concessioni, procedure |
| Cod. Crisi d'Impresa | D.Lgs. 14/2019 | art. N CCII | insolvenza, concordato, liquidazione |
| Cod. Antimafia | D.Lgs. 159/2011 | art. N Cod. Antimafia | misure di prevenzione, interdittive |
| Cod. Terzo Settore | D.Lgs. 117/2017 | art. N CTS | ETS, associazioni, fondazioni, ONLUS |

═══════════════════════════════════════════════════════════
LEGGI FONDAMENTALI
═══════════════════════════════════════════════════════════

| Nome | Riferimento | Materia |
|------|-------------|---------|
| Procedimento amministrativo | L. 241/1990 | accesso atti, silenzio-assenso, SCIA, conferenza servizi |
| Statuto dei Lavoratori | L. 300/1970 | diritti sindacali, licenziamento (art. 18) |
| Responsabilità enti | D.Lgs. 231/2001 | responsabilità amministrativa società, MOG, OdV |
| Mediazione civile | D.Lgs. 28/2010 | mediazione obbligatoria, accordo, verbale |
| Negoziazione assistita | D.L. 132/2014 | separazione, divorzio, crediti |
| Processo telematico | D.M. 44/2011 | PCT, deposito telematico, PEC |
| Parametri forensi | D.M. 55/2014 | compensi avvocati (agg. D.M. 147/2022) |
| Locazioni | L. 392/1978 (equo canone) + L. 431/1998 | contratti abitativi e commerciali |
| Condominio | artt. 1117-1139 c.c. (rif. L. 220/2012) | parti comuni, assemblea, amministratore |
| Divorzio | L. 898/1970 | scioglimento matrimonio, assegno |
| Adozione | L. 184/1983 | adozione nazionale e internazionale |
| Fallimento (abrogato) | R.D. 267/1942 | sostituito da CCII per procedure dal 15/07/2022 |

═══════════════════════════════════════════════════════════
NORMATIVA UE CHIAVE
═══════════════════════════════════════════════════════════

| Nome | Riferimento | Citazione breve | Materia |
|------|-------------|-----------------|---------|
| GDPR | Reg. UE 2016/679 | art. N GDPR | protezione dati personali |
| AI Act | Reg. UE 2024/1689 | art. N AI Act | intelligenza artificiale |
| DORA | Reg. UE 2022/2554 | art. N DORA | resilienza operativa digitale (finanza) |
| DSA | Reg. UE 2022/2065 | art. N DSA | servizi digitali, piattaforme |
| DMA | Reg. UE 2022/1925 | art. N DMA | mercati digitali, gatekeeper |
| EHDS | Reg. UE 2025/327 | art. N EHDS | spazio europeo dati sanitari |
| NIS 2 | Dir. UE 2022/2555 | art. N NIS 2 | cybersicurezza (rec. D.Lgs. 138/2024) |
| CER | Dir. UE 2022/2557 | art. N CER | resilienza entità critiche |
| Dir. Whistleblowing | Dir. UE 2019/1937 | art. N Dir. 2019/1937 | segnalazioni illeciti (rec. D.Lgs. 24/2023) |
| Dir. Copyright | Dir. UE 2019/790 | art. N Dir. 2019/790 | diritto d'autore digitale |

═══════════════════════════════════════════════════════════
STRATEGIA DI RICERCA NORMATIVA
═══════════════════════════════════════════════════════════

1. IDENTIFICARE L'AREA → consultare questa tabella per trovare le fonti pertinenti
2. RECUPERARE IL TESTO → cite_law("art. N [fonte]") per il testo vigente
3. ANNOTAZIONI → cite_law("art. N [fonte]", include_annotations=true) per giurisprudenza
4. NORME COLLEGATE → cercare richiami interni ed esterni nel testo recuperato
5. VERIFICARE MODIFICHE → controllare se la norma è stata novellata di recente
6. COORDINARE LE FONTI → applicare i criteri di risoluzione delle antinomie

Usa sempre cite_law PRIMA di citare qualsiasi norma — mai affidarsi alla memoria.
"""


@mcp.resource(
    "legal://riferimenti/gdpr-checklist",
    name="GDPR Compliance — Checklist Operativa",
    description="Checklist completa per la conformità GDPR: adempimenti, documenti, scadenze e tool disponibili",
)
def gdpr_checklist() -> str:
    return """GDPR COMPLIANCE — CHECKLIST OPERATIVA
(Reg. UE 2016/679, D.Lgs. 196/2003 come mod. D.Lgs. 101/2018)

═══════════════════════════════════════════════════════════
1. MAPPATURA TRATTAMENTI (Art. 30)
═══════════════════════════════════════════════════════════

☐ Censimento di tutti i trattamenti di dati personali
☐ Per ogni trattamento, registrare:
  ☐ Finalità del trattamento
  ☐ Base giuridica (art. 6) → usa `analisi_base_giuridica()`
  ☐ Categorie di interessati
  ☐ Categorie di dati personali
  ☐ Destinatari (interni ed esterni)
  ☐ Termine di cancellazione
  ☐ Misure di sicurezza (art. 32)
☐ Compilare il registro trattamenti → usa `genera_registro_trattamenti()`
☐ Aggiornare il registro ad ogni variazione significativa

═══════════════════════════════════════════════════════════
2. BASI GIURIDICHE (Art. 6)
═══════════════════════════════════════════════════════════

| Base | Lettera | Contesto tipico | Tool |
|------|---------|-----------------|------|
| Consenso | art. 6(1)(a) | Marketing, profilazione, cookie | `analisi_base_giuridica()` |
| Contratto | art. 6(1)(b) | E-commerce, clienti, dipendenti | `analisi_base_giuridica()` |
| Obbligo legale | art. 6(1)(c) | Adempimenti fiscali, AML | `analisi_base_giuridica()` |
| Interesse vitale | art. 6(1)(d) | Emergenze sanitarie | `analisi_base_giuridica()` |
| Interesse pubblico | art. 6(1)(e) | PA, sanità pubblica | `analisi_base_giuridica()` |
| Legittimo interesse | art. 6(1)(f) | Sicurezza, antifrode, CRM | `analisi_base_giuridica()` |

Per dati particolari (art. 9): serve condizione aggiuntiva ex art. 9(2)

═══════════════════════════════════════════════════════════
3. INFORMATIVE (Artt. 13-14)
═══════════════════════════════════════════════════════════

☐ Informativa generale (sito web / clienti) → `genera_informativa_privacy(tipo="art13")`
☐ Informativa per dati da terzi → `genera_informativa_privacy(tipo="art14")`
☐ Informativa cookie → `genera_informativa_cookie()`
☐ Informativa dipendenti → `genera_informativa_dipendenti()`
☐ Informativa videosorveglianza (cartello + estesa) → `genera_informativa_videosorveglianza()`

Elementi obbligatori art. 13:
- Identità titolare e contatti
- Contatti DPO (se nominato)
- Finalità e base giuridica
- Destinatari
- Trasferimento extra-UE (se presente)
- Periodo di conservazione
- Diritti dell'interessato
- Diritto di reclamo al Garante

═══════════════════════════════════════════════════════════
4. RESPONSABILI DEL TRATTAMENTO (Art. 28)
═══════════════════════════════════════════════════════════

☐ Censire tutti i fornitori che trattano dati personali per conto del titolare
☐ Per ciascun responsabile, stipulare DPA → usa `genera_dpa()`
☐ Le 8 clausole obbligatorie (art. 28(3)):
  1. Trattamento solo su istruzioni documentate del titolare
  2. Riservatezza delle persone autorizzate
  3. Misure di sicurezza (art. 32)
  4. Condizioni per sub-responsabili
  5. Assistenza per diritti degli interessati
  6. Assistenza per sicurezza, breach, DPIA
  7. Cancellazione o restituzione alla cessazione
  8. Diritto di audit

═══════════════════════════════════════════════════════════
5. VALUTAZIONE D'IMPATTO — DPIA (Art. 35)
═══════════════════════════════════════════════════════════

☐ Verificare la necessità → usa `verifica_necessita_dpia()`
☐ Criteri WP248: se ≥2 su 9 → DPIA obbligatoria
☐ Se necessaria → usa `genera_dpia()` per documentarla

I 9 criteri WP248 rev.01:
1. Valutazione/scoring/profilazione
2. Decisione automatizzata con effetti giuridici
3. Monitoraggio sistematico
4. Dati sensibili o altamente personali
5. Trattamento su larga scala
6. Incrocio/combinazione di dataset
7. Soggetti vulnerabili
8. Nuove tecnologie
9. Impedimento all'esercizio di diritti

═══════════════════════════════════════════════════════════
6. DATA BREACH (Artt. 33-34)
═══════════════════════════════════════════════════════════

☐ Predisporre procedura interna per la gestione dei data breach
☐ In caso di violazione:
  ☐ Valutare il rischio → usa `valutazione_data_breach()`
  ☐ Se rischio per diritti e libertà → notifica al Garante entro 72 ore
  ☐ Se rischio elevato → comunicare agli interessati
  ☐ Generare il modulo di notifica → usa `genera_notifica_data_breach()`
☐ Registrare ogni violazione nel registro dei data breach (art. 33(5))

═══════════════════════════════════════════════════════════
7. SANZIONI (Art. 83)
═══════════════════════════════════════════════════════════

| Tipo violazione | Massimale |
|-----------------|-----------|
| Art. 83(4) — obblighi titolare/responsabile | € 10M o 2% fatturato |
| Art. 83(5) — principi, diritti, trasferimenti | € 20M o 4% fatturato |
| Art. 83(6) — inosservanza ordini autorità | € 20M o 4% fatturato |

Stima sanzioni → usa `calcolo_sanzione_gdpr()`

═══════════════════════════════════════════════════════════
8. SCADENZE E TERMINI
═══════════════════════════════════════════════════════════

| Adempimento | Termine | Norma |
|-------------|---------|-------|
| Notifica data breach al Garante | 72 ore dalla scoperta | Art. 33(1) |
| Risposta a richieste degli interessati | 30 giorni (prorogabili a 90) | Art. 12(3) |
| DPIA prima dell'avvio del trattamento | Preventiva | Art. 35(1) |
| Consultazione preventiva (se rischio residuo alto) | Prima del trattamento | Art. 36 |
| Aggiornamento registro trattamenti | Continuativo | Art. 30 |
| Revisione DPIA | Se cambiano rischi | Art. 35(11) |
"""
