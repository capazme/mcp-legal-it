# mcp-legal-it — Tool Inventory (audit)

**Totals:** 30 modules · 214 tools · 23 prompts · 15 resources

> This inventory supersedes the stale counts in `CLAUDE.md`, which still report
> 177 tools / 19 prompts / 19 skills / 13–15 resources. The authoritative figure is
> **214 tools across 30 modules** (see per-module breakdown below). Update `CLAUDE.md`
> to match. Raw machine-readable catalog: [`inventory.json`](./inventory.json).

## Tools per module

| Module | Tools |
| --- | ---: |
| `atti_giudiziari.py` | 23 |
| `cerdef.py` | 3 |
| `cgue.py` | 4 |
| `consob.py` | 3 |
| `corte_cost.py` | 4 |
| `crisi_impresa.py` | 4 |
| `dichiarazione_redditi.py` | 16 |
| `diritto_lavoro.py` | 6 |
| `diritto_penale.py` | 5 |
| `diritto_societario.py` | 4 |
| `eu_implementation.py` | 3 |
| `fatturazione_avvocati.py` | 12 |
| `gazzetta.py` | 5 |
| `giurisprudenza_unificata.py` | 1 |
| `giustizia_amm.py` | 4 |
| `gpdp.py` | 3 |
| `investimenti.py` | 5 |
| `italgiure.py` | 5 |
| `legal_citations.py` | 8 |
| `modelli_atti.py` | 3 |
| `orientamento.py` | 3 |
| `parcelle_professionisti.py` | 11 |
| `privacy_gdpr.py` | 12 |
| `procedura_civile.py` | 3 |
| `proprieta_successioni.py` | 12 |
| `risarcimento_danni.py` | 7 |
| `rivalutazioni_istat.py` | 12 |
| `scadenze_termini.py` | 11 |
| `tassi_interessi.py` | 10 |
| `varie.py` | 12 |
| **Total** | **214** |

---

## `atti_giudiziari.py` (23 tools)

| name | signature | purpose |
| --- | --- | --- |
| `contributo_unificato` | `contributo_unificato(valore_causa: float, tipo_procedimento: str = "cognizione", grado: str = "primo") -> dict` | Calcola il Contributo Unificato per valore della causa, tipo di procedimento e grado (DPR 115/2002). |
| `diritti_copia` | `diritti_copia(n_pagine: int, tipo: str = "semplice", formato: str = "digitale", urgente: bool = False) -> dict` | Calcola i diritti di copia per atti giudiziari in formato cartaceo e digitale PCT. |
| `pignoramento_stipendio` | `pignoramento_stipendio(stipendio_netto_mensile: float, tipo_credito: str = "ordinario") -> dict` | Calcola le quote pignorabili dello stipendio o della pensione ex art. 545 c.p.c. |
| `sollecito_pagamento` | `sollecito_pagamento(creditore: str, debitore: str, importo: float, data_scadenza: str, data_sollecito: str, tasso_mora: float \| None = None) -> dict` | Genera bozza di lettera di sollecito pagamento con calcolo degli interessi di mora. |
| `decreto_ingiuntivo` | `decreto_ingiuntivo(creditore: str, debitore: str, importo: float, tipo_credito: str = "ordinario", provvisoria_esecuzione: bool = False) -> dict` | Genera bozza di ricorso per decreto ingiuntivo con calcolo della competenza per valore e CU. |
| `calcolo_hash` | `calcolo_hash(testo: str) -> dict` | Calcola l'impronta hash SHA-256 di un testo per il deposito telematico PCT. |
| `tassazione_atti` | `tassazione_atti(tipo_atto: str, valore: float, prima_casa: bool = False) -> dict` | Calcola l'imposta di registro dovuta su atti giudiziari (DPR 131/1986). |
| `copie_processo_tributario` | `copie_processo_tributario(n_pagine: int, tipo: str = "semplice", urgente: bool = False) -> dict` | Calcola i diritti di copia specifici per il processo tributario. |
| `note_iscrizione_ruolo` | `note_iscrizione_ruolo(tipo_procedimento: str, valore_causa: float \| None = None) -> dict` | Genera note per l'iscrizione a ruolo con codici oggetto suggeriti e CU calcolato. |
| `codici_iscrizione_ruolo` | `codici_iscrizione_ruolo(materia: str) -> dict` | Ricerca il codice oggetto per l'iscrizione a ruolo di cause civili. |
| `fascicolo_di_parte` | `fascicolo_di_parte(avvocato: str, parte: str, controparte: str, tribunale: str, rg_numero: str \| None = None) -> dict` | Genera bozza di frontespizio per il fascicolo di parte (art. 165 c.p.c.). |
| `procura_alle_liti` | `procura_alle_liti(parte: str, avvocato: str, cf_avvocato: str, foro: str, oggetto_causa: str, tipo: str = "generale") -> dict` | Genera bozza di procura alle liti ex art. 83 c.p.c. |
| `attestazione_conformita` | `attestazione_conformita(avvocato: str, tipo_documento: str, estremi_originale: str, modalita: str = "estratto") -> dict` | Genera bozza di attestazione di conformita per il deposito telematico PCT. |
| `relata_notifica_pec` | `relata_notifica_pec(avvocato: str, destinatario: str, pec_destinatario: str, atto_notificato: str, data_invio: str) -> dict` | Genera bozza di relata di notificazione a mezzo PEC ex L. 53/1994. |
| `indice_documenti` | `indice_documenti(documenti: list[dict]) -> dict` | Genera bozza di indice numerato dei documenti per deposito telematico PCT. |
| `note_trattazione_scritta` | `note_trattazione_scritta(avvocato: str, parte: str, tribunale: str, rg_numero: str, giudice: str, conclusioni: str) -> dict` | Genera bozza di note di trattazione scritta in sostituzione dell'udienza (art. 127-ter c.p.c.). |
| `sfratto_morosita` | `sfratto_morosita(locatore: str, conduttore: str, immobile: str, canone_mensile: float, mensilita_insolute: int, data_contratto: str) -> dict` | Genera bozza di intimazione di sfratto per morosita con citazione per convalida. |
| `atto_di_precetto` | `atto_di_precetto(creditore: str, debitore: str, titolo_esecutivo: str, importo_capitale: float, interessi: float = 0, spese: float = 0) -> dict` | Genera bozza di atto di precetto con avvertimento ex art. 480 c.p.c. |
| `nota_precisazione_credito` | `nota_precisazione_credito(creditore: str, debitore: str, procedura_esecutiva: str, capitale: float, interessi: float, spese_legali: float, spese_esecuzione: float) -> dict` | Genera bozza di nota di precisazione del credito per procedure esecutive (art. 547 c.p.c.). |
| `dichiarazione_553_cpc` | `dichiarazione_553_cpc(terzo_pignorato: str, debitore: str, procedura: str, tipo_rapporto: str = "conto_corrente") -> dict` | Genera bozza di dichiarazione del terzo pignorato ex art. 547 c.p.c. |
| `testimonianza_scritta` | `testimonianza_scritta(teste: str, capitoli_prova: list[str]) -> dict` | Genera bozza del modulo per testimonianza scritta con capitoli e ammonizione (art. 257-bis c.p.c.). |
| `istanza_visibilita_fascicolo` | `istanza_visibilita_fascicolo(avvocato: str, parte: str, tribunale: str, rg_numero: str, motivo: str = "costituzione") -> dict` | Genera bozza di istanza di visibilita del fascicolo telematico per avvocato non costituito. |
| `cerca_ufficio_giudiziario` | `cerca_ufficio_giudiziario(comune: str, tipo: str = "tribunale") -> dict` | Cerca l'ufficio giudiziario territorialmente competente per un dato comune. |

