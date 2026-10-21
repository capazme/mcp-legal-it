# CHANGELOG 3.0.0: cleaned section, to paste at release

**Not part of the changelog.** This file holds the 3.0.0 section of
`CHANGELOG.md` with the duplicates removed. It lives here because every open
3.0 PR edits `CHANGELOG.md` and an edit in this PR would conflict with all of
them. At release, after the whole chain is merged:

1. Replace the `## [Unreleased]` section of `CHANGELOG.md` with the section
   below (from `## [3.0.0]` to the end of this file), date filled in.
2. `plugin/CHANGELOG.md` is **not** a copy of the root one: its
   `[Unreleased]` lacks the entries of #58, #59, #61 and #62 and has several
   entries in Italian. Replace its `[Unreleased]` with the same section, and
   change the migration-guide link to `../docs/migration/2.x-to-3.0.md` (the
   plugin changelog sits one folder down). Which language the plugin
   changelog is written in is left to the owner; the section below is in
   English, as the root one.
3. Re-read the merged `[Unreleased]` once more: any entry landed after this
   draft (the remaining VisuaLex migration steps) must be carried over.
4. Answer **n** to `release.py`'s «Scrivere il CHANGELOG?»: it would prepend
   a second, auto-generated section built from commit subjects.

## What was removed, and why

The 3.0 `[Unreleased]` section repeats 2.x entries: until 2026-09-28 every
2.x feature was ported to the 3.0 line as a separate commit, and #55 merged
2.17.0 into develop. A user upgrading from 2.17.0 already has all of them, and
they stay in the 2.x sections of the changelog. The entries removed:

