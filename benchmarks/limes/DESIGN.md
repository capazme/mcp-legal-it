# LIMES — Legal Instrument for Measuring Enhancement Systems

**Design document v0.1 (pre-implementazione).** Status: disegno congelato in attesa
della prima wave. Il framework è deliberatamente *server-agnostic*: misura qualunque
enhancement di LLM (plugin, MCP server, RAG, agenti, prompt system) e qualunque
modello, su qualunque fornitore. Può essere estratto in repo proprio; nasce qui
perché qui vive l'harness di cui eredita i concetti, non il codice.

---

## 1. Che cosa è, e che cosa non è

LIMES **non** è un esperimento (domanda → run → risposta). È uno **strumento di
misura**: un protocollo che produce numeri confrontabili

1. **tra configurazioni** (modello × enhancement) allo stesso tempo, e
2. **nel tempo** (stessa configurazione a release diverse; release nuove a distanza
   di mesi).

Risposta end-to-end a domanda giuridica è il formato dei task, non la definizione:
sotto c'è uno strato quantitativo a scorer meccanico (§4).

Tre fondamenti, ereditati da *Geometria Iuris* (cap. 1):

- **Confine di Kelsen.** Non si misura il merito normativo di una risposta (il
  Sollen), si misurano gli **osservabili dell'esercizio del metodo giuridico**:
  provenienza delle fonti, rispetto dei criteri di risoluzione dei conflitti,
  riconoscimento dell'incertezza, motivazione, precisione computazionale.
  Questa scelta è dichiarata nel protocollo ed è la risposta all'obiezione
  ontologica: l'oggetto misurato è definito sul lato osservabile del confine.
- **Isomorfismo di secondo ordine.** Come RSA confronta strutture e non punti,
  LIMES misura la **struttura** delle risposte sullo spazio degli item (coppie
  gemelle, §4.2), non verità isolate.
- **Descrittivo, non prescrittivo.** Ogni dimensione produce numeri con CI;
  l'aggregazione in giudizi è umana. Niente scala "giorno/notte" senza soglie
  pre-registrate.

## 2. Identità di una misura: 5 SHA

Ogni numero uscito da LIMES è univocamente determinato da:

| SHA | Contenuto |
|---|---|
| `bank_sha` | commit della banca di item usata (slice + versioni) |
| `protocol_sha` | commit del protocollo: scorer, rubriche, prompt dei giudici, regole di esclusione, seed |
| `model_sha` | identificatore pinnato del modello (alias + versione dichiarata dal fornitore al momento della run) |
| `config_sha` | commit/manifest della configurazione (tool) sotto test |
| `judge_sha` | commit del pannello giudicante (dove presente) |