## `cerdef.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_giurisprudenza_tributaria` | `async cerca_giurisprudenza_tributaria(query: str, tipo_provvedimento: str = "", ente: str = "", data_da: str = "", data_a: str = "", numero: str = "", criterio: str = "tutti", ordinamento: str = "rilevanza", max_risultati: int = 10) -> str` | Cerca sentenze e provvedimenti nella banca dati CeRDEF (MEF — def.finanze.it). |
| `cerdef_leggi_provvedimento` | `async cerdef_leggi_provvedimento(guid: str) -> str` | Legge il testo completo di un provvedimento CeRDEF tramite GUID. |
| `ultime_sentenze_tributarie` | `async ultime_sentenze_tributarie(ente: str = "", tipo_provvedimento: str = "", max_risultati: int = 10) -> str` | Ultime sentenze e provvedimenti tributari da CeRDEF (MEF), con filtro opzionale. |

## `cgue.py` (4 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_giurisprudenza_cgue` | `async cerca_giurisprudenza_cgue(query: str, corte: str = "", tipo_documento: str = "", anno_da: str = "", anno_a: str = "", materia: str = "", max_risultati: int = 10) -> str` | Cerca sentenze e decisioni della Corte di Giustizia UE (CGUE) e del Tribunale UE via SPARQL CELLAR. |
| `leggi_sentenza_cgue` | `async leggi_sentenza_cgue(cellar_uri: str) -> str` | Legge il testo completo di una sentenza CGUE tramite CELLAR URI. |
| `giurisprudenza_cgue_su_norma` | `async giurisprudenza_cgue_su_norma(riferimento: str, corte: str = "", anno_da: str = "", max_risultati: int = 10) -> str` | Cerca sentenze CGUE e Tribunale UE che interpretano una specifica norma del diritto UE. |
| `ultime_sentenze_cgue` | `async ultime_sentenze_cgue(corte: str = "", tipo_documento: str = "", materia: str = "", max_risultati: int = 10) -> str` | Ultime sentenze e decisioni pubblicate dalla Corte di Giustizia UE e dal Tribunale UE. |

## `consob.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_delibere_consob` | `async cerca_delibere_consob(query: str, tipologia: str = "", argomento: str = "", data_da: str = "", data_a: str = "", max_risultati: int = 20) -> str` | Cerca delibere e provvedimenti CONSOB nel bollettino ufficiale. |
| `leggi_delibera_consob` | `async leggi_delibera_consob(numero: str) -> str` | Legge il testo completo di una delibera CONSOB tramite numero. |
| `ultime_delibere_consob` | `async ultime_delibere_consob(tipologia: str = "", argomento: str = "", max_risultati: int = 10) -> str` | Ultime delibere e provvedimenti pubblicati dalla CONSOB, con filtro opzionale. |

## `corte_cost.py` (4 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_pronuncia_costituzionale` | `async cerca_pronuncia_costituzionale(query: str, tipo: str = "", anno_da: int = 0, anno_a: int = 0, max_risultati: int = 10) -> str` | Cerca sentenze e ordinanze della Corte Costituzionale per parole chiave. |
| `leggi_pronuncia_costituzionale` | `async leggi_pronuncia_costituzionale(numero: int, anno: int) -> str` | Legge il testo completo di una pronuncia della Corte Costituzionale. |
| `pronunce_cost_su_norma` | `async pronunce_cost_su_norma(riferimento: str, anno_da: int = 0, anno_a: int = 0, max_risultati: int = 10) -> str` | Cerca pronunce costituzionali che invocano una norma come parametro. |
| `ultime_pronunce_cost` | `async ultime_pronunce_cost(tipo: str = "", max_risultati: int = 10) -> str` | Ultime pronunce depositate dalla Corte Costituzionale (anno corrente). |

## `crisi_impresa.py` (4 tools)

| name | signature | purpose |
| --- | --- | --- |
| `test_crisi_impresa` | `test_crisi_impresa(dscr: float, giorni_ritardo_inps: int = 0, giorni_ritardo_ade: int = 0, esposizioni_scadute_pct: float = 0.0, debiti_vs_attivo_pct: float = 0.0) -> dict` | Verifica la presenza di indicatori di crisi d'impresa ai sensi dell'art. 3 CCII (D.Lgs. 14/2019). |
| `composizione_negoziata` | `composizione_negoziata(fatturato: float, attivo: float, dipendenti: int, debito_totale: float, tipo_impresa: str = "commerciale") -> dict` | Verifica l'ammissibilita alla composizione negoziata della crisi e valuta gli indicatori finanziari. |
| `concordato_preventivo` | `concordato_preventivo(creditori_privilegiati: float, creditori_chirografari: float, proposta_pct_chirografari: float, proposta_pct_privilegiati: float = 100.0, tipo: str = "continuita") -> dict` | Verifica l'ammissibilita e calcola i parametri del concordato preventivo (artt. 84-120 CCII). |
| `compenso_occ` | `compenso_occ(passivo: float, tipo: str = "ristrutturazione") -> dict` | Calcola il compenso dell'Organismo di Composizione della Crisi (OCC) ex D.M. 202/2014. |

## `dichiarazione_redditi.py` (16 tools)

| name | signature | purpose |
| --- | --- | --- |
| `calcolo_irpef` | `calcolo_irpef(reddito_complessivo: float, tipo_reddito: str = "dipendente", deduzioni: float = 0, detrazioni_extra: float = 0, anno_fiscale: int = 0) -> dict` | Calcola l'IRPEF con scaglioni, detrazioni da lavoro e addizionali regionali e comunali. |
| `regime_forfettario` | `regime_forfettario(ricavi: float, coefficiente_redditivita: float = 78, anni_attivita: int = 1, contributi_inps: float = 0) -> dict` | Simula il regime forfettario: imposta sostitutiva e confronto con l'IRPEF ordinaria. |
| `calcolo_tfr` | `calcolo_tfr(retribuzione_annua_lorda: float, anni_servizio: int, rivalutazione_media_pct: float = 2.0) -> dict` | Calcola il TFR (Trattamento di Fine Rapporto) lordo e netto con tassazione separata. |
| `ravvedimento_operoso` | `ravvedimento_operoso(imposta_dovuta: float, giorni_ritardo: int, tipo: str = "omesso_versamento") -> dict` | Calcola sanzioni ridotte e interessi legali per il ravvedimento operoso. |
| `assegno_unico` | `assegno_unico(isee: float, n_figli: int, eta_figli: list[int] \| None = None, genitore_solo: bool = False) -> dict` | Simula l'Assegno Unico Universale (AUU) per figli a carico. |
| `detrazione_figli` | `detrazione_figli(reddito_complessivo: float, n_figli_over21: int, n_figli_disabili: int = 0) -> dict` | Calcola la detrazione IRPEF per figli a carico con eta >=21 anni (art. 12 TUIR). |
| `detrazione_coniuge` | `detrazione_coniuge(reddito_complessivo: float) -> dict` | Calcola la detrazione IRPEF per coniuge a carico (art. 12 TUIR). |
| `detrazione_altri_familiari` | `detrazione_altri_familiari(reddito_complessivo: float, n_familiari: int) -> dict` | Calcola la detrazione IRPEF per altri familiari a carico (art. 12 TUIR). |
| `detrazione_lavoro_dipendente` | `detrazione_lavoro_dipendente(reddito_complessivo: float, giorni_lavoro: int = 365) -> dict` | Calcola la detrazione IRPEF per redditi di lavoro dipendente (art. 13 TUIR), proporzionata ai giorni lavorati. |
| `detrazione_pensione` | `detrazione_pensione(reddito_complessivo: float, giorni: int = 365) -> dict` | Calcola la detrazione IRPEF per redditi da pensione (art. 13 TUIR), proporzionata ai giorni. |
| `detrazione_assegno_coniuge` | `detrazione_assegno_coniuge(reddito_complessivo: float) -> dict` | Calcola la detrazione per assegno periodico percepito dal coniuge separato o divorziato. |
| `detrazione_canone_locazione` | `detrazione_canone_locazione(reddito_complessivo: float, tipo_contratto: str = "libero") -> dict` | Calcola la detrazione IRPEF per inquilini con contratto di locazione come abitazione principale. |
| `acconto_irpef` | `acconto_irpef(imposta_anno_precedente: float, metodo: str = "storico") -> dict` | Calcola l'acconto IRPEF (primo e secondo acconto) con importi e scadenze. |
| `acconto_cedolare_secca` | `acconto_cedolare_secca(imposta_anno_precedente: float) -> dict` | Calcola l'acconto cedolare secca (primo e secondo acconto) con importi e scadenze. |
| `rateizzazione_imposte` | `rateizzazione_imposte(importo_totale: float, n_rate: int, data_prima_rata: str, tasso_interesse_annuo: float = 2.0) -> dict` | Calcola il piano di rateizzazione delle imposte IRPEF e addizionali da dichiarazione. |
| `cerca_codice_tributo` | `cerca_codice_tributo(query: str) -> str` | Cerca un codice tributo F24 per codice o descrizione. |

