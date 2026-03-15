# Tool Catalog — legal-it MCP Server

Reference completa dei tool disponibili. Ogni skill carica solo questa sezione se necessario.

> **Formato chiamata**: `legal-it:nome_tool`

## Consultazione Normativa
| Tool | Uso |
|------|-----|
| `legal-it:cite_law` | Testo vigente da Normattiva/EUR-Lex. **Sempre** prima di citare una norma. |
| `legal-it:fetch_law_article` | Basso livello: parametri espliciti (act_type, article, date) |
| `legal-it:fetch_law_annotations` | Solo annotazioni Brocardi |
| `legal-it:cerca_brocardi` | Annotazioni complete: ratio, spiegazione, massime + riferimenti Cassazione |
| `legal-it:download_law_pdf` | PDF ufficiale (EUR-Lex) o generato (Normattiva) |
| `legal-it:fetch_act_index` | Indice articoli di un atto normativo |
| `legal-it:fetch_full_act` | Testo integrale di un atto normativo |

## Giurisprudenza Cassazione (Italgiure)
| Tool | Uso |
|------|-----|
| `legal-it:leggi_sentenza` | Testo completo sentenza (numero + anno noti) |
| `legal-it:cerca_giurisprudenza` | Ricerca full-text (archivio 2020+). Parametri chiave: `modalita="esplora"` (solo distribuzione), `campo="dispositivo"` (solo dispositivo), `materia`, `sezione`, `tipo_provvedimento`. Strategia: esplora → filtra → leggi |
| `legal-it:giurisprudenza_su_norma` | Sentenze che citano un articolo specifico |
| `legal-it:ultime_pronunce` | Ultime decisioni depositate |

## CONSOB
| Tool | Uso |
|------|-----|
| `legal-it:cerca_delibere_consob` | Ricerca delibere/provvedimenti |
| `legal-it:leggi_delibera_consob` | Testo completo delibera (numero noto) |
| `legal-it:ultime_delibere_consob` | Ultime delibere pubblicate |

## Garante Privacy
| Tool | Uso |
|------|-----|
| `legal-it:cerca_provvedimenti_garante` | Ricerca provvedimenti GPDP |
| `legal-it:leggi_provvedimento_garante` | Testo completo provvedimento |
| `legal-it:ultimi_provvedimenti_garante` | Ultimi provvedimenti pubblicati |

## Rivalutazione e Interessi
| Tool | Uso |
|------|-----|
| `legal-it:rivalutazione_monetaria` | Rivalutazione ISTAT tra due date |
| `legal-it:interessi_legali` | Interessi al tasso legale art. 1284 c.c. |
| `legal-it:interessi_mora` | Interessi di mora D.Lgs. 231/2002 |
| `legal-it:interessi_corso_causa` | Interessi in corso di causa |
| `legal-it:calcolo_maggior_danno` | Maggior danno ex art. 1224 c.c. |
| `legal-it:variazioni_istat` | Indici ISTAT FOI |
| `legal-it:rivalutazione_tfr` | Rivalutazione TFR |

## Risarcimento Danni
| Tool | Uso |
|------|-----|
| `legal-it:danno_biologico_micro` | Invalidita <= 9% (tabelle art. 139 CdA) |
| `legal-it:danno_biologico_macro` | Invalidita > 9% (tabelle Milano) |
| `legal-it:danno_non_patrimoniale` | Componente morale/esistenziale |
| `legal-it:danno_parentale` | Danno da perdita del rapporto parentale |
| `legal-it:menomazioni_plurime` | Calcolo con pluralita di menomazioni |
| `legal-it:risarcimento_inail` | Risarcimento con indennizzo INAIL |

## Scadenze e Termini
| Tool | Uso |
|------|-----|
| `legal-it:scadenza_processuale` | Termine generico |
| `legal-it:scadenze_impugnazioni` | Termini impugnazione |
| `legal-it:termini_processuali_civili` | Termini rito civile |
| `legal-it:termini_183_190_cpc` | Termini Cartabia |
| `legal-it:termini_memorie_repliche` | Memorie e repliche |
| `legal-it:termini_esecuzioni` | Termini esecuzioni |
| `legal-it:termini_deposito_ctu` | Termini CTU |
| `legal-it:termini_separazione_divorzio` | Termini famiglia |

