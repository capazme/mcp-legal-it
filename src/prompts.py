"""MCP Prompts — 16 guided legal workflow prompts for Claude."""

from src.server import mcp


@mcp.prompt(
    description="Analisi completa sinistro stradale/sanitario/lavoro con quantificazione danni"
)
def analisi_sinistro(
    tipo_sinistro: str, percentuale_invalidita: float, eta_vittima: int
) -> str:
    tool_biologico = (
        "danno_biologico_micro"
        if percentuale_invalidita <= 9
        else "danno_biologico_macro"
    )
    return f"""Analizza questo sinistro e produci una quantificazione completa del danno.

DATI:
- Tipo sinistro: {tipo_sinistro} (stradale / sanitario / lavoro)
- Invalidità permanente: {percentuale_invalidita}%
- Età vittima: {eta_vittima} anni

PROCEDURA (segui nell'ordine):

1. DANNO BIOLOGICO
   Chiama `{tool_biologico}` con percentuale={percentuale_invalidita} e eta={eta_vittima}.
   Annota il risultato come "danno biologico base".

2. DANNO NON PATRIMONIALE
   Chiama `danno_non_patrimoniale` per calcolare la componente di danno morale/esistenziale.
   Applica la personalizzazione in base al tipo di sinistro ({tipo_sinistro}):
   - Stradale: valuta dinamica relazionale (incidenza su mobilità, lavoro, sport)
   - Sanitario: valuta sofferenza da errore medico (componente iatrogena)
   - Lavoro: valuta incidenza sulla capacità lavorativa specifica

3. RIVALUTAZIONE MONETARIA
   Chiama `rivalutazione_monetaria` sugli importi dalla data del sinistro a oggi.

4. INTERESSI LEGALI
   Chiama `interessi_legali` sul capitale rivalutato, dalla data del sinistro a oggi.

FORMATO OUTPUT:
Presenta i risultati in una tabella riepilogativa con:
| Voce | Importo |
|------|---------|
| Danno biologico (base tabellare) | € ... |
| Personalizzazione (morale/esistenziale) | € ... |
| Totale danno non patrimoniale | € ... |
| Rivalutazione monetaria | € ... |
| Interessi legali | € ... |
| **TOTALE RISARCIMENTO** | **€ ...** |

AVVERTENZE:
- I valori sono calcolati sulle tabelle di Milano (danno biologico macro) o tabelle ex art. 139 CdA (danno micro ≤9%).
- La quantificazione è INDICATIVA e non sostituisce la valutazione medico-legale.
- Per invalidità temporanea, danno emergente e lucro cessante servono dati aggiuntivi.
- Citare sempre la fonte tabellare e normativa utilizzata.
"""


@mcp.prompt(
    description="Workflow completo per recupero credito: interessi, rivalutazione, decreto ingiuntivo e parcella"
)
def recupero_credito(
    importo: float, tipo_credito: str, data_scadenza: str
) -> str:
    return f"""Analizza questo credito insoluto e produci il piano completo di recupero.

DATI:
- Importo credito: € {importo:,.2f}
- Tipo: {tipo_credito} (commerciale / professionale / privato)
- Data scadenza: {data_scadenza}

PROCEDURA (segui nell'ordine):

1. INTERESSI DI MORA
   Chiama `interessi_mora` con importo={importo}, data_decorrenza="{data_scadenza}".
   Per crediti commerciali applica D.Lgs. 231/2002 (tasso BCE + 8 punti).
   Per crediti privati applica il tasso legale ex art. 1284 c.c.

2. RIVALUTAZIONE MONETARIA
   Chiama `rivalutazione_monetaria` con importo={importo} dalla data di scadenza a oggi.
   Nota: interessi di mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017) —
   presentali come alternative e indica quale è più favorevole al creditore.

3. DECRETO INGIUNTIVO
   Chiama `decreto_ingiuntivo` con importo={importo} per verificare:
   - Competenza (Giudice di Pace fino a € 5.000 / Tribunale oltre)
   - Contributo unificato dovuto
   - Requisiti documentali (fatture, contratto, estratto autentico notarile)
   - Possibilità di provvisoria esecutività (art. 642 c.p.c.)

4. PARCELLA AVVOCATO
   Chiama `parcella_avvocato_civile` con valore_causa={importo} per fase monitoria.
   Indica il range compenso (minimo/medio/massimo) da D.M. 55/2014.

FORMATO OUTPUT:
## Riepilogo Recupero Credito

| Voce | Importo |
|------|---------|
| Capitale | € {importo:,.2f} |
| Interessi di mora (da {data_scadenza} a oggi) | € ... |
| Rivalutazione ISTAT (alternativa) | € ... |
| **Totale dovuto** | **€ ...** |

## Costi procedura
| Voce | Importo |
|------|---------|
| Contributo unificato | € ... |
| Marca da bollo | € 27,00 |
| Diritti di notifica | € ... |
| Compenso avvocato (medio) | € ... |
| **Costo totale procedura** | **€ ...** |

## Raccomandazioni
- Indicare se conviene la diffida stragiudiziale prima del ricorso
- Valutare la provvisoria esecutività
- Tempi medi della procedura
"""


