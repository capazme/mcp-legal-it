# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The 3.0 line now carries everything shipped on the 2.x line from 2.13.0 to
2.17.0 (the 2.x sections below): the benchmark corrections of 2.15.x, paged
reading of long texts (`da_carattere`), the `cite_law` guard against an
article the act does not have, the `Regime: PREVIGENTE` flag, the
directory-ready plugin and TEGM Q4 2026. Where an entry below repeats a 2.x
entry, it is the same feature as ported to the 3.0 line.

### Added
- **`api.modifiche_articolo(riferimento, *, dal=None, al=None, max_versioni=20)`:
  an article's versions and the amendments that produced them.** It returns a
  `ModificheArticolo` with:
  - `versioni` (`VersioneArticolo`: `version_number`, `valid_from`, `valid_to`,
    VisuaLex's keys);
  - `modifiche` (`Modifica`: the amending act as an `AttoModificante`, `tipo`,
    `disposizione`, `parti`, `in_vigore_dal`, `versione`, `data_gu`, `precisione`,
    `testo`);
  - `completa`, `precisione`, `avvisi` and `versioni_non_lette`.
  - **Source.** Normattiva gives each version of an article its own page and its own
    update table, and the table of version *k* lists the amendments that produced it.
    So `in_vigore_dal` is read from that version's window, not deduced from the
    Gazzetta date, and is `ESATTO`.
  - **Filters.** `dal`/`al` are inclusive and filter on `in_vigore_dal`, never on
    `data_gu`. Where the window cannot be read, the `data_gu` fallback is `INDICATIVO`,
    with an avviso.
  - **Walk.** Newest version first, at most `max_versioni` versions, at most
    2·`max_versioni` requests (2V for V versions).
  - **Never filling a gap.** A version that cannot be read (429, 5xx, an error or session
    page) stops the walk: `completa=False` and an avviso naming the versions to ask again.
    An unreadable article page is `verifica_non_disponibile`, never «not found» and never
    «no amendments».
  - **What it shows.**
    - A decree-law and its conversion law stay two amendments; only identical rows
      within one table are merged.
    - A version Normattiva already serves but that is not in force yet (art. 1 d.P.R.
      131/1986, abrogated from 2027) has its future `in_vigore_dal` and an avviso.
    - A code's article is read in the code.
    - An act without an article, or an article without a number, is `non_supportata`.
    - Version 1's table is the article's whole history: only its row introducing the
      article is taken, so the act that introduced it is version 1's `Modifica`
      (d.lgs. 101/2018 for art. 2-ter d.lgs. 196/2003).
    - An empty table, the page of another version, a page without the update links
      are never taken for complete.
  - **Cache.** Past versions are kept 90 days through `_cache.py`
    (`normattiva_aggiornamenti/`, declared in the cache inventory). The article page
    and the current version are read every time.
  - Documented in `docs/api.md` §3.
- **`api.risolvi_atto(tipo_atto, numero_atto, anno_o_data)`: an act's full date
  and NIR URN.** One call per act, from the act's own Normattiva page (never its
  art. 1). It returns an `AttoRisolto`: `data` («1993-09-01»), `urn`, `url`,
  `precisione` and `esito`, in the new closed vocabulary `EsitoAtto`.
  - **Precisione.** The date is `ESATTO` when the page's title names this act's
    type, year and number, for the seven types the new constant
    `api.TIPI_ATTO_VERIFICATI` declares (legge, d.lgs., d.l., d.P.R., r.d., r.d.l.,
    l. cost.). It is `INDICATIVO` when it comes from the page's ELI date (DPCM,
    decreto ministeriale).
  - **Esiti.**
    - A full date whose day is not the act's is `ambiguo`, with the act Normattiva
      has under that type, year and number. It never comes from a year alone.
    - Another act's page is `atto_non_trovato`.
    - EU acts and codici are `non_supportata`.
  - **Error page.** Normattiva serves one error page for an act it does not
    have and for a page asked without a session (byte-identical on 29 Oct). So
    that page is `atto_non_trovato` only when a known act (L. 241/1990, asked by
    its year as every act is) reads right after it; otherwise it is
    `fonte_non_raggiungibile`. The residual risk is documented: within five minutes
    of a successful check, a session error on one act's page reads as missing.
  - **Transient failures.** These are `fonte_non_raggiungibile`, never `trovato`
    without a date, and neither they nor their page are kept (only a page with a
    date is kept):
    - a 429, 403 or 5xx;
    - a network error;
    - an expired session or a maintenance page;
    - any other answer without an act, such as a WAF's empty 202;
    - a shared read whose first caller was cancelled.

    Any other HTTP error is `errore_fonte`, which is transient too.
  - **Cache parity.** A cached answer equals the live one but for `fonti=None`.
    The date file follows `MCP_CACHE_DIR` and `LEGAL_CACHE=off`.
  - **Cost.** One request per act, plus one for the check on the error page.
    The check is shared by concurrent calls, and its answer is kept five minutes
    (success) or one minute (failure). None from the disk cache of act dates
    (`act_dates.json`). Concurrent calls for one act share one request. The
    library's Normattiva limits apply: 3 in flight, 0.5 s apart, documented in
    `docs/api.md`.
  - Documented in `docs/api.md` §3. The batch form stays planned (§6).