## `diritto_lavoro.py` (6 tools)

| name | signature | purpose |
| --- | --- | --- |
| `indennita_licenziamento` | `indennita_licenziamento(anni_servizio: float, retribuzione_mensile: float, dimensione_azienda: str = "grande", tipo: str = "indennitario") -> dict` | Calcola l'indennita di licenziamento per tutele crescenti (D.Lgs. 23/2015). |
| `indennita_preavviso` | `indennita_preavviso(ccnl: str, livello: str, anzianita_anni: float, retribuzione_mensile: float, tipo: str = "licenziamento") -> dict` | Calcola l'indennita sostitutiva del preavviso per CCNL principali. |
| `calcolo_naspi` | `calcolo_naspi(retribuzione_media_mensile: float, settimane_contributive: int, eta_anni: int) -> dict` | Calcola l'importo e la durata della NASpI (indennita di disoccupazione). |
| `scadenze_licenziamento` | `scadenze_licenziamento(data_licenziamento: str) -> dict` | Calcola le scadenze perentorie per l'impugnazione del licenziamento. |
| `costo_lavoro` | `costo_lavoro(retribuzione_lorda_annua: float, tipo_contratto: str = "dipendente") -> dict` | Stima il costo totale del lavoro per l'azienda e il netto per il dipendente. |
| `offerta_conciliativa` | `offerta_conciliativa(anni_servizio: float, retribuzione_mensile: float, dimensione_azienda: str = "grande") -> dict` | Calcola l'offerta conciliativa esente da IRPEF e contributi (art. 6 D.Lgs. 23/2015). |

## `diritto_penale.py` (5 tools)

| name | signature | purpose |
| --- | --- | --- |
| `aumenti_riduzioni_pena` | `aumenti_riduzioni_pena(pena_base_mesi: float, aggravanti: list[dict] \| None = None, attenuanti: list[dict] \| None = None, recidiva: bool = False) -> dict` | Calcola la pena risultante applicando aggravanti, attenuanti e recidiva sulla pena base. |
| `conversione_pena` | `conversione_pena(importo: float, direzione: str = "detentiva_a_pecuniaria", tipo_pena: str = "reclusione") -> dict` | Converte pena detentiva in pecuniaria (o viceversa) al tasso legale di EUR 250/giorno. |
| `fine_pena` | `fine_pena(data_inizio_pena: str, pena_totale_mesi: float, liberazione_anticipata: bool = True, giorni_presofferto: int = 0) -> dict` | Calcola la data di fine pena con eventuale liberazione anticipata (45 giorni per semestre). |
| `prescrizione_reato` | `prescrizione_reato(pena_massima_anni: float, data_commissione: str, interruzioni_giorni: int = 0, sospensioni_giorni: int = 0, tipo_reato: str = "delitto") -> dict` | Calcola il termine di prescrizione del reato e la data di prescrizione. |
| `pena_concordata` | `pena_concordata(pena_base_mesi: float, attenuanti_generiche: bool = True, diminuente_rito: bool = True) -> dict` | Simula la pena patteggiata (art. 444 c.p.p.) con attenuanti generiche e diminuente di rito. |

## `diritto_societario.py` (4 tools)

| name | signature | purpose |
| --- | --- | --- |
| `quorum_assembleari` | `quorum_assembleari(tipo_societa: str, tipo_delibera: str, capitale_totale: float, capitale_presente: float = 0, voti_favorevoli: float = 0) -> dict` | Verifica i quorum costitutivi e deliberativi per assemblee societarie. |
| `soglie_organo_controllo_srl` | `soglie_organo_controllo_srl(ricavi: float, attivo: float, dipendenti: int) -> dict` | Verifica se una SRL supera le soglie che obbligano alla nomina di organo di controllo o revisore. |
| `scadenze_societarie` | `scadenze_societarie(data_chiusura_esercizio: str, bilancio_differito: bool = False) -> dict` | Calcola le principali scadenze societarie annuali a partire dalla chiusura dell'esercizio. |
| `costi_costituzione` | `costi_costituzione(tipo_societa: str) -> dict` | Stima i costi di costituzione di una societa o impresa individuale (valori 2025-2026). |

## `eu_implementation.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `get_italian_implementation` | `get_italian_implementation(direttiva: str) -> str` | Trova l'atto italiano che recepisce una direttiva UE (mappatura UE -> Italia). |
| `get_eu_basis` | `get_eu_basis(atto: str) -> str` | Trova la direttiva UE recepita da un atto italiano (mappatura Italia -> UE). |
| `elenco_misure_nazionali` | `elenco_misure_nazionali(direttiva: str, paese: str = "ITA") -> str` | Elenca le misure nazionali di recepimento di una direttiva UE in un Paese. |

## `fatturazione_avvocati.py` (12 tools)

