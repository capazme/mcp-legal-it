"""MCP Resources — 12 static legal reference documents."""

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


@mcp.resource(
    "legal://riferimenti/consob-delibere",
    name="CONSOB — Guida Ricerca Delibere",
    description="Guida all'uso dei tool CONSOB: tipologie, argomenti, workflow e riferimenti normativi mercati finanziari",
)
def consob_delibere() -> str:
    return """CONSOB — GUIDA ALLA RICERCA DELIBERE E PROVVEDIMENTI
(Commissione Nazionale per le Società e la Borsa)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_delibere_consob` | Ricerca nel bollettino | query, tipologia, argomento, data_da, data_a |
| `leggi_delibera_consob` | Testo completo delibera | numero (es. "23257") |
| `ultime_delibere_consob` | Ultime pubblicate | tipologia, argomento, max_risultati |

═══════════════════════════════════════════════════════════
TIPOLOGIE (filtro per tipo di provvedimento)
═══════════════════════════════════════════════════════════

| Chiave | Descrizione |
|--------|-------------|
| `delibere` | Delibere della Commissione |
| `comunicazioni` | Comunicazioni ufficiali |
| `provvedimenti_urgenti` | Provvedimenti d'urgenza |
| `opa` | Provvedimenti OPA |
| `regolamenti` | Regolamenti CONSOB |
| `interpelli` | Risposte a interpelli |
| `pareri` | Pareri resi dalla Commissione |

═══════════════════════════════════════════════════════════
ARGOMENTI (filtro per materia — ID Liferay)
═══════════════════════════════════════════════════════════

| Chiave | Descrizione | ID |
|--------|-------------|----|
| `abusi_di_mercato` | Market abuse, insider trading, manipolazione | 4989535 |
| `intermediari` | SIM, SGR, banche, consulenti | 4989527 |
| `emittenti` | Obblighi informativi società quotate | 4989652 |
| `mercati` | Struttura e regolamentazione mercati | 4989533 |
| `offerte_acquisto` | OPA, OPS, offerte pubbliche | 4989651 |
| `gestione_collettiva` | OICR, fondi, SICAV | 4989529 |
| `servizi_investimento` | MiFID II, adeguatezza, best execution | 4989531 |
| `cripto_attivita` | MiCA, crypto-asset, token | 4989653 |
| `crowdfunding` | Piattaforme, Reg. UE 2020/1503 | 4989654 |
| `vigilanza` | Attività di vigilanza generale | 4989534 |

═══════════════════════════════════════════════════════════
WORKFLOW CONSIGLIATI
═══════════════════════════════════════════════════════════

Ricerca tematica:
1. cerca_delibere_consob(query="tema") → lista delibere
2. leggi_delibera_consob(numero) → testo completo
3. cite_law("art. N TUF") → norma di riferimento

Monitoraggio novità:
1. ultime_delibere_consob() → ultime pubblicate
2. ultime_delibere_consob(argomento="intermediari") → per materia
3. leggi_delibera_consob(numero) → approfondimento

═══════════════════════════════════════════════════════════
NORMATIVA DI RIFERIMENTO MERCATI FINANZIARI
═══════════════════════════════════════════════════════════

| Fonte | Riferimento | Citazione | Materia |
|-------|-------------|-----------|---------|
| TUF | D.Lgs. 58/1998 | art. N TUF | Testo unico finanza |
| Reg. Emittenti | Reg. CONSOB 11971/1999 | — | Obblighi emittenti |
| Reg. Intermediari | Reg. CONSOB 20307/2018 | — | Servizi investimento |
| Reg. Mercati | Reg. CONSOB 20249/2017 | — | Struttura mercati |
| MAR | Reg. UE 596/2014 | art. N MAR | Abusi di mercato |
| MiFID II | Dir. 2014/65/UE | art. N MiFID II | Mercati strumenti fin. |
| MiFIR | Reg. UE 600/2014 | art. N MiFIR | Trasparenza mercati |
| MiCA | Reg. UE 2023/1114 | art. N MiCA | Cripto-attività |
| Crowdfunding | Reg. UE 2020/1503 | art. N Reg. 2020/1503 | Piattaforme crowdfunding |
| DORA | Reg. UE 2022/2554 | art. N DORA | Resilienza digitale |

Per il testo di queste norme: usare cite_law("art. N [fonte]").

═══════════════════════════════════════════════════════════
CROSS-REFERENCE GIURISPRUDENZA
═══════════════════════════════════════════════════════════

Per sentenze della Cassazione correlate a temi CONSOB:
1. cerca_giurisprudenza(query="\"tema\"", modalita="esplora") → distribuzione
2. Filtra con materia/sezione dai facets
3. leggi_sentenza(numero, anno) → testo integrale

Vedi risorsa: legal://riferimenti/ricerca-giurisprudenziale

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- Il numero delibera è nel formato numerico (es. "23257") o con suffisso (es. "23256-1")
- Le date nei filtri usano formato YYYY-MM-DD (es. "2024-01-01")
- Il testo delle delibere è troncato a 8000 caratteri per evitare saturazione del contesto
- La ricerca interroga il Bollettino CONSOB (Liferay Portal) — dati pubblici, nessuna autenticazione
"""


