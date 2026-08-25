# Phase 2 — Agnostic Build Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One capability manifest (`content/targets.yaml`) and one builder CLI (`scripts/build_targets.py`) replace the four legacy build scripts; the corpus engine becomes config-driven so Claude is a generated target among others; the Phase-1 hardening debt (parse guard, lint, byte-exact drift) is paid.

**Architecture:** `scripts/corpus/` stays the ENGINE (projection + prompt generation, now parameterized by target config). `scripts/build_targets.py` is the single ORCHESTRATOR: it loads `content/targets.yaml`, runs projections, and packages artifacts (web-skills zips, plugin zip, mcpb) in pure Python — the three shell scripts and `plugin/build-web-skills.py` are deleted. `release.py` and `.github/workflows/release.yml` are repointed with minimal diffs.

**Tech Stack:** Python 3.10+ (stdlib + PyYAML declared in the dev extra — already a transitive dep of fastmcp, cp310 wheels confirmed). `mcpb` CLI when present, zip fallback otherwise (ported from build-dxt.sh).

**Spec:** `docs/specs/2026-08-24-harness-agnostic-layer-design.md` (Phase 2 section). This plan implements ONLY Phase 2; Phase 3 (OpenAI bundle) gets its own plan.

## Global Constraints

- Branch: `feature/build-targets` (exists, from develop @ b363d01). Conventional Commits, trailer `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` on every commit.
- **The empty-diff gate is the phase's acceptance criterion**: after the engine refactor, regenerating the claude-code target MUST reproduce the committed `plugin/{skills,agents,commands}`, `src/prompts.py` and `src/data/references/` byte-for-byte (the existing drift tests enforce it — they must stay green through every commit of this plan).
- Never run `release.py` except with `--dry-run`, and only where a step explicitly says so. Its version-bump machinery (6 manifests + tool-count regex + autonomous plugin patch bump) must NOT be touched by this plan.
- release.py's minimal-diff contract: only the `BUILD_WEB_SKILLS` constant, the `build_web_skills()` subprocess invocation, its user-facing messages, and the three `dist_dir = BUILD_WEB_SKILLS.parent / ...` derivation lines (~1150/1332/1493 — they reference the renamed constant) may change. The `plugin/dist/web-skills` output path and the flows' `git add -f` staging of it are PRESERVED (that is the web-skills distribution channel at release time; Task 12 of Phase 1 untracked the zips between releases — both behaviors are deliberate).
- Test command: `uv run --python 3.12 --extra dev pytest <path> -q`. Full suite: `... pytest tests/ -m "not live" -q`.
- Corpus content untouched: no file under `content/` changes except the new `content/targets.yaml`.
- CI job "Dependency declarations in sync" runs `python scripts/check_deps_sync.py` — after the pyproject dev-extra edit, run that script and keep it green.
- Counts unchanged everywhere: 218 tools / 23 prompts / 15 resources / 30 skills / 6 agents / 8 commands.
- All new code, comments, docstrings in English; YAML manifest keys in English.

## Measured facts this plan relies on (recon 2026-08-25)