| name | signature | purpose |
| --- | --- | --- |
| `parcella_avvocato_civile` | `parcella_avvocato_civile(valore_causa: float, fasi: list[str] \| None = None, livello: str = "medio") -> dict` | Calcola compenso tabellare avvocato per contenzioso civile (DM 55/2014 agg. DM 147/2022). |
| `parcella_avvocato_penale` | `parcella_avvocato_penale(competenza: str, fasi: list[str] \| None = None, livello: str = "medio") -> dict` | Calcola compenso tabellare avvocato per procedimento penale (DM 55/2014 agg. DM 147/2022). |
| `parcella_stragiudiziale` | `parcella_stragiudiziale(valore_pratica: float, livello: str = "medio") -> dict` | Calcola compenso tabellare avvocato per attivita stragiudiziale (diffida, trattativa, negoziazione). |
| `parcella_volontaria_giurisdizione` | `parcella_volontaria_giurisdizione(valore_causa: float, fasi: list[str] \| None = None, livello: str = "medio") -> dict` | Calcola compenso tabellare per procedimento di volontaria giurisdizione (Tab. 7 DM 55/2014). |
| `preventivo_volontaria_giurisdizione` | `preventivo_volontaria_giurisdizione(valore_causa: float, fasi: list[str] \| None = None, livello: str = "medio", spese_generali: bool = True, cpa: bool = True, iva: bool = True) -> dict` | Genera preventivo completo per volontaria giurisdizione con spese generali (15%), CPA (4%) e IVA (22%). |
| `fattura_avvocato` | `fattura_avvocato(imponibile: float, regime: str = "ordinario", cpa: bool = True) -> dict` | Genera struttura fattura avvocato con CPA, IVA e ritenuta d'acconto. |
| `nota_spese` | `nota_spese(voci: list[dict]) -> dict` | Calcola nota spese avvocato aggregando voci di compenso, spese generali (15%), CPA (4%) e IVA (22%). |
| `preventivo_civile` | `preventivo_civile(valore_causa: float, fasi: list[str] \| None = None, livello: str = "medio", spese_generali: bool = True, cpa: bool = True, iva: bool = True) -> dict` | Genera preventivo completo per causa civile: compensi tabellari, spese generali (15%), CPA (4%), IVA (22%) e spese vive stimate. |
| `preventivo_stragiudiziale` | `preventivo_stragiudiziale(valore_pratica: float, livello: str = "medio", spese_generali: bool = True, cpa: bool = True, iva: bool = True) -> dict` | Genera preventivo per attivita stragiudiziale (diffida, trattativa, mediazione) con spese generali (15%), CPA (4%) e IVA (22%). |
| `spese_trasferta_avvocati` | `spese_trasferta_avvocati(km_distanza: float, ore_assenza: float, pernottamento: bool = False, mezzo: str = "auto") -> dict` | Calcola indennita di trasferta e rimborso chilometrico per avvocati (DM 55/2014 art. 27). |
| `modello_notula` | `modello_notula(tipo_procedimento: str, avvocato: str, cliente: str, valore_causa: float, fasi: list[str] \| None = None, livello: str = "medio") -> dict` | Genera notula (nota spese) completa formattata per procedimenti tipici di recupero crediti. |
| `calcolo_notula_penale` | `calcolo_notula_penale(competenza: str, fasi: list[str] \| None = None, livello: str = "medio", spese_generali: bool = True) -> dict` | Calcola parcella penale completa con spese generali (15%), CPA (4%) e IVA (22%). |

## `gazzetta.py` (5 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_gazzetta_ufficiale` | `cerca_gazzetta_ufficiale(query: str = "", titolo: str = "", testo: str = "", tipo_provvedimento: str = "", emettitore: str = "", materia: str = "", serie: str = "serie_generale", anno_da: str = "", anno_a: str = "", max_risultati: int = 20) -> str` | Cerca atti pubblicati nella Gazzetta Ufficiale (ricerca parametrica/full-text). |
| `leggi_atto_gazzetta` | `leggi_atto_gazzetta(codice_redazionale: str, data_pubblicazione: str, serie: str = "serie_generale", solo_metadati: bool = False) -> str` | Legge il testo completo di un atto pubblicato in Gazzetta Ufficiale. |
| `sommario_gazzetta` | `sommario_gazzetta(numero_gazzetta: str, data_pubblicazione: str, serie: str = "serie_generale") -> str` | Restituisce il sommario (indice degli atti) di un fascicolo di Gazzetta Ufficiale. |
| `ultime_gazzette` | `ultime_gazzette(serie: str = "serie_generale", max_risultati: int = 10) -> str` | Ultimi atti pubblicati nella Gazzetta Ufficiale (novita normative, via RSS). |
| `scarica_pdf_gazzetta` | `scarica_pdf_gazzetta(numero_gazzetta: str, data_pubblicazione: str, serie: str = "serie_generale") -> str` | Restituisce l'URL del PDF ufficiale di un fascicolo di Gazzetta Ufficiale. |

## `giurisprudenza_unificata.py` (1 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_giurisprudenza_unificata` | `cerca_giurisprudenza_unificata(query: str, fonti: str = "tutte", anno_da: str = "", anno_a: str = "", tipo_provvedimento: str = "", max_risultati: int = 5) -> str` | Cerca giurisprudenza su tutte le fonti disponibili in parallelo (Cassazione, tributaria, amministrativa, CGUE). |

## `giustizia_amm.py` (4 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_giurisprudenza_amministrativa` | `cerca_giurisprudenza_amministrativa(query: str, sede: str = "", tipo: str = "", anno: str = "", numero: str = "", max_risultati: int = 10) -> str` | Cerca sentenze e provvedimenti di TAR e Consiglio di Stato. |
| `leggi_provvedimento_amm` | `leggi_provvedimento_amm(sede: str, nrg: str, nome_file: str) -> str` | Legge il testo completo di un provvedimento amministrativo (TAR/CdS) dal sottodominio mdp. |
| `giurisprudenza_amm_su_norma` | `giurisprudenza_amm_su_norma(riferimento: str, sede: str = "", anno_da: str = "", max_risultati: int = 10) -> str` | Trova provvedimenti TAR/CdS che citano una norma specifica. |
| `ultimi_provvedimenti_amm` | `ultimi_provvedimenti_amm(sede: str = "", tipo: str = "", max_risultati: int = 10) -> str` | Ultimi provvedimenti depositati da TAR e Consiglio di Stato, con filtro opzionale. |

## `gpdp.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cerca_provvedimenti_garante` | `cerca_provvedimenti_garante(query: str, tipologia: str = "", data_da: str = "", data_a: str = "", max_risultati: int = 10) -> str` | Cerca provvedimenti, linee guida e pareri del Garante Privacy (GPDP) dalla fonte ufficiale. |
| `leggi_provvedimento_garante` | `leggi_provvedimento_garante(docweb_id: int) -> str` | Legge il testo completo di un provvedimento del Garante Privacy tramite DocWeb ID. |
| `ultimi_provvedimenti_garante` | `ultimi_provvedimenti_garante(tipologia: str = "", max_risultati: int = 10) -> str` | Ultimi provvedimenti depositati dal Garante Privacy, con filtro opzionale per tipologia. |

## `investimenti.py` (5 tools)

| name | signature | purpose |
| --- | --- | --- |
| `rendimento_bot` | `rendimento_bot(valore_nominale: float, prezzo_acquisto: float, giorni_scadenza: int, commissione_pct: float = 0.0) -> dict` | Calcola il rendimento netto di un BOT (Buono Ordinario del Tesoro, zero-coupon). |
| `rendimento_btp` | `rendimento_btp(valore_nominale: float, prezzo_acquisto: float, cedola_annua_pct: float, anni_scadenza: int, frequenza_cedola: int = 2) -> dict` | Calcola il rendimento netto di un BTP (Buono del Tesoro Poliennale) a cedola fissa. |
| `pronti_termine` | `pronti_termine(capitale: float, tasso_lordo_pct: float, giorni: int, tipo_sottostante: str = "titoli_stato") -> dict` | Calcola il rendimento netto di un pronti contro termine (PCT). |
| `rendimento_buoni_postali` | `rendimento_buoni_postali(importo: float, tipo: str = "ordinario", anni: int = 10) -> dict` | Calcola il rendimento netto di buoni fruttiferi postali con capitalizzazione a scaglioni. |
| `confronto_investimenti` | `confronto_investimenti(importo: float, investimenti: list[dict]) -> dict` | Confronta il rendimento netto tra diversi strumenti finanziari con tassazione corretta. |

## `italgiure.py` (5 tools)