@mcp.prompt(
    description="Pianificazione causa civile: contributo unificato, scadenze, impugnazioni e preventivo"
)
def causa_civile(valore_causa: float, rito: str, grado: str) -> str:
    return f"""Pianifica questa causa civile con tutti i costi e le scadenze.

DATI:
- Valore causa: € {valore_causa:,.2f}
- Rito: {rito} (ordinario / sommario / lavoro)
- Grado: {grado} (primo / appello / cassazione)

PROCEDURA (segui nell'ordine):

1. CONTRIBUTO UNIFICATO
   Chiama `contributo_unificato` con valore={valore_causa}, rito="{rito}", grado="{grado}".
   Verifica eventuali esenzioni (es. cause di lavoro sotto soglia, procedimenti di volontaria giurisdizione).

2. SCADENZE PROCESSUALI
   Chiama `scadenza_processuale` per calcolare i termini chiave in base al rito:
   - Ordinario: comparsa risposta (70gg), memorie art. 171-ter c.p.c.
   - Sommario: costituzione resistente, eventuale mutamento rito
   - Lavoro: ricorso, memoria difensiva, note autorizzate
   Indica la sospensione feriale (1-31 agosto) se applicabile.

3. SCADENZE IMPUGNAZIONI
   Chiama `scadenze_impugnazioni` per i termini del grado attuale:
   - Primo grado → appello: 30gg (breve) / 6 mesi (lungo)
   - Appello → cassazione: 60gg (breve) / 6 mesi (lungo)
   - Revocazione, opposizione di terzo se pertinenti

4. PREVENTIVO COSTI
   Chiama `preventivo_civile` con valore={valore_causa}, rito="{rito}", grado="{grado}".
   Mostra il range di compenso per ogni fase processuale.

FORMATO OUTPUT:
## Quadro Economico
| Voce | Importo |
|------|---------|
| Contributo unificato | € ... |
| Marca da bollo (iscrizione a ruolo) | € 27,00 |
| Compenso avvocato (range min-max) | € ... — € ... |
| Spese generali (15%) | € ... |
| CPA (4%) + IVA (22%) | € ... |
| **Budget stimato (medio)** | **€ ...** |

## Scadenze Chiave
| Termine | Scadenza | Norma |
|---------|----------|-------|
| ... | ... | ... |

## Note
- Indicare i rischi di soccombenza e regime spese (art. 91 c.p.c.)
- Valutare la mediazione obbligatoria se applicabile (D.Lgs. 28/2010)
- Segnalare se il rito è soggetto a negoziazione assistita (D.L. 132/2014)
"""


@mcp.prompt(
    description="Pianificazione successoria: quote ereditarie, imposte e adempimenti"
)
def pianificazione_successione(
    valore_asse: float, grado_parentela: str, numero_eredi: int
) -> str:
    return f"""Analizza questa successione e calcola quote, imposte e adempimenti.

DATI:
- Valore asse ereditario: € {valore_asse:,.2f}
- Grado di parentela con il de cuius: {grado_parentela}
- Numero eredi: {numero_eredi}

PROCEDURA (segui nell'ordine):

1. QUOTE EREDITARIE
   Chiama `calcolo_eredita` con valore_asse={valore_asse}, grado_parentela="{grado_parentela}",
   numero_eredi={numero_eredi}.
   Distingui tra:
   - Successione legittima (senza testamento): quote ex artt. 565-586 c.c.
   - Quote di legittima (con testamento): riserva ex artt. 536-564 c.c.
   Indica la quota disponibile.

2. IMPOSTE DI SUCCESSIONE
   Chiama `imposte_successione` per calcolare:
   - Imposta di successione (aliquota per grado di parentela)
   - Franchigia applicabile (€ 1M coniuge/figli, € 100K fratelli, nessuna altri)
   - Imposte ipotecaria (2%) e catastale (1%) se ci sono immobili
   - Imposta di bollo e tassa ipotecaria

3. IMPOSTE COMPRAVENDITA (se applicabile)
   Se l'asse include immobili da vendere post-successione,
   chiama `imposte_compravendita` per stimare il carico fiscale sulla vendita.

FORMATO OUTPUT:
## Quote Ereditarie
| Erede | Quota | Valore |
|-------|-------|--------|
| ... | ... | € ... |
| Disponibile | ... | € ... |

## Imposte di Successione
| Voce | Importo |
|------|---------|
| Base imponibile | € ... |
| Franchigia | € ... |
| Imposta di successione | € ... |
| Imposta ipotecaria (2%) | € ... |
| Imposta catastale (1%) | € ... |
| **Totale imposte** | **€ ...** |

## Adempimenti
- Dichiarazione di successione: entro 12 mesi dall'apertura
- Voltura catastale: entro 30 giorni dalla dichiarazione
- Accettazione eredità: espressa o tacita, con beneficio d'inventario se opportuno
- Pubblicazione testamento olografo (se presente): tribunale competente

## Avvertenze
- I calcoli sono indicativi; la situazione patrimoniale completa potrebbe variare le imposte.
- Per successioni internazionali si applica il Reg. UE 650/2012.
- Valutare l'opportunità del beneficio d'inventario (art. 484 c.c.).
"""


@mcp.prompt(
    description="Struttura per parere legale: fatto, diritto, normativa e conclusioni con citazione norme"
)
def parere_legale(area_diritto: str, quesito: str) -> str:
    return f"""Redigi un parere legale strutturato seguendo il metodo giuridico italiano.

DATI:
- Area del diritto: {area_diritto} (civile / penale / amministrativo / lavoro)
- Quesito: {quesito}

PROCEDURA:

1. RICERCA NORMATIVA
   Usa `cite_law` per recuperare il testo vigente di ogni norma rilevante.
   NON citare articoli a memoria — recupera sempre il testo aggiornato.
   Cerca almeno:
   - La norma principale che disciplina la fattispecie
   - Eventuali norme collegate o modificative
   - Disposizioni procedurali applicabili

2. REDAZIONE PARERE
   Struttura il parere secondo lo schema seguente:

---

## PARERE PRO VERITATE

### 1. FATTO
Esponi i fatti rilevanti come emergono dal quesito.
Evidenzia gli elementi giuridicamente significativi.

### 2. QUESITO
Riformula il quesito in termini giuridici precisi.

### 3. DIRITTO

#### 3.1 Quadro normativo
Elenca e cita le norme applicabili (testo da cite_law).
Indica le fonti: legge, regolamento, direttiva UE, etc.

#### 3.2 Orientamento giurisprudenziale
Se disponibile (tramite cite_law con include_annotations=true),
riporta gli orientamenti di Cassazione e giurisprudenza di merito.

#### 3.3 Dottrina
Se pertinente, menziona le posizioni dottrinali prevalenti.

### 4. ANALISI
Applica le norme al caso concreto.
Valuta le diverse interpretazioni possibili.
Evidenzia punti di forza e criticità della posizione del richiedente.

### 5. CONCLUSIONI
Rispondi al quesito con indicazione chiara e motivata.
Indica le azioni consigliate e i relativi termini.

---

AVVERTENZE:
- Ogni norma citata DEVE essere verificata con cite_law.
- Il parere ha natura indicativa e non sostituisce l'assistenza legale.
- Indicare espressamente se la questione è controversa o priva di precedenti.
- Area: {area_diritto} — usa il linguaggio e le categorie proprie di quest'area.
"""


