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
separate async function, `risolvi_atto` (§3), one act per call; the batch form
is planned (§6). If a remote
catalogue is ever needed, it gets an async variant next to the sync one, and
the existing signature does not change.

**Errors are data.** A function never raises for an outcome a caller must
expect: an unknown act, a missing article, a source that is down, an ambiguous
number. The result carries:

- `esito`, a closed vocabulary listed in the type (`EsitoNorma`,
  `EsitoLettura`, `EsitoRicerca`, `EsitoAtto`). New values can only appear in a minor
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
    `versione` other than `vigente`, `originale` or `futura`, a `data_versione` that
    is not a date, a future one (Normattiva would answer it with today's text and say
    nothing; with `futura` it must instead be after today), or a date together with
    `originale`;
  - `non_supportata`: a version of an EU act (`futura` included) or of an annex.
- **Versions.** `data_versione` (`"2010-01-01"`, or the long form `"1 gennaio
  2010"`) asks for the text in force on that day: the URN gains `!vig=2010-01-01`
  and the export is asked at that day. **A date always means the text in force on
  that date**, with `versione="vigente"` or without it, as in VisuaLex since
  4aa59a9d (its PR #276; before it, a date sent alone got today's text under the
  date asked for: art. 1284 c.c. «at 2010-01-01» came back with the 4th and 5th
  commi added in 2014). A date together with `versione="originale"` is
  `riferimento_non_valido`: the two ask for different texts. VisuaLex refuses the
  pair too since f47ac1b6 (before it, the date won).
  `versione="originale"` asks for the original text, read from the
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
- **The text not in force yet** (`versione="futura"`, VisuaLex's `upcoming: true`,
  its decision G-357; Normattiva acts only). The undated page, when its window
  starts after today: `not_in_force` is `True`, `precisione` `INDICATIVO`, the
  first `avviso` says it is not the text in force today and from when it is,
  `upcoming` describes it, `validity.request_in_window` is `True`, and `norma_data`
  is dated to the day it comes into force (`versione="vigente"`, `data_versione`
  that day; `url` and `urn` stay the undated page's), so it reads as a text at a
  day. The page at today's date (one request more) tells an article inserted from
  that day (`change` `inserted`) from one changed by it (`amended`; `None` when that
  page cannot be read, `abrogated` for a coming repeal). An optional `data_versione`,
  after today, is the latest day it may come into force. None published, or none by
  that day, is `articolo_non_trovato` («Nessuna versione non ancora in vigore …»,
  «… entra in vigore il …»). A day that falls before the latest version, with other
  versions not in force yet before it (`versions_between`), is
  `verifica_non_disponibile` («Non so dire quale versione … sia in vigore il …»):
  Normattiva shows only the latest, as in VisuaLex since 02ebc80a. A page whose validity cannot be read is
  `verifica_non_disponibile` («Non riesco a leggere la vigenza …»). An annex is
  `non_supportata`. `cite_law(..., versione="futura")` does the same, without a
  day.
- **An article inserted from a later day** (nothing of it is in force today: the
  page at today says «NON ANCORA ESISTENTE O VIGENTE», the undated page is its later
  text), asked without a version, is served as VisuaLex serves it (its G-358): the
  later text, `not_in_force` `True`, `precisione` `INDICATIVO`, `upcoming`
  `{change: "inserted", valid_from, version_number}` and a first `avviso` that it is
  not in force yet and from when. `norma_data` keeps the request's key (no date),
  `validity` is the page's. No extra request: both pages were read to look for
  today's text.
- **The text in force of an EU act** (issue #50). For a regulation or a directive
  without a date, `testo_articolo` serves the **latest consolidation** EUR-Lex
  publishes that applies today, when that consolidation includes an amending act or
  a corrigendum. A consolidation dated after today is not the text in force: it is
  said in `upcoming` (`{change: "amended", valid_from, version_number: None,
  celex}`) and in an `avviso`. The lookup is one SPARQL query to CELLAR per act,
  kept a day in memory under the base CELEX, through the `eur_lex` network rules,
  with a 12 s timeout and no retry; a failure is remembered for five minutes, so a
  down endpoint costs one wait per act, not one per citation. Art. 111 of the AI Act is read
  from 02024R1689-20260727, which includes Reg. (UE) 2026/1744. The GDPR is read from
  02016R0679-20160504, which includes the corrigenda: the Official Journal page lacks
  the Italian corrigendum, and 36 of its 99 articles differ in their words (art. 7
  «presta» il consenso, art. 41 «controllo»). The answer says which text it is:
  `consolidato` = `{celex, data, modificato_da: [{celex, atto}]}`, `precisione`
  `INDICATIVO`, and an `avviso` that a consolidated text is EUR-Lex's documentation,
  not authentic, and that only the text published in the Official Journal is. A
  corrigendum published in the Official Journal changes the text in force, so it
  counts; a consolidation made of corrigenda only says it «incorpora le rettifiche
  pubblicate in GUUE».
  - **No amending consolidation, or none at all:** the Official Journal text,
    `ESATTO`, `consolidato` None. Dir. 2019/790 has only its initial consolidation,
    the base act again.
  - **CELLAR could not say:** the Official Journal text, served anyway because it is
    authentic. `consolidato_verificato` is `False`, `precisione` is `INDICATIVO`, and
    the **first** `avviso` says the text may not be the one in force. `cite_law`
    prints it as its first line.
  - **`versione="originale"`:** the Official Journal text, with no lookup.
  - **`data_versione`:** the latest consolidation dated on or before that day,
    `INDICATIVO`. The `avviso` adds that EUR-Lex consolidations can lag behind
    amendments, so the Official Journal should be checked for amending acts published
    after the consolidation's date. A day after the act's publication in the
    Official Journal but before its first amending consolidation gives the Official
    Journal text; before the act's entry into force an `avviso` says it was
    published but not in force yet. A day before the act's publication in the
    Official Journal (not its adoption: the AI Act was adopted on 13.6.2024 and
    published on 12.7.2024) is `riferimento_non_valido`.
  - **An article the consolidation does not have** (a later act repealed or deleted it:
    art. 1 of dir. 2009/136 is not in 02009L0136-20201221) is `articolo_non_trovato`,
    and `errore` and an `avviso` say so: «non presente nel testo consolidato al … (CELEX
    …): probabilmente abrogato o soppresso da un atto successivo; il testo pubblicato
    in GUUE è disponibile con versione="originale"». `consolidato` names the
    consolidation checked. The Official Journal article is not served in its place: it
    would present a repealed text as current. No extra request.
  - **Not looked up:** treaties (unchanged), recitals (a consolidation has no
    preamble, and amendments do not rewrite recitals), and annexes. A consolidation's
    annexes are not read yet, so an annex is the Official Journal's, `INDICATIVO`,
    with an `avviso` that it may not be the one in force.
  - `consolidato_verificato`: `True` when CELLAR was asked, `False` when it could
    not say, `None` when not asked (an Italian act, a treaty, the original, a recital,
    an annex, a consolidation named by the caller).
  - This is a temporary divergence from VisuaLex, which serves the Official Journal
    text by default, **until VisuaLex follows**: it has adopted the same rule.
  - `cite_law(..., versione="originale")` asks for the original text: the Official
    Journal text of an EU act, or Normattiva's original of an Italian act (`@originale`;
    an act cited with the year only whose full date cannot be read has none). Its
    JSON carries `consolidato` and `consolidato_verificato` always (`null` when they
    do not apply).
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

### `risolvi_atto(tipo_atto: str, numero_atto: str, anno_o_data: str) -> AttoRisolto`

The full date and NIR URN of an Italian act, read from its Normattiva page. It is async
and makes at most two requests per act: the act's page, and one more for the check when
that page is Normattiva's error page (below; the check is shared per event loop).

- **Input:**
  - `tipo_atto`: any name `riferimento_da_parametri` accepts (`"d.lgs."`, `"legge"`,
    `"decreto ministeriale"`).
  - `numero_atto`: digits; leading zeros are dropped.
  - `anno_o_data`: the year (`"1993"`) or a date (`"1993-09-01"`, `"1 settembre 1993"`,
    `"1° settembre 1993"`).
- **How:** the act's own page is asked by its year (`…:1993-01-01;385`, which Normattiva
  tolerates), never its art. 1, so an act without an art. 1 resolves too.
  - **ESATTO:** for the types in `TIPI_ATTO_VERIFICATI`, the date is read from the
    page's title. It is accepted only when the title names this act's type, year and
    number, because Normattiva's resolver does not check what it is asked and a page of
    another act gives no date. The seven types are `legge`, `decreto legislativo`,
    `decreto legge`, `decreto del presidente della repubblica`, `regio decreto`,
    `regio decreto legge` and `legge costituzionale`, named as `normalize_act_type`
    names them, so `"d.lgs."` and `"d.P.R."` count.
  - **INDICATIVO:** for the other types it accepts (DPCM, `decreto ministeriale`, d.lgs.
    luogotenenziale), the page's ELI date is used, when it falls in the year given. This
    is the weaker check the library already used for these types. A caller that wants
    only verified dates skips them before calling, or reads `precisione`.