- `release.py` (1682 lines) invokes ONE build: `plugin/build-web-skills.py` via `BUILD_WEB_SKILLS` (line 34) in `build_web_skills()` (line ~224-236: `subprocess.run([sys.executable, str(BUILD_WEB_SKILLS)], capture_output=True, cwd=str(BUILD_WEB_SKILLS.parent))`, warn-and-continue on failure, "build-web-skills.py not found, skipping" on missing). Called at lines 1104 (from-develop), 1293 (tag-only), 1429 (plugin-only). `plugin/dist/web-skills` is derived as `BUILD_WEB_SKILLS.parent / "dist" / "web-skills"` at lines 1150/1332/1493 and staged with `git add -f`. It never builds zip/mcpb artifacts and has no GitHub upload.
- `.github/workflows/release.yml` (tag push `v*`): installs `.[dev]`, pytest, then `scripts/build-dxt.sh "$VERSION"` and `scripts/build-plugin.sh "$VERSION"`, uploads `dist/*.mcpb` + `dist/*.zip` to the GitHub Release. These are the ONLY automated consumers of the shell scripts; `build-all.sh` is manual convenience.
- Script contracts to reproduce: plugin zip = copy of `plugin/{.claude-plugin,skills,agents,commands,hooks,settings.json,start_server.sh(chmod +x),server,...}` into `dist/plugin-build`, `__pycache__`/`*.pyc` purged, optional version rewrite of the BUILD DIR's `.claude-plugin/plugin.json` (json indent=2, ensure_ascii=False), zipped to `dist/legal-it-plugin-${VERSION}.zip` excluding `*.pyc __pycache__/*`, build dir removed. mcpb = `dxt/manifest.json` + `dxt/.mcpbignore` + root `pyproject.toml` + `plugin/start_server.sh` + `plugin/server` → `server/` into `dist/dxt-build`, same purge, optional version rewrite of build-dir manifest, `mcpb pack` if CLI exists else `zip -r` with same exclusions, output `dist/legal-it-${VERSION}.mcpb`. Web skills: one zip per skill at `plugin/dist/web-skills/{name}.zip` containing exactly `{name}/Skill.md`, frontmatter reduced to name+description with description truncated at 200 chars on a word boundary + "...", `argument-hint`/`model` dropped.
- Zero references to any build script in README/CLAUDE.md/CONTRIBUTING/docs (excluding specs) — no doc sweep needed beyond CONTRIBUTING/CLAUDE.md additions for the new builder.
- `install.py` has no build-script references.
- dev extras today: `pytest>=7.0, pytest-asyncio>=0.21, playwright>=1.40`. PyYAML 6.0.3 present transitively (fastmcp). CI python matrix: 3.10 + 3.12 (tests), 3.12 elsewhere.
- Engine entry points: `project(root: Path, out: Path) -> None` (project_claude.py:63) + CLI `--out`; `generate_prompts.py` CLI `--out` (default `plugin/server/src/prompts.py`). Drift tests invoke both CLIs by path — their interfaces must keep working.
- Phase-1 hardening debt (final review): `_parse_tools` silently reads only the first line of a `tools:` block (a block-style list in a command would project with NO allowed-tools line); no lint for undeclared vocabulary names (verified 0 hits today); drift `_assert_trees_equal` uses shallow dircmp; `generate_prompts.py` hardcodes "23" in the generated header.

## File structure (end state)

```
content/targets.yaml                    # NEW — capability manifest (single source of target config)
scripts/corpus/
  targets.py                            # NEW — load_targets(root) with validation
  project_claude.py                     # engine: project(root, out, cfg); CLI loads claude-code cfg from yaml
  generate_prompts.py                   # header count derived; unchanged output today
scripts/build_targets.py                # NEW — orchestrator CLI: claude-code | claude-web | plugin-zip | mcpb | all
scripts/build-all.sh                    # DELETED
scripts/build-plugin.sh                 # DELETED
scripts/build-dxt.sh                    # DELETED
plugin/build-web-skills.py              # DELETED
release.py                              # BUILD_WEB_SKILLS → build_targets.py claude-web (minimal diff)
.github/workflows/release.yml           # two shell steps → one python step
tests/unit/test_corpus_targets.py       # NEW
tests/unit/test_build_targets.py        # NEW (packaging on tmp trees + web-zip content rules)
tests/unit/test_corpus_build.py         # byte-exact compare (shallow=False)
tests/unit/test_corpus_projection.py    # + multi-line guard & lint tests
tests/unit/test_release_script.py       # + repoint assertions (monkeypatched subprocess)
```

---

### Task 1: `content/targets.yaml` + loader

**Files:**
- Create: `content/targets.yaml`
- Create: `scripts/corpus/targets.py`
- Modify: `pyproject.toml` (dev extra + check_deps_sync), `uv.lock` (re-locked as a side effect of the uv run commands — commit it)
- Test: `tests/unit/test_corpus_targets.py`

**Interfaces:**
- Produces: `load_targets(root: Path) -> dict` returning the parsed, validated manifest; `get_target(root, name) -> dict`. Consumed by Tasks 2 and 4.

- [ ] **Step 1: Write `content/targets.yaml`** (exact content — the claude family only; Phase 3 will add openai targets):

