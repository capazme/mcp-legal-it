"""MCP Prompts — GENERATED from content/skills/*/SKILL.md 'prompt:' blocks.

Do not edit by hand: run  python scripts/corpus/generate_prompts.py
23 guided legal workflow prompts, for MCP clients that support prompts.
"""

from src.server import mcp

_BODY_ANALISI_ARTICOLO = """\
# Analisi Articolo

Testo, ratio, giurisprudenza e collegamenti per un articolo di legge.

Formati accettati per il riferimento: "art. 13 GDPR", "art. 2043 c.c.", "art. 6 D.Lgs. 231/2001".

## Workflow

### 1. Testo vigente

Chiama `cite_law` con il riferimento normativo. Se modificato, recupera anche la versione precedente.

### 2. Annotazioni e giurisprudenza

Chiama `cerca_brocardi` per:
- Ratio legis
- Spiegazione dottrinale
- Massime giurisprudenziali
- Casistica applicativa

I riferimenti Cassazione nelle massime possono essere letti con `leggi_sentenza`.

### 3. Norme collegate

Con `cite_law` recupera:
- Articoli precedenti/successivi (contesto sistematico)
- Norme richiamate nel testo
- Disposizioni di attuazione
- Norme che richiamano questo articolo

### 4. Evoluzione storica

Dalle annotazioni:
- Versioni precedenti del testo
- Leggi di modifica con date
- Motivazioni delle modifiche (relazioni illustrative)

## Output atteso

### Testo vigente
> [da cite_law]

### Ratio legis
Scopo e funzione nell'ordinamento.

### Elementi costitutivi
- Presupposti (fattispecie astratta)
- Effetti giuridici
- Soggetti destinatari
- Ambito di applicazione

### Giurisprudenza
| Pronuncia | Principio | Rilevanza |
|-----------|-----------|-----------|
| ... | ... | ... |

### Norme collegate
| Norma | Relazione | Contenuto |
|-------|-----------|-----------|
| art. ... | richiamo espresso / sistematico | ... |

### Note operative
Indicazioni pratiche per l'applicazione della norma.

## Regole

- Il testo dell'articolo DEVE provenire da `cite_law`, non dalla memoria.
- Se Brocardi non ha annotazioni per questa norma, indicarlo espressamente.
- Distinguere tra interpretazione consolidata e orientamenti minoritari.
"""


@mcp.prompt(description='Analisi approfondita di un singolo articolo di legge: testo, ratio, giurisprudenza e collegamenti')
def analisi_articolo(riferimento_norma: str) -> str:
    return (
        "DATI:\n"
        f"- riferimento_norma: {riferimento_norma}\n"
        "\n"
        + _BODY_ANALISI_ARTICOLO
    )


_BODY_ANALISI_COSTITUZIONALE = """\
# Analisi Costituzionale

Esegui un'analisi delle pronunce della Corte Costituzionale sul tema indicato.

## Dati richiesti

- **tema** — il tema costituzionale da analizzare. Se non fornito, chiedilo.
- **tipo** (opzionale) — filtro tipo: sentenza / ordinanza (vuoto = entrambi).

## Workflow

### Fase 1 — Ricerca pronunce
Chiama `cerca_pronuncia_costituzionale(query=<tema>, tipo=<tipo>)` per individuare le
pronunce rilevanti (numero/anno, ECLI, tipo, snippet).
Se il tema riguarda un parametro costituzionale o una norma specifica (es. "art. 3 Costituzione",
"art. 23 legge 87/1953"), chiama `pronunce_cost_su_norma(riferimento="art. ...")` per le pronunce
che lo invocano come parametro.

### Fase 2 — Lettura pronunce chiave
Presenta i risultati in tabella e chiedi all'utente quali approfondire (human-in-the-loop).
Per ciascuna scelta, chiama `leggi_pronuncia_costituzionale(numero, anno)` per epigrafe, testo,
dispositivo, collegio ed ECLI.

### Fase 3 — Fondamento normativo
Per le norme oggetto/parametro citate nelle pronunce, chiama `cite_law(reference)` per il testo
vigente dalla fonte ufficiale.

### Fase 4 — Sintesi
Produci una sintesi che includa: principio affermato dalla Consulta, tipo di decisione
(accoglimento / rigetto / inammissibilità / interpretativa / additiva), parametri costituzionali
invocati, ed effetti sulla norma impugnata.

## Regole

- Usare esclusivamente `cerca_pronuncia_costituzionale` / `leggi_pronuncia_costituzionale` /
  `pronunce_cost_su_norma` — mai numeri di pronuncia a memoria né web search.
- Citare le pronunce con gli estremi ufficiali (Corte cost., sent./ord. n./anno, ECLI).
"""


@mcp.prompt(description='Analisi delle pronunce della Corte Costituzionale su un tema: ricerca, lettura sentenze/ordinanze chiave, parametri costituzionali invocati')
def analisi_costituzionale(tema: str, tipo: str = '') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- tipo: {tipo}\n"
        "\n"
        + _BODY_ANALISI_COSTITUZIONALE
    )


_BODY_ANALISI_DELIBERE_CONSOB = """\
# Analisi Delibere CONSOB

Ricerca, lettura e analisi delibere/provvedimenti CONSOB.

## Workflow

### 1. Ricerca delibere

Chiama `cerca_delibere_consob` con query e filtri (tipologia, argomento, date).

Valori ammessi per i filtri:
- Tipologia: delibere / comunicazioni / provvedimenti_urgenti / opa
- Argomento: abusi_di_mercato / intermediari / emittenti / mercati / cripto_attivita / crowdfunding

Se il tema e ampio, esegui piu ricerche con query diverse.

### 2. Lettura delibere chiave

Seleziona 2-3 delibere significative.
Per ciascuna: `leggi_delibera_consob` con numero.

Privilegia:
- Delibere recenti (ultimo biennio)
- Delibere con principi generali o sanzioni rilevanti
- Provvedimenti che riguardano fattispecie analoghe al tema richiesto

### 3. Quadro normativo

Per le norme richiamate: `cite_law`.

Fonti tipiche:
- TUF (D.Lgs. 58/1998) — Testo Unico della Finanza
- Reg. Emittenti (Reg. CONSOB 11971/1999)
- Reg. Intermediari (Reg. CONSOB 20307/2018)
- Regolamento Mercati (Reg. CONSOB 20249/2017)
- MAR (Reg. UE 596/2014) — abusi di mercato
- MiFID II (Dir. 2014/65/UE) / MiFIR (Reg. UE 600/2014)
- Reg. UE 2020/1503 — crowdfunding
- MiCA (Reg. UE 2023/1114) — cripto-attivita

### 4. Giurisprudenza (se pertinente)

Se le delibere citano pronunce giurisdizionali o se il tema ha risvolti contenziosi:
1. Esplora la distribuzione: `cerca_giurisprudenza` con il tema tra virgolette e `modalita` esplora.
2. Filtra con materia/sezione dai facets, poi leggi il testo completo delle decisioni chiave (tool leggi_sentenza, se disponibile).

Usa virgolette per frasi esatte.

## Output atteso

### Quadro regolatorio
Norme primarie e secondarie applicabili (testo da `cite_law`).

### Orientamento CONSOB
| Delibera | Data | Principio/Esito |
|----------|------|-----------------|
| ... | ... | ... |

### Sanzioni e misure
Tabella delle sanzioni comminate o delle misure adottate nei provvedimenti esaminati.

### Principi consolidati
Sintesi dei principi ricorrenti nelle delibere CONSOB sul tema.

### Indicazioni operative
Raccomandazioni pratiche derivanti dall'analisi.

## Regole

- Usare `cerca_delibere_consob` e `leggi_delibera_consob` per i provvedimenti CONSOB.
- Usare `cite_law` per TUTTE le norme citate — mai citare a memoria.
- Indicare espressamente il numero e la data di ogni delibera citata.
- Segnalare se l'orientamento e consolidato o in evoluzione.
"""