- **The sigle of VisuaLex's source convention** (G-360, G-366, G-369): «cod.
  post.» and «c.g.c.» name their codes, and an annex of a code's decree with a
  sigla of its own reads as that code and annex, as VisuaLex keys it: «art. 1
  disp. att. c.p.a.» is the c.p.a.'s decree at annex 3 (`;104:3~art1`, `allegato`
  `"3"`), never the c.p.a. Also `disp. trans.` and `disp. coord. c.p.a.`, `disp.
  att.` and `disp. trans. c.g.c.`, `reg. nav. mar.`; a sigla of more than one word
  is read however dotted or spaced («disp att cpa», «cod nav», «disp.att.c.c.»).
  «1° settembre 1993» is read as the first of the month. Every label of the
  convention with a Normattiva identity reads back to it, three known exceptions
  aside (`tests/unit/test_sigle_convenzione.py`, adapted from VisuaLex's tests).
- **`verifica_citazioni` says a coming repeal or amendment.** An article in force
  today with a later version already published stays «verificata», and the note
  adds «abrogato con effetto dal …» or «modificato con effetto dal …» (art. 3
  d.P.R. 131/1986, repealed from 1 January 2027).
- **An EU act's index, tree and recitals** (`api`). `indice_atto` and
  `albero_atto` now answer for EU regulations, directives and treaties: VisuaLex's
  EU tree reader (`lib/visualex/eurlex_tree.py`) on the page of the text in force,
  the same page the articles are read from (one request, kept a day), with
  `consolidato` saying which text it is. A key keeps its ordinal («Articolo 15 bis»
  is `15-bis`), and a heading an amending act quotes is not one of its articles.
  The new `api.considerando(atto)` gives every recital, VisuaLex's
  `/fetch_recitals`: `{number, text}` from the Official Journal page (a consolidation,
  which has no preamble, is refused before any request). A page with articles but no
  rubriche (dir. 2002/58's legacy page) is `testo_assente` with an `errore`, never an
  empty «trovato».
- **ANAC acts** (#51): `cerca_atti_anac`, `leggi_atto_anac` and
  `ultimi_atti_anac` search the acts of the Autorità Nazionale Anticorruzione
  (delibere, pareri di precontenzioso and sulla normativa, linee guida, bandi
  tipo, comunicati del Presidente, regolamenti…) on www.anticorruzione.it's
  public «Consulta i documenti» search, newest first, by type and year (the
  portal's own «Anno» filter). An act is read by the reference the search
  returns or by type, number and year (the number searched within the type
  and the year: one result for delibera 444/2025): its
  particulars (year, topic, category, type, recipients), subject, «Riferimenti
  normativi», «Parole chiave» and the link to the official PDF. The full text is
  published only in that PDF and is not extracted. A page the client cannot
  read is an error, never «no results». New host `www.anticorruzione.it`
  (robots.txt allows every agent); the open-data portal refuses automated
  requests and is not used. New authority tag `anac`, in the `normativa`
  profile.
- **Corte dei conti: deliberazioni of the control sections** (#51, LI-054):
  `cerca_deliberazioni_corte_conti` (by words, number, year and section),
  `leggi_deliberazione_corte_conti` (by the id the search returns, such as
  `SRCCAM/29/2025/PREV`, or by number, year and section: a number several
  sections used is listed, never picked) and `ultime_deliberazioni_corte_conti`
  read the Court's banca dati. The answer gives the section, number, dates,
  outcome, president, rapporteur, recipients, subject, the full text as the
  banca dati holds it (25,000 characters per answer, `da_carattere` for the
  rest) and the public link to the official PDF. The search service runs on the
  Court's vendor's host and asks for the HTTP Basic pair the site's public
  configuration hands every visitor: the client reads that configuration at
  runtime, keeps the pair in memory only, re-reads it once when refused, and
  never writes it to code, logs, disk caches, error messages or the replay tapes
  (`scripts/replay_mcp_outputs.py` scrubs the recorded configuration; a test
  records a tape and checks it). One request at a time, 1 s apart, and at most
  5 documents per search, the public service's own limit (it answers an empty
  204 from 6). The sentenze of the jurisdictional sections are not covered: the
  public service counts them but returns none. New hosts
  `banchedati.corteconti.it` and `corteconti-iit.almawave.cloud`, new court tag
  `giurisprudenza_conti`; 234 tools.
- **EU consolidated versions** (`api`): `riferimento_da_parametri(...,
  celex_consolidated="02002L0058-20091219")` and `NormaDati.celex_consolidated`
  (VisuaLex's key, last in the dataclass) ask for the text of an EU regulation or
  directive as amended, instead of the Official Journal text. The CELEX must have
  the shape and be the act's own; the text is VisuaLex's reader on CELLAR's copy of
  the consolidated page: no «▼M2» markers, one line per lettered point, «14 bis»
  found in either spelling. A recital or an annex of a consolidation is
  `non_supportata` (a consolidated text has no preamble: its «(N)» are footnotes).
- **The text not in force yet** (`api`, `cite_law`; VisuaLex's `upcoming: true`).
  `versione="futura"` asks for the text Normattiva has published and not in force
  yet: the undated page, with `not_in_force=True` (a new `TestoArticolo` field, and a
  `cite_law` JSON key always present), `precisione` `INDICATIVO`, a first `avviso`
  with the day it comes into force, `upcoming` describing it (`inserted`,
  `amended` or `abrogated`; `None` when today's page cannot be read), and
  `norma_data` dated to that day, so it never reads as the text in force. An
  optional `data_versione` after today is the latest day it may start. None
  published, or none by that day, is `articolo_non_trovato`; an unreadable
  validity is `verifica_non_disponibile`. Normattiva acts only; an annex is
  `non_supportata`.
- **An article inserted from a later day** (nothing of it in force today) is
  served as VisuaLex serves it: its later text, `not_in_force`, `INDICATIVO`,
  `upcoming` `{change: "inserted", …}` and a first `avviso` that it is not in
  force yet, instead of «testo non leggibile» after a needless export request.
  `verifica_citazioni` gives it the verdict «non in vigore», with the day it comes
  into force, never «verificata».
- **The text of an article at a date, and the original text** (`api`).
  `riferimento_da_parametri(..., data_versione="2010-01-01")` (or «1 gennaio
  2010») and a `NormaDati` with `data_versione` ask for the text in force on that
  day: the page at that date (`!vig=`) and the export at that day.
  `versione="originale"` asks for the original text, from the page only
  (`@originale`), never the export. An article that did not exist yet on that day
  is `articolo_non_trovato`; a version of a year-only act whose full date could
  not be read is `verifica_non_disponibile`, never today's text. A date always
  means the text in force on that date, with or without `versione="vigente"`, as
  VisuaLex does since `4aa59a9d` (before, it served today's text under the date
  asked for when the date came without `"vigente"`). A future date, a date with `"originale"` or another
  `versione` is `riferimento_non_valido`; a version of an EU act or of an annex,
  and the whole act, its index or its tree at a date, are `non_supportata`. A
  page whose window misses the date is `INDICATIVO`, with an `avviso`
  (`validity.request_in_window`).
- **Normattiva's two channels checked against each other** (`api.testo_articolo`,
  `cite_law`), with no request: when the page kept a day and the export in its
  cache disagree on the repeal, an `avviso` says which says what; the export's
  text says the day it was consolidated (`consolidato`, from its ELI alias), and
  an `avviso` says when the act's page was updated at another day.
- **`LEGAL_CITATION_GATE=off` switches off the plugin's citation gate** (also
  `0`, `false`, `no`, any case). Only the Stop/SubagentStop hook stops; the
  plugin's tools stay. Meant for software-development sessions, for example
  `"env": {"LEGAL_CITATION_GATE": "off"}` in a project's
  `.claude/settings.local.json`; legal work should keep it on.
- **Network rules per source, from VisuaLex** (`core/_http`). Every request
  the readers send, redirects included, is checked before it leaves: scheme,
  no credentials, and a host the source may reach; until now the host list was
  only checked statically, in the tests. Per source and per process: at most 3
  requests in flight, 0.5 s between two, shared by every thread and event loop,
  and a `Retry-After` stated by a 429 or 503 pauses that source for every
  caller, for at most 30 s (a longer statement refuses that call at once with
  `FontePausata` and never holds the source longer). The limits hold within one
  process: N processes on one machine make N times the cap. `retry_request`
  now retries a 429 too, waiting what the source asked, with jitter. Optional circuit breaker,
  `LEGAL_CIRCUIT_BREAKER=on` (off by default): 3 consecutive failures suspend
  the source for 5 minutes; a 404 never counts. A library caller with its own
  `client_factory` keeps the host guard and can put the limits under its own
  cache with `con_regole`. Measured on VisuaLex's 19 timing requests: the same
  requests as before, row by row (`scripts/measure_requests.py`).
- **Article suffixes and act types from VisuaLex.** One suffix table,
  VisuaLex's, imported byte for byte and pinned to it (it runs from `bis` to
  `vicies` and its spelling variants): the private copies that stopped at
  `decies` read "art. 25-terdecies d.lgs. 231/2001" as art. 25-ter in the
  Cassazione searches (`giurisprudenza_su_norma` looked for the wrong article)
  and built a URN with a space for "25 terdecies". `api.SUFFISSI_ARTICOLO`
  now runs to the 20th and `api.ARTICLE_SUFFIX_ALTERNATION` is VisuaLex's
  (`tredecies`, which no source was found to print, is no longer listed).
  `normalize_act_type` reads case and spacing as VisuaLex does, and the act
  tables gain VisuaLex's rows: "d.l.", "l. cost.", "r.d.l.", "d.lgs.lgt."
  given as the act type (`fetch_law_article`, `api.riferimento_da_parametri`)
  built `urn:nir:stato:d.l.:…` and `l..cost.`; "c.p.a."; the implementing
  regulations of the c.p.p. and of the industrial property code. Written
  inside a citation (`cite_law("art. 1 l. cost. 1/2012")`) these short forms
  are still refused as an unknown act, never read as another: the citation
  parser takes them with the citation-gate work. VisuaLex's source
  convention (`golden.json`) is a pinned fixture: the norm identities
  mcp-legal-it builds already must match it, the others are listed with the
  step that closes them.
- **Normattiva articles are read from their page, with VisuaLex's extractor.**
  `cite_law`, `fetch_law_article` and `verifica_citazioni` now read the
  article's Normattiva page (the HTML channel, `api.testo_articolo(...,
  canale="html")`) instead of the Akoma Ntoso export first. The text is
  VisuaLex's `article_text`, byte for byte (`lib/visualex/normattiva_html.py`,
  imported unchanged; 11 of 11 texts identical to a live VisuaLex run, its
  frozen hashes pass): real accents ("è", "attività", not "e'", "attivita'"),
  Normattiva's «(( … ))» marks of amended words, no `### Art. N` heading, and
  the source line says "Normattiva" instead of "Normattiva-Akn". The export
  is the last resort, when the page cannot be read, and the answer says so.
  A page's reading is kept 24 hours (`normattiva_pagine/`, `LEGAL_CACHE=off`
  switches the disk copy off): no request more than before when warm, one
  fewer for an article of a code when cold. Articles of one act cited with
  the year only share one lookup of its date.
- **The act's index and tree, as VisuaLex serves them.** `api.indice_atto`
  now reads the Akoma Ntoso export: the act's title as a heading, the
  rubriche of its main text, the repealed articles, and every part (an
  annex, the preleggi, a code's Dispositivo) with its own keys, rubriche,
  repealed articles and Normattiva number (`allegato`). It was Normattiva's
  `vediRubriche` list, two requests every time; it is now two requests the
  first time and none after (`vediRubriche` stays the fallback when the
  export cannot be read). New `api.albero_atto`: Normattiva's article tree
  (VisuaLex's `/fetch_tree`, its parser imported), every article with the
  part it belongs to, one request a day per act; `api.articolo_nell_albero`
  and `api.dove_altrove` are VisuaLex's existence check as functions. An
  `articolo_non_trovato` answer now says where else in the act the article
  is ("su Normattiva l'art. 32-ter si trova nell'allegato 8"), read from the
  export already fetched; never for a code's own part (art. 40 of the
  preleggi is not art. 40 of the codice civile).
- **The Akoma Ntoso parser merged with VisuaLex's, and tables in the text.**
  VisuaLex's parser is the base (its XML settings resolve no entity and open
  no connection; rubriche, repealed articles, act titles and each article's
  date are read from the export, for the act index that comes next), with
  mcp-legal-it's choice of which text an act serves on top. Tables are now in
  the text, as Markdown tables: the rates of the Tariffa of d.P.R. 131/1986
  ("9 per cento", "2 per cento"…) were missing from both parsers. Every other
  article text is byte for byte what it was (checked on 9 exports). The export
  is parsed off the event loop, and its access counter is no longer rewritten
  on every article served from cache.
- `docs/migration/visualex-inventory.md`: the function-by-function inventory of
  the VisuaLex readers that move into mcp-legal-it, with the choice for each.
- **`mcp_legal_it.api`: mcp-legal-it as a library, and its only stable surface.**
  Pure `async` functions with typed returns (frozen dataclasses), no Markdown,
  errors as data (`esito` from a closed vocabulary, plus `errore`). Norms:
  `leggi_riferimento`, `riferimento_da_parametri`, `testo_articolo` (with a
  required `canale`), `testi_articoli`, `indice_atto`, `testo_atto`,
  `annotazioni_brocardi`, `catalogo_alias`. Decisions, in one shape for every
  court: `leggi_decisione` (Cassazione, Corte costituzionale; a number found in
  both archives is `ambigua`; a miss says whether it is outside the archive
  window), the readers by source key for CeRDEF, TAR/CdS and the CJEU, and the
  searches (`cerca_decisioni_*`, `giurisprudenza_su_articolo`,
  `pronunce_costituzionali_su_norma`, `giurisprudenza_ue_su_articolo`,
  `cerca_giurisprudenza_unificata`). Field names follow VisuaLex's JSON where
  VisuaLex answers the same question; `come_dict` gives JSON-ready data; every
  network result carries its `fonti`. Importing it loads neither FastMCP nor the
  server and opens no connection (tested with FastMCP blocked and sockets
  blocked). `configurazione(client_factory=…, cache_dir=…, cache=…, brocardi=…)`
  injects the HTTP client factory, the cache settings and the Brocardi switch;
  the environment's *off* still wins. Reference, deprecation policy and the
  operations planned for the VisuaLex migration: `docs/api.md`. The public
  names and signatures are frozen by `tests/unit/test_api_surface.py`.
- `scripts/replay_mcp_outputs.py`: records the real HTTP exchanges of 36 MCP
  tool calls once, then replays them offline against a git ref and the working
  tree and compares every answer, `_meta` included, so a refactor can prove
  the tools' outputs did not change. The tape stays local.
- Concurrent cold requests for the same act now share one download of its
  Akoma Ntoso export (before, N callers downloaded it N times).
- **`LEGAL_BROCARDI=off`: the server without Brocardi.** Brocardi.it, the only
  private source (doctrinal notes and case-law abstracts, never the text of a
  norm), stays on by default and can now be switched off in one place. Off
  means: `cerca_brocardi` and `fetch_law_annotations` (tag `solo_brocardi`) are
  not listed (228 → 226 tools); no request reaches brocardi.it, because the two
  scrapers that build Brocardi URLs ask `lib/_brocardi_switch.py` before any
  I/O (and `_egress.is_allowed()` reports the host as refused); `cite_law(include_annotations=True)`,
  `giurisprudenza_articolo` and `mappa_orientamento` (tag `brocardi`) answer
  without it and say so. In code: `crea_server(brocardi=False)` for one server,
  `_brocardi_switch.disabled()` / `set_default(False)` for library calls (these
  two stop every request but do not change a server's tool list); an
  *off* set in the environment cannot be switched back on from code.
  `stato_server` reports the state. `tests/unit/test_brocardi_switch.py` mocks
  the network and fails if any Brocardi-tagged tool, or either scraper, sends a
  request to a Brocardi host, and walks the call graph of `tools/` so that a
  new tool reaching the scrapers without the `brocardi` tag fails too.
- **`crea_server(include_tags=None, exclude_tags=None, brocardi=True, *, name, prompts)`**
  in `mcp_legal_it.server`: a FastMCP server exposing only the selected tools,
  for a host that mounts mcp-legal-it into its own surface. It mounts the stock
  server and narrows it with visibility filters, so the tools keep names,
  schemas, annotations, `_meta` and middleware; an excluded tool is absent from
  `list_tools` and answered as unknown. Unknown tags raise `ValueError` with
  the vocabulary, and so does an empty `include_tags` (it would select
  nothing; `None` keeps every tool). The server's instructions are the stock
  ones without the tools it hides, so the model is never pointed at a tool it
  cannot call; the stock server does the same under `LEGAL_BROCARDI=off`, and
  the skills, agents and prompts now say `cerca_brocardi` (se disponibile). The stock server and the plugin are unchanged. Example and
  parameters in `docs/tool-tags.md`.
- `stato_server()`: the diagnostics tool that tells the caller WHAT it is
  talking to — package version of the running code, active tool count after
  the `LEGAL_PROFILE` filter, pinned clock, cache switch and directory,
  hostname. Modeled on the `get_quota_status` / `check_capabilities` pattern
  of the Scopus MCP servers; the declared total is derived from the audited
  annotation policy, so it cannot drift into a second handwritten count.
  Surface is now 228 tools (210 read-only, 170 local-only).
- `server.json`: the server declares its own identity
  (`io.github.capazme/mcp-legal-it`, stdio transport) in the official MCP
  Registry schema, with the environment variables every host can pass
  (`LEGAL_PROFILE`, `LEGAL_CACHE`, `MCP_CACHE_DIR`, `LEGAL_TODAY`, `LEGAL_NOW`).
  The README carries the `mcp-name:` marker so aggregators can verify the
  package/manifest association once a public distribution channel exists.
- `verifica_dpa_fornitore(dominio)`: probes a supplier's site on a fixed list
  of conventional paths for a published art. 28 DPA, judges the HTML or PDF
  it finds against GDPR markers and caches the determination for 90 days
  (`src/lib/dpa_probe/`; the hand-maintained DPA whitelist is gone). The probe
  is the one tool that contacts a host chosen by the caller, so it is fenced:
  public registrable names only (no addresses, ports, local or reserved
  names), every name resolved and refused when any address is not public,
  the same check on every redirect, the consult declared in
  `fonti_consultate` and the cache under `LEGAL_CACHE`. `SECURITY.md`
  documents the exception.
- TMview (EUIPO/TMDN trademark database) as a new source — module
  `src/tools/tmview.py` with 3 tools (218 → 221): `cerca_marchi` (search across
  UIBM, EUIPO, WIPO and ~75 national offices with office/Nice-class/status
  filters), `leggi_marchio` (full record by ST13: owner, representatives,
  goods and services per Nice class, publications), and
  `verifica_anteriorita_marchio` (preliminary prior-rights screening that
  separates identical from similar marks, with an explicit disclaimer that it
  does not replace a professional availability search). The client
  (`src/lib/tmview/`) talks to TMview's public JSON API with browser-like
  headers, a session warm-up request and a minimum interval between calls to
  coexist with the site's F5 anti-bot gate; a challenge response surfaces as
  a clear "retry in a minute" error instead of garbage output. New egress
  host `www.tmdn.org` declared in `src/lib/_egress.py` and SECURITY.md.
- `verifica_citazioni(..., formato="json")` and `cite_law(..., formato="json")`:
  structured output for programmatic clients (LibreLex-IT). Markdown output
  unchanged.
- Console entry point `mcp-legal-it` (`src.cli:main`), so the server starts
  with `uvx --from git+https://github.com/capazme/mcp-legal-it@vX.Y.Z mcp-legal-it`.
- The server now declares its package version to MCP clients
  (`serverInfo.version`).
- The refusal series as a picture: `verbale_mensile` and the CLI report carry a
  `grafico` block now -- one bar per month, scaled to the window's maximum,
  the zero mark for a silent month, the current month marked -- so "is this
  month worse than the last one?" reads at a glance in `/verbale` too, from
  the same data the table mirrors.
- Tool annotations: all 221 tools now declare `readOnlyHint` / `openWorldHint`,
  so hosts that pre-approve safe tools (Claude Desktop, Freebuff) can offer the
  204 read-only lookups without a per-tool click, while the 17 that write a file
  stay behind an explicit approval. The classification is audited from the call
  graph — decorated function → helpers → imported clients, looking for
  `open(..., "w")`, `write_text`, the document constructors and mutating HTTP
  verbs. It lives in `src/tool_annotations.py`, generated by
  `scripts/audit_tool_annotations.py` (`--check` fails the suite on drift,
  `--json` prints the per-tool evidence); a middleware stamps it on
  `tools/list`, and `tests/unit/test_tool_annotations.py` fails if a tool is
  renamed out of the policy.
- The 12 cache writers are flagged as such (`CACHE_WRITES`): their only write
  refreshes `${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}` (parsed acts, Brocardi
  article URLs, Consulta massime), which is worth telling apart from the 5 tools
  that produce a document.
- `LEGAL_CACHE=off` (also `no`, `false`, `0`, `none`, `disabled`) keeps the
  server off the disk entirely: the cache directory is then never read and never
  created, and the caches live in memory for the life of the process (the parses
  still work, they are just not persisted). `src/lib/_cache.py` is the single
  module that reads the switch and resolves `MCP_CACHE_DIR`; `MCP_CACHE_DIR`
  alone only relocates the files.
- The cache side is audited too. `scripts/audit_tool_annotations.py` declares
  every cache location (`CACHE_LOCATIONS`) and fails when a module starts
  resolving a cache directory without being declared, when a declared cache
  loses its literals, or when a cache writer stops consulting the switch; the
  generated inventory is `docs/cache-inventory.md` (location, files, retention,
  writer module and the tools that can touch it), compared by `--check` just
  like the annotation policy. `tests/unit/test_cache_switch.py` proves the
  switch, including that with `LEGAL_CACHE=off` not even the directory appears.
- The wall clock has one reader (`src/lib/_clock.py`) and `LEGAL_TODAY` /
  `LEGAL_NOW` pin it. Several tools are "as of today" by design (prescriptions,
  deadlines, the current IRPEF brackets, the running year for the Consulta
  dumps): without an override they cannot be reproduced, so a test on their
  numbers could either rot with the calendar or skip the most interesting half
  of the surface. The audit fails on any `date.today()`/`datetime.now()` call
  outside that module, so a new tool cannot opt out of being pinnable.
- `tests/unit/test_golden_calcoli.py` freezes what the local read-only tools
  answer (167 of them) in `tests/fixtures/golden/calcoli_locali/` (arguments + expected answer,
  pinned to `LEGAL_TODAY`/`LEGAL_NOW`, truncated at 4000 characters where an
  answer is a whole document). The reference is **one file per set of data
  tables**, derived from the code (`@sourced(...)` declarations plus the
  module-level tables each tool's reachable code reads, derived constants
  included): `indici_foi`, `indici_foi+tassi_legali`, `tabella_danno_bio`,
  `nessuna_tabella` (104 pure algorithms) and 20 more. A refreshed table or a
  mistyped bracket fails with the dataset named first — changing a single FOI
  index reports "tables involved: indici_foi (12/12 tools), tassi_legali
  (3/12)", lists only the two affected group files, and tags every changed tool
  with the tables it read. Regenerate deliberately with `GOLDEN_UPDATE=1 pytest
  tests/unit/test_golden_calcoli.py`; the reference is also checked for being
  pinned, complete, partitioned by table (no tool twice, none missing), free of
  error payloads and free of local paths, and each answer's own `dati_applicati`
  footer must agree with the group it is filed under.
- The stdio harness the runtime tests share now lives in
  `tests/unit/mcp_harness.py`, and its argument generation fills object-shaped
  parameters (rows like `eredi`, `acconti`, `voci`, `rischi`) and picks dates by
  role (`data_inizio`/`data_fine`, `anno_partenza`/`anno_arrivo`) instead of one
  value for every `data_*`. Every local read-only tool now answers with a real
  result, where 12 previously came back with a validation error.
- `scripts/tool_report.py` renders the surface as a single self-contained page
  (`docs/tool-report.html`): the 221 tools split into 167 read-only local, 37
  read-only external, 12 cache refreshers and 5 document generators, with the
  service each external tool reaches, the cache directory each writer can touch,
  and — as of the change below — the tables each one applies and whether their
  vintage needs acting on. It is built from the same audit as the annotations, so the page and the
  policy cannot disagree.
- `tests/unit/test_read_only_contract.py` proves the read-only claim at runtime:
  the server is started with its own `HOME` and `MCP_CACHE_DIR`, every local
  read-only tool is called with arguments generated from its input schema,
  and the sandbox, the checkout and the real MCP cache are fingerprinted before
  and after — any file created, deleted or modified fails the test. All of them
  answered and nothing changed.
- `tests/unit/test_provenance_datasets.py` demonstrates the table → tool mapping
  instead of re-deriving it: a table is perturbed in a throwaway copy of the
  server and the answers are compared with a clean baseline, in both directions.
  An answer that moves with a table whose footer does not name it is a silent
  reader; an answer that names a table and does not move with it is a decorative
  footer. The caller set comes from the tools' own footers, the controls are
  tools that read other tables — the two oracles are independent of the audit.
- Every table a tool reads now says so *and* says how current it is, including
  the tables preloaded at import: six tools that answered in silence
  (`cerca_codice_tributo`, `genera_modello_atto`, `lista_categorie_atti`,
  `indennita_preavviso`, `costo_lavoro`, `ravvedimento_operoso`) carry their
  `dati_applicati` footer, which is how the unverified vintages of
  `preavviso_ccnl` and `contributo_unificato` now reach the reader as an explicit
  warning instead of not reaching them at all.
- The audit fails when a shipped table is applied by no tool: either it is dead
  data or its reader is a load the walk cannot follow, and in the second case
  the tool answering from it reports no vintage. That check is what found
  `codici_tributo`, `modelli_atti` and `preavviso_ccnl`.
- Every tool call now declares, in its result `_meta` under
  `mcp-legal-it/opened_tables`, which hand-maintained tables it *actually* read:
  observed, not derived. `src/lib/_ledger.py` wraps the table-carrying constants
  (`src/table_bindings.py`, generated by the audit) in dict and list subclasses
  that note their dataset when read, so a call that opens no table — a pure
  algorithm — declares nothing, and one that applies two tables says so. The
  wrappers are shallow and transparent: nested values stay plain, so `json.dumps`,
  `==` and the host's serialization see the same objects as before.
- The `dati_applicati` footer is written from what the call read rather than
  from the `@sourced(...)` declaration: `_data.effective()` intersects the two,
  so a tool that branches between tables names the branch it took. Called with
  the required parameters alone, `note_iscrizione_ruolo` declares
  `codici_ruolo` + `contributo_unificato` but applies only the first, and that
  is now what its answer says. The observation is only worth as much as its
  coverage, so the two tables a tool reads inside a *function body*
  (`mediazione_obbligatoria` in `procedura_civile`, `tegm` in `verifica_usura`)
  now go through the accessor `_data.load(name)`, which records the read; the
  audit recognises the same call as a read, keeping the static map and the
  observation describing one act. Rendering a vintage goes to the cached `_read`
  underneath instead, because a footer that counted as applying the tables it
  describes would make every observation equal its declaration and no answer
  could ever narrow. The declaration remains the fallback for what cannot be
  wrapped (a table reached through a scalar computed at import), and with the
  two in-body reads observed it is now the *only* fallback left: no tool in the
  local surface answers from a table the ledger could not see.
- An expired covered period and an unverified provenance are structured fields,
  not only a line at the end of an answer. A dict answer carries `avvisi_dati`
  next to `dati_applicati`, every answer carries
  `mcp-legal-it/data_warnings` in its result `_meta` -- the only channel a tool
  returning a string has -- and both are the same sentence as the footer, so the
  two cannot drift. The states are told apart: `scaduta` means the covered
  period has ended (`tassi_legali` from 2027-01-01; `indici_foi` past its own
  period *plus* the 92-day tolerance for ISTAT publishing in arrears, so
  2026-09-30 and not 2026-06-30), `non_verificata` means nobody has established where the table
  comes from (`contributo_unificato`, `comuni`, `codici_ateco`, and 11 more), and
  a table that is neither raises nothing -- so the field means something
  whenever it appears, instead of being a list everybody learns to ignore.
  Which tables a warning is about follows the same observation as the footer,
  not the declaration.
- A stale or unsourced table now changes the answer, not only the footer.
  Every tool already declares a grade in its own docstring (`Precisione:
  ESATTO|INDICATIVO|STIMATO`, 144 of them, parsed from the line the calling
  model reads), and `src/lib/_precision.py` decides what the vintage does to
  that claim: an exact claim resting on a table nobody sources is **withdrawn**
  -- the tool returns `errore: "dati_non_affidabili"` with no figure at all,
  naming the table, its state and the file that would unblock it -- while an
  indicative one steps down to `STIMATO` and says so in `precisione`, in the
  answer body and in `mcp-legal-it/precisione` in `_meta`. An expired table is
  the milder case, because coverage is not provenance: it stops an answer
  anchored to today (the tool read the clock, observed per call through
  `_clock.consulted()`) and only downgrades one about a period that has already
  closed. With the shipped tables that is 6 refusals (`codice_fiscale`,
  `imposte_*`, `indennita_preavviso`, ...) and 4 downgrades
  (`ricerca_codici_ateco`, `cerca_ufficio_giudiziario`, ...), and
  the audit fails when a tool applies a table without declaring a grade, or
  declares a word `_precision.py` does not know -- an unknown grade would be
  read as the strongest claim. `tests/unit/test_precision_policy.py` covers both
  states on the wire and at the seam.
- A refusal is negotiable, not final. Every tool that reads a table now also
  takes `accetta_precisione` (`INDICATIVO` or `STIMATO`), declared in its
  signature and documented in the `Args:` block like any other parameter: the
  caller names the grade it will settle for, the answer is given at that grade,
  and both the body (`precisione.accettata`) and `mcp-legal-it/precisione` in
  `_meta` say the acceptance is what allowed it. The claim itself is not for
  sale -- asking for `ESATTO` on a table nobody sources is refused, and the
  refusal carries `concedibile` so the retry is a decision -- and no acceptance
  unlocks an expired table under a figure about today: a stale rate is wrong, not
  imprecise, and the refusal says `negoziabile: false` instead of offering a
  grade that would not help.
- Two tools can do without the table altogether, which is the other half of the
  answer. `@sourced(..., alternativa="parametro")` names the parameter that
  provides what the table would have: `codice_fiscale` accepts the catastal code
  (`codice_catastale`, so the algorithm is exact on an input instead of a lookup)
  and `indennita_preavviso` accepts the notice period (`giorni_preavviso`, which
  is the part of a CCNL table that no vintage can ever be right about, since the
  contracts get renewed). Such a call reads no table at all, so nothing about a
  vintage enters the answer: the footer is empty, no warning is emitted, and the
  answer says `dati_forniti_dal_chiamante: {parametro, al_posto_di}` rather than
  leaving the reader to guess what backs the number. The middleware knows the
  same map (`TOOL_ALTERNATIVES`, generated) so it does not fall back to the
  declaration and flag a table the call deliberately did not open.
- `scripts/update-data.py` says what each unverified table costs, and it is no
  longer a warning: the per-table block now lists the tools that apply it with
  their declared grade and whether they refuse or merely degrade, derived from
  the audit and the same rule the server runs. The eight `da_verificare` tables
  block seven tools outright (`comuni` two, `imposte_successione` two,
  `contributo_unificato`, `preavviso_ccnl`, `violazioni_patente` one each) and
  degrade nine, which is what makes the check a to-do list rather than a note.
- The audit fails when a literal restates a shipped table, which is how
  `preventivo_civile`'s contributo unificato bands lived in
  `fatturazione_avvocati.py` while `contributo_unificato.json` was updated next to
  them: a copy reads no file, declares no provenance, and drifts in silence. The
  comparison is on content and across shapes — the bands were copied as a list of
  two-tuples while the table stores them as dicts — with `TABLE_COPIES_ALLOWED`
  for a justified copy (empty today, and the audit fails on an exemption that no
  longer matches anything).
- `contributo_unificato.json` is reconciled with the DPR 115/2002 in force
  (verified against the reference table updated to D.L. 132/2014 and D.L.
  90/2014), and the table now declares it: `aggiornato_al` + `verifica:
  manuale`. Three entries carried values or shapes the source contradicts, and
  the reconciliation fixes them rather than vouching for them: `cautelari` was a
  flat €147 but the procedurali cautelari are *50% of the ordinary bands by
  value* (`cautelari.riduzione`); `esecuzione_mobiliare` was a flat €43 but is
  €43 *below €2,500 and €139 above* (scaglioni, with the boundary at 2499.99 —
  the largest two-decimal amount the "inferiore a €2.500" rule admits, since
  the band lookup is inclusive); `ottemperanza` was €650, the source says €300;
  the never-read `opposizione_esecutiva` key (full bands, where the rule halves
  them) is replaced by `opposizione_decreto_ingiuntivo` at half bands. The
  refusal of `contributo_unificato` disappears and the five tools that were
  degraded by its unverified vintage (`decreto_ingiuntivo`, `modello_notula`,
  `note_iscrizione_ruolo`, `preventivo_civile`, `genera_quotazione_docx`) answer
  at their full declared grade again — which is the mechanism working, and the
  reason the tests pinning the gap moved to tables still unverified.
- Refusals are put on record, so a reconciliation backlog can be ordered by
  what *did* block and not only by what could. With `LEGAL_REFUSAL_LEDGER=on`
  the ledger middleware appends one JSONL line per refusal and one per
  acceptance to `refusals.jsonl` under the cache root: the tool, the tables
  that caused it, the state, the grade claimed and what happened — a counter,
  not a log of the studio's work, so no case data ever reaches the file. It is
  opt-in (a read-only tool that refuses must not start writing files the host
  never asked for) and best-effort exactly like the cache: an unwritable ledger
  never turns a refusal into an error. The audit declares the ledger as a cache
  location, and its timestamps go through `_clock.now()`, so a pinned
  `LEGAL_NOW` pins the tally too (`tests/unit/test_refusal_ledger.py`).
- Every table the vintage policy can block now has a *supplying* alternative,
  not only a cheaper grade: `@sourced(..., alternativa=...)` is extended from
  two tools to all seven readers of the blocking tables. `contributo_unificato`
  takes `tabella_contributo_unificato` (a replacement table with the same
  shape, consumed by the whole computation including the appello/cassazione
  multipliers), `imposte_successione` takes `aliquote_franchigie` (the bracket
  list, read per `parentela` and tolerant of malformed entries),
  `imposte_compravendita` takes `aliquote_registro` (the registro section),
  `decurtazione_punti_patente` takes `tabella_violazioni` (the violation map),
  and `decodifica_codice_fiscale` takes `mappa_comuni` (a reverse catastal-code
  map). A call that supplies its datum reads no table, so the answer carries no
  vintage it does not rest on — and a caller who *can* vouch for a value no
  longer has to buy back a grade the table never supported.
- `backlog_riconciliazione` (the 222nd tool) is the read-out: the tables still
  unverified or expired, each with its source, its static cost (who reads it,
  at what declared grade, refusing or degrading — the audit walk, computed once
  per process and shared with `scripts/update-data.py`) and the action to take;
  when the ledger is on, the observed tally re-ranks the list, so the table
  that actually blocked twice outranks the one that only could have. With the
  ledger off it says so (`disponibile: false`) instead of staying silent, and
  the answer is frozen in the golden reference like every other tool's. The
  same derivation is what `/dati` (new plugin command) reads, so refreshing a
  table — verify the source, update the values, set `verifica: manuale` and
  `aggiornato_al`, re-run the suite — is a guided flow that never opens the
  code.
- `imposte_successione` and `violazioni_patente` are reconciled with their
  sources in force: the Agenzia delle Entrate schedule for the succession
  brackets and franchises (every value matched -- the fix was provenance, not
  numbers) and the art. 126-bis attached table for the licence points, where
  three values were wrong and are corrected (failing to yield 6 points, not 8;
  overtaking 3, not 4; driving uninsured 5 points, not 0), with the speeding
  bands tied to the right subsections of art. 142 and the pecuniary ranges
  alongside the points. Their refusals go away: the shipped tables now block
  three tools (`codice_fiscale`, `decodifica_codice_fiscale`,
  `indennita_preavviso`) instead of six, and the golden reference shows the
  diff instead of trusting the edit.
- `comuni`, `codici_ruolo` and `preavviso_ccnl` are reconciled with their
  official sources, and with them the backlog reaches **zero refusals** on the
  shipped surface: every table an exact-grade tool applies is now verified.
  `comuni` is checked name-by-name against the ISTAT catastal-code list
  (7,899 comuni): 143 catastal codes were wrong and are corrected, official
  denominations come first so the reverse lookup answers with them instead of
  an alias, unverifiable entries are dropped, and the table re-declares
  itself. `codici_ruolo` is rebuilt on the official DM 32/2012 / DGSIA
  object-code table. `preavviso_ccnl` is verified against the three contracts
  (metalmeccanici and commercio matched cell-by-cell; studi professionali had
  14 wrong cells, corrected). What is left unverified -- `codici_ateco`,
  `tribunali_competenti` -- has only INDICATIVO readers, so nothing refuses:
  answers degrade and say so. The refusal path keeps its wire coverage on a
  probe server (`plugin/server/probe_precision.py`, the same `sourced`
  wrapper, launched through the harness), so the policy's teeth are tested
  against a real refusal instead of against a gap the data work has closed.
- Monthly refusal report: `verbale_mensile` (the 223rd tool) reads the ledger
  the middleware writes (`${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/refusals.jsonl`,
  opt-in with `LEGAL_REFUSAL_LEDGER=on`) and compares the current month with
  the previous ones — refusals and accepted downgrades per tool, which table
  blocked, and whether the callers are negotiating past the policy. The
  aggregation lives in `src/lib/_refusals.monthly()`, the recurring habit in
  `scripts/verbale-report.py` (cron line or pre-release check), and the host
  command `/verbale` reads the same numbers inside a conversation; `/dati`
  points there from the data side. `tests/unit/test_refusal_ledger.py` covers
  the aggregation and the wire surface.
- Online-source provenance: every open-world answer now declares *when it
  consulted the web*. The shared HTTP wrapper and the direct `httpx` sites
  (`retry_request(dataset=...)`, `note_source(...)`) record the consult in a
  contextvar (`src/lib/_sources.py`); the same middleware pass that stamps
  tables and precision attaches `mcp-legal-it/fonti_consultate` to the result
  `_meta` — dataset name, `scheme://host//path` prefix (never a query string,
  so the caller's search terms stay out of the provenance), and a call-level
  timestamp from the unrecorded clock. The committed policy is
  `src/source_bindings.py`, derived by the audit from the call graph: a client
  that starts fetching a new dataset fails the suite until the policy is
  regenerated, and the CI runs that check (`policy-sync` job) on every push.
  `tests/unit/test_online_sources.py` proves the middleware, the URL privacy
  and the undeclared-source flag; the golden fails if a local answer's shape
  changes, and the audit pins which tool may name which source.

### Changed
- **Text answers are sent once.** The 60 tools that answer plain text (the
  norm, case-law, authority and register readers, and a few writers) used to
  send each answer twice: as the text block and again as `structuredContent`
  `{"result": <the same text>}`, because FastMCP gives a `-> str` function a
  wrapped output schema. They are now declared with `output_schema=None`: the
  answer is the text block only, and `tools/list` no longer carries their
  `outputSchema`. The text the model reads is unchanged; the tools that return
  a dict keep their `structuredContent`. A test keeps every new text tool in
  line. For a FastMCP Python client, `CallToolResult.data` is now `None` for
  these 60 tools: read the answer from `result.content[0].text`.
- **`fetch_full_act` reads a long act in windows.** It used to return the whole
  act in one answer: L. 300/1970 alone was about 52,000 characters (~15k
  tokens), the Codice civile about two million. It now returns windows of
  30,000 characters and takes the optional `da_carattere` parameter that the
  other reading tools already have: the final note gives the range, the total
  and the `da_carattere` to read on from. An act that fits in one window gets
  the same answer as before, and calls without the parameter keep working.
  The windows of one act are cut from one complete reading of it, kept in
  memory for the Italian day (Europe/Rome, also in a UTC container): a later
  window sends no request (without the Akoma Ntoso export a code is rebuilt
  article by article, thousands of requests), and concurrent first reads of
  one act share a single reading. A reading with articles missing is served
  but not kept, and such readings still run one at a time. A later window whose reading is gone is served only from the
  same text or from a complete Akoma Ntoso export, and then says it was read
  again; otherwise it is refused with a pointer to `da_carattere=1`, never
  served shifted. Known limit: windows carry no reading id, so if the text
  leaves memory and another caller reads the act again first, a later window
  is cut from that reading (refused only when the text differs). The citation
  gate does not credit an article heading that a window cut at either end
  («Art. 4» of «Art. 41» at the end, «art. 7» of «vedi art. 7» at the start).
  Known limit: a genuine heading on a window's first or last line is not
  credited either, so the gate may ask to read an article the window served
  (it never credits one it did not); cutting the windows on a line boundary
  would remove it, and departs from the shared paging contract.
- **A shorter `tools/list`, same contract.** A middleware
  (`mcp_legal_it/_listing.py`) changes only what the listing says:
  - an optional parameter is published as `type: [X, "null"]` with
    `default: null` instead of `anyOf [{"type": X}, {"type": "null"}]` (164
    parameters); hosts that read a property's top-level `type` now find it, and
    null stays legal, so a client that converts the schema to OpenAI's strict
    mode does not force the model to invent a value;
  - `additionalProperties: false` is left out of the 231 input schemas;
  - descriptions lose the indentation docstrings leave at the start of their
    continuation lines (words and line breaks stay);
  - tools are listed by name, the same order for every profile and subset.

  What a tool accepts does not change: FastMCP validates each call against the
  function's signature, so an unknown argument is still refused by the server
  with the same «Unexpected keyword argument» error. The difference is only for
  a client that checks arguments against the schema before sending: it no
  longer refuses an unknown argument itself, and leaves it to the server.
- **Cassazione search snippets without `<em>` tags.** Italgiure's highlighter
  wraps every matched term in `<em>…</em>`, and the passages of
  `cerca_giurisprudenza`, `giurisprudenza_su_norma`, `giurisprudenza_articolo`
  and the unified search reached the model with them (362 tags in one
  `giurisprudenza_articolo` answer). The «Estratto» and «Dispositivo (match)»
  lines now carry the plain passage. The request to Italgiure is unchanged, and
  so is `mcp_legal_it.api`, whose search results keep the fragment as the
  source serves it. The other search sources already returned plain text.
- **The installer configures a local server only.** `install.py` no longer
  offers the «remoto (SSE)» plugin mode (`--mode local|remote` and the
  interactive question are gone): it pointed at a personal tunnel address
  written in the code. The plugin always runs the server on the user's
  machine; a test keeps remote endpoints out of the installer.
- **`indennita_licenziamento` returns the range, not an amount** (#76). After
  C.Cost. 194/2018 struck the words «di importo pari a due mensilità … per ogni
  anno di servizio» from art. 3 co. 1 d.lgs. 23/2015, the amount is set by the
  judge between 6 and 36 mensilità, weighing seniority and the other criteria of
  art. 8 L. 604/1966; the tool still computed years × 2 (years × 1 for small
  employers) and returned it as `mensilita` and `importo`. The indemnity branch
  now returns `minimo_mensilita`/`massimo_mensilita`, `importo_minimo`/
  `importo_massimo` and the `criteri`, and no single figure: 6-36, or 3-18 for an
  employer below the art. 18 St. lav. threshold (halved by art. 9 co. 1, with no
  six-month cap after C.Cost. 118/2025). **Breaking**: the indemnity no longer
  has `mensilita`/`importo`, because no single figure follows from the law; a
  caller that read them reads the range. `tipo="reintegra"` is unchanged. The
  answer also warns that Normattiva still prints the words struck down by
  194/2018 in art. 3.
- **A recital's text is VisuaLex's** (`considerando 42 GDPR`): without its «(42)»,
  and on a modern Official Journal page without its footnote calls (a legacy page
  keeps them in the text: «dati(4)» in recital 1 of dir. 2002/58). `cite_law` still prints «(42)»
  before it, as the label. A legacy page's recitals are read in their sequence, so a
  footnote numbered like a recital is never taken for one.
- **EUR-Lex readers re-pinned to VisuaLex `d067f710`** (its #346, the findings of the
  #94 review): a heading glued to the end of a paragraph is an article only when a
  body follows it, and never in a paragraph quoted by the act or set in a table cell
  (no «phantom» article); the regex of an old Official Journal title is linear on
  long runs of blanks. On 23 whole pages and fixtures, 1325 of 1325 article texts,
  the trees, the rubriche and the titles are unchanged.
- **VisuaLex re-pinned to `02ebc80a`** (its #342 and #343, and the review of #279):
  - EUR-Lex: on a legacy class-less Official Journal page a heading glued to the
    end of the paragraph before it («… della prescrizione. Articolo 11») is read
    as the next article's. Dir. 85/374's art. 11 was «non trovato» and its text was
    served at the end of art. 10; both are right now, and the act's index has 22
    articles. Old Official Journal titles (85/374, 64/221) are read. On whole pages
    (GDPR, AI Act, TFUE, OJ and consolidated, 85/374) and every fixture, 1207 of
    1209 article texts are unchanged; the two that change are 85/374's art. 10 and 11.
  - `upcoming` carries `versions_between: n` when other versions not in force yet
    come before the one Normattiva shows; `versione="futura"` with a day before the
    latest of them is `verifica_non_disponibile` («Non so dire quale versione …»).
  - «cod post telecom», without dots, is the codice postale (as «cod. post. telecom.»).
- **EUR-Lex readers re-pinned to VisuaLex `b2f7a30f`** (its PRs up to #312): a heading
  «Articolo 15 bis» no longer answers a request for art. 15 on any markup, «Articolo
  15 bisTesto» included, and the article opens in any spelling («15 bis», «15-bis»,
  «15bis»). A heading an amending act quotes (in a table cell, or opening with «)
  is never one of its articles, in the text, the index and the rubriche. The
  consolidated-text regexes are linear on long runs of blanks, and the title comes
  from the Italian ELI metadata of a legacy page and from `title-doc-first` of the
  consolidated GDPR. The checks this package kept in its wrapper for these cases are
  gone: VisuaLex's reader does the same. The article texts of the GDPR, the AI Act
  and the TFUE are unchanged.
- **EU article text: VisuaLex's reader, from CELLAR, one page per act.** The text
  of an article of an EU act is read by VisuaLex's extractor
  (`lib/visualex/eurlex_text.py`, `eurlex_scraper.py` at `493a8dd1`), whose text is
  frozen. Before the switch, the two readers were compared on every article of the
  GDPR, the AI Act, directive 2002/58 and the TFUE: 591 of 591 identical, so the
  Official Journal texts served do not change. VisuaLex reads EUR-Lex through a
  browser; a serial A/B check showed CELLAR's copy gives the same bytes, so no
  browser enters the package. The page is kept a day (`eurlex_pagine`, declared in
  the cache audit): one request serves every article of an act. An empty or error
  page is not kept. On an Official Journal page, art. 15 is not served art. 15-bis
  when the act has no art. 15 (a check outside the imported code).
- **Python 3.11 or later.** The article-number patterns now imported from
  VisuaLex use possessive quantifiers, which Python's `re` reads only from
  3.11. `requires-python`, the two manifests, `install.py`, the CI matrix
  (3.11 and 3.12 × FastMCP 3 and 4) and the docs say so; the package declares
  its Python classifiers. The plugin and the Docker image already run 3.12.
- **VisuaLex's codes table, validity reader and sources golden re-pinned to
  `f47ac1b6`** (its PRs #310 and #337, after `4aa59a9d`). The legge fallimentare
  joins the acts whose text is their annex 1 (r.d. 267/1942, `;267:1`); the
  validity reader gains VisuaLex's refusal of a date with «originale», which this
  API already refused. The 13 new rows of VisuaLex's source convention match the
  identities built here.
- **VisuaLex's validity reader and codes table re-pinned to `4aa59a9d`** (its PRs
  #274, #276, #277, #279). `normattiva_validity` gains the later-text helpers and
  compares the page's article label as the tree does («135 sex decies» is
  «135-sexdecies»), and an unreadable date is refused before any request. The
  codes approved as an annex of their decree (codice del turismo, norme di
  attuazione del c.p.p., navigazione marittima, codici penali militari) and the
  acts whose articles are their annex 1 (TULPS, c.p.p. minorile, TU successioni;
  VisuaLex's `ANNEXED_ACTS`) are filed in `norma_data` with their part
  (`allegato` `"1"`, `"2"` for the codice penale militare di guerra), as VisuaLex
  files them now; the provisional `allegato=None` for them is gone. The
  divergences the 3.0 line kept until VisuaLex followed (a date always the text
  in force on it; the text in force today when the undated page is a later one)
  are closed. VisuaLex's sources golden and its validity tests are re-pinned.
- **VisuaLex's parser, suffix table and tree reader re-pinned to `0f1477c2`.**
  The Akoma Ntoso parser takes VisuaLex's linear patterns, the rubriche an
  amendment wrote without brackets and `comparable_article_key`: a suffix
  written in two words is keyed as the act writes it again («135-sex-decies»,
  as VisuaLex answers it) and joined only to compare, so «135 sex decies» and
  «135-sexdecies» are one article in the tree and in the «elsewhere in the act»
  check. The tree also reads the links an annex writes «art 1», without the dot
  (d.lgs. 36/2023, Allegato I.4), which it used to drop. The cached exports are
  read again once (cache schema 5). VisuaLex's tests for these pieces are
  imported with their fixtures.
- **The August suspension says when it moved a deadline, and what it does not
  cover (decision LI-042).** When the suspension changed the result, the nine
  deadline tools that apply it (`scadenza_processuale`,
  `termini_processuali_civili`, `scadenze_impugnazioni`, `scadenze_multe`,
  `termini_memorie_repliche`, `termini_procedimento_semplificato`,
  `termini_183_190_cpc`, `termini_deposito_atti_appello`,
  `termini_deposito_ctu`) add `avviso_sospensione_feriale`: a line telling the
  lawyer to recompute with `sospensione_feriale=False` if the case is excluded,
  and the excluded matters with their source (art. 3 L. 742/1969: labour and
  social security; art. 92 R.D. 12/1941: alimenti, procedimenti cautelari,
  amministrazione di sostegno, interdizione e inabilitazione, ordini di
  protezione, sfratto, opposizione all'esecuzione, dichiarazione e revoca dei
  fallimenti, materia corporativa, cases declared urgent). When it changed
  nothing there is no notice. The fixed sentence on exclusions that
  `termini_memorie_repliche` and `termini_procedimento_semplificato` appended to
  every answer is gone (it also said "opposizioni esecutive" where art. 92
  says "opposizione all'esecuzione"); the `scadenza` command and the
  `procedura-civile` reference carry the same list. `termini_esecuzioni` keeps
  computing the art. 617 opposition without the suspension (the prudent
  reading) and, when August falls in its 20 days, adds
  `avvertenza_sospensione_feriale`: whether art. 617 is excluded is debated,
  since art. 92 R.D. 12/1941 names only the "opposizione all'esecuzione".
- **The citation gate reads like the server, and checks decisions too.** The
  plugin's Stop hook, now also registered on `SubagentStop`, extracts citations
  with the server's own parser and resolver (moved, unchanged, into the
  stdlib-only `core/riferimenti.py` and `core/citazioni.py`, re-exported where
  they were): an act is identified by the URL `cite_law` would fetch, so
  aliases of one act coincide and "art. 2 Cost." no longer covers "art. 2 c.p.".
  Credit comes from what a tool returned — a `cite_law`/`fetch_law_article`
  result that served that article, a `fetch_full_act` text that contains it, a
  `leggi_*`/`cerca_*` result of the same court naming a decision's number and
  year in its heading (never the precedents cited in a decision's body) — anywhere in the session, its subagents included and other sessions
  never. It reads every text block of the turn plus the prose written with
  Write/Edit and the inputs of `esporta_atto_docx`/`genera_*`, finds acts away
  from the article ("D.Lgs. 196/2003, art. 13", "art. 6, par. 1, lett. f), del
  Regolamento (UE) 2016/679", "artt. 1218 e 1223 c.c.", TUB/TUF) and no longer
  reads "atto di costituzione" as the Costituzione. Still advisory and
  fail-open: one block per turn at most, "fuori copertura" on the line as the
  escape for sources no tool covers, a stdlib fallback reader if the server's
  code does not import; about 0.25 s on a 40 MB transcript.
- **Tool tags follow one taxonomy, and some desktop profiles change.** Every
  tool now carries exactly one *kind* — `normativa` (19), `giurisprudenza` (24),
  `autorita` (6), `registri` (5), `calcolo` (141), `redazione` (30),
  `diagnostica` (3) — plus, for case law, its court (`giurisprudenza_cass`,
  `giurisprudenza_cost`, `giurisprudenza_trib`, `giurisprudenza_amm`,
  `giurisprudenza_ue`) and, for an authority, `garante` or `consob`. The
  vocabulary is data (`mcp_legal_it/tool_taxonomy.py`), the table is
  `docs/tool-tags.md`, and `tests/unit/test_tool_taxonomy.py` fails on a tool
  without a kind or with a tag outside the vocabulary. Renamed or moved tags:
  TAR/CdS and CGUE tools are `giurisprudenza` (no longer `normativa`);
  `costituzionale` → `giurisprudenza_cost`; the Garante tools are
  `autorita` + `garante` + `privacy`, CONSOB `autorita` + `consob`; TMview is
  `registri` + `marchi` and the diagnostics `diagnostica` (none of them
  `normativa` any more); the EU-transposition tools are `normativa` +
  `recepimento_ue` (no longer `giurisprudenza_ue`). Hosts filtering on the old
  tags must update them.

  `LEGAL_PROFILE` now names kinds and areas, and every profile carries
  `diagnostica`. Tool counts, before → after:

  | Profile | Before | After | What changed |
  |---|---|---|---|
  | `full` | 228 | 228 | — |
  | `sinistro` | 81 | 79 | − TMview (3), + `stato_server` |
  | `credito` | 91 | 89 | − TMview (3), + `stato_server` |
  | `penale` | 53 | 51 | − TMview (3), + `stato_server` |
  | `fiscale` | 66 | 66 | — |
  | `normativa` | 69 | 70 | + `stato_server` (TMview kept through `registri`) |
  | `privacy` | 66 | 64 | − TMview (3), + `stato_server`; Garante kept (now named by `garante`) |
  | `studio` | 73 | 76 | + `stato_server`, `verbale_mensile`, `backlog_riconciliazione` |
  | `redattore` | 86 | 76 | − TAR/CdS (4), CGUE (4), TMview (3), + `stato_server` |
  | `cowork` | 79 | 77 | − TMview (3), + `stato_server` |

  The tools that leave a profile were in it only by the stray `normativa` tag:
  trademarks are not a subject of any profile except the all-sources
  `normativa` one, and `redattore` never included case law (no Cassazione),
  so TAR/CdS and CGUE do not belong there either. With `LEGAL_BROCARDI=off`
  every profile containing `normativa` shows two tools fewer.
- **BREAKING — the import package is now `mcp_legal_it`, no longer `src`.**
  A published package must not own the name `src`: installed next to any
  project whose own code is a `src` package, one of the two shadowed the
  other. The sources moved from `plugin/server/src/` to
  `plugin/server/mcp_legal_it/` and the `src` symlink at the repository root
  is gone (the library build reads the package from `plugin/server/`). The
  distribution name and the console script stay `mcp-legal-it`; the script
  now points at `mcp_legal_it.cli:main`, and `python -m mcp_legal_it` replaces
  `python -m src`. There is no `src` compatibility shim, since a shim would keep
  owning the colliding name: code that imports `src.*` (for example
  `from src.tools.varie import ...`) has to switch to `mcp_legal_it.*`. The
  MCP surface (tool names, parameters, outputs) does not change, except that
  `backlog_riconciliazione` now names a table as `mcp_legal_it/data/<name>.json`.
  The generated bindings are keyed on the new module names, and a new test
  fails when any of their keys stops naming a module that imports, because
  the runtime ledger skips an unknown module silently and every result would
  lose `dati_applicati`.
- License: from 3.0.0 the project is distributed under the Mozilla Public
  License 2.0 (`LICENSE`, every manifest and `pyproject.toml`). Up to the 2.x
  line it was Apache-2.0; those releases, and the contributions received
  under that license, stay available under it (`NOTICE`).
- The plugin keeps the 2.17.0 layout on the 3.0 line: the server starts with
  `uv run --frozen --no-sync` from `plugin/server/uv.lock` through
  `plugin/server/bootstrap.py`; `start_server.sh` and `plugin/settings.json`
  are gone. `scripts/build_targets.py` packages that layout: no launcher
  script in the plugin zip or the `.mcpb`, no `server/.venv`, and the
  claude.ai web-skills zips are built into `dist/web-skills/` and released as
  one asset instead of living in the plugin folder.
- `/release` is maintainer-only: it leaves `content/commands/` for
  `.claude/commands/` (the plugin ships 9 slash commands). Command
  `allowed-tools` now list each MCP tool under both prefixes, the manual
  `mcp__legal-it__` and the plugin's `mcp__plugin_legal-it_legal-it__`:
  `command_tool_namespace` in `content/targets.yaml` accepts a list.
- `termini_separazione_divorzio`: the 6/12-month separation period before
  divorce is no longer extended under art. 155 c.p.c. when it ends on a
  Saturday or a holiday. It is a minimum duration, not a deadline for an act
  (owner's legal reading). Example: 12 months from 15/03/2025 now end on
  Sunday 15/03/2026 instead of Monday 16/03/2026. The result carries a `nota`.
- CI also verifies the release tarball on every push and on every tag
  (`tarball-sync` job): `scripts/verify_tarball.py` compares `git archive` of
  the revision against the tree itself and fails when something forbidden
  (`/src`, `/tests`, any symlink) is inside, or when a tracked non-ignored
  file is missing -- the same two directions the marketplace sandbox enforces
  as `failed_content`, checked before the backend can see the release.
- Grounding rules normalized: the six agent skills carried seven diverging
  restatements of the same Legal Grounding rule -- they now share one
  canonical wording. The server's OUTPUT convention adds the provenance
  clause (`dati_applicati` with their vintage, `mcp-legal-it/fonti_consultate`
  from `_meta`), so every host surfaces where an answer's numbers come from.

### Security
- **The FastMCP floor excludes the vulnerable releases.** Every declaration now asks for
  `fastmcp>=3.4.11,!=4.0.*,!=4.1.0,!=4.1.1,<5` (library installs: `pyproject.toml`,
  `plugin/server/pyproject.toml` and the plugin lock's metadata) or `fastmcp>=3.4.11,<4`
  (the `.mcpb` and the OpenAI bundle's launcher). Before, `>=3.4` still admitted 3.0–3.4.9
  and 4.0–4.1.1, affected by GHSA-7xgj-8392-5q4r and, on 4.x, GHSA-vqqp-x5qm-5qp4.
  Today's installs already resolved 3.4.11 (lock) and the latest 4.x. The floor now holds
  that against an older cache or a pinned environment. `scripts/check_deps_sync.py` checks
  the new ranges. The `.mcpb` launcher string changes, so Claude Desktop rebuilds its `uv`
  environment once on the first start of 3.0.
- **fastmcp 3.4.11 in the plugin's lock** (was 3.4.9): GHSA-7xgj-8392-5q4r,
  «post-transform component authorization is skipped on direct calls»
  (medium, published 2026-10-23, fixed in 3.4.10). Same major; the declared range
  `fastmcp>=3.4,<5` is unchanged.

### Fixed
- **`api.leggi_provvedimento_amministrativo` reads the number as «N/AAAA».** The
  reader gives a TAR/CdS decision's number as «1918/2026» (from the page, as from the
  XML). The api took its first four digits as the year: parere n. 1918/2026 became
  «anno 1918». Sentenza n. 17/2021 lost its year. Now `numero` and `anno` are 1918 and
  2026; the portal's 9-digit form («202614035») is still read.
- **TMview's refusals are said as such.** When TMview turns a request away with HTTP
  401/403 (since 2026-10-29 its trademark-detail endpoint answers `{"error":"Forbidden"}`
  while the search still works), `leggi_marchio`, `cerca_marchi` and
  `verifica_anteriorita_marchio` say «TMview ha rifiutato la richiesta (HTTP 403)». They
  add that this does not mean the mark does not exist, and that the record is on
  www.tmdn.org. Before, the answer was «non raggiungibile», followed by httpx's English
  message with the request URL. A refusal is not retried.
- **`leggi_provvedimento_amm` reads the full text again.** Since October 2026 the
  portal's document address (`mdp.giustizia-amministrativa.it/visualizza/`) serves the
  provvedimento as an HTML page instead of the `<GA>` XML, and every reading answered
  «pagina di errore». The reader now recognises the page by its own markup before
  testing for the error page (which is HTML too, and still reported as an error, never
  read as text). It takes the court, the type, the number of the «REG.PROV.COLL.» line
  and the «Pubblicato il» date, so the **Estremi** line is unchanged («Sentenza n.
  17/2021, pubblicata il 09/11/2021»). A parere gives «Parere n. 1918/2026»; its date is
  the dispatch date, so it is not reported as a publication date. No text is dropped:
  paragraphs, list items, quotations, headings, table rows and loose text after a line
  break are all read. AP 17/2021 comes to 106,878 characters, against 106,448 for its XML
  body. The page carries no markup or embedded emblem. The 15,000-character cut still
  keeps the dispositivo, from the last block that opens with «P.Q.M.», «P.Q.M.:»,
  «p.q.m.» or «PER QUESTI MOTIVI». When none is found, the note says «dispositivo non
  individuato». The XML is still read when the portal serves it. Fixtures: trimmed copies
  of the real pages of Ad. Plen. n. 17/2021 (private parties and lawyers pseudonymised)
  and parere n. 1918/2026, and of the portal's error page.
- **The update notes of a Normattiva article are back** (3.0 only: 2.17.1 reads
  the Akoma Ntoso export, which carries them). Since articles are read from their
  page, an article set out in comma divs came without its «AGGIORNAMENTO (n)»
  notes and without any notice. VisuaLex's extractor drops them for that shape
  and for the plain-text one, and keeps them for a code's article.
  - **What a lawyer saw.** Art. 3 d.lgs. 23/2015 printed «di importo pari a due
    mensilità … per ogni anno di servizio» with no word of C. cost. 194/2018, which
    declared those words unconstitutional.
  - **Library.** `article_text` stays VisuaLex's, byte for byte. The notes are read
    from the same page into `TestoArticolo.note_aggiornamento`, a tuple of the new
    `NotaAggiornamento` (`numero`, `testo`, `ordine`, `corte_costituzionale`), in page
    order. It is `()` for a page without notes and `None` when the text is not a
    Normattiva page's. `note_non_lette` and the avviso «note di aggiornamento non
    lette: verificare su Normattiva» flag a note that cannot be read, a «((n))» with
    no note n, and a heading outside the known markup. A comma renumbered «((6)).»
    and a year «((2025))» are not calls.
  - **MCP tools.** `cite_law` and `fetch_law_article` print the notes under the text,
    in an «Aggiornamenti» section, unless the text already carries them (a code's
    article: never twice). `cite_law(formato="json")` carries `note_aggiornamento`,
    `note_non_lette` and `note_nel_testo`.
  - **Cache.** The page cache's records now carry the notes (`normattiva_pagine`
    schema 3: older records are read again).
  - **Agreed shape.** The shape is agreed with VisuaLex. A future «notes on request»
    switch will never cover these notes.
  - **Live gate.** `tests/unit/test_note_aggiornamento_live.py`, 5 articles, serial.
    The live phrase checks now read the text with its notes
    (`tests/unit/_norme_live.py`).
- **TUIR, TUB, TUF and the Testo unico sicurezza carry their full date.** The
  names `TUIR`, `TUB`, `TUF` and «testo unico sicurezza» resolved to the year
  alone, so `mcp_legal_it.api.leggi_riferimento("art. 1 TUIR")` returned a
  placeholder date (`…:1986-01-01;917`) with `data_risolta=False`. They now
  carry the act's date as Normattiva gives it: d.P.R. 22 dicembre 1986, n. 917;
  d.lgs. 1 settembre 1993, n. 385; d.lgs. 24 febbraio 1998, n. 58; d.lgs.
  9 aprile 2008, n. 81. EU acts keep the year alone, as they are cited. The
  live gate `tests/unit/test_atti_denominati_live.py` now also checks every
  Italian act of `ATTI_NOTI` against Normattiva, one request at a time, and
  refuses an Italian act with the year alone before any request.
- **Act titles from Normattiva read as plain text.** Normattiva escapes the
  title in `eli:title` twice, so `fetch_full_act` showed «Norme  sulla  tutela
  della libert&agrave; e dignit&agrave; dei lavoratori» for L. 300/1970, split
  over three lines under its `#` heading. The titles read from a Normattiva page
  are now kept on one line with single spaces, and the complete character
  references of `eli:title`, the only field Normattiva escapes twice, are
  decoded once more (a bare «&» or «&notizie» stays as it is): «Norme sulla
  tutela della libertà e dignità dei lavoratori, …». The same title reaches
  `mcp_legal_it.api.testo_atto().titolo`.
- **Amounts are written the Italian way in every tool's text.** Python's
  default format put «Euro 25,000.00» in the decreto ingiuntivo, «€1,234.00»
  in quotes and fee notes, «€1092.48» or «€850.0» elsewhere. They now read
  «Euro 25.000,00», «€1.234,00», «€1.092,48», «€850,00». The fix covers:
  - deeds: `decreto_ingiuntivo`, `sfratto_morosita`, `atto_di_precetto`,
    `nota_precisazione_credito`, and the CU note of `note_iscrizione_ruolo`;
  - quotes and fee notes: `preventivo_civile`, `preventivo_stragiudiziale`,
    `preventivo_volontaria_giurisdizione`, `modello_notula`,
    `spese_trasferta_avvocati`;
  - other professionals: `compenso_curatore_fallimentare`,
    `compenso_delegati_vendite`, `fattura_enasarco`;
  - civil procedure: `competenza_giudice`, `gratuito_patrocinio`. Its margin
    no longer prints «+-0,00 €» when it rounds to zero;
  - GDPR: `calcolo_sanzione_gdpr`;
  - ISTAT revaluation: `lettera_adeguamento_canone`, `calcolo_devalutazione`,
    `calcolo_inflazione`;
  - civil fee brackets: «fino a 52.000€», not «fino a 52000€»;
  - property, labour and tax: `spese_condominiali` (lift quota),
    `indennita_licenziamento`, the `regime_forfettario` limit message;
  - fuel price in `spese_trasferta_avvocati`: «1,789 euro/litro», not the
    «1.789» an Italian reads as one thousand seven hundred;
  - interest: the `interessi_acconti` warnings;
  - penal: the conversion rate of `conversione_pena`;
  - attachment: the pension note of `pignoramento_stipendio`.

  Every tool now formats amounts through one helper, `lib/_numeri.numero_it`:
  the module copies call it instead of repeating the code. JSON numbers in
  structured answers are unchanged.
- **A profile no longer prints a false drift warning.** Under any
  `LEGAL_PROFILE`, the first `tools/list` printed «tool_annotations: policy
  names no longer registered: …» to stderr, listing every tool the profile
  only hid. The check now reads the registered tools, so it speaks only when a
  tool named in the policy is really gone.
- **Art. 1 of the legge fallimentare is the law's, from its own page.** Its
  articles are annex 1 of r.d. 267/1942, and the URN lacked the part: the page
  of `;267~art1` is the approving decree's, so the law's art. 1 came only from
  the Akoma Ntoso export (indicative, four requests). The URN is now
  `;267:1~artN` and `norma_data.allegato` `"1"`, as VisuaLex files it.
- **`python -m mcp_legal_it` refuses an unknown `LEGAL_PROFILE` without a
  traceback**, like the console script; the encoding guard of the package also
  sees `io.open`, `codecs.open`, an `open` under another name and
  `encoding=None` (#76 review).
- **ANAC: linee guida and bandi tipo are no longer looked up by number and
  year.** Their titles carry the number without a date («Linee guida n. 4»), so
  the lookup mostly answered «not found»: `leggi_atto_anac` now says to search
  them with `cerca_atti_anac` and read the act from the reference it returns. A
  year the portal's «Anno» filter does not list falls back to the newest acts,
  and the answer says so (#82 review).
- The citation hook (Stop and SubagentStop) no longer opens the server's
  Python environment. `uv run --project <plugin>/server`, even with
  `--no-sync`, deletes and recreates that environment whenever it finds it
  linked to an interpreter it cannot reach, and `--no-sync` then leaves it
  empty under the running server ("No module named ..."). The hook now runs
  on uv's Python 3.12 with `--no-project`: the gate and its reader need only
  the standard library. `check_directory_readiness.py` accepts a bare
  `uv run --no-project`, which installs nothing.
- **An unknown `LEGAL_PROFILE` refuses to start; `calcoli` exists** (#76). A
  name that is not a profile fell back to `full` in silence: asking for the
  offline `calcoli` profile (documented in 2.x, never defined) exposed every
  tool, the online ones included. The server now stops with an error listing the
  valid profiles (the console script prints it without a traceback), and
  `calcoli` exposes the 144 calculators and diagnostics, none of which goes
  online (a test checks the policy's sources and open-world hints). A blank
  value is still `full`.
- **The server starts on Windows without `PYTHONUTF8`** (#76). Thirty reads and
  writes of text files (the bundled JSON tables, the Brocardi cache, the
  `legal://` resources) named no encoding, so Python used the locale's: cp1252 on
  Windows, where the server failed at start with a `UnicodeDecodeError`. Every one
  says `encoding="utf-8"` now; a test scans the package for text I/O without an
  encoding and another imports the server with `-X warn_default_encoding`, so the
  mistake cannot come back.
- **Installing from git works on Windows** (#76). The 2.x root held `src` as a
  symlink to the package: on Windows, without `core.symlinks`, git checks it
  out as a text file and `pip install git+https://…` built a wheel with no code.
  The 3.0 package is found under `plugin/server` with no link (a wheel built
  from the repository root ships the whole `mcp_legal_it`), and a test now fails
  if git ever tracks a symlink again.
- **An EU article the text in force no longer has says so.** Without a date an EU
  act is read from its latest consolidation, and an article a later act repealed
  is not in it: art. 1 of dir. 2009/136 is not in 02009L0136-20201221. The answer
  was a bare «non trovato»; it now says the article is not in the consolidated
  text at that date (CELEX), was probably repealed or deleted by a later act, and
  that the Official Journal text is available with `versione="originale"`, in
  `errore` and in `avvisi`, with `consolidato` naming the consolidation checked.
  The Official Journal article is not served in its place.
- **Italgiure searches on an article find the same decisions however the code
  is written** (#73, reported with a patch by @SOsintOps).
  `giurisprudenza_su_norma("art. 2043 cod. civ.")` searched only the phrase
  typed, and lost the 1350 civil decisions that write «2043 c.c.»; «codice
  civile», «Costituzione», «cpc», «cod. pen.», «CCII» did the same. Every
  spelling of a code (its abbreviation with or without dots, each form Italgiure
  decisions use for it) now gives the query of the abbreviation, and so do act
  types without dots («d.lgs 231/2001», «dpr 445/2000»). A spelling must end
  where a word ends: «c.p.i.» (codice della proprietà industriale) is no longer
  read as the codice penale, nor «l.r. 12/2005» as the national law 12/2005,
  nor «l'impresa» as a law; «d.lgs.vo» and «d.l.vo» are legislative decrees.
  The codes that are numbered acts (t.u.b., t.u.f., codice del consumo, codice
  della strada, c.p.a., CCII, codice della navigazione) no longer OR in the bare
  «art. N», which matches any decision citing any art. N: the article is tied to
  the act's number and year by proximity, as for the other acts. The bare form
  stays for c.c., c.p., c.p.c., c.p.p. and the Constitution, and the acronyms
  without dots («TUB», «TUF», «cds», «cpa», «cod. cons.») are searched as
  phrases of their own. The search for the act's number/year no longer slows
  down quadratically on a long run of digits, and a double quote in the
  reference no longer closes the Solr phrase (it could inject a clause).
- **Giustizia Amministrativa: two quoted phrases no longer end in «non
  raggiungibile»** (#52). The firewall in front of the portal answers 403 to a
  search holding two phrases in quotes, and the tools reported the source as
  down, echoing the request URL with its session token. Such a query is now
  refused before any request, with a way to rephrase it (one phrase in quotes,
  the other words free: verified live); any other 4xx from the portal says the
  portal refused the request, not that it is unreachable, and no error repeats
  the request URL (a 5xx is still the source down). Same rules in
  `giurisprudenza_amm_su_norma`, `cerca_giurisprudenza_unificata` and
  `api.cerca_decisioni_amministrative` (`richiesta_non_valida`).
- **An EU regulation or directive is served in its text in force** (issue #50).
  `cite_law("art. 111 Regolamento UE 2024/1689")` served the Official Journal text
  of 12.7.2024, while Reg. (UE) 2026/1744 had rewritten par. 2 and added par. 4.
  Without a date, an EU act is now read from its latest consolidation when that
  consolidation includes an amending act or a corrigendum, with one SPARQL query to
  CELLAR per act, kept a day. A corrigendum published in the Official Journal
  changes the text in force, so it counts as an amendment. **The Italian text of
  the GDPR served until now (2.x included) lacked the Italian corrigendum**: 36 of
  its 99 articles read differently from the corrected text, e.g. art. 7 the data
  subject «presta» (not «esprime») consent, art. 17 «obbligo giuridico» (not
  «legale»), art. 41 «controllo» of codes of conduct (not «monitoraggio»). It is
  now read from 02016R0679-20160504, whose notice says it incorporates the
  corrigenda published in the Official Journal. A consolidated text is `INDICATIVO`, and an `avviso` says it is
  EUR-Lex's documentation and that only the Official Journal text is authentic.
  `consolidato` (CELEX, date, amending acts) and `consolidato_verificato` are in
  `api.testo_articolo` and in `cite_law`'s JSON, always present. Without an
  amending consolidation, the Official Journal text is served, `ESATTO`. When
  CELLAR cannot say, the Official Journal text is served with a notice as its
  first line, `INDICATIVO`. `cite_law(..., versione="originale")`, new and
  optional, gives the Official Journal text of an EU act or Normattiva's original
  of an Italian one. In the api an EU act now has a text at a date: the latest
  consolidation dated on or before that day, with a notice that consolidations can
  lag behind amendments; a day before the act's publication in the Official
  Journal is `riferimento_non_valido`, and a day before its entry into force has a
  notice. A consolidation dated after today is not served as in force: it is
  announced in `upcoming` and an `avviso`. The lookup waits at most 12 s, never
  retries, and remembers a failure for five minutes. Treaties, recitals and annexes
  are not looked up.
  `api.cerca_decisioni_amministrative` (`richiesta_non_valida`). A 429, or a
  pause the portal asks for, reads «troppe richieste: riprovare tra qualche
  minuto», not «non raggiungibile» (the api outcome is unchanged); reading a
  provvedimento never talks about a query's syntax, not even when the search
  page it opens first is refused.
- **An article an EU amending act quotes is no longer served as the act's own.**
  Dir. 2009/136/CE rewrites articles of dir. 2002/22/CE and quotes each one inside
  its art. 1. «art. 23 dir. 2009/136» was served art. 23 of dir. 2002/22 as amended,
  and so were 21, 22 and 27. On a modern Official Journal page an article whose
  every heading sits in a table cell or opens with « is a quotation, now «non
  trovato»; where the act's own article has its `div#art_N`, a text whose first
  lines are not the own heading and the line after it is refused. On the legacy
  class-less page the first heading naming the article decides (a «-heading is
  skipped): inside a table cell it is a quotation. VisuaLex's reader does the same
  since `b2f7a30f` (its #312), which the 3.0 line imports.
- **An act cited with the year only takes its full date from its own page's
  title.** The full date of «d.lgs. 36/2023» is read from the title of the page
  already fetched (VisuaLex's `date_from_title`, imported), and only when the
  title names that type, year and number: the resolver does not check what it is
  asked, and the page's ELI date used to be accepted on the year alone. A type
  outside VisuaLex's nine keeps the ELI rule. A found date is kept a year in
  `${MCP_CACHE_DIR}/act_dates.json`: after a restart a year-only citation costs
  no request for its date. A date read from the ELI alone (a kind the titles do
  not cover) serves the call and is not kept.
- **A page asked for an article with no digits is checked against today's
  window too.** Such a number has nothing to compare with the page's, and the
  undated page went through unchecked.
- **A citation without a date is the text in force today, even when Normattiva's
  page is not.** The page Normattiva serves without a date can be a version not
  in force yet: on 21/10/2026 art. 3 of d.P.R. 131/1986 (and of d.lgs. 546/1992,
  d.P.R. 633/1972, d.lgs. 346/1990) came back «ARTICOLO ABROGATO», in force from
  1/1/2027, and `cite_law` and `api.testo_articolo` served the repeal as today's
  text. The page's window is now read with the text (VisuaLex's
  `extract_validity`, imported): when it starts after today, or the page states
  none, the page at today's date is read (one request more, only then), or the
  export at today's date when that page cannot be read; never the undated page.
  `api.testo_articolo` fills `validity` from the same page and adds `precisione`
  (`ESATTO` for the page's text with its validity, `INDICATIVO` otherwise),
  `avvisi` (the coming version, with its day), `successione` (the repealing
  act a notice names, `INDICATIVO`) and `upcoming` (VisuaLex's: `change`,
  `valid_from`, `version_number`). `cite_law`'s JSON gains the keys `avvisi`
  (a list) and `upcoming` (an object or `null`), always present; its Markdown
  adds the line «**Attenzione**: …».
- **An article number with a long run of blanks no longer takes seconds.**
  VisuaLex's normaliser of article keys was quadratic: «1», 20,000 blanks and
  «x y» took 18 s. At `0f1477c2` it is linear (2 ms on the same input), and a
  test keeps every pattern of the normaliser under 0.1 s on such inputs.
- **Art. 3 of l. 654/1975 is the law's, not the Convention's.** On the Akoma
  Ntoso path the largest part of an act won, so a law that executes a treaty
  served the treaty's articles under its own numbers (art. 3 on apartheid for
  the law's repealed art. 3). The annexed part is now the act's text only when
  the act approves it, as a code's decree does ("È approvato il codice…").
- **`allegato` is Normattiva's position, as in VisuaLex.** In `NormaDati` and
  `api.riferimento_da_parametri`, a digit `allegato` is the `:k` of the URN
  (`;104:2` is the codice del processo amministrativo); it was read as the
  name the act gives an annex, so `allegato="2"` of d.lgs. 104/2010 reached its
  "Allegato 2", the implementing rules, and the preleggi by `allegato="1"`
  were not found. On the HTML channel these articles are now VisuaLex's page,
  no longer the export's text (a page is accepted only if its text is the
  export's article). A name ("I.7") stays a name, so does an EU act's
  `allegato`, and `"0"`/`"02"` are refused. `norma_data`
  carries what VisuaLex files the norm under: the `allegato` the caller gave,
  a code's default part, or none (see `docs/api.md`).
- **An article of an annex has its own URN.** "allegato I.7 art. 30 d.lgs.
  36/2023" answers with `;36:8~art30` (the act's URN before) and, on the HTML
  channel, that page's text. "art. 120 d.lgs. 104/2010" is read from the
  code's own page, `;104:2~art120`, instead of the export.
- Italgiure's bundled intermediate certificate is checked against its SHA-256
  pin every time the TLS context is built, as VisuaLex does: a file swapped
  inside an installed package is refused instead of trusted (the pin was
  checked only by a test). `lib/_egress.is_allowed` refuses a backslash, a
  control character, credentials and any scheme but http(s), the URLs that a
  browser and Python read as different hosts.
- **Appellee's deadline: 20 days before the hearing, not 70 (decision LI-040).**
  `termini_deposito_atti_appello` computed the comparsa of the appellee (and so
  the cross-appeal deadline, a decadenza under art. 343 c.p.c.) 70 days before
  the hearing, through art. 166 as the first Cartabia text of art. 347 implied.
  Art. 347, co. 1, c.p.c. as amended by D.Lgs. 164/2024 reads "almeno venti
  giorni prima dell'udienza indicata nell'atto di citazione o di quella fissata
  ai sensi dell'articolo 349-bis", and art. 7, co. 1, of that decree applies it
  to the proceedings introduced after 28/02/2023. The tool now counts 20 days
  back (August suspension and art. 155 anticipation as before), cites art. 347
  co. 1 and art. 343 instead of art. 166, and adds `avvertenza_regime_transitorio`
  for appeals introduced between 28/02/2023 and 26/11/2024 (D.Lgs. 164/2024 is
  in GU n. 264 of 11/11/2024 with no entry-into-force clause, so it applies
  from the fifteenth day, art. 10 disp. prel. c.c.): in that window art. 347
  pointed to the 70 days of art. 166, and whether the 20 days apply backwards
  is for the lawyer to assess. The warning also appears when the notification
  date of the citation is not given, since the appeal may fall in the window.
  Before 28/02/2023 the term was already 20 days (art. 166 as then in force).
  The reference `procedura-civile` and the docs say the same; the 70 days of
  the first-instance comparsa (art. 166) are unchanged. All norms re-read on
  Normattiva and the Gazzetta Ufficiale on 2026-10-21.
- **D.M. 55/2014 minimums are the exact half of the medium, to the cent
  (decision LI-041).** Art. 4, co. 1, lets the medium be "diminuiti in ogni caso
  non oltre il 50 per cento": the floor is the half. The table rounded it to
  the euro in 42 of its 94 minimums (40 up, e.g. 131 → 66 instead of 65,50;
  2 down, below the floor: 354 for a medium of 709, now 354,50), and one
  volontaria giurisdizione minimum was a whole euro too high (trattazione up to
  5.200: 107 for a medium of 212, now 106). `parametri_forensi.json` now
  carries the exact half (65.5, 212.5, ...), and the minimums computed in code
  (civil bands above 32 million, stragiudiziale above 520.000, `modello_notula`)
  use the same rule. Affected at `livello='min'`: `parcella_avvocato_civile`,
  `parcella_avvocato_penale`, `parcella_stragiudiziale`,
  `parcella_volontaria_giurisdizione`, `preventivo_civile`,
  `preventivo_stragiudiziale`, `preventivo_volontaria_giurisdizione`,
  `calcolo_notula_penale`, `modello_notula`; `genera_quotazione_docx` already
  used the exact half. The maximum follows the same rule: the medium "aumentati
  fino al 50 per cento" is the exact one and a half, to the cent (131 → 196,50,
  not 197), since a maximum rounded up overstates the ceiling. The table had it
  rounded in 44 of 94 maximums (39 up, 3 down, 2 a whole euro too high); the
  code-computed maximums and `modello_notula` at `livello='max'` changed too. The
  medium stays rounded to the euro, as the table transcribes it.
- **`cite_law` reads constitutional laws, royal decree-laws and lieutenancy
  decrees.** "art. 1 l. cost. 3/2001" answered "atto non riconosciuto": the
  reference parser had no `l. cost.` / `legge costituzionale`, `r.d.l.` /
  `regio decreto-legge` or `d.l.lgt.` / `d.lgs.lgt.`. They now resolve to the types
  the URN builder knows (`legge.costituzionale`, `regio.decreto.legge`,
  `decreto.legislativo.luogotenenziale`), and the citation gate never reads their
  numbers as decisions.
- `cerca_brocardi` now declares Italgiure among its online sources. Its probe of
  the archive window was missed by the sources audit (a call made through a
  module that only imports the function), so the answer's `_meta` listed
  `italgiure` under `non_dichiarate`. The audit now follows such calls.
- **`cite_law` with the act written first.** `"D.Lgs. 196/2003 art. 13"` was read
  as an act name: the decree resolved, the article was dropped and the answer
  was art. 1 of the Codice privacy, with no warning. Same for
  `"D.Lgs. 36/2023 allegato I.1 art. 1"` (art. 1 of the code). The act-first
  form (act, then article with its comma/lettera indicators and/or an annex) is
  now parsed like the article-first one; a reference naming an article that
  cannot be told apart from the act is refused with the expected-format error.
  Shared by every tool that uses the reference parser.
- **Italgiure over verified TLS.** The server sends the wrong intermediate
  certificates, so the client ran with `verify=False`. The missing one ("TI
  Trust Technologies OV CA", signed by the USERTrust RSA root in certifi) ships
  in `lib/italgiure/ti_trust_ov_ca.crt` and is added to certifi's roots; a test
  fails if `verify=False` appears anywhere in the package, and raises a renewal
  alarm 180 days before the intermediate expires (2029-07-29).
- `.mcpb` and the OpenAI config pin `fastmcp>=3.4,<4` (the floor was 2.0, older
  than the FastMCP the server needs). The change rebuilds the extension's uv
  environment once, on the first start of 3.0.
- **`verifica_citazioni` and other courts.** "Corte cost. n. 238/2014" and
  "Cons. St. n. 1/2020" were looked up on Italgiure as Cassazione and reported
  "inesistente". Corte costituzionale decisions are now checked on the Court's
  archive; Consiglio di Stato, TAR, CGUE, Corte dei conti, Corte EDU, tax and
  merits courts (giudice di pace included, in any case) are "non verificabile",
  with the tool to search them.
- **A range of articles is refused.** "art. 3-5 c.c." (also "3 - 5", "3–5",
  "artt. 3-5") became `~art35`: the
  library API returned the URN of art. 35 as "trovato". `cite_law`,
  `fetch_law_article` and the API now answer "chiedere un articolo alla volta".
- The annex parser (`split_annex`) ran in exponential time on a long article
  string (20 characters: 0.44 s, x4 every 2 more); it is linear now.
- The disposizioni di attuazione del c.p.c. are dated 18/12/1941 (R.D. n. 1368)
  in citations and URNs, not 25/08/1941; a test cross-checks the dates of every
  code across the three tables that state them.
- Corte costituzionale with `LEGAL_CACHE=off`: each decade bundle (~56 MB) is
  downloaded once per process and kept in memory (cap 256 MB, same 7-day expiry
  as the disk cache), instead of on every call; concurrent calls share one
  download.
- **Seven codes served the approving decree.** Their articles sit in an annex
  of the decree and the URN lacked it: "art. 3 codice del turismo" was the
  decree's "Abrogazioni". Fixed for the codice del turismo, the codici penali
  militari (di pace), the norme di attuazione c.p.p., the regolamento di
  esecuzione del codice della navigazione, the c.p.p. minorile, the TULPS and
  the TU successioni e donazioni. A live gate (`test_codici_urn_live.py`) checks
  every code before a release.
- `cite_law` recognises "c.p.m.p.", "c.p.m.g." (each military code on its own,
  also through the AKN export, which bundles both), "disp. att. c.p.p." and
  "att. c.p.p."; the all-caps "ART. 3" head (codice del turismo) is read as the
  served article.
- **`leggi_sentenza_cgue` fetches only CELLAR.** The `cellar_uri` came from the
  caller and was fetched as is: on the HTTP transport any client could read
  pages reachable from the server (localhost, cloud metadata, intranet). Only
  `http(s)://publications.europa.eu/resource/...` is accepted now, refused as
  `bad_input` before any request.
- **Generated documents are private.** Procure, quotazioni, atti, supplier
  reports and law PDFs are saved to `<tempdir>/mcp-legal-it` created 0700 (on
  Linux it was a world-readable `/tmp/mcp-legal-it`); a symlink or a folder
  owned by another user is refused. `esporta_atto_docx` used a hard-coded
  `/tmp` instead of the temp dir.
- `esporta_atto_docx`: numbered lists keep the typed numbers (1, 2 / 1, 2 / 10
  instead of 1..5), `**`/`*` in headings and `***x***` no longer leak
  asterisks, the title heads every page.
- Content: the non-cumulation of mora and revaluation is art. 1224 co. 2 c.c.
  (Cass. SS.UU. 19499/2008), not SS.UU. 16601/2017; giudice di pace 10.000 /
  25.000 euro (art. 7 c.p.c.); conclusionali and repliche under art. 189 (not
  the old art. 190); compensatory interest not on the fully revalued sum.
- `genera_procura_liti_docx` cites "Regolamento (UE) 2016/679";
  `indice_documenti` returns an error for non-numeric or negative pages
  instead of raising.
- Importing `mcp_legal_it.tools.legal_citations` first no longer fails on a
  circular import (library callers, single test files).
- Distribution: the citation-gate hook starts with `uv run --no-sync` (it
  installed the server's 76 packages on a fresh plugin); the plugin zip and the
  `.mcpb` no longer ship `*.egg-info`, `.DS_Store` or key files from the
  checkout; wheel and sdist carry `LICENSES/Apache-2.0.txt`, which NOTICE
  refers to; the Docker image runs as an unprivileged user (an `mcp-cache`
  volume created by an older image is root-owned: chown or recreate it, or the
  server runs without the disk cache); `scripts/corpus/extract_references.py`
  explains that the migration is done instead of crashing.
- Live gates realigned with their sources: CeRDEF unknown GUID is `not_found`,
  INPS reworded the ex-ENPALS split, Normattiva alternates "è"/"e'", a stale
  data path left by the package rename.
- Deadline tools: `giorno_settimana` is always the Italian name. It came from
  `strftime("%A")`, which follows the process locale, so the same output mixed
  «lunedì» and «Monday».
- `termini_esecuzioni`: the art. 617 term (opposizione agli atti esecutivi) is
  now `tipo='opposizione_atti_esecutivi'`. The old name `opposizione_esecuzione`,
  which read as art. 615, is removed: it now returns an error listing the
  accepted values.
- CeRDEF (giurisprudenza tributaria) works again and a failure of the source
  no longer reads as "no results" (#46). The portal changed its advanced
  search form and its XML: it answered every request of the old client with
  an HTTP 200 error page ("Ambito di ricerca non valido"), which the client
  read as zero results, so `ultime_sentenze_tributarie` reported "nessuna
  sentenza" to every call (and the weekly digest dropped the tax section),
  `cerca_giurisprudenza_tributaria` found nothing on any query, and
  `cerdef_leggi_provvedimento` returned an empty text as a success. The
  client now posts the current form (field names and option values verified
  against the live form by a unit test on a saved copy and by a live test),
  reads the new result and detail XML, follows the portal's own paginator,
  decodes the portal's JS escapes (`\à`, `\'`, `\u200B`) and keeps every
  cited norm inside its sentence (the portal links each citation, which used
  to split the text at every one of them). An error page,
  an unrecognised payload (a result list or a detail without the elements the
  client reads) or an empty list the portal's own counter does not confirm
  raises a `source_error` that every tool renders as `**Errore**` (the unified
  search labels it "errore", not "0 risultati"); an unknown filter is refused
  before any request; an unknown GUID is reported as such, not as the source
  being unreachable.
- `ultime_sentenze_tributarie` covers the decisions issued in the last twelve
  months (by issue date: CeRDEF exposes no publication date): the portal
  refuses a search without criteria, and ordering a whole CGT group by date
  takes 20-100 seconds. `ente="cgt_primo_grado"` is served by the group of all
  tax courts filtered client-side (the portal has no first-instance group), so
  `cerca_giurisprudenza_tributaria` requires `data_da` with it; the filter
  reads at most 250 items and, when it stops with items left unread, says so
  instead of reporting fewer results (or none) as if they were all. The
  `codice` criterion no longer exists on the portal; `parole_adiacenti` and
  `operatori_logici` are new.
- Two of the reconciled tables re-read against the primary source
  (2026-09-20). `violazioni_patente`: generic failure to yield is art. 145
  c.10 (5 points; the stop line, c.5, keeps its 6), safety distance and
  wrong-way driving now rest on their base commi (art. 149 c.4: 3, art. 143
  c.11: 4) with the aggravated cases as separate keys
  (`distanza_sicurezza_collisione` 5, `distanza_sicurezza_lesioni` 8,
  `contromano_curve_dossi` 10), hit-and-run split into injuries (art. 189
  c.6: 10) and damage to things only (`fuga_incidente_cose`, c.5: 4).
  `contributo_unificato`: sourced from art. 13 DPR 115/2002 on Normattiva
  instead of a secondary table; adds the fixed 168 for oppositions to
  enforcement acts (c.2), the three public-contract tiers up to 6.000 above
  1 M (c.6-bis lett. d), the 1.800 abbreviated rite, the 300 for citizenship
  and residence cases, and the Consiglio di Stato amounts raised by half
  (art. 1 c.27 L. 228/2012); the note records that the labour-court
  exemption only covers parties under twice the art. 76 threshold.
- Data refresh: FOI index for August 2026 (ISTAT, 16-09-2026: 103,7 in base
  2025=100 → 125,9 linked to 2015=100; official variations +3,4% / +4,8%,
  recorded without a Gazzetta reference until the comunicato is published).
  Verified against the sources on 2026-09-20: TEGM Q3 2026 (DM 23-06-2026,
  GU n.149; the Q4 decree is not out yet), late-payment rate H2 2026 10,40%
  (MRO 2,40% + 8, GU n.163 of 16-07-2026), legal rate 2026 1,60% (DM
  10-12-2025, GU n.289), IRPEF 2026 brackets 23/33/43 (L. 199/2025).
- Brocardi annotations for every act that is not a codice. `find_brocardi_url`
  matched the act name as a substring of the table labels, so a resolved
  `("decreto legislativo", 2001-06-08, 231)` never found `"(D.lgs. 8 giugno
  2001, n. 231)"` (46 of the 100 Brocardi sources had no page) and every
  `legge` fell into the first label containing the word — `art. 18 Statuto
  dei lavoratori` returned the massime of art. 18 legge fallimentare, legge
  Gelli those of L. 241/1990, legge Pinto those of the divorce law (13 wrong
  pages). The table labels are now parsed once into the identity (tipo,
  anno, numero) — `parse_brocardi_estremi` — and a citation matches only its
  own identity, by name for the labels without extremes (Costituzione,
  Preleggi, CCNL); a citation without a year matches only when the number is
  unique for that tipo; a Brocardi name paired with extremes resolves only
  if they are its own, and explicit extremes that contradict a codice's URN
  name the act themselves (`codice dei contratti pubblici` + 50/2016 is the
  abrogated code). The act date now travels from the resolver to the
  Brocardi client at every call site (`fetch_brocardi(..., data=)` from
  `cite_law`, `cerca_brocardi`, `fetch_law_annotations`, `mappa_orientamento`,
  `giurisprudenza_articolo`; `fetch_annotations`), which is what tells
  D.lgs. 81/2008 from D.lgs. 81/2015. No substring fallback remains: an act
  that is not on Brocardi says so. 97/101 of the sources listed at
  brocardi.it/fonti.html now resolve by name (was 35).
- Brocardi table completed against the fonti index: disposizioni di
  attuazione c.p.p. (D.lgs. 271/1989) and the abrogated codice dei contratti
  pubblici (D.lgs. 50/2016, reachable only by explicit citation — the name
  still resolves to D.lgs. 36/2023); D.L. 18/2020 "Cura Italia" reaches the
  page Brocardi files under its conversion law; the TU maternità label
  carries its estremi (D.lgs. 151/2001). Resolver aliases for the GDPR's full
  name, disp. att. c.p.p., and the quoted nicknames `Decreto "Sostegni"` etc.
  `scripts/generate_atti_denominati.py` reuses the same parser. New live gate
  `tests/unit/test_brocardi_codici_live.py` fetches every table URL and diffs
  the table against the fonti index.
- Data refresh (issue #36): FOI index for July 2026 (ISTAT, 12-08-2026: 103,1
  in base 2025=100 → 125,2 linked to 2015=100; official variations +2,8% /
  +4,3%) and the Gazzetta references for the June and July comunicati, both
  in GU n.201 of 31-08-2026 (26A04494, 26A04495). Art. 139 CAP
  micropermanenti amounts revalued by DM MIMIT 20 July 2026 (GU n.173 of
  28-07-2026, cod. 26A03765): first-point value €988,45, ITT €57,64/day,
  +2,6% on the April 2026 FOI, applying from April 2026 (`_vintage` now
  carries `aggiornato_al`; `docs/strumenti.md` follows). Shipped on the stable
  2.x line in v2.13.1.
- `scripts/refresh_data.py`: the monthly FOI append matched the first
  `"<year>": {` of the file, which since the 2025=100 rebasing belongs to
  `indici_base_2025`; the safety check refused the rewrite every month and
  the September cron opened issue #36 instead of a PR. The append is now
  anchored to its block, mirrors the published base-2025 value and moves
  `_vintage.copre_fino_a` (the one field it rewrites; the dead `_note`
  stamp is gone); the rewrite must equal the original plus exactly those
  edits.
- A helper module in `src/lib/` was classified as an *upstream service*.
  `upstream_clients()` returns `src/lib/<name>` unless the name is declared an
  in-process helper, and the ledger's own `_tables_open` was not. The 71 tools
  that import it (70 read-only calculations and one document generator) were
  counted as reaching an upstream service: the 70 moved into the report's
  "external" column and the page's open-world count went from 50 to 121, while
  every annotation stayed correct
  (`openWorldHint` reads the call graph instead and never saw the module as a
  client). Two readers of the same tree disagreed and nothing failed, which is
  the part worth fixing: `_ledger` and `_tables_open` are declared now, and a new
  `verify_lib_modules` check fails on any module under `src/lib` that is declared
  neither way -- a module is an in-process helper, a package is a client -- with
  `tests/unit/test_tool_annotations.py` sabotaging both directions.
- The call graph had no edge for a function handed over as a *value*.
  `_get_fonti()` in `giurisprudenza_unificata.py` returns a dict of the four
  jurisprudence implementations and the caller calls through it, so there was no
  `Call` node to follow and the walk stopped at the dispatch table.
  `cerca_giurisprudenza_unificata` searches Italgiure, CeRDEF, Giustizia
  Amministrativa and CGUE, and was annotated read-only *and* local -- which is
  what a host pre-approves without a click, and what a reviewer reads as "a pure
  lookup". A bare reference to an imported function now counts as an edge;
  exactly one tool changes classification (read-only local 168 -> 167, open world
  49 -> 50) and nothing else moves: no table attribution, no write, no cache.
  The same blind path was also the last live value in the pinned fixture -- the
  tool answered from the network, so its recorded expectation drifted with the
  Cassazione archive (the refinement count moved 3866 -> 3863 between two runs).
  It is out of the reproducible surface now, leaving 167 tools that are.
- Three import-preloaded tables were invisible to the audit: `_CODICI_TRIBUTO`
  binds through a subscript (`json.load(f)["codici"]`), `_CATALOGO` through a
  dict comprehension, `_PREAVVISO` through an annotated assignment, and the walk
  only recognised a bare `X = json.load(f)`. All three are now attributed to the
  tools that read them, and a load inside a function body is seen too.
- `preventivo_civile` and `modello_notula` estimated the contributo unificato
  from a hand-kept copy of the bands instead of the shipped table: the copy does
  not age with `contributo_unificato.json`, could diverge from what
  `contributo_unificato` and `decreto_ingiuntivo` answer without anything
  failing, and left the estimate with no vintage. Both now read
  `civile.cognizione` and declare the table (the numbers are unchanged).
- `verify_provenance` compared the declaration against a `datasets()` that
  already contained it, so "declares a table the code never reads" could never
  fire. The code-derived set is now `reads()` and the comparison is real in both
  directions; `tests/unit/test_tool_annotations.py` sabotages a copy of the tree
  to check the three cases (dropped declaration, invented declaration, renamed
  loader) actually fail.
- The stdio harness passed no `valore_causa` to `note_iscrizione_ruolo` — the
  parameter is optional *with a default of null* — so the recorded answer was
  the "valore_causa richiesto per il calcolo del CU" branch and the table the
  tool declares was never applied. The curated arguments now compute it.
- `start_server.sh` is PATH-independent. GUI hosts (Claude Desktop, Cowork,
  Freebuff) spawn MCP servers with launchd's bare PATH
  (`/usr/bin:/bin:/usr/sbin:/sbin`), which hides Homebrew, `~/.local/bin` and
  cargo installs: `command -v uv` failed there and the launch silently fell
  through to the venv path. The bootstrap now prepends the usual install
  locations and probes `uv` by absolute path as well.
- The venv fallback no longer trusts `command -v`. Each Python candidate is run
  and the first one that reports 3.10+ wins: an unaccepted Xcode licence turns
  the CLT `python3` into a shim that only prints a licence error, and it used
  to be selected. A cached venv is now reused only if its interpreter is 3.10+
  **and** imports every runtime dependency, so a half-built venv (deps added in
  a later release, interrupted install) is rebuilt instead of starting a server
  that dies on its first import. `MCP_FORCE_VENV=1` skips `uv` to exercise the
  fallback deliberately.

## [3.0.0-beta.1] - 2026-08-30

### Added
- Parliamentary sources module (`src/lib/parlamento/` + `src/tools/parlamento.py`,
  3 tools — total now 221): `cerca_ddl` (keyword search over bill titles, both
  chambers via dati.senato.it), `iter_ddl` (full bicameral navette from a fase
  number or idDdl, enriched with the Camera statoIter timeline and stampato
  PDFs from dati.camera.it), `ddl_su_norma` (pending-reform lookup for a given
  act, resolver-expanded, explicitly best-effort on titles only). Senato is
  queried via GET only (its WAF 403s POST) and title search uses plain
  `FILTER(CONTAINS(...))` because the WAF also blocks `bif:contains`
  expressions with quoted or/and operators. Navette suffixes handled
  (`S.562-B`, lowercase stralci `S.926-bis`, unified texts `S.93-338-353-B`).
  New egress hosts declared: `dati.senato.it`, `dati.camera.it` (SECURITY.md
  updated); scheda links to `www.senato.it` / `www.camera.it` are emitted,
  never fetched. Real-capture fixtures + 4 live guard-rail tests.

### Changed
- The pending-reforms rule in the `ricerca_normativa` and
  `mappatura_normativa` prompts is now GROUNDED: it used to say "report
  pending reforms" with no verifiable source behind it; it now requires
  anchoring every mention to `ddl_su_norma`/`cerca_ddl`/`iter_ddl` output —
  atto number, dated status and official scheda link — and states that no
  results never proves no reforms (titles-only search).

## [2.17.0] - 2026-10-20

### Changed
- Plugin first start: `server/bootstrap.py` (standard library only) answers
  Claude Code as soon as Python is available, installs the locked libraries in
  the background with no time limit, then hands the session to the real server
  and announces the tools (`notifications/tools/list_changed`). Before, the
  whole download had to fit in Claude Code's 30-second start limit, and on a
  slow network the server stayed "failed" until `/mcp` -> Reconnect. Tool calls
  made while it prepares get a plain «Legal IT si sta preparando» message.
- Data: TEGM table for Q4 2026 (DM MEF 28/09/2026, GU n. 227 del 30/09/2026).
- Plugin launcher: the MCP server starts with `uv run --frozen --project
  ${CLAUDE_PLUGIN_ROOT}/server`, from the exact versions pinned in the new
  `plugin/server/uv.lock` (FastMCP 3.4.9), in an environment of the plugin's own.
  `start_server.sh` is gone: no shell between Claude Code and the server, so
  Windows no longer needs Git Bash to start it. The system-Python fallback is
  gone too; `uv` is the one prerequisite. `plugin/server/pyproject.toml` is now
  the plugin's own project: Python 3.12 only (it always ran on 3.12) and no
  `dev` extras, which keeps the lock under the directory's 256 KiB file limit.
- Security audit: a weekly `pip-audit` of the versions pinned in the plugin lock,
  next to the existing audit of the library's resolved dependencies.
- Citation gate (plugin Stop hook): it runs in the same locked uv environment
  instead of a bare `python3`, which on Windows is usually the Microsoft Store
  alias (exit 9009) and turned every reply into a "Stop hook error".
- The plugin folder now meets the Claude directory's automated checks:
  `scripts/check_directory_readiness.py` replays them and runs in CI
  (job `directory-readiness`), replacing the tarball check.
- `.gitattributes` export-ignore rules removed (the directory refuses them); the
  GitHub archive of a tag contains the whole tree again.
- Skills for claude.ai upload are built outside the plugin folder and ship as one
  release asset, `legal-it-skills-X.Y.Z.zip`.
- `esporta-documento`: the .docx renderer no longer loads a style module from
  `~/.claude/skills`; it uses only its own code and the `docx` package. The PDF
  renderer runs in the plugin's locked environment.
- Plugin README: installation for Claude Code, first start, and a «Rete e dati»
  section listing everything the plugin downloads and every host it contacts.

### Fixed
- Security: `cryptography` 50 for every platform except Intel Macs (which have
  no wheels after 48.x and keep it). The plugin lock used to ship 48.0.1 to
  every machine, with PYSEC-2026-3552/3553/3554; the per-platform declaration
  makes the lock fork. `check_deps_sync.py` now tells per-platform entries apart.
- Starting the server from a folder that holds a `pyproject.toml` no longer syncs
  that project's `.venv` (`uv run --with` resolved the session's working
  directory as a project). The `.mcpb` launcher passes `--no-project` as well.
- FastMCP no longer asks pypi.org for a newer release at startup
  (`FASTMCP_CHECK_FOR_UPDATES=off` unless set): the server contacts only the
  hosts in `_egress.py`.
- Citation gate timeout: `15000` was read as seconds; it is now `120`.

### Removed
- `plugin/settings.json`: a plugin loads only `agent` and `subagentStatusLine`
  from it, so its `permissions` block never applied. Commands keep declaring
  `allowed-tools` under both tool prefixes.

## [2.16.1] - 2026-10-19

### Fixed
- Citation gate (plugin Stop hook): in Claude Code the result of a plugin tool
  reaches the hook as the FastMCP structured wrapper `{"result": "<markdown>"}`.
  The gate read it as a JSON object without `testo`, so every successful
  `cite_law()` counted as unverified and the hook nagged on every message that
  cited a norm. The wrapper is now unwrapped and its text judged like any other
  markdown answer (errors and a different article served still cover nothing).
- Server stdout: the "consulted undeclared online sources" diagnostic of the
  ledger (and the malformed `LEGAL_TODAY`/`LEGAL_NOW` notice) was printed on
  stdout, which is the JSON-RPC channel of the stdio transport. They go to stderr.
  Root cause of the warning: `src/server.py` installed the ledger without the
  committed online-source policy (`TOOL_SOURCES`), so every source looked
  undeclared; the policy is now passed, and `non_dichiarate` in the
  `fonti_consultate` block of `_meta` is empty for declared sources.
- Permission rules: tools installed through the plugin are named
  `mcp__plugin_legal-it_legal-it__<tool>`, not `mcp__legal-it__<tool>`, so
  `plugin/settings.json` and the `allowed-tools` of the slash commands matched
  nothing and every command asked for confirmation. Both prefixes are now listed
  (the old one stays right for a server registered by hand as `legal-it`).

### Changed
- Library installs (wheel, `uvx`) accept FastMCP 3.4 to 4.x: the `fastmcp`
  requirement is now `>=3.4,<5` (was `>=2.0,<4`, whose floor was already false: the
  server needs `FastMCP.enable`, added in 3.x). The code runs unchanged on FastMCP
  4.1.1 (full suite and wire output identical); CI now tests both majors. The
  Claude Code plugin and the Desktop `.mcpb` keep launching with `fastmcp<4` for now.
- The maintainer-only `/release` command is no longer shipped in the plugin: it
  moved to the repository-local `.claude/commands/release.md` (the plugin now
  has 9 slash commands).

### Docs
- README: `git` is a prerequisite of the Claude Code marketplace (not only `uv`);
  quit Claude completely (⌘Q) after installing `uv`; troubleshooting for
  `connection timed out after 30000ms` (retry from `/mcp`, or `MCP_TIMEOUT`) and
  `CONNECTION_CLOSED`; the Docker endpoint is `/mcp` (Streamable HTTP), not
  `/sse`; what `legal-it-plugin-X.Y.Z.zip` is for; claude.ai web/mobile has no
  supported connector.

## [2.16.0] - 2026-10-16

### Added
- `cookie-audit` skill: pixels and the tracking inside newsletters, as one repeatable
  mapping that needs from the client only what cannot be seen from outside.
  - Site: browser probe §5 classifies the calls already made to ~30 pixel and
    tracking vendors (Meta, TikTok, LinkedIn, Pinterest, X, Microsoft UET, Criteo,
    Google Ads/Floodlight, affiliate networks, the on-site scripts of e-mail
    platforms such as Klaviyo, HubSpot, Mailchimp, ActiveCampaign), with IDs, events,
    the NAMES of the user-data parameters (advanced matching), e-mail addresses in
    clear in URLs, consent signals (`gcs` decoded, TCF) and the pre/post consent
    split through a marker set when consent is granted. It also reads the pixel IDs
    written in the page code, `<noscript>` fallbacks, 1x1 images and the IDs exposed
    by the libraries, so an ad-blocker in the auditor's browser no longer hides them.
  - `scripts/inspect_container.py` (the existing `inspect_container.sh` now calls
    it) parses a GTM container or Google tag as data: vendor, IDs, events, user data
    and firing/blocking conditions of every tag, with a verdict read rule by rule
    (firing rules are alternatives: one rule that reads no consent decision — All
    Pages, Consent Initialization, a CMP event sent on every load — is enough for the
    warning), Consent Mode defaults (warning on
    `granted`), paused tags and server-side tagging. The Meta gallery template's
    `consent = true` is reported as what it is: an unconditional
    `fbq('consent','grant')`, not a filter.
  - `scripts/inspect_pixel_config.py` reads the configuration Meta publishes for a
    pixel: Automatic Advanced Matching and the form fields it reads, automatic
    events, the parameters Meta filters as unwanted. TikTok's loader returns the same
    flags for any pixel code, an invented one included, so it is deliberately not
    read: the evidence there is the request body (probe §6).
  - Newsletters: `scripts/inspect_newsletter.py` maps a `.eml` against the Garante's
    Guidelines on tracking pixels in e-mail (provv. 17 April 2026 n. 284, compliance
    due by 29 October 2026): sending platform from the headers, open pixels and
    images carrying identifiers, tracked links and the per-recipient IDs they carry
    onto the website, third parties, the recipient's address in any URL (clear,
    base64, hex, MD5/SHA-1/SHA-256), unsubscribe, the link to refuse ONLY the
    tracking (§6) and the notice (§4). With `--compare`, two copies sent to two test
    mailboxes decide whether the pixel is individual; one copy alone never claims it.
    Probe §7 reads the newsletter sign-up form (notice, consent wording, pre-ticked
    boxes).
  - References: `pixel-fingerprints.md`, `newsletter-tracking.md` (the repeatable
    path, the message types and the exemptions of the Guidelines, eight questions for
    the client), pixel and newsletter sections in `compliance-checklist.md`.
  - `generate_report.js`: pixel and tracker map (where, ID, data sent, moment,
    state) and a newsletter section, both optional.


## [2.15.3] - 2026-10-04

### Fixed
- `cite_law` on an article the act does not have answered with another
  article's text. Normattiva answers a URN naming a missing article with HTTP
  200 and the act's first article, and the HTML fallback took that page at face
  value: `cite_law("art. 99999 c.c.")` returned art. 1 of the R.D. 262/1942 ("È
  approvato il testo del Codice civile...") under the URL of art. 99999, with no
  warning, so a typo in the article number became a confident wrong citation.
  Existence is now decided by what identifies the article, never by the text
  alone: the act's Akoma Ntoso export (its article keys) or the number
  Normattiva gives the article it served (the numbered heading, or the "Art. N."
  head of a code article). A missing article is an error ("articolo N non
  trovato"); when neither check can be made the error says "verifica non
  disponibile" and no text is presented. The guard sits in `fetch_article`, so
  `cite_law` (markdown and json), `fetch_law_article` and `verifica_citazioni`
  share it; an article of a code that the AKN parser misses is still served
  when Normattiva's page names it. Numbers are compared in canonical form, so
  a real article whose suffix Normattiva spells another way ("2-quinquiesdecies"
  served as "Art. 2-quindecies", "2-sexiesdecies" as "Art. 2-sex-decies",
  "416-bis.1", "609-undecies") is still found; "non trovato" is said only when
  the number itself differs (99999 -> 1) or the act has no article with that
  number at all, and a different suffix on the same number is "verifica non
  disponibile", never "missing".
- `verifica_citazioni` on norms: a missing article is now `inesistente` (it was
  `verificata`), and a source that cannot be reached or cannot tell is `non
  verificata` (it was `non trovata`, which reads as "the norm does not exist").
- EUR-Lex: a missing article came back as the text "[Articolo N non trovato nel
  documento EUR-Lex]" under "Fonte: Eurlex"; it is now an error. A title that
  only starts with the number asked for ("Articolo 90" for art. 9) no longer
  matches.
- `cite_law(include_annotations=True)` no longer searches Brocardi, page by
  page, for an article that does not exist.
- Citation gate (plugin Stop hook): a `cite_law()` call covered the article it
  named whatever it returned. A call that ended in an error, or whose text is a
  different article, no longer counts as verification.

## [2.15.2] - 2026-10-01

### Fixed
- `cite_law` / `fetch_law_article` on acts with annexes (issue #47): in the
  Akoma Ntoso export of D.Lgs. 36/2023 the 233 articles of the Code sit in the
  body and each annex is a set of component documents. The parser let the
  largest annex replace the body, so artt. 1-44 of the Codice dei contratti
  pubblici returned the article with the same number of Allegato I.7 (art. 30
  "Cronoprogramma" instead of "Uso di procedure automatizzate"), under the URN
  of the Code's own article and with no warning. The body is now the default
  lookup; a component part replaces it only when it is the act's main text (the
  codici, where the body is the 2-3 article approving decree), and then the
  answer says so ("Testo tratto dall'Allegato ..."). Parsed acts cached on disk
  by the previous parser are discarded (`_CACHE_SCHEMA`).
- `cerca_pronuncia_costituzionale` without `anno_da`/`anno_a` searches only the
  current year, but when it found something the header read "Trovate N
  pronunce della Corte Costituzionale", a count that looks like the whole
  archive. The header now says "(solo anno 2026; specificare anno_da/anno_a
  ...)", as the no-results answer already did.

### Added
- Annexes on request. Italian acts: "art. 30 dell'allegato I.7 al D.Lgs.
  36/2023" or "allegato I.7 art. 30 D.Lgs. 36/2023" (also `article="allegato
  I.7 art. 30"` in `fetch_law_article`), read from the AKN export only — without
  it the tool answers with an error, never with the body article of the same
  number. EU acts: "Allegato III AI Act" returns the whole annex from CELLAR
  (`div#anx_N`), points and letters on their own lines; an unknown annex lists
  the available ones. `cite_law(formato="json")` gains the field `allegato`.
- Paged reading of long texts: `leggi_sentenza_cgue`, `leggi_sentenza`,
  `cerdef_leggi_provvedimento`, `leggi_provvedimento_amm`,
  `leggi_pronuncia_costituzionale`, `leggi_provvedimento_garante`,
  `leggi_delibera_consob` and `leggi_atto_gazzetta` take an optional
  `da_carattere` (default 1). Beyond each tool's cap the omitted text used to be
  unreachable: of CGUE C-203/22 (63,472 characters) the beginning and the
  operative part came back, the Court's reasoning (characters 25,001-61,449)
  could not be read at all. The first answer is unchanged, except that every
  note on a cut now says from which character to resume; `da_carattere=N`
  returns the window of the same text that starts there (`src/lib/_paging.py`).
- `leggi_sentenza_cgue` keeps the proposed answer of an Advocate General's
  opinion ("propongo alla Corte di ...") the way it keeps the operative part of
  a judgment: the opinions have no "Per questi motivi" and were cut before it.

## [2.15.0] - 2026-09-30

### Added
- Flag `Regime: PREVIGENTE` for tools that compute under a rule that no longer
  governs new cases (`src/lib/_regime.py`): declared once in the docstring
  (`Regime: PREVIGENTE — <casi residuali>; tool vigenti: <nomi>`), enforced by
  the tag `previgente` in `@mcp.tool(tags=...)` and by the wrapper
  `@previgente`, which puts a `regime_normativo` block in every answer. The
  audit renders the group into `tool_annotations.py` (`PREVIGENTE`), the
  middleware stamps `mcp-legal-it/regime` in the `_meta` of `tools/list` and of
  every result, and `LEGAL_PREVIGENTE=off` hides the group. Applied to
  `termini_183_190_cpc` (cause iscritte a ruolo prima del 28/02/2023) and
  `equo_indennizzo` (fatti anteriori al 06/12/2011). `verify_regime` fails the
  suite when the three declarations disagree or a successor is not a registered
  tool (`tests/unit/test_regime.py`).
- `tests/unit/test_cartabia_live.py`: live gate that reads artt. 171-ter, 189,
  190, 165, 166, 343, 347, 325, 327, 47, 281-undecies, 281-duodecies, 155, 7
  c.p.c., art. 1 L. 742/1969, art. 5 D.Lgs. 28/2010, artt. 161-bis c.p. e
  344-bis c.p.p., art. 545 c.p.c., artt. 9 e 13 DPR 115/2002 through `cite_law`
  and checks the day counts and amounts the tools hard-code (`-m live`).
- `docs/001_mcp-legal-it_AuditNormativa_RV_SAPG.md`: report of the legal
  currency audit of the 227 tools (Cartabia procedure, benchmark status,
  open items with confidence).

### Fixed
- Sospensione feriale (L. 742/1969) in every deadline tool: the days 1-31
  August are now skipped one by one, both forward and backward. The previous
  arithmetic added only the overlap of the raw period with August, so a term
  ending in August was extended by too little (20/07 + 30 days gave 07/09
  instead of 19/09), a backward term could land inside August (udienza 01/10,
  40 days before gave 12/08 instead of 22/07) and a term starting in August
  was one day late (10/08 + 30 gave 01/10 instead of 30/09). A term in months
  that includes August slides by 31 days; a dies a quo in August is deferred
  to the end of the suspension (prudential reading: 6 months from 31/08 end
  on 28/02). `scadenze_impugnazioni`, `termini_deposito_atti_appello`,
  `termini_memorie_repliche`, `termini_deposito_ctu` and `termini_183_190_cpc`
  now take `sospensione_feriale` (default True); `scadenza_processuale` takes
  it too (default False, it also serves substantive terms).
- `termini_processuali_civili`: `comparsa_conclusionale` and `replica` applied
  the abrogated art. 190 c.p.c. (60 and 80 days after the udienza di
  precisazione delle conclusioni) under a post-Cartabia label. They are now
  the art. 189 c.p.c. terms, 30 and 15 days before the udienza di rimessione
  della causa in decisione, plus `note_conclusioni` (60 days before) and an
  optional `giorni` for a shorter term assigned by the judge.
- `termini_procedimento_semplificato`: applied the rito ordinario terms (70
  days for the comparsa, 40/20/10 for the memorie) to the rito semplificato.
  Now: last day for the notifica (termini liberi of 40/60 days, art.
  281-undecies co. 2), costituzione del convenuto not later than 10 days
  before the udienza (co. 3), memoria integrativa and replica only if granted
  by the judge, within 20 and a further 10 days (art. 281-duodecies co. 3).
- `termini_deposito_atti_appello`: the appellant's costituzione is 10 days from
  the notifica of the citazione (art. 165 via art. 347 c.p.c.), not 30, and the
  appellee's comparsa is 70 days before the udienza (art. 166 via art. 347,
  post-Cartabia), not 20; both are computed from `data_notifica_citazione` and
  `data_udienza` when given.
- `scadenze_impugnazioni`: the regolamento di competenza has no 6-month term
  (art. 47 c.p.c.: 30 days from the comunicazione).
- `scadenze_multe`: the 30% discount for payment within 5 days comes from art.
  20 DL 69/2013 conv. L. 98/2013, not from L. 120/2010.
- `termini_separazione_divorzio`: the 6/12 months run from the comparizione
  dei coniugi in udienza (art. 3 n. 2 lett. b L. 898/1970), not from the
  omologa; note on the domanda cumulata ex art. 473-bis.49 c.p.c.
- `danno_biologico_micro`: the art. 139 co. 2 lett. a) and co. 6 Cod. Ass.
  formula applies the coefficient of the assessed degree to every point
  (valore punto x punti, as in the ministerial tables); the tool summed the
  values of the lower degrees and under-paid by up to a third at 9%.
- `danno_biologico_macro`: graded STIMATO with an explicit warning, because the
  bundled point values are not the tabella unica nazionale (DPR 13/01/2025
  n. 12) nor a court table and overstate high degrees; personalisation capped
  at 30% (art. 138 co. 3 Cod. Ass.).
- `contributo_unificato`: lavoro and previdenza follow art. 9 co. 1-bis DPR
  115/2002 (exempt up to three times the art. 76 threshold, otherwise 43 euro
  for previdenza and half the scaglione for lavoro; full amount in Cassazione)
  through `reddito_oltre_soglia_lavoro`; the untraceable lavoro-appello
  amounts are gone; tributario keeps the art. 13 co. 6-quater amounts in
  appello; new tipi `valore_indeterminabile`, `valore_indeterminabile_gdp`,
  `opposizione_decreto_ingiuntivo`, `opposizione_atti_esecutivi`; an unknown
  tipo is refused instead of silently priced as cognizione.
- `pignoramento_stipendio`: the minimo impignorabile delle pensioni (double
  the assegno sociale, at least 1.000 euro, art. 545 co. 7 c.p.c. as amended
  by art. 21-bis DL 115/2022) was reported but never deducted; `pensione=True`
  now applies the quota to the excess only, and `assegno_sociale_mensile`
  lets the caller pass the current year's amount.
- `decreto_ingiuntivo`: crediti di lavoro (`tipo_credito="retribuzioni"`) go
  to the tribunale in funzione di giudice del lavoro (art. 413 c.p.c.) whatever
  the value; the 10.000 euro threshold is attributed to art. 7 c.p.c.
  post-Cartabia; the opposizione (art. 641) and notifica (art. 644) terms are
  listed.
- Templates: attestazione di conformità and istanza di visibilità cite artt.
  196-quater ss. disp. att. c.p.c. instead of the repealed artt. 16-bis and
  16-undecies DL 179/2012; art. 127-ter c.p.c. applies from 01/01/2023;
  precetto without the abolished formula esecutiva and with the art. 617
  (20 days) / art. 615 (no term) distinction and the art. 480 co. 2 warning;
  relata PEC without the COA authorisation and with the art. 147 co. 3 c.p.c.
  perfection rule; dichiarazione del terzo cites art. 548 for the mancata
  dichiarazione; nota di precisazione del credito no longer cites art. 547;
  testimonianza scritta uses the art. 251 formula after Corte cost. 149/1995;
  `modelli_atti.json` notes (appello +50%, lavoro exemption, artt. 481/644,
  DM 150/2023).
- `fattura_professionista`: the rivalsa INPS 4% of the gestione separata is
  subject to ritenuta d'acconto, the contributo integrativo of a cassa is not;
  new `tipo="gestione_separata"`. `fattura_avvocato`: 2 euro bollo on
  forfettario invoices above 77,47 euro. `genera_quotazione_docx`: the CU of
  the esecuzione comes from the table (43 euro under 2.500).
- `prescrizione_reato`: the regime now depends on the date of the offence
  (ordinario until 02/08/2017; Orlando 03/08/2017-31/12/2019; from 01/01/2020
  the prescription stops with the first-instance judgment, art. 161-bis c.p.,
  and art. 344-bis c.p.p. improcedibilità terms apply, 3 years/18 months for
  appeals filed by 31/12/2024, then 2 years/1 year); `recidiva` drives the
  art. 161 co. 2 cap. The agent, prompt and docs that attributed these rules
  to D.Lgs. 150/2022 and to "Bonafede 2020-2024 / Cartabia dal 2025" are
  corrected.
- `composizione_negoziata`: the impresa minore thresholds of art. 2 co. 1
  lett. d CCII must all be met, not any one. `costi_costituzione`: 25% of
  cash contributions at incorporation of a SpA (art. 2342 co. 2 c.c.), SRLS
  exempt from diritti di segreteria (art. 3 co. 3 DL 1/2012).
  `scadenze_licenziamento`: the 180 days run from the impugnazione
  (`data_impugnazione`), the 60 days from the rifiuto della conciliazione
  (`data_rifiuto_conciliazione`), rito Fornero references removed (abrogated
  by D.Lgs. 149/2022). `calcolo_naspi`: the 3% reduction starts with the
  sixth month (art. 4 co. 3 D.Lgs. 22/2015).
- `decurtazione_punti_patente`: the 2024 road code reform is L. 177/2024, not
  D.Lgs. 36/2023 (the public contracts code).

### Changed
- Precision grades lowered to INDICATIVO, with the reason in the docstring, for
  tools whose figures cannot be traced to the decree they cite:
  `spese_mediazione`, `tariffe_mediazione`, `compenso_mediatore_familiare`
  (DM 151/2023 exists), `compenso_curatore_fallimentare`,
  `compenso_delegati_vendite`, `compenso_ctu`, `fattura_enasarco`,
  `spese_trasferta_avvocati`, `diritti_copia`, `copie_processo_tributario`,
  `danno_parentale`, `indennita_licenziamento`, `costo_lavoro`,
  `quorum_assembleari`, `test_crisi_impresa`, `compenso_occ`,
  `calcolo_maggior_danno`, `ravvedimento_operoso`.

### Fixed (benchmark phase 3, tools checked against official sources)
- leggi_pronuncia_costituzionale: the dispositivo and the epigrafe are always returned in full and only the reasons are cut to the 25,000-character budget; the whole-body cut dropped the dispositivo of most long sentenze (e.g. 194/2018, 1/1956, 153/2026), the part required by art. 18(3) and published under art. 30 l. 87/1953 (art. 136 Cost.).
- pronunce_cost_su_norma: with no years the search now runs from the current year down to 1956 (the massime bundle named 2001_2015 holds every year up to today, the tool stopped at 2015), and a reference that names the act type (Costituzione/Cost., legge, d.lgs., d.p.r., d.l., statuto, CEDU, TFUE, direttiva...) matches only parameters of that type instead of art. N of any act; a reference without the act now says so in the answer. Source: Corte costituzionale open data, massime archive (parametri[].descrizione).
- cerca_giurisprudenza_cgue: the corte filter compares the CELEX type through STR() (CELLAR stores it as xsd:string, so it returned nothing), one entry per decision instead of one per SPARQL row, official case number C-311/18 (two-digit year), Corte read from the CELEX type (CJ/TJ) instead of a CELLAR UUID, materia now narrows the search (AND) instead of widening it, title keeps the headnote with the norms applied, Official Journal notices (CELEX types CA/CB/TA/TB) no longer listed next to the decision, CC now labelled OPIN_AG and CO ORDER (were swapped).
- giurisprudenza_cgue_su_norma: the reference is normalised (art./artt./articolo -> 'articolo N', 'direttiva 2006/112/CE' -> '2006/112', GDPR -> 2016/679, CDFUE -> Carta dei diritti fondamentali) and searched as ANDed title terms, with article numbers matched as cited numbers (not prefixes) and no-break spaces read as spaces, so 'art. 101 TFUE' finds what 'Articolo 101 TFUE' finds; the corte filter now works (STR on the CELEX type); an empty reference is rejected.
- leggi_sentenza_cgue: over 25000 characters the text keeps its beginning and the operative part from the last 'Per questi motivi' (art. 87(i) Rules of Procedure of the Court, up to 8000 characters) with a note of the omitted range, instead of cutting the tail; the header carries the official case number, ECLI and date read from CELLAR by CELEX (best effort).
- ultime_sentenze_cgue: corte filter now returns the latest decisions of the Court or of the General Court (STR on the CELEX type), each decision once, with the official case number (C-369/25) and the court as CJ/TJ.
- cite_law: recitals of EU acts return the whole text (number cell + text cell of div#rct_N on CELLAR, Reg. (UE) 2016/679 recital 42), an act cited with the year only (L. 742/1969) gets its real date from the Normattiva page (eli:date_document) so `urn` is urn:nir:stato:legge:1969-10-07;742~art1 (null when unreadable, never 1969-01-01), and EU acts show the quotable EUR-Lex CELEX page as Fonte.
- fetch_law_annotations: the article text ('Testo dell'articolo', Brocardi div.corpoDelTesto.dispositivo, art. 2043 c.c.) is no longer dropped silently and the rubrica (h3.hbox-content) is reported; footnote calls are stripped from the text.
- cerca_brocardi: Cassazione references older than the Italgiure archive (a moving window, from 27/01/2021 penal and 17/02/2021 civil on 2026-09-28) are listed apart as 'Fuori archivio Italgiure' instead of being offered for leggi_sentenza; the article text and rubrica of fetch_law_annotations are included.
- fetch_full_act: short acts no longer fall back to the HTML walker (AKN export validated by structure instead of a 40,000-byte floor; L. 742/1969 export is 24,555 bytes) and the heading is the act's own title ('LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini processuali nel periodo feriale') instead of the sr-only portal banner; the URL carries the real act date.
- download_law_pdf: EU acts are downloaded from CELLAR by content negotiation (Accept application/pdf;type=pdfa1a with pdfa2a/pdf1x/pdfx fallbacks, Accept-Language ita) because EUR-Lex answers the PDF endpoint with a WAF challenge; the EUR-Lex CELEX PDF URL stays as the citable source.
- verifica_citazioni: the Italgiure archive start is read from the archive (moving window, 17/02/2021 civil and 27/01/2021 penal on 2026-09-28) instead of the fixed 2020; decisions before it, or not found in its first partly covered year (Cass. civ. sez. III n. 10579/2021), are 'non verificabile' instead of 'inesistente'; 'Cass. pen.'/'Cass. civ.' in the citation selects the archive and the cited section narrows the lookup (Cass. pen. sez. II n. 41994/2021 no longer compared with the civil SS.UU. namesake).
- Fixed `cerca_codice_tributo`: re-read src/data/codici_tributo.json on the AdE code tables of 23/09/2026 (erariali e regionali), 27/07/2026 (F24 ELIDE): 1840-1842 are now the cedolare secca (art. 3 D.Lgs. 23/2011), 1790-1792 the regime forfetario (art. 1 c. 64 L. 190/2014), 1550-1552 atti privati, 3843 acconto / 3844 saldo (ris. 368/E/2007); removed 1038 (suppressed from 2017, ris. 13/E/2016) and 1632 (non-existent); added 1668, 6035 and GA01-GA05; _vintage now declares its sources and date.
- rendimento_buoni_postali: rewritten on the CDP fogli informativi coefficients per series (new table buoni_postali, @sourced: ordinario TF120A250624 Tabella B, 3x4 con premio TF012A260724, dedicato minori TF118A260922 Tabelle A/C, historical 3x4 and 4x4 flagged not in placement); interest recognised only at the completed triennium/quadriennium, 12,50% substitute tax (art. 2 D.Lgs. 239/1996), bollo (0,20% above 5.000 euro portfolio, art. 19 D.L. 201/2011) reported apart; new parameters serie, eta_minore, valore_portafoglio_buoni.
- confronto_investimenti: substitute tax clipped at zero on negative yields (art. 45 co. 1 TUIR, art. 3 co. 1 D.L. 66/2014, art. 2 co. 1 D.Lgs. 239/1996), unknown tipo_tassazione refused instead of falling back to 26% (case and spacing of 'titoli_stato' normalised), durata_anni validated as integer >= 1, Vigenza line and model limits declared, new rendimento_netto_annualizzato_pct; field tipo_tassazione_riconosciuto removed.
- cerca_giurisprudenza_tributaria: already fixed by the 2.14.2 CeRDEF search-form rewrite (#46); no further change in this phase.
- cerdef_leggi_provvedimento: an unknown GUID is now reported as 'provvedimento non trovato o GUID non valido' (not_found, no retries) instead of a source error, a malformed GUID is refused before any request, and the docstring example is a real CeRDEF GUID.
- ultime_sentenze_tributarie: already fixed by the 2.14.2 CeRDEF search-form rewrite (#46); the publication delay is already declared in the docstring.
- get_italian_implementation no longer prints CELLAR's copy of the Gazzetta Ufficiale date as "Entrata in vigore" (D.Lgs. 177/2021: GU 27/11/2021, in force 12/12/2021; art. 73 co. 3 Cost., art. 10 preleggi): a date equal to the GU date is shown as "Data registrata in CELLAR (non è l'entrata in vigore)" with a pointer to Normattiva.
- get_eu_basis now finds acts whose CELLAR notice has no resource_legal_id_local (e.g. D.Lgs. 196/2003 -> directive 2002/58/CE, MNE 72002L0058ITA_117422) through a title fallback, and its no-result message no longer blames a correct number/year.
- elenco_misure_nazionali names the requested Member State in the heading and in the no-measures message ("Recepimento in Francia (FRA)", "Nessuna misura nazionale (GBR)"), keeps foreign act numbers ("Loi n. 2019-775") and labels non-Italian publications "Pubblicazione ufficiale" instead of "Gazzetta Ufficiale" (art. 29 dir. 2019/790).
- cerca_giurisprudenza_amministrativa no longer promises a date the portal search page does not carry (date of publication, art. 89 c.p.a., is read by leggi_provvedimento_amm); results give the citation form (n. 17/2021), name CdS sections P and C (Adunanza plenaria/generale) and report the portal total hit count.
- leggi_provvedimento_amm no longer hands PDF bytes over as full text (PDF-only provvedimenti get an explicit message with the official URL), always keeps the DISPOSITIVO (art. 88 c.p.a.) when a long text is shortened, and reports type, number and date of publication (art. 89 c.p.a.) from the official XML.
- CONSOB Bollettino: results that are not delibere (Comunicazione n. 13/25, Richiamo di attenzione n. 14/25, protocol-numbered comunicazioni, unnumbered Avvisi) keep their real type, full number and real page link instead of being labelled 'Delibera n. <n>' with a 404 link, and are deduplicated by href; docstring warns that the argomento filter follows the Bollettino taxonomy (abusi_di_mercato unused after 2017).
- Same CONSOB Bollettino fix (shared parser and formatter): unnumbered Avvisi and Orientamenti are no longer silently dropped, non-delibere carry their real type, number and link; docstring states the order is by publication date, descending.
- cerca_provvedimenti_garante: dates given as GG/MM/AAAA (as documented) are converted to AAAA-MM-GG, the only format the Garante portal's <input type=date> reads (any other format or a non-existent day is an explicit error instead of a silent empty result); tipologia is resolved to the portal's idsTipologia node ids ('provvedimento' = Provvedimenti 10533 plus its 25 descendant nodes, since the portal does not include children) instead of a local substring match on the leaf label; an unknown tipologia is an explicit error listing the valid values.
- leggi_provvedimento_garante: an unavailable DocWeb id (portal page 'Il contenuto o il file richiesto non e' disponibile') is now an explicit error instead of a pseudo-document, DocWeb links are absolute (https://www.garanteprivacy.it/...), the page toolbar is stripped from the text, and the docstring examples are corrected (9870832 is the Provvedimento of 30 March 2023 n. 112 on ChatGPT/OpenAI, not 'Linee guida AI'; 10000069 does not exist, replaced by 9874702, Provvedimento of 11 April 2023 n. 114).
- ultimi_provvedimenti_garante: tipologia is applied server-side through the portal's idsTipologia ('provvedimento' = Provvedimenti 10533 plus descendant nodes) over the whole archive instead of a local substring filter on the 15 latest cards, so 'provvedimento' now returns the latest provvedimenti; without a filter the heading now says 'Ultimi documenti pubblicati' (the unfiltered list mixes press reviews, news and provvedimenti); an unknown tipologia is an explicit error.
- leggi_marchio: an unknown ST13 (TMview HTTP 500 "Can't get trademark/design detail") is now reported as no_results ("ST13 inesistente o scheda momentaneamente non disponibile") instead of "tmview non raggiungibile", and that reply is no longer retried against the WAF.
- verifica_dpa_fornitore: the probe now sends Accept-Language en-US and the judge recognises Italian DPA titles and plural duty wording (art. 28 paras 3 and 9 GDPR set no language or title), so stripe.com gives dpa_dedicato instead of non_trovato; non_trovato is cached 14 days instead of 90.
- genera_report_fornitori: control characters forbidden by XML 1.0 s.2.2 (U+0000-0008, 000B-000C, 000E-001F) are stripped from every received text and counted in the result, instead of an unhandled IllegalCharacterError.
- Fixed cerca_gazzetta_ufficiale: a search with a single hit (the site redirects to the atto page) is no longer reported as 'no results', result pages are numbered from 1 so atti are no longer listed twice, the total also reads the 'Sono stati trovati N atti' form, and links carry the ELI segment of the atto's own series (sg, s1..s5, p2).
- Fixed leggi_atto_gazzetta: the atto page is read with the ELI segment of its series (s1..s5, p2), the header now reports estremi, oggetto and GU reference (h2/h3.consultazione), special-series text is read inline from vediMenuHTML, a malformed date gives a readable bad_input message, and 2a Serie speciale (UE) atti, which have no ELI page (HTTP 500), get an explicit answer pointing to the fascicolo PDF.
- Fixed scarica_pdf_gazzetta: the PDF URL uses the ELI segment of the requested series (.../s4/pdf for Concorsi, not .../sg/pdf which the site redirects to 'pdf non trovato') and a malformed date is reported as bad_input, not as source unreachable.
- Fixed sommario_gazzetta: the sommario now reads estremi, issuer and oggetto of each atto (two anchors per span.risultato, shared parser with the search results), the heading carries series, number and date, and the special series are requested with their own ELI segment (s1..s5, p2) instead of /sg.
- Fixed ultime_gazzette: RSS_CODE follows the official numbering of the special series (S1 Corte costituzionale, S2 Unione europea, S3 Regioni, S4 Concorsi ed esami, S5 Contratti pubblici), feed links keep their own series segment instead of /SG, and the 2a Serie speciale feed (pdfPaginato links, codes like 26CE2412) is parsed instead of being dropped.
- test_crisi_impresa: rebuilt on the vigente art. 3 co. 4 CCII signals (wages, suppliers, banks >= 5%, public creditors of art. 25-novies co. 1 with amounts and legal form), DSCR at 12 months and debts/assets ratio flagged as practice indices, corrected rubric.
- composizione_negoziata: access route now art. 12 co. 1 vs art. 25-quater co. 1 by the joint requirements of art. 2 co. 1 lett. d) CCII, missing requirement reported, art. 25-quinquies bars added, debt/turnover verdict replaced by the test pratico (art. 13 co. 2), effects of arts. 18, 20, 22, 24 restated.
- indennita_licenziamento: with tipo='reintegra' the ceiling is 12 mensilita whatever the seniority (art. 3 co. 2 D.Lgs. 23/2015, was min(anni x 2, 12)); reinstatement for employers under the art. 18 threshold is refused (art. 9 co. 1); docstring attributes C. Cost. 128/2024 to the objective-reason dismissal.
- indennita_preavviso: importo without intermediate rounding (art. 2118 co. 2 c.c., 150 days on 1.000 euro = 5.000,00); metalmeccanici C1_D1_D2 use the CCNL indemnity table in mensilita (0,33 / 0,67 / 1, Sez. IV Tit. VIII art. 1 CCNL 5/2/2021); Terziario reference corrected to artt. 251-252 and 256 TU CCNL 3/2/2026; 'quadri' accepted for studi professionali (art. 146 CCNL 16/2/2024).
- calcolo_naspi: below 13 weeks of contribution the outcome is 'non_spettante' with no amount (art. 3 co. 1 lett. b D.Lgs. 22/2015); the 3% monthly reduction starts on the sixth month, not the seventh (art. 4 co. 3); soglia and massimale moved to the new yearly table inps_parametri (circ. INPS 4/2026 par. 6), so from 2027 the stale 2026 values are refused.
- calcolo_sanzione_gdpr: art. 83(2) criteria now list letters a) to k) (k added), the range follows the EDPB Guidelines 04/2022 v2.1 method (new `gravita` parameter, seriousness bands par. 60, turnover adjustment par. 65-66) and the effective maximum of art. 83(4)-(6) is exposed as `massimale.effettivo_euro`; aggravating/mitigating multipliers stay a declared tool convention.
- valutazione_data_breach: the art. 34(3)(a) exemption from communicating to data subjects now applies only to confidentiality breaches with encryption (loss or alteration of encrypted data still requires communication, EDPB 9/2022 par. 76 and 79) and pseudonymisation no longer counts as encryption (par. 112); docstring declares the 10,000/100,000 data-subject steps as a tool convention.
- verifica_necessita_dpia: the transfer outside the EU no longer counts as a WP248 criterion (provv. Garante 467/2018); the DPIA is now also required by art. 35(3)(a)-(b) GDPR and by the items of the Garante's list (Allegato 1, art. 35(4)) on their own terms; lista_garante_italiano is the literal text of the twelve items; new parameters dati_biometrici, dati_genetici, rapporto_di_lavoro; esenzioni_dpia aligned to art. 35(1), (5), (10), (11).
- genera_dpa: clause 4.9 reproduces the last sub-paragraph of art. 28(3) GDPR (immediate notice of an unlawful instruction), 4.4 now imposes 'gli stessi obblighi' on sub-processors (art. 28(4)) and carries the art. 28(2) general-authorisation notice, ART. 6 cites art. 28(10); the art. 28(3) checklist is derived from the generated text instead of a fixed True dict.
- genera_dpia: residual risk is now computed after the declared mitigation measures (efficacia alta -2 levels, media -1, bassa 0; STIMATO) and prior consultation (art. 36(1) GDPR) is required whenever the residual level stays 'alto' or 'molto_alto', not only 'molto_alto'.
- genera_notifica_data_breach: art. 33(3)(b) accepts the DPO or another contact point (new punto_contatto), the contact section is labelled (b), art. 33(3)(a) records the approximate number of data records (new n_registrazioni), unofficial e-mail addresses removed from the heading (on-line procedure only, provv. Garante 209/2021), incoherent dates flagged, numbers formatted 1.200.
- genera_informativa_privacy now carries the legitimate interests (art. 13(1)(d) / 14(2)(b) GDPR), the nature of the provision of data (13(2)(e)), automated decision-making (13(2)(f) / 14(2)(g)), the specific source of the data (14(2)(f)) and the transfer safeguards with the way to obtain a copy (13(1)(f) / 14(1)(f)) via new parameters or visible [DA COMPLETARE] placeholders; the checklist no longer reports completeness when they are missing; sections are numbered progressively, 'incaricati' becomes 'persone autorizzate' (art. 29 GDPR, art. 2-quaterdecies D.Lgs. 196/2003) and the Garante contacts are protocollo@gpdp.it / protocollo@pec.gpdp.it.
- genera_informativa_cookie: the banner now warns that closing it with the X keeps the default settings (Garante cookie guidelines 10/06/2021, par. 7.1 i); analytics are equated to technical cookies only with masked IP, aggregate single-site statistics and no combination by the provider (par. 7.2), no longer depending on an extra-EU transfer (chapter V GDPR); scroll and 6-month re-proposal rules (par. 6.1, 6.2) are returned as implementation notes.
- genera_informativa_dipendenti: the ITL authorisation is cited to art. 4(1) L. 300/1970 (not 4(2)), tools of work to art. 4(2)-(3); the notice rests on art. 88 GDPR and artt. 113-114 D.Lgs. 196/2003 instead of art. 111-bis (CVs only); the health file is kept by the employer at least 10 years (art. 25(1)(e) D.Lgs. 81/2008), the 40 years being INAIL's (artt. 243(6), 260(4), 280(4)); 'incaricato' replaced by authorisation under art. 29 GDPR and art. 2-quaterdecies D.Lgs. 196/2003.
- Fixed scadenze_multe: the giudice di pace appeal now applies the August feriale suspension (art. 1 L. 742/1969, art. 7 D.Lgs. 150/2011, Cass. 30427/2022) and Saturday proroga (art. 155 co. 5 c.p.c.); prefetto and payment terms no longer roll over a Saturday (non-procedural terms).
- Fixed diritti_copia: paper copy rights now follow the fixed per-band amounts of DPR 115/2002 annexes 6 and 7 (D.I. 9 July 2021, +50% art. 4(5) DL 193/2009), urgent release triples the right (art. 270) instead of +50%, and the invented digital tariffs were replaced by the electronic transmission right of annex 8 (L. 207/2024).
- Fixed copie_processo_tributario: rights now follow DM 27 December 2011 annex 1 per-band amounts plus the EUR 9 conformity fee (art. 2(2)), with the invented per-page rates and the 50% urgency surcharge removed and unknown copy types rejected.
- Fixed codici_iscrizione_ruolo: keyword search now ignores accents and apostrophes, so 'responsabilita', 'responsabilita'' and 'responsabilità' return the same codes.
- Fixed note_iscrizione_ruolo: convalida di sfratto now halves the contributo unificato (art. 13(3) DPR 115/2002), labour cases can flag income above three times the art. 76 threshold (art. 9(1-bis)), and a movable execution without a value no longer silently prices EUR 43.
- gratuito_patrocinio: added diritti_personalita and interessi_in_conflitto parameters, counting only the applicant's own income (art. 76 co. 4 DPR 115/2002); previously the household income was always summed.
- pignoramento_stipendio: default assegno sociale updated to 2026 (546,24, INPS circular 153/2025, art. 545 co. 7 c.p.c.) and pignorabile rounded half-up on decimals (1,505 -> 1,51).
- sollecito_pagamento: BCE + 7 points for transactions concluded by 31/12/2012 (new data_contratto parameter, art. 5 D.Lgs. 231/2002 pre D.Lgs. 192/2012), explicit refusal beyond the rate table and for contracts before 08/08/2002 (art. 11), per-year divisor for agreed rates, first day of mora checked correctly, Italian number format and constitution in mora plus 40 euro lump sum (art. 6) in the letter.
- cerca_ufficio_giudiziario: no more wrong tribunal suggestions for comuni whose name contains a capoluogo's (Torino di Sangro, Bari Sardo...), tipo validated, ISTAT names of capoluoghi (Reggio nell'Emilia, Reggio di Calabria, Bolzano/Bozen) recognised; sources cited: R.D. 12/1941 tab. A as replaced by D.Lgs. 155/2012, D.Lgs. 156/2012.
- Fixed: modello_notula now pays each procedure on its own DM 55/2014 table (Tab. VIII monitorio, VI precetto, XVI esecuzione mobiliare, XVII presso terzi, XVIII esecuzione immobiliare) instead of the tribunal cognizione phases; contributo unificato of the executions from art. 13 co. 2 DPR 115/2002 (43/139/278); no art. 30 forfait on the precetto; new type esecuzione_presso_terzi; fasi values changed accordingly.
- Fixed: parcella_avvocato_civile (and preventivo_civile) above 32 million euro now applies the art. 6 co. 1 DM 55/2014 +30% for each further doubling instead of repeating the 16-32 million band.
- Fixed: parcella_stragiudiziale above 520,000 euro now applies the decreasing percentage of Tab. 25 (art. 22 DM 55/2014: 3% up to 2 million ... 0.25% above 22 million, on the whole value) instead of repeating the last band.
- Fixed: preventivo_stragiudiziale above 520,000 euro now uses the Tab. 25 decreasing percentage (art. 22 DM 55/2014) instead of the last fixed band; mediation is no longer claimed (Tab. 25-bis not implemented).
- Fixed spese_trasferta_avvocati: kilometric allowance is now one fifth of the fuel price per litre (art. 27 DM 55/2014) via the new prezzo_carburante_litro parameter, with optional hotel (+10%) and toll/parking amounts; default stays 0.30 euro/km (1.50 euro/l) and the trip allowance stays INDICATIVO.
- Fixed nota_spese: every line is rounded to the cent half-up on exact decimals (art. 5 Reg. CE 1103/97), so half-cent ties no longer depend on float bits (1000.10 with 15% SG now gives 1,459.27).
- Fixed calcolo_notula_penale: half-cent ties are rounded up on exact decimals (art. 5 Reg. CE 1103/97); 1,301.25 taxable now gives IVA 286.28 and total 1,587.53.
- Fixed fattura_avvocato: VAT, CPA and withholding are rounded half-up on exact decimals (art. 5 Reg. CE 1103/97); compensation 1,000.24 now gives IVA 228.86 and net 1,069.06.
- compenso_ctu: computes the DM 30/05/2002 tables (arts. 2, 3, 11, 13, 21, minimum 145.12 euro) and the art. 4 L. 319/1980 vacazioni at 14.68 euro (Corte cost. 16/2025, half vacazione rule, 4 per day cap) instead of market bands.
- compenso_curatore_fallimentare: applies the DM 30/2012 art. 1 min-max percentages per bracket on assets and liabilities (0.19-0.94% / 0.06-0.46%), the art. 4 minimum of 811.35 euro and 5% general expenses; drops the invented rates and the 405,656.80 ceiling; returns min, mean and max.
- compenso_delegati_vendite: applies the DM 227/2015 art. 2 fixed amount per phase (1,000/1,500/2,000 euro x 4), 10% general expenses, the 40% cap and the art. 3 movable-goods scheme (new tipo_vendita parameter) instead of the invented percentage scheme.
- fattura_enasarco: applies the annual commission ceiling per agency relationship (Enasarco RAI art. 5; 2026: 45,717 mono / 30,478 pluri), the year-specific rate (art. 4: 16.50% in 2019, 17% from 2020), the 23% withholding on 20% for agents with staff (art. 25-bis co. 2 DPR 600/1973) and half-cent rounding up; the legal reference no longer cites the non-existent D.Lgs. 303/1996.
- fattura_professionista: rounds every amount to the cent half-up on Decimal instead of binary float round(), which sent half-cent amounts (e.g. 22% x 1,000.24 = 228.855) one cent down.
- ricevuta_prestazione_occasionale: now computes the worker's third of the INPS Gestione separata contribution on the excess over 5,000 euro a year (art. 44 co. 2 DL 269/2003; INPS circ. 8/2026 row 09: 33.72%, 24% if insured elsewhere), supports the non-withholding client option and prior yearly earnings, and prints amounts in Italian format.
- spese_mediazione: rebuilt on DM 150/2023 (arts. 28, 30, 31, Tabella A with 12 brackets): avvio 40/75/110, first-meeting fee 60/120/170, +10%/+25% surcharge on the integration, one-fifth reduction for mandatory mediation, new momento/mediazione_obbligatoria/importo_tabella parameters; replaces the DM 180/2010 scheme.
- tariffe_mediazione: rebuilt on the DM 150/2023 Tabella A (12 brackets, min/max/mean), first-meeting fee and the four outcome scenarios with the art. 30 surcharges, VAT on the whole indennita'; replaces the DM 180/2010 figures.
- detrazione_coniuge: apply the art. 12 co. 1 lett. b) TUIR surcharges (10-30 euro between 29,000 and 35,200), truncate ratios to four decimals (art. 12 co. 4) and drop the wrong 4,000 spouse income limit (art. 12 co. 2 reserves it to children up to 24)
- detrazione_assegno_coniuge: apply art. 13 co. 5-bis TUIR (measure of co. 3: 1,955 up to 8,500, 700 + 1,255 x q, 700 x q) instead of the co. 5 amounts, with ratios truncated to four decimals (co. 6)
- detrazione_pensione: add the art. 13 co. 3 lett. a) minimum of 713 euro, the co. 3-bis surcharge of 50 euro (25,000-29,000) and ratios truncated to four decimals (co. 6)
- detrazione_lavoro_dipendente: add the art. 13 co. 1.1 TUIR surcharge of 65 euro (25,000-35,000), the co. 1 lett. a) minimums of 690/1,380 euro (new tempo_determinato parameter) and ratios truncated to four decimals (co. 6)
- fix(detrazione_figli): art. 12 c. 1 lett. c) and c. 4 TUIR: ratio truncated to four decimals, no deduction when the ratio equals one, and no 400 euro increase for disabled children (suppressed by D.Lgs. 230/2021), so 950 euro for every child.
- fix(detrazione_altri_familiari): art. 12 c. 1 lett. d) and c. 4 TUIR: ratio truncated to four decimals, no deduction when the ratio equals one, docstring aligned to the current text (only cohabiting ascendants).
- fix(detrazione_canone_locazione): art. 16 c. 1-ter TUIR: young tenants get 991.60 euro or, if higher, 20% of the rent capped at 2,000 (new canone_annuo parameter) instead of always 2,000.
- fix(calcolo_irpef): art. 13 TUIR: deductions computed on total income with ratios truncated to four decimals (c. 6, 6-bis), 65 euro increase for employees (c. 1.1), 50 euro for pensioners (c. 3-bis), self-employed deduction (c. 5, 5-ter), and years before 2024 refused instead of silently using 2026 brackets.
- Fixed acconto_irpef: single payment now stops at 257.51, since the first instalment (40%) must not exceed euro 103 (art. 17 c. 3 D.P.R. 435/2001); at 257.52 the two instalments apply (103.01 + 154.51). Vigenza now cites art. 11 c. 18 D.L. 76/2013.
- Fixed acconto_cedolare_secca: single payment now stops at 257.51 (first instalment not above euro 103, art. 17 c. 3 D.P.R. 435/2001, applied via art. 3 c. 4 D.Lgs. 23/2011); at 257.52 two instalments.
- Fixed ravvedimento_operoso: new optional data_scadenza; lett. b threshold is the dichiarazione deadline (31 Oct of the following year, art. 13 c. 1 D.Lgs. 472/1997), 1/7 without upper limit (lett. b-bis), interest at each year's legal rate day by day (art. 13 c. 2), single final rounding of the sanction, violations before 01/09/2024 refused (D.Lgs. 87/2024 art. 5).
- Fixed rateizzazione_imposte: interest on each instalment (AdE table 0.18% then +0.33% per month) instead of on the residual balance, instalments on the 16th of each month (art. 20 c. 4 D.Lgs. 241/1997), plan refused if it ends after 16 December (c. 1), 0.40% surcharge for a July start (art. 17 c. 2 D.P.R. 435/2001), rounding remainder on the last instalment. Precision lowered to INDICATIVO.
- calcolo_tfr: TFR net of the 17% (11% up to 2014) imposta sostitutiva on revaluations, revaluations excluded from taxable base and reference income (art. 19 c. 1 TUIR, art. 11 c. 3 D.Lgs. 47/2000), FOI never negative (art. 2120 c. 4 c.c.), 0.50% contribution deducted (art. 3 L. 297/1982), brackets of the year of cessation, art. 19 c. 1-ter deduction for fixed-term contracts.
- assegno_unico: without ISEE the minimum amounts apply (art. 4 c. 9 D.Lgs. 230/2021), +50% of the base for under-1 and (up to the upper ISEE threshold) 1-3 year-olds in 3+ child families (c. 1), increase for each child after the second (c. 3), adult children only up to 21 (c. 2), removed the unfounded 30% single-parent increase.
- imposta_registro_locazioni: concordato contracts taxed at 2% on 70% of the rent (art. 8 c. 1 L. 431/1998), single-payment option reduced by half the legal rate per year (note to art. 5 Tariffa, now D.Lgs. 123/2025).
- fix(imposte_compravendita): luxury dwellings (A/1, A/8, A/9) declared as prima casa are taxed at 9% registro, since the 2% rate is excluded by nota II-bis to art. 1 Tariffa I DPR 131/1986; precision lowered to INDICATIVO (bollo and tasse ipotecarie of VAT sales not included).
- fix(cedolare_secca): for concordato contracts the ordinary IRPEF comparison uses 66.5% of the rent (95% x 70%), applying the further 30% reduction of art. 8 co. 1 L. 431/1998; saving for a 12,000 rent at 23% goes from 1,650.00 to 795.00.
- fix(calcolo_imu): default rate for the A/1, A/8, A/9 principal residence is 0.5% (art. 1 co. 748 L. 160/2019) instead of 0.86%; 0.86% (co. 754) remains the default for other properties; A/1 rendita 1,500 gives 1,060.00 instead of 1,967.20.
- fix(calcolo_valore_catastale): removed the double 20% uplift (art. 1-bis co. 7 DL 168/2004) on A/10, C/1, D and E in compravendita, whose base multipliers 60 and 40.8 already include it (A/10 rendita 1,000: 63,000.00 instead of 75,600.00); added agricultural land (category T, reddito dominicale x 1.25 x 90, x 135 for IMU).
- fix(pensione_reversibilita): added the Tabella F safeguard clause (art. 1 co. 41 L. 335/1995), no cumulation reduction for households with minor, student or disabled children, and a year parameter with the INPS trattamento minimo for 2024, 2025 and 2026 (was fixed at 2024).
- fix(calcolo_superficie_commerciale): coefficients aligned to DPR 138/1998 allegato C (balconi and terrazze 30% up to 25 mq then 10%, garden 10% up to the main rooms surface then 2%, cantina and box 25% or 50% if communicating, pertinenze capped at half of the main rooms); added communicating flags; precision lowered to INDICATIVO.
- fix(spese_condominiali): reject millesimi above 1000; lift expense split over the sum of building heights as per art. 1124 c.c. (was normalised on a fixed 10 floors, giving shares above half of the expense); added portineria (90% tenant, art. 9 co. 2 L. 392/1978) and ascensore_straordinaria; ordinary lift costs are fully at the tenant's charge (art. 9 co. 1).
- danno_non_patrimoniale: micropermanent damage now applies the grade coefficient to each point (art. 139 co. 1 lett. a and co. 6 Cod. Ass.) instead of summing the lower grades, ITT is reported as temporary biological damage (art. 139 co. 1 lett. b) and no longer as patrimonial, and morale plus existential personalization is capped at 20% for lesions up to 9% (art. 139 co. 3); precision downgraded to STIMATO because the macro component is not the TUN (DPR 12/2025).
- equo_indennizzo: amount now follows Tabella 1 of L. 662/1996 (2 x tabular salary x category percentage 100/92/75/61/44/27/12/6), art. 49 DPR 686/1957 age reductions (eta_evento), art. 50 halving with privileged pension, category 9 = una tantum 3% (Tabella B); the invalidity percentage no longer enters the formula and the unsourced 1-5 pension flag is removed
- Fixed interessi_mora: transactions concluded before 1/1/2013 now use BCE + 7 points (art. 5 c.1 D.Lgs. 231/2002 original text, art. 3 c.1 D.Lgs. 192/2012) instead of +8; new contratto_ante_2013 parameter; explicit warning instead of a silent zero beyond the rate table.
- Fixed interessi_acconti: payments are now imputed first to accrued interest (art. 1194 c.c.), with imputazione='capitale' for imputation with the creditor's consent; an acconto on the final date is now deducted, and out-of-period or over-credit acconti are rejected instead of silently mishandled.
- verifica_usura: leasing strumentale 2025-Q1 TEGM corrected from 7.44 to 9.75 (MEF decree Allegato A, 1 Jan-31 Mar 2025, threshold 16.1875); threshold rounded half-up on Decimal with the four-decimal decree value in tasso_soglia_decreto_pct; unknown category or quarter now returns an error instead of silently using credito_personale or another quarter (art. 2 L. 108/1996).
- rendimento_bot: net yield now computed on the real outlay (price + substitute tax + commission, tax withheld at subscription, MEF BOT sheet), commission zeroed at or above par and capped so that the total price stays within par with a warning above the D.M. 15/1/2015 maximum, act/360 yields added, docstring Vigenza/Precisione updated.
- fix(calcolo_inflazione): FOI series 1990-2025 rebuilt from the ISTAT indices in their original bases and spliced with the official ISTAT coefficients (1,189, 1,141, 1,373, 1,071, Cst 1,0009); previous smoothed table gave errors up to 4.7 p.p. (e.g. Jun 1995-Jun 2005 20.35% instead of 24.96%).
- fix(calcolo_devalutazione): corrected through the rebuilt ISTAT FOI series (e.g. 10,000 euro of Dec 2023 back to Dec 2013 is 8,410.43 instead of 8,469.30; Jan 1990 4,109.19 instead of 4,773.63); docstring documents that the coefficient is not rounded to 3 decimals as ISTAT does.
- fix(interessi_vari_capitale_rivalutato): last-year segment now counts 1 January (art. 2963 c.c., dies a quo excluded only at the start: 365 days for 31/12/2024-31/12/2025, interest 505.41 instead of 504.02) and FOI indices corrected from the ISTAT series.
- fix(rivalutazione_annuale_media): annual means now come from the rebuilt ISTAT FOI series (2011 to 2013 gives 10,417.79 instead of 10,241.66; 2005 to 2025 14,244.27 instead of 13,509.23); docstring documents the unrounded-mean convention.
- fix(rivalutazione_mensile): FOI series 1996-2019 rebuilt from the ISTAT monthly series (SDMX, senza tabacchi); the old table was wrong in 1990-2019 and 1990-1995 were dropped for lack of a primary source.
- fix(rivalutazione_monetaria): FOI indices for 1996-2019 taken from the ISTAT monthly series with the official linking coefficients 1,373 (1995->2010) and 1,071 (2010->2015); e.g. 15/01/2015 index 99.44 instead of 99.7 and 12/2013 100.0 instead of 100.7.
- fix(rivalutazione_storica): annual means now computed on the corrected ISTAT FOI series (e.g. 2000->2020 coefficient 1.342967 instead of 1.237529); coverage starts in 1996.
- fix(rivalutazione_tfr): revaluation computed on the fund net of the substitute tax charged each year (art. 11 co. 4 D.Lgs. 47/2000), tax 11% up to 2014 and 17% from 2015 (L. 190/2014 art. 1 co. 623 and 625), variable part zero when the FOI index does not rise (art. 2120 co. 4 c.c.); FOI series corrected.
- fix(variazioni_istat): annual FOI variations recomputed on the corrected ISTAT series (2009 +0.68 instead of -0.65); first year of the series has a null variation instead of 0.0.
- fix(adeguamento_canone_locazione): the 12/24-month FOI variation is rounded to one decimal as published by ISTAT in the GU (art. 81 L. 392/1978) before applying the 75% cap of art. 32; e.g. 09/2025 gives 1.4% and 12,126.00 instead of 12,127.50.
- fix(lettera_adeguamento_canone): variation used in the letter rounded to one decimal as in the ISTAT communiques (art. 81 L. 392/1978), same as adeguamento_canone_locazione.
- Fixed aumenti_riduzioni_pena: the art. 67 co. 2 c.p. floor (not below a quarter with several ordinary attenuanti) is now applied; 12 months with four attenuanti of 1/3 gives 3 months instead of 2.37.
- Fixed fine_pena: liberazione anticipata (art. 54 co. 1 L. 354/1975) now counts only the semesters served before release instead of nominal days // 180; 24 months gives 135 days of detraction, not 180.
- calcolo_tempo_trascorso: years/months/days now follow art. 2963 c.c. (month completed on the matching day or the last day of the month), no more negative days (31/01->01/03 = 1 month 1 day); singular/plural in the description.
- calcolo_eta_anagrafica: age in years/months/days now follows the common calendar with the art. 2963 c.c. last-day-of-month rule (no negative days, consistent next birthday for people born on 29 February).
- codice_fiscale: accented vowels are folded to the plain vowel (Nicolò = NICOLO) instead of raising KeyError; non-Latin letters give an explicit error.
- decodifica_codice_fiscale: the century of the birth year is now the most recent one that does not put the birth date in the future (year 29 decodes to 1929, not 2029).
- decurtazione_punti_patente: art. 173 c.3-bis recidiva within two years now 10 points (new cellulare_recidiva entry and punti_recidiva_biennio), suspension ranges fixed (15 days-2 months, then 1-3 months), added art. 173 c.3 lenses at 8 points (L. 177/2024).
- prescrizione_diritti: a limitation period expiring on a Sunday or national holiday is extended to the next non-holiday day (art. 2963 c. 3 c.c.); new fields scadenza_naturale and prorogata_per_festivo.
- verifica_partita_iva: codice_ufficio now reads digits 8-10 (was digits 1-2), new matricola field; the office code list is still not validated.
- costo_lavoro: apprentice worker share 5.84% (INPS circ. 128/2012), +1% above the first pensionable band (art. 3-ter DL 384/1992, INPS circ. 6/2026), art. 13 TUIR deduction with the +65 euro and four-decimal ratios, L. 207/2024 art. 1 co. 4-6 (tax-free sum, further deduction), IRAP no longer added for permanent staff (art. 11 co. 4-octies D.Lgs. 446/1997), TFR net of the 0.50% (art. 2120 c.c., art. 3 L. 297/1982), INPDAI reference removed (art. 42 L. 289/2002).
- concordato_preventivo: the 20% threshold now covers chirografari plus privileged creditors degraded for incapienza (art. 84 co. 4-5 CCII), external-resources note aligned to the D.Lgs. 83/2022 text (10% of the available assets), partial payment of privileged creditors needs no consent (art. 84 co. 5), vote requirements per art. 85 co. 3, art. 109 co. 1 and 5 and art. 112 co. 2.
- compenso_occ: fee now computed as the range of art. 16 D.M. 202/2014 (attivo and passivo with the D.M. 30/2012 curatore percentages, reduced by 15-40%, general expenses 10-15%, cap of art. 16 co. 5), with no invented minimum; reference corrected to art. 2 co. 1 lett. t) CCII.
- fix(quorum_assembleari): quorums rewritten on artt. 2368-2369, 2479-bis co. 3, 2487, 2538 c.c.; new parameters convocazione and ricorso_mercato_capitale_rischio; closed s.p.a. needs more than half of the capital, s.r.l. constituted with half of the capital and no 2/3 rule, cooperatives defer to the atto costitutivo
- fix(soglie_organo_controllo_srl): obbligo_nomina no longer asserted on a single esercizio (art. 2477 co. 2 lett. c c.c.); optional previous-esercizio data and lett. a)/b) flags; limits attributed to art. 2-bis D.L. 32/2019
- fix(scadenze_societarie): verbale filed under art. 2435 co. 1 (not art. 2436), added the art. 2429 co. 1 communication to sindaci and weekend warnings
- Fixed analisi_base_giuridica: the matrix entry is now chosen from the processing (order execution rests on art. 6(1)(b) GDPR, employee video surveillance cites art. 4 L. 300/1970), art. 9(2) conditions follow the context (arts. 75 and 2-septies D.Lgs. 196/2003 for health, art. 2-sexies for public bodies), art. 22(2) lists all three exceptions.
- Fixed genera_informativa_videosorveglianza: the sign now carries the DPO contacts and the pointer to the full notice (EDPB 3/2019, Garante FAQ), the INL authorisation is cited at art. 4, co. 1, L. 300/1970 and art. 114 D.Lgs. 196/2003 is referenced.
- Fixed genera_registro_trattamenti: entry 1 now carries contacts of controller, joint controller, representative and DPO (art. 30(1)(a) GDPR), the legal basis is no longer labelled art. 30(1)(b), transfers are a field to fill in, and the docstring states the art. 30(5) threshold correctly (fewer than 250 employees).
- Fixed cerca_giurisprudenza_unificata: the all-words fallback for multi-word CGUE queries now calls the CGUE library with required_terms, so 'clausole abusive consumatori' reaches the 2022 judgments on directive 93/13/EEC.
- tassazione_atti: taxes judicial acts by content (DPR 131/1986 Tariffa I art. 8 lett. a-c with Notes I and II, art. 40, art. 41 co. 2), exempts causes up to 1,033 euro (art. 46 L. 374/1991) and mediation agreements up to 100,000 euro (art. 17 co. 2 D.Lgs. 28/2010), rejects negative values; new parameters contenuto, valore_causa, credito_soggetto_iva, mediazione, decreto_sostitutivo; precision lowered to INDICATIVO.
- attestazione_conformita: cites art. 196-novies (not 196-decies) for the copy of an analog act filed by the lawyer and drops the repealed artt. 16-bis and 16-undecies DL 179/2012 from riferimento_normativo.
- atto_di_precetto: template now states the date of notification of the title (art. 480 co. 2 c.p.c., null if missing), the full over-indebtedness warning with the OCC and the court competent for the execution (art. 480 co. 3).
- decreto_ingiuntivo: labour credits pay no contributo unificato unless income exceeds three times the art. 76 threshold (art. 9 co. 1-bis DPR 115/2002, new parameter reddito_oltre_soglia_lavoro), professional fees rest on art. 636 and art. 642 co. 2 c.p.c. (not co. 1), declaration of value added (art. 14 co. 2 DPR 115/2002), unknown tipo_credito rejected; contributo_unificato.json vintage note fixed (three times, not twice).
- dichiarazione_553_cpc: the third party declaration now states, in every variant, the debts and when payment or delivery is due, seizures and assignments, and the transmission by registered mail or PEC to the creditor (art. 547 c.p.c.); Vigenza cites art. 543 co. 2 n. 4 and clarifies that the art. 553 co. 1 declaration (art. 169-septies disp. att.) is a different act.
- istanza_visibilita_fascicolo: cites art. 76 co. 2 and art. 196-quater disp. att. c.p.c. instead of the repealed art. 16-bis DL 179/2012, rejects unknown motivo, addresses the Presidente/Giudice.
- nota_precisazione_credito: cite art. 553 c.p.c. (assegnazione di crediti) instead of art. 543 (form of the garnishment deed).
- note_trattazione_scritta: only istanze and conclusioni, no argumentative part or document production, recalls the substituting order and the peremptory term (art. 127-ter co. 1-2 c.p.c.).
- procura_alle_liti: anti-money-laundering clause now refers to arts. 17 ff. D.Lgs. 231/2007 (art. 4 repealed by D.Lgs. 90/2017), privacy clause rests on art. 6(1)(b) and 9(2)(f) GDPR instead of consent.
- relata_notifica_pec: relata now carries the content of art. 3-bis co. 5-6 L. 53/1994 (lawyer and party tax codes, source list, conformity attestation per art. 196-undecies disp. att., docket data); invalid dates return an error instead of raising.
- sfratto_morosita: adds the art. 660 co. 3 c.p.c. legal-aid warning, asks for an injunction to pay (arts. 658, 664) instead of a condemnation, validates amounts.
- testimonianza_scritta: form rebuilt on art. 103-bis disp. att. c.p.c. and art. 257-bis (truth warning per Corte cost. 149/1995, direct/indirect knowledge, signature after each answer, authentication by segretario comunale or cancelliere, missing fields added); empty question list returns an error.
- fix(genera_quotazione_docx): minimum fees are exactly half of the medio (art. 4 co. 1 D.M. 55/2014, no euro rounding), execution defaults come from Table 17 D.M. 147/2022 (165.50 + 283.50; 55 + 118 up to 1,100), PCT increase labelled 'up to 30%' per art. 4 co. 1-bis
- fix(genera_modello_atto): catalogue realigned to the vigente text: PCT attestations cite arts. 196-octies to 196-undecies disp. att. c.p.c. (DL 179/2012 arts. 16-bis and 16-undecies repealed by D.Lgs. 149/2022), no formula esecutiva (art. 475 c.p.c.), appellee 20 days (art. 347), art. 497/492-bis/636/5 L. 392/1978/152 c.p.p. warnings corrected, routing parameters and required fields aligned to the real tool signatures (new 'variante' field)
- Fixed costi_costituzione: SRLS now includes the concession tax (EUR 309.87, art. 3 co. 3 DL 1/2012 does not exempt it; total 629.87), SAS/SNC include the EUR 90 Registro Imprese fee (DM 17/7/2012), legal references corrected.
- Fixed competenza_giudice: condominio is no longer treated as reserved to the Tribunale (art. 7 co. 1 and co. 3 n. 2 c.p.c.), art. 9 co. 2 exclusive matters and immovables go to the Tribunale, unknown matters are refused, crisis law follows art. 27 CCII, thresholds dated 31/10/2027.
- Fixed verifica_mediazione_obbligatoria: exact/alias matching with accent normalisation instead of substring (rete, contratto di rete, responsabilita medica now recognised; generic or empty input no longer matches), exclusions now the eight letters of art. 5 co. 6 D.Lgs. 28/2010, urgent measures (co. 5) no longer listed as an exclusion.
- interessi_legali: the 10% saggio legale starts on 16/12/1990 and not on 16/04/1990 (art. 1 L. 353/1990, art. 92 co. 1 same law); the correction also applies to interessi_acconti and calcolo_maggior_danno, which read the same table.
- tasso_alcolemico: the sanction bands follow the wording of art. 186 co. 2 D.Lgs. 285/1992 ("superiore a 0,5", "non superiore a 0,8" and "1,5"): the exact thresholds 0.5, 0.8 and 1.5 g/l fall in the lower band.
- interessi_corso_causa: the mora rate of art. 1284 co. 4 c.c. applies only to proceedings begun from 11/12/2014 (art. 17 co. 2 DL 132/2014 conv. L. 162/2014); earlier domande run on the legal rate of art. 1284 co. 1.

## [2.14.2] - 2026-09-28

### Added
- `stato_server()`: the diagnostics tool that tells the caller WHAT it is
  talking to — package version of the running code, active tool count after
  the `LEGAL_PROFILE` filter, pinned clock, cache switch and directory,
  hostname. Modeled on the `get_quota_status` / `check_capabilities` pattern
  of the Scopus MCP servers; the declared total is derived from the audited
  annotation policy, so it cannot drift into a second handwritten count.
  Surface is now 228 tools (210 read-only, 170 local-only).
- `server.json`: the server declares its own identity
  (`io.github.capazme/mcp-legal-it`, stdio transport) in the official MCP
  Registry schema, with the environment variables every host can pass
  (`LEGAL_PROFILE`, `LEGAL_CACHE`, `MCP_CACHE_DIR`, `LEGAL_TODAY`, `LEGAL_NOW`).
  The README carries the `mcp-name:` marker so aggregators can verify the
  package/manifest association once a public distribution channel exists.

### Fixed
- CeRDEF (giurisprudenza tributaria) works again and a failure of the source
  no longer reads as "no results" (#46). The portal changed its advanced
  search form and its XML: it answered every request of the old client with
  an HTTP 200 error page ("Ambito di ricerca non valido"), which the client
  read as zero results, so `ultime_sentenze_tributarie` reported "nessuna
  sentenza" to every call (and the weekly digest dropped the tax section),
  `cerca_giurisprudenza_tributaria` found nothing on any query, and
  `cerdef_leggi_provvedimento` returned an empty text as a success. The
  client now posts the current form (field names and option values verified
  against the live form by a unit test on a saved copy and by a live test),
  reads the new result and detail XML, follows the portal's own paginator,
  decodes the portal's JS escapes (`\à`, `\'`, `\u200B`) and keeps every
  cited norm inside its sentence (the portal links each citation, which used
  to split the text at every one of them). An error page,
  an unrecognised payload (a result list or a detail without the elements the
  client reads) or an empty list the portal's own counter does not confirm
  raises a `source_error` that every tool renders as `**Errore**` (the unified
  search labels it "errore", not "0 risultati"); an unknown filter is refused
  before any request; an unknown GUID is reported as such, not as the source
  being unreachable.
- `ultime_sentenze_tributarie` covers the decisions issued in the last twelve
  months (by issue date: CeRDEF exposes no publication date): the portal
  refuses a search without criteria, and ordering a whole CGT group by date
  takes 20-100 seconds. `ente="cgt_primo_grado"` is served by the group of all
  tax courts filtered client-side (the portal has no first-instance group), so
  `cerca_giurisprudenza_tributaria` requires `data_da` with it; the filter
  reads at most 250 items and, when it stops with items left unread, says so
  instead of reporting fewer results (or none) as if they were all. The
  `codice` criterion no longer exists on the portal; `parole_adiacenti` and
  `operatori_logici` are new.

## [2.14.1] - 2026-09-24

### Fixed
- `LEGAL_PROFILE` works again on FastMCP 3. FastMCP 3 removed the
  `include_tags` attribute, so the assignment in `server.py` was a silent
  no-op and every profile exposed all 227 tools (through 2.14.0). The
  profile is now a visibility transform (`enable(tags=..., only=True)`) with
  prompts and resources re-enabled; `tests/unit/test_profiles.py` guards it
  and `install.py` carries the real per-profile counts.
- `package_version()` reports the checkout's version, not stale editable
  metadata: an editable install froze `importlib.metadata` at the version of
  whatever branch was checked out when it was installed, so the server could
  declare 2.14.0 to MCP clients from a tree that had moved on, and `test_cli`
  failed every time it did. The `pyproject.toml` next to the package now
  wins; metadata is the fallback for an installed wheel, where no pyproject
  ships.

### Changed
- Grounding rules normalized: the six agent skills carried seven diverging
  restatements of the same Legal Grounding rule -- they now share one
  canonical wording. The server's OUTPUT convention adds the provenance
  clause (`dati_applicati` with their vintage, `mcp-legal-it/fonti_consultate`
  from `_meta`), so every host surfaces where an answer's numbers come from.
- Documentation aligned with the shipped 2.x surface (227 tools, 34 modules,
  23 skills, 10 slash commands, 6 agents): tool table derived from the code,
  the working profile mechanism with real counts, the provenance, precision,
  cache and clock layer in `docs/architecture.md`, deployment and testing
  pages regenerated, manifests and the marketplace snippet re-tallied.
- `.gitignore` keeps AI-assistant and host-app context artifacts
  (`AGENTS.md`, `CLAUDE.md`, `.codex/`, `.cursor/`, ...) out of the
  repository.

## [2.14.0] - 2026-09-20

### Added
- `verifica_dpa_fornitore(dominio)`: probes a supplier's site on a fixed list
  of conventional paths for a published art. 28 DPA, judges the HTML or PDF
  it finds against GDPR markers and caches the determination for 90 days
  (`src/lib/dpa_probe/`; the hand-maintained DPA whitelist is gone). The probe
  is the one tool that contacts a host chosen by the caller, so it is fenced:
  public registrable names only (no addresses, ports, local or reserved
  names), every name resolved and refused when any address is not public,
  the same check on every redirect, the consult declared in
  `fonti_consultate` and the cache under `LEGAL_CACHE`. `SECURITY.md`
  documents the exception.
- TMview (EUIPO/TMDN trademark database) as a new source — module
  `src/tools/tmview.py` with 3 tools (218 → 221): `cerca_marchi` (search across
  UIBM, EUIPO, WIPO and ~75 national offices with office/Nice-class/status
  filters), `leggi_marchio` (full record by ST13: owner, representatives,
  goods and services per Nice class, publications), and
  `verifica_anteriorita_marchio` (preliminary prior-rights screening that
  separates identical from similar marks, with an explicit disclaimer that it
  does not replace a professional availability search). The client
  (`src/lib/tmview/`) talks to TMview's public JSON API with browser-like
  headers, a session warm-up request and a minimum interval between calls to
  coexist with the site's F5 anti-bot gate; a challenge response surfaces as
  a clear "retry in a minute" error instead of garbage output. New egress
  host `www.tmdn.org` declared in `src/lib/_egress.py` and SECURITY.md.
- `verifica_citazioni(..., formato="json")` and `cite_law(..., formato="json")`:
  structured output for programmatic clients (LibreLex-IT). Markdown output
  unchanged.
- Console entry point `mcp-legal-it` (`src.cli:main`), so the server starts
  with `uvx --from git+https://github.com/capazme/mcp-legal-it@vX.Y.Z mcp-legal-it`.
- The server now declares its package version to MCP clients
  (`serverInfo.version`).
- The refusal series as a picture: `verbale_mensile` and the CLI report carry a
  `grafico` block now -- one bar per month, scaled to the window's maximum,
  the zero mark for a silent month, the current month marked -- so "is this
  month worse than the last one?" reads at a glance in `/verbale` too, from
  the same data the table mirrors.
- Tool annotations: all 221 tools now declare `readOnlyHint` / `openWorldHint`,
  so hosts that pre-approve safe tools (Claude Desktop, Freebuff) can offer the
  204 read-only lookups without a per-tool click, while the 17 that write a file
  stay behind an explicit approval. The classification is audited from the call
  graph — decorated function → helpers → imported clients, looking for
  `open(..., "w")`, `write_text`, the document constructors and mutating HTTP
  verbs. It lives in `src/tool_annotations.py`, generated by
  `scripts/audit_tool_annotations.py` (`--check` fails the suite on drift,
  `--json` prints the per-tool evidence); a middleware stamps it on
  `tools/list`, and `tests/unit/test_tool_annotations.py` fails if a tool is
  renamed out of the policy.
- The 12 cache writers are flagged as such (`CACHE_WRITES`): their only write
  refreshes `${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}` (parsed acts, Brocardi
  article URLs, Consulta massime), which is worth telling apart from the 5 tools
  that produce a document.
- `LEGAL_CACHE=off` (also `no`, `false`, `0`, `none`, `disabled`) keeps the
  server off the disk entirely: the cache directory is then never read and never
  created, and the caches live in memory for the life of the process (the parses
  still work, they are just not persisted). `src/lib/_cache.py` is the single
  module that reads the switch and resolves `MCP_CACHE_DIR`; `MCP_CACHE_DIR`
  alone only relocates the files.
- The cache side is audited too. `scripts/audit_tool_annotations.py` declares
  every cache location (`CACHE_LOCATIONS`) and fails when a module starts
  resolving a cache directory without being declared, when a declared cache
  loses its literals, or when a cache writer stops consulting the switch; the
  generated inventory is `docs/cache-inventory.md` (location, files, retention,
  writer module and the tools that can touch it), compared by `--check` just
  like the annotation policy. `tests/unit/test_cache_switch.py` proves the
  switch, including that with `LEGAL_CACHE=off` not even the directory appears.
- The wall clock has one reader (`src/lib/_clock.py`) and `LEGAL_TODAY` /
  `LEGAL_NOW` pin it. Several tools are "as of today" by design (prescriptions,
  deadlines, the current IRPEF brackets, the running year for the Consulta
  dumps): without an override they cannot be reproduced, so a test on their
  numbers could either rot with the calendar or skip the most interesting half
  of the surface. The audit fails on any `date.today()`/`datetime.now()` call
  outside that module, so a new tool cannot opt out of being pinnable.
- `tests/unit/test_golden_calcoli.py` freezes what the local read-only tools
  answer (167 of them) in `tests/fixtures/golden/calcoli_locali/` (arguments + expected answer,
  pinned to `LEGAL_TODAY`/`LEGAL_NOW`, truncated at 4000 characters where an
  answer is a whole document). The reference is **one file per set of data
  tables**, derived from the code (`@sourced(...)` declarations plus the
  module-level tables each tool's reachable code reads, derived constants
  included): `indici_foi`, `indici_foi+tassi_legali`, `tabella_danno_bio`,
  `nessuna_tabella` (104 pure algorithms) and 20 more. A refreshed table or a
  mistyped bracket fails with the dataset named first — changing a single FOI
  index reports "tables involved: indici_foi (12/12 tools), tassi_legali
  (3/12)", lists only the two affected group files, and tags every changed tool
  with the tables it read. Regenerate deliberately with `GOLDEN_UPDATE=1 pytest
  tests/unit/test_golden_calcoli.py`; the reference is also checked for being
  pinned, complete, partitioned by table (no tool twice, none missing), free of
  error payloads and free of local paths, and each answer's own `dati_applicati`
  footer must agree with the group it is filed under.
- The stdio harness the runtime tests share now lives in
  `tests/unit/mcp_harness.py`, and its argument generation fills object-shaped
  parameters (rows like `eredi`, `acconti`, `voci`, `rischi`) and picks dates by
  role (`data_inizio`/`data_fine`, `anno_partenza`/`anno_arrivo`) instead of one
  value for every `data_*`. Every local read-only tool now answers with a real
  result, where 12 previously came back with a validation error.
- `scripts/tool_report.py` renders the surface as a single self-contained page
  (`docs/tool-report.html`): the 221 tools split into 167 read-only local, 37
  read-only external, 12 cache refreshers and 5 document generators, with the
  service each external tool reaches, the cache directory each writer can touch,
  and — as of the change below — the tables each one applies and whether their
  vintage needs acting on. It is built from the same audit as the annotations, so the page and the
  policy cannot disagree.
- `tests/unit/test_read_only_contract.py` proves the read-only claim at runtime:
  the server is started with its own `HOME` and `MCP_CACHE_DIR`, every local
  read-only tool is called with arguments generated from its input schema,
  and the sandbox, the checkout and the real MCP cache are fingerprinted before
  and after — any file created, deleted or modified fails the test. All of them
  answered and nothing changed.
- `tests/unit/test_provenance_datasets.py` demonstrates the table → tool mapping
  instead of re-deriving it: a table is perturbed in a throwaway copy of the
  server and the answers are compared with a clean baseline, in both directions.
  An answer that moves with a table whose footer does not name it is a silent
  reader; an answer that names a table and does not move with it is a decorative
  footer. The caller set comes from the tools' own footers, the controls are
  tools that read other tables — the two oracles are independent of the audit.
- Every table a tool reads now says so *and* says how current it is, including
  the tables preloaded at import: six tools that answered in silence
  (`cerca_codice_tributo`, `genera_modello_atto`, `lista_categorie_atti`,
  `indennita_preavviso`, `costo_lavoro`, `ravvedimento_operoso`) carry their
  `dati_applicati` footer, which is how the unverified vintages of
  `preavviso_ccnl` and `contributo_unificato` now reach the reader as an explicit
  warning instead of not reaching them at all.
- The audit fails when a shipped table is applied by no tool: either it is dead
  data or its reader is a load the walk cannot follow, and in the second case
  the tool answering from it reports no vintage. That check is what found
  `codici_tributo`, `modelli_atti` and `preavviso_ccnl`.
- Every tool call now declares, in its result `_meta` under
  `mcp-legal-it/opened_tables`, which hand-maintained tables it *actually* read:
  observed, not derived. `src/lib/_ledger.py` wraps the table-carrying constants
  (`src/table_bindings.py`, generated by the audit) in dict and list subclasses
  that note their dataset when read, so a call that opens no table — a pure
  algorithm — declares nothing, and one that applies two tables says so. The
  wrappers are shallow and transparent: nested values stay plain, so `json.dumps`,
  `==` and the host's serialization see the same objects as before.
- The `dati_applicati` footer is written from what the call read rather than
  from the `@sourced(...)` declaration: `_data.effective()` intersects the two,
  so a tool that branches between tables names the branch it took. Called with
  the required parameters alone, `note_iscrizione_ruolo` declares
  `codici_ruolo` + `contributo_unificato` but applies only the first, and that
  is now what its answer says. The observation is only worth as much as its
  coverage, so the two tables a tool reads inside a *function body*
  (`mediazione_obbligatoria` in `procedura_civile`, `tegm` in `verifica_usura`)
  now go through the accessor `_data.load(name)`, which records the read; the
  audit recognises the same call as a read, keeping the static map and the
  observation describing one act. Rendering a vintage goes to the cached `_read`
  underneath instead, because a footer that counted as applying the tables it
  describes would make every observation equal its declaration and no answer
  could ever narrow. The declaration remains the fallback for what cannot be
  wrapped (a table reached through a scalar computed at import), and with the
  two in-body reads observed it is now the *only* fallback left: no tool in the
  local surface answers from a table the ledger could not see.
- An expired covered period and an unverified provenance are structured fields,
  not only a line at the end of an answer. A dict answer carries `avvisi_dati`
  next to `dati_applicati`, every answer carries
  `mcp-legal-it/data_warnings` in its result `_meta` -- the only channel a tool
  returning a string has -- and both are the same sentence as the footer, so the
  two cannot drift. The states are told apart: `scaduta` means the covered
  period has ended (`tassi_legali` from 2027-01-01; `indici_foi` past its own
  period *plus* the 92-day tolerance for ISTAT publishing in arrears, so
  2026-09-30 and not 2026-06-30), `non_verificata` means nobody has established where the table
  comes from (`contributo_unificato`, `comuni`, `codici_ateco`, and 11 more), and
  a table that is neither raises nothing -- so the field means something
  whenever it appears, instead of being a list everybody learns to ignore.
  Which tables a warning is about follows the same observation as the footer,
  not the declaration.
- A stale or unsourced table now changes the answer, not only the footer.
  Every tool already declares a grade in its own docstring (`Precisione:
  ESATTO|INDICATIVO|STIMATO`, 144 of them, parsed from the line the calling
  model reads), and `src/lib/_precision.py` decides what the vintage does to
  that claim: an exact claim resting on a table nobody sources is **withdrawn**
  -- the tool returns `errore: "dati_non_affidabili"` with no figure at all,
  naming the table, its state and the file that would unblock it -- while an
  indicative one steps down to `STIMATO` and says so in `precisione`, in the
  answer body and in `mcp-legal-it/precisione` in `_meta`. An expired table is
  the milder case, because coverage is not provenance: it stops an answer
  anchored to today (the tool read the clock, observed per call through
  `_clock.consulted()`) and only downgrades one about a period that has already
  closed. With the shipped tables that is 6 refusals (`codice_fiscale`,
  `imposte_*`, `indennita_preavviso`, ...) and 4 downgrades
  (`ricerca_codici_ateco`, `cerca_ufficio_giudiziario`, ...), and
  the audit fails when a tool applies a table without declaring a grade, or
  declares a word `_precision.py` does not know -- an unknown grade would be
  read as the strongest claim. `tests/unit/test_precision_policy.py` covers both
  states on the wire and at the seam.
- A refusal is negotiable, not final. Every tool that reads a table now also
  takes `accetta_precisione` (`INDICATIVO` or `STIMATO`), declared in its
  signature and documented in the `Args:` block like any other parameter: the
  caller names the grade it will settle for, the answer is given at that grade,
  and both the body (`precisione.accettata`) and `mcp-legal-it/precisione` in
  `_meta` say the acceptance is what allowed it. The claim itself is not for
  sale -- asking for `ESATTO` on a table nobody sources is refused, and the
  refusal carries `concedibile` so the retry is a decision -- and no acceptance
  unlocks an expired table under a figure about today: a stale rate is wrong, not
  imprecise, and the refusal says `negoziabile: false` instead of offering a
  grade that would not help.
- Two tools can do without the table altogether, which is the other half of the
  answer. `@sourced(..., alternativa="parametro")` names the parameter that
  provides what the table would have: `codice_fiscale` accepts the catastal code
  (`codice_catastale`, so the algorithm is exact on an input instead of a lookup)
  and `indennita_preavviso` accepts the notice period (`giorni_preavviso`, which
  is the part of a CCNL table that no vintage can ever be right about, since the
  contracts get renewed). Such a call reads no table at all, so nothing about a
  vintage enters the answer: the footer is empty, no warning is emitted, and the
  answer says `dati_forniti_dal_chiamante: {parametro, al_posto_di}` rather than
  leaving the reader to guess what backs the number. The middleware knows the
  same map (`TOOL_ALTERNATIVES`, generated) so it does not fall back to the
  declaration and flag a table the call deliberately did not open.
- `scripts/update-data.py` says what each unverified table costs, and it is no
  longer a warning: the per-table block now lists the tools that apply it with
  their declared grade and whether they refuse or merely degrade, derived from
  the audit and the same rule the server runs. The eight `da_verificare` tables
  block seven tools outright (`comuni` two, `imposte_successione` two,
  `contributo_unificato`, `preavviso_ccnl`, `violazioni_patente` one each) and
  degrade nine, which is what makes the check a to-do list rather than a note.
- The audit fails when a literal restates a shipped table, which is how
  `preventivo_civile`'s contributo unificato bands lived in
  `fatturazione_avvocati.py` while `contributo_unificato.json` was updated next to
  them: a copy reads no file, declares no provenance, and drifts in silence. The
  comparison is on content and across shapes — the bands were copied as a list of
  two-tuples while the table stores them as dicts — with `TABLE_COPIES_ALLOWED`
  for a justified copy (empty today, and the audit fails on an exemption that no
  longer matches anything).
- `contributo_unificato.json` is reconciled with the DPR 115/2002 in force
  (verified against the reference table updated to D.L. 132/2014 and D.L.
  90/2014), and the table now declares it: `aggiornato_al` + `verifica:
  manuale`. Three entries carried values or shapes the source contradicts, and
  the reconciliation fixes them rather than vouching for them: `cautelari` was a
  flat €147 but the procedurali cautelari are *50% of the ordinary bands by
  value* (`cautelari.riduzione`); `esecuzione_mobiliare` was a flat €43 but is
  €43 *below €2,500 and €139 above* (scaglioni, with the boundary at 2499.99 —
  the largest two-decimal amount the "inferiore a €2.500" rule admits, since
  the band lookup is inclusive); `ottemperanza` was €650, the source says €300;
  the never-read `opposizione_esecutiva` key (full bands, where the rule halves
  them) is replaced by `opposizione_decreto_ingiuntivo` at half bands. The
  refusal of `contributo_unificato` disappears and the five tools that were
  degraded by its unverified vintage (`decreto_ingiuntivo`, `modello_notula`,
  `note_iscrizione_ruolo`, `preventivo_civile`, `genera_quotazione_docx`) answer
  at their full declared grade again — which is the mechanism working, and the
  reason the tests pinning the gap moved to tables still unverified.
- Refusals are put on record, so a reconciliation backlog can be ordered by
  what *did* block and not only by what could. With `LEGAL_REFUSAL_LEDGER=on`
  the ledger middleware appends one JSONL line per refusal and one per
  acceptance to `refusals.jsonl` under the cache root: the tool, the tables
  that caused it, the state, the grade claimed and what happened — a counter,
  not a log of the studio's work, so no case data ever reaches the file. It is
  opt-in (a read-only tool that refuses must not start writing files the host
  never asked for) and best-effort exactly like the cache: an unwritable ledger
  never turns a refusal into an error. The audit declares the ledger as a cache
  location, and its timestamps go through `_clock.now()`, so a pinned
  `LEGAL_NOW` pins the tally too (`tests/unit/test_refusal_ledger.py`).
- Every table the vintage policy can block now has a *supplying* alternative,
  not only a cheaper grade: `@sourced(..., alternativa=...)` is extended from
  two tools to all seven readers of the blocking tables. `contributo_unificato`
  takes `tabella_contributo_unificato` (a replacement table with the same
  shape, consumed by the whole computation including the appello/cassazione
  multipliers), `imposte_successione` takes `aliquote_franchigie` (the bracket
  list, read per `parentela` and tolerant of malformed entries),
  `imposte_compravendita` takes `aliquote_registro` (the registro section),
  `decurtazione_punti_patente` takes `tabella_violazioni` (the violation map),
  and `decodifica_codice_fiscale` takes `mappa_comuni` (a reverse catastal-code
  map). A call that supplies its datum reads no table, so the answer carries no
  vintage it does not rest on — and a caller who *can* vouch for a value no
  longer has to buy back a grade the table never supported.
- `backlog_riconciliazione` (the 222nd tool) is the read-out: the tables still
  unverified or expired, each with its source, its static cost (who reads it,
  at what declared grade, refusing or degrading — the audit walk, computed once
  per process and shared with `scripts/update-data.py`) and the action to take;
  when the ledger is on, the observed tally re-ranks the list, so the table
  that actually blocked twice outranks the one that only could have. With the
  ledger off it says so (`disponibile: false`) instead of staying silent, and
  the answer is frozen in the golden reference like every other tool's. The
  same derivation is what `/dati` (new plugin command) reads, so refreshing a
  table — verify the source, update the values, set `verifica: manuale` and
  `aggiornato_al`, re-run the suite — is a guided flow that never opens the
  code.
- `imposte_successione` and `violazioni_patente` are reconciled with their
  sources in force: the Agenzia delle Entrate schedule for the succession
  brackets and franchises (every value matched -- the fix was provenance, not
  numbers) and the art. 126-bis attached table for the licence points, where
  three values were wrong and are corrected (failing to yield 6 points, not 8;
  overtaking 3, not 4; driving uninsured 5 points, not 0), with the speeding
  bands tied to the right subsections of art. 142 and the pecuniary ranges
  alongside the points. Their refusals go away: the shipped tables now block
  three tools (`codice_fiscale`, `decodifica_codice_fiscale`,
  `indennita_preavviso`) instead of six, and the golden reference shows the
  diff instead of trusting the edit.
- `comuni`, `codici_ruolo` and `preavviso_ccnl` are reconciled with their
  official sources, and with them the backlog reaches **zero refusals** on the
  shipped surface: every table an exact-grade tool applies is now verified.
  `comuni` is checked name-by-name against the ISTAT catastal-code list
  (7,899 comuni): 143 catastal codes were wrong (Ercolano, Olbia, Cortona,
  Bitetto and Bitonto swapped, ...) and are corrected, official denominations
  come first so the reverse lookup answers with them instead of an alias,
  unverifiable entries (foreign towns, fractions without a vouched code) are
  dropped, and the table re-declares itself (`aggiornato_al`, `verifica:
  manuale`, the ISTAT list as source). `codici_ruolo` is rebuilt on the
  official DM 32/2012 / DGSIA object-code table. `preavviso_ccnl` is verified
  against the three contracts (metalmeccanici and commercio matched
  cell-by-cell; studi professionali had 14 wrong cells, corrected). What is
  left unverified -- `codici_ateco`, `tribunali_competenti` -- has only
  INDICATIVO readers, so nothing refuses: answers degrade and say so. The
  refusal path keeps its wire coverage on a probe server
  (`plugin/server/probe_precision.py`, the same `sourced` wrapper, launched
  through the harness), so the policy's teeth are tested against a real
  refusal instead of against a gap the data work has closed.
- Monthly refusal report: `verbale_mensile` (the 223rd tool) reads the ledger
  the middleware writes (`${MCP_CACHE_DIR:-~/...cache/mcp-legal-it}/refusals.jsonl`,
  opt-in with `LEGAL_REFUSAL_LEDGER=on`) and compares the current month with
  the previous ones — refusals and accepted downgrades per tool, which table
  blocked, and whether the callers are negotiating past the policy. The
  aggregation lives in `src/lib/_refusals.monthly()`, the recurring habit in
  `scripts/verbale-report.py` (cron line or pre-release check), and the host
  command `/verbale` reads the same numbers inside a conversation; `/dati`
  points there from the data side. `tests/unit/test_refusal_ledger.py` covers
  the aggregation and the wire surface.
- Online-source provenance: every open-world answer now declares *when it
  consulted the web*. The shared HTTP wrapper and the direct `httpx` sites
  (`retry_request(dataset=...)`, `note_source(...)`) record the consult in a
  contextvar (`src/lib/_sources.py`); the same middleware pass that stamps
  tables and precision attaches `mcp-legal-it/fonti_consultate` to the result
  `_meta` — dataset name, `scheme://host//path` prefix (never a query string,
  so the caller's search terms stay out of the provenance), and a call-level
  timestamp from the unrecorded clock. The committed policy is
  `src/source_bindings.py`, derived by the audit from the call graph: a client
  that starts fetching a new dataset fails the suite until the policy is
  regenerated, and the CI runs that check (`policy-sync` job) on every push.
  `tests/unit/test_online_sources.py` proves the middleware, the URL privacy
  and the undeclared-source flag; the golden fails if a local answer's shape
  changes, and the audit pins which tool may name which source.

### Fixed
- Two of the reconciled tables re-read against the primary source
  (2026-09-20). `violazioni_patente`: generic failure to yield is art. 145
  c.10 (5 points; the stop line, c.5, keeps its 6), safety distance and
  wrong-way driving now rest on their base commi (art. 149 c.4: 3, art. 143
  c.11: 4) with the aggravated cases as separate keys
  (`distanza_sicurezza_collisione` 5, `distanza_sicurezza_lesioni` 8,
  `contromano_curve_dossi` 10), hit-and-run split into injuries (art. 189
  c.6: 10) and damage to things only (`fuga_incidente_cose`, c.5: 4).
  `contributo_unificato`: sourced from art. 13 DPR 115/2002 on Normattiva
  instead of a secondary table; adds the fixed 168 for oppositions to
  enforcement acts (c.2), the three public-contract tiers up to 6.000 above
  1 M (c.6-bis lett. d), the 1.800 abbreviated rite, the 300 for citizenship
  and residence cases, and the Consiglio di Stato amounts raised by half
  (art. 1 c.27 L. 228/2012); the note records that the labour-court
  exemption only covers parties under twice the art. 76 threshold.
- Brocardi annotations for every act that is not a codice. `find_brocardi_url`
  matched the act name as a substring of the table labels, so a resolved
  `("decreto legislativo", 2001-06-08, 231)` never found `"(D.lgs. 8 giugno
  2001, n. 231)"` (46 of the 100 Brocardi sources had no page) and every
  `legge` fell into the first label containing the word — `art. 18 Statuto
  dei lavoratori` returned the massime of art. 18 legge fallimentare, legge
  Gelli those of L. 241/1990, legge Pinto those of the divorce law (13 wrong
  pages). The table labels are now parsed once into the identity (tipo,
  anno, numero) — `parse_brocardi_estremi` — and a citation matches only its
  own identity, by name for the labels without extremes (Costituzione,
  Preleggi, CCNL); a citation without a year matches only when the number is
  unique for that tipo; a Brocardi name paired with extremes resolves only
  if they are its own, and explicit extremes that contradict a codice's URN
  name the act themselves (`codice dei contratti pubblici` + 50/2016 is the
  abrogated code). The act date now travels from the resolver to the
  Brocardi client at every call site (`fetch_brocardi(..., data=)` from
  `cite_law`, `cerca_brocardi`, `fetch_law_annotations`, `mappa_orientamento`,
  `giurisprudenza_articolo`; `fetch_annotations`), which is what tells
  D.lgs. 81/2008 from D.lgs. 81/2015. No substring fallback remains: an act
  that is not on Brocardi says so. 97/101 of the sources listed at
  brocardi.it/fonti.html now resolve by name (was 35).
- Brocardi table completed against the fonti index: disposizioni di
  attuazione c.p.p. (D.lgs. 271/1989) and the abrogated codice dei contratti
  pubblici (D.lgs. 50/2016, reachable only by explicit citation — the name
  still resolves to D.lgs. 36/2023); D.L. 18/2020 "Cura Italia" reaches the
  page Brocardi files under its conversion law; the TU maternità label
  carries its estremi (D.lgs. 151/2001). Resolver aliases for the GDPR's full
  name, disp. att. c.p.p., and the quoted nicknames `Decreto "Sostegni"` etc.
  `scripts/generate_atti_denominati.py` reuses the same parser. New live gate
  `tests/unit/test_brocardi_codici_live.py` fetches every table URL and diffs
  the table against the fonti index.
- Data refresh: FOI index for August 2026 (ISTAT, 16-09-2026: 103,7 in base
  2025=100 → 125,9 linked to 2015=100; official variations +3,4% / +4,8%,
  recorded without a Gazzetta reference until the comunicato is published).
  Verified against the sources on 2026-09-20: TEGM Q3 2026 (DM 23-06-2026,
  GU n.149; the Q4 decree is not out yet), late-payment rate H2 2026 10,40%
  (MRO 2,40% + 8, GU n.163 of 16-07-2026), legal rate 2026 1,60% (DM
  10-12-2025, GU n.289), IRPEF 2026 brackets 23/33/43 (L. 199/2025).
- Data refresh (issue #36): FOI index for July 2026 (ISTAT, 12-08-2026: 103,1
  in base 2025=100 → 125,2 linked to 2015=100; official variations +2,8% /
  +4,3%) and the Gazzetta references for the June and July comunicati, both
  in GU n.201 of 31-08-2026 (26A04494, 26A04495). Art. 139 CAP
  micropermanenti amounts revalued by DM MIMIT 20 July 2026 (GU n.173 of
  28-07-2026, cod. 26A03765): first-point value €988,45, ITT €57,64/day,
  +2,6% on the April 2026 FOI, applying from April 2026 (`_vintage` now
  carries `aggiornato_al`; `docs/strumenti.md` follows).
- `scripts/refresh_data.py`: the monthly FOI append matched the first
  `"<year>": {` of the file, which since the 2025=100 rebasing belongs to
  `indici_base_2025`; the safety check refused the rewrite every month and
  the September cron opened issue #36 instead of a PR. The append is now
  anchored to its block, mirrors the published base-2025 value and moves
  `_vintage.copre_fino_a` (the one field it rewrites; the dead `_note`
  stamp is gone); the rewrite must equal the original plus exactly those
  edits.
- Tests probing the "index not yet published" fallback run on a FOI series
  frozen at 06/2026 (`tests/unit/conftest.py:foi_serie_fissa`) instead of
  the live table, so a data refresh — including the monthly auto-refresh
  PR — no longer turns them red by construction.
- A helper module in `src/lib/` was classified as an *upstream service*.
  `upstream_clients()` returns `src/lib/<name>` unless the name is declared an
  in-process helper, and the ledger's own `_tables_open` was not. The 71 tools
  that import it (70 read-only calculations and one document generator) were
  counted as reaching an upstream service: the 70 moved into the report's
  "external" column and the page's open-world count went from 50 to 121, while
  every annotation stayed correct
  (`openWorldHint` reads the call graph instead and never saw the module as a
  client). Two readers of the same tree disagreed and nothing failed, which is
  the part worth fixing: `_ledger` and `_tables_open` are declared now, and a new
  `verify_lib_modules` check fails on any module under `src/lib` that is declared
  neither way -- a module is an in-process helper, a package is a client -- with
  `tests/unit/test_tool_annotations.py` sabotaging both directions.
- The call graph had no edge for a function handed over as a *value*.
  `_get_fonti()` in `giurisprudenza_unificata.py` returns a dict of the four
  jurisprudence implementations and the caller calls through it, so there was no
  `Call` node to follow and the walk stopped at the dispatch table.
  `cerca_giurisprudenza_unificata` searches Italgiure, CeRDEF, Giustizia
  Amministrativa and CGUE, and was annotated read-only *and* local -- which is
  what a host pre-approves without a click, and what a reviewer reads as "a pure
  lookup". A bare reference to an imported function now counts as an edge;
  exactly one tool changes classification (read-only local 168 -> 167, open world
  49 -> 50) and nothing else moves: no table attribution, no write, no cache.
  The same blind path was also the last live value in the pinned fixture -- the
  tool answered from the network, so its recorded expectation drifted with the
  Cassazione archive (the refinement count moved 3866 -> 3863 between two runs).
  It is out of the reproducible surface now, leaving 167 tools that are.
- Three import-preloaded tables were invisible to the audit: `_CODICI_TRIBUTO`
  binds through a subscript (`json.load(f)["codici"]`), `_CATALOGO` through a
  dict comprehension, `_PREAVVISO` through an annotated assignment, and the walk
  only recognised a bare `X = json.load(f)`. All three are now attributed to the
  tools that read them, and a load inside a function body is seen too.
- `preventivo_civile` and `modello_notula` estimated the contributo unificato
  from a hand-kept copy of the bands instead of the shipped table: the copy does
  not age with `contributo_unificato.json`, could diverge from what
  `contributo_unificato` and `decreto_ingiuntivo` answer without anything
  failing, and left the estimate with no vintage. Both now read
  `civile.cognizione` and declare the table (the numbers are unchanged).
- `verify_provenance` compared the declaration against a `datasets()` that
  already contained it, so "declares a table the code never reads" could never
  fire. The code-derived set is now `reads()` and the comparison is real in both
  directions; `tests/unit/test_tool_annotations.py` sabotages a copy of the tree
  to check the three cases (dropped declaration, invented declaration, renamed
  loader) actually fail.
- The stdio harness passed no `valore_causa` to `note_iscrizione_ruolo` — the
  parameter is optional *with a default of null* — so the recorded answer was
  the "valore_causa richiesto per il calcolo del CU" branch and the table the
  tool declares was never applied. The curated arguments now compute it.
- `start_server.sh` is PATH-independent. GUI hosts (Claude Desktop, Cowork,
  Freebuff) spawn MCP servers with launchd's bare PATH
  (`/usr/bin:/bin:/usr/sbin:/sbin`), which hides Homebrew, `~/.local/bin` and
  cargo installs: `command -v uv` failed there and the launch silently fell
  through to the venv path. The bootstrap now prepends the usual install
  locations and probes `uv` by absolute path as well.
- The venv fallback no longer trusts `command -v`. Each Python candidate is run
  and the first one that reports 3.10+ wins: an unaccepted Xcode licence turns
  the CLT `python3` into a shim that only prints a licence error, and it used
  to be selected. A cached venv is now reused only if its interpreter is 3.10+
  **and** imports every runtime dependency, so a half-built venv (deps added in
  a later release, interrupted install) is rebuilt instead of starting a server
  that dies on its first import. `MCP_FORCE_VENV=1` skips `uv` to exercise the
  fallback deliberately.

### Changed
- CI also verifies the release tarball on every push and on every tag
  (`tarball-sync` job): `scripts/verify_tarball.py` compares `git archive` of
  the revision against the tree itself and fails when something forbidden
  (`/src`, `/tests`, any symlink) is inside, or when a tracked non-ignored
  file is missing -- the same two directions the marketplace sandbox enforces
  as `failed_content`, checked before the backend can see the release.


## [2.13.0] - 2026-08-30

### Added
- Parliamentary sources module (`src/lib/parlamento/` + `src/tools/parlamento.py`,
  3 tools — total now 221): `cerca_ddl` (keyword search over bill titles, both
  chambers via dati.senato.it), `iter_ddl` (full bicameral navette from a fase
  number or idDdl, enriched with the Camera statoIter timeline and stampato
  PDFs from dati.camera.it), `ddl_su_norma` (pending-reform lookup for a given
  act, resolver-expanded, explicitly best-effort on titles only). Senato is
  queried via GET only (its WAF 403s POST) and title search uses plain
  `FILTER(CONTAINS(...))` because the WAF also blocks `bif:contains`
  expressions with quoted or/and operators. Navette suffixes handled
  (`S.562-B`, lowercase stralci `S.926-bis`, unified texts `S.93-338-353-B`).
  New egress hosts declared: `dati.senato.it`, `dati.camera.it` (SECURITY.md
  updated); scheda links to `www.senato.it` / `www.camera.it` are emitted,
  never fetched. Real-capture fixtures + 4 live guard-rail tests.

### Changed
- The pending-reforms rule in the `ricerca_normativa` and
  `mappatura_normativa` prompts is now GROUNDED: it used to say "report
  pending reforms" with no verifiable source behind it; it now requires
  anchoring every mention to `ddl_su_norma`/`cerca_ddl`/`iter_ddl` output —
  atto number, dated status and official scheda link — and states that no
  results never proves no reforms (titles-only search).

## [2.12.1] - 2026-08-24

### Added
- `cite_law()` — and every tool sharing its resolver (`cerca_brocardi`,
  `fetch_full_act`, `download_law_pdf`, `giurisprudenza_su_norma`,
  `orientamento_su_norma`, `verifica_citazioni`) — now resolves acts cited by
  name rather than by number. The new `ATTI_DENOMINATI` table carries 80 acts
  and ~200 aliases: Statuto dei lavoratori, legge fallimentare, TUEL, TULPS,
  statuto del contribuente, the testi unici, and eponyms such as legge
  Gelli-Bianco, legge Cirinna, legge Biagi, legge Pinto, Jobs Act.
- EU treaties are citable: `art. 101 TFUE`, `art. 6 TUE`, `art. 8 CDFUE`,
  also under "Carta di Nizza" and the treaties' full names.
- 21 EU compliance acts by their usual acronym: DSA, DMA, Data Act, Data
  Governance Act, eIDAS and eIDAS2, Cyber Resilience Act, MiCA, CSRD, CSDDD,
  PSD2, the NIS, whistleblowing and ePrivacy directives, Machinery Regulation,
  European Accessibility Act.
- More citation forms: spelled-out act types (`legge 241/1990`, `decreto
  legislativo 231/2001`), `n. X del YYYY`, EU variants (`reg. (UE) 2016/679`,
  `direttiva 95/46/CE`), leading prepositions (`art. 111 della Costituzione`),
  dotted acronyms (`t.u.e.l.`, `c.p.a.`), and paragraph chains
  (`art. 2, comma 1, lett. a), del d.lgs. 231/2001`).
- An unrecognised act now reports the closest known names instead of a dead
  end. The resolver still returns nothing rather than guessing: citing the
  wrong act silently is worse than not citing it at all.
- `tests/unit/test_atti_denominati_live.py` (marker `live`) asks Normattiva and
  EUR-Lex whether every act in the tables exists with the date and number
  claimed. Run it before each release.
- `scripts/generate_atti_denominati.py --check` reports Brocardi acts the
  resolver cannot handle (currently 94/94).

### Fixed
- EUR-Lex articles were truncated to their heading: a substring test for
  `ti-art` also matched `sti-art`, the class of the article's own subtitle, so
  collection stopped on the first line. This affected every article carrying a
  separate rubric, not only the treaties.
- EU treaties could not be fetched at all — EUR-Lex answers automated requests
  with a WAF challenge (HTTP 202 and an empty body). They now come from CELLAR
  by CELEX, while the citable eur-lex.europa.eu URL stays the reported source.
- `codice del Terzo settore` was unreachable and produced a wrong URN: its key
  in `NORMATTIVA_URN_CODICI` carries a capital letter while every lookup
  arrives lowercased. Codici URNs are now matched case-insensitively.

### Changed
- Resolution order is explicit and documented in CLAUDE.md: the hand-verified
  tables (`ATTI_NOTI`, `NORMATTIVA_URN_CODICI`) take precedence over
  `ATTI_DENOMINATI`, whose base was generated from Brocardi labels. Act names
  are tried literal first, so normalization can only add resolutions, never
  change an existing one.

Diagnostic battery: 29/64 to 64/64 references resolved. 80 Italian acts and
21 EU acts verified live against Normattiva and EUR-Lex.

## [2.12.0] - 2026-08-24
### Fixed
- stop tracking `.mcp.json`: it carried the author's absolute paths into every
  clone, so it resolved to nothing on any other machine and asked a third party
  to approve a nested config on trust. `.mcp.json.example` replaces it, resolving
  everything from the checkout via `plugin/start_server.sh`
- `esporta-documento` told users to run the author's local venv for the PDF path,
  which exists on no other machine — the skill now uses `uv`, the prerequisite the
  plugin already declares
- the Stop-hook citation gate matched `cost` as a bare substring, so "costi",
  "costo" and "costante" read as a citation of the Costituzione and any nearby
  `art. N` tripped it. Anchored to `cost.`/`costituzion...`; covered by
  `tests/unit/test_citation_gate.py`
- the citation gate only recognised the abbreviated `art. N`, so `articolo 2043
  del codice civile`, `artt. 536 e 544 c.c.` and `articoli 2941 e 2946` — forms
  Italian legal writing uses interchangeably — passed unchecked. The article
  pattern is now shared with the `cite_law()` dedup, which previously failed to
  match a reference written out in full, and the law-token list covers the named
  codes (consumo, strada, crisi, navigazione, privacy, assicurazioni, contratti,
  CCII, TUIR, TUF). Codes enumerated one by one on purpose: a bare `codice`
  would have fired on codice fiscale, codice tributo and codice ATECO, which
  this project handles as data. Norms asserted with no article number at all
  stay out of reach of a regex and are deliberately not attempted
- the citation gate also fired on norms quoted inside fenced code blocks and
  inline spans — a sample tool payload or a fixture value is not the assistant
  asserting what an article says. Caught red-handed while writing up this very
  change: the gate nagged about an `art. 1284 c.c.` that appeared only inside a
  block showing what a tool returns
- the repo's own `.claude/settings.json` declared a Stop hook the plugin already
  registers, so the gate fired twice with an identical message. It ran the LLM
  `prompt` variant that `citation-gate.py` was written to replace for
  over-firing; the plugin owns the hook, so the repo no longer declares it
- the README badge advertised 177 tools against the 218 the server registers
- the test counts in `CLAUDE.md` and `docs/testing.md` had not moved since the
  comparison suite grew from 1 file to 30. Replaced with the file count and the
  command that prints the current figure: an exact number in prose goes stale on
  the next test added, which is the drift it was supposed to expose

### Added
- every table in `src/data/` declares a `_vintage` block (source, covered period,
  who verifies it), `src/lib/_data.py` reads it, and the 65 tools that consume a
  table now print it next to the number they derived from it. 16 tables are
  declared; the 8 whose provenance is not yet established say so explicitly in
  the tool output rather than staying silent
- `scripts/update-data.py --strict` fails on a table with no `_vintage` or an
  elapsed covered period, and warns on the ones still marked `da_verificare` —
  new drift is blocked, known gaps stay visible without a permanently red build

- `SECURITY.md` answers the questions an auditor asks before running this on
  client matters: no telemetry, the full egress host list, what the nested
  configs contain, how to fork and stay independent. `src/lib/_egress.py` holds
  the allowlist as code and `tests/unit/test_egress_allowlist.py` fails the
  build both on an undeclared host in `src/` and on a declared host missing
  from `SECURITY.md`, so the document cannot drift from the code

### Changed
- CI also runs on pushes to `main`, which previously went unverified between
  releases — `check_deps_sync` stayed red on `main` for days without a signal

## [2.11.1] - 2026-08-15

### Fixed
- pin `cryptography < 49` on Intel Macs: from 49.0.0 upstream ships arm64-only macOS
  wheels, so x86_64 Macs attempted a source build requiring Rust + OpenSSL and the
  `.mcpb` extension never started ("server disconnected")
- correct the 2025 FOI series: the published values were about one point too high, so
  every year-on-year figure disagreed with the official ISTAT variations in Gazzetta
  Ufficiale (0.00% against a published 0.8% for January 2026, 1.71% against 2.9% for
  June). Rivalutazione monetaria and rent adjustments under art. 32 L. 392/1978 were
  understating the change. The corrected series reproduces all six published
  variations to the cent
- carry the ISTAT 2025=100 rebasing explicitly: keep the original base-2025 series
  next to the linked one, record the official 1.214 linking coefficient with its
  Gazzetta Ufficiale source, and store the official art. 81 L. 392/1978 variations,
  which prevail over recomputing across the rebasing boundary
- fail closed on a missing FOI year instead of silently falling back to the closest
  one available, which could swallow whole years of inflation; a substituted month is
  now always reported in the result's `avvertenza`
- restore TAR/CdS search after the 2026 reorganisation of the giustizia-amministrativa
  portal, and replace the test suite that had been asserting against the old endpoints
- README: the `.mcpb` was described as having "nessuna dipendenza" while it requires
  `uv`; added a troubleshooting table for the disconnected-server case

### Changed
- realign the documentation with the actual codebase: the tool catalogue listed 162
  entries while claiming 218, and the prompt, resource, skill, agent, module and test
  counts were stale across `CLAUDE.md` and `docs/`

## [2.11.0] - 2026-07-30

### Added
- add analisi-fornitori supplier screening skill
- add genera_report_fornitori xlsx report generator
- add canonical supplier record validation (collect-all)
- add verifica_partita_iva_vies (VIES lookup)
- extend freshness check to IRPEF brackets and art. 139 danno bio
- auto-refresh FOI/mora with monthly PR; recalibrate staleness windows
- add VIES REST client with IT checksum pre-check

### Fixed
- harden analisi-fornitori xlsx output and VIES parsing edge cases
- guard supplier validation against unhashable field values
- document usufruct 2.5% floor and correct stale IRPEF resource
- harden check_vat never-raises contract (payload + JSON decode)
- refresh TEGM/FOI/mora to July 2026 and correct February FOI index

### Changed
- render CU, interessi/mora and IRPEF brackets from datasets

### Other
- fix stale module count in architecture pattern note
- align README and tool catalogs with the 218-tool set
- Merge feature/analisi-fornitori into develop
- Merge pull request #29 from capazme/fix/usufrutto-floor-irpef-resource
- update remaining tool-count mentions in CLAUDE.md setup notes
- register analisi-fornitori tools in server instructions and CLAUDE.md
- Merge pull request #28 from capazme/claude/data-refresher-update-cf6963
- add openpyxl dependency for supplier report generation
- add analisi-fornitori implementation plan
- add analisi-fornitori (supplier ledger privacy screening) design spec
- Merge develop into main (issue routing config)
- Merge pull request #27 from capazme/chore/issue-routing
- route security reports and questions off the issue tracker

## [2.10.1] - 2026-07-30

### Removed
- **Deleted three orphaned dependency files: `requirements.txt`, `requirements.lock`, `dxt/start_server.sh`.** No install path referenced any of them — Docker installs from `pyproject.toml`, the plugin and `.mcpb` bootstrap through `plugin/start_server.sh`, and both build scripts copy that file, not the `dxt/` one. They were nonetheless a real problem in two ways. `requirements.lock` had been frozen since the first commit and static scanners flagged 20 packages / 62 advisories against it (issue #25) — genuine CVEs, but in a file nothing installs. And `requirements.txt` and `dxt/start_server.sh` had both silently drifted, losing `python-docx`, so anyone who did install from them got a server whose procura/quotazione tools failed at import. `pyproject.toml` is now the single source of truth. Verified with `pip-audit 2.10.1`: every real install path resolves clean, 0 known vulnerabilities.

### Fixed
- **`fastmcp` version bound is now `>=2.0,<4` everywhere.** It was unbounded (`>=2.0.0`) in `pyproject.toml`, `plugin/server/pyproject.toml` and the no-`uv` venv fallback, but capped at `<4` in the `uv` path and `dxt/manifest.json`. The two sets happened to resolve to the same version today, so nothing was broken yet — but the release of fastmcp 4.0 would have broken Docker and the Cowork sandbox fallback while leaving the plugin pinned, a divergence that only shows up in production. Smoke-tested on fastmcp 3.4.5: 216 tools and 23 prompts register, 2366 tests pass.

### Added
- **`scripts/check_deps_sync.py` + CI gate.** The runtime dependency set is necessarily declared in five places, because each install path resolves it independently; nothing kept the copies aligned, and two of them had already drifted. The script treats `pyproject.toml` as authoritative and fails with an explicit per-file delta when a launcher disagrees, normalizing package names per PEP 503 so `python_docx >= 1.0` and `python-docx>=1.0` compare equal. Wired into `ci.yml` as the `deps-sync` job.
- **`security-audit.yml` workflow — `pip-audit` on PRs, pushes and weekly.** Dependencies declare lower bounds only, so upstream security fixes reach users without a release here; the cost is that a clean resolution can rot with no change to the repository. The Monday schedule catches that, and opens a labelled `security` issue when a scheduled run fails, mirroring the existing `data-freshness.yml` pattern. Workflow permissions are least-privilege (`contents: read`, `issues: write` only on the reporting job) and the third-party action is pinned to a commit SHA.

## [2.10.0] - 2026-07-27

### Added
- **`genera_procura_liti_docx()` + `genera_quotazione_docx()`** — new `procure_quotazioni` tool module for serial debt-collection paperwork. The first produces a signature-ready one-page power of attorney (art. 83, co. 3, c.p.c.) with the full declaration set (mediation ex art. 4 D.Lgs. 28/2010, assisted negotiation ex D.L. 132/2014, fee estimate, insurance, GDPR consent) and counsel authentication block; the second produces the client-facing fee-quotation letter (D.M. 55/2014 as amended by D.M. 147/2022) with the full liquidation table (30% PCT uplift ex art. 4, co. 1-bis, 15% general expenses, 4% CPA, 22% VAT, 20% withholding), automatic contributo unificato (halved for monitorio ex art. 13, co. 3, DPR 115/2002), registration-tax note and a client-acceptance block. Three quotation types matching the actual procedural phase: `monitorio` (single-phase table), `esecuzione` (introductory + conclusion phases, enforcement disbursements), `opposizione` (full four-phase litigation table). Figures validated against real filed prospetti.
- **`procure-quotazioni` skill** — orchestrates the serial workflow: reads a positions spreadsheet (or inline data), normalizes amounts (Swiss separators, corrupted cells), classifies each position's procedural phase (executive decree → esecuzione; opposed decree → opposizione; else monitorio), extracts the debtor-identification clause verbatim from prior deeds (anchored matching to avoid substring collisions), calls the two tools per position and files the output per client with a final report. Firm data lives in a local `studio.json` (example config bundled; no real data in the repo). Surface is now **216 tool / 22 skill / 8 slash command / 6 agent**.

## [2.9.0] - 2026-07-14

### Added
- **`cookie-audit` skill** — forensic in-browser cookie/tracker audit. Captures pre- and post-consent state in a clean context, fingerprints the CMP and third-party trackers, inspects the real server-side Google Tag Manager container (bypassing ad-blockers), builds the full cookie table, assesses compliance (Provv. Garante 10 giugno 2021, GDPR, art. 122 Codice Privacy, ePrivacy 2002/58/CE), exports a Word report and proposes remediation. Surface is now **214 tool / 21 skill / 8 slash command / 6 agent**.

### Fixed
- **`cite_law()` / `fetch_law_article()` now resolve the *preleggi* (Disposizioni sulla legge in generale).** `art. 12 preleggi` returned the abrogated art. 12 of the civil-code body (ex persone giuridiche) instead of the interpretation rule. The codice civile AKN export bundles the preleggi as a separate component part that the parser discarded in favour of the ~3249-article code body; the parser now exposes every component part and selects the preleggi part when `tipo_atto=preleggi`, leaving the c.c./c.p. and flat-act lookups unchanged. Added the aliases `disp. prel. c.c.`, `disposizioni sulla legge in generale`, `disposizioni preliminari (al/del) codice civile`. Verified live against Normattiva: `art. 12 preleggi` → "significato proprio delle parole" (art. 12 co. 1).

## [2.8.0] - 2026-07-01

### Removed
- **Consolidated the redundant command/skill surface.** Removed 5 slash-commands that were mere aliases of existing skills — `/parere` (→ `parere-legale`), `/compliance` (→ `compliance-privacy`), `/giurisprudenza` (→ `analisi-giurisprudenziale`), `/parcella` (→ `calcolo-parcella`), `/ricerca` (→ `ricerca-normativa` / `analisi-giurisprudenziale`) — and the `digest-giuridico` skill (superseded by the `/digest` command + the `digest-giuridico` agent; `/digest` now points to the agent only). No functionality lost: every removed workflow stays available via its skill/agent. Surface is now **214 tool / 20 skill / 8 slash command / 6 agent**.

## [2.7.9] - 2026-07-01

### Fixed
- **Citation `Stop` hook rewritten — no more over-firing, no wasted tokens.** The previous hook was a `type: prompt` (LLM) gate that ran on every stop: it hallucinated citations (flagging acronyms, concepts and template-file content as norms) and re-flagged norms already verified earlier in the session, spending tokens on an LLM call per turn. Replaced with a deterministic `plugin/hooks/citation-gate.py` that extracts article-level citations from the last assistant message and dedups them against the `cite_law()` calls already present in the transcript. Conservative (anti-nag bias); the strong enforcement of the merits stays on the pre-export gate and human review.

## [2.7.8] - 2026-06-23

### Fixed
- **`.mcpb` Desktop Extension now installs on Windows.** `dxt/manifest.json` declared `compatibility.platforms` as `["darwin", "linux"]`, so Claude Desktop on Windows refused the extension ("requires macOS or Linux"). Added `"win32"`. The bundle launches the server via `uv` directly (no `bash` dependency) and all deps ship Windows wheels, so it is cross-platform. Windows runtime confirmation pending. Reported by @giovannizanotto.

## [2.7.7] - 2026-06-23

### Fixed
- **`.mcpb` Desktop Extension was broken — the server never started.** `build-dxt.sh` places the server code under `server/`, but `dxt/manifest.json` pointed the runtime at `${__dirname}/run_server.py` (bundle root) → `Failed to spawn … No such file or directory (os error 2)`. Fixed the path to `${__dirname}/server/run_server.py` (and `entry_point` to `server/run_server.py`). Rebuilt and smoke-tested: the `.mcpb` now boots and registers all 214 tools. **The 2.7.6 `.mcpb` and earlier are unusable — use 2.7.7+.**

### Docs
- README: corrected the Windows `uv` install command — it needs the `powershell -ExecutionPolicy ByPass -c "…"` wrapper, otherwise PowerShell's execution policy blocks the script. Thanks @giovannizanotto.
- README: documented that Claude Desktop **Cowork** (the cloud agent) no longer runs local/stdio MCP servers (since the June 2026 cloud-backend migration), so the marketplace rejects this plugin with `failed_content`. The supported self-contained channels are the **`.mcpb`** Desktop Extension and the **Claude Code CLI** (both run locally). Refreshed stale counts in `plugin/README.md` (214 tool / 21 skill / 13 command / 6 agent).

## [2.7.6] - 2026-06-23

### Fixed
- **Marketplace install on Claude Desktop Cowork — the actual regression.** Bisected from the report that ≤2.6.1 worked: the only breaking change was 2.6.2 switching the marketplace `.mcp.json` command from `bash start_server.sh` to `uv`. Cowork's sandbox/validator accepts `bash` (and runs the bundled bootstrap with system Python) but not `uv` (not on its command allowlist / not in the sandbox), so every sync since 2.6.2 failed with `failed_content`. Reverted the marketplace `.mcp.json` to `command: bash` and hardened `start_server.sh` to **prefer `uv` when available** (Mac/Linux/Git-Bash, pins Python 3.12) and **fall back to a system-Python venv** (the 2.6.1 path that works in the Cowork sandbox). Smoke-tested: `bash start_server.sh` boots the server and registers all 214 tools.
- **Windows** keeps the `uv` path via the `.mcpb` Desktop Extension (`dxt/manifest.json` / `server/manifest.json` unchanged) — install via the `.mcpb` rather than the marketplace.

### Note
- The 2.7.3–2.7.5 changes (`.gitattributes` archive hygiene, `parcella.md` YAML, skill/agent/hook schema conformance) were real corrections but were **not** the Cowork blocker: at 2.6.1 the skills already carried `argument-hint`, the hooks already had a `SessionStart` prompt hook, and the agents lacked `name`/`color`, yet Cowork worked. They are kept as genuine hygiene / CLI-schema improvements.

## [2.7.5] - 2026-06-23

### Fixed
- **Marketplace install `failed_content` — schema conformance (the actual blocker).** The Cowork/Desktop marketplace validator enforces a closed schema on packaged plugin components; several components carried fields outside their schema and were rejecting the whole bundle on every fresh sync:
  - **Skills (21):** removed `argument-hint` (a slash-command field, **not** part of the Agent Skills schema) and `allowed-tools` from every `SKILL.md` frontmatter — reduced to the canonical `name` + `description`.
  - **Agents (6):** added the required `name` and `color` fields (the files had only `model` + `description`); removed the invalid `allowed-tools` field (the subagent schema uses `tools`).
  - **Hooks:** removed the unsupported `SessionStart` prompt hook (prompt hooks are only valid on Stop/SubagentStop/UserPromptSubmit/PreToolUse) and the undocumented `model` key from the Stop prompt hook. The Legal Grounding Stop hook is unchanged.
  - **Command:** `release.md` `argument-hint` `<versione>` → `[versione]` (avoid angle brackets in frontmatter values).

### Note
- The previous 2.7.3 (`.gitattributes`) and 2.7.4 (`parcella.md` YAML) fixes were real hygiene/parse corrections but were not the blocker; this schema conformance pass is.

## [2.7.4] - 2026-06-23

### Fixed
- **Marketplace install `failed_content` — real root cause.** `commands/parcella.md` carried an invalid YAML frontmatter: the `argument-hint` value used unquoted `[...]` brackets (`argument-hint: [civile|penale|stragiudiziale] [valore causa in euro]`), which YAML parses as a malformed flow sequence. Introduced by the 2.7.0 content audit (commit `353b8c2`); it was the only one of 13 commands / 21 skills not quoting the value. The account-scoped marketplace validator parses every command's frontmatter as YAML, so this single file failed the whole-plugin content validation on every fresh sync. Quoted the value to match the rest. The 2.7.3 `.gitattributes` `export-ignore` change stays as archive hygiene but was not the cause.

## [2.7.3] - 2026-06-23

### Fixed
- Marketplace remote sync `failed_content` on Claude Desktop (Cowork): the account-scoped marketplace validator rejected the repository tarball because of the tracked root `src` symlink (sandboxed extractors refuse symlinks for path-traversal safety) and the 14 MB AKN test fixtures bloating the archive to 19 MB (6× the working peers). Added `.gitattributes` `export-ignore` for `/src` and `/tests` so GitHub's generated tarball excludes both — the distributed archive drops from 2.0 MB to 0.5 MB and is symlink-free. No impact on local dev/test/Docker: real checkouts (`git clone`) ignore `export-ignore`, so the `src` symlink and the test suite stay available and tests keep resolving `src.` imports.

## [2.7.2] - 2026-06-23

### Removed
- Obsolete duplicate project-level skills (`.claude/skills/`, 5) and agents (`.claude/agents/`, 3) that shadowed the canonical `plugin/` versions — notably a stale `sinistro` skill still carrying the pre-2.7.1 double-counting workflow. The `.claude/settings*.json` are kept.
- Stale, unreferenced `plugin/skills/resources/tool-catalog.md`. Skill count corrected to 21 in the manifests (the `resources/` helper dir was miscounted as a skill).

## [2.7.1] - 2026-06-23

### Fixed
Legal-figures audit (resolution of the 3 open items + the sinistro workflow), verified against avvocatoandreani.it + official sources:
- **Valore catastale** (`calcolo_valore_catastale`): fixed double 5% revaluation — the coefficients 126/63/42.84 are already `base×1.05` and were applied to an already-revalued rendita. Now uses base multipliers (120/60/140/40.8) on `rendita×1.05`, adds a `prima_casa` parameter, and the **+20% surcharge ex DL 168/2004** on non-prima-casa strumentali for *compravendita* (not for successioni). Group E is now handled. (Refs: DPR 131/1986 art. 52; D.Lgs. 346/1990 art. 34; DL 168/2004 art. 1-bis; DL 262/2006 art. 2 c.45.)
- **`offerta_conciliativa`**: the 6-mensilità cap (art. 9 c.1, projected onto art. 6) was struck down by **Corte Cost. 118/2025** → cap rebuilt as 13.5 (=27/2). The ×0.5 halving is untouched (the Court did not strike it) and kept. Realigned with `indennita_licenziamento` (already updated to 118/2025).
- **`orientamento` disclaimer**: the L. 132/2025 article on AI in justice is **art. 15** ("Impiego dei sistemi di IA nell'attività giudiziaria"), not art. 13 (professioni intellettuali).
- **`analisi_sinistro` prompt + skill**: removed the double-counting of non-pecuniary damage (unitary per Cass. SU 26972/2008 «San Martino») and the interest computed on the fully-revalued capital (now on the progressively-revalued / average base per Cass. SU 1712/1995).

## [2.7.0] - 2026-06-18

### Changed
- **Content audit & refine** (`docs/_audit/`): full consistency pass over the 214 tools / 21 skills / 13 commands / 6 agents / 23 prompts / 15 resources. Skill/command/agent markdown realigned to the real tools (removed a reference to a non-existent tool, corrected parameter names + frontmatter). Legal figures touched by the audit were each verified against official sources and either kept (tests updated to the source) or reverted where unconfirmed — per-item decision register in [`docs/_audit/TRIAGE-RESOLUTION.md`](docs/_audit/TRIAGE-RESOLUTION.md). Three items remain flagged for the lawyer's sign-off (cadastral coefficients, `offerta_conciliativa` cap vs C. Cost. 118/2025, L. 132/2025 article number).

### Fixed
- `verifica_citazioni`/Italgiure step-4 fallback: reject a decision whose number/year don't match the cited one.
- `genera_notifica_data_breach`: the art. 33(3) DPO checklist is now truthful (was always-True).
- `diritto_societario` quorum: fail-closed (`False`) when data is insufficient.
- CeRDEF date format (`GG/MM/AAAA`) and other input validations (negative amounts, inconsistent dates, codice fiscale omocodia).
- **Security**: Brocardi URL cache directory created with `mode=0o700` (owner-only) — recovered from the orphaned `fix/cache-permissions` branch.

## [2.6.2] - 2026-06-15

### Fixed
- **Plugin MCP server did not start on Windows / Python 3.14**: the marketplace plugin (and `.mcpb`) launched the server via `bash start_server.sh`, which fails on Windows (no `bash`; venv uses `Scripts\` not `bin/`) and was fragile on macOS (first-run install timeout, non-self-healing venv). The skill loaded but the tools (`cerca_giurisprudenza`, `leggi_sentenza`, …) never connected. Now launched via `uv run --python 3.12 --with <deps> run_server.py` — one command identical on Windows/macOS/Linux; `uv` auto-provisions Python 3.12 and manages deps in its own cache. **New prerequisite: [`uv`](https://docs.astral.sh/uv/)** (one-line install, see README).

## [2.6.1] - 2026-06-15

### Fixed
- **Brocardi annotations 404**: `fetch_brocardi` now self-heals a stale/poisoned URL cache — when a cached article URL returns 404 (left over from an older version), it is dropped and re-resolved once, instead of failing permanently (e.g. annotations for `art. 2043 c.c.`).
- **Orientamento output**: removed the duplicated `sez.` for Sezioni Unite (`szdec="U"` now renders `Cass. civ., sez. un., ...` instead of `sez. sez. un.`).

## [2.6.0] - 2026-06-15

### Added
- 4 guided `@mcp.prompt` workflows (19 → 23) for the sources added in 2.5.0: `analisi_costituzionale` (Corte Costituzionale), `ricerca_gazzetta` (Gazzetta Ufficiale, RSS + as-published vs vigente), `orientamento_giurisprudenziale` (descriptive, with the L. 132/2025 disclaimer), `attuazione_direttiva` (EU directive → Italian implementing act → Normattiva text → CGUE case law).

## [2.5.0] - 2026-06-15

### Added
- **`verifica_citazioni`** — verifies a list of legal references (sentenze Cassazione + articoli) by resolving each via `cite_law`/`leggi_sentenza`; flags non-existent, pre-2020-not-verifiable, and metadata-mismatch citations (existence + metadata only, not holding accuracy).
- **Corte Costituzionale** (4 tools: `cerca_pronuncia_costituzionale`, `leggi_pronuncia_costituzionale`, `pronunce_cost_su_norma`, `ultime_pronunce_cost`) — reads the `dati.cortecostituzionale.it` open-data dumps (the main site is bot-blocked) with a cached download-and-parse model (latin-1, weekly TTL).
- **Gazzetta Ufficiale** (5 tools: `cerca_gazzetta_ufficiale`, `leggi_atto_gazzetta`, `sommario_gazzetta`, `ultime_gazzette`, `scarica_pdf_gazzetta`) — RSS feeds for "latest", HTML + ELI RDFa metadata for full text, official PDF link. No XML/AKN is exposed by the source.
- **`orientamento_giurisprudenziale`** (3 tools: `orientamento_su_norma`, `orientamento_su_principio`, `mappa_orientamento`) — descriptive map of conforming vs conflict-flagging Cassazione decisions + Sezioni Unite, over Italgiure + Brocardi. Strictly descriptive per L. 132/2025; no overruling prediction.
- **EU→Italy implementation mapping** (3 tools: `get_italian_implementation`, `get_eu_basis`, `elenco_misure_nazionali`) — CELLAR national-implementing-measures, reusing the CGUE SPARQL client.
- **Plugin / Cowork**: `digest-giuridico` weekly-briefing agent + command + skill; `esporta-documento` skill (DOCX via docx-js/SAPG canon, PDF via fpdf2); ported `parere`/`giurisprudenza`/`compliance` slash commands; new `cowork` `LEGAL_PROFILE`.
- ~300 new unit tests (full suite 2321 passing).

### Changed
- Tool count 198 → 214; `costituzionale` tag added to the `normativa` profile; manifests re-tallied to 214 tools / 22 skills / 13 commands / 6 agents.

### Fixed
- `orientamento`/Sezioni Unite detection uses `szdec:U` (the previous `szdec:SU` matched nothing).

## [2.4.1] - 2026-06-15

### Fixed
- Version metadata consistency: bumped all distribution manifests (`.claude-plugin/marketplace.json`, `dxt/manifest.json`, `plugin/server/manifest.json`, `plugin/server/pyproject.toml`) and the plugin changelog to the package version. The 2.4.0 `.mcpb` was built from stale 2.3.3 manifests.

## [2.4.0] - 2026-06-15

### Added
- AKN XML fetch path for Normattiva (`akn_parser.py`, `akn_fetch.py`): fetches the official Akoma Ntoso 3.0 export via `caricaAKN` instead of scraping per-article HTML, with automatic fallback to the HTML path on any failure
- Parser handles both Normattiva structures — flat (`<article eId="art_N">`) and component (`<doc name="...-art. N">` for codici like c.c./c.p.) — resolves `<ins>`/`<del>` to vigente text and strips `(( ))` modification markers
- Bounded LRU + on-disk parsed-act cache with a persisted hit counter; a URL→params index lets warm hits skip the landing page entirely (0 network for the 2nd+ article of the same act)
- `AKN_DISABLED` env var to force the legacy HTML path
- 60 new unit tests + a HTML-vs-AKN benchmark harness (`benchmarks/akn_vs_html.py`)

### Changed
- `fetch_article` and `fetch_normattiva_full_text` now route AKN-first with HTML fallback (public tool signatures unchanged)

### Performance
- Full-text retrieval 8–37x faster (1 request vs 33–158 AJAX calls) and more complete than the HTML walker (e.g. L. 241/1990: 51 vs 32 articles); single-article at parity cold, instant when cached

## [2.3.3] - 2026-04-13

### Added
- `_normalize_query()`: preprocesses LLM queries — strips quotes from normative references, removes single-word quotes, drops Italian stopwords from long queries
- `_auto_relax()`: progressive fallback when search returns 0 results (strip quotes → relax minimum-match → reduce terms → explore suggestion)
- `leggi_sentenza` fallback chain: retries without sezione, without zero-padding, then full-text search before giving up with actionable suggestion
- `_smart_suggestions()`: generates concrete filter suggestions from facet data when explore returns >10k results
- 38 new unit tests (224 total)

### Changed
- `cerca_giurisprudenza` docstring: anti-patterns, CORRECT vs WRONG examples, emphasis on structured filters over query terms
- `giurisprudenza_su_norma` docstring: clarified when to use vs `cerca_giurisprudenza`

## [2.3.2] - 2026-04-01

### Fixed
- Removed 20 nested `.zip` files from `plugin/dist/web-skills/` that blocked plugin installation in Claude Desktop (`ZipExtractionError: Nested zip files are not allowed`)
- `start_server.sh`: Python discovery now tries `python3.12`, `python3.11`, `python3.10` before `python3` — fixes Conda/Anaconda environments where `python3` points to 3.9
- Added `plugin/dist/` to `.gitignore` to prevent future build artifacts from being committed

## [2.3.1] - 2026-04-01

### Fixed
- All 6 manifest files now correctly report 198 tool count (dxt/manifest.json, plugin/server/manifest.json, plugin/server/pyproject.toml were stuck at "177 tool" since v2.2.0)
- release.py: `bump_extra_manifests()` syncs version + tool count across all manifests
- release.py: `verify_all_versions()` pre-tag gate prevents releasing with misaligned versions
- release.py: `count_tools()` auto-detects @mcp.tool count from source files
- /release command: added Step 9 mandatory pre-tag verification

## [2.1.0] - 2026-03-17

### Added
- **CeRDEF integration** (def.finanze.it): 3 tools for Italian tax case law (`cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento`, `ultime_sentenze_tributarie`)
- **Giustizia Amministrativa integration** (giustizia-amministrativa.it): 4 tools for TAR/CdS case law (`cerca_giurisprudenza_amministrativa`, `leggi_provvedimento_amm`, `giurisprudenza_amm_su_norma`, `ultimi_provvedimenti_amm`)
- **CGUE integration** (CELLAR SPARQL): 4 tools for EU Court of Justice case law (`cerca_giurisprudenza_cgue`, `leggi_sentenza_cgue`, `giurisprudenza_cgue_su_norma`, `ultime_sentenze_cgue`)
- Prompt `analisi_tributaria` — workflow giurisprudenza tributaria
- Prompt `analisi_giurisprudenza_amministrativa` — workflow TAR/CdS
- Prompt `analisi_giurisprudenza_europea` — workflow CGUE
- Resource `legal://riferimenti/cerdef-giurisprudenza` — guida CeRDEF
- Resource `legal://riferimenti/giustizia-amministrativa` — guida TAR/CdS con 28 sedi
- Resource `legal://riferimenti/cgue-giurisprudenza` — guida CGUE con materie e CELEX

### Changed
- Tool count: 166 → 177 (+3 CeRDEF, +4 GA, +4 CGUE)
- Prompt count: 16 → 19
- Profile `normativa`: added `giurisprudenza_amm`, `giurisprudenza_ue` tags
- Profile `fiscale`: CeRDEF tools included via existing `giurisprudenza` + `fiscale` tags

## [2.0.2] - 2026-03-17

### Changed
- License changed from MIT to Apache 2.0 across all manifests

### Added
- Professional README with badges, installation guides, and full tool catalog
- `LICENSE` file in repository root (Apache 2.0)
- GitHub Actions CI workflow (Python 3.10 + 3.12, runs on PR and push to develop)
- Issue templates (bug report, feature request)
- Pull request template with checklist

## [2.0.1] - 2026-03-17

### Added
- `.mcp.json` in plugin for automatic MCP server startup via marketplace (Claude Code CLI and Cowork)
- `manifest.json` (mcpb) for Desktop Extension packaging as alternative distribution channel

## [2.0.0] - 2026-03-16

### Changed
- **BREAKING**: Dual entry point — plugin for skills/agents/hooks, DXT for MCP server
- Plugin: 19 skills, 8 commands, 5 agents, Legal Grounding Protocol hooks
- Server: 166 MCP tools, 16 prompts, 10 resources
- Server code moved to `plugin/server/` — plugin is fully self-contained

## [1.2.0] - 2026-03-15

### Added
- CONSOB integration: 3 tools (`cerca_delibere_consob`, `leggi_delibera_consob`, `ultime_delibere_consob`)
- CONSOB scraper (`src/lib/consob/client.py`)
- Privacy/GDPR: 12 tools, 3 Garante Privacy tools
- 8 slash commands: norma, sentenza, ricerca, interessi, parcella, codice-fiscale, scadenza, privacy
- Resource `legal://riferimenti/gdpr-checklist`, `legal://riferimenti/consob-delibere`
- GitHub Actions release workflow

### Changed
- Tool count: 146 → 164
- Prompt count: 12 → 16

## [1.0.0] - 2026-02-26

### Added
- Initial release: 146 tools in 15 categories
- Normattiva, EUR-Lex, Italgiure, Brocardi scrapers
- 12 prompt workflows, 8 static resources
- Legal Grounding Protocol
- Docker support (stdio + SSE transports)
