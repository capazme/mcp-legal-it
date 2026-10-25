# Etichette dei tool

Ogni tool porta delle etichette (`tags`). Sono ciò su cui filtrano `LEGAL_PROFILE`,
`crea_server(include_tags=…, exclude_tags=…)` e `LEGAL_BROCARDI=off`: un filtro vale
quanto le etichette su cui lavora. Il vocabolario è dato, in
[`mcp_legal_it/tool_taxonomy.py`](../plugin/server/mcp_legal_it/tool_taxonomy.py), e
`tests/unit/test_tool_taxonomy.py` fa fallire la suite se un tool viola una regola
(un tool nuovo senza tipo, un calcolatore con `normativa`, una sentenza senza organo) o
se questa pagina smette di coincidere con il vocabolario.

## Regole

1. Ogni tool ha **esattamente un tipo**.
2. Un tool di tipo `giurisprudenza` ha **almeno un organo**; le etichette di organo
   non compaiono su tool di altro tipo.
3. Un tool di tipo `autorita` ha **esattamente un'autorità**; le etichette di autorità
   non compaiono su tool di altro tipo.
4. Aree e marcatori sono liberi, a parte `solo_brocardi`, che va sempre con `brocardi`.

## Tipo (uno per tool)

| Etichetta | Tool | Significato |
|---|---|---|
| `normativa` | 19 | Legislazione e ciò che la annota: testo delle norme, indice e PDF dell'atto, Gazzetta Ufficiale, disegni di legge, recepimento UE↔Italia, verifica delle citazioni, annotazioni Brocardi. |
| `giurisprudenza` | 24 | Decisioni di un giudice: ricerca, testo integrale, giurisprudenza su una norma, orientamenti. |
| `autorita` | 9 | Provvedimenti e indirizzi di un'autorità indipendente (Garante privacy, CONSOB, ANAC). |
| `registri` | 5 | Fatti cercati online in un registro pubblico o su un sito di terzi, non diritto: marchi (TMview), partite IVA (VIES), DPA pubblicato da un fornitore. |
| `calcolo` | 141 | Risposta calcolata in locale dagli input e dalle tabelle incluse: calcoli, termini, compensi, imposte, verifiche e ricerche in tabella. Nessuna fonte online. |
| `redazione` | 30 | Produce una bozza di documento o di testo da usare come tale: atti, lettere, informative, DPA, file DOCX ed Excel. Fatture, notule, ricevute e preventivi sono `calcolo`: il loro contenuto è il conto. |
| `diagnostica` | 3 | Riferisce sul server stesso: versione, freschezza dei dati, verbale dei rifiuti. |

## Organo (per i tool di giurisprudenza)

| Etichetta | Significato |
|---|---|
| `giurisprudenza_cass` | Corte di cassazione (Italgiure) e gli orientamenti costruiti su di essa. |
| `giurisprudenza_cost` | Corte costituzionale. |
| `giurisprudenza_trib` | Giudici tributari e Cassazione tributaria (CeRDEF). |
| `giurisprudenza_amm` | Giustizia amministrativa: TAR e Consiglio di Stato. |
| `giurisprudenza_ue` | Corte di giustizia e Tribunale dell'Unione europea (CGUE). |

`cerca_giurisprudenza_unificata` porta quattro organi: interroga Cassazione, CeRDEF,
TAR/CdS e CGUE.

## Autorità (per i tool di tipo `autorita`)