@mcp.prompt(description='Ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, regolamenti mercati finanziari')
def analisi_delibere_consob(tema: str, tipologia: str = '', argomento: str = '') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- tipologia: {tipologia}\n"
        f"- argomento: {argomento}\n"
        "\n"
        + _BODY_ANALISI_DELIBERE_CONSOB
    )


_BODY_ANALISI_GIURISPRUDENZA_AMMINISTRATIVA = """\
# Analisi Giurisprudenza Amministrativa

Esegui un'analisi della giurisprudenza amministrativa sul tema indicato.

## Dati richiesti

- **tema** — il tema amministrativo da analizzare. Se non fornito, chiedilo.
- **sede** (opzionale) — filtro sede: consiglio_di_stato / tar_lazio / tar_lombardia / ...

## Workflow

### Fase 1 — Ricerca provvedimenti
Chiama `cerca_giurisprudenza_amministrativa(query=<tema>)` — aggiungi `sede=<sede>` se indicato — per trovare
sentenze e provvedimenti di TAR e Consiglio di Stato.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia CdS e Adunanza Plenaria).
Per ciascuno, chiama `leggi_provvedimento_amm(sede, nrg, nome_file)` per il testo completo.

### Fase 3 — Giurisprudenza su norma (se pertinente)
Se il tema ruota attorno a una norma specifica, chiama
`giurisprudenza_amm_su_norma(riferimento="art. ...")` per trovare decisioni che la citano.

### Fase 4 — Quadro normativo
Per le norme citate nelle sentenze, chiama `cite_law(reference)` per il testo vigente.
Fonti tipiche: CPA (D.Lgs. 104/2010), D.Lgs. 36/2023 (Codice Appalti), TUEL (D.Lgs. 267/2000),
L. 241/1990, DPR 380/2001 (TU Edilizia).

### Fase 5 — Sintesi

## Analisi Giurisprudenza Amministrativa: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Sede | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Adunanza Plenaria / Sezioni Unite
Se si è pronunciata l'Adunanza Plenaria, riportare il principio di diritto.

### 4. Quadro Normativo
Norme amministrative rilevanti con testo da cite_law.

### 5. Indicazioni Operative
Raccomandazioni pratiche per il ricorrente/PA.

## Regole

- Usare `cerca_giurisprudenza_amministrativa` e `leggi_provvedimento_amm` per i provvedimenti.
- Usare `cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza a memoria.
"""


@mcp.prompt(description='Analisi giurisprudenza amministrativa: ricerca TAR/CdS, lettura provvedimenti e sintesi orientamenti')
def analisi_giurisprudenza_amministrativa(tema: str, sede: str = '') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- sede: {sede}\n"
        "\n"
        + _BODY_ANALISI_GIURISPRUDENZA_AMMINISTRATIVA
    )


_BODY_ANALISI_GIURISPRUDENZA_EUROPEA = """\
# Analisi Giurisprudenza Europea

Esegui un'analisi giurisprudenziale strutturata sulla Corte di Giustizia UE per il tema indicato.

## Dati richiesti

- **tema** — il tema di diritto UE da analizzare. Se non fornito, chiedilo.
- **corte** (opzionale, default `tutte`) — filtro corte: tutte / corte_di_giustizia / tribunale.

## Workflow

### Fase 1 — Ricerca sentenze
Chiama `cerca_giurisprudenza_cgue(query=<tema>, corte=<corte>)`
per trovare le sentenze CGUE pertinenti.

Se il tema riguarda una norma specifica del diritto UE (es. "art. 101 TFUE", "art. 7 GDPR"),
chiama `giurisprudenza_cgue_su_norma(riferimento="art. ... norma")` per trovare le decisioni
che interpretano quella norma.

### Fase 1b — Filtraggio per materia
Se il tema rientra in una delle materie predefinite (iva, concorrenza, ambiente, lavoro,
protezione_dati, appalti, consumatori), aggiungi il parametro materia alla ricerca per
ottenere risultati più mirati.

### Fase 2 — Lettura sentenze chiave
Seleziona le 2-3 sentenze più significative dalla ricerca.
Per ciascuna, chiama `leggi_sentenza_cgue(cellar_uri)` con il CELLAR URI riportato nel risultato.

Privilegia:
- Sentenze della Grande Sezione (massima autorità interpretativa)
- Sentenze recenti (ultimi 3 anni)
- Sentenze che citano principi generali del diritto UE

IMPORTANTE: usa `leggi_sentenza_cgue` con il CELLAR URI — NON usare EUR-Lex (ha WAF).

### Fase 3 — Fondamento normativo
Per le norme UE citate nelle sentenze lette, chiama `cite_law(reference)` per verificare
il testo vigente dalla fonte ufficiale. Fonti tipiche:
- TFUE: "art. 101 TFUE", "art. 267 TFUE" (rinvio pregiudiziale)
- Regolamenti UE: "Reg. UE 2016/679 art. 5" (GDPR), "Reg. UE 596/2014 art. 7" (MAR)
- Direttive: cercare il D.Lgs. italiano di recepimento

### Fase 4 — Sintesi strutturata

## Analisi Giurisprudenziale CGUE: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalla giurisprudenza CGUE sul tema.

### 2. Sentenze Chiave
| Caso | ECLI | Data | Principio |
|------|------|------|-----------|
| C-.../... | ECLI:EU:C:... | GG/MM/AAAA | ... |

### 3. Evoluzione dell'Interpretazione
Come si è evoluta l'interpretazione della CGUE nel tempo.

### 4. Impatto sull'Ordinamento Italiano
Come i principi CGUE influenzano l'applicazione del diritto italiano:
- Obbligo di interpretazione conforme (Mangold/Kücükdeveci)
- Disapplicazione norme nazionali incompatibili
- Responsabilità dello Stato per violazione diritto UE (Francovich)

### 5. Norme di Riferimento
Disposizioni UE rilevanti (testo da cite_law).

### 6. Indicazioni Operative
Raccomandazioni pratiche per avvocati e giuristi italiani.

## Regole

- Non citare mai numeri di sentenza a memoria — usa esclusivamente i risultati dei tool.
- Il CELLAR URI per leggere il testo completo è riportato in ogni risultato.
- Ogni affermazione deve essere supportata da una sentenza o norma verificata.
- Per norme citate, usare sempre cite_law — mai citare a memoria.
"""


@mcp.prompt(description='Analisi giurisprudenziale europea strutturata: ricerca CGUE/Tribunale UE, lettura sentenze chiave e sintesi orientamenti')
def analisi_giurisprudenza_europea(tema: str, corte: str = 'tutte') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- corte: {corte}\n"
        "\n"
        + _BODY_ANALISI_GIURISPRUDENZA_EUROPEA
    )


