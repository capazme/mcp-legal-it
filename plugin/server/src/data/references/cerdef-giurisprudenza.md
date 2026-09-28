CeRDEF — BANCA DATI GIURISPRUDENZA TRIBUTARIA (def.finanze.it)
(Ministero dell'Economia e delle Finanze)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza_tributaria` | Ricerca nel database | query, tipo_provvedimento, ente, data_da, data_a, numero, criterio, ordinamento |
| `cerdef_leggi_provvedimento` | Testo completo provvedimento | guid |
| `ultime_sentenze_tributarie` | Più recenti degli ultimi 12 mesi (per data di emissione) | ente, tipo_provvedimento, max_risultati |

═══════════════════════════════════════════════════════════
ENTI (filtro per organo giudicante)
═══════════════════════════════════════════════════════════

| Chiave | Denominazione completa |
|--------|------------------------|
| `corte_suprema` | Corte di Cassazione |
| `cgt_primo_grado` | Corti di giustizia tributaria di primo grado (ex CTP) |
| `cgt_secondo_grado` | Corti di giustizia tributaria di secondo grado (ex CTR) |

Nota: CGT = Commissioni Tributarie rinominate dalla L. 130/2022 (ex CTP/CTR).
Il portale non ha un filtro per il solo primo grado: con `cgt_primo_grado`
si interrogano tutte le CGT e si tengono quelle di primo grado, quindi in
`cerca_giurisprudenza_tributaria` va indicato anche `data_da` (senza limite di
date la ricerca impiega circa 100 secondi).

═══════════════════════════════════════════════════════════
CRITERI DI RICERCA
═══════════════════════════════════════════════════════════

| Chiave | Effetto |
|--------|---------|
| `tutti` | Tutte le parole (default) |
| `almeno_uno` | Almeno una parola |
| `frase_esatta` | Frase esatta |
| `parole_adiacenti` | Parole adiacenti |
| `operatori_logici` | Con operatori logici |

Per cercare un provvedimento per numero usare il parametro `numero` (solo cifre).

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
1. ultime_sentenze_tributarie() → provvedimenti degli ultimi 12 mesi, dal più recente
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
- Una risposta anomala del portale è un **Errore** esplicito, mai "nessun
  risultato": "Nessun provvedimento" significa che CeRDEF non ne ha trovati
- Max risultati: 250 per richiesta (paginazione automatica via cookie di sessione)
