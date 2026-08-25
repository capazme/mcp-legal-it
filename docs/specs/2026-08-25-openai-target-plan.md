# Phase 3 — OpenAI Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A distributable OpenAI bundle — `dist/openai/` with `.agents/skills/` (43 skills: 30 corpus + 6 role-skills from agents + 7 command-skills), a generated `AGENTS.md`, a `config.toml.example` and a bundle README — built by `build_targets.py openai` and zipped by `openai-zip`, attached to GitHub Releases automatically.

**Architecture:** The Phase-2 manifest/engine carry the whole weight: a new `openai` projection block (supports: [skills], `merge_into_skills` for agents/commands, per-target description cap, exclusions) plus a supports-aware `project()`. Bodies keep BARE tool names — the only spelling stable across Codex's two MCP naming modes (`mcp__server__tool` / `server__tool`, PR #21576; the colon form never existed in current Codex). No committed projection: `dist/openai/` is build output; determinism is tested, not drift-gated.

**Tech Stack:** Phase-2 toolkit (targets.py, project_claude.py, build_targets.py). No new dependencies.

**Spec:** `docs/specs/2026-08-24-harness-agnostic-layer-design.md` (Phase 3 section), refined by the measured facts below — where they conflict, the measured facts win and the Deviations section records it.

## Global Constraints