_BODY_ANALISI_GIURISPRUDENZIALE = """\
# Analisi giurisprudenziale

Sei un ricercatore giuridico specializzato. Conduci un'analisi degli orientamenti giurisprudenziali seguendo questo workflow.

## Fase 1 — Ricerca iniziale

### Se il tema riguarda un articolo specifico (es. "art. 2043 c.c.")
1. Chiama `giurisprudenza_articolo(riferimento="art. 2043 c.c.")` — questo tool recupera le massime Brocardi, usa il testo come query Italgiure e recupera direttamente le sentenze Cassazione citate.

### Se il tema e' generico (es. "responsabilita' del medico")
1. **Esplora**: `cerca_giurisprudenza(query="...", modalita="esplora")` per distribuzione materia/sezione/anno.
2. **Filtra**: applica i filtri piu' mirati basati sui facets.
3. **Cerca**: `cerca_giurisprudenza(query="...", materia="...", tipo_provvedimento="sentenza", max_risultati=10)`.

### Per ricerche cross-fonte
Se il tema coinvolge piu' giurisdizioni, usa `cerca_giurisprudenza_unificata(query="...", fonti="tutte")`.

## Fase 2 — Presentazione risultati e scelta utente (OBBLIGATORIA)

**STOP. NON chiamare `leggi_sentenza` prima di completare questa fase.**

Presenta i risultati in tabella:

| # | Estremi | Materia | Tipo | Anno |
|---|---------|---------|------|------|
| 1 | Cass. civ., sez. III, n. 10787/2024 | resp. civile | sentenza | 2024 |
| 2 | Cass. civ., sez. un., n. 5678/2023 | resp. civile | sentenza | 2023 |

Chiedi:

> **Quali sentenze vuoi approfondire?** Indica i numeri (es. 1, 3, 5) oppure scrivi "tutte" per leggere le prime 3.

**Attendi la risposta dell'utente prima di procedere.**

## Fase 3 — Approfondimento selettivo

Leggi SOLO le sentenze selezionate:
- Cassazione: `leggi_sentenza(numero, anno)`
- CeRDEF: `cerdef_leggi_provvedimento(guid)`
- GA: `leggi_provvedimento_amm(sede, nrg, nome_file)`
- CGUE: `leggi_sentenza_cgue(cellar_uri)`

Per articoli specifici: `cerca_brocardi(reference)` per ratio legis.

## Fase 4 — Fallback web (se necessario)

Se fonti istituzionali restituiscono errore o zero risultati:
1. Comunica: "La ricerca su [fonte] non ha prodotto risultati / non e' raggiungibile."
2. Chiedi: "Vuoi che cerchi informazioni tramite ricerca web?"
3. Se accetta: usa lo strumento di ricerca web disponibile nel tuo ambiente (es. una web search MCP) con query «giurisprudenza italiana Cassazione [tema]»
4. **Avvertenza obbligatoria**: "Risultati da fonti web non ufficiali. Numeri e principi devono essere verificati su fonti primarie."

## Fase 5 — Fondamento normativo

Verifica norme con `cite_law(reference)`. Mai citare a memoria.

## Fase 6 — Sintesi strutturata

Basandoti ESCLUSIVAMENTE sulle sentenze lette:
1. **Orientamento prevalente** con sentenze a supporto
2. **Evoluzione** nel tempo
3. **Contrasti** tra sezioni
4. **Sezioni Unite** se intervento risolutivo
5. **Norme di riferimento** verificate
6. **Tabella decisioni**: estremi, massima, orientamento

## Regole

1. Mai citare numeri di sentenza a memoria
2. Mai web search per sentenze senza consenso esplicito
3. Sempre esplorare prima di cercare
4. Sempre chiedere all'utente quali sentenze approfondire
5. Sempre leggere prima di sintetizzare
"""


@mcp.prompt(description='Analisi giurisprudenziale strutturata su un tema: ricerca su Italgiure, lettura decisioni chiave e sintesi orientamenti')
def analisi_giurisprudenziale(tema: str, archivio: str = 'tutti') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- archivio: {archivio}\n"
        "\n"
        + _BODY_ANALISI_GIURISPRUDENZIALE
    )


_BODY_ANALISI_SINISTRO = """\
# Analisi Sinistro

Quantificazione del danno NON PATRIMONIALE da sinistro stradale, sanitario o lavorativo.

**Principio (Cass. SS.UU. 26972/2008, «San Martino»)**: il danno non patrimoniale è UNITARIO
(art. 2059 c.c.). Biologico, morale ed esistenziale sono aspetti di un unico pregiudizio, NON
poste autonome da sommare. Le Tabelle di Milano liquidano un valore COMPLESSIVO che già incorpora
la componente morale.

## Workflow

### 1. Danno non patrimoniale (valore complessivo, unitario)

Chiama UNA SOLA VOLTA `danno_non_patrimoniale` con `percentuale_invalidita` (intero) e
`eta_vittima` (intero). Usa le Tabelle di Milano (macro >9%) o l'art. 139 Cod. Ass. (micro ≤9%).
Il valore restituito è GIÀ comprensivo del danno morale.

NON chiamare in aggiunta un tool di "danno morale" da sommare: duplicherebbe la componente già
inclusa (unitarietà del danno non patrimoniale).

### 2. Personalizzazione (solo se motivata da circostanze eccezionali)

Solo in presenza di circostanze peculiari documentate, applica una personalizzazione ENTRO i tetti
massimi della tabella (calcolata sulla componente biologica), tramite `personalizzazione_pct`. NON
è una seconda voce cumulata: è un incremento del valore tabellare entro i limiti. In base al tipo:
- **Stradale**: dinamica relazionale (mobilità, lavoro, sport)
- **Sanitario**: sofferenza iatrogena da errore medico
- **Lavoro**: incidenza sulla capacità lavorativa specifica

### 3. Rivalutazione monetaria (debito di valore)

Chiama `rivalutazione_monetaria` dalla data del sinistro a oggi.

### 4. Interessi compensativi (Cass. SS.UU. 1712/1995)

NON calcolare gli interessi sul capitale INTERAMENTE rivalutato all'attualità: sarebbe la
sovra-compensazione censurata dalle SS.UU. Calcolali sulla somma PROGRESSIVAMENTE rivalutata anno
per anno o, in via semplificata, sul VALORE MEDIO tra somma originaria e somma finale rivalutata:
chiama `interessi_legali` sulla base `(somma_originaria + somma_rivalutata) / 2`.

## Output atteso

| Voce | Importo |
|------|---------|
| Danno non patrimoniale (valore complessivo, morale incluso) | ... |
| Personalizzazione (se ricorrente, entro i tetti) | ... |
| Rivalutazione monetaria | ... |
| Interessi compensativi (su base media/progressiva) | ... |
| **TOTALE RISARCIMENTO** | **...** |

## Avvertenze da includere

- Danno non patrimoniale UNITARIO: una sola voce comprensiva del morale (SS.UU. 26972/2008) — non sommare biologico e morale come poste distinte.
- Interessi compensativi sulla somma progressivamente rivalutata / valore medio, MAI sul capitale già interamente rivalutato (SS.UU. 1712/1995).
- Valori INDICATIVI (Tabelle di Milano macro >9% / art. 139 Cod. Ass. micro ≤9%) — non sostituiscono la valutazione medico-legale.
- Per ITT/ITP, danno emergente e lucro cessante servono dati aggiuntivi.
- Citare sempre la fonte tabellare e normativa.
"""


@mcp.prompt(description='Analisi completa sinistro stradale/sanitario/lavoro con quantificazione danni')
def analisi_sinistro(tipo_sinistro: str, percentuale_invalidita: float, eta_vittima: int) -> str:
    return (
        "DATI:\n"
        f"- tipo_sinistro: {tipo_sinistro}\n"
        f"- percentuale_invalidita: {percentuale_invalidita}\n"
        f"- eta_vittima: {eta_vittima}\n"
        "\n"
        + _BODY_ANALISI_SINISTRO
    )


_BODY_ANALISI_TRIBUTARIA = """\
# Analisi Tributaria

Esegui un'analisi della giurisprudenza tributaria sul tema indicato.

## Dati richiesti

- **tema** — il tema fiscale da analizzare. Se non fornito, chiedilo.
- **ente** (opzionale) — filtro ente: corte_suprema / cgt_primo_grado / cgt_secondo_grado.

## Workflow

### Fase 1 — Ricerca CeRDEF
Chiama `cerca_giurisprudenza_tributaria(query=<tema>)` — aggiungi `ente=<ente>` se indicato — per trovare
sentenze e provvedimenti nella banca dati del MEF.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia Cassazione se presente).
Per ciascuno, chiama `cerdef_leggi_provvedimento(guid)` per leggere massima e testo completo.

### Fase 3 — Quadro normativo
Per le norme tributarie citate nelle sentenze, chiama `cite_law(reference)` per il testo vigente.
Fonti tipiche: TUIR (DPR 917/1986), D.Lgs. 546/1992, DPR 633/1972 (IVA), D.Lgs. 472/1997.

### Fase 4 — Giurisprudenza Cassazione (se pertinente)
Se emergono principi di diritto rilevanti, cerca anche su Italgiure:
`cerca_giurisprudenza(query="\\"<tema>\\"", archivio="civile")` per sezione tributaria.

### Fase 5 — Sintesi

## Analisi Giurisprudenza Tributaria: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Ente | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Quadro Normativo
Norme tributarie rilevanti con testo da cite_law.

### 4. Indicazioni Operative
Raccomandazioni pratiche per il contribuente/professionista.

## Regole

- Usare `cerca_giurisprudenza_tributaria` e `cerdef_leggi_provvedimento` per i provvedimenti CeRDEF.
- Usare `cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza o GUID a memoria.
"""