| Removed entry | Already in |
|---|---|
| `stato_server()`; `server.json` | 2.14.2 |
| CeRDEF works again (#46); `ultime_sentenze_tributarie` covers twelve months | 2.14.2 |
| Grounding rules normalized | 2.14.1 |
| `verifica_dpa_fornitore`; TMview; `formato="json"`; console entry point; `serverInfo.version`; the refusal chart; tool annotations; cache writers; `LEGAL_CACHE=off`; cache audit; the one clock reader; golden calculators; stdio harness; `tool_report.py`; read-only contract; provenance datasets; table vintages and footers; dead-table audit; `opened_tables`; `dati_applicati` from observation; `avvisi_dati`; precision policy; `accetta_precisione`; supplying alternatives; `update-data.py` costs; table-copy audit; `contributo_unificato`, `imposte_successione`, `violazioni_patente`, `comuni`, `codici_ruolo`, `preavviso_ccnl` reconciled; refusal ledger; `backlog_riconciliazione`; `verbale_mensile`; online-source provenance | 2.14.0 |
| Two reconciled tables re-read; FOI August 2026 refresh; Brocardi by identity; Brocardi table completed; FOI July 2026 refresh (#36); `refresh_data.py` anchoring; helper-module classification; call-graph edge for function values; import-preloaded tables; `preventivo_civile` copy; `verify_provenance`; harness `valore_causa` | 2.14.0 |
| `start_server.sh` PATH independence; venv fallback | 2.14.0, and the launcher no longer exists (2.17.0 layout) |
| CI `tarball-sync` job | Superseded: 2.17.0 replaced it with `directory-readiness`, which the 3.0 line keeps |
| `/release` maintainer-only; both tool prefixes in `allowed-tools` | 2.16.1 |
| Parliament module (the `[3.0.0-beta.1]` section) | 2.13.0; the beta section stays as history |

Kept and reworded: the #62 entry said that «l. cost.» inside a citation was
still refused; #60 makes the parser read it, so the two entries are merged.
Added from the PR descriptions where `[Unreleased]` had no entry:
`orientamento_su_norma` ordering (#58) and the `certifi` bump (#55).

---

## [3.0.0] - YYYY-MM-DD

3.0 is 2.17.0 plus the work below. Upgrading from 2.x:
[`docs/migration/2.x-to-3.0.md`](docs/migration/2.x-to-3.0.md). Every 2.x
feature from 2.13.0 to 2.17.0 is included (see those sections).

### Added
- **`mcp_legal_it.api`: mcp-legal-it as a library, and its only stable
  surface.** Pure `async` functions for network work and sync ones for parsing
  and catalogues, typed returns (frozen dataclasses), no Markdown, errors as
  data (`esito` from a closed vocabulary, plus `errore`). Norms:
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
  network result carries its `fonti`. Importing it loads neither FastMCP nor
  the server and opens no connection (tested with FastMCP and sockets
  blocked). `configurazione(client_factory=…, cache_dir=…, cache=…,
  brocardi=…)` injects the HTTP client factory, the cache settings and the
  Brocardi switch; the environment's *off* still wins. Reference, deprecation
  policy and planned operations: `docs/api.md`. Public names and signatures
  are frozen by `tests/unit/test_api_surface.py`.
- **`crea_server(include_tags=None, exclude_tags=None, brocardi=True, *, name,
  prompts)`** in `mcp_legal_it.server`: a FastMCP server exposing only the
  selected tools, for a host that mounts mcp-legal-it into its own surface. It
  mounts the stock server and narrows it with visibility filters, so the tools
  keep names, schemas, annotations, `_meta` and middleware; an excluded tool is
  absent from `list_tools` and answered as unknown. Unknown tags, and an empty
  `include_tags`, raise `ValueError` with the vocabulary. The instructions
  never point the model at a tool the server hides; the skills, agents and
  prompts say `cerca_brocardi` (se disponibile). Example in
  `docs/tool-tags.md`.
- **`LEGAL_BROCARDI=off`: the server without Brocardi.** Brocardi.it, the only
  private source (doctrinal notes and case-law abstracts, never the text of a
  norm), stays on by default. Off means: `cerca_brocardi` and
  `fetch_law_annotations` are not listed (228 → 226 tools); no request reaches
  brocardi.it, because the two scrapers that build Brocardi URLs ask
  `lib/_brocardi_switch.py` before any I/O (and `_egress.is_allowed()` refuses
  the host); `cite_law(include_annotations=True)`, `giurisprudenza_articolo`
  and `mappa_orientamento` answer without it and say so. In code:
  `crea_server(brocardi=False)` for one server, `_brocardi_switch.disabled()` /
  `set_default(False)` for library calls (these stop every request but do not
  change a server's tool list); an *off* set in the environment cannot be
  switched back on from code. `stato_server` reports the state.
  `tests/unit/test_brocardi_switch.py` fails if any Brocardi-tagged tool, or
  either scraper, sends a request to a Brocardi host, and walks the call graph
  of `tools/` so a new tool reaching the scrapers without the tag fails too.
- **Network rules per source, from VisuaLex** (`core/_http`). Every request
  the readers send, redirects included, is checked before it leaves: scheme,
  no credentials, and a host the source may reach (until now the host list was
  checked only by the tests). Per source and per process: at most 3 requests
  in flight, 0.5 s between two, shared by every thread and event loop; a
  `Retry-After` stated by a 429 or 503 pauses that source for every caller for
  at most 30 s (a longer statement refuses that call at once with
  `FontePausata`). The limits hold within one process: N processes on one
  machine make N times the cap. `retry_request` now retries a 429 too, waiting
  what the source asked, with jitter. Optional circuit breaker,
  `LEGAL_CIRCUIT_BREAKER=on` (off by default): 3 consecutive failures suspend
  the source for 5 minutes; a 404 never counts. A library caller with its own
  `client_factory` keeps the host guard and can put the limits under its own
  cache with `con_regole`. Measured on VisuaLex's 19 timing requests: the same
  requests as before, row by row (`scripts/measure_requests.py`).
- **Article suffixes and act types from VisuaLex.** One suffix table,
  VisuaLex's, imported byte for byte and pinned to it (from `bis` to `vicies`
  and their spelling variants): the private copies that stopped at `decies`
  read "art. 25-terdecies d.lgs. 231/2001" as art. 25-ter in the Cassazione
  searches (`giurisprudenza_su_norma` looked for the wrong article) and built a
  URN with a space for "25 terdecies". `api.SUFFISSI_ARTICOLO` now runs to the
  20th and `api.ARTICLE_SUFFIX_ALTERNATION` is VisuaLex's (`tredecies`, which
  no source was found to print, is no longer listed). `normalize_act_type`
  reads case and spacing as VisuaLex does, and the act tables gain VisuaLex's
  rows: "d.l.", "l. cost.", "r.d.l.", "d.lgs.lgt." given as the act type
  (`fetch_law_article`, `api.riferimento_da_parametri`) built
  `urn:nir:stato:d.l.:…` and `l..cost.`; "c.p.a."; the implementing regulations
  of the c.p.p. and of the industrial property code. VisuaLex's source
  convention (`golden.json`) is a pinned fixture: the norm identities
  mcp-legal-it builds already must match it, the others are listed with the
  step that closes them.
- Concurrent cold requests for the same act share one download of its Akoma
  Ntoso export (before, N callers downloaded it N times).
- `scripts/replay_mcp_outputs.py`: records the real HTTP exchanges of 36 MCP
  tool calls once, then replays them offline against a git ref and the working
  tree and compares every answer, `_meta` included, so a refactor can prove the
  tools' outputs did not change. The tape stays local.
- `docs/migration/visualex-inventory.md`: the function-by-function inventory of
  the VisuaLex readers that move into mcp-legal-it, with the choice for each.

### Changed
- **BREAKING — the import package is now `mcp_legal_it`, no longer `src`.**
  A published package must not own the name `src`: installed next to any
  project whose own code is a `src` package, one of the two shadowed the
  other. The sources moved from `plugin/server/src/` to
  `plugin/server/mcp_legal_it/` and the `src` symlink at the repository root is
  gone. The distribution name and the console script stay `mcp-legal-it`; the
  script points at `mcp_legal_it.cli:main`, and `python -m mcp_legal_it`
  replaces `python -m src`. There is no `src` compatibility shim: code that
  imports `src.*` has to switch to `mcp_legal_it.*`. The MCP surface does not
  change, except that `backlog_riconciliazione` now names a table as
  `mcp_legal_it/data/<name>.json`. A new test fails when any key of the
  generated bindings stops naming a module that imports, because the runtime
  ledger skips an unknown module silently and every result would lose
  `dati_applicati`.
- **Tool tags follow one taxonomy, and some desktop profiles change.** Every
  tool carries exactly one *kind* — `normativa` (19), `giurisprudenza` (24),
  `autorita` (6), `registri` (5), `calcolo` (141), `redazione` (30),
  `diagnostica` (3) — plus, for case law, its court (`giurisprudenza_cass`,
  `giurisprudenza_cost`, `giurisprudenza_trib`, `giurisprudenza_amm`,
  `giurisprudenza_ue`) and, for an authority, `garante` or `consob`. The
  vocabulary is data (`mcp_legal_it/tool_taxonomy.py`), the table is
  `docs/tool-tags.md`, and `tests/unit/test_tool_taxonomy.py` fails on a tool
  without a kind or with a tag outside the vocabulary. Renamed or moved tags:
  TAR/CdS and CGUE tools are `giurisprudenza` (no longer `normativa`);
  `costituzionale` → `giurisprudenza_cost`; the Garante tools are `autorita` +
  `garante` + `privacy`, CONSOB `autorita` + `consob`; TMview is `registri` +
  `marchi` and the diagnostics `diagnostica`; the EU-transposition tools are
  `normativa` + `recepimento_ue` (no longer `giurisprudenza_ue`). Hosts
  filtering on the old tags must update them.

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

  The tools that leave a profile were in it only by the stray `normativa` tag.
  With `LEGAL_BROCARDI=off` every profile containing `normativa` shows two
  tools fewer.
- **The citation gate reads like the server, and checks decisions too.** The
  plugin's Stop hook, now also registered on `SubagentStop`, extracts citations
  with the server's own parser and resolver (moved, unchanged, into the
  stdlib-only `core/riferimenti.py` and `core/citazioni.py`, re-exported where
  they were): an act is identified by the URL `cite_law` would fetch, so
  aliases of one act coincide and "art. 2 Cost." no longer covers "art. 2
  c.p.". Credit comes from what a tool returned — a `cite_law` /
  `fetch_law_article` result that served that article, a `fetch_full_act` text
  that contains it, a `leggi_*` / `cerca_*` result of the same court naming a
  decision's number and year in its heading (never the precedents cited in a
  decision's body) — anywhere in the session, its subagents included and other
  sessions never. It reads every text block of the turn plus the prose written
  with Write/Edit and the inputs of `esporta_atto_docx` / `genera_*`, finds
  acts away from the article ("D.Lgs. 196/2003, art. 13", "art. 6, par. 1,
  lett. f), del Regolamento (UE) 2016/679", "artt. 1218 e 1223 c.c.",
  TUB/TUF) and no longer reads "atto di costituzione" as the Costituzione.
  Still advisory and fail-open: one block per turn at most, "fuori copertura"
  on the line as the escape for sources no tool covers, a stdlib fallback
  reader if the server's code does not import; about 0.25 s on a 40 MB
  transcript.