- Branch: `feature/openai-target` (exists, from develop @ d193039). Conventional Commits + trailer `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Claude projections stay byte-identical EXCEPT the three deliberate source fixes in Task 1 (enumerated there; everything else drift-gated green at every commit).
- Test command: `uv run --python 3.12 --extra dev pytest <path> -q`; full suite before each commit that touches engine/builder.
- MCP surface unchanged: 218 tools / 23 prompts / 15 resources. Claude skills stay 30 / agents 6 / commands 8.
- release.py NOT touched. content/skills bodies NOT touched (the pre-release back-fill is a separate workstream).
- All new code/comments in English; corpus content and AGENTS.md prose in Italian (it addresses the Italian-lawyer end user).

## Measured facts this plan relies on (recon 2026-08-25, sources in the recon record)

- **Skill format** (learn.chatgpt.com/docs/build-skills): SKILL.md with `name` + `description` required, extra keys tolerated; `scripts/`, `references/`, `assets/`, `agents/` optional. `agents/openai.yaml` fully optional (UI metadata/policy/deps; no required fields).
- **Discovery**: `$CWD/.agents/skills` → parents → repo root → `$HOME/.agents/skills` → `/etc/codex/skills` → bundled. ChatGPT: direct upload in Skills UI ("including one built for or exported from Claude Code") or Plugin Directory.
- **Skills-list budget**: 2% of context, or **8,000 chars when unknown**; descriptions shortened first, skills may be omitted. Our 44 descriptions total 12,044 chars → a cap is REQUIRED: `description_max_chars: 150` ⇒ 43×150 = 6,450 max ✓.
- **MCP tool naming**: `mcp__<server>__<tool>` or `<server>__<tool>` depending on mode (PR #21576, 2026-05-26); dashes normalized to code-safe (PR #14605); hyphenated SERVER names caused "Tools: (none)" (issue #15832) → the shipped config names the server **`legal_it`**. Bodies therefore use BARE tool names — correct under every mode.
- **AGENTS.md**: global `~/.codex/AGENTS.md` then project files concatenated root→cwd, 32 KiB combined default cap.
- **Corpus adaptation** (measured per file): no name collisions among 30+6+8; agent bodies clean (bare tools) but descriptions use subagent framing ("Delega quando…"); `commands/release` is maintainer-only (Claude-builtin tools) and `commands/digest` is harness-scheduling-bound → both EXCLUDED from the bundle (→ 43 skills). Three source lines are wrong beyond Claude and get fixed at the source: `content/agents/redattore-atti.md:40` (MCP-resource routing), `content/agents/ricerca-giurisprudenziale.md:103` (hardcoded `mcp__perplexity-mcp__search`), `content/commands/sentenza.md:11` (stale `/ricerca` slash reference — a bug on Claude too).
- **Engine surface**: `project()` hard-indexes `out_map["skills"/"agents"/"commands"/"references"]` (lines 102/141/162) and rmtrees per kind — a same-dir merge needs a single up-front rmtree; `targets.py` never validates out sub-keys (a skills-only target passes load and crashes later) → validation must land WITH the supports refactor.
- **Builder/CI**: `_TARGET_NAMES`/`_expand`/`main()` slot new targets mechanically; release.yml uploads `dist/*.zip` (glob already matches `dist/legal-it-openai-skills-{v}.zip`) but its BUILD step must add the new targets.
- **Local ground truth**: `~/.agents/skills/{docx,find-skills}/SKILL.md` confirm the format (name+description, extra keys tolerated).

## File structure (end state)

```
content/
  targets.yaml                    # + projections.openai, packaging.openai-zip
  agents/*.md                     # + standalone-description: (6), 2 body-line fixes
  commands/sentenza.md            # 1 body-line fix
scripts/corpus/
  targets.py                      # supports-aware out-map validation
  project_claude.py               # supports:, merge_into_skills, exclude, description cap, single rmtree
scripts/build_targets.py          # + build_openai (projection + AGENTS.md + config example + bundle README), build_openai_zip
scripts/corpus/agents_md.py       # NEW — AGENTS.md generator (from server.py instructions + grounding protocol)
dist/openai/                      # BUILD OUTPUT (gitignored): .agents/skills/<43>/SKILL.md, AGENTS.md, config.toml.example, README.md
tests/unit/test_openai_target.py  # NEW — bundle content/determinism tests
docs/openai.md                    # NEW — install guide (Codex CLI + ChatGPT)
```

---

### Task 1: Source hygiene — 3 fixes + standalone descriptions

**Files:** Modify `content/agents/redattore-atti.md`, `content/agents/ricerca-giurisprudenziale.md`, `content/commands/sentenza.md`, all 6 `content/agents/*.md` (new frontmatter key), `scripts/corpus/project_claude.py` (strip the new key on claude), regenerated `plugin/` (3 files change — the ONLY allowed projection diffs).

**The three body fixes (exact old→new):**
1. `redattore-atti.md:40` — «- **resource**: leggi il modello dalla resource, compila i placeholder con i dati» → «- **modello**: recupera il modello con `genera_modello_atto` (su Claude puoi leggerlo anche dalla resource `legal://riferimenti/modelli-atti-catalogo`), compila i placeholder con i dati»
2. `ricerca-giurisprudenziale.md:103` — «3. Se accetta: `mcp__perplexity-mcp__search(query="giurisprudenza italiana Cassazione [tema]")`» → «3. Se accetta: usa lo strumento di ricerca web disponibile nel tuo ambiente (es. una web search MCP) con query «giurisprudenza italiana Cassazione [tema]»»
3. `sentenza.md:11` — replace the stale «suggerisci di usare `/ricerca`…» clause with «suggerisci di cercarla prima con `cerca_giurisprudenza`» (read the full line and preserve its surrounding sense).

**`standalone-description:`** — new OPTIONAL frontmatter key on the 6 agents (trigger-style, replaces the subagent «Delega…» framing when a target projects the agent as a standalone skill). Exact texts:
- civilista: «Metodologia da avvocato civilista per contratti, responsabilità civile, successioni, diritti reali, obbligazioni e famiglia. Usa per impostare analisi civilistiche rigorose con verifica delle fonti.»
- digest-giuridico: «Briefing giuridico periodico dalle ultime novità di tutte le fonti (Cassazione, tributario, TAR/CdS, CGUE, Garante, CONSOB), raggruppato per fonte con sintesi operative.»
- penalista: «Metodologia da avvocato penalista per reati, pene, prescrizione, misure cautelari e riti alternativi, con i regimi temporali della prescrizione.»
- privacy-specialist: «Metodologia GDPR e protezione dati: Codice Privacy, provvedimenti del Garante, cookie, data breach, DPIA, con verifica delle fonti.»
- redattore-atti: «Redazione di atti giudiziari e stragiudiziali italiani dal catalogo di 100 modelli: routing del tipo di atto, raccolta campi, composizione e export.»
- ricerca-giurisprudenziale: «Ricerca giurisprudenziale esperta su Italgiure (Cassazione): strategia esplora→filtra→leggi, sintassi Solr, incroci con Brocardi e fonti collegate.»

Claude projector: add `standalone-description` to the keys stripped for the claude-code target (manifest `strip_frontmatter_keys` gains it — a manifest edit, not code).

- [ ] Steps: edits → regenerate claude (`build_targets.py claude-code`) → `git diff -- plugin/` shows EXACTLY the 3 body fixes (agents ×2, commands ×1), nothing else → full suite green → commit `fix(corpus): harness-neutral wording for resource/web-search/slash references; standalone descriptions for agents`.

---

### Task 2: Engine — supports:, merge_into_skills, exclude, description cap

**Files:** `scripts/corpus/targets.py`, `scripts/corpus/project_claude.py`; tests in `tests/unit/test_corpus_projection.py` + `tests/unit/test_corpus_targets.py`.

Config contract for a projection target (all new keys optional):
- `supports: [skills]` — kinds projected; default (absent) = full claude behavior. `out` must contain a key per supported filesystem kind (`{"skills","agents","commands"} ∩ supports`), plus `references` iff `mcp_resources ∈ supports` — validated in `load_targets()` with a clean ValueError (mcp_prompts/hooks demand no out key).
- `merge_into_skills: [agents, commands]` — those kinds are projected INTO the skills out-dir, each `X.md` becoming `X/SKILL.md`; agent/command frontmatter is reduced to `name` + description where description = `standalone-description` if present else `description`; `tools:`/`model`/`color`/`argument-hint` dropped; command bodies get the same treatment as skills (tool prefixing per target namespace — identity for openai).
- `exclude: [commands/release, commands/digest]` — kind-qualified names skipped.
- `description_max_chars: 150` — applied to EVERY projected skill description (word-boundary truncation + "…", reusing the Task-4-Phase-2 web truncation helper — extract it into a shared function if needed).
- Single up-front rmtree of each DISTINCT out dir (compute the set first) so same-dir merging can't wipe earlier kinds.

Engine behavior guards stay: bare-name lint, multi-line tools guard, undeclared-name lint (agents/commands merged as skills go through the same checks). Claude-code target behavior byte-identical (drift gates green — its config gains only the `standalone-description` strip key).

- [ ] Steps: failing tests first (skills-only target with merge+exclude+cap on tmp fixtures: merged agent appears as `X/SKILL.md` with standalone description, excluded names absent, >150-char description truncated at word boundary, missing out-subkey → clean ValueError naming the kind) → implement → full suite + drift green → commit `feat(corpus): supports-aware projection with merge_into_skills, exclusions and description cap`.

---

### Task 3: Manifest — openai projection + openai-zip packaging

**Files:** `content/targets.yaml`; test additions in `tests/unit/test_corpus_targets.py`.

```yaml
  openai:
    tool_namespace: "{tool}"        # bare — stable across Codex's mcp__server__tool / server__tool modes
    strip_frontmatter_keys: [tools, prompt, standalone-description]
    supports: [skills]
    merge_into_skills: [agents, commands]
    exclude: [commands/release, commands/digest]
    description_max_chars: 150
    out:
      skills: dist/openai/.agents/skills
```
(claude-code's `strip_frontmatter_keys` gains `standalone-description` here if Task 1 hasn't already; packaging block:)
```yaml
  openai-zip:
    from: openai
    artifact: "dist/legal-it-openai-skills-{version}.zip"
    root: dist/openai
```
Pin tests: openai out dir under dist/ (gitignored — assert `git check-ignore dist/openai` true in a test comment, not code); artifact name matches release.yml's `dist/*.zip` glob.

- [ ] Steps: manifest + tests → commit `feat(build): openai projection and packaging targets in the manifest`.

---

### Task 4: Builder — build_openai + AGENTS.md generator + openai-zip

**Files:** `scripts/build_targets.py`, NEW `scripts/corpus/agents_md.py`; tests in `tests/unit/test_build_targets.py` + NEW `tests/unit/test_openai_target.py`.

- `agents_md.py`: `generate(root) -> str` assembling the Italian AGENTS.md from (a) a hand-written header block IN THE MODULE (scope: «strumenti legali italiani via MCP legal_it», Legal Grounding Protocol distilled from CLAUDE.md's section — cite_law prima di citare, leggi_sentenza per numero noto, cerca_*→leggi_* per fonte, i calcoli non richiedono cite_law), (b) the REGOLE/OUTPUT/WORKFLOW sections EXTRACTED verbatim from `plugin/server/src/server.py`'s instructions string (parse between "REGOLE:" and the closing quote — single source, no duplication), (c) a footer on tool naming («i tool compaiono come legal_it__<nome> o mcp__legal_it__<nome> secondo la modalità; nei testi delle skill sono citati col nome bare»). Deterministic output; well under 32 KiB.
- `build_openai(root)`: project openai → write `dist/openai/AGENTS.md` (from agents_md), `dist/openai/config.toml.example` (stdio `[mcp_servers.legal_it]` uv invocation mirroring plugin/.mcp.json's args + commented streamable-http `url =` variant), `dist/openai/README.md` (short: cosa contiene, installazione Codex — copy `.agents/skills` in repo o `$HOME/.agents/skills`, `codex mcp add` / config.toml, ChatGPT — upload skills + connector self-host, link a docs/openai.md).
- `build_openai_zip(root, version=None) -> Path`: zip `dist/openai/` (root per manifest) → `dist/legal-it-openai-skills-{version}.zip` (default version: root pyproject.toml). No manifest rewrite.
- `_TARGET_NAMES` += `openai`, `openai-zip` (in that order, before nothing that consumes them); main() dispatch; `all` includes both.
- Tests (`test_openai_target.py`, running the real projection into tmp via `--out`-style or direct `project(root, tmp, cfg)`): 43 skill dirs exactly; `release`/`digest` absent; every SKILL.md frontmatter = name+description only, description ≤153 chars; agent skills carry the standalone description; ZERO occurrences of `legal-it:` or `mcp__` in any body; AGENTS.md contains «REGOLE» + «cite_law» + «legal_it__»; config example contains `[mcp_servers.legal_it]`; zip member count = file count.

- [ ] Steps: failing tests → implement → full suite → `build_targets.py openai openai-zip` smoke (artifacts exist, tree clean) → commit `feat(build): openai bundle target — 43 skills, AGENTS.md, config example, zip`.

---

### Task 5: CI + docs

**Files:** `.github/workflows/release.yml` (build step adds `openai openai-zip`… actually: change the build command to `python scripts/build_targets.py mcpb plugin-zip openai openai-zip --version "$VERSION"`), NEW `docs/openai.md`, `README.md` (new «Codex CLI / ChatGPT» setup section replacing the stale CLAUDE.md-era instructions if present), `CLAUDE.md` (compat table row updates: skills column for ChatGPT/Codex ✓ via bundle), `CONTRIBUTING.md` (builder targets list), CHANGELOGs [Unreleased].

`docs/openai.md` content (Italian): installazione Codex CLI (3 vie: unzip in `$HOME/.agents/skills`; clone+copy; futuro skill-installer), server MCP (config.toml stdio uv + url variant, nome `legal_it` OBBLIGATORIO senza trattini con il perché — issue #15832), AGENTS.md (dove metterlo: `~/.codex/AGENTS.md` o radice progetto), ChatGPT (upload skills nella Skills UI; tool via connector Developer Mode sull'endpoint Docker self-host → link docs esistenti), limiti (niente prompt MCP/risorse/hook; citation gate = disciplina AGENTS.md + `verifica_citazioni`), verifica naming («/mcp in Codex deve elencare i tool; se vuoto controlla il nome server»).

- [ ] Steps: edits → verification grep (no stale claims: CLAUDE.md compat table rows for skills/Codex updated truthfully) → full suite → commit `docs+ci: openai bundle in release builds and install guide`.

---

### Task 6: Final verification

- Full non-live suite → 0 failures (paste tail).
- `build_targets.py all` → 6 targets; tree clean; openai bundle: 43 skills, zip present, AGENTS.md sane (eyeball 20 lines in report).
- Claude regression: registration snapshot 218/23/15; drift gates green; `git diff develop..HEAD --stat -- plugin/` shows ONLY the 3 Task-1 files.
- `git log --oneline develop..HEAD` in report. NO merge/push/release.

## Deviations from the spec (measured, deliberate)

1. **Tool naming**: spec anticipated measuring `legal-it:`-style qualified names on a live Codex; current Codex uses `__`-separated forms varying by mode (PR #21576), so bodies ship BARE names — correct under every mode — and the config pins server name `legal_it`. The live-probe task is replaced by a documented `/mcp` verification step in docs/openai.md (Codex CLI not installed on this machine; a probe would also age instantly across Codex versions, the bare-name choice doesn't).
2. **`agents/openai.yaml` NOT emitted** (spec item 7): measured as fully optional with no required fields; 43 boilerplate files add maintenance for cosmetic UI metadata. Revisit on user demand.
3. **No committed projection for openai**: dist/openai is build output; determinism is test-asserted, not drift-gated (no marketplace-equivalent consumes the committed tree). A committed repo-root `.agents/skills/` (zero-install for cloners via Codex discovery) is recorded as a FUTURE option for the user to opt into.
4. **`commands/release` and `commands/digest` excluded** from the bundle (maintainer-only / harness-scheduling-bound); spec said "map the 8 slash commands" — 6 ship (both exclusions are corpus-measured, not concessions to effort).
5. **Role-skills instead of `~/.agents/` multi-agent roles** (spec item 5's optional variant): Codex multi-agent is behind a feature flag and version-dependent; role-skills work everywhere. Variant deferred.