@mcp.prompt(description='Analisi giurisprudenza tributaria: ricerca CeRDEF, lettura provvedimenti e sintesi orientamenti fiscali')
def analisi_tributaria(tema: str, ente: str = '') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- ente: {ente}\n"
        "\n"
        + _BODY_ANALISI_TRIBUTARIA
    )


_BODY_ATTUAZIONE_DIRETTIVA = """\
# Attuazione Direttiva

Ricostruisci il recepimento italiano della direttiva UE indicata.

## Dati richiesti

- **direttiva** — CELEX es. "32019L0790" oppure "direttiva (UE) 2019/790". Se non fornito, chiedilo.

## Workflow

### Fase 1 — Atto di attuazione italiano
Chiama `get_italian_implementation(direttiva=<direttiva>)` per gli atti italiani di trasposizione
(tipo, numero, GU n./data, entrata in vigore, titolo, CELEX MNE). Se la direttiva è in realtà un
REGOLAMENTO, il tool lo segnala: i regolamenti sono direttamente applicabili e NON hanno atto di
recepimento — riportalo.

### Fase 2 — Testo dell'atto italiano
Per ciascun atto di attuazione chiama `cite_law(reference)` (es. "D.Lgs. 177/2021") per il testo
vigente da Normattiva. (CELLAR fornisce solo i metadati del recepimento, non il testo nazionale.)

### Fase 3 — Base UE e giurisprudenza
Per la direttiva, chiama `cite_law` sul testo UE e `giurisprudenza_cgue_su_norma(riferimento=...)` per
le pronunce della Corte di Giustizia che la interpretano. (Percorso inverso: da un atto italiano alla
direttiva, usa `get_eu_basis(atto="...")`.)

### Fase 4 — Sintesi
Riporta: direttiva → atto/i italiano/i di attuazione (con estremi e GU), termine di trasposizione,
eventuale ritardo/incompletezza emersa, e principali pronunce CGUE collegate.

## Regole

- Un atto nazionale può recepire più direttive e viceversa: riportarli tutti, senza assumere 1:1.
- Distinguere metadati di recepimento (CELLAR) dal testo vigente (Normattiva).
- Usare i tool, mai estremi a memoria.
"""


@mcp.prompt(description="Recepimento di una direttiva UE in Italia: dalla direttiva all'atto di attuazione (Normattiva) e alla giurisprudenza CGUE collegata")
def attuazione_direttiva(direttiva: str) -> str:
    return (
        "DATI:\n"
        f"- direttiva: {direttiva}\n"
        "\n"
        + _BODY_ATTUAZIONE_DIRETTIVA
    )


_BODY_CALCOLO_PARCELLA = """\
# Calcolo Parcella

Compenso avvocato D.M. 55/2014 con nota spese.

## Workflow

### 1. Calcolo compenso

| Tipo | Tool |
|------|------|
| Civile | `parcella_avvocato_civile` |
| Penale | `parcella_avvocato_penale` |
| Stragiudiziale | `parcella_stragiudiziale` |
| Vol. giurisdizione | `parcella_volontaria_giurisdizione` |

Le fasi compensate variano con il tipo di attività — la tabella di output va adeguata di conseguenza.

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

### 2. Nota spese

Chiama `nota_spese` per il prospetto: compenso per fase, spese generali (15%), CPA (4%), IVA (22%), contributo unificato e bolli (se giudiziale).

## Output atteso

| Fase | Minimo | Medio | Massimo |
|------|--------|-------|---------|
| Studio | ... | ... | ... |
| Introduttiva | ... | ... | ... |
| Istruttoria | ... | ... | ... |
| Decisionale | ... | ... | ... |
| **Totale** | **...** | **...** | **...** |

### Nota Spese (su compenso medio)

| Voce | Importo |
|------|---------|
| Compenso | € ... |
| Spese generali (15%) | € ... |
| CPA (4%) | € ... |
| Imponibile IVA | € ... |
| IVA (22%) | € ... |
| **Totale parcella** | **€ ...** |

## Note

- I compensi si riferiscono al D.M. 55/2014 come da ultimo aggiornato dal D.M. 147/2022.
- Indicare sempre lo scaglione di valore applicato.
- In sede di liquidazione giudiziale i massimi sono derogabili in casi di particolare complessità, ma i minimi sono inderogabili (D.M. 55/2014 come modificato dal D.M. 147/2022).
"""


@mcp.prompt(description='Calcolo parcella avvocato per attività civile, penale o stragiudiziale')
def calcolo_parcella(tipo_attivita: str, valore_causa: float) -> str:
    return (
        "DATI:\n"
        f"- tipo_attivita: {tipo_attivita}\n"
        f"- valore_causa: {valore_causa}\n"
        "\n"
        + _BODY_CALCOLO_PARCELLA
    )


_BODY_CAUSA_CIVILE = """\
# Causa Civile

Pianificazione completa: costi, scadenze, preventivo.

## Workflow

### 1. Contributo unificato

Chiama `contributo_unificato` con valore_causa, tipo_procedimento (es. cognizione, lavoro, monitorio) e grado (primo/appello/cassazione).

Verifica eventuali esenzioni (es. cause di lavoro sotto soglia, procedimenti di volontaria giurisdizione).

### 2. Scadenze processuali

Chiama `scadenza_processuale` per i termini in base al rito:
- **Ordinario**: comparsa risposta (70gg), memorie art. 171-ter c.p.c.
- **Sommario**: costituzione resistente, mutamento rito
- **Lavoro**: ricorso, memoria difensiva, note autorizzate

Sospensione feriale (1-31 agosto): indicala solo se il rito o la materia vi è soggetto — non opera, tra l'altro, in materia di lavoro, procedimenti cautelari e alimenti.

### 3. Impugnazioni

Chiama `scadenze_impugnazioni`:
- Primo -> appello: 30gg (breve) / 6 mesi (lungo)
- Appello -> cassazione: 60gg (breve) / 6 mesi (lungo)
- Revocazione, opposizione di terzo se pertinenti

### 4. Preventivo

Chiama `preventivo_civile` con range compenso per fase.

## Formato output

```markdown
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
```

## Note
- Indicare i rischi di soccombenza e regime spese (art. 91 c.p.c.)
- Valutare la mediazione obbligatoria se applicabile (D.Lgs. 28/2010, materie estese dalla riforma Cartabia)
- Segnalare se il rito è soggetto a negoziazione assistita (D.L. 132/2014)
"""


@mcp.prompt(description='Pianificazione causa civile: contributo unificato, scadenze, impugnazioni e preventivo')
def causa_civile(valore_causa: float, rito: str, grado: str) -> str:
    return (
        "DATI:\n"
        f"- valore_causa: {valore_causa}\n"
        f"- rito: {rito}\n"
        f"- grado: {grado}\n"
        "\n"
        + _BODY_CAUSA_CIVILE
    )