@mcp.prompt(
    description="Quantificazione danni: biologico, patrimoniale o morale con personalizzazione e attualizzazione"
)
def quantificazione_danni(
    tipo_danno: str, importo_o_percentuale: float, eta_vittima: int
) -> str:
    return f"""Quantifica il danno richiesto con personalizzazione e attualizzazione.

DATI:
- Tipo danno: {tipo_danno} (biologico / patrimoniale / morale)
- Valore/percentuale: {importo_o_percentuale}
- Età vittima: {eta_vittima} anni

PROCEDURA:

1. CALCOLO BASE
   In base al tipo di danno:

   **Biologico** (percentuale invalidità = {importo_o_percentuale}%):
   - Se ≤ 9%: chiama `danno_biologico_micro` (tabelle art. 139 CdA)
   - Se > 9%: chiama `danno_biologico_macro` (tabelle Milano)
   - Parametri: percentuale={importo_o_percentuale}, eta={eta_vittima}

   **Patrimoniale** (importo = € {importo_o_percentuale}):
   - Danno emergente: il valore indicato
   - Lucro cessante: calcola in base alla durata della privazione
   - Chiama `interessi_legali` sulla somma dalla data dell'evento

   **Morale/esistenziale**:
   - Chiama `danno_non_patrimoniale` come punto di partenza
   - Applica la personalizzazione per gravità e impatto sulla vita di relazione

2. PERSONALIZZAZIONE
   Valuta i criteri di personalizzazione (Cass. SS.UU. 26972/2008):
   - Entità della sofferenza soggettiva
   - Incidenza sulla vita di relazione
   - Specificità del caso concreto
   Indica una percentuale di personalizzazione motivata.

3. ATTUALIZZAZIONE
   Chiama `rivalutazione_monetaria` dalla data dell'evento a oggi.
   Chiama `interessi_legali` sulla somma rivalutata.

FORMATO OUTPUT:
## Quantificazione Danno ({tipo_danno})

| Componente | Importo |
|------------|---------|
| Danno base (tabellare/documentale) | € ... |
| Personalizzazione (±...%) | € ... |
| Subtotale | € ... |
| Rivalutazione ISTAT | € ... |
| Interessi legali | € ... |
| **TOTALE** | **€ ...** |

## Motivazione
Spiega i criteri di personalizzazione adottati e la giurisprudenza di riferimento.

## Avvertenze
- Quantificazione indicativa basata sulle tabelle vigenti.
- La prova del danno patrimoniale richiede documentazione specifica.
- Per il danno biologico è necessaria perizia medico-legale.
"""


@mcp.prompt(
    description="Calcolo parcella avvocato per attività civile, penale o stragiudiziale"
)
def calcolo_parcella(
    tipo_attivita: str, valore_causa: float
) -> str:
    tool_map = {
        "civile": "parcella_avvocato_civile",
        "penale": "parcella_avvocato_penale",
        "stragiudiziale": "parcella_stragiudiziale",
    }
    tool_name = tool_map.get(tipo_attivita, "parcella_avvocato_civile")

    return f"""Calcola la parcella per questa prestazione professionale.

DATI:
- Tipo attività: {tipo_attivita} (civile / penale / stragiudiziale)
- Valore causa/pratica: € {valore_causa:,.2f}

PROCEDURA:

1. CALCOLO COMPENSO
   Chiama `{tool_name}` con valore={valore_causa}.

   Per attività **civile** (D.M. 55/2014 e succ. mod.):
   - Fase di studio
   - Fase introduttiva
   - Fase istruttoria / trattazione
   - Fase decisoria
   Ogni fase ha parametri: minimo, medio, massimo.

   Per attività **penale** (D.M. 55/2014):
   - Fase di studio
   - Fase introduttiva
   - Fase istruttoria
   - Fase dibattimentale
   - Fase decisoria

   Per attività **stragiudiziale**:
   - Assistenza/consulenza
   - Redazione atti e diffide
   - Negoziazione

2. NOTA SPESE
   Chiama `nota_spese` per generare il prospetto completo con:
   - Compenso per ciascuna fase
   - Spese generali (15%)
   - CPA (4%)
   - IVA (22%)
   - Contributo unificato e bolli (se giudiziale)

FORMATO OUTPUT:
## Parcella — Attività {tipo_attivita.title()}

### Compenso (D.M. 55/2014)
| Fase | Minimo | Medio | Massimo |
|------|--------|-------|---------|
| ... | € ... | € ... | € ... |
| **Totale compenso** | **€ ...** | **€ ...** | **€ ...** |

### Nota Spese (su compenso medio)
| Voce | Importo |
|------|---------|
| Compenso | € ... |
| Spese generali (15%) | € ... |
| CPA (4%) | € ... |
| Imponibile IVA | € ... |
| IVA (22%) | € ... |
| **Totale parcella** | **€ ...** |

### Note
- I compensi si riferiscono al D.M. 55/2014 come aggiornato dal D.M. 147/2022.
- Lo scaglione applicabile è quello corrispondente al valore di € {valore_causa:,.2f}.
- Il giudice può liquidare compensi anche oltre i massimi in casi di particolare complessità.
"""