| name | signature | purpose |
| --- | --- | --- |
| `leggi_sentenza` | `leggi_sentenza(numero: int, anno: int, sezione: str = "", archivio: str = "tutti") -> str` | Legge il testo completo di una specifica sentenza della Cassazione da Italgiure (fonte ufficiale). |
| `cerca_giurisprudenza` | `cerca_giurisprudenza(query: str, archivio: str = "tutti", materia: str = "", sezione: str = "", anno_da: int = 0, anno_a: int = 0, tipo_provvedimento: str = "", solo_sezioni_unite: bool = False, ordinamento: str = "rilevanza", max_risultati: int = 5, pagina: int = 0, campo: str = "tutto", modalita: str = "cerca") -> str` | Ricerca full-text nelle sentenze della Cassazione su Italgiure (fonte ufficiale, archivio 2020+). |
| `giurisprudenza_su_norma` | `giurisprudenza_su_norma(riferimento: str, archivio: str = "tutti", solo_sezioni_unite: bool = False, anno_da: int = 0, anno_a: int = 0, max_risultati: int = 5, pagina: int = 0) -> str` | Trova sentenze della Cassazione che citano uno specifico articolo di legge. |
| `ultime_pronunce` | `ultime_pronunce(materia: str = "", sezione: str = "", archivio: str = "tutti", tipo_provvedimento: str = "", solo_sezioni_unite: bool = False, max_risultati: int = 5) -> str` | Ultime pronunce depositate dalla Cassazione, con filtri opzionali. |
| `giurisprudenza_articolo` | `giurisprudenza_articolo(riferimento: str, archivio: str = "tutti", anno_da: int = 0, anno_a: int = 0, max_risultati: int = 5) -> str` | Cerca giurisprudenza su un articolo usando le massime Brocardi come guida. |

## `legal_citations.py` (8 tools)

| name | signature | purpose |
| --- | --- | --- |
| `cite_law` | `cite_law(reference: str, include_annotations: bool = False) -> str` | Recupera il testo ufficiale di una norma di legge. USARE SEMPRE prima di citare qualsiasi norma. |
| `fetch_law_article` | `fetch_law_article(act_type: str, article: str, date: str = "", act_number: str = "") -> str` | Recupero a basso livello di un articolo con parametri espliciti da Normattiva o EUR-Lex. |
| `fetch_law_annotations` | `fetch_law_annotations(act_type: str, article: str, date: str = "", act_number: str = "") -> str` | Recupera le annotazioni Brocardi per un articolo: ratio legis, spiegazione dottrinale, massime giurisprudenziali. |
| `cerca_brocardi` | `cerca_brocardi(reference: str) -> str` | Cerca annotazioni Brocardi per un articolo: ratio legis, spiegazione dottrinale, massime con riferimenti strutturati alla Cassazione. |
| `fetch_act_index` | `fetch_act_index(reference: str) -> str` | Recupera l'indice strutturato (rubriche) di un atto normativo da Normattiva. |
| `fetch_full_act` | `fetch_full_act(reference: str) -> str` | Recupera il testo completo di un atto normativo italiano da Normattiva. |
| `download_law_pdf` | `download_law_pdf(reference: str) -> str` | Scarica (UE da EUR-Lex) o genera (leggi italiane da Normattiva) il PDF completo di una legge. |
| `verifica_citazioni` | `verifica_citazioni(citazioni: str, archivio: str = "tutti") -> str` | Verifica l'esistenza e la coerenza dei metadati di un elenco di citazioni legali (sentenze e norme). |

## `modelli_atti.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `genera_modello_atto` | `genera_modello_atto(tipo_atto: str, parametri: dict \| None = None) -> dict` | Restituisce i metadati per comporre un atto legale: struttura, campi obbligatori, tool di calcolo, resource modello e riferimenti normativi. |
| `esporta_atto_docx` | `esporta_atto_docx(testo: str, titolo: str = "Atto", autore: str = "") -> str` | Esporta un testo (atto, parere, bozza) in formato DOCX (Microsoft Word) da Markdown semplice. |
| `lista_categorie_atti` | `lista_categorie_atti() -> dict` | Restituisce le categorie di atti disponibili con il conteggio per ciascuna. |

## `orientamento.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `orientamento_su_norma` | `orientamento_su_norma(riferimento: str, archivio: str = "tutti", anno_da: int = 0, max_risultati: int = 10) -> str` | Mappa descrittiva degli orientamenti della Cassazione su un articolo di legge (intervento SS.UU., cluster per sezione, trend, segnali testuali — non predittiva). |
| `orientamento_su_principio` | `orientamento_su_principio(principio: str, archivio: str = "tutti", anno_da: int = 0, sezione: str = "", max_risultati: int = 10) -> str` | Mappa descrittiva degli orientamenti della Cassazione a partire da un principio di diritto in linguaggio libero. |
| `mappa_orientamento` | `mappa_orientamento(riferimento: str, archivio: str = "tutti", anno_da: int = 0) -> str` | Mappa descrittiva completa orchestrata: ancoraggio Brocardi (massime consolidate) + orientamenti Cassazione su un articolo. |

## `parcelle_professionisti.py` (11 tools)

| name | signature | purpose |
| --- | --- | --- |
| `fattura_professionista` | `fattura_professionista(imponibile: float, tipo: str = "ingegnere", regime: str = "ordinario") -> dict` | Calcola la fattura di un professionista (non avvocato) con rivalsa INPS, IVA e ritenuta d'acconto. |
| `compenso_ctu` | `compenso_ctu(tipo_incarico: str, valore_causa: float \| None = None, ore_lavoro: float \| None = None) -> dict` | Calcola il compenso indicativo del consulente tecnico d'ufficio (CTU) nominato dal giudice. |
| `spese_mediazione` | `spese_mediazione(valore_controversia: float, esito: str = "positivo") -> dict` | Calcola l'indennità di mediazione civile e commerciale per scaglione di valore (DM 150/2023). |
| `compenso_orario` | `compenso_orario(tariffa_oraria: float, ore: int, minuti: int = 0, arrotondamento: str = "mezz_ora") -> dict` | Calcola il compenso professionale a ore con arrotondamento per eccesso all'unità scelta. |
| `ritenuta_acconto` | `ritenuta_acconto(compenso_lordo: float, aliquota: float = 20.0) -> dict` | Calcola la ritenuta d'acconto su compensi professionali e i campi per la Certificazione Unica (art. 25 DPR 600/1973). |
| `compenso_curatore_fallimentare` | `compenso_curatore_fallimentare(attivo_realizzato: float, passivo_accertato: float) -> dict` | Calcola il compenso del curatore fallimentare su scaglioni progressivi (DM 30/2012). |
| `compenso_delegati_vendite` | `compenso_delegati_vendite(prezzo_aggiudicazione: float) -> dict` | Calcola il compenso del professionista delegato alle vendite giudiziarie immobiliari (DM 227/2015). |
| `compenso_mediatore_familiare` | `compenso_mediatore_familiare(n_incontri: int, tariffa_incontro: float = 120.0) -> dict` | Calcola il compenso del mediatore familiare per un percorso di mediazione (primo incontro gratuito). |
| `fattura_enasarco` | `fattura_enasarco(provvigioni: float, tipo_agente: str = "monocommittente", anno: int = 2026) -> dict` | Calcola la struttura della fattura di un agente di commercio con contributo Enasarco, IVA e ritenuta. |
| `ricevuta_prestazione_occasionale` | `ricevuta_prestazione_occasionale(compenso_lordo: float, committente: str, prestatore: str, descrizione: str) -> dict` | Genera il testo di una ricevuta per prestazione occasionale con ritenuta d'acconto e bollo se >€77,47. |
| `tariffe_mediazione` | `tariffe_mediazione(valore_controversia: float) -> dict` | Restituisce la tabella completa delle indennità di mediazione DM 150/2023 (incluse spese di avvio) per lo scaglione applicabile. |

## `privacy_gdpr.py` (12 tools)

