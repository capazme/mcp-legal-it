# Guida: quando il server dice «dati_non_affidabili»

Il server rifiuta un calcolo quando la tabella su cui poggerebbe non ha una
provenienza verificata: un numero esatto su una base non verificata sarebbe un
numero che mente. Il rifiuto non è un vicolo cieco — è una domanda: *o mi porti
tu il dato, o mi autorizzi a rispondere a un grado minore*. Questa guida mostra
le quattro forme della risposta, con esempi da copiare nella chiamata del tool.

Prima regola: **il rifiuto elenca sempre la via d'uscita**. Nel corpo arriva
`come_sbloccare` con il nome del file da riconciliare *e* il parametro che
sblocca la singola chiamata; nel `_meta` arriva `mcp-legal-it/precisione` con
`concedibile`, il grado che sarebbe stato concesso.

---

## 1. Portare il codice catastale (al posto della tabella `comuni`)

`comuni` è un sottoinsieme di ~500 codici catastali, non il dataset ISTAT
completo: è il buco più difficile da chiudere in repository e il più facile da
chiudere in chiamata, perché il codice è stampato sulla documentazione del
cliente.

**`codice_fiscale`** — senza codice il tool rifiuta; con il codice l'algoritmo
è esatto e la risposta non tocca nessuna tabella:

```json
{"tool": "codice_fiscale", "arguments": {
  "cognome": "Rossi", "nome": "Mario",
  "data_nascita": "1980-01-01", "sesso": "M",
  "comune_nascita": "Roma",
  "codice_catastale": "H501"
}}
```

Risposta: `codice_fiscale: "RSSMRA80A01H501U"`, `dati_forniti_dal_chiamante`
che dichiara la sostituzione, **nessun avviso**.

**`decodifica_codice_fiscale`** — per la via inversa serve la mappa inversa
(comune → codice), che si copia dal pragmatario del cliente:

```json
{"tool": "decodifica_codice_fiscale", "arguments": {
  "codice_fiscale": "RSSMRA80A01H501U",
  "mappa_comuni": {"ROMA": "H501", "MILANO": "F704"}
}}
```

## 2. Portare il preavviso (al posto della tabella `preavviso_ccnl`)

`preavviso_ccnl` non potrà mai avere un vintage giusto: i contratti collettivi
si rinnovano, quindi il periodo di preavviso corretto è quello del contratto
che avete in mano, non quello del repository. Il giorno del preavviso viaggia
nella chiamata:

```json
{"tool": "indennita_preavviso", "arguments": {
  "retribuzione_mensile": 2500.0,
  "anni_servizio": 7,
  "giorni_preavviso": 45
}}
```

Risposta: l'importo calcolato sul periodo che avete indicato, con
`giorni_preavviso_fonte: "forniti dal chiamante"`. L'aritmetica resta del tool;
solo i giorni vengono da fuori.

## 3. Portare i valori fiscali (al posto delle tabelle di tributi)

Tre tabelle fiscali accettano i loro contenuti sostituiti dalla chiamata.
Utile quando avete il dato fresco dalla fonte (circulare, sito dell'Agenzia)
e non volete aspettare l'aggiornamento del repository.

**`imposte_successione`** — le coppie aliquota/franchigia per grado di
parentela che servono alla chiamata (quelle non indicate cadono):

```json
{"tool": "imposte_successione", "arguments": {
  "valore_beni": 500000.0,
  "parentela": "coniuge_linea_retta",
  "aliquote_franchigie": [
    {"parentela": "coniuge_linea_retta", "aliquota": 4, "franchigia": 1000000}
  ]
}}
```

**`imposte_compravendita`** — la sezione registro con le aliquote del caso:

```json
{"tool": "imposte_compravendita", "arguments": {
  "prezzo": 200000.0,
  "prima_casa": true,
  "aliquote_registro": {
    "prima_casa": {"registro": 2, "ipotecaria": 50, "catastale": 50,
                   "minimo_registro": 1000}
  }
}}
```

**`contributo_unificato`** — l'intera tabella sostitutiva, nella stessa forma
di `src/data/contributo_unificato.json` (gli scaglioni che non servite possono
mancare):

```json
{"tool": "contributo_unificato", "arguments": {
  "valore_causa": 10000.0,
  "tabella_contributo_unificato": {
    "civile": {"cognizione": [
      {"fino_a": 1100, "importo": 43}, {"fino_a": 5200, "importo": 98},
      {"fino_a": 26000, "importo": 237}, {"fino_a": 52000, "importo": 518},
      {"fino_a": 260000, "importo": 759}, {"fino_a": 520000, "importo": 1214},
      {"oltre": true, "importo": 1686}
    ]},
    "appello": {"moltiplicatore": 1.5},
    "cassazione": {"moltiplicatore": 2.0}
  }
}}
```

**`decurtazione_punti_patente`** — la mappa delle violazioni (stessa struttura
della tabella inclusa):

```json
{"tool": "decurtazione_punti_patente", "arguments": {
  "violazione": "sorpasso",
  "tabella_violazioni": {
    "sorpasso": {"punti": 3, "articolo": "Art. 148 c.15 CdS",
                 "descrizione": "Sorpasso vietato"}
  }
}}
```

In tutti questi casi la risposta nomina `dati_forniti_dal_chiamante` con il
parametro e la tabella che ha sostituito: chi legge sa che la base è vostra,
non del repository.

## 4. Accettare un grado minore (quando il dato non lo portate)

Se non avete il dato, il rifiuto di un tool `ESATTO` è negoziabile: con
`accetta_precisione` dite il grado con cui vi accontentate e la risposta arriva
a quel grado, con l'avviso sulla provenienza **ancora attaccato** — accettare
non cancella da dove viene il numero.

```json
{"tool": "imposte_successione", "arguments": {
  "valore_beni": 500000.0,
  "parentela": "coniuge_linea_retta",
  "accetta_precisione": "INDICATIVO"
}}
```

Cosa aspettarsi:

- il corpo porta `precisione: {dichiarata: ESATTO, effettiva: INDICATIVO,
  accettata: INDICATIVO}` e l'`avviso` sulla tabella;
- il `_meta` porta `mcp-legal-it/precisione` con la stessa storia, per l'host
  che legge solo il meta;
- chiedere di *restare* `ESATTO` viene rifiutato con `concedibile:
  INDICATIVO`: l'affermazione non è in vendita;
- una tabella **scaduta** sotto una cifra che riguarda oggi non è negoziabile a
  nessun grado (`negoziabile: false`): un tasso vecchio è sbagliato, non
  impreciso.

---

## Quale strada scegliere

| situazione | strada |
|---|---|
| il dato è sulla documentazione del cliente (codice catastale, preavviso CCNL) | parametro-alternativa (sezioni 1-2): risposta esatta, zero avvisi |
| il dato è su una fonte ufficiale che avete sottomano (scheda Agenzia, tabella CU) | tabella sostitutiva (sezione 3): risposta esatta alla vostra fonte |
| il dato non c'è ma il grado indicativo basta (stima, preventivo) | `accetta_precisione` (sezione 4): risposta con avviso |
| serve il numero esatto del repository | niente da negoziare: riconciliare la tabella (`verifica: manuale` + `aggiornato_al`, poi la suite — `/dati` mostra la classifica di cosa blocca di più) |

La terza via è la politica di sempre del repository: `backlog_riconciliazione`
ordina le tabelle per quanto bloccano, e con `LEGAL_REFUSAL_LEDGER=on` il
verbale riordina la classifica per quanto hanno bloccato *davvero* nello
studio.