```yaml
# Capability manifest — the harness-agnostic layer.
# Each projection target declares what the harness supports and how tool
# names are spelled there. Packaging targets bundle a projection's output.
# Adding a harness is a new block here, not a code branch in the builder.
version: 1

projections:
  claude-code:
    tool_namespace: "legal-it:{tool}"
    command_tool_namespace: "mcp__legal-it__{tool}"
    strip_frontmatter_keys: [tools, prompt]
    supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]
    out:
      skills: plugin/skills
      agents: plugin/agents
      commands: plugin/commands
      references: plugin/server/src/data/references

packaging:
  claude-web:
    from: claude-code
    out_dir: plugin/dist/web-skills
    description_max_chars: 200
    keep_frontmatter: [name, description]
    zip_member: "{name}/Skill.md"
  plugin-zip:
    from: claude-code
    artifact: "dist/legal-it-plugin-{version}.zip"
    include: [.claude-plugin, skills, agents, commands, hooks, settings.json, start_server.sh, .mcp.json, server]
    root: plugin
    version_manifest: ".claude-plugin/plugin.json"
  mcpb:
    from: claude-code
    artifact: "dist/legal-it-{version}.mcpb"
    version_manifest: "manifest.json"
```

NOTE for the implementer: the include list above was verified item-by-item against `scripts/build-plugin.sh` lines 20-33 (9 entries — plugin/README.md, CHANGELOG.md and LICENSE exist on disk but the legacy zip NEVER shipped them; do not add them). Still re-verify against the script before committing — it remains the authority while it exists. Same for the mcpb file set in Task 4.

- [ ] **Step 2: Failing test**

```python
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "corpus_targets", REPO / "scripts" / "corpus" / "targets.py"
)
tg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tg)


def test_load_real_manifest():
    data = tg.load_targets(REPO)
    assert data["version"] == 1
    cc = tg.get_target(REPO, "claude-code")
    assert cc["tool_namespace"] == "legal-it:{tool}"
    assert cc["out"]["skills"] == "plugin/skills"


def test_unknown_target_raises():
    with pytest.raises(KeyError):
        tg.get_target(REPO, "nonexistent")


def test_validation_rejects_missing_namespace(tmp_path):
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "targets.yaml").write_text(
        "version: 1\nprojections:\n  broken:\n    out: {skills: x}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="tool_namespace"):
        tg.load_targets(tmp_path)
```

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_targets.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement `scripts/corpus/targets.py`**

```python
"""Load and validate content/targets.yaml — the capability manifest."""
from __future__ import annotations

from pathlib import Path

import yaml

_REQUIRED_PROJECTION_KEYS = {"tool_namespace", "strip_frontmatter_keys", "out"}


def load_targets(root: Path) -> dict:
    data = yaml.safe_load((root / "content" / "targets.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("targets.yaml: unsupported or missing version")
    for name, cfg in (data.get("projections") or {}).items():
        missing = _REQUIRED_PROJECTION_KEYS - set(cfg)
        if missing:
            raise ValueError(f"targets.yaml projection {name!r}: missing {sorted(missing)} (tool_namespace, strip_frontmatter_keys, out are required)")
    return data


def get_target(root: Path, name: str) -> dict:
    data = load_targets(root)
    for section in ("projections", "packaging"):
        if name in (data.get(section) or {}):
            return data[section][name]
    raise KeyError(name)
```

- [ ] **Step 4: Declare PyYAML** — add `"pyyaml>=6.0",` to `[project.optional-dependencies] dev` in `pyproject.toml`; run `uv run --python 3.12 --extra dev python scripts/check_deps_sync.py` and fix whatever it reports until green (that script is the CI gate for dependency declarations).
- [ ] **Step 5: Run tests** → 3 passed. Full unit suite once → green.
- [ ] **Step 6: Commit** (include `uv.lock`) — `feat(build): capability manifest content/targets.yaml + loader`

---

### Task 2: Config-driven engine + Phase-1 hardening

The engine's claude-specific constants move into the manifest; the projector gains the two guards the Phase-1 reviews demanded. **The committed projections must not change**: the drift tests are the gate for every step here.

**Files:**
- Modify: `scripts/corpus/project_claude.py`
- Test: extend `tests/unit/test_corpus_projection.py`; modify `tests/unit/test_corpus_build.py` (byte-exact)

