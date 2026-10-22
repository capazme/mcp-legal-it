# `mcp_legal_it.api` — the library API

`mcp_legal_it.api` is mcp-legal-it used as a Python library: Italian and EU norms
and case law as plain `async` functions that return typed data. It needs
Python 3.11 or later.

**It is the package's only stable surface.** Everything else is internal:
`mcp_legal_it.core`, `mcp_legal_it.lib`, `mcp_legal_it.tools`, the MCP server
and the `_impl` functions. Any of them can change in any release, a patch
release included.

```python
import asyncio
from mcp_legal_it import api

async def main():
    t = await api.testo_articolo("art. 2043 c.c.", canale="html")
    if t.esito == "trovato":
        print(t.norma_data.urn)
        print(t.article_text)
    else:
        print(t.esito, t.errore)

asyncio.run(main())
```

## Contents

1. [Contract](#1-contract)
2. [Configuration](#2-configuration)
3. [Norms](#3-norms)
4. [Decisions](#4-decisions)
5. [Types](#5-types)
6. [Planned functions](#6-planned-functions)
7. [Versioning and deprecation](#7-versioning-and-deprecation)
8. [For VisuaLex](#8-for-visualex)

---

## 1. Contract

**Import.** `import mcp_legal_it.api` does not import FastMCP, the MCP SDK,
`mcp_legal_it.server` or any tool module. It registers no tool and opens no
network connection. `tests/unit/test_api_import_contract.py` enforces this: it
runs the import with FastMCP made to fail and every socket blocked. Constants
(`ARTICLE_SUFFIX_ALTERNATION`, `SUFFISSI_ARTICOLO`) and the offline functions
(`leggi_riferimento`, `riferimento_da_parametri`, `catalogo_alias`) work in
that state.

**Async where the network is.** Functions that can reach the network are
`async`; pure parsing and catalogue functions are sync (`leggi_riferimento`,
`riferimento_da_parametri`, `catalogo_alias`: CPU only). There are no sync
wrappers of the network functions: from sync code use `asyncio.run(...)`.

The sync functions stay sync and offline. `leggi_riferimento` never resolves
over the network the full date of an act cited with the year only: that is a
separate async function (`risolvi_date_atti`, planned, §6). If a remote
catalogue is ever needed, it gets an async variant next to the sync one, and
the existing signature does not change.

**Errors are data.** A function never raises for an outcome a caller must
expect: an unknown act, a missing article, a source that is down, an ambiguous
number. The result carries:

- `esito`, a closed vocabulary listed in the type (`EsitoNorma`,
  `EsitoLettura`, `EsitoRicerca`). New values can only appear in a minor
  release, and are announced in the CHANGELOG.
- `errore`, a message for a person, in Italian, without Markdown. It is `None`
  on success.
- `errori` (`{field: message}`), only for `richiesta_non_valida`.

They do raise for programming errors: a wrong argument type, an unknown
`canale`, a non-positive `concorrenza`, an unknown source name in
`cerca_giurisprudenza_unificata`. They raise `TypeError` or `ValueError`.

**No Markdown.** Texts are returned as the source serves them. The MCP tools do
their own formatting on top of the same internal functions
(`mcp_legal_it.core`), and their outputs did not change when the API was added.

**Provenance.** Every network result carries `fonti: FontiConsultate | None`:
which online sources the call reached (dataset name, URL without the query
string) and when. Inside an MCP tool call, the same sources are also added to
the call's `_meta.fonti_consultate`.

**Field names.** Where VisuaLex already answers the same question in JSON, the
dataclass fields carry VisuaLex's key names verbatim: `article_text`,
`norma_data`, `validity`, `identita`, `attributi`, `avvisi`, and so on. Fields
VisuaLex lacks are additions. `come_dict(result)` turns any result into plain
JSON-ready data:

- tuples become lists;
- `Attributi` keeps only its filled fields;
- an `Avviso` is flattened to `{tipo, ...dettagli}`.

## 2. Configuration

| Name | Signature |
|---|---|
| `configurazione` | `configurazione(*, client_factory=…, cache_dir=…, cache=…, brocardi=…)`, a context manager |
| `configura` | `configura(*, client_factory=…, cache_dir=…, cache=…, brocardi=…) -> Configurazione` |
| `Configurazione` | frozen dataclass of the four fields; `None` means "as the environment says" |
| `ClientFactory` | `Callable[..., httpx.AsyncClient]`, called as `factory(fonte, **kwargs)` |
| `con_regole` | `con_regole(fonte, transport) -> httpx.AsyncBaseTransport`: *transport* with the source's network limits around it, for a factory that builds its own (see **Network rules**) |

- **`configurazione(...)`** applies to the current context only. Concurrent
  tasks can hold different configurations.
- **`configura(...)`** sets the process default. A field you do not pass keeps
  its value. `configura()` with no field resets every field.
- **`client_factory(fonte, **kwargs)`** builds every HTTP client the library
  opens.
  - `fonte` is the stable source name: `normattiva`, `eur_lex`, `italgiure`,
    `brocardi`, `corte_cost`, `cerdef`, `giustizia_amm`, `cgue`, and so on.
  - `kwargs` are exactly what the library would pass to `httpx.AsyncClient`:
    headers, timeout, `follow_redirects`, and Italgiure's `verify` SSL context.
  - The client is used as `async with` and closed afterwards.
  - Use it to add a cache transport or a test transport. Pass the `kwargs` on
    to `httpx.AsyncClient`: `headers` (some sources refuse requests without
    their `User-Agent`/`Accept`), `timeout`, `verify` (Italgiure's is an SSL
    context that adds the intermediate its server fails to send) and `follow_redirects`.
  - **The guards cannot be dropped.** `event_hooks` (the request guards, such as
    `dpa_probe`'s check of every request and redirect against private
    addresses) and `follow_redirects=False` are re-applied to whatever the
    factory returns, before the factory's own hooks. A factory set for the
    whole process with `configura()` therefore cannot disarm the MCP server
    either. The factory must return an `httpx.AsyncClient`.
- **`cache_dir`** relocates the disk caches, in place of `MCP_CACHE_DIR`. The
  caches are parsed Akoma Ntoso acts, the Brocardi URL map and the
  Constitutional Court open data. Set it per process (`configura(cache_dir=…)`):
  the in-memory caches are shared by the process, so a per-request directory
  would split only the disk part.
- **`cache=False`** turns the disk caches off, as `LEGAL_CACHE=off` does.
- **`brocardi=False`** sends no request to brocardi.it, as `LEGAL_BROCARDI=off`
  does.

**An *off* wins.**

- `cache=True` cannot override `LEGAL_CACHE=off`.
- `brocardi=True` raises `ValueError` under `LEGAL_BROCARDI=off`. Inside
  `configurazione` it also raises inside a context where Brocardi was switched
  off (`crea_server(brocardi=False)`, an enclosing `configurazione(brocardi=False)`).
- A field a block does not pass is inherited and never overrides the switch of
  the context it runs in.

**Caches and limits that stay as they are.** The parsed-act cache keeps its
in-memory LRU, capped by `AKN_CACHE_MAX_ACTS` (default 50), and its disk
layout. Concurrent cold requests for the same act share one download: the
callers waiting on it get the first caller's result (the same parsed act, as
the in-memory LRU already gave), and each of them lists the download's sources
in its own `fonti`. If the first caller is cancelled, the waiters get no AKN
act and fall back to the HTML reader, as on any AKN failure.

**Network rules.** Every client is made in one place,
`mcp_legal_it/core/_http.py`, for a named source. Two kinds of rule hang on
that name (VisuaLex's rules, ported):

- **the host guard, per hostname** (security; a factory cannot drop it): every
  request, each redirect hop included, must use http(s), carry no credentials
  and name a host the source may reach (`HOST_PER_FONTE`, kept inside
  `lib/_egress.ALLOWED_HOSTS` by a test). A request outside it raises
  `HostNonConsentito` (an `httpx.TransportError`) and never reaches the
  network. It travels in `event_hooks`, so it is re-applied like the other
  guards;
- **the limits, per source** (politeness), shared by every client, thread and
  event loop of the process: at most 3 requests in flight and 0.5 s between two;
  a `Retry-After` stated by a 429 or 503 pauses the source for every caller, for
  at most 30 s. A longer statement refuses the call that received it at once
  (`FontePausata`, with the wait the source asked for) and never holds the
  source longer than 30 s, so a site that comes back is read again; with
  `LEGAL_CIRCUIT_BREAKER=on` (off by default) 3 consecutive failures (network
  error, 5xx, 429; never a 404) suspend the source for 5 minutes
  (`FonteSospesa`). Retries are `retry_request`'s, at most two.

**The limits hold within one process.** N processes against the same source
(a server, a worker and a command-line tool on one machine) make N times the
cap. A limiter shared between processes, for example through the cache
backend, is a possible later step, not part of this release.

The limits sit in a transport around the network one, so they count real
requests. A factory that brings its own transport drops them, unless it builds
its network transport with **`api.con_regole(fonte, transport)`**: put a cache
above it and its hits are served without waiting, while every request that
reaches the network keeps the source's limits.

```python
import httpx
from mcp_legal_it import api

def con_cache(fonte, **kwargs):
    rete = api.con_regole(fonte, httpx.AsyncHTTPTransport(verify=kwargs.pop("verify", True)))
    return httpx.AsyncClient(transport=MyCachingTransport(fonte, rete), **kwargs)

with api.configurazione(client_factory=con_cache, cache=False):
    ...
```

## 3. Norms

Shared outcome vocabulary, `EsitoNorma`:

| `esito` | Meaning |
|---|---|
| `trovato` | success |
| `riferimento_non_valido` | the citation could not be read |
| `atto_non_riconosciuto` | no act has that name; `errore` lists the closest names |
| `articolo_non_trovato` | the act exists, the article is not in it. Normattiva answers a missing article with art. 1; this is detected |
| `verifica_non_disponibile` | the source could not tell: down, slow, rate limited, or its structure unreadable |
| `testo_assente` | the source answered without a text |
| `errore_fonte` | the source answered with an error |
| `non_supportata` | a form of the request this version does not serve yet |

### `leggi_riferimento(testo: str) -> EsitoRiferimento`

Reads a citation (`"art. 2043 c.c."`, `"art. 6 GDPR"`, `"art. 2-bis D.Lgs. 196/2003"`,
`"allegato I.7 art. 30 D.Lgs. 36/2023"`) into one `NormaDati`. No network.

- **Esiti:** `trovato` (the act is identified; the article is not checked),
  `riferimento_non_valido`, `atto_non_riconosciuto`.
- **Resolution:** the same resolver as `cite_law`, hand-verified tables first
  (CLAUDE.md, "Risoluzione degli estremi normativi"). It never guesses: an
  unknown name is `atto_non_riconosciuto`, with the closest names in `errore`.

```python
r = api.leggi_riferimento("art. 2043 c.c.")
r.norma_data[0].urn   # 'urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043'
```

### `riferimento_da_parametri(tipo_atto, numero_articolo="", data="", numero_atto="", allegato=None, versione="vigente", data_versione=None, celex_consolidated=None) -> EsitoRiferimento`

The same, from explicit fields (the VisuaLex request body). No network.

- **Esiti:**
  - `trovato`;
  - `atto_non_riconosciuto`: an act type the resolver does not know. Long and
    short names are both accepted (`"decreto legislativo"`, `"d.lgs."`), and so
    are the codes by name (`"codice civile"`, `"costituzione"`);
  - `riferimento_non_valido`: no type; an EU regulation or directive without year
    (`data`) and `numero_atto`; or an Italian act without the date and number
    needed to build its address;
  - `riferimento_non_valido` also for a version that cannot be one: a
    `versione` other than `vigente` or `originale`, a `data_versione` that is not a
    date, a future one (Normattiva would answer it with today's text and say
    nothing), or a date together with `originale`;
  - `non_supportata`: a version of an EU act or of an annex.
- **Versions.** `data_versione` (`"2010-01-01"`, or the long form `"1 gennaio
  2010"`) asks for the text in force on that day: the URN gains `!vig=2010-01-01`
  and the export is asked at that day. **A date always means the text in force on
  that date**, with `versione="vigente"` or without it. This is a temporary
  divergence from VisuaLex, until its PR #276 lands: today its `generate_urn`
  reads the date only together with `versione="vigente"`, so a date sent alone
  gets today's text under the date asked for (art. 1284 c.c. «at 2010-01-01»
  came back with the 4th and 5th commi added in 2014). VisuaLex adopts the same
  rule there. `versione="originale"` asks for the original text, read from the
  page only (`@originale`): the export is a text in force on a day, and an act's
  own day can precede its entry into force. An article that did not exist yet on
  the day asked for (the page says «NON ANCORA ESISTENTE O VIGENTE») is
  `articolo_non_trovato`, and `errore` says from when it is in force. A version of
  an act cited with the year only whose full date could not be read is
  `verifica_non_disponibile`, asking for the date: the export would otherwise be
  asked at today's date. `NormaDati.versione` and
  `data_versione` carry the version to `testo_articolo`. The whole act, its index
  and its tree are today's: `indice_atto`, `testo_atto` and `albero_atto` answer
  `non_supportata` for a `NormaDati` with a version.
- **EU consolidated versions.** `celex_consolidated` (VisuaLex's key) names a
  consolidated version of an EU regulation or directive by its sector-0 CELEX:
  `"02002L0058-20091219"` is directive 2002/58/CE as amended up to 19 December
  2009. The Official Journal text is the act as published, which is the wrong text
  for an amended act (2002/58 without the 2009 amendment has no cookie rule in art.
  5(3)). The CELEX must have the shape (sector 0, ASCII digits, nothing after the
  date) and be this act's own (year, type and number): another act's consolidation
  is `riferimento_non_valido`, as is the field on an act that is not an EU
  regulation or directive. `url` is the consolidated page (VisuaLex's URL); the text
  is read from CELLAR's copy of it, with VisuaLex's reader: no «▼M2» marker, one
  line per point. A recital of a consolidated version is `non_supportata`: a
  consolidated text has no preamble, and its «(N)» paragraphs are footnotes. An annex
  of a consolidated version is `non_supportata` for now.

### `testo_articolo(riferimento: str | NormaDati, *, canale: Canale) -> TestoArticolo`

The text in force of one article, from Normattiva or EUR-Lex.

- **`canale` is required**, so that no default text channel reaches a caller by
  accident:
  - `"html"` reads the article's Normattiva page with VisuaLex's extractor,
    imported unchanged (`lib/visualex/normattiva_html.py`): `article_text` is
    VisuaLex's, byte for byte, accents and «(( … ))» amendment markers
    included. The Akoma Ntoso export is the last resort, when the page cannot
    be fetched or holds no article text, and `fonte` then says
    `normattiva-akn`. A page's reading is kept for 24 hours (memory and
    `MCP_CACHE_DIR/normattiva_pagine/`), so the same article asked again
    makes no request. This is what the MCP tools (`cite_law`,
    `fetch_law_article`, `verifica_citazioni`) read.
  - `"akn"` reads the Akoma Ntoso export first and the page as fallback. It is
    faster when warm, but the export transliterates accents (`attivita'`),
    drops the amendment markers and adds a heading of its own: never
    VisuaLex's display text.
  - EUR-Lex is always read from its HTML; `fonte` is `eurlex`.
- **`allegato` is Normattiva's position, as in VisuaLex.** A digit `allegato`
  (in a `NormaDati`, or `riferimento_da_parametri(..., allegato="2")`) is the
  `:k` of the URN, the entry of Normattiva's tree: it goes into the URL, and on
  the HTML channel the text is that page's. It is not the name the act gives an
  annex, which is often another number:

  | Act | Part | Name in the act | Position (`allegato`, URN) |
  |---|---|---|---|
  | r.d. 262/1942 | preleggi | Disposizioni sulla legge in generale | `1`, `;262:1` |
  | r.d. 262/1942 | codice civile | CODICE CIVILE | `2`, `;262:2` |
  | r.d. 1398/1930 | codice penale | Codice Penale | `1`, `;1398:1` |
  | d.lgs. 104/2010 | codice del processo amministrativo | Allegato 1 | `2`, `;104:2` ("Indice generale" is `:1`) |
  | l. 654/1975 | the Convention it executes | Convenzione | `2`, `;654:2` |
  | d.lgs. 36/2023 | Allegato I.7 / I.11 | Allegato I.7 / I.11 | `8` / `12` (a sub-part after a dash, "Allegato I.4-Tabella A", is not an entry) |

  Measured on the exports and checked live on 21/10/2026. A name the act gives
  ("I.7", "III") stays a name, and so does any `allegato` of an EU act (EUR-Lex
  URLs have no part). A part number is a positive integer without leading zeros:
  `"0"` or `"02"` is `riferimento_non_valido`. An annex article read from the
  part's page on the HTML channel is served only if the page's text is the
  export's article (accents aside); a position two parts share builds no URN. A citation of an annex by a digit name
  ("allegato 1 al d.lgs. 104/2010") keeps the annex in `numero_articolo`
  (`"allegato 1 art. 120"`) with `allegato=None`, so that it is never read back
  as a position.
- **`allegato` in `norma_data` is what VisuaLex files the norm under**, nothing
  more: the `allegato` the caller gave, a code's default part (c.c. `"2"`, c.p.
  and c.p.c. `"1"`, as VisuaLex gives them), or `None`. The part an answer was
  served from is in `url` and `urn` only: "art. 120 d.lgs. 104/2010" answers
  with `urn` `…;104:2~art120` and `allegato=None`. Passing a code's default
  part back (`allegato="2"` for the c.c.) reads the article, not an annex.
  The `None` of the codes whose URN gained its part on 21/10/2026 is
  **provisional** (see §8, «Saved norms keep their key»).
- **`url` and `urn`** are both always filled for Normattiva acts (EU acts have
  no NIR URN). An act cited with the year only whose full date could not be
  read keeps the URN derived from its URL. That URN has a placeholder date,
  `YYYY-01-01`, and `norma_data.data_risolta` is `False`.
- **A text without a date is the text in force today.** Normattiva's page
  without a date can serve a version not in force yet: on 21/10/2026 art. 3 of
  d.P.R. 131/1986 came back «ARTICOLO ABROGATO DAL D.LGS. 1 AGOSTO 2025, N. 123…»,
  «Testo in vigore dal: 01-01-2027», while the article is in force today. When the
  page states a window that starts after today, or states none, the page at
  today's date (`!vig=<today>`) is read: one request more, only then, and `url`
  is that page's. If it cannot be read, the export at today's date answers (never
  the undated page). The coming version is an `avviso`, and its repealing act is
  `successione` with `dal`. **`upcoming`** carries the same facts as VisuaLex's
  `upcoming`, key for key: `change` (`abrogated` when the coming version repeals
  the article, else `amended`), `valid_from`, `version_number`; `None` when the
  undated page was today's text. This is a deliberate, temporary divergence from
  VisuaLex, which serves the undated page as it is: VisuaLex adopts the same rule
  (its decision G-355), and the two converge with VisuaLex <SHA>.
- **`cite_law(..., formato="json")`** carries the same two facts under the same
  names, and both keys are always present so the schema does not change with the
  answer: `avvisi` (a list, `[]` when there is nothing to say) and `upcoming` (the
  object above, or `null`). The Markdown form prints the notice as a line
  «**Attenzione**: …».
- **`validity`** is what the page states of the text it served: the window
  «Testo in vigore dal … al …», the version, the repeal (VisuaLex's
  `extract_validity`, imported). It is read from the same page as the text, when
  it is fetched: no second request. `None` for the export's text or a page that
  does not say.
- **`precisione`**: `ESATTO` only for the text of Normattiva's page whose
  validity the page states (decision LI-031); `INDICATIVO` for the export's text
  or a page that does not say, or a page whose window does not hold the date
  asked for (`validity.request_in_window` is `False`, and an `avviso` says so).
  **`avvisi`**: what the reader must know about the text (the coming version, an
  unread window, a window that misses the date, the export's text with the day it
  was consolidated). **The two channels are checked against each other** wherever
  the other one is already at hand, with no request: the page kept a day, the
  export in its cache. When they disagree on the repeal, an `avviso` says which
  says what; when the export's consolidation day differs from the day the act's
  page says it was updated, an `avviso` says the two texts may differ.
  **`successione`**: the act that repealed the article (or will), as the repeal
  notice names it, derived automatically and always `INDICATIVO`.
- **Esiti:** the whole `EsitoNorma` vocabulary.

```python
t = await api.testo_articolo("art. 99999 c.c.", canale="html")
t.esito    # 'articolo_non_trovato'
```

### `testi_articoli(riferimenti, *, canale: Canale, concorrenza: int = 4) -> list[TestoArticolo]`

`testo_articolo` for many articles, in input order, at most `concorrenza` at a
time. Articles of the same act share one download of the act.

### `indice_atto(atto: str | NormaDati) -> IndiceAtto`

The article headings of an Italian act: VisuaLex's `/fetch_rubriche`, from the
act's Akoma Ntoso export (two requests cold, none warm: the export is cached).

- `title`: the act's title as a heading (`presentable_title`: no Gazzetta code,
  no amendment brackets, accents restored).
- `rubriche` maps each article key of the act's main text (`"1"`, `"2-bis"`) to
  its heading, accents restored; an article without a heading is absent.
  `count` is `len(rubriche)`. `abrogati`: the keys of the repealed articles.
- `parts`: one dict per part of the export, VisuaLex's keys `name`, `keys`,
  `rubriche`, `abrogati`, plus `allegato`, the part's Normattiva number (`None`
  for the Dispositivo or a position two parts share). Each annex has its own
  art. 1 with its own heading.
- When the export cannot be read (Normattiva down, `AKN_DISABLED`), Normattiva's
  `vediRubriche` answers: `rubriche` from its lines and `voci` (the lines as
  listed), with no `title`, `abrogati` or `parts`. `voci` is empty when the export
  answered.
- **Esiti:** `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`,
  `non_supportata` (EU acts), `verifica_non_disponibile`, `errore_fonte`,
  `testo_assente`.

### `albero_atto(atto: str | NormaDati, *, link: bool = False, dettagli: bool = False) -> AlberoAtto`

Normattiva's article tree of an Italian act: VisuaLex's `/fetch_tree`, read by
VisuaLex's parser (`lib/visualex/albero_normattiva.py`, imported) from the
act's page. One request, kept a day; every variant is read from the same page.

- `articles`: `{"numero", "allegato"}` per article in the act's order, plus `url`
  with `link=True` and the section labels (strings) with `dettagli=True`.
  `allegato` is Normattiva's part number (`None` for the act's own text): the
  same number as `NormaDati.allegato`.
- `metadata["annexes"]`: `number`, `label`, `article_count`, `article_numbers`
  per part.
- **Esiti:** `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`,
  `non_supportata` (EU acts), `verifica_non_disponibile`, `errore_fonte`.

### `articolo_nell_albero(albero: AlberoAtto, articolo: str, allegato: str | None = None) -> bool | None`

VisuaLex's existence check, before an article is fetched, as a function. Whether
*articolo* is in the tree, in part *allegato* when given (`""` is the act's own
text). `None` when the tree was not read: an outage is never "the article does not
exist". Article numbers are compared in canonical form ("1-bis" = "1 bis"). No
network.

### `dove_altrove(albero: AlberoAtto, articolo: str, allegato: str | None) -> str`

Where else in the act *articolo* is, as a sentence to append to a refusal
(`": su Normattiva l'art. 120 si trova nell'allegato 2"`), or `""`. No network.
`testo_articolo` adds the same sentence to its `articolo_non_trovato` answers,
read from the export it already has.

### `testo_atto(atto: str | NormaDati) -> TestoAtto`

The whole text of an Italian act from Normattiva. It can be very long for the
codes.

- **Esiti:** as `indice_atto`. `testo_assente` covers a text under 50 characters.

### `annotazioni_brocardi(riferimento: str) -> AnnotazioniBrocardi`

Brocardi notes on an article: ratio, explanation, brocardi, case-law abstracts.

- This is **third-party editorial content, never the norm**. Whether to show it
  is the consumer's call.
- The Brocardi switch is honoured. When it is off, the answer is
  `brocardi_disattivato` and no request is made.
- **Esiti:** `trovato`, `brocardi_disattivato`, `riferimento_non_valido` (also
  when no article is given), `atto_non_riconosciuto`, `non_supportata`
  (annexes), `errore_fonte`, `testo_assente`.

### `catalogo_alias() -> CatalogoAlias`

The act names the resolver knows, in VisuaLex's `/fetch_alias_catalog` shape.
No network.

- `presets`: the hand-verified short names (`gdpr`, `ai act`, `tub` …) mapped to
  `{act_type, act_number?, date?}`.
- `known_acts`: every name `leggi_riferimento` recognises, sorted.

### Constants

- **`SUFFISSI_ARTICOLO`**: the Latin ordinals after an article number, from
  `bis` (2nd) to `vicies` (20th), each with the other spellings Normattiva
  prints (`novies`/`nonies`, `quinquiesdecies`/`quindecies`,
  `octiesdecies`/`duodevicies` …). Built from VisuaLex's suffix table, which
  mcp-legal-it imports byte for byte (`lib/visualex/article_suffixes.py`).
- **`ARTICLE_SUFFIX_ALTERNATION`**: VisuaLex's regex alternation of all those
  spellings plus `semel` ("vicies semel", 21st), longest first. Close the group
  with `\b`, or a suffix matches the head of an ordinary word ("art. 5 bisogna"):
  `rf"(\d+)-?({ARTICLE_SUFFIX_ALTERNATION})\b"`.

## 4. Decisions

One result shape for every court:

- `EsitoDecisione` for a decision read (VisuaLex `/fetch_decision`);
- `RicercaDecisioni` for a search (VisuaLex `/search_decisions`).

**Source codes.** `fonte.codice` (`CodiceFonte`) and `RicercaDecisioni.fonte`
name the source as VisuaLex does: `cassazione`, `corte_costituzionale`, `curia`,
`giustizia_amministrativa`, plus `cerdef`. A `fonte_non_raggiungibile` answer
always carries it, so the shell can write
`{"esito": "fonte_non_raggiungibile", "fonte": fonte.codice}`.

**Sezione.** For the Cassazione, `attributi.sezione` is the Italgiure code in
upper case (`1`–`7`, `L`, `U`, `F`), the form VisuaLex's resolver and saved
records accept.

**Text.** `testo_grezzo` is the text exactly as the source serves it:

- Cassazione: `testo` = `ocr`, `dispositivo` = `ocrdis`;
- Corte costituzionale: `epigrafe`, `testo`, `dispositivo`;
- CeRDEF: `testo`, `massima`.

The MCP tools cut the text into windows; the API never truncates.
`testo` (VisuaLex's block form, `TestoDecisione`) is **planned** and `None`
today.

Outcomes of a read, `EsitoLettura`:

| `esito` | Meaning |
|---|---|
| `trovata` | success |
| `ambigua` | the same number and year name more than one decision. `candidati` lists them; ask again with `archivio` or `sezione` |
| `non_trovata` | not found. `motivo` says why: `inesistente`; `fuori_archivio` (older than the archive window, `archivio_dal` says where it starts); `anno_parziale` (the first year of the window, or the current year, which the index covers only in part). In the last two cases a miss proves nothing |
| `richiesta_non_valida` | the request is malformed (`errori`) |
| `fonte_non_raggiungibile` | the source did not answer |
| `errore_fonte` | the source answered with an error |
| `non_supportata` | not served in this version |

**Search outcomes** (`EsitoRicerca`):

- **No hit is not an error.** It is `risultati` with `totale == 0` and no
  `decisioni`, as in VisuaLex.
- **`troncato=True`** means the source stopped before the end, so fewer hits
  than asked does not mean there are no more.
- **`totale`** is the source's own count. It is `None` when the source gives
  none.

### `leggi_decisione(riferimento: RiferimentoDecisione) -> EsitoDecisione`

One decision by court, number and year.

- **Courts served:**
  - `cassazione`: `archivio` `civile`/`penale`, optional `sezione` (`"3"`,
    `"L"`, `"U"`/`"SU"`, `"T"`). Italgiure's archive is a moving window of about
    five years. A number found in both archives is `ambigua`. A section other
    than the cited one adds the warning `sezione_diversa`.
  - `corte_costituzionale`.
- **Other courts** answer `non_supportata` (planned). Read them by the source
  key their search returns, with the readers below.

```python
d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=10579, anno=2022))
d.esito                                    # 'ambigua': one civil and one criminal decision
[c.identita.archivio for c in d.candidati] # ['civile', 'penale']
```

### `leggi_provvedimento_tributario(guid: str) -> EsitoDecisione`

A CeRDEF decision by the `guid` of a search result (`identita.chiave_fonte`).

- **Esiti:** `trovata`, `non_trovata` (CeRDEF does not know the guid),
  `richiesta_non_valida`, `fonte_non_raggiungibile`, `errore_fonte`.

### `leggi_provvedimento_amministrativo(sede: str, nrg: str, nome_file: str) -> EsitoDecisione`

A TAR / Consiglio di Stato decision by the key a search result carries
(`identita.chiave_fonte`).

- A decision published only as a PDF is `trovata` without `testo_grezzo`, with
  the warning `testo_non_disponibile` (`motivo: solo_pdf`, `url`).
- An outdated key (the portal answers with an error page) is `non_trovata`.

### `leggi_sentenza_cgue(cellar_uri: str) -> EsitoDecisione`

A Court of Justice / General Court decision in Italian, by the CELLAR URI a
search returned. ECLI, case number and date are read from CELLAR, best effort.

- **Only CELLAR is fetched.** The URI must be
  `http(s)://publications.europa.eu/resource/cellar/…` or `…/resource/celex/…`:
  no other host or port, no user info, query or fragment. Anything else is
  `richiesta_non_valida` before any request.
- **Esiti:** `trovata`, `non_trovata` (empty or invalid page),
  `richiesta_non_valida`, `fonte_non_raggiungibile`, `errore_fonte`.

### `cerca_decisioni_cassazione(tema=None, norma=None, *, archivio=None, pagina=1, per_pagina=20, anno_dal=None, anno_al=None, materia=None, sezione=None, solo_sezioni_unite=False, tipo_provvedimento=None) -> RicercaDecisioni`

A full-text search of the Cassazione archive (`modo="testo"`).

- **Arguments:**
  - `norma` (`"art. 2043 c.c."`) keeps only the decisions citing that article.
    Alone, it finds every decision that cites it.
  - At least one of `tema` and `norma` is required.
  - `pagina` starts at 1; `per_pagina` is 1 to 50.
- **Each hit** carries `identita`, `attributi` and `frammento`: the highlighted
  passage as text, with the `[start, end)` offsets of the matched words.
- **`anni`**: the years facet.
- **`archivio_dal`**: where the archive window starts.
- **Nothing is relaxed or narrowed automatically.** The MCP tool does that for
  agents; the API returns what the archive returns.
- **Planned:** VisuaLex's index search (`modo="indice"`).

### `giurisprudenza_su_articolo(riferimento, *, archivio=None, pagina=1, per_pagina=20, anno_dal=None, anno_al=None, sezione=None, solo_sezioni_unite=False) -> RicercaDecisioni`

The Cassazione decisions that cite an article. It is `cerca_decisioni_cassazione`
with `norma=` only. Name the act: a bare `"art. 13"` matches any act's article 13.

### `cerca_decisioni_costituzionali(tema, *, tipo=None, anno_dal=None, anno_al=None, max_risultati=10) -> RicercaDecisioni`

Corte costituzionale decisions from the open data.

- `tema`: comma-separated alternatives. `tipo`: `"sentenza"` or `"ordinanza"`.
- Without years, only the current year is read.

### `pronunce_costituzionali_su_norma(riferimento, *, anno_dal=None, anno_al=None, max_risultati=10) -> RicercaDecisioni`

The decisions whose massime invoke `riferimento` as a parameter of
constitutionality. `frammento` is the massima's text; `attributi.titolo` is its
title.

### `cerca_decisioni_tributarie(tema, *, ente="", tipo_provvedimento="", data_da="", data_a="", numero="", criterio="tutti", ordinamento="rilevanza", max_risultati=10) -> RicercaDecisioni`

CeRDEF tax case law.

- Dates are `GG/MM/AAAA`. `criterio` is `tutti`, `frase_esatta`, `almeno_uno` or
  `codice`.
- A filter CeRDEF would not understand is `richiesta_non_valida`.
- `troncato=True` means the first-instance filter stopped at its scan limit.

### `cerca_decisioni_amministrative(tema, *, sede="", tipo="", anno="", numero="", max_risultati=10) -> RicercaDecisioni`

TAR and Consiglio di Stato decisions.

- The portal cannot filter by year alone. A year without a number is applied to
  the page the portal returned, so `totale` is `None` and `troncato` is `True`.
- `sede` takes the city or the legacy code (`"Roma"`, `"CDS"`).

### `cerca_decisioni_ue(tema, *, corte="", tipo="", anno_dal="", anno_al="", materia="", max_risultati=10) -> RicercaDecisioni`

Court of Justice and General Court decisions, searched by title in CELLAR.

- `tema`: comma-separated alternatives. `corte`: `"CJ"` or `"TJ"`.
- `tipo`: `"JUDG"`, `"ORDER"` or `"OPIN_AG"`.

### `giurisprudenza_ue_su_articolo(riferimento, *, corte="", anno_dal="", max_risultati=10) -> RicercaDecisioni`

EU decisions whose title cites a provision (`"art. 82 GDPR"`, `"art. 101 TFUE"`).

- This searches titles, not CELLAR's citation graph.
- VisuaLex's `/search_eu_case_law` (by CELEX and article, over citations) is a
  different query, and it is planned.

### `cerca_giurisprudenza_unificata(tema, *, fonti=("cassazione","tributaria","amministrativa","ue"), anno_dal=None, anno_al=None, max_risultati=5) -> dict[str, RicercaDecisioni]`

The same query on several sources at once.

- `fonti` may also include `costituzionale`.
- One source down is that entry's `esito`, never a failure of the whole call.
- Each source is searched as its own function does.
- A year range reaches the administrative portal only when
  `anno_dal == anno_al`.

## 5. Types

All results are frozen dataclasses (`mcp_legal_it/api/tipi.py`).

### Outcomes and channels

| Type | Values |
|---|---|
| `EsitoNorma` | the norm outcomes (§3) |
| `EsitoLettura` | the outcomes of reading a decision (§4) |
| `EsitoRicerca` | the outcomes of a search (§4) |
| `Canale` | `"akn"` \| `"html"` |

### Norm types

| Type | Fields |
|---|---|
| `NormaDati` | `tipo_atto, data, numero_atto, url, allegato, numero_articolo, versione, data_versione, urn`, plus `descrizione, data_risolta`, and VisuaLex's `celex_consolidated` last |
| `EsitoRiferimento` | `esito, norma_data: tuple[NormaDati, ...], errore` |
| `TestoArticolo` | `esito, article_text, norma_data, url, validity`, plus `urn, fonte, canale, data_consultazione, errore, fonti, precisione, avvisi, successione, upcoming` |
| `Vigenza` | VisuaLex `validity`: `state, valid_from, valid_to, version_number, act_updated, request_in_window` |
| `IndiceAtto` | `esito, title, rubriche, abrogati, parts, count`, plus `voci, codice_redazionale, data_gu, url, errore, fonti` |
| `AlberoAtto` | VisuaLex `/fetch_tree`: `esito, articles, count, metadata`, plus `url, errore, fonti` |
| `TestoAtto` | `esito, testo, titolo, url, errore, fonti` |
| `AnnotazioniBrocardi` | `esito, url, ratio, spiegazione, brocardi, massime, errore, fonti` |
| `MassimaBrocardi` | `autorita, numero, anno, testo` |
| `CatalogoAlias` | `presets, known_acts` |

### Decision types

| Type | Fields |
|---|---|
| `RiferimentoDecisione` | `corte, numero, anno, archivio, sezione, sede, provvedimento, tipo` |
| `Identita` | `corte, numero, anno, archivio, sede, provvedimento`, plus `chiave_fonte` (the CeRDEF guid, `{sede, nrg, nome_file}` for TAR/CdS, the CELLAR URI for the CJEU) |
| `Attributi` | `sezione` (Cassazione: Italgiure code), `tipo, data_deposito, data_decisione, ecli, relatore, presidente, materia`, plus `estremi, titolo` (dates ISO) |
| `TestoDecisione` | VisuaLex blocks: `epigrafe, motivazione, dispositivo` (planned) |
| `TestoGrezzo` | `testo, epigrafe, dispositivo, massima`, as the source serves them |
| `FonteDecisione` | `nome, licenza, url`, plus `codice` |
| `CodiceFonte` | `"cassazione"` \| `"corte_costituzionale"` \| `"curia"` \| `"giustizia_amministrativa"` \| `"cerdef"` |
| `Avviso` | `tipo, dettagli` (`come_dict` flattens it) |
| `Candidato` | `identita, attributi` |
| `EsitoDecisione` | `esito, identita, attributi, testo, fonte, avvisi, candidati, motivo, archivio_dal, errori`, plus `testo_grezzo, errore, fonti` |
| `Frammento` | `testo, evidenziati: tuple[tuple[int, int], ...]` |
| `DecisioneTrovata` | `identita, attributi, trovata, frammento` |
| `RicercaDecisioni` | `esito, fonte, totale, pagina, modo, archivio, archivio_dal, decisioni, anni`, plus `troncato, errori, errore, fonti` |

### Provenance and serialisation

| Name | What it is |
|---|---|
| `FonteConsultata` | `fonte, url` |
| `FontiConsultate` | `consultate_al, fonti` |
| `come_dict` | `come_dict(valore) -> Any`: any result as JSON-ready data (§1) |

## 6. Planned functions

These operations are part of the contract but **not in `__all__` yet**. The
migration phase fills them in, taking the better implementation of each piece
from VisuaLex and mcp-legal-it, and only then adds them to the frozen surface
with their signature.

| Planned operation | VisuaLex route it backs |
|---|---|
| Multi-article references (`"1,2"`, `"3-5"`) | `/fetch_norma_data` |
| EU recitals | `/fetch_recitals` |
| Per-article fingerprints | `/fetch_act_fingerprints` |
| Full dates of year-only URNs, in batch | `/resolve_act_dates` |
| Natural-language query to references | `/parse_query` |
| Citations in free text | `/extract_citations` |
| Decision text in VisuaLex's block form (`TestoDecisione`) | `/fetch_decision` |
| TAR/CdS/CGARS/CJEU/General Court read by number and year | `/fetch_decision` |
| Cassazione index search (`modo="indice"`) | `/search_decisions` |
| EU case law on an article over CELLAR citations | `/search_eu_case_law` |
| Decision citation reader | `/parse_decision` |
| Original decision PDF | `/fetch_decision_pdf` |

## 7. Versioning and deprecation

`mcp_legal_it.api` follows the package's semver.

- **Patch.** Fixes that keep every name, signature, field and `esito` value.
- **Minor.** Additions only: a new function, a new optional keyword parameter
  with a default, a new field with a default, a new `esito` value. A consumer
  must tolerate added fields and treat an unknown `esito` like `errore_fonte`.
- **Major.** Removing or renaming anything, changing a type or a default,
  making an optional parameter required.

**Deprecation.**

1. A name to be removed is first marked deprecated in a minor release: in this
   document, in the CHANGELOG, and with a `DeprecationWarning` when it is used.
2. It is removed no earlier than the next major release, and at least 90 days
   after the deprecating release.
3. The replacement is available from the deprecating release on.

**Refactors behind the API** must leave the MCP tools' answers unchanged.
`scripts/replay_mcp_outputs.py` proves it: it records the real HTTP exchanges
of 36 tool calls once, then replays them offline against a git ref and the
working tree and compares every answer, `_meta` included. The tape stays
local: it holds third-party content and hundreds of MB of open data.

The frozen surface is `tests/unit/test_api_surface.py`. It pins every public
name with its signature, or with its fields for a type. An intentional change
updates that test, this document and the CHANGELOG in the same change.

## 8. For VisuaLex

**The subset the VisuaLex shell uses.** Every function in §3 and §4 except
`annotazioni_brocardi`: VisuaLex does not serve Brocardi content.

**When to switch which route.** The text routes (`/fetch_article_text`,
`/stream_article_text`, `/fetch_all_data`) can switch to `canale="html"`, which
returns VisuaLex's `article_text` byte for byte (checked against VisuaLex's
frozen hashes and a live run of its `collector_timing.py`), with `validity`
read from the same page. One exception, until VisuaLex <SHA>: when the undated page
serves a version not in force yet, this library serves today's page (see
`testo_articolo`). Multi-article references come with the next phases. `/fetch_decision` switches
**only once** the block form of §6 exists.

- `canale="akn"` text is not VisuaLex's frozen `article_text`: AKN and HTML
  readings differ, and must never reach VisuaLex's anchors.
- Today's `testo_grezzo` is not VisuaLex's block projection, so its hashes would
  differ.

**Migration constraints.**

- **VisuaLex's goldens stay the reference.** These are VisuaLex's own tests and
  must keep passing against this library before any route switches:
  - `article_text` byte-identical;
  - the decision-text projection hashes (`test_decisions_text_frozen.py`);
  - the `parse_query` display and `parse_decision` readings;
  - the sources golden (`conventions/sources/`).
- **The TypeScript copies stay in sync.** VisuaLex keeps TypeScript copies of
  its article-suffix and act-type tables, checked by the sources golden. Any
  change to `SUFFISSI_ARTICOLO`, `ARTICLE_SUFFIX_ALTERNATION` or the act tables
  that VisuaLex consumes must keep that golden green. mcp-legal-it's copies are
  pinned to VisuaLex's files by sha256 (`tests/unit/test_article_suffixes.py`,
  `tests/unit/test_visualex_golden.py`): VisuaLex changes them first.
- **`identita` does not drift.** Its fields are shared by page addresses,
  dossiers and remote clients. Adding a field is allowed; renaming or reshaping
  one is not.
- **Saved norms keep their key.** VisuaLex identifies a saved norm by a key
  derived from it, `norma_key`, not by its URN: `decreto_legislativo_AAAA_MM_GG_N`,
  `codice_civile`, `codice_penale`, `regolamento-ue--AAAA--NNNN::art::N`. Any
  change that alters that key for an existing norm (a code's URN, a date, an act
  type) needs an alignment on VisuaLex's side before the shell switches to the
  3.0 package. The shell switches only after realigning the saved norms whose
  code URN differs from VisuaLex's table. Today these are the codes whose URN
  gained the part holding their articles on 21/10/2026: codice del turismo
  (`;79:1`), codici penali militari (`;303:1`), norme di attuazione del c.p.p.
  (`;271:1`), regolamento per la navigazione marittima (`;328:1`), and the acts
  cited by their own number whose articles are an annex: c.p.p. minorile
  (d.P.R. 448/1988, `;448:1`), TULPS (r.d. 773/1931, `;773:1`), TU successioni
  (d.lgs. 346/1990, `;346:1`). For the codice del turismo no saved norm depends
  on it, so it needs no data migration, only the code fix in VisuaLex. VisuaLex
  corrects the URN only, never `norma_data.allegato`: for these seven the
  `:1` is in the URN and `allegato` stays `None`, as VisuaLex has it, so their
  item keys do not change. The same holds for the codice penale militare di pace (`;303:1`)
  and di guerra (`;303:2`), added on 21/10/2026 and absent from VisuaLex's table.
  **Provisional:** this `allegato=None` rule for those nine depends on a decision
  still open on VisuaLex's side, which may file them with `allegato` "1" (or "2")
  as it does the c.c. and the c.p.; it is not part of the frozen contract until
  that decision is taken.
- **Serialisation stays the shell's job.** Key order, ASCII escaping, the NDJSON
  stream: `come_dict` returns data, not JSON text.
