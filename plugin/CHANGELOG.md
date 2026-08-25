# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- OpenAI bundle (`scripts/build_targets.py openai openai-zip`) — 40 skills
  (28 corpus + 6 agents + 6 commands merged as skills; `cookie-audit` and
  `esporta-documento` excluded — the latter ships `${CLAUDE_PLUGIN_ROOT}`
  paths, structurally broken outside Claude) plus a generated `AGENTS.md`
  and `config.toml.example`, packaged as
  `legal-it-openai-skills-{version}.zip` and attached to GitHub Releases.
  Install guide: `docs/openai.md`.

### Changed
- Corpus consolidation (v3 phase 1): skills/agents/commands moved to `content/`
  as the single source; `plugin/` subtrees and `src/prompts.py` are now
  generated projections (`scripts/corpus/`). 7 prompt-only workflows promoted
  to skills (23 → 30). 12 of 15 static resources extracted to
  `content/references/`. MCP surface unchanged: 218 tools, 23 prompts,
  15 resources. I corpi dei 23 prompt MCP derivano ora dai corpi delle skill
  e per 13 workflow sono più sintetici dei precedenti; nomi, firme e
  descrizioni sono invariati. I web-skills ZIP non sono più versionati
  (plugin/dist è build output; si rigenerano con `python scripts/build_targets.py claude-web`).
- `scripts/build_targets.py` is now the single builder for every distribution
  target (`claude-code`, `claude-web`, `plugin-zip`, `mcpb`), replacing
  `scripts/build-all.sh`, `scripts/build-plugin.sh`, `scripts/build-dxt.sh`
  and `plugin/build-web-skills.py`, which are removed.

## [2.12.1] - 2026-08-24

### Added
- `cite_law()` resolves far more references: acts cited by name (Statuto dei
  lavoratori, legge fallimentare, TUEL, statuto del contribuente, legge
  Gelli-Bianco, Jobs Act and ~75 more), the EU treaties (TFUE, TUE, CDFUE),
  and 21 EU compliance acts by acronym (DSA, DMA, Data Act, eIDAS, MiCA,
  CSRD, CSDDD, PSD2, NIS...).
- More ways to write a citation: `legge 241/1990`, `legge n. 241 del 1990`,
  `reg. (UE) 2016/679`, `direttiva 95/46/CE`, `art. 111 della Costituzione`,
  `t.u.e.l.`, `art. 2, comma 1, lett. a), del d.lgs. 231/2001`.
- An unrecognised act name now comes back with the closest matches instead of
  a bare error.

### Fixed
- Articles carrying a separate rubric came back as the heading alone.
- EU treaties could not be retrieved at all.
- `codice del Terzo settore` resolved to a wrong URN.

## [2.12.0] - 2026-08-24

### Added
- ogni tabella di dati dichiara la propria provenienza e il periodo che copre, e
  i 65 tool che ne usano una la stampano accanto al risultato: «tassi legali:
  copre fino al 31/12/2026 (DM MEF 10 dicembre 2025)». Le 8 tabelle la cui
  provenienza non e' ancora accertata lo dicono esplicitamente invece di tacere
- `SECURITY.md` risponde alle domande di chi valuta il plugin prima di usarlo su
  pratiche vere: nessuna telemetria, elenco completo degli host contattati, cosa
  contengono le configurazioni annidate, come forkare e restare indipendenti

### Fixed
- la skill `esporta-documento` indicava per il PDF il venv locale dell'autore,
  che su nessun'altra macchina esiste: ora usa `uv`, gia' prerequisito del plugin
- il gate citazioni scattava su «costi», «costo» e «costante», letti come
  Costituzione, e su norme citate dentro blocchi di codice — un esempio di output
  non e' un'affermazione giuridica
- il gate riconosceva solo `art. N`: `articolo 2043 del codice civile` e
  `artt. 536 e 544 c.c.` passavano inosservati, e una `cite_law()` scritta per
  esteso non copriva la citazione che aveva appena verificato

## [2.11.1] - 2026-08-15

### Fixed
- the Desktop Extension (`.mcpb`) never started on Intel Macs: `cryptography` no longer
  ships macOS x86_64 wheels, so the install tried to compile it from source and the
  server stayed "disconnected". Pinned below 49 on that platform only
