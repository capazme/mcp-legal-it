# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