## Atti Giudiziari
| Tool | Uso |
|------|-----|
| `legal-it:contributo_unificato` | CU per materia e valore |
| `legal-it:decreto_ingiuntivo` | Calcolo decreto ingiuntivo |
| `legal-it:atto_di_precetto` | Redazione precetto |
| `legal-it:pignoramento_stipendio` | Calcolo quote pignorabili |
| `legal-it:sfratto_morosita` | Procedura sfratto |

## Parcelle e Compensi
| Tool | Uso |
|------|-----|
| `legal-it:parcella_avvocato_civile` | Compenso civile D.M. 55/2014 |
| `legal-it:parcella_avvocato_penale` | Compenso penale |
| `legal-it:parcella_stragiudiziale` | Compenso stragiudiziale |
| `legal-it:parcella_volontaria_giurisdizione` | Compenso vol. giurisdizione |
| `legal-it:preventivo_civile` | Preventivo causa civile |
| `legal-it:preventivo_stragiudiziale` | Preventivo stragiudiziale |
| `legal-it:nota_spese` | Nota spese completa |
| `legal-it:fattura_avvocato` | Fattura avvocato |
| `legal-it:compenso_ctu` | Compenso CTU |
| `legal-it:compenso_curatore_fallimentare` | Compenso curatore |
| `legal-it:spese_mediazione` | Spese mediazione |

## Proprieta e Successioni
| Tool | Uso |
|------|-----|
| `legal-it:calcolo_eredita` | Quote ereditarie |
| `legal-it:imposte_successione` | Imposte di successione |
| `legal-it:imposte_compravendita` | Imposte compravendita immobiliare |
| `legal-it:calcolo_usufrutto` | Valore usufrutto |
| `legal-it:calcolo_imu` | Calcolo IMU |
| `legal-it:calcolo_valore_catastale` | Valore catastale |
| `legal-it:grado_parentela` | Grado di parentela |

## Diritto Penale
| Tool | Uso |
|------|-----|
| `legal-it:prescrizione_reato` | Termine prescrizione reato |
| `legal-it:aumenti_riduzioni_pena` | Calcolo pena con circostanze |
| `legal-it:conversione_pena` | Conversione pene sostitutive |
| `legal-it:fine_pena` | Data fine pena |
| `legal-it:pena_concordata` | Patteggiamento |

## Fiscale
| Tool | Uso |
|------|-----|
| `legal-it:calcolo_irpef` | IRPEF con detrazioni |
| `legal-it:regime_forfettario` | Calcolo forfettario |
| `legal-it:calcolo_tfr` | TFR lordo e netto |
| `legal-it:ravvedimento_operoso` | Sanzioni ridotte |
| `legal-it:cedolare_secca` | Cedolare secca locazioni |

## Privacy / GDPR
| Tool | Uso |
|------|-----|
| `legal-it:analisi_base_giuridica` | Analisi basi giuridiche art. 6 GDPR |
| `legal-it:verifica_necessita_dpia` | 9 criteri WP248 per DPIA |
| `legal-it:genera_dpia` | DPIA completa con matrice rischi |
| `legal-it:genera_registro_trattamenti` | Scheda art. 30 GDPR |
| `legal-it:genera_informativa_privacy` | Informativa art. 13/14 GDPR |
| `legal-it:genera_informativa_cookie` | Cookie policy |
| `legal-it:genera_informativa_dipendenti` | Informativa dipendenti |
| `legal-it:genera_informativa_videosorveglianza` | Informativa videosorveglianza |
| `legal-it:genera_dpa` | Contratto art. 28 GDPR |
| `legal-it:genera_notifica_data_breach` | Notifica data breach 72h |
| `legal-it:valutazione_data_breach` | Valutazione rischio breach |
| `legal-it:calcolo_sanzione_gdpr` | Stima sanzioni art. 83 GDPR |

## Utilita
| Tool | Uso |
|------|-----|
| `legal-it:codice_fiscale` | Calcolo CF |
| `legal-it:decodifica_codice_fiscale` | Decodifica CF |
| `legal-it:verifica_iban` | Verifica IBAN |
| `legal-it:scorporo_iva` | Scorporo IVA |
| `legal-it:prescrizione_diritti` | Prescrizione diritti civili |
| `legal-it:conta_giorni` | Conteggio giorni tra date |
| `legal-it:ricerca_codici_ateco` | Ricerca codici ATECO |
