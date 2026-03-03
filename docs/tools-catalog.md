# Tool Catalog — mcp-legal-it

Riferimento completo di tutti i tool esposti dal server MCP. Fonte di verità per nome, firma e
descrizione di ogni tool.

**Totale tool: 161** in 16 categorie.

---

## Indice

1. [Consultazione normativa](#1-consultazione-normativa) — 7 tool
2. [Giurisprudenza Cassazione](#2-giurisprudenza-cassazione) — 4 tool
3. [Provvedimenti Garante Privacy (GPDP)](#3-provvedimenti-garante-privacy-gpdp) — 3 tool
4. [Privacy / GDPR Compliance](#4-privacy--gdpr-compliance) — 12 tool
5. [Rivalutazioni ISTAT](#5-rivalutazioni-istat) — 11 tool
6. [Tassi e interessi](#6-tassi-e-interessi) — 10 tool
7. [Scadenze processuali](#7-scadenze-processuali) — 11 tool
8. [Atti giudiziari](#8-atti-giudiziari) — 23 tool
9. [Parcelle avvocati](#9-parcelle-avvocati) — 12 tool
10. [Parcelle professionisti](#10-parcelle-professionisti) — 11 tool
11. [Risarcimento danni](#11-risarcimento-danni) — 7 tool
12. [Diritto penale](#12-diritto-penale) — 5 tool
13. [Proprietà e successioni](#13-proprietà-e-successioni) — 12 tool
14. [Investimenti](#14-investimenti) — 5 tool
15. [Dichiarazione redditi](#15-dichiarazione-redditi) — 14 tool
16. [Utilità generali](#16-utilità-generali) — 12 tool

---

## 1. Consultazione normativa

**Modulo:** `src/tools/legal_citations.py`
**Tag:** `normativa`
**API esterne:** Normattiva, EUR-Lex, Brocardi

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `cite_law` | `cite_law(reference: str, include_annotations: bool = False)` | Testo ufficiale di una norma da Normattiva/EUR-Lex. Entry point principale per citazioni. |
| `fetch_law_article` | `fetch_law_article(act_type: str, article: str, date: str = "", act_number: str = "")` | Recupero a basso livello del testo di un articolo con parametri espliciti. |
| `fetch_law_annotations` | `fetch_law_annotations(act_type: str, article: str, date: str = "", act_number: str = "")` | Solo annotazioni Brocardi per un articolo specifico. |
| `cerca_brocardi` | `cerca_brocardi(reference: str)` | Annotazioni complete Brocardi: ratio, spiegazione, massime strutturate con riferimenti Cassazione. |
| `fetch_act_index` | `fetch_act_index(reference: str)` | Indice degli articoli di un atto normativo. |
| `fetch_full_act` | `fetch_full_act(reference: str)` | Testo integrale di un atto normativo. |
| `download_law_pdf` | `download_law_pdf(reference: str)` | PDF ufficiale (EUR-Lex) o generato (Normattiva) della norma. |

---

## 2. Giurisprudenza Cassazione

**Modulo:** `src/tools/italgiure.py`
**Tag:** `giurisprudenza`
**API esterne:** Italgiure (Cassazione Solr API, `https://www.italgiure.giustizia.it`)
**Note:** SSL non valido → `verify=False`; collezioni `snciv` (civile) e `snpen` (penale); OCR troncato a 30.000 caratteri.

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `leggi_sentenza` | `leggi_sentenza(numero: int, anno: int, sezione: str = "", archivio: str = "tutti")` | Testo completo di una sentenza da Italgiure. Usare quando si conosce già il numero. |
| `cerca_giurisprudenza` | `cerca_giurisprudenza(query: str, archivio: str = "tutti", materia: str = "", sezione: str = "", anno_da: int = 0, anno_a: int = 0, max_risultati: int = 10, pagina: int = 0)` | Ricerca full-text nelle sentenze della Cassazione. |
| `giurisprudenza_su_norma` | `giurisprudenza_su_norma(riferimento: str, archivio: str = "tutti", max_risultati: int = 10, pagina: int = 0)` | Sentenze della Cassazione che citano uno specifico articolo di legge. |
| `ultime_pronunce` | `ultime_pronunce(materia: str = "", sezione: str = "", archivio: str = "tutti", tipo_provvedimento: str = "", max_risultati: int = 10)` | Ultime decisioni depositate dalla Cassazione, con filtri opzionali. |

---

## 3. Provvedimenti Garante Privacy (GPDP)

**Modulo:** `src/tools/gpdp.py`
**Tag:** `privacy`
**API esterne:** Portale GPDP (`https://www.gpdp.it`)

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `cerca_provvedimenti_garante` | `cerca_provvedimenti_garante(query: str, tipologia: str = "", data_da: str = "", data_a: str = "", max_risultati: int = 10)` | Ricerca full-text nei provvedimenti del Garante Privacy. |
| `leggi_provvedimento_garante` | `leggi_provvedimento_garante(docweb_id: int)` | Testo completo di un provvedimento del Garante per ID docweb. |
| `ultimi_provvedimenti_garante` | `ultimi_provvedimenti_garante(tipologia: str = "", max_risultati: int = 10)` | Ultimi provvedimenti pubblicati dal Garante, con filtro tipologia. |

---

## 4. Privacy / GDPR Compliance

**Modulo:** `src/tools/privacy_gdpr.py`
**Tag:** `privacy`
**Riferimento normativo:** GDPR (Reg. UE 2016/679); D.Lgs. 101/2018

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `genera_informativa_privacy` | `genera_informativa_privacy(titolare: str, finalita: list, basi_giuridiche: list, categorie_dati: list, destinatari: list, periodo_conservazione: str, tipo: str = "art13", dpo: str = "", diritti_esercitabili: list \| None = None, trasferimento_extra_ue: str = "")` | Informativa completa art. 13 o 14 GDPR con checklist elementi obbligatori. |
| `genera_informativa_cookie` | `genera_informativa_cookie(titolare: str, cookie_tecnici: list, sito_web: str, cookie_analytics: list \| None = None, cookie_profilazione: list \| None = None)` | Cookie policy con tabella cookie e testo banner suggerito. |
| `genera_informativa_dipendenti` | `genera_informativa_dipendenti(titolare: str, dpo: str = "", videosorveglianza: bool = False, geolocalizzazione: bool = False, strumenti_aziendali: bool = False)` | Informativa privacy per dipendenti (art. 13 GDPR + Statuto Lavoratori). |
| `genera_informativa_videosorveglianza` | `genera_informativa_videosorveglianza(titolare: str, finalita: list, tempo_conservazione: str, aree_riprese: list)` | Cartello EDPB e informativa estesa per impianti di videosorveglianza. |
| `genera_dpa` | `genera_dpa(titolare: str, responsabile: str, oggetto: str, durata: str, categorie_interessati: list, categorie_dati: list, misure_sicurezza: list, sub_responsabili: list \| None = None)` | Contratto art. 28 GDPR con checklist delle 8 clausole obbligatorie. |
| `genera_registro_trattamenti` | `genera_registro_trattamenti(titolare: str, trattamento: str, finalita: str, base_giuridica: str, categorie_interessati: list, categorie_dati: list, destinatari: list, termine_cancellazione: str, misure_sicurezza: list)` | Scheda registro trattamenti art. 30 GDPR formattata. |
| `genera_dpia` | `genera_dpia(titolare: str, descrizione: str, finalita: str, necessita_proporzionalita: str, rischi: list, misure_mitigazione: list)` | DPIA completa con matrice rischi e calcolo del rischio residuo. |
| `analisi_base_giuridica` | `analisi_base_giuridica(tipo_trattamento: str, contesto: str, finalita: str, dati_particolari: bool = False)` | Analisi basi giuridiche applicabili (art. 6 GDPR) con raccomandazione motivata. |
| `verifica_necessita_dpia` | `verifica_necessita_dpia(tipo_trattamento: str, profilazione: bool = False, dati_sensibili: bool = False, monitoraggio_sistematico: bool = False, larga_scala: bool = False, soggetti_vulnerabili: bool = False, nuove_tecnologie: bool = False, valutazione_scoring: bool = False, incrocio_dataset: bool = False, trasferimento_extra_ue: bool = False, impedimento_diritto: bool = False)` | Verifica i 9 criteri WP248: ≥2 criteri → DPIA obbligatoria. |
| `valutazione_data_breach` | `valutazione_data_breach(tipo_violazione: str, categorie_dati: list, n_interessati: int, dati_particolari: bool = False, misure_protezione: list \| None = None, impatto: str = "medio")` | Valutazione rischio e obblighi di notifica/comunicazione del data breach. |
| `calcolo_sanzione_gdpr` | `calcolo_sanzione_gdpr(tipo_violazione: str, fatturato_annuo: float \| None = None, fattori_aggravanti: list \| None = None, fattori_attenuanti: list \| None = None, precedenti: bool = False)` | Stima range sanzioni con analisi criteri art. 83(2) GDPR. |
| `genera_notifica_data_breach` | `genera_notifica_data_breach(titolare: str, data_violazione: str, data_scoperta: str, descrizione: str, categorie_dati: list, n_interessati: int, conseguenze: str, misure_adottate: str, dpo: str = "")` | Modulo notifica al Garante con scadenza 72h (art. 33 GDPR). |

---

## 5. Rivalutazioni ISTAT

**Modulo:** `src/tools/rivalutazioni_istat.py`
**Tag:** `rivalutazione`
**File dati:** `src/data/indici_foi.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `rivalutazione_monetaria` | `rivalutazione_monetaria(capitale: float, data_inizio: str, data_fine: str, con_interessi_legali: bool = True)` | Rivalutazione ISTAT del capitale con o senza interessi legali. |
| `rivalutazione_mensile` | `rivalutazione_mensile(importo_mensile: float, data_inizio: str, data_fine: str)` | Rivalutazione di un importo mensile su base ISTAT FOI. |
| `adeguamento_canone_locazione` | `adeguamento_canone_locazione(canone_annuo: float, data_stipula: str, data_adeguamento: str, percentuale_istat: float = 75.0)` | Adeguamento ISTAT del canone di locazione con percentuale configurabile. |
| `calcolo_inflazione` | `calcolo_inflazione(data_inizio: str, data_fine: str)` | Variazione percentuale dell'indice FOI tra due date. |
| `rivalutazione_tfr` | `rivalutazione_tfr(retribuzione_annua: float, anni_servizio: int, anno_cessazione: int)` | Rivalutazione del TFR (art. 2120 c.c.): 1,5% fisso + 75% FOI annuo. |
| `interessi_vari_capitale_rivalutato` | `interessi_vari_capitale_rivalutato(capitale: float, data_inizio: str, data_fine: str, tasso_personalizzato: float \| None = None)` | Interessi su capitale rivalutato ISTAT, con tasso legale o personalizzato. |
| `lettera_adeguamento_canone` | `lettera_adeguamento_canone(locatore: str, conduttore: str, indirizzo_immobile: str, canone_attuale: float, data_stipula: str, data_adeguamento: str, percentuale_istat: float = 75.0)` | Genera testo della lettera di adeguamento ISTAT del canone. |
| `calcolo_devalutazione` | `calcolo_devalutazione(importo_attuale: float, data_attuale: str, data_passata: str)` | Calcola il valore passato equivalente a un importo attuale (devalutazione). |
| `rivalutazione_storica` | `rivalutazione_storica(importo: float, anno_partenza: int, anno_arrivo: int)` | Rivalutazione ISTAT per anno intero, senza granularità mensile. |
| `variazioni_istat` | `variazioni_istat(anno_inizio: int, anno_fine: int)` | Serie storica delle variazioni ISTAT annuali tra due anni. |
| `rivalutazione_annuale_media` | `rivalutazione_annuale_media(importo: float, data_inizio: str, data_fine: str)` | Rivalutazione con indice medio annuale (anziché puntuale). |

---

## 6. Tassi e interessi

**Modulo:** `src/tools/tassi_interessi.py`
**Tag:** `interessi`
**File dati:** `src/data/tassi_legali.json`, `src/data/tassi_mora.json`, `src/data/tegm.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `interessi_legali` | `interessi_legali(capitale: float, data_inizio: str, data_fine: str, tipo: str = "semplici")` | Interessi al tasso legale (art. 1284 c.c.) semplici o composti. |
| `interessi_mora` | `interessi_mora(capitale: float, data_inizio: str, data_fine: str)` | Interessi di mora su crediti commerciali (D.Lgs. 231/2002, BCE + 8 punti). |
| `interessi_tasso_fisso` | `interessi_tasso_fisso(capitale: float, tasso_annuo: float, data_inizio: str, data_fine: str, tipo: str = "semplici")` | Interessi a tasso fisso personalizzato, semplici o composti. |
| `calcolo_ammortamento` | `calcolo_ammortamento(capitale: float, tasso_annuo: float, durata_mesi: int, tipo: str = "francese")` | Piano di ammortamento (francese/italiano/americano) con tabella rate. |
| `verifica_usura` | `verifica_usura(tasso_applicato: float, tipo_operazione: str = "mutuo_prima_casa", trimestre: str \| None = None)` | Verifica superamento soglia usura (TEGM + spread L. 108/1996). |
| `interessi_acconti` | `interessi_acconti(capitale: float, data_inizio: str, acconti: list[dict], data_fine: str)` | Interessi su credito con defalco progressivo degli acconti versati. |
| `calcolo_maggior_danno` | `calcolo_maggior_danno(capitale: float, data_inizio: str, data_fine: str)` | Maggior danno da svalutazione monetaria (art. 1224 co. 2 c.c.). |
| `interessi_corso_causa` | `interessi_corso_causa(capitale: float, data_citazione: str, data_sentenza: str, data_pagamento: str \| None = None)` | Interessi dalla citazione alla sentenza e al pagamento effettivo. |
| `calcolo_surroga_mutuo` | `calcolo_surroga_mutuo(debito_residuo: float, rata_attuale: float, tasso_attuale: float, tasso_nuovo: float, mesi_residui: int)` | Convenienza della surroga mutuo: confronto rata e risparmio totale. |
| `calcolo_taeg` | `calcolo_taeg(capitale: float, rate: int, importi_rate: list[float], spese_iniziali: float = 0, spese_periodiche: float = 0)` | Calcolo TAEG (Tasso Annuo Effettivo Globale) secondo Dir. 2008/48/CE. |

---

## 7. Scadenze processuali

**Modulo:** `src/tools/scadenze_termini.py`
**Tag:** `scadenze`
**File dati:** `src/data/festivita.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `scadenza_processuale` | `scadenza_processuale(data_inizio: str, giorni: int, tipo: str = "calendario")` | Calcola la scadenza processuale escludendo festivi e weekend se richiesto. |
| `termini_processuali_civili` | `termini_processuali_civili(tipo_termine: str, data_notifica: str)` | Scadenze dei principali termini nel processo civile (post-Cartabia). |
| `termini_separazione_divorzio` | `termini_separazione_divorzio(tipo: str, data_udienza: str)` | Termini processuali per separazione e divorzio giudiziali. |
| `scadenze_impugnazioni` | `scadenze_impugnazioni(tipo_atto: str, data_notifica: str, via_breve: bool = False)` | Termini per impugnare sentenze (appello, Cassazione, opposizione). |
| `scadenze_multe` | `scadenze_multe(data_notifica: str)` | Termini per pagamento in misura ridotta, ricorso prefetto e giudice di pace. |
| `termini_memorie_repliche` | `termini_memorie_repliche(data_udienza: str, tipo_procedimento: str = "ordinario")` | Scadenza deposito memorie ex art. 171-ter c.p.c. (Cartabia). |
| `termini_procedimento_semplificato` | `termini_procedimento_semplificato(data_notifica: str)` | Termini per il procedimento semplificato di cognizione (art. 281-terdecies c.p.c.). |
| `termini_183_190_cpc` | `termini_183_190_cpc(data_udienza_183: str)` | Termini memorie istruttorie ex artt. 183, 183-bis, 190 c.p.c. |
| `termini_esecuzioni` | `termini_esecuzioni(tipo: str, data_atto: str)` | Termini processuali per procedure esecutive (pignoramento, udienza, etc.). |
| `termini_deposito_atti_appello` | `termini_deposito_atti_appello(data_udienza: str)` | Termini di deposito atti nel procedimento d'appello (art. 352 c.p.c.). |
| `termini_deposito_ctu` | `termini_deposito_ctu(data_conferimento_incarico: str, giorni_proroga: int = 0)` | Termine deposito relazione CTU con eventuale proroga. |

---

## 8. Atti giudiziari

**Modulo:** `src/tools/atti_giudiziari.py`
**Tag:** `giudiziario`
**File dati:** `src/data/contributo_unificato.json`, `src/data/codici_ruolo.json`, `src/data/tribunali_competenti.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `contributo_unificato` | `contributo_unificato(valore_causa: float, tipo_procedimento: str = "cognizione", grado: str = "primo")` | Calcola il contributo unificato per valore e tipo di procedimento. |
| `diritti_copia` | `diritti_copia(n_pagine: int, tipo: str = "semplice", formato: str = "digitale", urgente: bool = False)` | Diritti di copia atti giudiziari (digitali e cartacei). |
| `pignoramento_stipendio` | `pignoramento_stipendio(stipendio_netto_mensile: float, tipo_credito: str = "ordinario")` | Calcola la quota pignorabile dello stipendio (art. 545 c.p.c.). |
| `sollecito_pagamento` | `sollecito_pagamento(creditore: str, debitore: str, importo: float, data_scadenza: str, data_sollecito: str, tasso_mora: float \| None = None)` | Genera bozza lettera di sollecito con conteggio interessi di mora. |
| `decreto_ingiuntivo` | `decreto_ingiuntivo(creditore: str, debitore: str, importo: float, tipo_credito: str = "ordinario", provvisoria_esecuzione: bool = False)` | Genera bozza ricorso per decreto ingiuntivo con calcolo contributo unificato. |
| `calcolo_hash` | `calcolo_hash(testo: str)` | Calcola hash SHA-256 di un testo (per integrità atti telematici PCT). |
| `tassazione_atti` | `tassazione_atti(tipo_atto: str, valore: float, prima_casa: bool = False)` | Calcola imposta di registro, ipotecaria e catastale per atti notarili. |
| `copie_processo_tributario` | `copie_processo_tributario(n_pagine: int, tipo: str = "semplice", urgente: bool = False)` | Diritti di copia per il processo tributario (CGT). |
| `note_iscrizione_ruolo` | `note_iscrizione_ruolo(tipo_procedimento: str, valore_causa: float \| None = None)` | Genera bozza note di iscrizione a ruolo con codici e modelli. |
| `codici_iscrizione_ruolo` | `codici_iscrizione_ruolo(materia: str)` | Restituisce i codici materia e rito per l'iscrizione a ruolo. |
| `fascicolo_di_parte` | `fascicolo_di_parte(avvocato: str, parte: str, controparte: str, tribunale: str, rg_numero: str \| None = None)` | Genera indice del fascicolo di parte per il deposito telematico. |
| `procura_alle_liti` | `procura_alle_liti(parte: str, avvocato: str, cf_avvocato: str, foro: str, oggetto_causa: str, tipo: str = "generale")` | Genera bozza di procura alle liti (generale o speciale). |
| `attestazione_conformita` | `attestazione_conformita(avvocato: str, tipo_documento: str, estremi_originale: str, modalita: str = "estratto")` | Genera attestazione di conformità per copie informatiche (art. 16-undecies DL 179/2012). |
| `relata_notifica_pec` | `relata_notifica_pec(avvocato: str, destinatario: str, pec_destinatario: str, atto_notificato: str, data_invio: str)` | Genera relata di notifica a mezzo PEC (L. 53/1994). |
| `indice_documenti` | `indice_documenti(documenti: list[dict])` | Genera indice numerato dei documenti allegati all'atto. |
| `note_trattazione_scritta` | `note_trattazione_scritta(avvocato: str, parte: str, tribunale: str, rg_numero: str, giudice: str, conclusioni: str)` | Genera bozza note per trattazione scritta/cartolare. |
| `sfratto_morosita` | `sfratto_morosita(locatore: str, conduttore: str, immobile: str, canone_mensile: float, mensilita_insolute: int, data_contratto: str)` | Genera bozza atto di intimazione di sfratto per morosità (art. 658 c.p.c.). |
| `atto_di_precetto` | `atto_di_precetto(creditore: str, debitore: str, titolo_esecutivo: str, importo_capitale: float, interessi: float = 0, spese: float = 0)` | Genera bozza atto di precetto con avvertimento ex art. 480 c.p.c. |
| `nota_precisazione_credito` | `nota_precisazione_credito(creditore: str, debitore: str, procedura_esecutiva: str, capitale: float, interessi: float, spese_legali: float, spese_esecuzione: float)` | Genera bozza nota di precisazione del credito per procedure esecutive. |
| `dichiarazione_553_cpc` | `dichiarazione_553_cpc(terzo_pignorato: str, debitore: str, procedura: str, tipo_rapporto: str = "conto_corrente")` | Genera bozza dichiarazione del terzo pignorato ex art. 547 c.p.c. |
| `testimonianza_scritta` | `testimonianza_scritta(teste: str, capitoli_prova: list[str])` | Genera modulo per testimonianza scritta con capitoli e ammonizione (art. 257-bis c.p.c.). |
| `istanza_visibilita_fascicolo` | `istanza_visibilita_fascicolo(avvocato: str, parte: str, tribunale: str, rg_numero: str, motivo: str = "costituzione")` | Genera istanza di visibilità fascicolo telematico per avvocato non costituito. |
| `cerca_ufficio_giudiziario` | `cerca_ufficio_giudiziario(comune: str, tipo: str = "tribunale")` | Cerca l'ufficio giudiziario territorialmente competente per un comune. |

---

## 9. Parcelle avvocati

**Modulo:** `src/tools/fatturazione_avvocati.py`
**Tag:** `parcelle_avv`
**File dati:** `src/data/parametri_forensi.json`
**Riferimento:** D.M. 55/2014 (mod. D.M. 147/2022)

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `parcella_avvocato_civile` | `parcella_avvocato_civile(valore_causa: float, fasi: list[str], grado: str = "primo", numero_udienza: int = 3)` | Calcola il compenso per attività civile su scaglioni D.M. 55/2014. |
| `parcella_avvocato_penale` | `parcella_avvocato_penale(tipo_reato: str, fasi: list[str], grado: str = "primo")` | Compenso per attività penale su tabelle D.M. 55/2014. |
| `parcella_stragiudiziale` | `parcella_stragiudiziale(valore: float, tipo: str = "stragiudiziale")` | Compenso per attività stragiudiziale (diffide, contratti, consulenze). |
| `parcella_volontaria_giurisdizione` | `parcella_volontaria_giurisdizione(tipo_atto: str)` | Compenso per atti di volontaria giurisdizione (accettazione eredità, etc.). |
| `preventivo_volontaria_giurisdizione` | `preventivo_volontaria_giurisdizione(tipo_procedimento: str, include_spese: bool = True)` | Preventivo completo per procedimenti di volontaria giurisdizione. |
| `fattura_avvocato` | `fattura_avvocato(imponibile: float, regime: str = "ordinario", cassa_forense: float = 4.0)` | Calcola fattura avvocato con CPA 4%, IVA 22% e ritenuta d'acconto. |
| `nota_spese` | `nota_spese(spese: list[dict])` | Genera nota spese documentata per rimborso spese vive. |
| `preventivo_civile` | `preventivo_civile(valore_causa: float, tipo_giudizio: str = "ordinario", grado: str = "primo")` | Preventivo analitico per causa civile con stima costi totali. |
| `preventivo_stragiudiziale` | `preventivo_stragiudiziale(tipo_pratica: str, valore: float \| None = None)` | Preventivo per attività stragiudiziale con range min-max. |
| `spese_trasferta_avvocati` | `spese_trasferta_avvocati(km: float, tipo_mezzo: str = "auto_propria", notti: int = 0)` | Calcola rimborso trasferta avvocato (km, vitto, alloggio). |
| `modello_notula` | `modello_notula(avvocato: str, cliente: str, attivita: list[dict], data: str)` | Genera bozza notula professionale con riepilogo attività. |
| `calcolo_notula_penale` | `calcolo_notula_penale(tipo_reato: str, fasi_svolte: list[str], note: str = "")` | Calcolo notula per procedimento penale con dettaglio fasi D.M. 55/2014. |

---

## 10. Parcelle professionisti

**Modulo:** `src/tools/parcelle_professionisti.py`
**Tag:** `parcelle_prof`
**Riferimento:** DPR 115/2002 (CTU), DM 150/2023 (mediazione), DM 30/2012 (curatore), DM 227/2015 (delegati vendite)

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `fattura_professionista` | `fattura_professionista(imponibile: float, tipo: str = "ingegnere", regime: str = "ordinario")` | Fattura professionista non-avvocato: rivalsa INPS (4-5%), IVA 22%, ritenuta 20%. |
| `compenso_ctu` | `compenso_ctu(tipo_incarico: str, valore_causa: float \| None = None, ore_lavoro: float \| None = None)` | Compenso indicativo CTU nominato dal giudice (range min-max per incarico). |
| `spese_mediazione` | `spese_mediazione(valore_controversia: float, esito: str = "positivo")` | Indennità di mediazione civile per scaglione DM 150/2023. |
| `compenso_orario` | `compenso_orario(tariffa_oraria: float, ore: int, minuti: int = 0, arrotondamento: str = "mezz_ora")` | Compenso professionale a ore con arrotondamento per eccesso. |
| `ritenuta_acconto` | `ritenuta_acconto(compenso_lordo: float, aliquota: float = 20.0)` | Calcola ritenuta d'acconto e mostra campi Certificazione Unica. |
| `compenso_curatore_fallimentare` | `compenso_curatore_fallimentare(attivo_realizzato: float, passivo_accertato: float)` | Compenso curatore su scaglioni progressivi DM 30/2012 (min €811, max €405.657). |
| `compenso_delegati_vendite` | `compenso_delegati_vendite(prezzo_aggiudicazione: float)` | Compenso professionista delegato a vendite giudiziarie immobiliari (DM 227/2015). |
| `compenso_mediatore_familiare` | `compenso_mediatore_familiare(n_incontri: int, tariffa_incontro: float = 120.0)` | Compenso mediatore familiare (primo incontro gratuito, poi a tariffa). |
| `fattura_enasarco` | `fattura_enasarco(provvigioni: float, tipo_agente: str = "monocommittente", anno: int = 2026)` | Fattura agente di commercio con Enasarco 17%, IVA e ritenuta. |
| `ricevuta_prestazione_occasionale` | `ricevuta_prestazione_occasionale(compenso_lordo: float, committente: str, prestatore: str, descrizione: str)` | Genera ricevuta prestazione occasionale con ritenuta 20% e bollo se >€77,47. |
| `tariffe_mediazione` | `tariffe_mediazione(valore_controversia: float)` | Tabella completa indennità DM 150/2023 con spese avvio e tabella tutti gli scaglioni. |

---

## 11. Risarcimento danni

**Modulo:** `src/tools/risarcimento_danni.py`
**Tag:** `danni`
**Riferimento:** Tabelle Milano 2023, DM 3/7/2023 (macro-permanenti), INAIL

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `danno_biologico_micro` | `danno_biologico_micro(percentuale_invalidita: float, eta_vittima: int, giorni_itt: int = 0, giorni_itp75: int = 0, giorni_itp50: int = 0, giorni_itp25: int = 0, personalizzazione_pct: float = 0)` | Danno biologico da micro-permanente (≤9%) con ITT e ITP. |
| `danno_biologico_macro` | `danno_biologico_macro(percentuale_invalidita: float, eta_vittima: int, personalizzazione_pct: float = 0)` | Danno biologico da macro-permanente (≥10%) con tabelle DM 3/7/2023. |
| `danno_parentale` | `danno_parentale(vittima: str, superstite: str, tabella: str = "milano", personalizzazione_pct: float = 50)` | Danno parentale per perdita del congiunto con personalizzazione. |
| `menomazioni_plurime` | `menomazioni_plurime(percentuali: list[float])` | Combina percentuali di invalidità plurime con formula Balthazar. |
| `risarcimento_inail` | `risarcimento_inail(retribuzione_annua: float, percentuale_invalidita: float, tipo: str = "permanente")` | Calcola prestazione INAIL per infortunio sul lavoro (permanente/temporanea). |
| `danno_non_patrimoniale` | `danno_non_patrimoniale(percentuale_invalidita: float, eta_vittima: int, tipo_danno: str = "biologico", giorni_itt: int = 0, spese_mediche: float = 0, danno_morale_pct: float = 0, danno_esistenziale_pct: float = 0)` | Danno non patrimoniale complessivo con componenti biologica, morale ed esistenziale. |
| `equo_indennizzo` | `equo_indennizzo(categoria_tabella: str, percentuale_invalidita: float, stipendio_annuo: float)` | Equo indennizzo per dipendenti pubblici per infermità da causa di servizio. |

---

## 12. Diritto penale

**Modulo:** `src/tools/diritto_penale.py`
**Tag:** `penale`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `aumenti_riduzioni_pena` | `aumenti_riduzioni_pena(pena_base_mesi: float, aggravanti: list \| None = None, attenuanti: list \| None = None, recidiva: bool = False)` | Calcola pena definitiva applicando aggravanti, attenuanti e recidiva. |
| `conversione_pena` | `conversione_pena(importo: float, direzione: str = "detentiva_a_pecuniaria", tipo_pena: str = "reclusione")` | Conversione pena detentiva in pecuniaria e viceversa (art. 135 c.p.). |
| `fine_pena` | `fine_pena(data_inizio_pena: str, pena_totale_mesi: float, liberazione_anticipata: bool = True, giorni_presofferto: int = 0)` | Calcola la data di fine pena con liberazione anticipata e presofferto. |
| `prescrizione_reato` | `prescrizione_reato(pena_massima_anni: float, data_commissione: str, interruzioni_giorni: int = 0, sospensioni_giorni: int = 0, tipo_reato: str = "delitto")` | Calcola la data di prescrizione del reato (artt. 157-161 c.p., Riforma Cartabia). |
| `pena_concordata` | `pena_concordata(pena_base_mesi: float, attenuanti_generiche: bool = True, diminuente_rito: bool = True)` | Calcola pena patteggiata con diminuzioni ex art. 444 c.p.p. |

---

## 13. Proprietà e successioni

**Modulo:** `src/tools/proprieta_successioni.py`
**Tag:** `proprieta`
**File dati:** `src/data/imposte_successione.json`, `src/data/usufrutto_coefficienti.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `calcolo_eredita` | `calcolo_eredita(massa_ereditaria: float, eredi: dict)` | Quote di legittima e quota disponibile per composizione del nucleo familiare. |
| `imposte_successione` | `imposte_successione(valore_beni: float, parentela: str, immobili: bool = False, prima_casa: bool = False)` | Imposta di successione con franchigie, aliquote e imposte ipocatastali. |
| `calcolo_usufrutto` | `calcolo_usufrutto(valore_piena_proprieta: float, eta_usufruttuario: int)` | Valore dell'usufrutto e della nuda proprietà per coefficienti AgE. |
| `calcolo_imu` | `calcolo_imu(rendita_catastale: float, categoria: str, aliquota_comunale: float = 0.86, prima_casa: bool = False)` | IMU annua e semestrale per categoria catastale e aliquota comunale. |
| `imposte_compravendita` | `imposte_compravendita(prezzo: float, tipo_immobile: str = "abitazione", prima_casa: bool = False, da_costruttore: bool = False, rendita_catastale: float \| None = None)` | Imposte acquisto immobile: registro, ipotecaria, catastale e IVA. |
| `pensione_reversibilita` | `pensione_reversibilita(pensione_de_cuius: float, beneficiari: dict, reddito_beneficiario: float = 0)` | Pensione di reversibilità INPS con quote e riduzione per cumulo redditi. |
| `grado_parentela` | `grado_parentela(relazione: str)` | Calcola grado di parentela con rilevanza successoria e fiscale. |
| `calcolo_valore_catastale` | `calcolo_valore_catastale(rendita_catastale: float, categoria: str, tipo: str = "successione")` | Valore catastale rivalutato per successione, compravendita o IMU. |
| `calcolo_superficie_commerciale` | `calcolo_superficie_commerciale(superficie_calpestabile: float, balconi: float = 0, terrazzi: float = 0, giardino: float = 0, cantina: float = 0, garage: float = 0)` | Superficie commerciale con coefficienti DPR 138/1998. |
| `cedolare_secca` | `cedolare_secca(canone_annuo: float, tipo_contratto: str = "libero", irpef_marginale: float = 38)` | Confronto convenienza cedolare secca vs. IRPEF ordinaria. |
| `imposta_registro_locazioni` | `imposta_registro_locazioni(canone_annuo: float, durata_anni: int = 4, tipo_contratto: str = "libero", prima_registrazione: bool = True)` | Imposta di registro per contratti di locazione abitativa. |
| `spese_condominiali` | `spese_condominiali(importo_totale: float, millesimi_proprietario: float, tipo_spesa: str = "ordinaria", piano: int = 0, immobile_locato: bool = False)` | Quota condominiale per millesimi e ripartizione proprietario/inquilino. |

---

## 14. Investimenti

**Modulo:** `src/tools/investimenti.py`
**Tag:** `investimenti`
**Tassazione:** 12,5% titoli di Stato (D.Lgs. 239/1996); 26% altri strumenti

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `rendimento_bot` | `rendimento_bot(valore_nominale: float, prezzo_acquisto: float, giorni_scadenza: int, commissione_pct: float = 0.0)` | Rendimento netto BOT (zero-coupon) con imposta sostitutiva 12,5%. |
| `rendimento_btp` | `rendimento_btp(valore_nominale: float, prezzo_acquisto: float, cedola_annua_pct: float, anni_scadenza: int, frequenza_cedola: int = 2)` | Rendimento netto BTP cedola fissa con flusso cedole e capital gain. |
| `pronti_termine` | `pronti_termine(capitale: float, tasso_lordo_pct: float, giorni: int, tipo_sottostante: str = "titoli_stato")` | Rendimento netto pronti contro termine (12,5% o 26% secondo sottostante). |
| `rendimento_buoni_postali` | `rendimento_buoni_postali(importo: float, tipo: str = "ordinario", anni: int = 10)` | Rendimento netto buoni fruttiferi postali con capitalizzazione per scaglioni. |
| `confronto_investimenti` | `confronto_investimenti(importo: float, investimenti: list[dict])` | Confronto rendimento netto tra strumenti finanziari diversi. |

---

## 15. Dichiarazione redditi

**Modulo:** `src/tools/dichiarazione_redditi.py`
**Tag:** `fiscale`
**File dati:** `src/data/irpef_scaglioni.json`
**Riferimento:** L. 199/2025 (scaglioni IRPEF 2026), TUIR (DPR 917/1986)

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `calcolo_irpef` | `calcolo_irpef(reddito_complessivo: float, tipo_reddito: str = "dipendente", deduzioni: float = 0, detrazioni_extra: float = 0)` | IRPEF con scaglioni 2026, detrazioni da lavoro e addizionali medie. |
| `regime_forfettario` | `regime_forfettario(ricavi: float, coefficiente_redditivita: float = 78, anni_attivita: int = 1, contributi_inps: float = 0)` | Imposta sostitutiva forfettaria 15% (5% startup) con confronto IRPEF ordinaria. |
| `calcolo_tfr` | `calcolo_tfr(retribuzione_annua_lorda: float, anni_servizio: int, rivalutazione_media_pct: float = 2.0)` | TFR lordo e netto con tassazione separata (art. 2120 c.c., artt. 17-19 TUIR). |
| `ravvedimento_operoso` | `ravvedimento_operoso(imposta_dovuta: float, giorni_ritardo: int, tipo: str = "omesso_versamento")` | Sanzioni ridotte e interessi per ravvedimento (D.Lgs. 87/2024 — sanzione base 25%). |
| `assegno_unico` | `assegno_unico(isee: float, n_figli: int, eta_figli: list[int] \| None = None, genitore_solo: bool = False)` | Assegno Unico Universale 2026 con maggiorazioni per età e genitore solo. |
| `detrazione_figli` | `detrazione_figli(reddito_complessivo: float, n_figli_over21: int, n_figli_disabili: int = 0)` | Detrazione IRPEF per figli a carico ≥21 anni (art. 12 TUIR). |
| `detrazione_coniuge` | `detrazione_coniuge(reddito_complessivo: float)` | Detrazione IRPEF per coniuge a carico (art. 12 TUIR). |
| `detrazione_altri_familiari` | `detrazione_altri_familiari(reddito_complessivo: float, n_familiari: int)` | Detrazione IRPEF per altri familiari a carico €750 (art. 12 TUIR). |
| `detrazione_lavoro_dipendente` | `detrazione_lavoro_dipendente(reddito_complessivo: float, giorni_lavoro: int = 365)` | Detrazione da lavoro dipendente (art. 13 TUIR) proporzionata ai giorni. |
| `detrazione_pensione` | `detrazione_pensione(reddito_complessivo: float, giorni: int = 365)` | Detrazione da pensione (art. 13 TUIR) proporzionata ai giorni. |
| `detrazione_assegno_coniuge` | `detrazione_assegno_coniuge(reddito_complessivo: float)` | Detrazione per assegno periodico da coniuge separato (art. 13 co. 5-bis TUIR). |
| `detrazione_canone_locazione` | `detrazione_canone_locazione(reddito_complessivo: float, tipo_contratto: str = "libero")` | Detrazione IRPEF per inquilini (art. 16 TUIR): libero, concordato, giovani under 31. |
| `acconto_irpef` | `acconto_irpef(imposta_anno_precedente: float, metodo: str = "storico")` | Calcola primo e secondo acconto IRPEF con scadenze (art. 17 DPR 435/2001). |
| `acconto_cedolare_secca` | `acconto_cedolare_secca(imposta_anno_precedente: float)` | Acconti cedolare secca (40% giugno, 60% novembre) con soglia €51,65. |
| `rateizzazione_imposte` | `rateizzazione_imposte(importo_totale: float, n_rate: int, data_prima_rata: str, tasso_interesse_annuo: float = 2.0)` | Piano di rateizzazione IRPEF da dichiarazione (2-7 rate, art. 20 D.Lgs. 241/1997). |

> **Nota:** La sezione 15 elenca 15 tool (incluso `rateizzazione_imposte`) anziché 14; il conteggio corretto per questa categoria è 15.

---

## 16. Utilità generali

**Modulo:** `src/tools/varie.py`
**Tag:** `utility`
**File dati:** `src/data/comuni.json`, `src/data/festivita.json`, `src/data/codici_ateco.json`, `src/data/violazioni_patente.json`

| Tool | Firma | Descrizione |
|------|-------|-------------|
| `codice_fiscale` | `codice_fiscale(cognome: str, nome: str, data_nascita: str, sesso: str, comune_nascita: str)` | Genera il codice fiscale italiano a 16 caratteri (algoritmo ufficiale DM 12/03/1974). |
| `decodifica_codice_fiscale` | `decodifica_codice_fiscale(codice_fiscale: str)` | Decodifica un codice fiscale estraendo dati anagrafici e validando il carattere di controllo. |
| `verifica_iban` | `verifica_iban(iban: str)` | Valida un IBAN italiano (27 caratteri) con algoritmo ISO 7064 mod 97. |
| `conta_giorni` | `conta_giorni(data_inizio: str, data_fine: str, tipo: str = "calendario")` | Conta giorni tra due date: calendario, lavorativi o solo festivi italiani. |
| `scorporo_iva` | `scorporo_iva(importo_ivato: float, aliquota: float = 22)` | Scorporo IVA da importo ivato: ricava imponibile e IVA separati. |
| `decurtazione_punti_patente` | `decurtazione_punti_patente(violazione: str)` | Punti decurtati, sanzione pecuniaria e sospensione per violazione CdS. |
| `tasso_alcolemico` | `tasso_alcolemico(sesso: str, peso_kg: float, unita_alcoliche: float, ore_trascorse: float, stomaco_pieno: bool = False)` | Tasso alcolemico teorico (formula Widmark) e fascia sanzionatoria art. 186 CdS. |
| `prescrizione_diritti` | `prescrizione_diritti(tipo_diritto: str, data_evento: str)` | Calcola data prescrizione di un diritto civile e verifica se già prescritto. |
| `calcolo_tempo_trascorso` | `calcolo_tempo_trascorso(data_inizio: str, data_fine: str \| None = None)` | Tempo trascorso tra due date in anni, mesi e giorni. |
| `verifica_partita_iva` | `verifica_partita_iva(partita_iva: str)` | Valida formalmente una partita IVA italiana (11 cifre, algoritmo di controllo). |
| `calcolo_eta_anagrafica` | `calcolo_eta_anagrafica(data_nascita: str, data_riferimento: str \| None = None)` | Età anagrafica esatta in anni, mesi e giorni con prossimo compleanno. |
| `ricerca_codici_ateco` | `ricerca_codici_ateco(keyword: str)` | Ricerca codici ATECO per parola chiave con coefficiente regime forfettario. |

---

## Riepilogo per tag

| Tag | Categoria | N. tool |
|-----|-----------|---------|
| `normativa` | Consultazione normativa | 7 |
| `giurisprudenza` | Giurisprudenza Cassazione | 4 |
| `privacy` | Garante GPDP + GDPR Compliance | 15 |
| `rivalutazione` | Rivalutazioni ISTAT | 11 |
| `interessi` | Tassi e interessi | 10 |
| `scadenze` | Scadenze processuali | 11 |
| `giudiziario` | Atti giudiziari | 23 |
| `parcelle_avv` | Parcelle avvocati | 12 |
| `parcelle_prof` | Parcelle professionisti | 11 |
| `danni` | Risarcimento danni | 7 |
| `penale` | Diritto penale | 5 |
| `proprieta` | Proprietà e successioni | 12 |
| `investimenti` | Investimenti | 5 |
| `fiscale` | Dichiarazione redditi | 15 |
| `utility` | Utilità generali | 12 |
| **Totale** | | **160+** |

---

## File dati (`src/data/`)

| File | Usato da | Contenuto |
|------|----------|-----------|
| `indici_foi.json` | `rivalutazioni_istat` | Serie storica indici FOI ISTAT |
| `tassi_legali.json` | `tassi_interessi`, `dichiarazione_redditi` | Tassi legali art. 1284 c.c. dal 2000 |
| `tassi_mora.json` | `tassi_interessi` | Tassi BCE per interessi di mora D.Lgs. 231/2002 |
| `tegm.json` | `tassi_interessi` | TEGM per categoria operazione (anti-usura) |
| `contributo_unificato.json` | `atti_giudiziari` | Tabella scaglioni contributo unificato 2025 |
| `parametri_forensi.json` | `fatturazione_avvocati` | Tabelle D.M. 55/2014 per fasi e scaglioni |
| `festivita.json` | `scadenze_termini`, `varie` | Festività nazionali fisse (L. 260/1949) |
| `tribunali_competenti.json` | `atti_giudiziari` | Mappa comuni → circondario giudiziario |
| `codici_ruolo.json` | `atti_giudiziari` | Codici materia per iscrizione a ruolo |
| `imposte_successione.json` | `proprieta_successioni` | Aliquote e franchigie D.Lgs. 346/1990 |
| `usufrutto_coefficienti.json` | `proprieta_successioni` | Coefficienti usufrutto per fascia d'età (DPR 131/1986) |
| `irpef_scaglioni.json` | `dichiarazione_redditi` | Scaglioni IRPEF 2026 (L. 199/2025) e detrazioni |
| `comuni.json` | `varie` | Codici catastali comuni italiani e stati esteri |
| `codici_ateco.json` | `varie` | Codici ATECO 2007 con coefficienti forfettario |
| `violazioni_patente.json` | `varie` | Violazioni CdS con punti e sanzioni |

---

## Convenzioni di precisione

I tool indicano nella docstring il livello di affidabilità del calcolo:

- **ESATTO** — calcolo matematico su dati normativi fissi (es. aliquote, scaglioni di legge)
- **INDICATIVO** — stima su dati variabili o medie (es. addizionali regionali, tabelle orientative)

I tool che generano documenti (bozze atti, notule, lettere) producono testo da revisionare
prima dell'uso — non sono documenti legali pronti alla firma.