**Interfaces:**
- Produces: `project(root: Path, out: Path, cfg: dict | None = None) -> None` — `cfg=None` loads the `claude-code` projection from `content/targets.yaml`. CLI unchanged (`--out`), so the drift test's subprocess invocation keeps working. Consumed by Task 4.

- [ ] **Step 1: Failing tests first** (append to `tests/unit/test_corpus_projection.py`; reuse its `_load` helper and fixtures):

```python
def test_multiline_tools_block_is_rejected(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    bad = src_root / "content/skills/demo/SKILL.md"
    bad.write_text(SKILL.replace(
        "tools: [cite_law, leggi_sentenza]",
        "tools:\n  - cite_law\n  - leggi_sentenza",
    ), encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit, match="single-line"):
        pc.project(src_root, tmp_path / "out")


def test_undeclared_vocabulary_name_is_rejected(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    skill = src_root / "content/skills/demo/SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "Usa `cite_law`", "Usa `cite_law` e poi `cerca_brocardi`"
        ),
        encoding="utf-8",
    )  # cerca_brocardi is in the fixture vocabulary but NOT in demo's tools:
    import pytest
    with pytest.raises(SystemExit, match="undeclared"):
        pc.project(src_root, tmp_path / "out")
```

The fixture `_make_content` must ALSO write a minimal `content/targets.yaml` (claude-code block as in Task 1) so `project()` can default-load config in tmp roots — add that line to the fixture and keep the existing three tests passing.

- [ ] **Step 2: Refactor `project_claude.py`:**
  1. `project(root, out, cfg=None)`; when `cfg is None`, load via `targets.py` (`get_target(root, "claude-code")`).
  2. Replace the hardcoded `"legal-it:{}"`/`"mcp__legal-it__{}"` templates and the target dir paths with values from `cfg` (`tool_namespace`, `command_tool_namespace`, `out` mapping, `strip_frontmatter_keys`). **Placeholder convention (load-bearing)**: the manifest uses the NAMED placeholder `{tool}` for readability, but `toolnames.add_prefixes` formats POSITIONALLY (`template.format(tool)` — `"legal-it:{tool}".format(x)` raises KeyError). The engine converts once when reading the config: `template = cfg["tool_namespace"].replace("{tool}", "{}")` (same for `command_tool_namespace`). Add a unit assertion for this conversion in the projection tests.
  3. `_parse_tools`: when `block_range` spans more than one line, `raise SystemExit(f"{path}: 'tools:' must be a single-line flow list — multi-line blocks are silently truncated")` (thread the path through).
  4. New lint inside `project()`: for every corpus body (SKILL.md bodies + skill reference .md files + agent/command bodies), `tn.find_bare_tools(body, vocab_minus_declared)` where `vocab_minus_declared = sorted(vocab - set(declared_tools))`; any hit → `SystemExit(f"{path}: undeclared tool name(s) in body: {hits} — add them to tools: or rephrase")`. (Verified against the real corpus: 0 hits today, so this lands green.)
- [ ] **Step 3: Byte-exact drift compare** — in `tests/unit/test_corpus_build.py`, replace the dircmp shallow logic in `_assert_trees_equal` with an explicit walk: same relative file sets on both sides (ignoring `.DS_Store`), and `read_bytes()` equality per file. Keep the assertion messages informative (name the first differing file).
- [ ] **Step 4: Run the WHOLE unit suite** → all green, drift tests included (this proves the refactor is projection-neutral). Then regenerate in-tree (`uv run ... python scripts/corpus/project_claude.py`) and `git status --short -- plugin/ src/` → EMPTY (nothing changed on disk).
- [ ] **Step 5: Commit** — `refactor(corpus)!: projection engine reads target config from targets.yaml; guard multi-line tools and undeclared names`

---

### Task 3: Derived count in the prompts generator

**Files:** Modify `scripts/corpus/generate_prompts.py`; regenerate; verify no diff.

- [ ] **Step 1:** In `_HEADER`, replace the literal `23` with a `{count}` placeholder and format it with `len(items)` at write time (keep the wording byte-identical otherwise: `"{count} guided legal workflow prompts, for MCP clients that support prompts."`).
- [ ] **Step 2:** Regenerate: `uv run --python 3.12 --extra dev python scripts/corpus/generate_prompts.py` then `git status --short -- plugin/server/src/prompts.py` → EMPTY (23 prompts → same header text). Run the drift + prompt-surface tests → green.
- [ ] **Step 3: Commit** — `fix(corpus): derive prompt count in generated header`