_BODY_COMPLIANCE_PRIVACY = """\
# Compliance Privacy GDPR

Assessment completo: base giuridica, DPIA, registro, informativa, DPA.

## Workflow

### 1. Analisi base giuridica

Chiama `analisi_base_giuridica` con tipo_trattamento e contesto.
Valori ammessi per `contesto`: B2C / B2B / dipendenti / pubblica_amministrazione / sanita / profilazione.
Identifica la base ex art. 6 GDPR. Se dati particolari (art. 9), attiva flag.
Annota la base consigliata per i passi successivi.

### 2. Verifica necessita DPIA

Chiama `verifica_necessita_dpia` con i criteri applicabili.
Valuta: profilazione, dati sensibili, monitoraggio sistematico, larga scala, soggetti vulnerabili, nuove tecnologie, scoring, incrocio dataset.

Se >= 2 criteri soddisfatti (WP248): DPIA obbligatoria.

### 2b. DPIA (se necessaria)

Chiama `genera_dpia` con rischi e misure di mitigazione.
Documenta la matrice dei rischi e il rischio residuo.

### 3. Registro trattamenti

Chiama `genera_registro_trattamenti` per scheda art. 30 GDPR.
Usa la base giuridica identificata al passo 1.

### 4. Informativa privacy

Chiama `genera_informativa_privacy` per informativa art. 13 GDPR.
Includi tutte le finalità, basi giuridiche, categorie di dati e destinatari.

Varianti disponibili:
- `genera_informativa_cookie` (cookie policy)
- `genera_informativa_dipendenti` (dipendenti)
- `genera_informativa_videosorveglianza` (videosorveglianza)

### 5. DPA (se responsabili esterni)

Se il trattamento coinvolge responsabili esterni (fornitori IT, cloud, commercialista, ecc.),
chiama `genera_dpa` per contratto art. 28 GDPR.

## Output atteso

Report intestato «Assessment Compliance GDPR — `titolare`», con le sezioni seguenti.

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
Scheda art. 30 con tutti i campi obbligatori.

### 4. Informativa Privacy
Testo completo dell'informativa art. 13 GDPR pronto per l'uso.

### 5. DPA
Contratto art. 28 GDPR (se applicabile).

### Checklist compliance
- [ ] Base giuridica identificata e documentata
- [ ] DPIA eseguita (se necessaria)
- [ ] Registro trattamenti aggiornato
- [ ] Informativa privacy redatta e pubblicata
- [ ] DPA stipulati con responsabili
- [ ] Misure di sicurezza (art. 32)
- [ ] Procedura data breach (artt. 33-34)

## Avvertenze

- Il presente assessment è uno strumento di supporto e non sostituisce la consulenza legale specializzata.
- Verificare sempre la normativa nazionale integrativa (D.Lgs. 196/2003 come modificato dal D.Lgs. 101/2018).
- Per trattamenti su larga scala o ad alto rischio, consultare il DPO e valutare una consultazione preventiva (art. 36 GDPR).
"""


@mcp.prompt(description='Workflow completo compliance privacy GDPR: analisi base giuridica, DPIA, registro, informativa e DPA')
def compliance_privacy(titolare: str, tipo_trattamento: str, contesto: str) -> str:
    return (
        "DATI:\n"
        f"- titolare: {titolare}\n"
        f"- tipo_trattamento: {tipo_trattamento}\n"
        f"- contesto: {contesto}\n"
        "\n"
        + _BODY_COMPLIANCE_PRIVACY
    )


_BODY_CONFRONTO_NORME = """\
# Confronto Norme

Differenze, sovrapposizioni, prevalenza e coordinamento.

## Workflow

### 1. Recupero testi

Chiama `cite_law` per ciascuna norma. Per annotazioni: `cerca_brocardi`.

### 2. Analisi comparativa

Confronta su: ambito oggettivo, soggettivo, presupposti, effetti, sanzioni.

### 3. Rapporto tra le norme

- **Specialita** (art. 15 c.p. / lex specialis): una e speciale rispetto all'altra?
- **Successione** (lex posterior): una ha abrogato l'altra?
- **Gerarchia**: una prevale per rango (Costituzione > legge > regolamento)?
- **Concorso**: si applicano entrambe contemporaneamente?
- **Complementarieta**: disciplinano aspetti diversi della stessa materia?

### 4. Giurisprudenza sul coordinamento

Dalle annotazioni, individua pronunce sul rapporto tra le norme.

## Formato output

Apri con il titolo «Confronto: `norma_1` vs. `norma_2`», poi:

### Testi a confronto

| Elemento | `norma_1` | `norma_2` |
|----------|-----------|-----------|
| Fonte | ... | ... |
| Ambito oggettivo | ... | ... |
| Ambito soggettivo | ... | ... |
| Presupposti | ... | ... |
| Effetti | ... | ... |
| Sanzioni | ... | ... |

### Rapporto tra le norme

Analisi del criterio di prevalenza applicabile.

### Aree di sovrapposizione

Casi in cui entrambe le norme sono potenzialmente applicabili e come si coordinano.

### Orientamento giurisprudenziale

Come la giurisprudenza ha risolto i conflitti tra queste norme.

### Conclusioni operative

Indicazione pratica su quale norma applicare e in quali circostanze.

## Regole

- Entrambi i testi DEVONO provenire da `cite_law`.
- Non dare per scontata la prevalenza di una norma — argomentare il criterio.
- Se il rapporto e controverso, esporre le diverse tesi.
"""


@mcp.prompt(description='Confronto tra due o più norme: differenze, sovrapposizioni, prevalenza e coordinamento')
def confronto_norme(norma_1: str, norma_2: str, contesto: str = '') -> str:
    return (
        "DATI:\n"
        f"- norma_1: {norma_1}\n"
        f"- norma_2: {norma_2}\n"
        f"- contesto: {contesto}\n"
        "\n"
        + _BODY_CONFRONTO_NORME
    )


_BODY_MAPPATURA_NORMATIVA = """\
# Mappatura Normativa

Mappa completa delle fonti per settore/attivita, organizzata per gerarchia.

## Workflow

### 1. Fonti per livello

Per ogni livello, chiama `cite_law` su ogni articolo fondamentale:
1. **Costituzione** — identifica gli articoli della Costituzione rilevanti e chiama `cite_law` per ciascuno (es. art. 41, 42, 117 Cost.)
2. **UE** — regolamenti e direttive con D.Lgs. di recepimento: per i regolamenti (direttamente applicabili) chiama `cite_law` per gli articoli chiave; per le direttive identifica il D.Lgs. di recepimento italiano
3. **Nazionale** — mappa: codici applicabili (civile, penale, procedura, settoriali), testi unici / codici di settore, leggi ordinarie e decreti legislativi, decreti legge convertiti
4. **Secondarie** — decreti ministeriali (D.M.), regolamenti di autorita indipendenti (Garante Privacy, AGCM, CONSOB, ecc.), linee guida e provvedimenti generali, standard tecnici (ISO, UNI) se vincolanti

### 2. Fonti autorita vigilanza

- Settori finanziari: `cerca_delibere_consob`
- Privacy: `cerca_provvedimenti_garante`

Per le delibere CONSOB chiave, approfondisci leggendone il testo integrale con `leggi_delibera_consob`.

### 3. Matrice adempimenti

Per ogni fonte, estrai gli obblighi concreti:
- Adempimenti documentali
- Obblighi di comunicazione / notifica
- Registri e tenuta documentale
- Formazione e designazioni
- Termini e scadenze

| Obbligo | Fonte | Soggetto | Termine | Sanzione |
|---------|-------|----------|---------|----------|
| ... | ... | ... | ... | ... |

## Formato output

Intitola l'output `Mappa Normativa:` seguito dal `settore` indicato.

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

| Fonte | Autorita | Oggetto |
|-------|----------|---------|
| ... | ... | ... |

Segue la Matrice adempimenti (tabella del punto 3 del workflow), poi:

### Checklist Operativa

Elenco ordinato per priorita degli adempimenti da verificare.

## Regole

- Usare `cite_law` per TUTTI gli articoli citati nella mappa.
- Indicare la data di entrata in vigore di ciascuna fonte.
- Segnalare le norme in fase di modifica o revisione solo se la modifica risulta gia pubblicata in Gazzetta Ufficiale (verificabile con i tool); non segnalare riforme pendenti o de lege ferenda.
- Per settori regolati (privacy, bancario, sanitario), includere sempre le fonti dell'autorita di vigilanza.
"""


@mcp.prompt(description='Mappatura del quadro normativo completo per un settore o attività: tutte le fonti applicabili organizzate per livello')
def mappatura_normativa(settore: str, attivita_specifica: str = '') -> str:
    return (
        "DATI:\n"
        f"- settore: {settore}\n"
        f"- attivita_specifica: {attivita_specifica}\n"
        "\n"
        + _BODY_MAPPATURA_NORMATIVA
    )


