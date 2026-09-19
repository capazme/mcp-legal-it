# Guide: precision, refusals, and the four negotiated calls

The server refuses a calculation when the table it would rest on has no
verified provenance: an exact number on an unverified base is a number that
lies. The refusal is not a dead end — it is a question: *either you bring the
datum, or you authorize a lower grade*. This guide shows the four shapes of the
negotiated call, with payloads you can paste into a tool call.

First rule: **the refusal always lists the way out**. The body carries
`come_sbloccare` with the file to reconcile *and* the parameter that unblocks
this one call; the result `_meta` carries `mcp-legal-it/precisione` with
`concedibile`, the grade that would have been granted.

> **Where things stand.** Since the 2026-09-20 reconciliations (ISTAT catastal
> codes, the DM 32/2012 role-code table, the three CCNL notice schedules) no
> shipped tool refuses: every table an exact-grade tool applies is verified,
> and the two tables still unverified (`codici_ateco`, `tribunali_competenti`)
> have only indicative readers, which answer at a lowered grade and say so.
> The four moves below are the permanent contract for the day one is needed
> again: a table **expires** (a rate schedule with a covered period — a figure
> about *today* then refuses instead of lying), a new table ships unverified,
> or you hold **fresher data** than the repository and want the answer on
> yours. The wire answers shown here are exactly what the probe server
> (`plugin/server/probe_precision.py`) produces and what the tests exercise.

---

## 1. Bring the catastal code (instead of the `comuni` table)

`comuni` is now verified against the full ISTAT list, but it is deliberately a
subset of the main municipalities: a town that is not in it is not an error,
it is what the `codice_catastale` parameter is for — the code is printed on
the client's own documents.

**`codice_fiscale`** — with the code, the algorithm is exact and the answer
touches no table:

```json
{"tool": "codice_fiscale", "arguments": {
  "cognome": "Rossi", "nome": "Mario",
  "data_nascita": "1980-01-01", "sesso": "M",
  "comune_nascita": "Roma",
  "codice_catastale": "H501"
}}
```

Answer: `codice_fiscale: "RSSMRA80A01H501U"`, `dati_forniti_dal_chiamante`
declaring the substitution, **no warnings**.

**`decodifica_codice_fiscale`** — the reverse way wants the reverse map
(municipality → code), copied from the client's pragmatario:

```json
{"tool": "decodifica_codice_fiscale", "arguments": {
  "codice_fiscale": "RSSMRA80A01H501U",
  "mappa_comuni": {"ROMA": "H501", "MILANO": "F205"}
}}
```

## 2. Bring the notice period (instead of the `preavviso_ccnl` table)

`preavviso_ccnl` can never have a right vintage: collective agreements are
renegotiated, so the correct notice period is the one in the contract *you*
hold, not the one in the repository. The notice days travel in the call:

```json
{"tool": "indennita_preavviso", "arguments": {
  "retribuzione_mensile": 2500.0,
  "anni_servizio": 7,
  "giorni_preavviso": 45
}}
```

Answer: the amount computed on the period you named, with
`giorni_preavviso_fonte: "forniti dal chiamante"`. The arithmetic stays the
tool's; only the days come from outside.

## 3. Bring the fiscal tables (instead of the shipped ones)