- corrected the 2025 FOI index series, which was about one point too high and made every
  rivalutazione and rent adjustment disagree with the official ISTAT figures published
  in Gazzetta Ufficiale
- TAR/CdS search works again after the 2026 reorganisation of the giustizia-amministrativa
  portal
- documentation now matches the code: the tool catalogue was missing 56 of the 218 tools,
  and the skill, agent and hook lists named entries that no longer exist

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
- **Rimossi tre file di dipendenze orfani** — `requirements.txt`, `requirements.lock`, `dxt/start_server.sh`. Nessun percorso di installazione li usava, ma due avevano perso `python-docx`: chi installava da lì otteneva i tool procura/quotazione rotti all'import. `pyproject.toml` è ora l'unica fonte di verità. Verificato con `pip-audit`: tutti i percorsi reali risolvono a 0 vulnerabilità note (issue #25).

### Fixed
- **Vincolo `fastmcp` uniformato a `>=2.0,<4`** in tutti e cinque i punti di dichiarazione. Era illimitato in tre di essi: l'uscita di fastmcp 4.0 avrebbe rotto Docker e il fallback venv (sandbox Cowork) lasciando il plugin fermo. Nessuna modifica funzionale — 216 tool e 23 prompt registrati su fastmcp 3.4.5.

### Added
- **Controlli automatici sulle dipendenze in CI** — `scripts/check_deps_sync.py` blocca la PR quando un launcher diverge da `pyproject.toml`, e il workflow `security-audit.yml` esegue `pip-audit` su ogni PR e ogni lunedì.

## [2.10.0] - 2026-07-23

### Added
- **Tool `genera_procura_liti_docx` + `genera_quotazione_docx`** (nuovo modulo `procure_quotazioni`) — recupero crediti seriale: procura alle liti ex art. 83, co. 3, c.p.c. in DOCX pronta-firma (una pagina, dichiarazioni mediazione/negoziazione/privacy, autentica difensori) e lettera di quotazione compensi D.M. 55/2014 (agg. D.M. 147/2022) con prospetto completo (+30% PCT, SG 15%, CPA 4%, IVA 22%, R.A. 20%), contributo unificato automatico dalla tabella canonica (monitorio dimezzato ex art. 13, co. 3, DPR 115/2002), nota imposta di registro e blocco di accettazione del cliente. Tre tipi per fase reale: `monitorio` (fase unica), `esecuzione` (con oneri pignoramento), `opposizione` (quattro fasi di cognizione).
- **Skill `procure-quotazioni`** — orchestrazione del flusso seriale: lettura Excel posizioni, normalizzazione importi, classificazione della fase processuale, clausola debitore verbatim dagli atti, generazione per posizione e report finale. Config studio locale (`studio.json`, esempio incluso). Ora: **216 tool / 22 skill / 8 slash command / 6 agenti**.

## [2.9.0] - 2026-07-14

### Added
- **Skill `cookie-audit`** — audit forense dei cookie/tracker di un sito: stato pre/post-consenso in contesto pulito, fingerprint di CMP e tracker di terze parti, ispezione del container GTM reale lato server, tabella cookie completa, valutazione di conformità (Provv. Garante 10/6/2021, GDPR, art. 122 Codice Privacy, ePrivacy), report Word + remediation. Ora: **214 tool / 21 skill / 8 slash command / 6 agenti**.

### Fixed
- **`cite_law` / `fetch_law_article`: risolte le preleggi.** `art. 12 preleggi` restituiva l'art. 12 (abrogato) del corpo del codice civile invece della regola di interpretazione. L'export AKN del c.c. contiene le preleggi come parte component separata che il parser scartava a favore del corpo (~3249 art.); ora il parser espone tutte le parti e seleziona quella delle preleggi quando `tipo_atto=preleggi`, senza toccare i lookup c.c./c.p. Aggiunti gli alias `disp. prel. c.c.`, `disposizioni sulla legge in generale`, `disposizioni preliminari (al/del) codice civile`.

## [2.8.0] - 2026-07-01

### Removed
- **Consolidamento superficie ridondante.** Rimossi 5 slash-command alias di skill esistenti (`/parere`, `/compliance`, `/giurisprudenza`, `/parcella`, `/ricerca` — usa le skill equivalenti) e la skill `digest-giuridico` (sostituita da `/digest` + agente `digest-giuridico`). Nessuna funzione persa. Ora: **20 skill / 8 slash command / 6 agenti**.

## [2.7.9] - 2026-07-01

### Fixed
- **Citation `Stop` hook: from `prompt` (LLM) to deterministic.** The LLM gate over-fired (hallucinated citations, re-flagged already-verified norms) and cost tokens every turn. Replaced with `hooks/citation-gate.py` that dedups article-level citations against the session's `cite_law()` calls.

## [2.7.8] - 2026-06-23

### Fixed
- **`.mcpb` now installs on Windows.** `dxt/manifest.json` `platforms` was `["darwin","linux"]` → Claude Desktop on Windows refused it. Added `"win32"`. The bundle uses `uv` directly (no `bash`), so it's cross-platform. Windows confirmation pending. Reported by @giovannizanotto.

## [2.7.7] - 2026-06-23

### Fixed
- **`.mcpb` Desktop Extension was broken — never started.** The bundle ships the server under `server/`, but `dxt/manifest.json` ran `${__dirname}/run_server.py` (root) → `Failed to spawn … No such file or directory`. Fixed to `${__dirname}/server/run_server.py`. Rebuilt + smoke-tested: 214 tools. **Use 2.7.7+; the 2.7.6 `.mcpb` is unusable.**

### Docs
- Windows `uv` command corrected (needs `powershell -ExecutionPolicy ByPass -c "…"`). Documented that Cowork (cloud agent) doesn't run local MCP servers → use the `.mcpb` or the CLI. Refreshed counts (214/21/13/6).

## [2.7.6] - 2026-06-23

### Fixed
- **Marketplace install on Claude Desktop Cowork — the actual regression.** Bisected from "≤2.6.1 worked": the only breaking change was 2.6.2 switching the marketplace `.mcp.json` command from `bash start_server.sh` to `uv`. Cowork accepts `bash` but not `uv`, so every sync since 2.6.2 returned `failed_content`. Reverted `.mcp.json` to `command: bash` and hardened `start_server.sh` to prefer `uv` when present (Mac/Linux/Git-Bash, Python 3.12) and fall back to a system-Python venv (the Cowork-compatible 2.6.1 path). Smoke-tested: boots and registers all 214 tools.
- **Windows** keeps the `uv` path via the `.mcpb` Desktop Extension (unchanged) — install via the `.mcpb`, not the marketplace.

### Note
- The 2.7.3–2.7.5 changes were real corrections but **not** the Cowork blocker (those fields/hooks were already present at 2.6.1 when Cowork worked). Kept as hygiene / CLI-schema improvements.

## [2.7.5] - 2026-06-23

### Fixed
- **Marketplace install `failed_content` — schema conformance (the actual blocker).** Components carried fields outside their closed schema, rejecting the whole bundle:
  - **Skills (21):** dropped `argument-hint` (command-only field, not in the Agent Skills schema) and `allowed-tools` from every `SKILL.md` → canonical `name` + `description`.
  - **Agents (6):** added required `name` + `color`; removed invalid `allowed-tools` (agent schema uses `tools`).
  - **Hooks:** removed the unsupported `SessionStart` prompt hook and the undocumented `model` key on the Stop hook (Legal Grounding Stop hook otherwise unchanged).
  - **Command:** `release.md` `argument-hint` `<versione>` → `[versione]`.

## [2.7.4] - 2026-06-23

### Fixed
- **Marketplace install `failed_content` — real root cause.** `commands/parcella.md` had invalid YAML frontmatter (`argument-hint` with unquoted `[...]` brackets), introduced by the 2.7.0 content audit. The marketplace validator parses every command's frontmatter as YAML, so this single malformed file failed whole-plugin validation on every fresh sync. Quoted the value to match the other 12 commands / 21 skills. (The 2.7.3 `.gitattributes` change stays as archive hygiene but was not the cause.)

## [2.7.3] - 2026-06-23

### Fixed
- Marketplace remote sync `failed_content` on Claude Desktop (Cowork): the validator rejected the repo tarball over the tracked root `src` symlink (sandboxed extractors refuse symlinks) and the 14 MB AKN test fixtures (archive 19 MB, 6× the working peers). Added `.gitattributes` `export-ignore` for `/src` and `/tests` — GitHub's generated tarball now excludes both (2.0 MB → 0.5 MB, symlink-free). No impact on local dev/test/Docker: real checkouts ignore `export-ignore`.

## [2.7.2] - 2026-06-23

### Removed
- Obsolete duplicate `.claude/` skills (5) and agents (3) shadowing the canonical `plugin/` versions; stale `tool-catalog.md`. Skill count corrected to 21.

## [2.7.1] - 2026-06-23

### Fixed
- Legal-figures audit (fonti: avvocatoandreani.it + ufficiali): valore catastale (corretto il doppio 5% + `prima_casa` + `+20%` DL 168/2004 compravendita); `offerta_conciliativa` (cap 6 abrogato da Corte Cost. 118/2025 → 13,5, dimezzamento mantenuto); disclaimer L. 132/2025 → art. 15; `analisi_sinistro` (danno non patrimoniale unitario SU 26972/2008 + interessi su base media SU 1712/1995).

## [2.7.0] - 2026-06-18

### Changed
- Content audit & refine: skill/command/agent markdown realigned to the real 214 tools; legal figures verified against official sources (decision register in `docs/_audit/TRIAGE-RESOLUTION.md`). 3 items flagged for the lawyer's sign-off.

### Fixed
- `verifica_citazioni` number/year mismatch rejection; data-breach DPO checklist truthfulness; quorum fail-closed; CeRDEF date format; input validations.
- Security: Brocardi cache dir created `mode=0o700` (owner-only).

## [2.6.2] - 2026-06-15

### Fixed
- Plugin MCP server now launches via `uv` (cross-platform) instead of `bash start_server.sh` — fixes the server not starting on Windows and on macOS with Python 3.14. New prerequisite: `uv` (one-line install, see README).

## [2.6.1] - 2026-06-15

### Fixed
- Brocardi annotations 404: self-healing URL cache (re-resolves a stale 404 entry instead of failing).
- Orientamento output: no more duplicated `sez.` for Sezioni Unite (`sez. un.`).

## [2.6.0] - 2026-06-15

### Added
- 4 guided prompt workflows (23 total): `analisi_costituzionale`, `ricerca_gazzetta`, `orientamento_giurisprudenziale` (descriptive, L. 132/2025), `attuazione_direttiva` (EU→IT recepimento).

## [2.5.0] - 2026-06-15

### Added
- `verifica_citazioni` — verifies a list of references (sentenze + articoli), flagging non-existent / not-verifiable / metadata-mismatch citations.
- Corte Costituzionale (4 tools) via the official open-data dumps; Gazzetta Ufficiale (5 tools, RSS + HTML + ELI + PDF); `orientamento_giurisprudenziale` (3 tools, descriptive, L. 132/2025); EU→IT implementation mapping (3 tools, CELLAR).
- Cowork: `digest-giuridico` weekly briefing (agent + command + skill); `esporta-documento` (DOCX/PDF) skill; `parere`/`giurisprudenza`/`compliance` slash commands; `cowork` profile.

### Changed
- 198 → 214 tools; manifests re-tallied to 214 tools / 22 skills / 13 commands / 6 agents.

## [2.4.1] - 2026-06-15

### Fixed
- Version metadata consistency across all distribution manifests and changelogs (the 2.4.0 `.mcpb` was built from stale 2.3.3 manifests).

## [2.4.0] - 2026-06-15

### Added
- AKN XML fetch path for Normattiva (`akn_parser.py`, `akn_fetch.py`): official Akoma Ntoso 3.0 export via `caricaAKN` instead of per-article HTML scraping, with automatic HTML fallback. Handles flat and component (codici) structures, resolves `<ins>`/`<del>`, strips `(( ))` markers.
- Bounded LRU + on-disk parsed-act cache with a URL→params index so warm hits skip the landing page (0 network for the 2nd+ article of the same act).
- `AKN_DISABLED` env var to force the legacy HTML path; 60 new unit tests + benchmark harness.

### Changed
- `fetch_article` and `fetch_normattiva_full_text` route AKN-first with HTML fallback (public tool signatures unchanged).

### Performance
- Full-text retrieval 8–37x faster (1 request vs 33–158) and more complete than the HTML walker (e.g. L. 241/1990: 51 vs 32 articles).

## [2.3.3] - 2026-04-13

### Added
- Italgiure search improvements: query normalization, zero-result fallback, smart explore suggestions
- `leggi_sentenza` fallback chain for better sentence lookup reliability
- 38 new unit tests

### Changed
- Improved tool docstrings with anti-patterns and best practice examples

## [2.3.2] - 2026-04-01

### Fixed
- Removed nested `.zip` files that blocked plugin installation in Claude Desktop
- `start_server.sh`: Python discovery tries `python3.12`/`python3.11`/`python3.10` before `python3` (fixes Conda environments)

## [2.3.1] - 2026-04-01

### Fixed
- All manifest descriptions now correctly report 198 tools
- Release automation: pre-tag verification prevents version/description misalignment

## [2.1.0] - 2026-03-17

### Added
- CeRDEF: 3 tools for Italian tax case law (def.finanze.it)
- Giustizia Amministrativa: 4 tools for TAR/CdS case law (giustizia-amministrativa.it)
- CGUE: 4 tools for EU Court of Justice case law via CELLAR SPARQL
- 3 new prompts: analisi_tributaria, analisi_giurisprudenza_amministrativa, analisi_giurisprudenza_europea
- 3 new resources: cerdef-giurisprudenza, giustizia-amministrativa, cgue-giurisprudenza

### Changed
- Tool count: 166 → 177
- Prompt count: 16 → 19

## [2.0.1] - 2026-03-17

### Added
- `.mcp.json` restored — plugin now auto-starts the MCP server via `start_server.sh`
- Works in both Claude Code CLI and Claude Desktop Cowork (via GitHub marketplace)
- `manifest.json` (mcpb) for Desktop Extension packaging

### Fixed
- Plugin README updated: correct tool count (166), skill count (19), agent count (5)
- Removed debug scripts from distribution

## [2.0.0] - 2026-03-16

### Changed
- **BREAKING**: Dual entry point — plugin for skills/agents/hooks, DXT for MCP server
- Server code moved to `plugin/server/` — plugin is fully self-contained
- Plugin provides: 19 skills, 8 commands, 5 agents, hooks (Legal Grounding Protocol)
- DXT provides: 166 MCP tools, 16 prompts, 10 resources

## [1.6.1] - 2026-03-16

### Fixed
- Venv created in `MCP_CACHE_DIR` (writable) instead of plugin dir (read-only in Cowork sandbox)
- Removed `2>/dev/null` from `python3 -m venv` call — errors are now visible for debugging

## [1.6.0] - 2026-03-16

### Changed
- SessionStart hook auto-configures `claude_desktop_config.json` with the MCP server entry
- On first plugin session, the hook creates venv, installs deps, and registers the server in Sviluppatore
- Subsequent sessions skip if already configured (idempotent)
- Reverted to stdio transport (SSE/HTTPS dropped — connectors require valid SSL certs)
- `.mcp.json` restored to stdio for Claude Code CLI compatibility

## [1.5.0] - 2026-03-16

### Changed
- MCP server now uses SSE transport on localhost:8000 instead of stdio
- SessionStart hook auto-starts the SSE daemon in background
- `start_server.sh` supports `--daemon` flag for background SSE mode
- `run_server.py` updated for FastMCP 3.x SSE API (`mcp.run(transport="sse")`)
- Co-work compatible: hook starts server, `.mcp.json` connects via SSE

## [1.4.1] - 2026-03-16

### Fixed
- DXT build (`build-dxt.sh`) now includes `start_server.sh` and server code in `server/` subdir
- Previously the .mcpb package was missing the bootstrap script, causing "No such file or directory" in Claude Desktop

## [1.4.0] - 2026-03-16

### Changed
- Server code (`src/`, `run_server.py`) moved inside `plugin/server/` — plugin is now fully self-contained
- Root `src` is a symlink to `plugin/server/src` for dev/test/Docker retrocompatibility
- Root `run_server.py` is a thin wrapper delegating to `plugin/server/run_server.py`
- `pyproject.toml` copied to `plugin/server/` for standalone install
- Dockerfile and build scripts updated to reference new paths
- Co-work / marketplace install now includes MCP server without needing repo root

## [1.3.8] - 2026-03-16

### Fixed
- Restored `legal-it:` prefix on tool names in skill/agent/command body text — Claude Desktop needs the MCP server prefix to resolve tools correctly
- v1.3.6 removal of prefix caused "No such tool available" errors; ToolSearch with prefix is cosmetic only (tools still work)
- Combined with v1.3.7 frontmatter (`allowed-tools`, `argument-hint`, `description`) for optimal behavior

## [1.3.7] - 2026-03-16

### Fixed
- Added `allowed-tools` frontmatter to all 19 skills and 8 commands — pre-authorizes MCP tools, prevents ToolSearch lookups
- Added `argument-hint` frontmatter to all 18 skills missing it (restored from v1.0.2)
- Added `description` frontmatter to all 5 agents — enables proper delegation routing
- Removed `## Tool utilizzati` / `## Tool principali` / `## Tool disponibili` sections from skills and agents — these caused ToolSearch triggers when Claude parsed tool names in body text

## [1.3.6] - 2026-03-16

### Fixed
- Removed `legal-it:` prefix from all tool references in skills, commands, and agents
- Tool references like `legal-it:cite_law` triggered ToolSearch in newer Claude Desktop versions, causing "No matching deferred tools found"
- Reverted to bare function names (`cite_law`, `cerca_giurisprudenza`, etc.) which Claude resolves directly to MCP tools

## [1.1.1] - 2026-03-15

### Fixed
- Author: gpuzio → capazme in all manifests (plugin.json, marketplace.json, dxt/manifest.json)
- marketplace.json description updated to 164 tool
- README updated with correct tool count, skills, commands, and links
- CHANGELOG cleaned up (removed duplicate entries)
- Version aligned across all manifests (pyproject.toml, dxt/manifest.json, plugin.json)
- Web skills ZIP regenerated (added analisi-delibere-consob, novita-consob)

## [1.1.0] - 2026-03-08

### Added
- CONSOB integration: 3 new tools (`cerca_delibere_consob`, `leggi_delibera_consob`, `ultime_delibere_consob`)
- CONSOB scraper (`src/lib/consob/client.py`)
- 2 new skills: `analisi-delibere-consob`, `novita-consob`
- 2 new prompts: `analisi_delibere_consob`, `novita_consob`
- Desktop Extension (DXT) support: `dxt/manifest.json`, `dxt/start_server.sh`
- Build scripts: `scripts/build-dxt.sh`, `scripts/build-plugin.sh`, `scripts/build-all.sh`
- GitHub Actions release workflow (`.github/workflows/release.yml`)
- 8 slash commands: norma, sentenza, ricerca, interessi, parcella, codice-fiscale, scadenza, privacy
- Distributable `.mcp.dist.json` with `${CLAUDE_PLUGIN_ROOT}` variable

### Changed
- Tool count: 161 → 164
- Skill count: 17 → 18 (renamed analisi-norma → analisi-articolo externally, added CONSOB skills)
- All agents updated with `legal-it:` tool-qualified references
- Docker support: added `MCP_PATH_PREFIX` for reverse proxy deployment

## [1.0.0] - 2026-02-26

### Added
- Initial release of the `legal-it` Claude Code plugin
- `.claude-plugin/plugin.json` manifest
- `.mcp.json` MCP server connection (161 tools)
- 17 skills (workflow guidati):
  - 5 existing: `parere-legale`, `analisi-norma`, `analisi-giurisprudenziale`, `recupero-credito`, `sinistro`
  - 10 from MCP prompts: `causa-civile`, `pianificazione-successione`, `quantificazione-danni`, `calcolo-parcella`, `verifica-prescrizione`, `ricerca-normativa`, `analisi-articolo`, `confronto-norme`, `mappatura-normativa`, `compliance-privacy`
  - 2 new: `data-breach`, `redazione-contratto`
- 3 agents: `civilista`, `penalista`, `privacy-specialist`
- Legal Grounding Protocol hooks (Stop + SessionStart)
- `settings.json` with recommended MCP permissions
- README with full catalog and usage examples