@mcp.resource(
    "legal://riferimenti/ricerca-giurisprudenziale",
    name="Ricerca Giurisprudenziale — Guida Italgiure",
    description="Guida alla ricerca su Italgiure: strategia esplora→filtra→leggi, sintassi Solr, facets e workflow tipo",
)
def ricerca_giurisprudenziale() -> str:
    return """RICERCA GIURISPRUDENZIALE — GUIDA ALL'USO DI ITALGIURE
(Archivio Cassazione, sentenze dal 2020 in poi)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza` | Ricerca full-text | query, modalita, campo, materia, sezione, tipo_provvedimento, archivio, max_risultati |
| `giurisprudenza_su_norma` | Sentenze su un articolo | riferimento, solo_sezioni_unite, anno_da, anno_a, archivio |
| `leggi_sentenza` | Testo completo | numero, anno, sezione, archivio |
| `ultime_pronunce` | Ultime depositate | materia, sezione, archivio |

═══════════════════════════════════════════════════════════
STRATEGIA: ESPLORA → FILTRA → LEGGI
═══════════════════════════════════════════════════════════

### Passo 1 — Esplora la distribuzione
```
cerca_giurisprudenza(query="\"tema\"", modalita="esplora")
```
Restituisce solo i facets (materia, sezione, anno, tipo provvedimento) SENZA documenti.
Serve per capire dove si concentrano i risultati prima di cercare.

### Passo 2 — Filtra con i facets
In base alla distribuzione, scegli i filtri:
- **Materia** dominante (>40%) → filtra per materia
- **Sezione** dominante (es. III per resp. civile) → filtra per sezione
- **Sezioni Unite** presenti → cercale separatamente (le più autorevoli)
- `tipo_provvedimento="sentenza"` → esclude ordinanze (meno motivate)

```
cerca_giurisprudenza(
    query="\"tema\"",
    materia="...",
    sezione="...",
    tipo_provvedimento="sentenza",
    max_risultati=10
)
```

### Passo 3 — Leggi le decisioni chiave
Per le 2-4 decisioni più rilevanti:
```
leggi_sentenza(numero=XXXXX, anno=2024)
```
Privilegia: Sezioni Unite > sentenze recenti > sentenze (non ordinanze).

═══════════════════════════════════════════════════════════
SINTASSI QUERY SOLR
═══════════════════════════════════════════════════════════

Il motore è Solr eDisMax. Sintassi supportata nel campo `query`:

| Sintassi | Effetto | Esempio |
|----------|---------|---------|
| `"frase esatta"` | Match testuale esatto | `"responsabilità medica"` |
| `AND` / `OR` | Operatori booleani (default: OR) | `"art. 2043" AND "danno"` |
| `-termine` | Esclude termine | `"onere prova" -lavoro` |
| `"frase"~3` | Prossimità (entro N parole) | `"nesso causale"~5` |
| `termin*` | Wildcard (prefisso) | `risarcim*` |

REGOLA: usare SEMPRE virgolette per frasi di 2+ parole correlate.

═══════════════════════════════════════════════════════════
PARAMETRO `campo`
═══════════════════════════════════════════════════════════

| Valore | Cerca in | Quando usare |
|--------|----------|--------------|
| (default) | Testo completo (OCR) | Ricerca ampia |
| `"dispositivo"` | Solo dispositivo | Più preciso, meno recall |

═══════════════════════════════════════════════════════════
FACETS DISPONIBILI
═══════════════════════════════════════════════════════════

| Facet | Descrizione | Esempio valori |
|-------|-------------|----------------|
| Materia | Area giuridica | Obbligazioni, Lavoro, Famiglia |
| Sezione | Sezione della Corte | I, II, III, lav., SU |
| Anno | Anno di deposito | 2020, 2021, ..., 2026 |
| Tipo provvedimento | Tipo decisione | sentenza, ordinanza |

═══════════════════════════════════════════════════════════
ARCHIVI
═══════════════════════════════════════════════════════════

| Archivio | Collezione Solr | Documenti |
|----------|----------------|-----------|
| `civile` | snciv | ~186K |
| `penale` | snpen | ~238K |
| `tutti` (default) | entrambi | ~424K |

═══════════════════════════════════════════════════════════
WORKFLOW TIPO
═══════════════════════════════════════════════════════════

Ricerca su tema:
1. cerca_giurisprudenza(query="\"tema\"", modalita="esplora")
2. Analizza facets → scegli filtri
3. cerca_giurisprudenza(query="\"tema\"", materia="...", sezione="...", max_risultati=10)
4. leggi_sentenza(numero, anno) per le 2-3 decisioni chiave
5. cite_law("art. ...") per le norme citate

Ricerca su norma specifica:
1. giurisprudenza_su_norma(riferimento="art. 2043 c.c.")
2. leggi_sentenza(numero, anno) per le decisioni chiave
3. cerca_brocardi("art. 2043 c.c.") per massime e dottrina

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- API: Solr REST su italgiure.giustizia.it (pubblica, nessuna autenticazione)
- OCR troncato a 30000 caratteri per evitare saturazione contesto
- Certificato SSL non valido → verify=False (necessario)
- Campi chiave: numdec (numero), anno, datdep (data deposito), szdec (sezione), ocr (testo)
"""


