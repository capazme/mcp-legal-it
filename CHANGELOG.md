# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