@mcp.prompt(
    description="Verifica prescrizione di un diritto civile o di un reato penale"
)
def verifica_prescrizione(
    tipo: str, descrizione_fatto: str, data_fatto: str
) -> str:
    tool_name = "prescrizione_diritti" if tipo == "civile" else "prescrizione_reato"
    return f"""Verifica la prescrizione per questo fatto giuridico.

DATI:
- Tipo: {tipo} (civile / penale)
- Descrizione fatto: {descrizione_fatto}
- Data del fatto: {data_fatto}

PROCEDURA:

1. CALCOLO PRESCRIZIONE
   Chiama `{tool_name}` con i dati forniti.

   **Se civile** (`prescrizione_diritti`):
   - Identifica il tipo di diritto (contrattuale, extracontrattuale, reale, etc.)
   - Termine ordinario: 10 anni (art. 2946 c.c.)
   - Termini brevi: 5 anni (risarcimento danni, art. 2947 c.c.),
     2 anni (assicurazione, art. 2952 c.c.), 1 anno (trasporti, spedizioni)
   - Verifica cause di sospensione (art. 2941-2942 c.c.)
   - Verifica cause di interruzione (art. 2943 c.c.): messa in mora, ricorso,
     riconoscimento del debito

   **Se penale** (`prescrizione_reato`):
   - Identifica il reato (titolo e articolo c.p.)
   - Calcola il termine base = massimo edittale della pena (min. 6 anni delitto, 4 anni contravvenzione)
   - Verifica cause di sospensione (art. 159 c.p.)
   - Verifica cause di interruzione (art. 160 c.p.) e termine massimo con interruzioni

2. ANALISI TEMPORALE
   - Data decorrenza: {data_fatto}
   - Data odierna: calcola il tempo trascorso
   - Data prescrizione: indica la scadenza esatta
   - Stato: PRESCRITTA / NON PRESCRITTA / IN SCADENZA (ultimi 6 mesi)

FORMATO OUTPUT:
## Verifica Prescrizione — {tipo.title()}

| Elemento | Dettaglio |
|----------|----------|
| Fatto | {descrizione_fatto} |
| Data fatto | {data_fatto} |
| Tipo diritto/reato | ... |
| Norma applicabile | art. ... |
| Termine prescrizione | ... anni |
| Data decorrenza | {data_fatto} |
| Data scadenza prescrizione | GG/MM/AAAA |
| Tempo trascorso | ... anni, ... mesi, ... giorni |
| Tempo residuo | ... anni, ... mesi, ... giorni |
| **STATO** | **PRESCRITTA / NON PRESCRITTA / IN SCADENZA** |

## Cause di Sospensione/Interruzione
Elenca eventuali cause note che potrebbero aver modificato il decorso.

## Avvertenze
- La prescrizione può essere interrotta o sospesa da atti non noti al momento dell'analisi.
- Per la prescrizione penale, la riforma Bonafede (L. 3/2019) e la riforma Cartabia
  (D.Lgs. 150/2022) hanno modificato il regime — verificare la data del fatto
  per applicare la disciplina corretta.
- In ambito civile, il decorso della prescrizione può essere interrotto con atto
  stragiudiziale (raccomandata/PEC di messa in mora).
"""


# ---------------------------------------------------------------------------
# Prompts per ricerca normativa
# ---------------------------------------------------------------------------


@mcp.prompt(
    description="Ricerca normativa completa su un tema giuridico: norme applicabili, gerarchia delle fonti e coordinamento"
)
def ricerca_normativa(tema: str, area_diritto: str) -> str:
    return f"""Esegui una ricerca normativa completa sul tema indicato.

TEMA: {tema}
AREA: {area_diritto} (civile / penale / amministrativo / lavoro / tributario / privacy / commerciale)

PROCEDURA:

1. INDIVIDUAZIONE FONTI PRIMARIE
   Identifica le norme principali che disciplinano il tema.
   Per ciascuna norma, chiama `cite_law` per recuperare il testo vigente.
   Ordina per gerarchia delle fonti:
   - Costituzione (artt. rilevanti)
   - Regolamenti UE (direttamente applicabili)
   - Direttive UE (recepite con D.Lgs.)
   - Leggi ordinarie / D.Lgs. / D.L.
   - Regolamenti ministeriali / D.M.
   - Circolari e prassi amministrativa

2. NORME COLLEGATE E COORDINAMENTO
   Per ogni norma primaria, verifica:
   - Norme di attuazione e regolamenti
   - Modifiche successive (novelle, correttivi)
   - Norme abrogate espressamente o implicitamente
   - Disposizioni transitorie
   Usa `cite_law` per ciascun articolo rilevante.

3. GIURISPRUDENZA E DOTTRINA
   Per le norme chiave, chiama `cite_law` con `include_annotations=true`
   per recuperare da Brocardi:
   - Massime di Cassazione e Corte Costituzionale
   - Orientamenti consolidati vs. questioni aperte
   - Posizioni dottrinali prevalenti

   Per trovare giurisprudenza recente (2020+), chiama
   `cerca_giurisprudenza(query="\"art. ... codice\"", modalita="esplora")`
   per la distribuzione, poi con filtri per le decisioni più rilevanti.

4. QUADRO SANZIONATORIO
   Se pertinente, identifica:
   - Sanzioni penali (contravvenzioni, delitti)
   - Sanzioni amministrative (pecuniarie, interdittive)
   - Responsabilità civile (risarcimento danni)
   - Sanzioni disciplinari (ordini professionali, PA)

FORMATO OUTPUT:

## Ricerca Normativa: {tema}

### 1. Fonti Primarie
| Fonte | Norma | Oggetto |
|-------|-------|---------|
| Costituzione | art. ... | ... |
| Reg. UE | ... | ... |
| Legge | ... | ... |

### 2. Articoli Chiave
Per ciascun articolo: testo (da cite_law), commento sintetico, nessi con altri articoli.

### 3. Evoluzione Normativa
Timeline delle modifiche rilevanti.

### 4. Orientamenti Interpretativi
Giurisprudenza consolidata e questioni aperte.

### 5. Quadro Sanzionatorio
Tabella sanzioni applicabili.

5. FONTI AUTORITÀ DI VIGILANZA (se area finanziaria/mercati)
   Se il tema riguarda mercati finanziari, intermediari, emittenti, OPA, crowdfunding
   o cripto-attività, chiama `cerca_delibere_consob(query="{tema}")` per recuperare
   le delibere e i provvedimenti CONSOB rilevanti.
   Per le delibere più significative, chiama `leggi_delibera_consob(numero)` per il testo.

REGOLE:
- OGNI norma citata DEVE essere verificata con cite_law — mai citare a memoria.
- Indicare espressamente se una norma è stata modificata o abrogata.
- Segnalare norme in corso di modifica o proposte di riforma pendenti.
- Per materie finanziarie, includere sempre i provvedimenti delle autorità di vigilanza (CONSOB, Banca d'Italia).
"""