- **Cache and limits:**
  - A date read from a title is kept a year on disk (`act_dates.json` in the cache
    directory, the same file `cite_law` uses), and the page in memory for the process.
    A miss or a failure is never kept.
  - Concurrent calls for one act share one request.
  - The requests go through the library's client, with the factory of
    `configurazione`/`configura` and the `normattiva` limits (§2, **Network rules**).
    The limits are at most 3 requests in flight and 0.5 s between two, for the whole
    process. A `Retry-After` of a 429 or 503 pauses the source for at most 30 s. They
    are shared with every other call that reads Normattiva.
  - **Cost:**
    - one request for an act not seen before;
    - when its page is the error page, one more for the check, unless a check answered
      in the last five minutes (success) or one minute (failure). One check in flight
      is shared by every call that needs it, so N concurrent misses cost N pages and
      one check;
    - none for an act whose date is in the disk cache, or whose page this process
      already read;
    - never the act's art. 1 or its index.
  - An answer from the disk cache has `fonti=None`: no source was reached.
  - **Transient failures:**
    - `fonte_non_raggiungibile` and `errore_fonte` are transient: retry later, and do not
      cache them. Neither ever comes with a date, and the library keeps neither (nor the
      page that caused it), so the next call asks again.
    - `fonte_non_raggiungibile` covers:
      - a 429, 403 (a WAF or rate block, not a fact about the act) or 5xx on the act's page;
      - a network error, and a source the limits have paused (`FontePausata`, `FonteSospesa`);
      - a page that says the session expired, or announces maintenance;
      - any other answer without an act: a 2xx other than 200 (a WAF's 202 with an empty
        body), a body that does not decode, a page with neither an act nor the error notice;
      - Normattiva's generic error page when the known act cannot be read either (below);
      - a shared page read whose first caller was cancelled (the others get
        `LetturaAnnullata`, a transport error).
    - `errore_fonte` is any other HTTP error (a 400, a 410).
  - **The error page needs a check.** For an act it does not have, Normattiva answers
    HTTP 200 with «Normattiva - Errore» / «Errore nel caricamento delle informazioni». On
    29 Oct 2026 that page was byte-identical, but for the session id, to the one it serves
    for an update table asked without the session cookie. So the page alone does not say
    that the act is missing. On that page, `risolvi_atto` reads a known act, L. 7 agosto
    1990, n. 241, asked by its year like every act (`legge:1990-01-01;241`), so through the
    same resolver:
    - if that act reads correctly, the error is about the act asked: `atto_non_trovato`;
    - if it does not, Normattiva is the problem: `fonte_non_raggiungibile`.
    - The check's answer is kept in the process: a success five minutes, a failure one
      minute. Concurrent calls share one check. A miss therefore costs two requests at
      most, and one when a check answered recently; during an outage, one check a minute.
  - **`atto_non_trovato` is never transient.** Normattiva answered, and one of these
    says it has no such act:
    - a 404;
    - the page of another act, recognisable by its heading («LEGGE 7 agosto 1990, n. 241»)
      or its `eli:` metadata, or an ELI date of another year;
    - the error page («Normattiva - Errore» with «Errore nel caricamento delle
      informazioni»), with the check passed.

    It can be cached. The library keeps in memory only pages that carry a date.

    **Accepted residual risk:** in the five minutes after a successful check, an error
    page caused by a session or server problem on one act's page reads as
    `atto_non_trovato`, because the check is not repeated. A caller that caches misses
    for long may want to ask a miss again later.
  - **Cache parity:** an answer from the cache (disk or memory) has the same `esito`, `data`,
    `urn`, `url`, `precisione` and `errore` as the live answer; only `fonti` is `None`.
    The disk file is `act_dates.json` in the cache directory: it follows `MCP_CACHE_DIR`,
    `configurazione(cache_dir=…)`, and is neither read nor written under `LEGAL_CACHE=off` or
    `configurazione(cache=False)` (§2). Only dates read from a title go to disk; an ELI
    date (`INDICATIVO`) is kept in memory for the process only.

