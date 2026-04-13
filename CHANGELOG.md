# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