| name | signature | purpose |
| --- | --- | --- |
| `genera_informativa_privacy` | `genera_informativa_privacy(titolare: str, finalita: list[str], basi_giuridiche: list[str], categorie_dati: list[str], destinatari: list[str], periodo_conservazione: str, tipo: str = "art13", dpo: str = "", diritti_esercitabili: list[str] \| None = None, trasferimento_extra_ue: str = "") -> dict` | Genera un'informativa privacy completa ai sensi dell'art. 13 o 14 GDPR. |
| `genera_informativa_cookie` | `genera_informativa_cookie(titolare: str, cookie_tecnici: list[str], sito_web: str, cookie_analytics: list[str] \| None = None, cookie_profilazione: list[str] \| None = None) -> dict` | Genera una cookie policy completa con tabella cookie e testo del banner di consenso. |
| `genera_informativa_dipendenti` | `genera_informativa_dipendenti(titolare: str, dpo: str = "", videosorveglianza: bool = False, geolocalizzazione: bool = False, strumenti_aziendali: bool = False) -> dict` | Genera l'informativa privacy per dipendenti e collaboratori (art. 13 GDPR + art. 4 Statuto Lavoratori). |
| `genera_informativa_videosorveglianza` | `genera_informativa_videosorveglianza(titolare: str, finalita: list[str], tempo_conservazione: str, aree_riprese: list[str]) -> dict` | Genera l'informativa breve (cartello EDPB) ed estesa per sistemi di videosorveglianza. |
| `genera_dpa` | `genera_dpa(titolare: str, responsabile: str, oggetto: str, durata: str, categorie_interessati: list[str], categorie_dati: list[str], misure_sicurezza: list[str], sub_responsabili: list[str] \| None = None) -> dict` | Genera un Data Processing Agreement (DPA) completo ai sensi dell'art. 28 GDPR. |
| `genera_registro_trattamenti` | `genera_registro_trattamenti(titolare: str, trattamento: str, finalita: str, base_giuridica: str, categorie_interessati: list[str], categorie_dati: list[str], destinatari: list[str], termine_cancellazione: str, misure_sicurezza: list[str]) -> dict` | Genera la scheda di un trattamento per il Registro dei Trattamenti (art. 30 GDPR). |
| `genera_dpia` | `genera_dpia(titolare: str, descrizione: str, finalita: str, necessita_proporzionalita: str, rischi: list[dict], misure_mitigazione: list[dict]) -> dict` | Genera una Valutazione d'Impatto sulla Protezione dei Dati (DPIA) ai sensi dell'art. 35 GDPR. |
| `analisi_base_giuridica` | `analisi_base_giuridica(tipo_trattamento: str, contesto: str, finalita: str, dati_particolari: bool = False) -> dict` | Analizza e consiglia la base giuridica appropriata per un trattamento dati (art. 6 GDPR), con analisi art. 9 se richiesto. |
| `verifica_necessita_dpia` | `verifica_necessita_dpia(tipo_trattamento: str, profilazione: bool = False, dati_sensibili: bool = False, monitoraggio_sistematico: bool = False, larga_scala: bool = False, soggetti_vulnerabili: bool = False, nuove_tecnologie: bool = False, valutazione_scoring: bool = False, incrocio_dataset: bool = False, trasferimento_extra_ue: bool = False, impedimento_diritto: bool = False) -> dict` | Verifica se un trattamento richiede obbligatoriamente la DPIA secondo i 9 criteri WP248 (art. 35 GDPR, soglia ≥2). |
| `valutazione_data_breach` | `valutazione_data_breach(tipo_violazione: str, categorie_dati: list[str], n_interessati: int, dati_particolari: bool = False, misure_protezione: list[str] \| None = None, impatto: str = "medio") -> dict` | Valuta un data breach e determina gli obblighi di notifica al Garante (art. 33) e comunicazione agli interessati (art. 34). |
| `calcolo_sanzione_gdpr` | `calcolo_sanzione_gdpr(tipo_violazione: str, fatturato_annuo: float \| None = None, fattori_aggravanti: list[str] \| None = None, fattori_attenuanti: list[str] \| None = None, precedenti: bool = False) -> dict` | Calcola il massimale e il range stimato di sanzione amministrativa GDPR ex art. 83 con analisi dei criteri art. 83(2). |
| `genera_notifica_data_breach` | `genera_notifica_data_breach(titolare: str, data_violazione: str, data_scoperta: str, descrizione: str, categorie_dati: list[str], n_interessati: int, conseguenze: str, misure_adottate: list[str], dpo: str = "") -> dict` | Genera il modulo di notifica di un data breach al Garante ai sensi dell'art. 33 GDPR (scadenza 72h). |

## `procedura_civile.py` (3 tools)

| name | signature | purpose |
| --- | --- | --- |
| `competenza_giudice` | `competenza_giudice(valore_causa: float, materia: str = "civile") -> dict` | Determina il giudice competente (Giudice di Pace o Tribunale) per valore e materia (artt. 7-17 c.p.c.). |
| `verifica_mediazione_obbligatoria` | `verifica_mediazione_obbligatoria(materia: str) -> dict` | Verifica se una materia è soggetta a mediazione obbligatoria come condizione di procedibilità (art. 5 D.Lgs. 28/2010). |
| `gratuito_patrocinio` | `gratuito_patrocinio(reddito_richiedente: float, n_familiari_conviventi: int = 0, redditi_familiari: list[float] \| None = None, ambito: str = "civile", vittima_violenza: bool = False) -> dict` | Verifica l'ammissibilità al patrocinio a spese dello Stato in base ai limiti di reddito (DPR 115/2002). |

## `proprieta_successioni.py` (12 tools)

| name | signature | purpose |
| --- | --- | --- |
| `calcolo_eredita` | `calcolo_eredita(massa_ereditaria: float, eredi: dict) -> dict` | Calcola le quote di legittima e la quota disponibile secondo la successione necessaria (art. 536 ss. c.c.). |
| `imposte_successione` | `imposte_successione(valore_beni: float, parentela: str, immobili: bool = False, prima_casa: bool = False) -> dict` | Calcola l'imposta di successione con franchigie, aliquote e imposte ipocatastali (TU 346/1990). |
| `calcolo_usufrutto` | `calcolo_usufrutto(valore_piena_proprieta: float, eta_usufruttuario: int) -> dict` | Calcola il valore dell'usufrutto e della nuda proprietà in base all'età dell'usufruttuario (DPR 131/1986). |
| `calcolo_imu` | `calcolo_imu(rendita_catastale: float, categoria: str, aliquota_comunale: float = 0.86, prima_casa: bool = False) -> dict` | Calcola l'IMU annua e semestrale per un immobile in base a rendita catastale e categoria (L. 160/2019). |
| `imposte_compravendita` | `imposte_compravendita(prezzo: float, tipo_immobile: str = "abitazione", prima_casa: bool = False, da_costruttore: bool = False, rendita_catastale: float \| None = None) -> dict` | Calcola le imposte per l'acquisto di un immobile (registro, ipotecaria, catastale e IVA). |
| `pensione_reversibilita` | `pensione_reversibilita(pensione_de_cuius: float, beneficiari: dict, reddito_beneficiario: float = 0) -> dict` | Calcola la pensione di reversibilità INPS con quote per tipologia di beneficiari e riduzione per cumulo redditi (L. 335/1995). |
| `grado_parentela` | `grado_parentela(relazione: str) -> dict` | Calcola il grado di parentela tra due persone con rilevanza successoria e fiscale (artt. 74-77 c.c.). |
| `calcolo_valore_catastale` | `calcolo_valore_catastale(rendita_catastale: float, categoria: str, tipo: str = "successione") -> dict` | Calcola il valore catastale rivalutato dell'immobile per successione, compravendita o IMU (DPR 131/1986; L. 160/2019). |
| `calcolo_superficie_commerciale` | `calcolo_superficie_commerciale(superficie_calpestabile: float, balconi: float = 0, terrazzi: float = 0, giardino: float = 0, cantina: float = 0, garage: float = 0) -> dict` | Calcola la superficie commerciale dell'immobile applicando i coefficienti DPR 138/1998. |
| `cedolare_secca` | `cedolare_secca(canone_annuo: float, tipo_contratto: str = "libero", irpef_marginale: float = 38) -> dict` | Confronta la convenienza tra cedolare secca e IRPEF ordinaria per redditi da locazione (D.Lgs. 23/2011). |
| `imposta_registro_locazioni` | `imposta_registro_locazioni(canone_annuo: float, durata_anni: int = 4, tipo_contratto: str = "libero", prima_registrazione: bool = True) -> dict` | Calcola l'imposta di registro per un contratto di locazione abitativa (DPR 131/1986 art. 5). |
| `spese_condominiali` | `spese_condominiali(importo_totale: float, millesimi_proprietario: float, tipo_spesa: str = "ordinaria", piano: int = 0, immobile_locato: bool = False) -> dict` | Calcola la quota condominiale spettante per millesimi e tipo di spesa, con ripartizione proprietario/inquilino se locato (artt. 1123-1124 c.c.). |