_BODY_NOVITA_CONSOB = """\
# Novita CONSOB

Ultime delibere con sintesi orientamenti.

## Workflow

### 1. Ultime delibere

Chiama `ultime_delibere_consob` con eventuali filtri (tipologia, argomento).

### 2. Approfondimento

Per le 2-3 delibere piu rilevanti: `leggi_delibera_consob` con numero.

### 3. Quadro normativo

Per le norme richiamate: `cite_law`.

## Output atteso

### Panoramica
Tendenze emergenti dai provvedimenti recenti.

### Per ciascuna delibera letta:

#### Delibera n. ... del GG/MM/AAAA
- **Oggetto**
- **Norme di riferimento**
- **Decisione/Sanzione**
- **Rilevanza pratica**

### Tendenze e indicazioni
Sintesi orientamenti dalle delibere piu recenti.

## Regole

- Usare esclusivamente i tool CONSOB per i provvedimenti — mai citare a memoria.
- Per le norme, usare sempre `cite_law`.
- Indicare data e numero di ogni delibera.
"""


@mcp.prompt(description='Ultime novità CONSOB: delibere recenti per tipologia o argomento con sintesi degli orientamenti')
def novita_consob(tipologia: str = '', argomento: str = '') -> str:
    return (
        "DATI:\n"
        f"- tipologia: {tipologia}\n"
        f"- argomento: {argomento}\n"
        "\n"
        + _BODY_NOVITA_CONSOB
    )


_BODY_ORIENTAMENTO_GIURISPRUDENZIALE = """\
# Orientamento Giurisprudenziale

Costruisci una mappa DESCRITTIVA degli orientamenti della Cassazione.

## Dati richiesti

- **riferimento** — una norma, es. "art. 2043 c.c.", oppure un principio/massima. Se non fornito, chiedilo.
- **archivio** (opzionale, default `tutti`) — filtro archivio: civile / penale / tutti.

## Workflow

### Fase 1 — Mappa orientamenti
Se il riferimento è una NORMA, chiama `mappa_orientamento(riferimento=<riferimento>, archivio=<archivio>)`
(orchestratore: ancora le massime Brocardi, recupera le decisioni successive, isola le Sezioni Unite).
In alternativa: `orientamento_su_norma(...)` per una norma o `orientamento_su_principio(principio="...")`
per un principio espresso a parole.

### Fase 2 — Lettura decisioni rappresentative
Presenta la distribuzione (Sezioni Unite, cluster per sezione, trend per anno, segnali testuali di
contrasto/conformità) e chiedi all'utente quali decisioni leggere. Per ciascuna scelta usa
`leggi_sentenza(numero, anno)`.

### Fase 3 — Fondamento normativo
Per le norme rilevanti chiama `cite_law(reference)`.

### Fase 4 — Sintesi
Riporta: orientamento prevalente, eventuali contrasti segnalati, intervento delle Sezioni Unite (se
presente) ed evoluzione temporale.

## Regole — IMPORTANTE

- La mappa è DESCRITTIVA (distribuzioni, segnali testuali "contrasto/consolidato"), NON una previsione
  di overruling né una classifica dell'indirizzo "vincente" (art. 15 L. 132/2025 — ogni decisione su
  interpretazione, fatti e prove è riservata al magistrato).
- I segnali di (dis)conformità indicano che la decisione DISCUTE il contrasto/la conformità, non che essa
  conforma/diverge in fatto. Etichettali come "decisioni che segnalano...".
- Copertura full-text Italgiure ~dal 2020; segnalare il limite temporale.
- Mai numeri di sentenza a memoria.
"""


@mcp.prompt(description='Mappa descrittiva degli orientamenti di legittimità su una norma o un principio: conformi vs contrasti, Sezioni Unite, evoluzione temporale')
def orientamento_giurisprudenziale(riferimento: str, archivio: str = 'tutti') -> str:
    return (
        "DATI:\n"
        f"- riferimento: {riferimento}\n"
        f"- archivio: {archivio}\n"
        "\n"
        + _BODY_ORIENTAMENTO_GIURISPRUDENZIALE
    )


_BODY_PARERE_LEGALE = """\
# Workflow Parere Legale

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Analisi del quesito
Identifica:
- **Questione giuridica** principale
- **Norme potenzialmente applicabili** (codice civile, leggi speciali, regolamenti UE)
- **Parti coinvolte** e loro posizioni
- **Fatti rilevanti**

## Step 2 — Verifica normativa
Per OGNI norma che intendi citare nel parere:
1. Chiama `cite_law` con il riferimento (es. "art. X legge Y") per ottenere il testo vigente
2. Se serve approfondimento dottrinale: chiama `cerca_brocardi`

MAI citare una norma a memoria. Ogni citazione deve avere un `cite_law` corrispondente.

## Step 3 — Ricerca giurisprudenziale
Per le questioni controverse o con orientamenti divergenti:
1. Chiama `cerca_giurisprudenza` con il tema specifico per trovare le sentenze rilevanti
2. Per le top 2-3 sentenze piu pertinenti: chiama `leggi_sentenza` con numero e anno per il testo integrale
3. Identifica l'orientamento prevalente (consolidato, in evoluzione, contrasto)

## Step 4 — Redazione del parere
Struttura il parere nelle seguenti sezioni:

### FATTO
Riassumi i fatti rilevanti come esposti dal cliente.

### DIRITTO
Esponi il quadro normativo applicabile, citando:
- Articoli di legge (con testo recuperato da `cite_law`)
- Principi giurisprudenziali (con numero e anno delle sentenze)
- Dottrina rilevante (se emersa da `cerca_brocardi`)

### ANALISI
Applica il diritto ai fatti:
- Sussunzione dei fatti nelle fattispecie normative
- Valutazione dei pro e contro per le diverse tesi
- Rischi e incertezze

### CONCLUSIONI
- Risposta al quesito in termini chiari
- Raccomandazioni operative
- Eventuali azioni da intraprendere con tempistiche

## Note
- Ogni norma citata DEVE avere un `cite_law` nel transcript
- Ogni sentenza citata DEVE essere stata letta con `leggi_sentenza`
- Segnalare chiaramente quando un'interpretazione è controversa
- Distinguere tra orientamento consolidato e orientamento minoritario
"""


@mcp.prompt(description='Struttura per parere legale: fatto, diritto, normativa e conclusioni con citazione norme')
def parere_legale(area_diritto: str, quesito: str) -> str:
    return (
        "DATI:\n"
        f"- area_diritto: {area_diritto}\n"
        f"- quesito: {quesito}\n"
        "\n"
        + _BODY_PARERE_LEGALE
    )


_BODY_PIANIFICAZIONE_SUCCESSIONE = """\
# Pianificazione Successione

Quote ereditarie, imposte e adempimenti.

## Workflow

### 1. Quote ereditarie

Chiama `calcolo_eredita` con massa_ereditaria (valore totale dell'asse in €) ed eredi (dict: {'coniuge': bool, 'figli': int, 'ascendenti': bool, 'fratelli': int}).

Distingui tra:
- Successione legittima (senza testamento): quote ex artt. 565-586 c.c.
- Quote di legittima (con testamento): riserva ex artt. 536-564 c.c.

Indica la quota disponibile.

### 2. Imposte di successione

Chiama `imposte_successione` con valore_beni, parentela (uno tra 'coniuge_linea_retta', 'fratelli_sorelle', 'parenti_fino_4_grado_affini_fino_3', 'altri'), immobili (bool), prima_casa (bool).
- Aliquota per grado di parentela
- Franchigia (€ 1M coniuge/figli, € 100K fratelli, nessuna franchigia per gli altri soggetti)
- Imposte ipotecaria (2%) e catastale (1%) se immobili
- Segnala che oltre a quanto calcolato dal tool si applicano tributi minori (imposta di bollo, tassa ipotecaria) non inclusi nell'output

### 3. Imposte compravendita (se immobili da vendere)

Chiama `imposte_compravendita`.

## Formato output

```markdown
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
```

## Adempimenti da indicare

- Dichiarazione di successione: entro 12 mesi dall'apertura
- Voltura catastale: entro 30 giorni dalla dichiarazione
- Accettazione eredità: espressa o tacita, con beneficio d'inventario se opportuno
- Pubblicazione testamento olografo (se presente): tribunale competente

## Avvertenze

- I calcoli sono indicativi; la situazione patrimoniale completa potrebbe variare le imposte.
- Franchigie e aliquote vanno lette alla luce della riforma del D.Lgs. 139/2024, che ha introdotto l'autoliquidazione dell'imposta di successione.
- Per successioni internazionali si applica il Reg. UE 650/2012.
- Valutare l'opportunità del beneficio d'inventario (art. 484 c.c.).
"""


