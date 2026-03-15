# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-03-15

### Added
- new resource `legal://riferimenti/ricerca-giurisprudenziale` — Italgiure search guide
- `/health` endpoint for SSE transport (liveness probe)
- cross-reference section in `consob-delibere` resource
- Passo 7 cross-reference CONSOB/Garante in ricerca-giurisprudenziale agent
- prompt regression tests (`tests/unit/test_prompts.py`)
- pytest step in CI release workflow (fail-fast)

### Changed
- `analisi_delibere_consob` Fase 4: esplora→filtra strategy for giurisprudenza
- `parere_legale` sez. 3.2: Italgiure search with esplora strategy
- privacy-specialist agent: esplora strategy rules for giurisprudenza
- tool-catalog: enriched `giurisprudenza_su_norma` description with parameters

### Fixed
- removed duplicate CHANGELOG entry for 0.3.1

## [0.3.1] - 2026-03-03

### Added
- overhaul install.py with CLI flags, plugin support, updated profiles

### Fixed
- use git add -f for dist files ignored by .gitignore
- use venv python for pytest in release.py
- marketplace add path should point to repo root, not plugin subdir

### Other
- feature/update-installer into develop
- improve release.py with version sync, CHANGELOG, plugin-only mode
- update installer and mcp config
- add comprehensive project documentation and release tooling
- main (v0.3.0) back into develop