@mcp.prompt(
    description="Analisi approfondita di un singolo articolo di legge: testo, ratio, giurisprudenza e collegamenti"
)
def analisi_articolo(riferimento_norma: str) -> str:
    return f"""Esegui un'analisi approfondita dell'articolo di legge indicato.

NORMA: {riferimento_norma}
(esempi di formato: "art. 13 GDPR", "art. 2043 c.c.", "art. 6 D.Lgs. 231/2001")

PROCEDURA:

1. TESTO VIGENTE
   Chiama `cite_law("{riferimento_norma}")` per recuperare il testo ufficiale aggiornato.
   Se la risposta indica che il testo è stato modificato, recupera anche la versione precedente.

2. ANNOTAZIONI E GIURISPRUDENZA
   Chiama `cerca_brocardi("{riferimento_norma}")` per recuperare da Brocardi:
   - Ratio legis (scopo della norma)
   - Spiegazione dottrinale
   - Massime giurisprudenziali rilevanti
   - Casistica applicativa

3. NORME COLLEGATE
   Identifica e recupera con `cite_law`:
   - Articoli precedenti e successivi nello stesso testo normativo (contesto sistematico)
   - Norme richiamate espressamente nel testo
   - Norme che richiamano questo articolo
   - Disposizioni di attuazione o regolamentari

4. EVOLUZIONE STORICA
   Se disponibile dalle annotazioni, riporta:
   - Versioni precedenti del testo
   - Leggi di modifica con date
   - Motivazioni delle modifiche (relazioni illustrative)

FORMATO OUTPUT:

## Analisi: {riferimento_norma}

### Testo Vigente
> [testo completo dell'articolo da cite_law]

### Ratio Legis
Spiegazione dello scopo e della funzione della norma nell'ordinamento.

### Elementi Costitutivi
Scomposizione della norma in:
- Presupposti (fattispecie astratta)
- Effetti giuridici (conseguenze)
- Soggetti destinatari
- Ambito di applicazione

### Giurisprudenza di Riferimento
| Pronuncia | Principio | Rilevanza |
|-----------|-----------|-----------|
| Cass. n. .../... | ... | ... |

### Norme Collegate
| Norma | Relazione | Contenuto |
|-------|-----------|-----------|
| art. ... | richiamo espresso / sistematico | ... |

### Note Operative
Indicazioni pratiche per l'applicazione della norma.

REGOLE:
- Il testo dell'articolo DEVE provenire da cite_law, non dalla memoria.
- Se Brocardi non ha annotazioni per questa norma, indicarlo espressamente.
- Distinguere tra interpretazione consolidata e orientamenti minoritari.
"""