---

### Task 4: `scripts/build_targets.py` — the orchestrator

**Files:**
- Create: `scripts/build_targets.py`
- Test: `tests/unit/test_build_targets.py`

**Interfaces:**
- Consumes: `targets.py` (Task 1), engine `project()` (Task 2), `generate_prompts.py` CLI behavior.
- Produces: CLI `python scripts/build_targets.py TARGET [TARGET ...] [--version X.Y.Z] [--out DIR]` with targets `claude-code`, `claude-web`, `plugin-zip`, `mcpb`, `all`. Library functions `build_claude_code(root)`, `build_claude_web(root, out_dir=None) -> int` (returns zip count, prints `"{count} ZIP generati in {out_dir}"` — release.py greps nothing but keep the line for humans), `build_plugin_zip(root, version=None) -> Path`, `build_mcpb(root, version=None) -> Path`.

Implementation requirements (port faithfully — the shell scripts are still in the tree during this task; read them and mirror behavior exactly):
- `claude-code`: call `project(root, root, cfg)` + run generate_prompts with an ABSOLUTE path (a relative path breaks when the CLI runs from elsewhere): `subprocess.run([sys.executable, str(root / "scripts" / "corpus" / "generate_prompts.py")], cwd=root, check=True)`.
- `claude-web` (ports `plugin/build-web-skills.py`): iterate `plugin/skills/*/SKILL.md` (the PROJECTED tree — same input as the legacy script). The REDUCTION and the EMISSION must both be reproduced (measured: all 30 projected descriptions exceed 80 chars, 28/30 exceed 200, one is multi-line — every rule below is exercised by the parity gate):
  1. keep only `name` + `description`; drop `argument-hint`/`model`;
  2. normalize the description UNCONDITIONALLY: `desc = " ".join(desc.split())`;
  3. truncate when `len > description_max_chars`: cut at `max_chars - 3`, back to the last space (`rfind(" ")`), append `"..."` (total ≤ 200);
  4. EMISSION format (mirrors legacy lines 59-74): a value containing a newline or longer than 80 chars is written as a folded scalar — `description: >` newline + each line two-space-indented and stripped; otherwise plain `key: value`. `name` is always plain.
  Write `{out_dir}/{skill}.zip` each containing exactly `{skill}/Skill.md` (ZIP_DEFLATED). Reuse `scripts/corpus/frontmatter.py` for the SPLIT — do NOT copy the legacy regex parser; the emission rules above replace the legacy rebuild logic.