@mcp.resource(
    "legal://riferimenti/cerdef-giurisprudenza",
    name="CeRDEF — Giurisprudenza Tributaria",
    description="Guida ai tool CeRDEF: enti, criteri di ricerca, tipi provvedimento e norme fiscali principali",
)
def cerdef_giurisprudenza() -> str:
    return """CeRDEF — BANCA DATI GIURISPRUDENZA TRIBUTARIA (def.finanze.it)
(Ministero dell'Economia e delle Finanze)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza_tributaria` | Ricerca nel database | query, tipo_provvedimento, ente, data_da, data_a, numero, criterio, ordinamento |
| `cerdef_leggi_provvedimento` | Testo completo provvedimento | guid |
| `ultime_sentenze_tributarie` | Ultime pubblicate | ente, tipo_provvedimento, max_risultati |

═══════════════════════════════════════════════════════════
ENTI (filtro per organo giudicante)
═══════════════════════════════════════════════════════════

| Chiave | Denominazione completa |
|--------|------------------------|
| `corte_suprema` | Corte Suprema di Cassazione |
| `cgt_primo_grado` | CGT I grado (Corte di Giustizia Tributaria di primo grado) |
| `cgt_secondo_grado` | CGT II grado (Corte di Giustizia Tributaria di secondo grado) |

Nota: CGT = Commissioni Tributarie rinominate dalla L. 130/2022 (ex CTP/CTR).

═══════════════════════════════════════════════════════════
CRITERI DI RICERCA
═══════════════════════════════════════════════════════════

| Chiave | Codice | Effetto |
|--------|--------|---------|
| `tutti` | T | Tutte le parole (default) |
| `frase_esatta` | E | Frase esatta |
| `almeno_uno` | O | Almeno una parola |
| `codice` | C | Per codice/numero atto |

═══════════════════════════════════════════════════════════
TIPI PROVVEDIMENTO
═══════════════════════════════════════════════════════════

| Chiave | Tipo |
|--------|------|
| `sentenza` | Sentenza |
| `ordinanza` | Ordinanza |
| `decreto` | Decreto |

═══════════════════════════════════════════════════════════
NORME TRIBUTARIE PRINCIPALI
═══════════════════════════════════════════════════════════

| Nome | Riferimento | Citazione | Materia |
|------|-------------|-----------|---------|
| TUIR | D.P.R. 917/1986 | art. N TUIR | IRPEF, IRES, redditi, deduzioni |
| IVA | D.P.R. 633/1972 | art. N DPR 633/1972 | Imposta sul Valore Aggiunto |
| Contenzioso tributario | D.Lgs. 546/1992 | art. N D.Lgs. 546/1992 | Processo tributario |
| Sanzioni tributarie | D.Lgs. 472/1997 | art. N D.Lgs. 472/1997 | Sanzioni amministrative fiscali |
| Accertamento imposte | D.P.R. 600/1973 | art. N DPR 600/1973 | Accertamento IRPEF/IRES |
| Riscossione | D.P.R. 602/1973 | art. N DPR 602/1973 | Riscossione coattiva |
| Registro | D.P.R. 131/1986 | art. N DPR 131/1986 | Imposta di registro |
| IMU | D.Lgs. 23/2011 + L. 160/2019 | art. N D.Lgs. 23/2011 | Imposta municipale propria |
| ICI (storico) | D.Lgs. 504/1992 | art. N D.Lgs. 504/1992 | Imposta comunale sugli immobili |
| Successioni e donazioni | D.Lgs. 346/1990 | art. N D.Lgs. 346/1990 | Imposta successioni e donazioni |

Per il testo vigente: usare cite_law("art. N [fonte]").

═══════════════════════════════════════════════════════════
WORKFLOW CONSIGLIATI
═══════════════════════════════════════════════════════════

Ricerca tematica:
1. cerca_giurisprudenza_tributaria(query="tema") → lista provvedimenti
2. cerdef_leggi_provvedimento(guid) → massima e testo completo
3. cite_law("art. N TUIR") → norma tributaria di riferimento

Monitoraggio novità:
1. ultime_sentenze_tributarie() → ultime pubblicate
2. ultime_sentenze_tributarie(ente="corte_suprema") → solo Cassazione
3. cerdef_leggi_provvedimento(guid) → approfondimento

Ricerca per ente e tipo:
cerca_giurisprudenza_tributaria(query="IVA", ente="corte_suprema", tipo_provvedimento="sentenza")

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- Endpoint: def.finanze.it/DocTribFrontend/ (MEF — dati pubblici)
- Ricerca: POST form-encoded, risultati in XML embedded in JS
- Testo troncato a 25000 caratteri per evitare saturazione del contesto
- Il GUID identifica univocamente ogni provvedimento
- Date nei parametri di ricerca: formato DD/MM/YYYY
- Max risultati: 250 per richiesta (paginazione automatica via cookie di sessione)
"""