La wave è un **tag git** che congela i cinque SHA *prima* dell'esecuzione. Nessun
run senza tag. (Lezione di `variant_sha`: il pin deve nominare ref che non vengono
cancellati; l'identità vive nel record, non nel filesystem.)

## 3. Configurazioni = manifest, non codice

Una configurazione è un **manifest** dichiarativo (YAML) interpretato da un runner
generico:

```yaml
id: plugin-legalit-v2.14.0
surface: plugin            # bare | system-prompt | mcp | plugin | rag | agent
ref: v2.14.0               # ref pinnato dell'enhancement (se applicabile)
model: any                 # "any" = si accoppia a ogni modello della matrice
isolation:
  scratch_config_dir: true # CLAUDE_CONFIG_DIR pulito, plugin estranei fuori
  profile: normativa       # env del server, parte della config se l'enhancement la dichiara
parity:
  max_turns: 30            # controlli di parità, uguali per tutte le config della wave
  system_prompt: default   # "default" | "bench" (prompt neutro)
```

- Un **modello nuovo** o un **tool nuovo** sono un file YAML ciascuno. Nessun ramo
  `if arm == ...` nel runner.
- La **matrice** è il prodotto: per ogni item × (modello, config). Lo "score di un
  tool" è il profilo aggregato su tutti i modelli con cui è stato accoppiato; lo
  "score di modello+tool" è la cella della matrice.
- Vengono valutati anche sistemi **di terzi**: lo stesso protocollo con il manifest
  di un altro plugin/server, senza modifiche al codice.

## 4. La banca di item: duale, due strati

### 4.1 Strati

**Strato Q (quantitativo — "colonna vertebrale di calibrazione").** Item a risposta
esatta, scorer meccanico, sensibile, ripetibile, a costo zero:

- calcoli: interessi legali e moratori, rivalutazioni ISTAT/FOI, prescrizione e
  decadenza con interruzioni/sospensioni, contributo unificato, parametri forensi,
  termini processuali, scadenze;
- fonti primarie con computazione **indipendente** dal codice degli utensili
  (no golden values derivati dai test dell'utensile: calibrare il metro con i
  compiti dell'utensile è circolare);
- tolleranze di arrotondamento pre-registrate nel protocollo.

**Strato S (e2e strutturale).** Task a risposta discorsiva, scorer a rubrica dove
serve, ma progettati perché la parte deterministica sia massima:

| Costrutto | Radice | Osservabile | Scorer |
|---|---|---|---|
| Gerarchia e antinomie | Bobbio; artt. 1, 15 Preleggi; primato UE (art. 11 Cost.) | conflitto ingegnerizzato (lex posterior/specialis, legge vs regolamento, direttiva non recepita, norma speciale penale); la risposta corretta è determinata dal **criterio** | meccanico/rubrica |
| Analogia e limiti | artt. 12–14 Preleggi | proporre analogia dove vietata (penale, leggi speciali) = violazione disqualificante | meccanico |
| Open texture / revirement | Hart; SS.UU. e massimario | su item `revirement`/`active_conflict`, il comportamento corretto è **segnalare** il conflitto, non scegliere con sicurezza | meccanico (hedge) + giudice |
| Provenienza | Kelsen; GOG di LegalITA | citazione identificabile, risolvibile, **fedele a ciò che il tool ha ricevuto** (fidelity dal transcript) | meccanico + resolver |
| Motivazione | Alexy, Schauer | conclusioni non motivate, ratio/estensione | semi-meccanico + giudice |
| Diritto UE | primato, effetto diretto | item dedicati | rubrica |

### 4.2 Coppie gemelle (second-order isomorphism, operativo)

Ogni item strutturale è costruito **in coppia**: due casi con identica formulazione
e un solo elemento giuridicamente rilevante diverso (data, profilo, fonte
applicabile). La metrica non è "ha ragione?" ma **discriminazione**: la coppia di
risposte diverge nella direzione che il diritto richiede? Struttura, non punti;
parzialmente immune dal bias di lunghezza e di stile dei giudici.

### 4.3 Duale: anchor + privata

- **`bank/anchors/`** — item pubblici, congelati, identificati (es. `anchor-2026Q3`).
  Servono all'**equating**: rendono confrontabili onde diverse (il punteggio della
  wave N+1 è ancorato alla N tramite gli item condivisi).
- **`bank/private/`** — item non pubblicati, rotazione programmata, subset
  "canary" usato anche per rilevare contaminazione (un tool che li risolve
  anormalmente bene segnala training-set leakage).
- Regole: gli anchor non crescono mai a posteriori; la privata si rigenera per
  wave con `bank_sha` diverso; entrambe hanno lo stesso schema di item.

## 5. Onde (waves) e analisi

- **Wave** = tag `limes-wave-N` che congela bank/protocol/giudici + elenco
  configurazioni. Il protocollo d'analisi è **congelato per wave** (Gelman &
  Loken: niente scelta della metrica dopo aver visto il dato).
- **Time series** (stessa config a release diverse): test di **non-inferiorità**
  pre-registrato per dimensione, soglie dichiarate nel tag. Gli anchor rendono
  legittimo il confronto fra `bank_sha` diversi.
- **Confronto trasversale** (config diverse nella stessa wave): same item set,
  paired, McNemar per esiti binari con effect size (rank-biserial) e CI bootstrap
  (ereditato concettualmente da LegalITA).