- `termini_separazione_divorzio`: the 6/12-month separation period before
  divorce is no longer extended under art. 155 c.p.c. when it ends on a
  Saturday or a holiday. It is a minimum duration (art. 3 n. 2 lett. b) L.
  898/1970), not a deadline for an act (owner's legal reading). Example: 12
  months from 15/03/2025 now end on Sunday 15/03/2026 instead of Monday
  16/03/2026. The result carries a `nota`.
- License: from 3.0.0 the project is distributed under the Mozilla Public
  License 2.0 (`LICENSE`, every manifest and `pyproject.toml`). Up to the 2.x
  line it was Apache-2.0; those releases, and the contributions received under
  that license, stay available under it (`NOTICE`, full text in
  `LICENSES/Apache-2.0.txt`, shipped in the plugin zip, the `.mcpb`, the wheel
  and the sdist).
- Packaging: `scripts/build_targets.py` builds every artifact from the
  `content/` corpus (it replaces `build-plugin.sh`, `build-dxt.sh` and
  `build-web-skills.py`) on the 2.17.0 plugin layout (`uv run --frozen
  --no-sync` from `plugin/server/uv.lock` through `bootstrap.py`). The
  claude.ai web-skills zips are built into `dist/web-skills/` and released as
  one asset.
- `orientamento_su_norma` orders sections with equal counts by section code;
  it followed the hash-seed order of a set, so two runs could disagree.
- **The August suspension says when it moved a deadline, and what it does not
  cover.** When the suspension changed the result, the nine
  deadline tools that apply it (`scadenza_processuale`,
  `termini_processuali_civili`, `scadenze_impugnazioni`, `scadenze_multe`,
  `termini_memorie_repliche`, `termini_procedimento_semplificato`,
  `termini_183_190_cpc`, `termini_deposito_atti_appello`,
  `termini_deposito_ctu`) add `avviso_sospensione_feriale`: recompute with
  `sospensione_feriale=False` if the case is excluded, and the excluded matters
  with their source (art. 3 L. 742/1969: labour and social security; art. 92
  R.D. 12/1941: alimenti, procedimenti cautelari, amministrazione di sostegno,
  interdizione e inabilitazione, ordini di protezione, sfratto, opposizione
  all'esecuzione, dichiarazione e revoca dei fallimenti, materia corporativa,
  cases declared urgent). When it changed nothing there is no notice. The fixed
  sentence on exclusions that `termini_memorie_repliche` and
  `termini_procedimento_semplificato` appended to every answer is gone; the
  `scadenza` command and the `procedura-civile` reference carry the same list.
  `termini_esecuzioni` keeps computing the art. 617 opposition without the
  suspension (the prudent reading) and, when August falls in its 20 days, adds
  `avvertenza_sospensione_feriale`: whether art. 617 is excluded is debated,
  since art. 92 R.D. 12/1941 names only the "opposizione all'esecuzione".

### Removed
- `termini_esecuzioni(tipo="opposizione_esecuzione")`: the art. 617 c.p.c.
  term (opposizione agli atti esecutivi) is `tipo="opposizione_atti_esecutivi"`.
  The old name read as art. 615 and now returns an error listing the accepted
  values.
- The `src` import package and the repository-root `src` symlink (see
  Changed).

### Fixed
- **`cite_law` with the act written first.** `"D.Lgs. 196/2003 art. 13"` was
  read as an act name: the decree resolved, the article was dropped and the
  answer was art. 1 of the Codice privacy, with no warning. Same for
  `"D.Lgs. 36/2023 allegato I.1 art. 1"`. The act-first form is now parsed like
  the article-first one; a reference naming an article that cannot be told
  apart from the act is refused with the expected-format error. The parser is
  linear in its input (it was cubic on runs of whitespace). Shared by every
  tool that uses the reference parser.
- **`cite_law` reads constitutional laws, royal decree-laws and lieutenancy
  decrees** written inside a citation ("art. 1 l. cost. 3/2001" answered "atto
  non riconosciuto"): `l. cost.` / `legge costituzionale`, `r.d.l.` / `regio
  decreto-legge`, `d.l.lgt.` / `d.lgs.lgt.` now resolve to `legge.costituzionale`,
  `regio.decreto.legge` and `decreto.legislativo.luogotenenziale`, and the
  citation gate never reads their numbers as decisions.
- **A range of articles is refused.** "art. 3-5 c.c." (also "3 - 5", "3–5",
  "artt. 3-5") became `~art35`: the library API returned the URN of art. 35 as
  "trovato". `cite_law`, `fetch_law_article` and the API now answer "chiedere
  un articolo alla volta".
- **`verifica_citazioni` and other courts.** "Corte cost. n. 238/2014" and
  "Cons. St. n. 1/2020" were looked up on Italgiure as Cassazione and reported
  "inesistente". Corte costituzionale decisions are now checked on the Court's
  archive; Consiglio di Stato, TAR, CGUE, Corte dei conti, Corte EDU, tax and
  merits courts (giudice di pace included) are "non verificabile", with the
  tool to search them.
- Content: the non-cumulation of mora and revaluation is art. 1224 co. 2 c.c.
  (Cass. SS.UU. 19499/2008), not SS.UU. 16601/2017; giudice di pace 10.000 /
  25.000 euro (art. 7 c.p.c.); conclusionali and repliche under art. 189 (not
  the old art. 190); compensatory interest not on the fully revalued sum.
- The disposizioni di attuazione del c.p.c. are dated 18/12/1941 (R.D. n.
  1368) in citations and URNs, not 25/08/1941; a test cross-checks the dates of
  every code across the three tables that state them.
- Deadline tools: `giorno_settimana` is always the Italian name. It came from
  `strftime("%A")`, which follows the process locale, so the same output mixed
  «lunedì» and «Monday».
- The annex parser (`split_annex`) ran in exponential time on a long article
  string (20 characters: 0.44 s, x4 every 2 more); it is linear now.
- `cerca_brocardi` declares Italgiure among its online sources. Its probe of
  the archive window was missed by the sources audit (a call made through a
  module that only imports the function), so `_meta` listed `italgiure` under
  `non_dichiarate`. The audit now follows such calls.
- Corte costituzionale with `LEGAL_CACHE=off`: each decade bundle (~56 MB) is
  downloaded once per process and kept in memory (cap 256 MB, same 7-day expiry
  as the disk cache), instead of on every call; concurrent calls share one
  download.
- `esporta_atto_docx`: numbered lists keep the typed numbers, `**`/`*` in
  headings and `***x***` no longer leak asterisks, the title heads every page.
  `genera_procura_liti_docx` cites "Regolamento (UE) 2016/679";
  `indice_documenti` returns an error for non-numeric or negative pages instead
  of raising.
- Importing `mcp_legal_it.tools.legal_citations` first no longer fails on a
  circular import (library callers, single test files).
- `.mcpb` and the OpenAI config pin `fastmcp>=3.4,<4` (the floor was 2.0, older
  than the FastMCP the server needs). The extension's uv environment is rebuilt
  once, on the first start of 3.0.
- Distribution: the citation-gate hook starts with `uv run --no-sync`; the
  plugin zip and the `.mcpb` no longer ship `*.egg-info`, `.DS_Store` or key
  files; `scripts/corpus/extract_references.py` explains that the migration is
  done instead of crashing.
- Live gates realigned with their sources: CeRDEF unknown GUID is `not_found`,
  INPS reworded the ex-ENPALS split, Normattiva alternates "è"/"e'".
- **Appellee's deadline: 20 days before the hearing, not 70.**
  `termini_deposito_atti_appello` computed the comparsa of the appellee (and so
  the cross-appeal deadline, a decadenza under art. 343 c.p.c.) 70 days before the hearing, through art. 166. Art. 347 co. 1 c.p.c.
  as amended by D.Lgs. 164/2024 reads "almeno venti giorni prima dell'udienza",
  and art. 7 co. 1 of that decree applies it to proceedings introduced after
  28/02/2023. The tool counts 20 days back (August suspension and art. 155
  anticipation as before), cites art. 347 co. 1 and art. 343, and adds
  `avvertenza_regime_transitorio` for appeals introduced between 28/02/2023 and
  26/11/2024 (in that window art. 347 pointed to the 70 days of art. 166:
  whether the 20 days apply backwards is for the lawyer to assess); the warning
  also appears when the notification date of the citation is not given. The 70
  days of the first-instance comparsa (art. 166) are unchanged.
- **D.M. 55/2014 minimums and maximums are the exact half and the exact one and
  a half of the medium, to the cent.** Art. 4 co. 1 lets the
  medium be reduced "in ogni caso non oltre il 50 per cento" and increased
  "fino al 50 per cento". The table rounded them to the euro (42 of 94 minimums
  and 44 of 94 maximums: 131 → 66 and 197 instead of 65,50 and 196,50);
  `parametri_forensi.json` and the minimums and maximums computed in code now
  carry the exact values. Affected at `livello='min'` and `'max'`:
  `parcella_avvocato_civile`, `parcella_avvocato_penale`,
  `parcella_stragiudiziale`, `parcella_volontaria_giurisdizione`,
  `preventivo_civile`, `preventivo_stragiudiziale`,
  `preventivo_volontaria_giurisdizione`, `calcolo_notula_penale`,
  `modello_notula`. The medium stays rounded to the euro.

### Security
- **`leggi_sentenza_cgue` fetches only CELLAR.** The `cellar_uri` came from
  the caller and was fetched as is: on the HTTP transport any client could read
  pages reachable from the server (localhost, cloud metadata, intranet). Only
  `http(s)://publications.europa.eu/resource/...` is accepted, refused as
  `bad_input` before any request, and a redirect may not leave CELLAR.
- **Italgiure over verified TLS.** The server sends the wrong intermediate
  certificates, so the client ran with `verify=False`. The missing one ("TI
  Trust Technologies OV CA", signed by the USERTrust RSA root in certifi)
  ships in `lib/italgiure/ti_trust_ov_ca.crt`, is checked against its SHA-256
  pin every time the TLS context is built, and is added to certifi's roots; a
  test fails on any `verify=False` in the package and raises a renewal alarm
  180 days before the intermediate expires (2029-07-29).
- `lib/_egress.is_allowed` refuses a backslash, a control character,
  credentials and any scheme but http(s), the URLs a browser and Python read as
  different hosts.
- **Generated documents are private.** Procure, quotazioni, atti, supplier
  reports and law PDFs are saved to `<tempdir>/mcp-legal-it` created 0700 (on
  Linux it was a world-readable `/tmp/mcp-legal-it`); a symlink or a folder
  owned by another user is refused. `esporta_atto_docx` used a hard-coded
  `/tmp`.
- The Docker image runs as an unprivileged user (uid 10001). An `mcp-cache`
  volume created by an older image is root-owned: chown or recreate it, or the
  server runs without the disk cache.
- `certifi` 2026.10.19 in the plugin lock (2026.10.18 is affected by
  PYSEC-2026-4320).
