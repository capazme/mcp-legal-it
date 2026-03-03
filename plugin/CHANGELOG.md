# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-03-03

### Added
- overhaul install.py with CLI flags, plugin support, updated profiles

### Fixed
- use venv python for pytest in release.py
- marketplace add path should point to repo root, not plugin subdir

### Other
- feature/update-installer into develop
- improve release.py with version sync, CHANGELOG, plugin-only mode
- update installer and mcp config
- add comprehensive project documentation and release tooling
- main (v0.3.0) back into develop

## [1.0.0] - 2026-02-26

### Added
- Initial release of the `legal-it` Claude Code plugin
- `.claude-plugin/plugin.json` manifest
- `.mcp.json` SSE connection to remote server (161 tools)
- 17 skills (workflow guidati):
  - 5 existing: `parere-legale`, `analisi-norma`, `analisi-giurisprudenziale`, `recupero-credito`, `sinistro`
  - 10 from MCP prompts: `causa-civile`, `pianificazione-successione`, `quantificazione-danni`, `calcolo-parcella`, `verifica-prescrizione`, `ricerca-normativa`, `analisi-articolo`, `confronto-norme`, `mappatura-normativa`, `compliance-privacy`
  - 2 new: `data-breach`, `redazione-contratto`
- 3 agents: `civilista`, `penalista`, `privacy-specialist`
- Legal Grounding Protocol hooks (Stop + SessionStart)
- `settings.json` with recommended MCP permissions
- README with full catalog and usage examples
