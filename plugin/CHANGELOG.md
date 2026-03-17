# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
