# Tool Catalog — legal-it MCP Server

Reference completa dei tool disponibili. Ogni skill carica solo questa sezione se necessario.

> **Formato chiamata**: `nome_tool(parametro1, parametro2)`

## Consultazione Normativa
| Tool | Uso |
|------|-----|
| `cite_law` | Testo vigente da Normattiva/EUR-Lex. **Sempre** prima di citare una norma. |
| `fetch_law_article` | Basso livello: parametri espliciti (act_type, article, date) |
| `fetch_law_annotations` | Solo annotazioni Brocardi |
| `cerca_brocardi` | Annotazioni complete: ratio, spiegazione, massime + riferimenti Cassazione |
| `download_law_pdf` | PDF ufficiale (EUR-Lex) o generato (Normattiva) |
| `fetch_act_index` | Indice articoli di un atto normativo |
| `fetch_full_act` | Testo integrale di un atto normativo |

## Giurisprudenza Cassazione (Italgiure)
| Tool | Uso |
|------|-----|
| `leggi_sentenza` | Testo completo sentenza (numero + anno noti) |
| `cerca_giurisprudenza` | Ricerca full-text (archivio 2020+). Parametri chiave: `modalita="esplora"` (solo distribuzione), `campo="dispositivo"` (solo dispositivo), `materia`, `sezione`, `tipo_provvedimento`. Strategia: esplora → filtra → leggi |
| `giurisprudenza_su_norma` | Sentenze che citano un articolo specifico. Parametri: `solo_sezioni_unite`, `anno_da`/`anno_a`, `archivio`. Preferire a `cerca_giurisprudenza` quando si parte da un articolo |
| `ultime_pronunce` | Ultime decisioni depositate |

## CONSOB
| Tool | Uso |
|------|-----|
| `cerca_delibere_consob` | Ricerca delibere/provvedimenti |
| `leggi_delibera_consob` | Testo completo delibera (numero noto) |
| `ultime_delibere_consob` | Ultime delibere pubblicate |

## Garante Privacy
| Tool | Uso |
|------|-----|
| `cerca_provvedimenti_garante` | Ricerca provvedimenti GPDP |
| `leggi_provvedimento_garante` | Testo completo provvedimento |
| `ultimi_provvedimenti_garante` | Ultimi provvedimenti pubblicati |

## Rivalutazione e Interessi
| Tool | Uso |
|------|-----|
| `rivalutazione_monetaria` | Rivalutazione ISTAT tra due date |
| `interessi_legali` | Interessi al tasso legale art. 1284 c.c. |
| `interessi_mora` | Interessi di mora D.Lgs. 231/2002 |
| `interessi_corso_causa` | Interessi in corso di causa |
| `calcolo_maggior_danno` | Maggior danno ex art. 1224 c.c. |
| `variazioni_istat` | Indici ISTAT FOI |
| `rivalutazione_tfr` | Rivalutazione TFR |

## Risarcimento Danni
| Tool | Uso |
|------|-----|
| `danno_biologico_micro` | Invalidita <= 9% (tabelle art. 139 CdA) |
| `danno_biologico_macro` | Invalidita > 9% (tabelle Milano) |
| `danno_non_patrimoniale` | Componente morale/esistenziale |
| `danno_parentale` | Danno da perdita del rapporto parentale |
| `menomazioni_plurime` | Calcolo con pluralita di menomazioni |
| `risarcimento_inail` | Risarcimento con indennizzo INAIL |

## Scadenze e Termini
| Tool | Uso |
|------|-----|
| `scadenza_processuale` | Termine generico |
| `scadenze_impugnazioni` | Termini impugnazione |
| `termini_processuali_civili` | Termini rito civile |
| `termini_183_190_cpc` | Termini Cartabia |
| `termini_memorie_repliche` | Memorie e repliche |
| `termini_esecuzioni` | Termini esecuzioni |
| `termini_deposito_ctu` | Termini CTU |
| `termini_separazione_divorzio` | Termini famiglia |

## Atti Giudiziari
| Tool | Uso |
|------|-----|
| `contributo_unificato` | CU per materia e valore |
| `decreto_ingiuntivo` | Calcolo decreto ingiuntivo |
| `atto_di_precetto` | Redazione precetto |
| `pignoramento_stipendio` | Calcolo quote pignorabili |
| `sfratto_morosita` | Procedura sfratto |