@mcp.prompt(description='Pianificazione successoria: quote ereditarie, imposte e adempimenti')
def pianificazione_successione(valore_asse: float, grado_parentela: str, numero_eredi: int) -> str:
    return (
        "DATI:\n"
        f"- valore_asse: {valore_asse}\n"
        f"- grado_parentela: {grado_parentela}\n"
        f"- numero_eredi: {numero_eredi}\n"
        "\n"
        + _BODY_PIANIFICAZIONE_SUCCESSIONE
    )


_BODY_QUANTIFICAZIONE_DANNI = """\
# Quantificazione Danni

Calcolo base, personalizzazione e attualizzazione.

## Workflow

### 1. Calcolo base

**Biologico** (percentuale invalidita):
- <= 9%: `danno_biologico_micro` (tabelle art. 139 CdA)
- > 9%: `danno_biologico_macro` (tabelle Milano)
- Parametri richiesti: percentuale di invalidita ed eta della vittima (l'eta incide sul demoltiplicatore tabellare)

**Patrimoniale** (importo):
- Danno emergente + lucro cessante
- Lucro cessante: calcola in base alla durata della privazione
- `interessi_legali` dalla data evento

**Morale/esistenziale**:
- `danno_non_patrimoniale` come base

### 2. Personalizzazione

Criteri Cass. SS.UU. 26972/2008: sofferenza soggettiva, vita di relazione, specificita del caso.

Indica una percentuale di personalizzazione motivata.

### 3. Attualizzazione

1. `rivalutazione_monetaria` dalla data evento
2. `interessi_legali` sulla somma rivalutata

## Formato output

Intestazione `## Quantificazione Danno` con il tipo di danno tra parentesi, poi la tabella a componenti:

| Componente | Importo |
|------------|---------|
| Danno base (tabellare/documentale) | € ... |
| Personalizzazione (±...%) | € ... |
| Subtotale | € ... |
| Rivalutazione ISTAT | € ... |
| Interessi legali | € ... |
| **TOTALE** | **€ ...** |

### Motivazione

Spiega i criteri di personalizzazione adottati e la giurisprudenza di riferimento.

## Avvertenze

- Quantificazione indicativa basata sulle tabelle vigenti. Per le macropermanenti (> 9%) in ambito RC auto e responsabilita sanitaria la liquidazione segue la Tabella Unica Nazionale ex art. 138 CdA (vincolante); le tabelle Milano restano il riferimento per i danni fuori dal perimetro del Codice delle Assicurazioni.
- La prova del danno patrimoniale richiede documentazione specifica.
- Per il danno biologico serve una perizia medico-legale.
"""


@mcp.prompt(description='Quantificazione danni: biologico, patrimoniale o morale con personalizzazione e attualizzazione')
def quantificazione_danni(tipo_danno: str, importo_o_percentuale: float, eta_vittima: int) -> str:
    return (
        "DATI:\n"
        f"- tipo_danno: {tipo_danno}\n"
        f"- importo_o_percentuale: {importo_o_percentuale}\n"
        f"- eta_vittima: {eta_vittima}\n"
        "\n"
        + _BODY_QUANTIFICAZIONE_DANNI
    )


_BODY_RECUPERO_CREDITO = """\
# Recupero Credito

Workflow completo: interessi mora, rivalutazione, decreto ingiuntivo, parcella.

## Workflow

### 1. Interessi di mora

Chiama `interessi_mora` con capitale, data_inizio (decorrenza della mora) e data_fine (data di calcolo).

- **Commerciale** (imprese/PA): usa `interessi_mora` — tasso BCE + 8 punti (D.Lgs. 231/2002)
- **Privato** (crediti tra privati): usa `interessi_legali` — tasso legale art. 1284 c.c.

### 2. Rivalutazione monetaria

Chiama `rivalutazione_monetaria` con l'importo del credito, dalla data di scadenza a oggi.

**Nota**: mora e rivalutazione NON si cumulano (Cass. SS.UU. 16601/2017). Presenta entrambi, indica il piu favorevole.

### 3. Decreto ingiuntivo

Chiama `decreto_ingiuntivo` con l'importo del credito per verificare:

- Competenza — Giudice di Pace fino a € 10.000 per i procedimenti instaurati dal 28/2/2023 (riforma Cartabia, D.Lgs. 149/2022); fino a € 5.000 per quelli anteriori. Oltre la soglia, Tribunale.
- Contributo unificato dovuto
- Requisiti documentali (fatture, contratto, estratto autentico notarile)
- Possibilità di provvisoria esecutività (art. 642 c.p.c.)

### 4. Parcella

Chiama `parcella_avvocato_civile` con valore della causa pari all'importo del credito, per fase monitoria. Indica il range compenso (minimo/medio/massimo) da D.M. 55/2014.

## Formato output

### Riepilogo Recupero Credito

| Voce | Importo |
|------|---------|
| Capitale | € `importo` |
| Interessi di mora (da `data_scadenza` a oggi) | € ... |
| Rivalutazione ISTAT (alternativa) | € ... |
| **Totale dovuto** | **€ ...** |

### Costi procedura

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


@mcp.prompt(description='Workflow completo per recupero credito: interessi, rivalutazione, decreto ingiuntivo e parcella')
def recupero_credito(importo: float, tipo_credito: str, data_scadenza: str) -> str:
    return (
        "DATI:\n"
        f"- importo: {importo}\n"
        f"- tipo_credito: {tipo_credito}\n"
        f"- data_scadenza: {data_scadenza}\n"
        "\n"
        + _BODY_RECUPERO_CREDITO
    )


_BODY_RICERCA_GAZZETTA = """\
# Ricerca Gazzetta

Esegui una ricerca sulla Gazzetta Ufficiale per il tema indicato.

## Dati richiesti

- **tema** — il tema da cercare in Gazzetta Ufficiale. Se non fornito, chiedilo.
- **serie** (opzionale, default `serie_generale`) — filtro serie: serie_generale / unione_europea / regioni / corte_costituzionale / parte_seconda / contratti / concorsi.

## Workflow

### Fase 1 — Novità o ricerca mirata
Per le ultime pubblicazioni, chiama `ultime_gazzette(serie=<serie>)` (fonte: feed RSS).
Per una ricerca mirata, chiama `cerca_gazzetta_ufficiale(titolo=<tema>, serie=<serie>)`
(usa anche `testo=`, `tipo_provvedimento=`, `emettitore=`, `materia=`, `anno_da=`, `anno_a=` se utile).

### Fase 2 — Lettura atto
Presenta i risultati e, per l'atto scelto, chiama
`leggi_atto_gazzetta(codice_redazionale, data_pubblicazione, serie=<serie>)` per metadati ELI +
testo as-published. Per il PDF ufficiale firmato usa `scarica_pdf_gazzetta(...)`.
Per l'intero sommario di un numero di GU usa `sommario_gazzetta(numero_gazzetta, data_pubblicazione)`.

### Fase 3 — Testo vigente vs as-published
La Gazzetta dà il testo ORIGINALE come pubblicato. Per il testo CONSOLIDATO/VIGENTE chiama
`cite_law(reference)` (Normattiva). Distingui sempre le due cose nella risposta.

## Regole

- La Gazzetta è la fonte dell'atto come pubblicato (con PDF/ELI citabile); Normattiva è la fonte del
  vigente. Non confonderle.