## `risarcimento_danni.py` (7 tools)

| name | signature | purpose |
| --- | --- | --- |
| `danno_biologico_micro` | `danno_biologico_micro(percentuale_invalidita: int, eta_vittima: int, giorni_itt: int = 0, giorni_itp75: int = 0, giorni_itp50: int = 0, giorni_itp25: int = 0, personalizzazione_pct: float = 0) -> dict` | Calcola il danno biologico per MICROPERMANENTI (<=9% di invalidita), art. 139 Codice delle Assicurazioni. |
| `danno_biologico_macro` | `danno_biologico_macro(percentuale_invalidita: int, eta_vittima: int, personalizzazione_pct: float = 0) -> dict` | Calcola il danno biologico per MACROPERMANENTI (>=10% di invalidita), art. 138 Codice delle Assicurazioni con tabella unica nazionale. |
| `danno_parentale` | `danno_parentale(vittima: str, superstite: str, tabella: str = "milano", personalizzazione_pct: float = 50) -> dict` | Calcola il danno da perdita del rapporto parentale (danno morale da morte del congiunto) con tabelle Milano/Roma. |
| `menomazioni_plurime` | `menomazioni_plurime(percentuali: list[float]) -> dict` | Calcola l'invalidita complessiva per menomazioni plurime con la formula Balthazard. |
| `risarcimento_inail` | `risarcimento_inail(retribuzione_annua: float, percentuale_invalidita: float, tipo: str = "permanente") -> dict` | Calcola l'indennizzo INAIL per infortunio sul lavoro o malattia professionale. |
| `danno_non_patrimoniale` | `danno_non_patrimoniale(percentuale_invalidita: int, eta_vittima: int, tipo_danno: str = "biologico", giorni_itt: int = 0, spese_mediche: float = 0, danno_morale_pct: float = 0, danno_esistenziale_pct: float = 0) -> dict` | Calcola il danno non patrimoniale complessivo con tutte le componenti (biologico, morale, esistenziale, patrimoniale emergente). |
| `equo_indennizzo` | `equo_indennizzo(categoria_tabella: str, percentuale_invalidita: float, stipendio_annuo: float) -> dict` | Calcola l'equo indennizzo per causa di servizio per dipendenti pubblici (istituto abrogato per eventi post 06/12/2011). |

## `rivalutazioni_istat.py` (12 tools)