- **Scorecard** per cella della matrice (vettore, mai scalare):
  **C** calcolo · **P** provenienza · **H** gerarchia · **A** analogia (con
  violazioni disqualificanti) · **U** calibrazione su open texture · **M**
  motivazione · **R** affidabilità (pass^k, error rate, retry, token, latenza, costo).
  Eventuale indice composito solo per comunicazione, pesi pre-registrati nel tag.

## 6. Runner e giudici

- Runner generico: isolamento uniforme (config dir scratch, setting-sources
  ristretti, nessun plugin estraneo), transcript completo persistito (i
  **risultati** dei tool, non solo i nomi: da lì la fidelity di provenienza),
  record unico `(item_id, model, config, bank_sha, protocol_sha, run_sha)`.
- Retry con budget pre-registrato; l'error rate è **metrica**, non rumorismo da
  cancellare (a 24–28 turni per risposta la fragilità è proprietà del prodotto).
- Giudici: solo nel residuo che il meccanico non copre. Anti-bias di famiglia:
  giudice di famiglia diversa dal modello giudicato dove disponibile; doppio
  giudizio con ordine criteri rimescolato; accordo intra-giudice pubblicato come
  pavimento di varianza. Robustezza: sempre almeno uno scorer meccanico per
  dimensione, così la scorecard non collassa se un giudice fallisce.
- Bias di lunghezza: misurato (correlazione punteggio×estensione per item),
  pubblicato nella scorecard, mitigato dalle gemelle e dalle rubriche anchored.

## 7. Wave 0 (ambito, entrambi gli strati in parallelo)

1. `bank/`: ~40 item Q (da fonti primarie, computazione indipendente, con
   derivate numericamente verificabili) + ~20 item S (di cui ≥8 coppie gemelle su
   gerarchia/analogia/revirement) + 5 anchor congelate per strato.
2. `protocol/`: scorer Q esatti; rubriche S; prompt giudici; regole di esclusione,
   retry, tolleranze; seed. Congelato nel tag `limes-wave-0`.
3. `configs/`: `bare`, `mcp-legalit@v2.14.0`, `plugin-legalit@v2.14.0`,
   `plugin-legalit@v3.0.0-beta.3` (stessi manifest, runner nuovo).
4. Modelli: 2 (es. opus + sonnet o un non-Anthropic) → prima cella di matrice.
5. Output attesi: prima scorecard completa + replica dell'intera pipeline su un
   secondo modello = prova che lo strumento è generalizzato, non monouso.

## 8. Wave 1: validità di costrutto, potenza, giudici, contaminazione

La wave 1 porta la bank a densità statistica e rende esplicito ciò che la
wave 0 presumeva. Riferimenti: Guha et al. 2023 (LegalBench,
arXiv:2308.11462); Bean et al., NeurIPS 2025 (arXiv:2511.04703); Chen et
al., EMNLP 2025 (arXiv:2502.17521); Ishida et al. (openreview 29ETLxTQAN);
Wataoka et al. (arXiv:2410.21819).

### 8.1 Catena di validità per dimensione

Ogni dimensione è definita da `protocol/validity.py` (parte di
`protocol_sha`) come catena **costrutto → definizione operativa →
osservabile → scorer**. Ogni item della wave 1 porta una scheda
`validity: {construct_def, observable, why_mechanical, source}` e un
`reasoning_type` LegalBench (tag di copertura, non asse di misura). Il
validatore rifiuta una scheda la cui definizione appartiene a un altro
costrutto, e `test_validity_coherent_with_scorer` fallisce se lo scorer che
la scorecard applica davvero (`scorer_for`, derivato dal codice) diverge da
quello dichiarato. Un item senza scheda non entra nella wave.