Four tables accept their contents replaced by the call. Useful when you have
the figure fresh from the source (a circular, the Agenzia's site) and do not
want to wait for the repository to catch up.

**`imposte_successione`** — the aliquot/franchise pairs for the kinship grades
the call needs (others fall back to the shipped table):

```json
{"tool": "imposte_successione", "arguments": {
  "valore_beni": 500000.0,
  "parentela": "coniuge_linea_retta",
  "aliquote_franchigie": [
    {"parentela": "coniuge_linea_retta", "aliquota": 4, "franchigia": 1000000}
  ]
}}
```

**`imposte_compravendita`** — the registro section with the rates of the case:

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

**`contributo_unificato`** — the whole replacement table, in the same shape as
`src/data/contributo_unificato.json` (brackets you do not need may be left
out):

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

**`decurtazione_punti_patente`** — the violation map (same shape as the
shipped table):

```json
{"tool": "decurtazione_punti_patente", "arguments": {
  "violazione": "sorpasso",
  "tabella_violazioni": {
    "sorpasso": {"punti": 3, "articolo": "Art. 148 c.15 CdS",
                 "descrizione": "Sorpasso vietato"}
  }
}}
```

In every case the answer names `dati_forniti_dal_chiamante` with the parameter
and the table it replaced: whoever reads it knows the base is yours, not the
repository's.

## 4. Accept a lower grade (when you do not have the datum)

If you do not have the datum, an `ESATTO` tool's refusal is negotiable: with
`accetta_precisione` you name the grade you will settle for, and the answer
arrives at that grade with the provenance warning **still attached** —
accepting does not erase where the number comes from.

```json
{"tool": "imposte_successione", "arguments": {
  "valore_beni": 500000.0,
  "parentela": "coniuge_linea_retta",
  "accetta_precisione": "INDICATIVO"
}}
```

What to expect:

- the body carries `precisione: {dichiarata: ESATTO, effettiva: INDICATIVO,
  accettata: INDICATIVO}` and the warning about the table;
- the `_meta` carries `mcp-legal-it/precisione` with the same story, for a
  host that reads only the meta;
- asking to *stay* `ESATTO` is refused with `concedibile: INDICATIVO`: the
  claim is not for sale;
- an **expired** table under a figure about *today* is not negotiable at any
  grade (`negoziabile: false`): an old rate is wrong, not imprecise.

---

## Which road to take

| situation | road |
|---|---|
| the datum is on the client's paperwork (catastal code, CCNL notice) | alternative parameter (sections 1-2): exact answer, zero warnings |
| the datum is on an official source at hand (Agenzia schedule, CU table) | replacement table (section 3): exact answer on your source |
| no datum, and an indicative grade is enough (estimate, budget) | `accetta_precisione` (section 4): answer with warning |
| you need the repository's own exact number | nothing to negotiate: reconcile the table (`verifica: manuale` + `aggiornato_al`, then the suite — the backlog shows what blocks most) |

The last road is the repository's standing policy: `backlog_riconciliazione`
ranks the tables by what they block, and with `LEGAL_REFUSAL_LEDGER=on` the
tally re-ranks the list by what actually blocked in the studio.

---

## How the Freebuff host surfaces these moves

Freebuff talks to this server as an MCP connector, and every mechanism above
is already visible from its side of the wire — no extra configuration beyond
the connector itself.

**Approval, once.** The connector's annotations (`readOnlyHint` /
`openWorldHint`, audited from the call graph) let Freebuff pre-approve the 205
read-only lookups, so a refusal and a negotiated re-call are ordinary tool
calls — no prompt, no click. The 17 tools that write a document wait for a
one-time manual approval in *Connectors*. `accetta_precisione` and the
alternative parameters are plain tool arguments: they need no approval of
their own, because the tool answering with them is already approved.

**The refusal reaches the model, not just the user.** The refusal is the
tool's result: the body (`errore`, `come_sbloccare`) and the `_meta`
(`mcp-legal-it/precisione`) are both in what the model reads. That is what
makes the negotiation automatic in practice: ask "quantifica l'imposta di
successione per 500k al coniuge" the day a table has expired, and the refusal
names the exit — the model can re-issue the call with `accetta_precisione:
"INDICATIVO"` or with the alternative parameter you named in the chat ("usa
questa tabella: ..."), and the second answer carries
`dati_forniti_dal_chiamante` instead of the warning.

**Structured state, not only prose.** The same fact travels twice —
`avvisi_dati` next to `dati_applicati` in the JSON body, and
`mcp-legal-it/data_warnings` / `mcp-legal-it/precisione` in the result
`_meta` — so a host that renders structured results can show the vintage
state without parsing Italian prose, and the two channels cannot drift
(the tests fail if they disagree).

**The backlog is a tool, not a ticket.** `backlog_riconciliazione` is itself
read-only and pre-approved: from the chat you can ask "quali tabelle sono da
riconciliare e quanto bloccano" and get the ranked list — source, static cost,
observed tally (with `LEGAL_REFUSAL_LEDGER=on` in the connector's env), and
the action to take. Refreshing a table is a guided flow (`/dati` command in
the plugin) that never opens the code.