## Parcelle e Compensi
| Tool | Uso |
|------|-----|
| `parcella_avvocato_civile` | Compenso civile D.M. 55/2014 |
| `parcella_avvocato_penale` | Compenso penale |
| `parcella_stragiudiziale` | Compenso stragiudiziale |
| `parcella_volontaria_giurisdizione` | Compenso vol. giurisdizione |
| `preventivo_civile` | Preventivo causa civile |
| `preventivo_stragiudiziale` | Preventivo stragiudiziale |
| `nota_spese` | Nota spese completa |
| `fattura_avvocato` | Fattura avvocato |
| `compenso_ctu` | Compenso CTU |
| `compenso_curatore_fallimentare` | Compenso curatore |
| `spese_mediazione` | Spese mediazione |

## Proprieta e Successioni
| Tool | Uso |
|------|-----|
| `calcolo_eredita` | Quote ereditarie |
| `imposte_successione` | Imposte di successione |
| `imposte_compravendita` | Imposte compravendita immobiliare |
| `calcolo_usufrutto` | Valore usufrutto |
| `calcolo_imu` | Calcolo IMU |
| `calcolo_valore_catastale` | Valore catastale |
| `grado_parentela` | Grado di parentela |

## Diritto Penale
| Tool | Uso |
|------|-----|
| `prescrizione_reato` | Termine prescrizione reato |
| `aumenti_riduzioni_pena` | Calcolo pena con circostanze |
| `conversione_pena` | Conversione pene sostitutive |
| `fine_pena` | Data fine pena |
| `pena_concordata` | Patteggiamento |

## Fiscale
| Tool | Uso |
|------|-----|
| `calcolo_irpef` | IRPEF con detrazioni |
| `regime_forfettario` | Calcolo forfettario |
| `calcolo_tfr` | TFR lordo e netto |
| `ravvedimento_operoso` | Sanzioni ridotte |
| `cedolare_secca` | Cedolare secca locazioni |

## Privacy / GDPR
| Tool | Uso |
|------|-----|
| `analisi_base_giuridica` | Analisi basi giuridiche art. 6 GDPR |
| `verifica_necessita_dpia` | 9 criteri WP248 per DPIA |
| `genera_dpia` | DPIA completa con matrice rischi |
| `genera_registro_trattamenti` | Scheda art. 30 GDPR |
| `genera_informativa_privacy` | Informativa art. 13/14 GDPR |
| `genera_informativa_cookie` | Cookie policy |
| `genera_informativa_dipendenti` | Informativa dipendenti |
| `genera_informativa_videosorveglianza` | Informativa videosorveglianza |
| `genera_dpa` | Contratto art. 28 GDPR |
| `genera_notifica_data_breach` | Notifica data breach 72h |
| `valutazione_data_breach` | Valutazione rischio breach |
| `calcolo_sanzione_gdpr` | Stima sanzioni art. 83 GDPR |

## Redazione Atti (100 tipi)
| Tool | Uso |
|------|-----|
| `genera_modello_atto` | **ENTRY POINT** — metadati, campi, routing per qualsiasi tipo di atto. Usare `tipo_atto="catalogo"` per elenco completo, `tipo_atto="cerca"` con `parametri={"query": "..."}` per ricerca |
| `lista_categorie_atti` | Elenco categorie (atti_introduttivi, esecuzione, notifiche, attestazioni, procure, stragiudiziale, istanze, pct, preventivi, privacy) con conteggio |
| `decreto_ingiuntivo` | DI con tipo_credito: ordinario, professionale, condominiale, cambiale |
| `atto_di_precetto` | Precetto con interessi |
| `sfratto_morosita` | Sfratto con calcolo canoni |
| `procura_alle_liti` | Procura: generale, speciale, appello |
| `attestazione_conformita` | Attestazione PCT: estratto, copia_informatica, duplicato |
| `relata_notifica_pec` | Relata PEC generica |
| `sollecito_pagamento` | Sollecito/messa in mora |

## Utilita
| Tool | Uso |
|------|-----|
| `codice_fiscale` | Calcolo CF |
| `decodifica_codice_fiscale` | Decodifica CF |
| `verifica_iban` | Verifica IBAN |
| `scorporo_iva` | Scorporo IVA |
| `prescrizione_diritti` | Prescrizione diritti civili |
| `conta_giorni` | Conteggio giorni tra date |
| `ricerca_codici_ateco` | Ricerca codici ATECO |