@mcp.resource(
    "legal://riferimenti/modelli-atti-catalogo",
    name="Catalogo Modelli Atti — 100 Tipi",
    description="Indice di tutti i 100 tipi di atti legali generabili: routing, tool, resource e campi obbligatori per ciascun tipo",
)
def modelli_atti_catalogo() -> str:
    return """CATALOGO MODELLI ATTI LEGALI — 100 TIPI DISPONIBILI
Per generare un atto: chiama genera_modello_atto(tipo_atto="nome_tipo") per i metadati.

═══════════════════════════════════════════════════════════
CATEGORIE E TIPI
═══════════════════════════════════════════════════════════

ATTI INTRODUTTIVI (11 tipi)
  Tier 1 (tool diretto): decreto_ingiuntivo_ordinario, decreto_ingiuntivo_professionale,
    decreto_ingiuntivo_condominiale, decreto_ingiuntivo_cambiale, sfratto_morosita
  Tier 2 (enhance): decreto_ingiuntivo_fatture, decreto_ingiuntivo_retribuzioni
  Tier 3 (resource): citazione_ordinaria, ricorso_giudice_pace, ricorso_semplificato,
    atto_appello, opposizione_decreto_ingiuntivo

ESECUZIONE (16 tipi)
  Tier 1: atto_di_precetto, nota_precisazione_credito, dichiarazione_553_cpc
  Tier 3: ricerca_beni_492bis, pignoramento_presso_terzi, pignoramento_immobiliare,
    avviso_543_5_cpc, cessazione_obbligo_custodia, ordinanza_assegnazione_somme,
    ordinanza_assegnazione_crediti, ordinanza_assegnazione_543_cpc, proroga_567_cpc,
    vendita_mobili, vendita_immobili, rinuncia_esecuzione, rinuncia_intervento,
    perdita_efficacia_pignoramento, assegnazione_510_cpc, termine_efficacia_titolo

NOTIFICHE (9 tipi)
  Tier 1: relata_pec_generica
  Tier 2: relata_pec_decreto_ingiuntivo, relata_pec_opposizione_di, relata_pec_appello,
    relata_pec_sentenza_giudicato, relata_pec_penale, relata_unep, relata_pat
  Tier 3: relata_posta

ATTESTAZIONI (11 tipi)
  Tier 1: attestazione_estratto, attestazione_copia_informatica, attestazione_duplicato
  Tier 2: attestazione_margine_fascicolo, attestazione_separata_fascicolo,
    attestazione_margine_scanner, attestazione_separata_scanner, attestazione_archivio_zip,
    attestazione_stampe_pec, attestazione_composito_di, attestazione_composito_decreto

PROCURE (8 tipi)
  Tier 1: procura_generale, procura_speciale, procura_appello
  Tier 2: procura_mediazione, procura_mediazione_sostanziale, procura_negoziazione,
    procura_arbitrato, procura_incarico_professionale

STRAGIUDIZIALE (8 tipi)
  Tier 1: sollecito_pagamento
  Tier 2: sollecito_formale_mora, sollecito_prima_richiesta, sollecito_post_sentenza
  Tier 3: invito_negoziazione, adesione_negoziazione, lettera_adeguamento_istat,
    richiesta_nominativi_morosi

ISTANZE (6 tipi)
  Tier 3: istanza_esecutorieta, certificato_giudicato, istanza_giudicato,
    ricorso_intervento, avviso_impugnazione, avviso_opposizione_di

PCT (2 tipi)
  Tier 3: nota_deposito_pct, nomina_ctp

PREVENTIVI (17 tipi)
  Tier 1: preventivo_civile, preventivo_stragiudiziale, preventivo_volontaria_giurisdizione
  Tier 4: preventivo_mediazione, preventivo_decreto_ingiuntivo, preventivo_opposizione_di,
    preventivo_precetto, preventivo_pignoramento, preventivo_esecuzione_mobiliare,
    preventivo_esecuzione_immobiliare, preventivo_atp, preventivo_giudice_pace,
    preventivo_cautelari, preventivo_lavoro, preventivo_appello, preventivo_penale,
    preventivo_sfratto

PRIVACY (8 tipi)
  Tier 1: informativa_privacy_art13, informativa_cookie, informativa_dipendenti,
    informativa_videosorveglianza, dpa_art28, registro_trattamenti, dpia,
    notifica_data_breach

═══════════════════════════════════════════════════════════
TIER E ROUTING
═══════════════════════════════════════════════════════════

Tier 1 — Tool diretto (27 tipi): l'atto è generato chiamando un tool esistente.
Tier 2 — Tool enhance (25 tipi): richiede enhancement dei tool esistenti (Fase 2).
Tier 3 — Resource + LLM (34 tipi): l'LLM compone l'atto leggendo un modello da resource (Fase 3).
Tier 4 — Preventivo parametrico (14 tipi): generato dal tool preventivo_procedura (Fase 4).

═══════════════════════════════════════════════════════════
WORKFLOW TIPO
═══════════════════════════════════════════════════════════

1. genera_modello_atto(tipo_atto="decreto_ingiuntivo_ordinario")
   → Restituisce: tool_diretto="decreto_ingiuntivo", campi, calcoli necessari
2. Raccogli i campi obbligatori dall'utente
3. Chiama i tool_calcolo (contributo_unificato, parcella_avvocato_civile, ...)
4. Chiama il tool_diretto o leggi la resource_modello
5. Verifica norme con cite_law()
6. Presenta l'atto completo con calcoli e checklist
"""