@mcp.prompt(
    description="Confronto tra due o più norme: differenze, sovrapposizioni, prevalenza e coordinamento"
)
def confronto_norme(norma_1: str, norma_2: str, contesto: str = "") -> str:
    ctx = f"\nCONTESTO: {contesto}" if contesto else ""
    return f"""Confronta le seguenti disposizioni normative evidenziando differenze, sovrapposizioni e criteri di coordinamento.

NORMA 1: {norma_1}
NORMA 2: {norma_2}{ctx}

PROCEDURA:

1. RECUPERO TESTI
   Chiama `cite_law("{norma_1}")` e `cite_law("{norma_2}")` per ottenere i testi vigenti.
   Per entrambe, chiama anche con `include_annotations=true` per giurisprudenza e dottrina.

2. ANALISI COMPARATIVA
   Confronta le due norme su:
   - **Ambito oggettivo**: quale materia disciplinano
   - **Ambito soggettivo**: a chi si applicano
   - **Presupposti**: quando si attivano
   - **Effetti**: quali conseguenze producono
   - **Sanzioni**: apparato sanzionatorio

3. RAPPORTO TRA LE NORME
   Determina la relazione:
   - **Specialità** (art. 15 c.p. / lex specialis): una è speciale rispetto all'altra?
   - **Successione temporale** (lex posterior): una ha abrogato l'altra?
   - **Gerarchia**: una prevale per rango (Costituzione > legge > regolamento)?
   - **Concorso**: si applicano entrambe contemporaneamente?
   - **Complementarietà**: disciplinano aspetti diversi della stessa materia?

4. GIURISPRUDENZA SUL COORDINAMENTO
   Dalle annotazioni, individua pronunce che hanno affrontato il rapporto tra le due norme.

FORMATO OUTPUT:

## Confronto: {norma_1} vs. {norma_2}

### Testi a Confronto
| Elemento | {norma_1} | {norma_2} |
|----------|-----------|-----------|
| Fonte | ... | ... |
| Ambito oggettivo | ... | ... |
| Ambito soggettivo | ... | ... |
| Presupposti | ... | ... |
| Effetti | ... | ... |
| Sanzioni | ... | ... |

### Rapporto tra le Norme
Analisi del criterio di prevalenza applicabile.

### Aree di Sovrapposizione
Casi in cui entrambe le norme sono potenzialmente applicabili e come si coordinano.

### Orientamento Giurisprudenziale
Come la giurisprudenza ha risolto i conflitti tra queste norme.

### Conclusioni Operative
Indicazione pratica su quale norma applicare e in quali circostanze.

REGOLE:
- Entrambi i testi DEVONO provenire da cite_law.
- Non dare per scontata la prevalenza di una norma — argomentare il criterio.
- Se il rapporto è controverso, esporre le diverse tesi.
"""


@mcp.prompt(
    description="Mappatura del quadro normativo completo per un settore o attività: tutte le fonti applicabili organizzate per livello"
)
def mappatura_normativa(settore: str, attivita_specifica: str = "") -> str:
    att = f"\nATTIVITÀ SPECIFICA: {attivita_specifica}" if attivita_specifica else ""
    return f"""Costruisci la mappa normativa completa applicabile a questo settore/attività.

SETTORE: {settore}{att}

PROCEDURA:

1. FONTI COSTITUZIONALI
   Identifica gli articoli della Costituzione rilevanti.
   Chiama `cite_law` per ciascuno (es. art. 41, 42, 117 Cost.).

2. FONTI EUROPEE
   Identifica regolamenti e direttive UE applicabili.
   Per i regolamenti: chiama `cite_law` per gli articoli chiave.
   Per le direttive: identifica il D.Lgs. di recepimento italiano.

3. FONTI LEGISLATIVE NAZIONALI
   Mappa:
   - Codici applicabili (civile, penale, procedura, settoriali)
   - Testi unici / Codici di settore
   - Leggi ordinarie e decreti legislativi
   - Decreti legge convertiti
   Per ciascuna: chiama `cite_law` per gli articoli fondamentali.

4. FONTI REGOLAMENTARI E SOFT LAW
   - Decreti ministeriali (D.M.)
   - Regolamenti di autorità indipendenti (Garante Privacy, AGCM, CONSOB, ecc.)
   - Linee guida e provvedimenti generali
   - Standard tecnici (ISO, UNI) se vincolanti
   Per settori finanziari/mercati: chiama `cerca_delibere_consob` per delibere CONSOB.
   Per le delibere chiave, leggi il testo con `leggi_delibera_consob(numero)`.

5. OBBLIGHI E ADEMPIMENTI
   Per ogni fonte, estrai gli obblighi concreti:
   - Adempimenti documentali
   - Obblighi di comunicazione / notifica
   - Registri e tenuta documentale
   - Formazione e designazioni
   - Termini e scadenze

FORMATO OUTPUT:

## Mappa Normativa: {settore}

### Livello 1 — Costituzione
| Articolo | Principio | Rilevanza |
|----------|-----------|-----------|
| art. ... | ... | ... |

### Livello 2 — Diritto UE
| Fonte | Tipo | Articoli chiave | Recepimento IT |
|-------|------|-----------------|----------------|
| ... | Reg./Dir. | artt. ... | D.Lgs. .../... |

### Livello 3 — Legislazione Nazionale
| Fonte | Materia | Articoli chiave |
|-------|---------|-----------------|
| ... | ... | artt. ... |

### Livello 4 — Fonti Secondarie
| Fonte | Autorità | Oggetto |
|-------|----------|---------|
| ... | ... | ... |

### Matrice Adempimenti
| Obbligo | Fonte | Soggetto | Termine | Sanzione |
|---------|-------|----------|---------|----------|
| ... | art. ... | ... | ... | ... |

### Checklist Operativa
Elenco ordinato per priorità degli adempimenti da verificare.

REGOLE:
- Usare `cite_law` per TUTTI gli articoli citati nella mappa.
- Indicare la data di entrata in vigore di ciascuna fonte.
- Segnalare norme in fase di modifica o revisione.
- Per settori regolati (privacy, bancario, sanitario), includere sempre le fonti dell'autorità di vigilanza.
"""