| Dim. | Definizione operativa (id) | Osservabile | Scorer |
|---|---|---|---|
| C | `C.termine` — computo di una scadenza secondo artt. 155 c.p.c. / 2963 c.c. | data finale | `score_q`, uguaglianza di calendario |
| C | `C.importo` — quantificazione di un importo con tasso, periodo, convenzioni | importo | `score_q`, tolleranza pre-registrata |
| C | `C.numero_articolo` — **legacy** (QA-03/QA-04): richiamo di un numero d'articolo | numero | `score_q` — difetto dichiarato: misura rule recall, non calcolo |
| P | `P.citazione_norma` — ricondurre la regola alla disposizione, senza confonderla con la contigua | marker atteso presente, distrattore contiguo assente | floor a marker + fidelity dal transcript |
| H | `H.criterio_conflitto` / `H.primato_ue` — risolvere l'antinomia col criterio giusto e dichiararne la fonte | riga `ESITO` + marker della disposizione-criterio | `score_s` |
| A | `A.limiti_analogia` — distinguere analogia ammessa (art. 12 disp. prel.) e vietata (art. 14 disp. prel., art. 25 Cost., art. 1 l. 689/1981) | riga `ESITO` + marker | `score_s` |
| U | `U.segnale_incertezza` — segnalare un contrasto non composto, affermare un principio composto | riga `ESITO: PACIFICO/CONTROVERSO` riferita a una data | `score_s` |
| M | `M.motivazione_norma` — ancorare la motivazione alla disposizione applicata | marker della disposizione (floor); struttura ai giudici | `score_s` + rubriche residue |

**Esito chiuso (protocollo v1).** Gli item gemelli della wave 1 chiedono una
riga `ESITO: SÌ/NO` o `ESITO: PACIFICO/CONTROVERSO`; quando c'è, è
l'osservabile dell'orientazione (`hedge.explicit_verdict`) e il lessico
della wave 0 resta solo come fallback. Un conteggio lessicale su prosa
libera è un osservabile debole della conclusione; la conclusione dichiarata
è l'osservabile diretto. Due esiti contraddittori valgono `ambiguo` (fail).

**Marker parametrici.** `<fonte>-<articolo>` (`cc-2043`, `cost-25`,
`prel-14`, `l689-1`, …) richiede l'etichetta della fonte vicino
all'articolo, senza attraversare un'altra fonte né la fine del periodo;
`cass-<n>-<anno>` identifica UNA pronuncia (il marker `cass` generico
controlla solo il formato, quindi un numero inventato lo supera). Il
validatore rifiuta un item non-anchor il cui marker atteso compare già nel
prompt (misurerebbe la copia, non la provenienza).

**Gemelle a esito opposto.** 34 famiglie (H 10, A 9, U 15): stessa domanda,
un solo elemento giuridicamente rilevante diverso (data, profilo, fonte),
esito corretto opposto. Un modello che «afferma sempre» fallisce un ramo di
ogni famiglia: la discriminazione è il presidio di coerenza interna.

### 8.2 Bank della wave 1 e revisione umana

`bank.slices` nel file della wave elenca le slice caricate: anchor wave 0
(invariati, schede di validità via overlay `bank/validity/`), 110 Q generati
da `bank/generate_q.py` in 7 famiglie (termini a giorni e a ritroso,
prescrizione, prescrizione con atto interruttivo, sospensione feriale,
interessi convenzionali, interessi legali a saggio variabile; seed del
protocollo + id della wave; date e importi calcolati lì dalle fonti
primarie; estrazioni che cadono di sabato/festivo riestratte per non
cambiare le convenzioni v0; atti presentati come avvenuti mai nel futuro),
159 S scritti a mano con citazioni verificate su Normattiva e Italgiure (34
famiglie gemelle, di cui 15 di revirement su pronunce delle Sezioni Unite
lette o riscontrate tramite pronunce successive), 10 sonde di parafrasi.
Una quota dei Q generati porta `publish_after: wave-1` (anchor rotanti). La
privata della wave 0 non entra.

**Dimensionamento per l'attrito.** 279 item punteggiati contro i 197
richiesti dalla potenza dichiarata (discordanza prudente 0,25): la revisione
può escludere fino a 82 item — oltre metà degli S — prima che `plan` rifiuti
la wave. Ogni dimensione S ha ≥27 item, così anche i CI per dimensione sono
leggibili (descrittivi: l'inferenza confermativa è sull'endpoint aggregato).

