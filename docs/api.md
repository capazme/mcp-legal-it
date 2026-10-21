# `mcp_legal_it.api` — the library API

`mcp_legal_it.api` is mcp-legal-it used as a Python library: Italian and EU norms
and case law as plain `async` functions that return typed data.

**It is the package's only stable surface.** Everything else is internal:
`mcp_legal_it.core`, `mcp_legal_it.lib`, `mcp_legal_it.tools`, the MCP server
and the `_impl` functions. Any of them can change in any release, a patch
release included.

```python
import asyncio
from mcp_legal_it import api

async def main():
    t = await api.testo_articolo("art. 2043 c.c.", canale="akn")
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
- **the limits, per source** (politeness), shared by every client of the
  process: at most 3 requests in flight and 0.5 s between two; a `Retry-After`
  stated by a 429 or 503 pauses the source for every caller, and a pause over
  30 s refuses the request at once (`FontePausata`); with
  `LEGAL_CIRCUIT_BREAKER=on` (off by default) 3 consecutive failures (network
  error, 5xx, 429; never a 404) suspend the source for 5 minutes
  (`FonteSospesa`). Retries are `retry_request`'s, at most two.

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

### `riferimento_da_parametri(tipo_atto, numero_articolo="", data="", numero_atto="", allegato=None, versione="vigente", data_versione=None) -> EsitoRiferimento`

The same, from explicit fields (the VisuaLex request body). No network.

- **Esiti:**
  - `trovato`;
  - `atto_non_riconosciuto`: an act type the resolver does not know. Long and
    short names are both accepted (`"decreto legislativo"`, `"d.lgs."`), and so
    are the codes by name (`"codice civile"`, `"costituzione"`);
  - `riferimento_non_valido`: no type; an EU regulation or directive without year
    (`data`) and `numero_atto`; or an Italian act without the date and number
    needed to build its address;
  - `non_supportata`: a `versione` other than `vigente`, or any `data_versione`
    (vigenza phase).

### `testo_articolo(riferimento: str | NormaDati, *, canale: Canale) -> TestoArticolo`

The text in force of one article, from Normattiva or EUR-Lex.

- **`canale` is required**, so that no default text channel reaches a caller by
  accident:
  - `"akn"` is mcp-legal-it's pipeline. It reads Normattiva's Akoma Ntoso
    export first and falls back to mcp-legal-it's own HTML reader. EUR-Lex is
    always HTML. `fonte` says which reader served the text: `normattiva-akn`,
    `normattiva` or `eurlex`.
  - `"html"` is VisuaLex's frozen HTML reader. It is **planned**; until then it
    answers `non_supportata` and makes no request.
- **`allegato` of the codes.** A code carries the annex its URN points at even
  when the citation does not name it: c.c. `"2"`, c.p. and c.p.c. `"1"` (the
  same annex is in the URN, `;262:2`). Passing that default annex back
  (`riferimento_da_parametri(..., allegato="2")`, or a `NormaDati`) reads the
  article, not an annex.
- **`url` and `urn`** are both always filled for Normattiva acts (EU acts have
  no NIR URN). An act cited with the year only whose full date could not be
  read keeps the URN derived from its URL. That URN has a placeholder date,
  `YYYY-01-01`, and `norma_data.data_risolta` is `False`.
- **`validity`** is `None` until the vigenza phase. When it arrives it will come
  from the same fetch as the text: no second request.
- **Esiti:** the whole `EsitoNorma` vocabulary.

```python
t = await api.testo_articolo("art. 99999 c.c.", canale="akn")
t.esito    # 'articolo_non_trovato'
```

### `testi_articoli(riferimenti, *, canale: Canale, concorrenza: int = 4) -> list[TestoArticolo]`

`testo_articolo` for many articles, in input order, at most `concorrenza` at a
time. Articles of the same act share one download of the act.

### `indice_atto(atto: str | NormaDati) -> IndiceAtto`

The article headings of an Italian act (Normattiva `vediRubriche`).

- `rubriche` maps each article key (`"1"`, `"2-bis"`) to its heading, wherever
  an index line reads as one. `count` is `len(rubriche)`.
- `voci` keeps every line as Normattiva lists it.
- `title`, `abrogati` and `parts` are **planned** and empty today.
- **Esiti:** `trovato`, `riferimento_non_valido`, `atto_non_riconosciuto`,
  `non_supportata` (EU acts), `verifica_non_disponibile`, `errore_fonte`,
  `testo_assente`.

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
  `bis` (2nd) to `sexiesdecies` (16th), each with the other spellings Normattiva
  uses (`novies`/`nonies`, `quinquiesdecies`/`quindecies` …).
- **`ARTICLE_SUFFIX_ALTERNATION`**: a regex alternation of all those spellings,
  longest first. Use it inside a group:
  `rf"(\d+)-?({ARTICLE_SUFFIX_ALTERNATION})"`.

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
| `NormaDati` | `tipo_atto, data, numero_atto, url, allegato, numero_articolo, versione, data_versione, urn`, plus `descrizione, data_risolta` |
| `EsitoRiferimento` | `esito, norma_data: tuple[NormaDati, ...], errore` |
| `TestoArticolo` | `esito, article_text, norma_data, url, validity`, plus `urn, fonte, canale, data_consultazione, errore, fonti` |
| `Vigenza` | VisuaLex `validity`: `state, valid_from, valid_to, version_number, act_updated, request_in_window` |
| `IndiceAtto` | `esito, title, rubriche, abrogati, parts, count`, plus `voci, codice_redazionale, data_gu, url, errore, fonti` |
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
| HTML text channel (`canale="html"`), byte-identical to VisuaLex's frozen `article_text` | `/fetch_article_text`, `/stream_article_text`, `/fetch_all_data` |
| `validity` with the text, from the same fetch | same |
| Multi-article references (`"1,2"`, `"3-5"`) | `/fetch_norma_data` |
| Act tree with annexes and metadata | `/fetch_tree` |
| `title`, `abrogati`, `parts` of the index | `/fetch_rubriche` |
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
`/stream_article_text`, `/fetch_all_data`) and `/fetch_decision` switch to this
library **only once** the HTML channel and the block form of §6 exist.

- Today's `canale="akn"` text is not VisuaLex's frozen `article_text`: AKN and
  HTML readings differ.
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
  that VisuaLex consumes must keep that golden green.
- **`identita` does not drift.** Its fields are shared by page addresses,
  dossiers and remote clients. Adding a field is allowed; renaming or reshaping
  one is not.
- **Serialisation stays the shell's job.** Key order, ASCII escaping, the NDJSON
  stream: `come_dict` returns data, not JSON text.
