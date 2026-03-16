# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