| Etichetta | Significato |
|---|---|
| `garante` | Garante per la protezione dei dati personali (porta anche l'area `privacy`). |
| `consob` | CONSOB. |
| `anac` | ANAC (Autorità Nazionale Anticorruzione). |

La Gazzetta Ufficiale non è un'autorità: i suoi tool sono `normativa`.

## Area (materia)

| Etichetta | Significato |
|---|---|
| `atti` | Atti giudiziari e stragiudiziali composti dal catalogo dei modelli. |
| `credito` | Percorso di recupero crediti (interessi, decreto ingiuntivo, esecuzione, compensi). |
| `crisi_impresa` | Crisi d'impresa e insolvenza (CCII). |
| `danni` | Danno alla persona e risarcimento. |
| `fiscale` | Imposte, dichiarazione dei redditi, giurisprudenza tributaria. |
| `giudiziario` | Procedura: contributo unificato, depositi PCT, verifiche processuali. |
| `interessi` | Tassi, interessi di mora, usura, ammortamento. |
| `investimenti` | Titoli di Stato e prodotti di risparmio. |
| `lavoro` | Diritto del lavoro. |
| `marchi` | Marchi. |
| `parcelle_avv` | Compensi degli avvocati (D.M. 55/2014), fatture e preventivi. |
| `parcelle_prof` | Compensi di altri professionisti (CTU, mediatori, curatori). |
| `parlamento` | Disegni di legge e iter parlamentare. |
| `penale` | Diritto penale: pena, prescrizione, conversione. |
| `privacy` | Protezione dei dati (GDPR, Codice privacy). |
| `proprieta` | Proprietà, successioni, imposte sugli immobili. |
| `recepimento_ue` | Recepimento degli atti UE in Italia e base UE degli atti italiani. |
| `rivalutazione` | Rivalutazione monetaria sugli indici ISTAT. |
| `scadenze` | Termini processuali e sostanziali. |
| `sinistro` | Percorso del sinistro stradale o sanitario. |
| `societario` | Diritto societario. |
| `utility` | Verifiche e conversioni generali (codice fiscale, IBAN, partita IVA, date). |

## Marcatori

| Etichetta | Significato |
|---|---|
| `brocardi` | La risposta può contenere contenuto di Brocardi.it (note dottrinali, massime): `cite_law`, `cerca_brocardi`, `fetch_law_annotations`, `giurisprudenza_articolo`, `mappa_orientamento`. |
| `solo_brocardi` | La risposta è solo contenuto Brocardi: con Brocardi spento il tool non è esposto (`cerca_brocardi`, `fetch_law_annotations`). |
| `previgente` | Calcola secondo un regime superato, per i casi residuali che ancora governa; `LEGAL_PREVIGENTE=off` lo nasconde. |

## Profili `LEGAL_PROFILE`

Un profilo espone i tool che hanno almeno una delle sue etichette. I profili nominano
tipi e aree, mai singoli tool: un tool nuovo entra nei profili giusti per le sue
etichette. Tutti includono `diagnostica`.

| Profilo | Etichette | Tool |
|---|---|---|
| **full** | tutte | 231 |
| **sinistro** | danni, rivalutazione, interessi, normativa, giurisprudenza, sinistro, diagnostica | 79 |
| **credito** | interessi, rivalutazione, parcelle_avv, normativa, giurisprudenza, credito, diagnostica | 89 |
| **penale** | penale, normativa, giurisprudenza, diagnostica | 51 |
| **fiscale** | fiscale, proprieta, utility, consob, investimenti, crisi_impresa, societario, diagnostica | 66 |
| **normativa** | normativa, giurisprudenza, autorita, registri, privacy, diagnostica | 73 |
| **privacy** | privacy, garante, normativa, giurisprudenza, diagnostica | 64 |
| **studio** | scadenze, giudiziario, parcelle_avv, parcelle_prof, investimenti, lavoro, diagnostica | 76 |
| **redattore** | atti, giudiziario, parcelle_avv, scadenze, normativa, diagnostica | 76 |
| **cowork** | normativa, giurisprudenza, privacy, parcelle_avv, diagnostica | 77 |
| **calcoli** | calcolo, diagnostica | 144 |

Con `LEGAL_BROCARDI=off` ogni profilo che contiene `normativa` espone due tool in meno
(`cerca_brocardi`, `fetch_law_annotations`); `full` passa da 231 a 229.

## Un server con una parte dei tool: `crea_server`

```python
from mcp_legal_it.server import crea_server

# solo fonti: norme e giurisprudenza, senza Brocardi
fonti = crea_server(include_tags={"normativa", "giurisprudenza"}, brocardi=False)
fonti.run()                                   # come server a sé
# oppure: il_mio_server.mount(fonti, namespace="legal")
```

- `include_tags`: tiene i tool con almeno una di queste etichette (`None` = tutti; un insieme
  vuoto è rifiutato con `ValueError`, perché non selezionerebbe nulla).
- `exclude_tags`: poi toglie quelli con una di queste etichette.
- `brocardi=False`: nasconde i `solo_brocardi` e fa girare ogni chiamata di quel server
  con Brocardi spento; i tool misti rispondono senza Brocardi e lo dicono.
  `exclude_tags={"brocardi"}` è diverso: toglie *ogni* tool che può mostrare Brocardi,
  `cite_law` compreso.
- `prompts=False`: niente prompt né risorse `legal://` (non hanno etichette, i filtri
  non li toccano; i prompt possono nominare tool rimasti fuori dal sottoinsieme).
- Un'etichetta sconosciuta solleva `ValueError` con il vocabolario.
- Le istruzioni del server sono quelle standard senza i tool esclusi: un passo di workflow che
  nomina un tool nascosto viene tolto dalla catena, una riga che lo nomina altrimenti viene
  tolta. Lo stesso vale per il server standard con `LEGAL_BROCARDI=off`
  («Norma → cite_law → giurisprudenza_su_norma → leggi_sentenza»).

I tool esclusi non compaiono in `list_tools` e una chiamata riceve «Unknown tool».
Nomi, firme, annotazioni, `_meta` e middleware restano quelli del server standard,
che il factory monta senza modificarlo. Le variabili d'ambiente del processo
(`LEGAL_PROFILE`, `LEGAL_PREVIGENTE=off`, `LEGAL_BROCARDI=off`) agiscono sotto e
possono solo restringere ciò che il factory seleziona.