- `plugin-zip` (ports build-plugin.sh): stage the include-list into a temp dir (`tempfile.mkdtemp`, not dist/plugin-build), purge `__pycache__`/`*.pyc`, optional version rewrite of staged `.claude-plugin/plugin.json` (json indent=2, ensure_ascii=False, trailing newline preserved as the shell's json.dump produced), zip to `dist/legal-it-plugin-{version}.zip` (default version = plugin.json's current), exclude `*.pyc` and `__pycache__` from the archive, clean temp dir.
- `mcpb` (ports build-dxt.sh): stage `dxt/manifest.json`, `dxt/.mcpbignore`, root `pyproject.toml`, `plugin/start_server.sh` (executable bit), `plugin/server` → `server/`; purge caches; optional version rewrite of staged `manifest.json`; if `shutil.which("mcpb")` → `mcpb pack`, else zipfile fallback with the same exclusions; output `dist/legal-it-{version}.mcpb` (default version = dxt/manifest.json's current).
- `all` = claude-code, claude-web, plugin-zip, mcpb in that order.
- Exit non-zero with a clear message on any failure; no silent partial builds.

**Tests** (`tests/unit/test_build_targets.py`, loaded via importlib like the siblings):
1. `test_web_zip_conversion_rules(tmp_path)` — build a fake projected skill with a >200-char multi-word description + `argument-hint`; run `build_claude_web` with `out_dir=tmp_path`; open the zip: single member `{name}/Skill.md`, frontmatter uses the folded `description: >` form, the normalized description ends with `"..."`, is cut on a word boundary and is ≤200 chars total, `argument-hint` gone.
2. `test_plugin_zip_stages_and_excludes(tmp_path)` — minimal fake plugin tree with a `__pycache__` dir and a `.pyc`; build with `version="9.9.9"`; zip contains the include-list files, no pyc/pycache, and the staged plugin.json says 9.9.9 while the SOURCE plugin.json is untouched.
3. `test_mcpb_fallback_zip(tmp_path, monkeypatch)` — `monkeypatch.setattr(shutil, "which", lambda _: None)`; verify the fallback zip is produced with the expected members.
4. `test_cli_rejects_unknown_target` — subprocess CLI with `nonsense` → returncode != 0, helpful stderr.

- [ ] **Steps:** failing tests → implement → tests green → **parity check** (mandatory, evidence in the report): run the OLD scripts and the NEW builder side by side with the same explicit version, each writing into its OWN scratch output (never the same dist/ path — shell `zip -r` updates an existing archive in place). Compare FILE members only: `zipinfo -1 X | grep -v '/$' | sort` — shell `zip -r` emits directory entries, `zipfile` does not, and directory entries are irrelevant to consumers; the file-member lists must match exactly. Byte-diff the staged manifests. Zip BYTES will differ (timestamps) — never compare archive bytes. For claude-web: run legacy `plugin/build-web-skills.py` into a scratch copy and the new builder into another; unzip both sets and `diff -r` the extracted trees → must be identical for all 30 skills.
- [ ] **Commit** — `feat(build): unified builder scripts/build_targets.py (claude-code, claude-web, plugin-zip, mcpb)`

---

### Task 5: Repoint release.py (minimal diff) and release.yml

**Files:**
- Modify: `release.py` (constant + one function, nothing else)
- Modify: `.github/workflows/release.yml`
- Test: extend `tests/unit/test_release_script.py`

- [ ] **Step 1: Failing test** (follow the file's existing importlib pattern; monkeypatch `subprocess.run` to capture the command):

```python
def test_build_web_skills_invokes_unified_builder(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        class R: returncode = 0; stdout = b""; stderr = b""
        return R()

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    release.build_web_skills(dry_run=False)
    (cmd, kw), = calls
    assert cmd[1].endswith("scripts/build_targets.py")
    assert cmd[2] == "claude-web"
    assert kw["cwd"] == str(release.PROJECT_DIR)
```

(Adapt attribute names to how the module is loaded in that test file; if `build_web_skills` prints via helpers that need a tty, monkeypatch them as the existing tests do.)

- [ ] **Step 2: Edit release.py** — exactly:
  - line 34: `BUILD_WEB_SKILLS = PROJECT_DIR / "plugin" / "build-web-skills.py"` → `BUILD_TARGETS = PROJECT_DIR / "scripts" / "build_targets.py"`
  - in `build_web_skills()`: missing-file check + message reference the new path ("build_targets.py not found, skipping"); invocation becomes `subprocess.run([sys.executable, str(BUILD_TARGETS), "claude-web"], capture_output=True, cwd=str(PROJECT_DIR))`; success message unchanged ("Web skills ZIP rebuilt").
  - the three `dist_dir = BUILD_WEB_SKILLS.parent / "dist" / "web-skills"` sites (lines ~1150/1332/1493) become `dist_dir = PROJECT_DIR / "plugin" / "dist" / "web-skills"` (same value as before — verify with a quick python equality check in the report).
  - NOTHING ELSE changes: no version logic, no changelog logic, no flow reordering.
- [ ] **Step 3: Edit release.yml** — replace the two build steps with one:

```yaml
      - name: Build artifacts (mcpb + plugin zip)
        run: |
          VERSION="${TAG_VERSION#v}"
          python scripts/build_targets.py mcpb plugin-zip --version "$VERSION"
```

Upload steps unchanged (`dist/*.mcpb`, `dist/*.zip` patterns still match).
- [ ] **Step 4:** Runtime note (record in the task report AND add one line to CONTRIBUTING in Task 6): the repointed build now imports PyYAML via targets.py, which the legacy stdlib-only script never needed — release.py must run from an environment with the project installed (`uv run --python 3.12 --extra dev python release.py ...`); a bare interpreter would fail the build subprocess, and release.py's pre-existing warn-and-continue would then stage STALE web-skills zips. Behavior unchanged by design (minimal diff) — the environment requirement is documented instead.
  Then `git diff release.py` — confirm the diff touches ONLY the constant, `build_web_skills()`, and the three dist_dir lines. Run the extended test_release_script.py + full unit suite → green. Then one smoke: `uv run --python 3.12 --extra dev python release.py --help` (arg parsing intact; do NOT run any flow).
- [ ] **Step 5: Commit** — `refactor(release): point release.py and release.yml at the unified builder`

---

### Task 6: Retire the legacy scripts + docs

**Files:**
- Delete: `scripts/build-all.sh`, `scripts/build-plugin.sh`, `scripts/build-dxt.sh`, `plugin/build-web-skills.py`
- Modify: `CONTRIBUTING.md`, `CLAUDE.md`, `docs/deployment.md` (check), `CHANGELOG.md` + `plugin/CHANGELOG.md` ([Unreleased])

- [ ] **Step 1:** `git rm` the four scripts. Repo-wide grep for their names (excluding docs/specs/ and CHANGELOG history) → zero live references (recon says only release.py/release.yml referenced them — both already repointed).
- [ ] **Step 2: Docs** — CONTRIBUTING "Generated files" section: add the builder as the canonical command (`python scripts/build_targets.py claude-code` regenerates all projections; packaging targets listed). CLAUDE.md: «Struttura» gains `content/targets.yaml` + `scripts/build_targets.py`, the Docker/build command sections that mention `build-*.sh` (check «Comandi»/deployment blocks; recon found zero but verify with grep) get the new command. `docs/deployment.md`: check for build instructions, update if present. CHANGELOGs [Unreleased]: one line about the unified builder replacing the four scripts.
- [ ] **Step 3:** Full suite + `uv run ... python scripts/build_targets.py all` smoke (artifacts produced; then `git status` — dist/ and plugin/dist are gitignored so tree stays clean; delete the produced dist/ artifacts if the smoke leaves any tracked noise — it must not).
- [ ] **Step 4: Commit** — `chore(build)!: retire build-all/build-plugin/build-dxt/build-web-skills in favour of build_targets.py`

---

### Task 7: Final verification

- [ ] Full non-live suite (`tests/`) → 0 failures; paste tail.
- [ ] `python scripts/build_targets.py all` → 4 outcomes verified: projections no-diff (`git status` clean), 30 web zips, plugin zip with 30 SKILL.md (`unzip -l | grep -c`), mcpb produced.
- [ ] Registration snapshot unchanged: `tools=218 prompts=23 resources=15`.
- [ ] `git log --oneline develop..HEAD` — clean history.
- [ ] Report in Italian: what changed, parity evidence, release.py diff summary, what Phase 3 needs next. NO merge, NO push, NO release.py flows.

## Deviations from the spec (deliberate)

1. **The engine stays in `scripts/corpus/`** — the spec said the builder "absorbs" the Phase-1 scripts; measured reality: the drift tests invoke those CLIs by path and the layering (engine library vs orchestrator CLI) is cleaner than a single monolith. `build_targets.py` absorbs the four LEGACY scripts; the corpus engine becomes its config-driven library.
2. **`targets.yaml` lives at `content/targets.yaml`** (the spec drew it beside content/) — it is corpus metadata and the Phase-1 SVG shown to the user already places it there.
3. **release.py's `git add -f` of web-skills zips is preserved** — the zips return to git in release commits (their distribution channel for Claude Web users) while staying untracked between releases. Both this and Phase 1's untracking are deliberate; documented here rather than "fixed".
4. **`agents.tools:` naming collision** (flagged by the Phase-1 final review): the corpus key `tools:` on agents is stripped on projection and never collides today because base agents declare no such key. The precedence rule belongs in targets.yaml when a target actually consumes agent tool lists (Phase 3 at the earliest) — no code now, note recorded.
5. **Manifest schema diverges from the spec's sketch** — projections:/packaging: split, deny-list `strip_frontmatter_keys` (spec sketched an allow-list `frontmatter:`), per-kind `out:` map to committed in-tree paths (spec sketched dist/claude/). Deliberate improvements; Phase 3's plan must reconcile its manifest additions with THIS schema, and make project() honour `supports:` (dead config today, like packaging `from:` on plugin-zip/mcpb).