@mcp.prompt(
    description="Analisi giurisprudenziale strutturata su un tema: ricerca su Italgiure, lettura decisioni chiave e sintesi orientamenti"
)
def analisi_giurisprudenziale(tema: str, archivio: str = "tutti") -> str:
    return f"""Esegui un'analisi giurisprudenziale strutturata sul tema indicato.

TEMA: {tema}
ARCHIVIO: {archivio} (civile / penale / tutti)

PROCEDURA:

### Fase 1 — Esplorazione distribuzione
Chiama `cerca_giurisprudenza(query="\"{tema}\"", archivio="{archivio}", modalita="esplora")`
per vedere la distribuzione per materia, sezione, anno e tipo provvedimento.
Usa virgolette per frasi esatte.

Se il tema riguarda una norma specifica (es. "art. 2043 c.c."), chiama prima
`giurisprudenza_su_norma(riferimento="art. ...")` per trovare le decisioni che la citano.

### Fase 1b — Ricerca con filtri
In base ai facets, chiama `cerca_giurisprudenza` con filtri mirati (materia, sezione,
tipo_provvedimento="sentenza", max_risultati=10).
Per cercare solo nel dispositivo: `campo="dispositivo"`.

### Fase 2 — Approfondimento decisioni chiave
Seleziona le 2-3 decisioni più significative (privilegia Sezioni Unite se presenti).
Per ciascuna, chiama `leggi_sentenza(numero, anno)` per leggere il testo completo.

IMPORTANTE: usa `leggi_sentenza` — NON fare web search per sentenze già identificate.

### Fase 3 — Annotazioni Brocardi (se norma specifica)
Se il tema ruota attorno a un articolo specifico, chiama `cerca_brocardi(reference)`
per ottenere ratio legis, spiegazione dottrinale e massime strutturate.
I riferimenti Cassazione nelle massime possono essere letti con `leggi_sentenza`.

### Fase 4 — Fondamento normativo
Per le norme citate nelle decisioni lette, chiama `cite_law(reference)` per verificare
il testo vigente dalla fonte ufficiale (Normattiva/EUR-Lex).

### Fase 5 — Sintesi strutturata
Produci una sintesi che includa:
1. **Orientamento prevalente**: principio di diritto che emerge dalla giurisprudenza
2. **Evoluzione**: come si è evoluto l'orientamento nel tempo
3. **Contrasti**: eventuali divergenze tra sezioni o indirizzi minoritari
4. **Sezioni Unite**: se le SU si sono pronunciate, riporta il principio di diritto
5. **Norme di riferimento**: disposizioni normative rilevanti
6. **Decisioni citate**: elenco con estremi (Cass. civ./pen., sez., n./anno)

REGOLE:
- Non citare mai numeri di sentenza a memoria — usa esclusivamente i risultati dei tool.
- Ogni affermazione deve essere supportata da una sentenza o norma verificata.
- Se una sentenza non è trovata su Italgiure, indicarlo esplicitamente.
"""


# ---------------------------------------------------------------------------
# Prompt per CONSOB e mercati finanziari
# ---------------------------------------------------------------------------


@mcp.prompt(
    description="Ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, regolamenti mercati finanziari"
)
def analisi_delibere_consob(tema: str, tipologia: str = "", argomento: str = "") -> str:
    filtri_extra = ""
    if tipologia:
        filtri_extra += f'\n- Tipologia: {tipologia} (delibere / comunicazioni / provvedimenti_urgenti / opa)'
    if argomento:
        filtri_extra += f'\n- Argomento: {argomento} (abusi_di_mercato / intermediari / emittenti / mercati / cripto_attivita / crowdfunding)'

    return f"""Esegui una ricerca e analisi delle delibere CONSOB sul tema indicato.

TEMA: {tema}{filtri_extra}

PROCEDURA:

### Fase 1 — Ricerca delibere
Chiama `cerca_delibere_consob(query="{tema}"{', tipologia="' + tipologia + '"' if tipologia else ''}{', argomento="' + argomento + '"' if argomento else ''})` per trovare
le delibere e i provvedimenti CONSOB pertinenti.

Se il tema è ampio, esegui più ricerche con query diverse per coprire i diversi aspetti.

### Fase 2 — Lettura delibere chiave
Seleziona le 2-3 delibere più significative dalla ricerca.
Per ciascuna, chiama `leggi_delibera_consob(numero)` per leggere il testo completo.

Privilegia:
- Delibere recenti (ultimo biennio)
- Delibere che stabiliscono principi generali o sanzioni rilevanti
- Provvedimenti che riguardano fattispecie analoghe al tema richiesto

### Fase 3 — Quadro normativo di riferimento
Identifica le norme richiamate nelle delibere lette.
Per ciascuna norma chiave, chiama `cite_law(reference)` per il testo vigente.

Fonti tipiche:
- TUF (D.Lgs. 58/1998) — Testo Unico della Finanza
- Regolamento Emittenti (Reg. CONSOB 11971/1999)
- Regolamento Intermediari (Reg. CONSOB 20307/2018)
- Regolamento Mercati (Reg. CONSOB 20249/2017)
- MAR (Reg. UE 596/2014) — abusi di mercato
- MiFID II (Dir. 2014/65/UE) / MiFIR (Reg. UE 600/2014)
- Reg. UE 2020/1503 — crowdfunding
- MiCA (Reg. UE 2023/1114) — cripto-attività

### Fase 4 — Giurisprudenza correlata (se pertinente)
Se le delibere citano pronunce giurisdizionali o se il tema ha risvolti contenziosi,
chiama `cerca_giurisprudenza(query="{tema}")` per verificare eventuali sentenze.

### Fase 5 — Sintesi strutturata

## Analisi Delibere CONSOB: {tema}

### 1. Quadro Regolatorio
Norme primarie e secondarie applicabili (testo da cite_law).

### 2. Orientamento CONSOB
| Delibera | Data | Principio / Esito |
|----------|------|--------------------|
| n. ... | GG/MM/AAAA | ... |

### 3. Sanzioni e Misure
Tabella delle sanzioni comminate o delle misure adottate nei provvedimenti esaminati.

### 4. Principi Consolidati
Sintesi dei principi ricorrenti nelle delibere CONSOB sul tema.

### 5. Indicazioni Operative
Raccomandazioni pratiche derivanti dall'analisi.

REGOLE:
- Usare `cerca_delibere_consob` e `leggi_delibera_consob` per i provvedimenti CONSOB.
- Usare `cite_law` per TUTTE le norme citate — mai citare a memoria.
- Indicare espressamente il numero e la data di ogni delibera citata.
- Segnalare se l'orientamento è consolidato o in evoluzione.
"""


