CGUE — GIURISPRUDENZA CORTE DI GIUSTIZIA EUROPEA (CELLAR SPARQL)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI (4)
═══════════════════════════════════════════════════════════

| Tool | Quando usarlo |
|------|---------------|
| cerca_giurisprudenza_cgue(query, corte?, tipo_documento?, anno_da?, anno_a?, materia?) | Ricerca per keyword nei titoli italiani |
| leggi_sentenza_cgue(cellar_uri) | Testo completo via CELLAR URI (da risultati ricerca) |
| giurisprudenza_cgue_su_norma(riferimento, corte?, anno_da?) | Sentenze che citano una norma UE specifica |
| ultime_sentenze_cgue(corte?, tipo_documento?, materia?) | Ultime decisioni pubblicate |

═══════════════════════════════════════════════════════════
CORTI (parametro corte=)
═══════════════════════════════════════════════════════════

| Valore | Corte | Codice CELEX |
|--------|-------|--------------|
| corte_di_giustizia | Corte di Giustizia | CJ (sentenza), CC (ordinanza), CO (conclusioni AG) |
| tribunale | Tribunale dell'UE | TJ (sentenza), TO (ordinanza) |
| tutte | Tutte le corti | — (default) |

═══════════════════════════════════════════════════════════
TIPI DOCUMENTO (parametro tipo_documento=)
═══════════════════════════════════════════════════════════

| Valore | Descrizione |
|--------|-------------|
| sentenza | Sentenza (JUDG) |
| ordinanza | Ordinanza (ORDER) |
| conclusioni_ag | Conclusioni dell'Avvocato Generale (OPIN_AG) |
| tutti | Tutti i tipi (default) |

═══════════════════════════════════════════════════════════
MATERIE PREDEFINITE (parametro materia=)
═══════════════════════════════════════════════════════════

| Valore | Keywords incluse |
|--------|-----------------|
| iva | iva, imposta sul valore aggiunto, sesta direttiva |
| concorrenza | concorrenza, aiuti di stato, intesa, abuso di posizione dominante |
| ambiente | ambiente, rifiuti, emissioni, valutazione impatto ambientale |
| lavoro | lavoro, lavoratore, contratto di lavoro, licenziamento |
| protezione_dati | dati personali, protezione dei dati, gdpr, vita privata |
| appalti | appalto, appalti pubblici, gara, aggiudicazione |
| consumatori | consumatore, clausola abusiva, garanzia |

═══════════════════════════════════════════════════════════
FORMATO CELEX (giurisprudenza)
═══════════════════════════════════════════════════════════

Struttura: 6 {anno_caso} {codice_corte} {numero_caso_paddato}

Esempi:
- 62024CJ0008 → Sentenza CJ, caso C-8/2024
- 62023TJ0100 → Sentenza Tribunale, caso T-100/2023
- 62022CJ0262 → Sentenza CJ, caso C-262/2022

Settore 6 = giurisprudenza (case law)
Il CELEX con "_" (es. "_RES") = sommario, NON la decisione → filtrato automaticamente

═══════════════════════════════════════════════════════════
FORMATO ECLI
═══════════════════════════════════════════════════════════

ECLI:EU:C:{anno}:{numero}   → Corte di Giustizia
ECLI:EU:T:{anno}:{numero}   → Tribunale UE
ECLI:EU:F:{anno}:{numero}   → Tribunale della Funzione Pubblica (cessato)

Esempio: ECLI:EU:C:2026:210

═══════════════════════════════════════════════════════════
CELLAR URI — RECUPERO TESTO COMPLETO
═══════════════════════════════════════════════════════════

Il CELLAR URI è fornito in ogni risultato di ricerca.
Formato: http://publications.europa.eu/resource/cellar/{uuid}.{lang_code}

Esempio: http://publications.europa.eu/resource/cellar/44bb4d8a-21e1-11f1-8c3a-01aa75ed71a1.0006

IMPORTANTE: usare sempre leggi_sentenza_cgue(cellar_uri) — NON le URL EUR-Lex
(EUR-Lex ha protezione WAF/JS challenge, CELLAR risponde direttamente).

═══════════════════════════════════════════════════════════
WORKFLOW TIPO
═══════════════════════════════════════════════════════════

1. Ricerca per tema:
   cerca_giurisprudenza_cgue(query="rinvio pregiudiziale IVA", materia="iva")

2. Lettura testo completo:
   leggi_sentenza_cgue(cellar_uri="http://publications.europa.eu/resource/cellar/abc.0006")

3. Verifica norma citata:
   cite_law("art. 168 direttiva 2006/112")

4. Ricerca per norma specifica:
   giurisprudenza_cgue_su_norma(riferimento="art. 101 TFUE")

5. Ultime decisioni per materia:
   ultime_sentenze_cgue(materia="concorrenza", tipo_documento="sentenza")

═══════════════════════════════════════════════════════════
NORME UE FREQUENTI DA COMBINARE CON CGUE
═══════════════════════════════════════════════════════════

| Norma | cite_law reference | Materia CGUE |
|-------|-------------------|--------------|
| TFUE art. 101 | "art. 101 TFUE" | concorrenza |
| TFUE art. 107 | "art. 107 TFUE" | aiuti di stato |
| TFUE art. 267 | "art. 267 TFUE" | rinvio pregiudiziale |
| GDPR art. 5 | "art. 5 Reg. UE 2016/679" | protezione_dati |
| Direttiva IVA art. 168 | "art. 168 Direttiva 2006/112" | iva |
| Direttiva appalti art. 57 | "art. 57 Direttiva 2014/24" | appalti |
| Direttiva consumatori art. 6 | "art. 6 Direttiva 2011/83" | consumatori |