| name | signature | purpose |
| --- | --- | --- |
| `rivalutazione_monetaria` | `rivalutazione_monetaria(capitale: float, data_inizio: str, data_fine: str, con_interessi_legali: bool = True) -> dict` | Rivaluta un capitale con indici FOI ISTAT, con o senza interessi legali anno per anno. |
| `rivalutazione_mensile` | `rivalutazione_mensile(importo_mensile: float, data_inizio: str, data_fine: str) -> dict` | Rivaluta ogni singola mensilita di una rata/assegno ricorrente con indici FOI ISTAT. |
| `adeguamento_canone_locazione` | `adeguamento_canone_locazione(canone_annuo: float, data_stipula: str, data_adeguamento: str, percentuale_istat: float = 75.0) -> dict` | Calcola l'adeguamento ISTAT del canone di locazione secondo L. 392/1978 art. 32. |
| `calcolo_inflazione` | `calcolo_inflazione(data_inizio: str, data_fine: str) -> dict` | Calcola la variazione percentuale di inflazione tra due date usando gli indici FOI ISTAT. |
| `rivalutazione_tfr` | `rivalutazione_tfr(retribuzione_annua: float, anni_servizio: int, anno_cessazione: int) -> dict` | Calcola il TFR con rivalutazione annuale ex art. 2120 c.c. (1.5% fisso + 75% FOI, imposta sostitutiva 17%). |
| `interessi_vari_capitale_rivalutato` | `interessi_vari_capitale_rivalutato(capitale: float, data_inizio: str, data_fine: str, tasso_personalizzato: float \| None = None) -> dict` | Rivaluta un capitale FOI e calcola interessi a tasso personalizzato o legale sul rivalutato (criterio Cass. SU 1712/1995). |
| `lettera_adeguamento_canone` | `lettera_adeguamento_canone(locatore: str, conduttore: str, indirizzo_immobile: str, canone_attuale: float, data_stipula: str, data_adeguamento: str, percentuale_istat: float = 75.0) -> dict` | Genera il testo della lettera formale di comunicazione dell'adeguamento ISTAT del canone di locazione. |
| `calcolo_devalutazione` | `calcolo_devalutazione(importo_attuale: float, data_attuale: str, data_passata: str) -> dict` | Calcolo inverso della rivalutazione: riconduce un importo attuale al suo valore in una data passata. |
| `rivalutazione_storica` | `rivalutazione_storica(importo: float, anno_partenza: int, anno_arrivo: int) -> dict` | Rivalutazione semplificata basata sulla media annuale degli indici FOI (senza specificare il mese). |
| `variazioni_istat` | `variazioni_istat(anno_inizio: int, anno_fine: int) -> dict` | Restituisce la tabella delle variazioni percentuali annuali degli indici FOI ISTAT per un periodo. |
| `rivalutazione_annuale_media` | `rivalutazione_annuale_media(importo: float, data_inizio: str, data_fine: str) -> dict` | Rivaluta un importo usando la media annuale degli indici FOI (ignora il mese, conta solo l'anno). |
| `inflazione_titoli_stato` | `inflazione_titoli_stato(capitale_investito: float, rendimento_lordo_annuo_pct: float, data_inizio: str, data_fine: str) -> dict` | Confronta il rendimento nominale di un investimento con l'inflazione FOI nello stesso periodo (rendimento reale, eq. di Fisher). |

## `scadenze_termini.py` (11 tools)

| name | signature | purpose |
| --- | --- | --- |
| `scadenza_processuale` | `scadenza_processuale(data_evento: str, giorni: int, tipo: str = "calendario") -> dict` | Calcola una scadenza processuale generica con proroga festiva ex art. 155 c.p.c. |
| `termini_processuali_civili` | `termini_processuali_civili(data_udienza: str, tipo_termine: str, sospensione_feriale: bool = True) -> dict` | Calcola i termini per memorie e comparse ex art. 171-ter c.p.c. (rito post-Cartabia). |
| `termini_separazione_divorzio` | `termini_separazione_divorzio(data_evento: str, tipo: str) -> dict` | Calcola le scadenze di diritto di famiglia per separazione, divorzio e negoziazione assistita. |
| `scadenze_impugnazioni` | `scadenze_impugnazioni(data_pubblicazione: str, tipo_impugnazione: str, notificata: bool = False) -> dict` | Calcola i termini di impugnazione per sentenze civili (termine breve e termine lungo) ex artt. 325-327 c.p.c. |
| `scadenze_multe` | `scadenze_multe(data_notifica: str, tipo_ricorso: str) -> dict` | Calcola i termini per ricorso o pagamento contro contravvenzioni al Codice della Strada. |
| `termini_memorie_repliche` | `termini_memorie_repliche(data_udienza: str) -> dict` | Calcola in un'unica risposta tutte le scadenze per memorie e repliche ex art. 171-ter c.p.c. |
| `termini_procedimento_semplificato` | `termini_procedimento_semplificato(data_udienza: str) -> dict` | Calcola i termini per il procedimento semplificato di cognizione (rito Cartabia, artt. 281-decies ss. c.p.c.). |
| `termini_183_190_cpc` | `termini_183_190_cpc(data_udienza: str) -> dict` | Calcola i termini ex art. 183 co. 6 e art. 190 c.p.c. (rito civile ordinario PRE-Cartabia). |
| `termini_esecuzioni` | `termini_esecuzioni(data_notifica_titolo: str, tipo: str = "pignoramento_mobiliare") -> dict` | Calcola i termini nelle procedure esecutive civili (pignoramento, opposizione). |
| `termini_deposito_atti_appello` | `termini_deposito_atti_appello(data_notifica_sentenza: str \| None = None, data_pubblicazione: str \| None = None) -> dict` | Calcola i termini per proporre appello (termine breve e lungo) con iscrizione a ruolo. |
| `termini_deposito_ctu` | `termini_deposito_ctu(data_conferimento: str, giorni_termine: int = 60) -> dict` | Calcola le scadenze per il deposito della relazione CTU e le osservazioni delle parti (art. 195 c.p.c.). |

## `tassi_interessi.py` (10 tools)

| name | signature | purpose |
| --- | --- | --- |
| `interessi_legali` | `interessi_legali(capitale: float, data_inizio: str, data_fine: str, tipo: str = "semplici") -> dict` | Calcola interessi legali art. 1284 c.c. tra due date, con cambio automatico di tasso per periodo. |
| `interessi_mora` | `interessi_mora(capitale: float, data_inizio: str, data_fine: str) -> dict` | Calcola interessi di mora per transazioni commerciali (tasso BCE + 8 punti percentuali, D.Lgs. 231/2002). |
| `interessi_tasso_fisso` | `interessi_tasso_fisso(capitale: float, tasso_annuo: float, data_inizio: str, data_fine: str, tipo: str = "semplici") -> dict` | Calcola interessi a tasso fisso personalizzato (contrattuale, convenzionale o ipotetico). |
| `calcolo_ammortamento` | `calcolo_ammortamento(capitale: float, tasso_annuo: float, durata_mesi: int, tipo: str = "francese") -> dict` | Calcola il piano di ammortamento completo per un mutuo o finanziamento (francese o italiano). |
| `verifica_usura` | `verifica_usura(tasso_applicato: float, tipo_operazione: str = "mutuo_prima_casa", trimestre: str \| None = None) -> dict` | Verifica se un tasso supera la soglia di usura ex art. 644 c.p. con formula min(TEGMx1.25+4, TEGM+8). |
| `interessi_acconti` | `interessi_acconti(capitale: float, data_inizio: str, acconti: list[dict], data_fine: str) -> dict` | Calcola interessi legali art. 1284 c.c. con acconti intermedi che riducono il capitale residuo. |
| `calcolo_maggior_danno` | `calcolo_maggior_danno(capitale: float, data_inizio: str, data_fine: str) -> dict` | Calcola il maggior danno ex art. 1224 co. 2 c.c. confrontando rivalutazione ISTAT e interessi legali (Cass. SU 19499/2008). |
| `interessi_corso_causa` | `interessi_corso_causa(capitale: float, data_citazione: str, data_sentenza: str, data_pagamento: str \| None = None) -> dict` | Calcola interessi in corso di causa art. 1284 co. 4 c.c. (tasso mora D.Lgs. 231/2002 dalla citazione). |
| `calcolo_surroga_mutuo` | `calcolo_surroga_mutuo(debito_residuo: float, rata_attuale: float, tasso_attuale: float, tasso_nuovo: float, mesi_residui: int) -> dict` | Confronta il mutuo attuale con un mutuo surrogato per valutare la convenienza della portabilita (art. 120-quater TUB). |
| `calcolo_taeg` | `calcolo_taeg(capitale: float, rate: int, importi_rate: float, spese_iniziali: float = 0, spese_periodiche: float = 0) -> dict` | Calcola il TAEG (Tasso Annuo Effettivo Globale) con metodo iterativo Newton-Raphson. |

## `varie.py` (12 tools)

| name | signature | purpose |
| --- | --- | --- |
| `codice_fiscale` | `codice_fiscale(cognome: str, nome: str, data_nascita: str, sesso: str, comune_nascita: str) -> dict` | Genera il codice fiscale italiano a 16 caratteri secondo l'algoritmo ufficiale (DM 12/03/1974). |
| `decodifica_codice_fiscale` | `decodifica_codice_fiscale(codice_fiscale: str) -> dict` | Decodifica un codice fiscale italiano a 16 caratteri estraendo i dati anagrafici. |
| `verifica_iban` | `verifica_iban(iban: str) -> dict` | Valida un IBAN italiano (27 caratteri) ed estrae le componenti ABI, CAB e conto (ISO 7064 mod 97). |
| `conta_giorni` | `conta_giorni(data_inizio: str, data_fine: str, tipo: str = "calendario") -> dict` | Conta i giorni tra due date per tipo: calendario, lavorativi (escl. weekend e festivi italiani) o festivi. |
| `scorporo_iva` | `scorporo_iva(importo_ivato: float, aliquota: float = 22) -> dict` | Scorporo dell'IVA da un importo ivato: ricava imponibile e IVA separati (DPR 633/1972). |
| `decurtazione_punti_patente` | `decurtazione_punti_patente(violazione: str) -> dict` | Restituisce punti decurtati, sanzione pecuniaria e sospensione patente per violazione CdS. |
| `tasso_alcolemico` | `tasso_alcolemico(sesso: str, peso_kg: float, unita_alcoliche: float, ore_trascorse: float, stomaco_pieno: bool = False) -> dict` | Calcola il tasso alcolemico teorico con la formula di Widmark e indica la fascia sanzionatoria CdS (art. 186). |
| `prescrizione_diritti` | `prescrizione_diritti(tipo_diritto: str, data_evento: str) -> dict` | Calcola la data di prescrizione di un diritto civile e verifica se e gia prescritto. |
| `calcolo_tempo_trascorso` | `calcolo_tempo_trascorso(data_inizio: str, data_fine: str \| None = None) -> dict` | Calcola il tempo trascorso tra due date espresso in anni, mesi e giorni. |
| `verifica_partita_iva` | `verifica_partita_iva(partita_iva: str) -> dict` | Valida formalmente una partita IVA italiana tramite algoritmo di controllo (11 cifre). |
| `calcolo_eta_anagrafica` | `calcolo_eta_anagrafica(data_nascita: str, data_riferimento: str \| None = None) -> dict` | Calcola l'eta anagrafica esatta in anni, mesi e giorni con data del prossimo compleanno. |
| `ricerca_codici_ateco` | `ricerca_codici_ateco(keyword: str) -> dict` | Ricerca codici ATECO per parola chiave, con coefficiente di redditivita per il regime forfettario. |