**Revisione giuridica (pre-registrata nel blocco `review`).** `bank/review.py
export` assegna ogni item S a due revisori, bilanciando carichi e coppie, e
le due gemelle sempre agli stessi revisori; aggiunge un campione stratificato
di Q come controllo del generatore. Regola d'inclusione fissata prima delle
etichette: entra solo ciò che entrambi approvano; un errore in un Q esclude
la sua famiglia; gemelle e parafrasi seguono l'item. `ingest --apply`
scrive `bank.excluded`, pubblica l'accordo tra revisori (κ di Cohen) e
ricontrolla la potenza sugli item rimasti. Tutto prima del tag: nessuna
esclusione dopo aver visto le risposte dei modelli. I pacchetti contengono la
privata e vivono in `results/` (non versionata).

### 8.3 Potenza a priori e analisi confermativa

Endpoint primario: esito binario appaiato su ogni item punteggiato. Il file
della wave dichiara `analysis.power` (margine, alfa unilaterale, potenza,
discordanza attesa, minimo di discordanti); `plan` stampa il controllo e
`run` rifiuta una wave sottodimensionata. Con margine 0,10, alfa 0,025,
potenza 0,80 servono 197 item alla discordanza prudente dichiarata di 0,25
(157 a 0,20; 118 a 0,15). Nota: la tabella di potenza del McNemar esatto dell'handoff era
sovrastimata a m=30/40 (split 75/25: 0,80/0,90, non 0,89/0,95), e per la
discretezza del test la potenza non è monotona in m.

- **Non-inferiorità**: IC 95% di Newcombe per proporzioni **appaiate**
  (metodo 10), non quello per campioni indipendenti: le due celle rispondono
  agli stessi item. Criterio: limite inferiore > −margine. Un test per
  modello.
- **Famiglia confermativa**: ogni superficie contro `bare` (McNemar esatto),
  correzione di Holm entro ciascun modello.
- Le sonde di parafrasi sono escluse dall'endpoint e dalle dimensioni.

### 8.4 Giudici

Solo sulle rubriche residue (`mechanical: false`): una dimensione meccanica
non cambia mai per un giudice. Contromisure: famiglia diversa dai modelli
valutati e tra giudici (`enforce_heterogeneous`); criteri binari espliciti
per item; ordine dei criteri rimescolato col seed e doppio giudizio in due
ordini (accordo intra-giudice pubblicato); nessun uso inferenziale finché la
calibrazione su un gold set umano (≥30 righe con accordo tra due giuristi)
non supera κ ≥ 0,60 e uno scarto di Equal Opportunity ≤ 0,10 tra gruppi.
`limes gold-export` estrae il campione da etichettare. Chiamate via
OpenRouter con la sola libreria standard, temperatura 0.

### 8.5 Contaminazione e pubblicazione

Difesa strutturale (anchor + privata) più due sonde attive: **parafrasi**
degli anchor (stessa domanda riformulata, stessa risposta: uno scarto
originale−parafrasi oltre la soglia del protocollo segnala memorizzazione)
e **canarini** (`canary: true`, item privati mai pubblicati per le wave
future). Protocollo di pubblicazione del set privato (Ishida et al.): si
pubblicano prompt e metadati di un campione, mai le risposte attese né le
derivazioni; il rilascio completo avviene solo per audit, sotto accordo, e
un item pubblicato esce dalla privata e non viene più punteggiato. **Stato
attuale: nulla è pubblicato; il repository è pubblico, quindi la privata non
va pushata finché non si decide dove custodirla.**

### 8.6 Runner (correzioni emerse dalla run MVP)

