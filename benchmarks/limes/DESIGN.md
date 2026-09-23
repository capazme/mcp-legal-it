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

## 8. Limiti (dichiarati nello strumento)

Nessuna misura del merito in materie controverse; bias di famiglia e di lunghezza
dei giudici (misurato, non eliminato); contaminazione da training set (mitigata da
privata + canary, non esclusa); Goodhart sulle anchor pubbliche (mitigato dalla
privata); il confine di Kelsen: **misuriamo il metodo, non la giustizia degli esiti**.

## 9. Layout proposto

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
  analysis/            # equating, McNemar, CI, scorecard renderer
  results/             # gitignored; record jsonl + scorecard
```

Rapporto con `benchmarks/legalita/`: resta l'esperimento storico; la wave 0 di LIMES
ne ripete i bracci come configurazioni (validazione del runner), senza importarne
il codice. L'eventuale estrazione in repo proprio avviene dopo la wave 0.