`EsitoAtto`:

| `esito` | Meaning |
|---|---|
| `trovato` | `data`, `urn`, `url` and `precisione` are the act's |
| `atto_non_trovato` | Normattiva has no act of that type, year and number: its error page with the check passed, a 404, the page of another recognisable act (`errore` names it), or an ELI date of another year. Not transient |
| `ambiguo` | only when `anno_o_data` is a full date, never with the year alone: a date whose day is not the act's. `data`, `urn` and `url` are those of the act Normattiva has with that type, year and number, and `errore` says so: either the day or the number is wrong |
| `fonte_non_raggiungibile` | transient: Normattiva down, slow, blocking or limiting us (5xx, 429, 403, network error, a source paused by the limits, an expired session, maintenance, any other answer without an act, the error page with the check failed). Retry, do not cache |
| `errore_fonte` | transient: Normattiva answered with another HTTP error (400, 410). Retry, do not cache |
| `riferimento_non_valido` | no type, a number that is not digits (or is 0), a year or date that cannot be read |
| `atto_non_riconosciuto` | no act type has that name (`errore` suggests the long name) |
| `non_supportata` | an EU act, a codice, the Costituzione: their date and URN are fixed, use `leggi_riferimento` |

`AttoRisolto` fields:

| Field | Value |
|---|---|
| `esito` | `EsitoAtto` |
| `tipo_atto` | the normalised type (`"decreto legislativo"`), `""` when the type could not be read |
| `numero_atto` | the number without leading zeros (`"385"`) |
| `data` | `"YYYY-MM-DD"` with `trovato` and `ambiguo`, else `None` |
| `urn` | `"urn:nir:stato:decreto.legislativo:1993-09-01;385"`, with `data` |
| `url` | the act's Normattiva N2Ls URL, with `data` |
| `precisione` | `"ESATTO"` or `"INDICATIVO"` (above), with `data` |
| `errore` | message for a person; `None` with `trovato` |
| `fonti` | `FontiConsultate`, `None` when nothing was reached |

```python
r = await api.risolvi_atto("d.lgs.", "385", "1993")
r.esito, r.data, r.urn, r.precisione
# ('trovato', '1993-09-01', 'urn:nir:stato:decreto.legislativo:1993-09-01;385', 'ESATTO')
```

### `modifiche_articolo(riferimento: str | NormaDati, *, dal=None, al=None, max_versioni=20) -> ModificheArticolo`

The versions of an Italian article and the amendments that produced them, read from
Normattiva. It is async.