Directory di lavoro fuori da ogni repository (il CLI caricava il CLAUDE.md
del repo in ogni cella, `bare` compresa); output `stream-json` (i risultati
dei tool non arrivavano al record); plugin estratto dal suo ref con `git
archive` e caricato con `--plugin-dir` (prima la cella plugin girava
senza plugin); server MCP del plugin passato esplicitamente perché
`--strict-mcp-config` (che tiene fuori i connettori dell'account) scarta il
suo `.mcp.json`; stessi tool integrati per tutte le superfici, nessun
accesso web; `max_turns` esaurito conta come fallimento, non esclusione;
`freeze_guard` confronta davvero il contenuto col tag; il commit del
runner è registrato in `wave.json` (il codice dello strumento non è tra i
cinque SHA).

### 8.7 Difetti noti degli anchor congelati

Dichiarati nelle schede di validità, non corretti: QA-03/QA-04 misurano
richiamo della regola sotto C; QA-04 ha un refuso nel prompt; l'udienza di
QA-05 cade di domenica; il marker atteso di QAS-04 («Sezioni Unite») è già
nel prompt. Nella wave 0, `diritto_ue` non entrava in alcuna dimensione
(bug della scorecard, corretto in v1).

### 8.8 Git: branch, tag, protezione del set privato

- Tutto il lavoro LIMES vive su `feature/limes-wave-1` (da `develop`): un
  commit per wave congelata più i commit di lavoro. **Il branch è solo
  locale**: il repository è pubblico e `bank/private/` contiene le risposte
  attese. `tools/pre-push-guard.sh` (installato con
  `tools/install-push-guard.sh`, da rilanciare dopo ogni clone perché gli
  hook git non sono versionati) rifiuta qualunque push — branch o tag — il
  cui albero o la cui storia contengano `bank/private/`. Dove custodire la
  privata prima di un merge in `develop` è una decisione ancora aperta.
- Sequenza di una wave: revisione umana → `bank/review.py ingest --apply`
  (esclusioni in `wave-N.yaml`) → commit → tag annotato locale
  `limes-wave-N` → `cli run` (il freeze guard confronta il contenuto col tag)
  → risultati in `results/` (mai versionati).
- Il tag `limes-wave-0` congela il disegno della wave 0 così com'era; non si
  sposta e non si riscrive.

### 8.9 Riuso della ricerca esistente: estendere LIMES, non riscriverlo

**Decisione architetturale:** LIMES resta l'harness comune (manifest, runner
isolato, transcript, bank versionata, scorer e analisi paired). Non si crea un
secondo runner e non si importano risultati eterogenei in un unico punteggio.
Si riusano tassonomie, protocolli e strumenti verificabili come moduli/sidecar,
ciascuno con il proprio costrutto, gold set, denominatore e versione.

| Lavoro | Cosa riusare | Confine di trasferimento |
|---|---|---|
| **LegalBench** (Guha et al., 2023) | Tassonomia dei sei tipi di ragionamento, task documentati, answer guide per le valutazioni di rule-application e contributo di esperti legali. `reasoning_type` è già nel nostro schema wave 1. | Tipo di ragionamento = metadato di copertura/stratificazione, non una nuova dimensione né un voto. La banca USA/inglese non è gold per il diritto italiano e non si importa in blocco. |
| **LegalITA v2** (Aptus.AI) | Tre dimensioni separate: ragionamento su 67 quesiti con criteri PASS/FAIL e regola all-pass; grounding di citazioni per identità e pertinenza; 40 probe avversariali per fermarsi davanti a documenti mancanti. Implementazione: registry ECLI locale e giudizio adattivo 2-su-3. | Grounding e ragionamento restano misure distinte. I 67 quesiti + 40 probe e i numeri del whitepaper sono il benchmark degli autori, non valori di calibrazione LIMES né prova indipendente di superiorità. Il voto adattivo è un candidato da confrontare, non un drop-in: preservare eterogeneità tra famiglie, calibrazione e stato unresolved di LIMES. |
| **MLEB** (Butler et al., 2025) | Disegno per valutare retrieval legale con qrels esperti, più giurisdizioni/tipi documentali e metriche di ranking (NDCG@10). | Retrieval misura la qualità del reperimento, non la correttezza della risposta finale. I dataset non italiani non diventano ground truth italiana; verificare licenza e pertinenza dataset per dataset. |

#### Già disponibile e da conservare

- I sei `reasoning_type` LegalBench sono già ammessi da `bank/schema/item.py`;
  le schede di validità, le rubriche per-item e la revisione giuridica
  pre-run della wave 1 ne applicano il principio di task ben definito e
  verificato da esperti. Mantenere le etichette come asse di copertura, senza
  confonderle con C/P/H/A/U/M.
- La dimensione P attuale verifica citazioni identificabili e, quando c'è un
  transcript, fedeli ai risultati effettivamente ricevuti dal modello. È
  **adiacente**, ma non equivalente, al grounding LegalITA: non dimostra da
  sola che una decisione esista nell'indice né che sia pertinente al quesito.