@mcp.prompt(
    description="Ultime novità CONSOB: delibere recenti per tipologia o argomento con sintesi degli orientamenti"
)
def novita_consob(tipologia: str = "", argomento: str = "") -> str:
    filtri = ""
    if tipologia:
        filtri += f', tipologia="{tipologia}"'
    if argomento:
        filtri += f', argomento="{argomento}"'

    return f"""Fornisci un riepilogo delle ultime delibere e provvedimenti CONSOB.

PROCEDURA:

1. ULTIME DELIBERE
   Chiama `ultime_delibere_consob({filtri.lstrip(', ') if filtri else ''})` per ottenere
   le delibere più recenti pubblicate dalla CONSOB.

2. APPROFONDIMENTO
   Per le 2-3 delibere più rilevanti, chiama `leggi_delibera_consob(numero)` per
   leggere il testo completo e comprendere il contenuto.

3. QUADRO NORMATIVO
   Per le norme richiamate nelle delibere, chiama `cite_law(reference)` per il testo vigente.

FORMATO OUTPUT:

## Ultime Delibere CONSOB

### Panoramica
Riepilogo sintetico delle tendenze emergenti dai provvedimenti recenti.

### Delibere Principali
Per ciascuna delibera letta:

#### Delibera n. ... del GG/MM/AAAA
- **Oggetto**: ...
- **Norme di riferimento**: ...
- **Decisione/Sanzione**: ...
- **Rilevanza pratica**: ...

### Tendenze e Indicazioni
Sintesi degli orientamenti che emergono dalle delibere più recenti.

REGOLE:
- Usare esclusivamente i tool CONSOB per i provvedimenti — mai citare a memoria.
- Per le norme, usare sempre cite_law.
- Indicare data e numero di ogni delibera.
"""


# ---------------------------------------------------------------------------
# Prompt per compliance GDPR/Privacy
# ---------------------------------------------------------------------------


@mcp.prompt(
    description="Workflow completo compliance privacy GDPR: analisi base giuridica, DPIA, registro, informativa e DPA"
)
def compliance_privacy(
    titolare: str, tipo_trattamento: str, contesto: str
) -> str:
    return f"""Esegui un assessment di compliance GDPR completo per il trattamento indicato.

DATI:
- Titolare: {titolare}
- Tipo di trattamento: {tipo_trattamento}
- Contesto: {contesto} (B2C / B2B / dipendenti / pubblica_amministrazione / sanita / profilazione)

PROCEDURA (segui nell'ordine):

1. ANALISI BASE GIURIDICA
   Chiama `analisi_base_giuridica` con tipo_trattamento="{tipo_trattamento}", contesto="{contesto}".
   Identifica la base giuridica appropriata ex art. 6 GDPR.
   Se il trattamento coinvolge dati particolari (art. 9), attiva il flag dati_particolari=true.
   Annota la base consigliata per i passi successivi.

2. VERIFICA NECESSITÀ DPIA
   Chiama `verifica_necessita_dpia` con i criteri applicabili al trattamento.
   Valuta: profilazione, dati sensibili, monitoraggio sistematico, larga scala,
   soggetti vulnerabili, nuove tecnologie, scoring, incrocio dataset.
   Se il risultato è dpia_necessaria=true, procedere al passo 2b.

   2b. DPIA (se necessaria)
   Chiama `genera_dpia` con i rischi identificati e le misure di mitigazione previste.
   Documenta la matrice dei rischi e il rischio residuo.

3. REGISTRO TRATTAMENTI
   Chiama `genera_registro_trattamenti` per creare la scheda del trattamento ai sensi dell'art. 30.
   Usa la base giuridica identificata al passo 1.

4. INFORMATIVA PRIVACY
   Chiama `genera_informativa_privacy` per generare l'informativa ai sensi dell'art. 13 GDPR.
   Includi tutte le finalità, basi giuridiche, categorie di dati e destinatari.

5. DPA (se presenti responsabili del trattamento)
   Se il trattamento coinvolge responsabili esterni (fornitori IT, cloud, commercialista, ecc.),
   chiama `genera_dpa` per generare il contratto ex art. 28 GDPR.

FORMATO OUTPUT:

## Assessment Compliance GDPR — {titolare}

### 1. Base Giuridica
| Elemento | Dettaglio |
|----------|----------|
| Base consigliata | ... |
| Articolo | ... |
| Motivazione | ... |

### 2. DPIA
| Criterio | Soddisfatto | Descrizione |
|----------|-------------|-------------|
| ... | Sì/No | ... |
| **DPIA necessaria** | **Sì/No** | ... |

### 3. Registro Trattamenti
Scheda art. 30 generata con tutti i campi obbligatori.

### 4. Informativa Privacy
Testo completo dell'informativa art. 13 GDPR pronto per l'uso.

### 5. DPA
Contratto art. 28 GDPR (se applicabile).

### Checklist Compliance
- [ ] Base giuridica identificata e documentata
- [ ] DPIA eseguita (se necessaria)
- [ ] Registro trattamenti aggiornato
- [ ] Informativa privacy redatta e pubblicata
- [ ] DPA stipulati con tutti i responsabili
- [ ] Misure di sicurezza adeguate (art. 32 GDPR)
- [ ] Procedura data breach predisposta (artt. 33-34 GDPR)

AVVERTENZE:
- Il presente assessment è uno strumento di supporto e non sostituisce la consulenza legale specializzata.
- Verificare sempre la normativa nazionale integrativa (D.Lgs. 196/2003 come modificato dal D.Lgs. 101/2018).
- Per trattamenti su larga scala o ad alto rischio, consultare il DPO e valutare una consultazione preventiva (art. 36 GDPR).
"""