@mcp.resource(
    "legal://riferimenti/giustizia-amministrativa",
    name="Giustizia Amministrativa — Guida Ricerca TAR/CdS",
    description="Guida all'uso dei tool per la ricerca di sentenze TAR e Consiglio di Stato: sedi, tipi, workflow e normativa di riferimento",
)
def giustizia_amministrativa() -> str:
    return """GIUSTIZIA AMMINISTRATIVA — GUIDA ALLA RICERCA PROVVEDIMENTI TAR/CdS
(giustizia-amministrativa.it — mdp.giustizia-amministrativa.it)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza_amministrativa` | Ricerca full-text TAR/CdS | query, sede, tipo, anno, max_risultati |
| `leggi_provvedimento_amm` | Testo completo dal sottodominio mdp | sede, nrg, nome_file |
| `giurisprudenza_amm_su_norma` | Decisioni che citano un articolo | riferimento, sede, anno_da |
| `ultimi_provvedimenti_amm` | Ultimi depositati | sede, tipo, max_risultati |

═══════════════════════════════════════════════════════════
SEDI DISPONIBILI (28 sedi)
═══════════════════════════════════════════════════════════

| Chiave | Codice | Sede |
|--------|--------|------|
| `consiglio_di_stato` | CDS | Consiglio di Stato |
| `cgars` | CGARS | CGARS (Consiglio di Giustizia Amministrativa per la Regione Siciliana) |
| `tar_lazio` | TARLAZ | TAR Lazio |
| `tar_lombardia` | TARLOM | TAR Lombardia |
| `tar_campania_napoli` | TARCAM | TAR Campania - Napoli |
| `tar_campania_salerno` | TARCAMSAL | TAR Campania - Salerno |
| `tar_sicilia_palermo` | TARSIC | TAR Sicilia - Palermo |
| `tar_sicilia_catania` | TARSICCAT | TAR Sicilia - Catania |
| `tar_veneto` | TARVEN | TAR Veneto |
| `tar_piemonte` | TARPIE | TAR Piemonte |
| `tar_emilia_romagna` | TAREMI | TAR Emilia-Romagna |
| `tar_toscana` | TARTOS | TAR Toscana |
| `tar_puglia_bari` | TARPUG | TAR Puglia - Bari |
| `tar_puglia_lecce` | TARPUGLEC | TAR Puglia - Lecce |
| `tar_calabria_catanzaro` | TARCAL | TAR Calabria - Catanzaro |
| `tar_calabria_reggio` | TARCALREG | TAR Calabria - Reggio |
| `tar_liguria` | TARLIG | TAR Liguria |
| `tar_sardegna` | TARSAR | TAR Sardegna |
| `tar_friuli` | TARFRI | TAR Friuli-Venezia Giulia |
| `tar_marche` | TARMAR | TAR Marche |
| `tar_abruzzo_pescara` | TARABR | TAR Abruzzo - Pescara |
| `tar_abruzzo_laquila` | TARABRLAQ | TAR Abruzzo - L'Aquila |
| `tar_umbria` | TARUMB | TAR Umbria |
| `tar_molise` | TARMOL | TAR Molise |
| `tar_basilicata` | TARBAS | TAR Basilicata |
| `tar_trentino_bolzano` | TARBOL | TAR Trentino-Alto Adige - Bolzano |
| `tar_trentino_trento` | TARTRETN | TAR Trentino-Alto Adige - Trento |
| `tar_valle_aosta` | TARVDA | TAR Valle d'Aosta |

═══════════════════════════════════════════════════════════
TIPI DI PROVVEDIMENTO
═══════════════════════════════════════════════════════════

| Chiave | Descrizione |
|--------|-------------|
| `sentenza` | Sentenza (decisione nel merito) |
| `ordinanza` | Ordinanza (cautelare, istruttoria) |
| `decreto` | Decreto monocratico (cautelare urgente) |
| `parere` | Parere del Consiglio di Stato |

═══════════════════════════════════════════════════════════
WORKFLOW CONSIGLIATI
═══════════════════════════════════════════════════════════

Ricerca tematica:
1. cerca_giurisprudenza_amministrativa(query="appalto esclusione requisiti")
2. leggi_provvedimento_amm(sede="CDS", nrg="...", nome_file="...")
3. cite_law("art. 83 D.Lgs. 36/2023") → norma di riferimento

Ricerca su norma:
1. giurisprudenza_amm_su_norma(riferimento="art. 21-nonies L. 241/1990")
2. leggi_provvedimento_amm(...) → testo completo decisioni
3. cite_law("art. 21-nonies L. 241/1990") → testo aggiornato

Monitoraggio novità:
1. ultimi_provvedimenti_amm(sede="consiglio_di_stato", tipo="sentenza")
2. leggi_provvedimento_amm(...) → approfondimento

═══════════════════════════════════════════════════════════
NORMATIVA AMMINISTRATIVA DI RIFERIMENTO
═══════════════════════════════════════════════════════════

| Fonte | Riferimento | Citazione | Materia |
|-------|-------------|-----------|---------|
| CPA | D.Lgs. 104/2010 | art. N CPA | Codice del Processo Amministrativo |
| Codice Appalti | D.Lgs. 36/2023 | art. N D.Lgs. 36/2023 | Appalti e concessioni |
| Procedimento amm. | L. 241/1990 | art. N L. 241/1990 | Accesso, silenzio, SCIA, conferenza servizi |
| TUEL | D.Lgs. 267/2000 | art. N TUEL | Enti locali, bilancio, organi |
| TU Edilizia | D.P.R. 380/2001 | art. N DPR 380/2001 | Permesso costruire, abusi edilizi |
| CAD | D.Lgs. 82/2005 | art. N CAD | Documento informatico, PEC |
| Codice Antimafia | D.Lgs. 159/2011 | art. N Cod. Antimafia | Informative antimafia, interdittive |
| D.Lgs. 33/2013 | D.Lgs. 33/2013 | art. N D.Lgs. 33/2013 | Trasparenza PA, accesso civico |

Per il testo aggiornato: usare cite_law("art. N [fonte]").

═══════════════════════════════════════════════════════════
MATERIE TIPICHE — ESEMPI DI QUERY
═══════════════════════════════════════════════════════════

| Materia | Query suggerita | Norma tipica |
|---------|----------------|--------------|
| Appalti — esclusione | "esclusione gara requisiti" | art. 94-98 D.Lgs. 36/2023 |
| Appalti — offerta anomala | "offerta anomala verifica" | art. 110 D.Lgs. 36/2023 |
| Silenzio-assenso | "silenzio-assenso formazione" | art. 20 L. 241/1990 |
| Accesso atti | "accesso documenti amministrativi" | art. 22 L. 241/1990 |
| Autotutela | "annullamento in autotutela" | art. 21-nonies L. 241/1990 |
| Urbanistica | "permesso costruire variante PRG" | DPR 380/2001 |
| Interdittiva antimafia | "informativa antimafia interdittiva" | D.Lgs. 159/2011 |
| Accesso civico | "accesso civico generalizzato FOIA" | D.Lgs. 33/2013 |

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- Il portale usa Liferay Portal — ricerca pubblica, nessuna autenticazione
- Testi integrali sul sottodominio mdp in formato XML <GA> (epigrafe + motivazione + dispositivo)
- Certificato SSL non valido → verify=False (necessario, come Italgiure)
- Il testo è troncato a 15000 caratteri per evitare saturazione del contesto
- I parametri sede, nrg e nome_file per leggi_provvedimento_amm vengono dai risultati di ricerca
- Adunanza Plenaria: massima autorità del CdS — privilegiare nelle ricerche
"""