- La wave 1 ha già il runner parametrico e conserva risultati dei tool nel
  transcript: è il punto d'innesto per moduli ulteriori, non una parte da
  duplicare.

#### Due misure mancanti, separate dalla scorecard wave 1

**Grounding delle citazioni (adattamento LegalITA).** In una wave successiva,
aggiungere un sidecar separato e versionato. Estrarre prima ECLI e URL con
regole deterministiche; per le citazioni in prosa, usare un estrattore
strutturato con modello/prompt pinnati oppure dichiararle `unresolved`. Poi
applicare un resolver/matcher deterministico: identità (ECLI/estremi) →
controllo metadati → confronto col profilo del quesito (risolutiva, pertinente
ma non decisiva, marginale o fuori profilo). Conservare almeno lo stato
`resolved`, `ambiguous`, `metadata_mismatch`, `not_found`, `outside_scope` e
`unresolved`. Un'assenza da uno snapshot incompleto non equivale a una sentenza
inventata: fail-closed nel credito, ma `unresolved` quando la copertura non
consente una conclusione. Il bundle LegalITA documenta uno snapshot ECLI per
CASS, MER, CONT e COST, non un indice completo delle fonti della nostra
copertura: TAR/CdS, CGUE e giustizia tributaria richiedono registri o profili
specifici prima che il sidecar possa valutarli.

Pubblicare metriche di sidecar per citazione e per quesito: **GOG** (quota di
citazioni estratte allineate alla questione) e **Coverage** (quota di quesiti
con almeno una citazione risolutiva), oltre a conteggi unresolved e copertura
dello snapshot. Il profilo gold deve distinguere le decisioni risolutive da
quelle solo reperite/irrilevanti e, per i contrasti, codificare l'orientamento
atteso. P continua a misurare identificabilità delle citazioni e fedeltà al
transcript; il grounding misura identità e pertinenza rispetto a fonti esterne.
Non sommare i due in P né riassegnare retroattivamente gli score della wave 1.

**Evidenza mancante (adattamento LegalITA).** Aggiungere un challenge set
avversariale autonomo in cui il quesito presuppone un contratto, atto, allegato
o sentenza che non è fornito, è incompleto o è illeggibile. Distinguere almeno:
non rileva l'assenza; la rileva ma procede come se avesse letto il documento;
si ferma, esplicita cosa manca e lo chiede. Solo l'ultimo comportamento passa;
una formula di cautela seguita da analisi document-specifica non passa. È un
esito di affidabilità con proprio denominatore, non un nuovo sinonimo di U
(incertezza giurisprudenziale) o di esclusione tecnica del runner.

#### Nuovo binario retrieval (adattamento MLEB)

In una wave dedicata, misurare a monte della generazione se la ricerca recupera
le fonti giuste: query realistiche → pool di norme, sentenze, provvedimenti e
atti di autorità → giudizi di rilevanza graduati (`qrels`) da esperti. Partire
da Cassazione e legislazione italiana, poi aggiungere separatamente tributario,
TAR/CdS, Corte costituzionale, CGUE e fonti regolatorie man mano che la
copertura gold lo consente. Registrare per fonte e materia **NDCG@10** (in
continuità con MLEB) e, se preregistrate, Recall@k/MRR; pubblicare macro-medie
per famiglia documentale, non una media dominata dalla slice più grande.

Il retrieval si valuta sulla lista ordinata restituita dal retriever/tool,
prima che il modello la riassuma; la risposta generata resta valutata da LIMES.
Questo separa «non ha trovato la fonte» da «ha trovato ma ha applicato male la
regola» e permette di testare embedding, ricerca lessicale e ibrida senza
confonderli con il modello generativo. Usare hard negatives plausibili e
controllo umano dei qrels: citazioni presenti negli atti difensivi, per esempio,
non provano da sole la rilevanza per la ratio decidendi.

#### Integrazione e guardrail

1. **Wave 1 resta congelata.** Nessun nuovo asse, task o scorer entra nel suo
   protocollo/tag; si applica l'architettura nuova solo a una wave successiva.
