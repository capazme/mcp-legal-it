# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `stato_server()`: the diagnostics tool that tells the caller WHAT it is
  talking to — package version of the running code, active tool count after
  the `LEGAL_PROFILE` filter, pinned clock, cache switch and directory,
  hostname. Modeled on the `get_quota_status` / `check_capabilities` pattern
  of the Scopus MCP servers; the declared total is derived from the audited
  annotation policy, so it cannot drift into a second handwritten count.
  Surface is now 228 tools (210 read-only, 170 local-only).

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