- **Source.** Normattiva gives each version of an article its own page («Testo in vigore
  dal … al …») and its own update table («aggiornamenti all'articolo»). The table of
  version *k* lists the amendments that produced version *k*. Measured on 29 Oct 2026 on
  art. 2 c.c., artt. 2-ter and 13 d.lgs. 196/2003, art. 64-bis CCII and art. 1 d.P.R.
  131/1986.
  - So an amendment's `in_vigore_dal` is the start of the version it produced, read from
    that version's page, not deduced from the Gazzetta date. This is why it is `ESATTO`.
  - Both pages need the session cookie the article page sets: every call reads them with
    one client, after the article page.
  - Asked without the session, the update table answers Normattiva's error page.
    Therefore `url` is the article's page, never the update table's.
- **Input:**
  - an article of an Italian act (`"art. 13 d.lgs. 196/2003"`, a `NormaDati`); a code's
    article is read in the code (`regio.decreto:1942-03-16;262:2~art2`), never in its
    approving decree;
  - an act without an article is `non_supportata`, never its art. 1;
  - EU acts and articles of an annex named by the act are `non_supportata`;
  - a `NormaDati` with `versione`/`data_versione` is read as the article: the history is
    the same.
- **dal / al.**
  - Both are `"YYYY-MM-DD"` and both inclusive. They filter on `in_vigore_dal`, the
    entry into force.
  - They never filter on the Gazzetta date: the two differ by days and would flip the
    results. The abrogation of art. 13 d.lgs. 196/2003 was published on 4 Sept 2018 and
    is in force from 19 Sept 2018.
  - An amendment whose version window cannot be read has no `in_vigore_dal`. It is
    filtered on `data_gu`, it is `INDICATIVO`, and an avviso says so.
  - `versioni` always lists every version.
  - A bad date or `dal` after `al` is `riferimento_non_valido`.
- **The walk.** Newest version first, each window before its table:
  - the table of a version that starts after `al` is not read;
  - the walk stops at the first version that starts before `dal`, because the older
    versions start earlier still.
- **Ceiling.** At most `max_versioni` versions are read, the newest. Past the ceiling:
  - `completa=False`, `precisione="INDICATIVO"`, and `versioni_non_lette` counts the rest;
  - an avviso says how many versions were read and how to reach the others: raise
    `max_versioni`, or move `dal` later. Moving `al` earlier does not help, because the
    later versions still use up the ceiling;
  - the unread versions are listed with `valid_from`/`valid_to` at `None`.
  - `max_versioni < 1` raises `ValueError`.
- **Cost.**
  - For an article with V versions, all read: 2V requests (the article page, V-1 version
    pages, V tables, version 1's included); at most 2·`max_versioni`.
  - With the cache warm: 2 (the article page and the current version's table).
  - An article never amended: 1 (its page has no update link).
  - Plus one, the first time, for an act cited with the year only («art. 1 L. 742/1969»):
    its full date is read from its page (the lookup `risolvi_atto` uses, kept a year in
    `act_dates.json`).
  - The library's Normattiva limits apply (3 in flight, 0.5 s apart, §2).
- **Cache.**
  - Kept: a version whose window has ended, with its table, on disk for 90 days
    (`normattiva_aggiornamenti/` in the cache directory, through `_cache.py`). Never for
    ever, because Normattiva corrects its data at times. Version 1 is kept with its own
    introduction (below).
  - Not kept: the current version, a future version, a version that failed, a version
    whose table was not read or was empty.
  - The article page (current version, number of versions) is read every time, so a new
    version is seen at once.
  - `LEGAL_CACHE=off` or `configurazione(cache=False)`: nothing is read or written.
  - A cached answer equals the live one but for `fonti`.
- **Partial failure.**
  - A version whose page or table cannot be read stops the walk there. The cause can be
    a 429, a 5xx, a network error, an error or session page, or a page of another
    article.
  - The answer keeps what was read: `esito="trovato"`, `completa=False`,
    `precisione="INDICATIVO"`, and an avviso naming the unread versions and saying
    «riprovare». A gap is never filled.
  - Read `completa=False` with that avviso as transient, like `fonte_non_raggiungibile`:
    ask again. A version read whole before the failure is kept, a failed one never.
- **Article page.**
  - If the page cannot be read, the result is `verifica_non_disponibile` (transient),
    never `articolo_non_trovato` and never «no amendments». This covers an error or session
    page, a 429/5xx/403, a network error, a 2xx without an article, and a page that does
    not say which article it is.
  - If the page names another article (Normattiva answers a missing article with art. 1),
    the result is `articolo_non_trovato`.
- **Future versions.**
  - Without a date, Normattiva can serve as «the article» a version not yet in force. For
    example, art. 1 d.P.R. 131/1986 is abrogated from 1 Jan 2027 by d.lgs. 123/2025.
  - That version is listed with its future `valid_from`, its amendment with a future
    `in_vigore_dal`, and an avviso says it is not in force yet.
  - `valid_to` is as Normattiva states it, inclusive, even when it lies in the future.
- **Abrogation.** An abrogated article ends with a `Modifica` of `tipo="abrogazione"`. The
  version before it has its `valid_to`. The last version is Normattiva's abrogated
  stub, open-ended.
- **Version 1.**
  - Version 1's table is not «what produced version 1»: it is the article's whole
    history, the later versions' rows included. This was measured on all five amended
    articles above.
  - So only its row introducing this very article («ha disposto (con l'art. 2, comma 1,
    lettera f)) l'introduzione dell'art. 2-ter») is taken, as the `Modifica` of version
    1. Its `in_vigore_dal` is version 1's start, so d.lgs. 101/2018 is the act that
    introduced art. 2-ter d.lgs. 196/2003, from 2018-09-19.
  - The row must have been published by version 1's start: a later «introduzione» re-inserted
    an abrogated article, and is not what produced version 1. A row continuing another
    («convertito con modificazioni …» under its own entry) is never taken. An article
    introduced by a converted decree-law has the note in its own row and is taken (art.
    612-bis c.p., d.l. 11/2009).
  - More than one such row, or none, gives version 1 no amendment, with an avviso. The
    same holds for an article of the act's original text, which has no such row (art. 13
    d.lgs. 196/2003). A version 1 with such an avviso is never kept in the cache.
- **Identical rows.** Only a row that one table lists twice identically (same act,
  provision, action and parts) is kept once. Rows are never merged across tables: which
  version keeps a row would then depend on `dal`, which decides which tables are read.
  A decree-law and its conversion law are never merged either: Normattiva lists the
  decree-law as published in one version and as converted «con modificazioni» in the
  next, and those are two amendments.
- **What is never taken for complete:**
  - **An empty table** of a version after the first: an avviso and `INDICATIVO`, and it
    is not kept.
  - **The page of another version** served for version *k* (its own update link names
    another version): the walk stops there.
  - **«Never amended»** is said only of a page that has a window and the act's own update
    link but no article update link. A page without them is markup that changed:
    `completa=False`, `INDICATIVO` and an avviso.
  - **An article without a number** («XIII», «preambolo») is `non_supportata` before any
    request: no page could be checked against it, and an error page names no article
    either.
- **`tipo`.** It is Normattiva's verb, never guessed:
  - «la modifica» → `modifica`;
  - «l'introduzione» → `inserimento`;
  - «l'abrogazione» → `abrogazione`;
  - «la sostituzione» → `sostituzione`;
  - «la conversione» → `conversione`;
  - anything else → `altro`.

  A provision with two actions («l'introduzione del comma 1-bis … e la modifica … commi 2
  e 3») gives one `Modifica` per action, each with the provision's whole text.
- **`testo` and `descrizione`** are Normattiva's wording only, never editorial commentary.

Esiti: `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`, `articolo_non_trovato`,
`verifica_non_disponibile` (transient), `errore_fonte`, `non_supportata`.

`ModificheArticolo`:

| Field | Value |
|---|---|
| `esito` | `EsitoNorma` |
| `norma_data` | the article (`NormaDati`), with the act's full date |
| `versioni` | every version Normattiva lists, oldest first (`VersioneArticolo`) |
| `modifiche` | the amendments within `dal`/`al`, oldest version first (`Modifica`) |
| `url` | the article's Normattiva page (the update table needs a session: never given) |
| `completa` | `True` when every version within `dal`/`al` was read, its table included |
| `precisione` | `"ESATTO"` when complete, every amendment is, no table is empty and version 1 was not left without its act for want of certainty; else `"INDICATIVO"`; `None` without `trovato` |
| `avvisi` | version 1 without its act, versions not in force yet, the ceiling, unread versions, an empty table, a page without the update links, the `data_gu` fallback |
| `versioni_non_lette` | versions left unread by the ceiling or by a failure |
| `errore`, `fonti` | as everywhere |

`VersioneArticolo` (VisuaLex's `validity` keys): `version_number` (Normattiva's own
`art.versione`), `valid_from`, `valid_to` (ISO, inclusive; `None` when open or not read,
never `""`).

`Modifica`:

| Field | Value |
|---|---|
| `atto` | `AttoModificante` |
| `tipo` | `TipoModifica` (above) |
| `disposizione` | of the amending act: `"art. 9, comma 1, lettera a)"` |
| `parti` | of the article: `"commi 1, 1-bis, 2 e 3"`, `"comma 1-bis"`; `None` for the whole article |
| `in_vigore_dal` | the start of the version it produced (read); `None` when that window is unreadable |
| `versione` | that version (Normattiva's number) |
| `data_gu` | the row's «data pubblicazione», ISO: not the day it applies |
| `precisione` | `ESATTO` when the act was read whole and the window read; `INDICATIVO` otherwise, and with the `data_gu` fallback |
| `testo` | the provision as Normattiva words it: `"ha disposto (con l'art. 9, comma 5) la modifica dell'art. 2-ter, comma 1"` |

`AttoModificante`: `tipo_atto` (normalised, `""` when the row cannot be read), `data`,
`numero_atto`, `urn` (`"urn:nir:stato:decreto.legge:2021-10-08;139"`), `gazzetta`
(`"G.U. 08/10/2021, n.241"`, `"SO n.30, relativo alla G.U. 11/08/2026, n.185"`), `descrizione`
(the row's act as Normattiva writes it, with «convertito con modificazioni dalla …»).

```python
r = await api.modifiche_articolo("art. 2-ter d.lgs. 196/2003")
[(m.versione, m.in_vigore_dal, m.tipo, m.atto.numero_atto, m.parti) for m in r.modifiche]
# [(2, '2021-10-09', 'inserimento', '139', 'comma 1-bis'), (2, '2021-10-09', 'modifica', '139', 'commi 2 e 3'),
#  (3, '2021-12-08', 'modifica', '139', 'commi 1, 1-bis, 2 e 3'), (3, '2021-12-08', 'modifica', '139', 'comma 1'),
#  (3, '2021-12-08', 'conversione', '205', None)]
```

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
- **Update notes (`note_aggiornamento`, `note_non_lette`).** A Normattiva page
  carries, after the article, its «AGGIORNAMENTO (n)» notes, which the body calls
  «((n))» or «(n)». They say what the text alone does not: a Corte costituzionale
  declaration of illegitimacy (art. 3 d.lgs. 23/2015: C. cost. 194/2018 struck the
  words «di importo pari a due mensilità … per ogni anno di servizio», which stay in
  the text), a deferred effect, an exclusion.
  - **Where they are.** VisuaLex's extractor keeps them in `article_text` for a code's
    attachment and for its fallback shape, and drops them for the article in comma divs
    and for the plain text span. `article_text` stays VisuaLex's, byte for byte, so the
    notes are read from the same page into `note_aggiornamento`, for every shape, in
    page order (`NotaAggiornamento`: `numero` «10», `testo` the note's own words,
    `ordine` from 1, `corte_costituzionale` a word match on «Corte costituzionale»/«C.
    cost.» with «sentenza»).
  - **Values.** `()` means a page without notes. `None` means the text is not a
    Normattiva page's (EU, the `normattiva-akn` export, which carries its notes in its
    text) or the page's notes could not be read.
  - **When a note cannot be read.** This covers a block without its number or words, a
    «((n))» call without note n, more «AGGIORNAMENTO (n)» headings on the page than notes
    read (a note outside the markup this reader knows), a reader failure, and a kept
    reading of another shape. Then `note_non_lette` is `True` and `avvisi` says «note di
    aggiornamento non lette: verificare su Normattiva»; the article is never lost.
  - **What is not a call.** A plain «(n)» is a call only when note n exists. A «((n))» at
    the start of a line before its full stop is a comma renumbered by an amendment (art.
    117 TUB: «((6)). Sono nulle …»), and a four-digit «((2025))» is a year: neither is a call.
  - **Agreed shape.** The shape is agreed with VisuaLex, which will give the same field.
  - **In the MCP tools.** `cite_law` and `fetch_law_article` print them under the text,
    in a section «**Aggiornamenti**», «(n) testo», unless the text already carries them
    (a code's article). They always print them: a notes-on-request switch, if one comes,
    will never cover these notes. `cite_law(formato="json")` carries
    `note_aggiornamento`, `note_non_lette` and `note_nel_testo`.
- **Articles split into parts (`parti`, `testo_parziale`).** Normattiva serves a very long
  article in parts. Art. 1 L. 296/2006 is 14 parts, «1 (commi 1-100)» to «1 (commi
  1301-1364)», and the article's own page is the first.
  - **What you get.** `article_text` is that page's text, VisuaLex's, byte for byte. `parti`
    lists every part in order (`ParteArticolo`: `progressivo`, `commi_dal`, `commi_al`,
    `url`). `testo_parziale` is `True`, and `avvisi` says «testo parziale: commi 1-100 di
    1364 (l'articolo è diviso in 14 parti su Normattiva)».
  - **Values.** `parti` is `()` for an article not split and `None` when the text is not a
    Normattiva page's.
  - **Reading another part.** A reference string that names a comma («art. 1, comma 773,
    L. 296/2006») reads that comma's part in `testo_articolo` too. Otherwise use
    `parte_articolo(riferimento, progressivo)`, with `parte_del_comma(parti, "773")` to
    find the part of a comma. The library's notice says so: «… ; per un comma, indicarlo
    nel riferimento (…) oppure leggerne la parte con parte_del_comma(parti, comma) e
    parte_articolo(riferimento, progressivo)».
  - **A part read that lacks the comma's own line** («773. …», for example a «-bis» on a
    part's edge) gets a notice too.
  - **`verifica_citazioni`.** When the comma's part could not be read, it answers «non
    verificata», never «metadati discordanti» on another part's text.
  - **Notes.** `note_aggiornamento` is the part's own: the notes of the other parts are
    covered by the notice.
  - **In the MCP tools.** `cite_law` reads the part that holds the comma its reference names
    («art. 1, comma 773, L. 296/2006», also «co. 773», «c. 773», «773° comma», «comma
    773-bis»). That is one request more, and none when it is the page's own part. It says
    «**Commi 701-800** (parte 8 di 14 …)» before the text.
  - **Without a comma.** `cite_law` serves the first part with the notice and the list of the
    parts after the text. It never serves the whole article: 1.3 million characters in one
    answer for art. 1 L. 296/2006.
  - **A comma in no part, or a part that cannot be read.** Said in an «Attenzione» line;
    never another part's text in silence.
  - **JSON.** It carries `parti`, `parte` and `testo_parziale`.
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
  Since 4aa59a9d VisuaLex gives their part to the codes approved as an annex of
  their decree too: codice del turismo, norme di attuazione del c.p.p.,
  regolamento della navigazione marittima, codici penali militari (`"1"`; the
  codice penale militare di guerra, which VisuaLex has only inside the joint row,
  `"2"`), and to the acts cited by their own number whose articles are their
  annex 1 (VisuaLex's `ANNEXED_ACTS`, at f47ac1b6): TULPS (r.d. 773/1931), legge
  fallimentare (r.d. 267/1942), c.p.p. minorile (d.P.R. 448/1988) and TU successioni
  (d.lgs. 346/1990), all `"1"`, with the part in the URN (`;267:1~art1`): without it,
  Normattiva's art. 1 of these acts is the approving decree's.
- **Sigle of the convention** (VisuaLex's G-360, G-366, G-369, at f47ac1b6). The codes
  cited by sigla read as the code: `c.p.a.`, `cod. nav.`, `cod. post.`, `c.g.c.`. An
  annex of a code's decree with a sigla of its own reads as that code and annex, as
  VisuaLex keys it: «art. 1 disp. att. c.p.a.» is `codice del processo amministrativo`
  with `allegato="3"` (`;104:3~art1`), never the c.p.a.; likewise `disp. trans. c.p.a.`
  (`"4"`), `disp. coord. c.p.a.` (`"5"`), `disp. att. c.g.c.` (`"2"`), `disp. trans.
  c.g.c.` (`"3"`), `reg. nav. mar.`, `c.p.m.p.`, `c.p.m.g.`, `disp. att. c.p.p.`. Every
  sigla of more than one word is read however dotted or spaced («disp att cpa»,
  «disp.att.c.c.», «cod nav»), and only as the whole act name. «1° settembre 1993» is the
  first of the month. Every label of VisuaLex's source convention with a Normattiva
  identity reads back to it (`tests/unit/test_sigle_convenzione.py`), except a code
  cited by its decree (its annex is found at the lookup), an annex named «A», and an act
  with no number.
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
  the article, else `amended`; `inserted` for an article inserted from a later
  day, below), `valid_from`, `version_number`, and `versions_between: n` when the
  version numbers show `n` other versions not in force yet before it (absent
  otherwise: Normattiva's undated page is the latest version, and the ones in
  between cannot be read on their own); `None` when the undated page was today's
  text. VisuaLex follows the same rule since 4aa59a9d (its decision G-355), and
  `versions_between` since 02ebc80a.
- **`cite_law(..., formato="json")`** carries the same two facts under the same
  names, and the keys are always present so the schema does not change with the
  answer: `avvisi` (a list, `[]` when there is nothing to say), `upcoming` (the
  object above, or `null`) and `not_in_force` (`true` when the text is a later one:
  with `versione="futura"`, and for an article inserted from a later day asked
  without a date). The Markdown form prints the notice as a line
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

### `parte_articolo(riferimento: str | NormaDati, progressivo: int, *, canale: Canale) -> TestoArticolo`

One part of an article Normattiva splits into parts: `progressivo` is a
`ParteArticolo.progressivo` from `testo_articolo(...).parti`.

- **What you get.** `article_text` is the part's page, read by VisuaLex's extractor, with
  the part's own notes. `parti` is the whole list, `testo_parziale` is `True`, and `avvisi`
  names the part's commi.
- **Cost.**
  - Two requests: the article's page, then the part's, which needs that page's session.
  - One when the session kept from the page is less than 10 minutes old, or when the part
    is the page's own.
  - None when the part is in the cache: a part read is kept a day, under the article URL,
    the tree's `art.versione` and the part's commi.
  - Two more when the kept session has died: Normattiva then answers with another page.
    The session is dropped, the page is read again and the part asked with the fresh
    page's path. A session is kept only after it served the part.
- **The index holds for the current tree only.** An amendment can split the article again,
  so never keep a `progressivo` as a key: read `parti` again. For the same reason
  `commi_dal`/`commi_al` are strings («1-bis»).
- **`url`.** A part's `url` (`/atto/caricaArticolo?…`) needs the article page's session:
  it does not open on its own.
- **Channel.** Only `canale="html"`: the Akoma Ntoso export has the article whole, so
  `canale="akn"` is `non_supportata`.
- **Esiti:** those of `testo_articolo`, plus:
  - `riferimento_non_valido` for an article not split or a `progressivo` its tree does not
    have (`parti` is then filled, when there are parts);
  - `verifica_non_disponibile` for a part that could not be read (source down, or a page
    that is not that part).

### `parte_del_comma(parti: Iterable[ParteArticolo], comma: str) -> ParteArticolo | None`

The part whose commi hold `comma` («773», «773-bis», «100 bis»), or `None`. No network. A
comma with a suffix sits after its number, so the part ending at «100» holds «100-bis».

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
- **An EU regulation or directive** (since the 3.0 migration): `title` and
  `rubriche` from the EUR-Lex page of its text in force, the page its articles are
  read from (one request, kept a day), with VisuaLex's EU tree reader
  (`lib/visualex/eurlex_tree.py`, imported). The text in force is chosen as for
  `testo_articolo`: the latest consolidation that amends the act, else the Official
  Journal text. `consolidato` and `consolidato_verificato` say which, as in
  `TestoArticolo`. A key keeps its ordinal («Articolo 15 bis» is `"15-bis"`), and a
  heading an amending act quotes (in a table cell, or opening with «) is not one of
  its articles. No `abrogati`, `parts` or `voci`. A treaty: from its page too. A page
  with articles but no rubriche (the legacy class-less Official Journal page, dir.
  2002/58) is `testo_assente`, with an `errore` saying so: its articles are in
  `albero_atto`. A version asked for (a date, the original, `versione="futura"`) is
  `non_supportata`, as for an Italian act. `considerando` of a `NormaDati` with
  `celex_consolidated` is `non_supportata`, before any request.
- **Esiti:** `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`,
  `non_supportata` (a NormaDati with a version), `verifica_non_disponibile`,
  `errore_fonte`, `testo_assente`.

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
- **An EU regulation, directive or treaty**: VisuaLex's EU tree on the page of the
  text in force (as for `indice_atto`). `articles` are `{"numero"}` (plus `url`,
  the article's ELI address on an Official Journal page, with `link=True`), the
  chapter headings as strings with `dettagli=True`, and
  `metadata = {"rubriche", "title"}`. `consolidato` and `consolidato_verificato`
  say which text the tree is read from.
- **Esiti:** `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`,
  `non_supportata` (a NormaDati with a version), `verifica_non_disponibile`,
  `errore_fonte`, `testo_assente`.

### `considerando(atto: str | NormaDati) -> ConsiderandiAtto`

Every recital of an EU regulation or directive: VisuaLex's `/fetch_recitals`.
`considerando` is `({"number": "1", "text": "…"}, …)`, read by VisuaLex's reader
(`extract_recitals`) from the Official Journal page, since a consolidated text
has no preamble. The text has no «(N)»; a modern page's footnote calls are dropped, a
legacy page keeps them in the text («dati(4)», recital 1 of dir. 2002/58). Modern pages read
the `rct_N` blocks, legacy pages the «(N) …» sequence after «considerando quanto
segue». One request, kept a day with the act's page. A single recital is
`testo_articolo("considerando 42 GDPR")`, with the same text; `cite_law` prints
«(42)» before it as the label.

- **Esiti:** `trovato`, `testo_assente` (no recital on the page),
  `riferimento_non_valido`, `atto_non_riconosciuto`, `non_supportata` (an Italian
  act, a treaty), `verifica_non_disponibile`, `errore_fonte`.

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
- **`TIPI_ATTO_VERIFICATI`**: the act types whose date and number `risolvi_atto`
  reads from the Normattiva page's title (`ESATTO`), as `normalize_act_type` names
  them: `legge`, `decreto legislativo`, `decreto legge`, `decreto del presidente
  della repubblica`, `regio decreto`, `regio decreto legge`, `legge costituzionale`.
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
| `EsitoAtto` | the outcomes of `risolvi_atto` (§3) |
| `TipoModifica` | `"modifica"` \| `"inserimento"` \| `"abrogazione"` \| `"sostituzione"` \| `"conversione"` \| `"altro"` (§3, `modifiche_articolo`) |
| `Canale` | `"akn"` \| `"html"` |

### Norm types

| Type | Fields |
|---|---|
| `NormaDati` | `tipo_atto, data, numero_atto, url, allegato, numero_articolo, versione, data_versione, urn`, plus `descrizione, data_risolta`, and VisuaLex's `celex_consolidated` last |
| `EsitoRiferimento` | `esito, norma_data: tuple[NormaDati, ...], errore` |
| `AttoRisolto` | `esito, tipo_atto, numero_atto, data, urn, url, precisione, errore, fonti` |
| `ModificheArticolo` | `esito, norma_data, versioni, modifiche, url, completa, precisione, avvisi, versioni_non_lette, errore, fonti` |
| `VersioneArticolo` | VisuaLex `validity` keys: `version_number, valid_from, valid_to` |
| `Modifica` | `atto, tipo, disposizione, parti, in_vigore_dal, versione, data_gu, precisione, testo` |
| `AttoModificante` | `tipo_atto, data, numero_atto, urn, gazzetta, descrizione` |
| `TestoArticolo` | `esito, article_text, norma_data, url, validity`, plus `urn, fonte, canale, data_consultazione, errore, fonti, precisione, avvisi, successione, upcoming, not_in_force, consolidato, consolidato_verificato, note_aggiornamento, note_non_lette, parti, testo_parziale` |
| `NotaAggiornamento` | `numero, testo, ordine, corte_costituzionale`: one «AGGIORNAMENTO (n)» note of the page (§3, `testo_articolo`) |
| `ParteArticolo` | `progressivo, commi_dal, commi_al, url`: one part of an article Normattiva splits (§3, `parte_articolo`) |
| `Vigenza` | VisuaLex `validity`: `state, valid_from, valid_to, version_number, act_updated, request_in_window` |
| `IndiceAtto` | `esito, title, rubriche, abrogati, parts, count`, plus `voci, codice_redazionale, data_gu, url, errore, fonti, consolidato, consolidato_verificato` |
| `AlberoAtto` | VisuaLex `/fetch_tree`: `esito, articles, count, metadata`, plus `url, errore, fonti, consolidato, consolidato_verificato` |
| `ConsiderandiAtto` | VisuaLex `/fetch_recitals`: `esito, considerando` (`{number, text}`), plus `url, errore, fonti` |
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
| Full dates of year-only URNs, in batch (one act per call: `risolvi_atto`, §3) | `/resolve_act_dates` |
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
read from the same page, and the text in force today when the undated page serves
a later version, and the later text of an article inserted from a later day,
marked `not_in_force`, as VisuaLex since 4aa59a9d (see `testo_articolo`). Multi-article references come with the next phases. `/fetch_decision` switches
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
  3.0 package. Since f47ac1b6 VisuaLex has the URNs this library gives the codes
  approved as an annex of their decree (codice del turismo `;79:1`, codici penali
  militari `;303:1`, norme di attuazione del c.p.p. `;271:1`, regolamento per la
  navigazione marittima `;328:1`) and the acts whose text is their annex 1 (TULPS
  `;773:1`, legge fallimentare `;267:1`, c.p.p. minorile `;448:1`, TU successioni
  `;346:1`), and files them with that `allegato`: `norma_data` here gives the same. The
  codice penale militare di guerra (`;303:2`), absent from VisuaLex's table, is filed
  with `"2"`. VisuaLex's saved norms of the last three, filed before f47ac1b6 without
  the part, need realigning on its side before the shell switches.
- **Serialisation stays the shell's job.** Key order, ASCII escaping, the NDJSON
  stream: `come_dict` returns data, not JSON text.