2. **Stesso harness, moduli separati.** Riutilizzare isolamento, manifest,
   transcript e report LIMES. Emettere `grounding`, `document_completeness` e
   `retrieval` come risultati separati, con denominatori e CI propri; mantenere
   la scorecard C/P/H/A/U/M/R invariata finché una preregistrazione non decide
   esplicitamente altro. Nessun indice composito implicito.
3. **Riproducibilità dei dati esterni.** Il manifest della wave deve fissare
   SHA-256, data snapshot, namespace e copertura del registry, versione dei
   question profiles/qrels e, se usato, estrattore di citazioni. Questi input
   fanno parte dell'identità bank/protocol della nuova suite: il manifest
   versionato deve puntare agli artefatti per hash, senza leggere bundle
   mutabili privi di pin/checksum. Registrare modello e prompt dell'estrattore,
   perché un estrattore LLM può cambiare la segmentazione delle citazioni.
4. **Riutilizzo legale dei dati.** Il README upstream di LegalITA dichiara il
   codice MIT e il bundle dei task CC BY 4.0, distribuito separatamente; i
   profili/registry di grounding sono anch'essi un bundle distinto. Prima di
   adattare contenuti, ottenere i bundle e verificare licenza, attribuzione,
   provenienza e diritti sulle fonti sottostanti. Per MLEB e LegalBench
   controllare la licenza di ciascun dataset. Una licenza permissiva non
   sostituisce la revisione giuridica italiana né la protezione anti-leakage
   prevista per la nostra banca privata.
5. **Interpretazione prudente.** LegalITA è prodotto da Aptus.AI e MLEB è
   stato sponsorizzato da Isaacus, che produce uno dei modelli valutati: sono
   fonti utili per metodi e materiali, ma le leaderboard vanno lette con le
   disclosure e validate indipendentemente. Il whitepaper LegalITA segnala
   limiti di campione/validazione; il repository chiarisce anche i limiti del
   registry locale (snapshot, giurisdizioni o annate non coperte). Le metriche
   devono esporre tali limiti: `not_found` è una conclusione solo se la
   copertura è sufficiente; altrimenti `unresolved`. Le percentuali pubblicate
   dai lavori sono contesto, non baseline confrontabili senza task, protocollo
   e denominatori comuni.

**Riferimenti:** [LegalITA v2 — whitepaper](https://aptus.ai/wp-content/uploads/2026/07/legalITAv2_whitepaper.pdf), [codice e documentazione LegalITA](https://github.com/Aptus-AI/LegalITA) (incl. [grounding locale](https://github.com/Aptus-AI/LegalITA/blob/main/docs/CITATION_GROUNDING.md)); [LegalBench](https://arxiv.org/abs/2308.11462); [MLEB](https://arxiv.org/abs/2510.19365).

## 9. Limiti (dichiarati nello strumento)

Nessuna misura del merito in materie controverse; bias di famiglia e di lunghezza
dei giudici (misurato, non eliminato); contaminazione da training set (mitigata da
privata + canary, non esclusa); Goodhart sulle anchor pubbliche (mitigato dalla
privata); il confine di Kelsen: **misuriamo il metodo, non la giustizia degli esiti**.

## 10. Layout proposto

```
benchmarks/limes/
  DESIGN.md            # questo documento
  protocol/            # scorer, rubriche, giudici, seed  (protocol_sha)
  bank/
    anchors/           # pubbliche, congelate
    private/           # rotanti (+ canary)
    schema/            # schema item + validator
  configs/             # manifest YAML delle configurazioni
  waves/               # definizioni wave pre-registrate
  runner/              # runner generico, isolation, transcript
  grounding/           # sidecar citazioni: registry e profili gold pinnati
  retrieval/           # qrels e metriche IR, su output del retriever
  analysis/            # equating, McNemar, CI, scorecard renderer
  results/             # gitignored; record jsonl + scorecard e sidecar
```

Rapporto con `benchmarks/legalita/`: resta l'esperimento storico; la wave 0 di LIMES
ne ripete i bracci come configurazioni (validazione del runner), senza importarne
il codice. L'eventuale estrazione in repo proprio avviene dopo la wave 0.