- Usare i tool, mai estremi a memoria.
"""


@mcp.prompt(description='Ricerca e lettura di atti pubblicati in Gazzetta Ufficiale: novità per serie, ricerca parametrica, testo as-published + PDF ufficiale')
def ricerca_gazzetta(tema: str, serie: str = 'serie_generale') -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- serie: {serie}\n"
        "\n"
        + _BODY_RICERCA_GAZZETTA
    )


_BODY_RICERCA_NORMATIVA = """\
# Ricerca Normativa

Fonti primarie, norme collegate, giurisprudenza e sanzioni.

Inquadra la ricerca nell'area di diritto indicata dall'utente (civile / penale / amministrativo / lavoro / tributario / privacy / commerciale) prima di individuare le fonti.

## Regola fondamentale

**Ogni norma citata DEVE essere verificata con `cite_law`**. Mai citare a memoria.

Regole ulteriori:
- Indicare espressamente se una norma è stata modificata o abrogata.
- Segnalare le modifiche normative già pubblicate in Gazzetta Ufficiale e verificabili con i tool. Non segnalare riforme pendenti o proposte de lege ferenda, per le quali il server non dispone di una fonte verificabile.

## Workflow

### 1. Fonti primarie

Per ogni norma individuata, chiama `cite_law`. Ordina per gerarchia:
1. Costituzione
2. Regolamenti UE
3. Direttive UE (+ D.Lgs. recepimento)
4. Leggi ordinarie / D.Lgs. / D.L.
5. D.M. e regolamenti
6. Circolari e prassi

### 2. Norme collegate

Per ogni norma primaria: attuazione, modifiche, abrogazioni, disposizioni transitorie.

### 3. Giurisprudenza

`cerca_brocardi` per massime. `cerca_giurisprudenza` per approfondimento.

Per le norme chiave, chiama `cite_law` con `include_annotations=true` per recuperare da Brocardi:
- Massime di Cassazione e Corte Costituzionale
- Orientamenti consolidati vs. questioni aperte
- Posizioni dottrinali prevalenti

Per trovare giurisprudenza recente (ultimi 5 anni), chiama `cerca_giurisprudenza` con la query tra virgolette (es. `query="\\"art. ... codice\\""`) e `modalita="esplora"` per vedere la distribuzione, poi ripeti la ricerca con filtri per le decisioni più rilevanti.

### 4. Fonti autorita vigilanza

- Finanza/mercati: `cerca_delibere_consob`
- Privacy: `cerca_provvedimenti_garante`

Se il tema riguarda mercati finanziari, intermediari, emittenti, OPA, crowdfunding o cripto-attività, chiama `cerca_delibere_consob` con il tema come query per recuperare le delibere e i provvedimenti CONSOB rilevanti; per le delibere più significative, recupera anche il testo integrale della delibera.

Per le materie finanziarie includere sempre i provvedimenti delle autorità di vigilanza. Per Banca d'Italia non esiste un tool dedicato: indicare al lettore la fonte da consultare, senza riportarne il contenuto a memoria.

### 5. Quadro sanzionatorio

Se pertinente, identifica:
- Sanzioni penali (contravvenzioni, delitti)
- Sanzioni amministrative (pecuniarie, interdittive)
- Responsabilità civile (risarcimento danni)
- Sanzioni disciplinari (ordini professionali, PA)

## Formato output

```markdown
## Ricerca Normativa su [tema]

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
Tabella delle sanzioni applicabili.
```
"""


@mcp.prompt(description='Ricerca normativa completa su un tema giuridico: norme applicabili, gerarchia delle fonti e coordinamento')
def ricerca_normativa(tema: str, area_diritto: str) -> str:
    return (
        "DATI:\n"
        f"- tema: {tema}\n"
        f"- area_diritto: {area_diritto}\n"
        "\n"
        + _BODY_RICERCA_NORMATIVA
    )


_BODY_VERIFICA_PRESCRIZIONE = """\
# Verifica Prescrizione

Calcolo termine prescrizione civile o penale.

## Workflow

### Civile

Identifica anzitutto il tipo di diritto (contrattuale, extracontrattuale, reale, etc.): è la classificazione che determina quale termine si applica.

Chiama `prescrizione_diritti`:
- **10 anni**: ordinaria (tipo_diritto='ordinaria', art. 2946 c.c.)
- **5 anni**: risarcimento danni (tipo_diritto='risarcimento_danni', art. 2947 c.c.)
- **2 anni**: danno da circolazione veicoli / RCA (tipo_diritto='risarcimento_rca', art. 2947 c.2 c.c.)
- **2 anni**: diritti derivanti dal contratto di assicurazione (art. 2952 c.c.)
- **1 anno**: trasporti e spedizioni

Verifica sospensione (artt. 2941-2942) e interruzione (art. 2943 c.c.): messa in mora, ricorso, riconoscimento del debito.

### Penale

Identifica anzitutto il reato (titolo e articolo c.p.): è il presupposto per calcolare il massimo edittale.

Chiama `prescrizione_reato`:
- Termine = massimo edittale (min 6 anni delitto, 4 contravvenzione)
- Sospensione (art. 159 c.p.), interruzione (art. 160 c.p.) e termine massimo con interruzioni (art. 161 c.p.)
- Riforma Cartabia: improcedibilita in appello/cassazione — per il regime applicabile in base alla data del fatto, vedi «Avvertenze»

### Analisi temporale

- Data decorrenza: la data del fatto indicata
- Data odierna: calcola il tempo trascorso
- Data prescrizione: indica la scadenza esatta
- Stato: PRESCRITTA / NON PRESCRITTA / IN SCADENZA (ultimi 6 mesi)

## Formato output

Stato PRESCRITTA / NON PRESCRITTA / IN SCADENZA con data esatta, presentato in tabella:

### Verifica Prescrizione — civile o penale

| Elemento | Dettaglio |
|----------|----------|
| Fatto | descrizione del fatto |
| Data fatto | data indicata |
| Tipo diritto/reato | ... |
| Norma applicabile | art. ... |
| Termine prescrizione | ... anni |
| Data decorrenza | data del fatto |
| Data scadenza prescrizione | GG/MM/AAAA |
| Tempo trascorso | ... anni, ... mesi, ... giorni |
| Tempo residuo | ... anni, ... mesi, ... giorni |
| **STATO** | **PRESCRITTA / NON PRESCRITTA / IN SCADENZA** |

### Cause di Sospensione/Interruzione

Elenca eventuali cause note che potrebbero aver modificato il decorso.

## Avvertenze

- La prescrizione può essere interrotta o sospesa da atti non noti al momento dell'analisi: ogni verdetto PRESCRITTA è provvisorio rispetto alla completezza dei fatti forniti.
- Prescrizione penale — regime intertemporale, da individuare in base alla data del fatto:
  - **Fatti ante 1.1.2020**: disciplina ex-Orlando — la prescrizione corre anche in appello, con le sospensioni introdotte dalla L. 103/2017.
  - **Fatti dal 1.1.2020**: blocco Bonafede (L. 3/2019) — il corso della prescrizione cessa dopo la sentenza di primo grado; per i giudizi di impugnazione opera l'improcedibilità Cartabia ex art. 344-bis c.p.p. (introdotto dalla L. 134/2021, con attuazione nel D.Lgs. 150/2022).
- In ambito civile, il decorso della prescrizione può essere interrotto con atto stragiudiziale (raccomandata/PEC di messa in mora) — rimedio economico da suggerire quando lo stato è IN SCADENZA.
"""


@mcp.prompt(description='Verifica prescrizione di un diritto civile o di un reato penale')
def verifica_prescrizione(tipo: str, descrizione_fatto: str, data_fatto: str) -> str:
    return (
        "DATI:\n"
        f"- tipo: {tipo}\n"
        f"- descrizione_fatto: {descrizione_fatto}\n"
        f"- data_fatto: {data_fatto}\n"
        "\n"
        + _BODY_VERIFICA_PRESCRIZIONE
    )
