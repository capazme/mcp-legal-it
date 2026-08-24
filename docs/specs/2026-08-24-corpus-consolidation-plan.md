# Phase 1 — Corpus Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One source of truth per workflow: skills, agents, commands and static references move to a `content/` corpus; `plugin/{skills,agents,commands}` and `src/prompts.py` become committed, generated projections; the MCP prompt surface (23 prompts) is preserved by generation and 7 previously prompt-only workflows become skills.

**Architecture:** Text-level transformations only (never re-serialize YAML — round-trip must be byte-identical). A small `scripts/corpus/` toolkit provides frontmatter handling, tool-name rewriting, a Claude projector, a prompt generator and one-shot migration/extraction scripts. Drift between corpus and generated artifacts is caught by a pytest gate that regenerates into a temp dir and diffs.

**Tech Stack:** Python 3.10+ stdlib only for the toolkit (no PyYAML — line-based frontmatter handling is deliberate). FastMCP 3.4.7 in-process `Client` for registration tests. pytest via `uv run --extra dev`.

**Spec:** `docs/specs/2026-08-24-harness-agnostic-layer-design.md` (Phase 1 section). This plan implements ONLY Phase 1. The spec's Phase 2 (targets.yaml, build_targets.py) and Phase 3 (OpenAI bundle) get their own plans later.

## Global Constraints

- Branch: `feature/harness-agnostic-layer` (already exists, from `develop`). All commits land here. Conventional Commits.
- Never run `release.py` during this work (it bumps manifests and rewrites changelogs on its own).
- Corpus content (SKILL.md bodies, agents, commands, references) is **Italian**; all new code, comments, and generated-file headers are **English**.
- Frontmatter is handled at TEXT level: split on `---` lines, insert/remove whole lines. Never parse-and-dump YAML — byte fidelity is a hard requirement.
- Generated files carry a first-line marker: `<!-- GENERATED from content/... — do not edit; run scripts/corpus/project_claude.py -->` for markdown is NOT used (Claude reads skills verbatim — a marker would leak into context). Instead generated-ness is documented in CONTRIBUTING.md and enforced by the drift test. `src/prompts.py` (Python) DOES carry a `# GENERATED` header docstring.
- Test command (the project `.venv` has no pytest): `uv run --python 3.12 --extra dev pytest <path> -q`. Full suite: `uv run --python 3.12 --extra dev pytest tests/ -m "not live" -q`.
- FastMCP is 3.4.7: `get_tools()` does not exist; use `await mcp.list_tools()` (pattern already used by `install.py:verify_server`) or the in-process `fastmcp.Client`.
- `test_resources_dynamic.py` imports `_render_contributo_unificato` and friends from `src/resources.py` — the resources rewrite MUST keep those helper names and signatures.
- Counts after this phase: tools 218 (unchanged), skills **30** (23+7), MCP prompts **23** (16 generated from existing skills + 7 from new skills), resources 15 (12 static + 3 dynamic), agents 6, commands 8.
- Do not touch: `src/tools/`, `src/lib/`, `plugin/hooks/`, `plugin/server/` (except `src/prompts.py`, `src/resources.py`, `src/data/references/`), `dxt/`, `benchmarks/`.

## Measured inventory this plan relies on (recon 2026-08-24)

- 16 prompt/skill duplicates; 7 orphan prompts (`analisi_tributaria`, `analisi_giurisprudenza_europea`, `analisi_giurisprudenza_amministrativa`, `analisi_costituzionale`, `ricerca_gazzetta`, `orientamento_giurisprudenziale`, `attuazione_direttiva`) at `src/prompts.py` lines 1053-1500.
- All 23 skills have exactly `name` + `description` frontmatter. 4 skills have extra files. 4 skills reference tools with BARE names (no `legal-it:` prefix): `cookie-audit` (cite_law, genera_informativa_cookie), `esporta-documento` (5 tools), `analisi-fornitori` (genera_dpa), `analisi-giurisprudenziale` (leggi_sentenza, once). These 4, plus ~9 more prose/code-fence cases measured by adversarial simulation, form the expected round-trip diff (full list in Task 5 Step 3).
- `legal-it:` occurs in 34 files (20 SKILL.md + 1 skill reference file + 6 agents + 7 commands); `mcp__legal-it__` occurs ONLY on `allowed-tools:` frontmatter lines of the 7 tool-using commands (comma+space separated). CAUTION: `allowed-tools` ALSO carries non-MCP entries — `digest.md` ends with `CronCreate, CronDelete` and `release.md` is entirely harness tools (`Bash, Read, Edit, Write, Grep, Glob`) — the projector must namespace only vocabulary members. 2 non-backtick `legal-it:` occurrences exist in `plugin/agents/ricerca-giurisprudenziale.md` lines 23, 31.
- resources.py (1644 lines): decorator form is `@mcp.resource("<uri>", name="...", description="...")`, no mime_type anywhere. 12 resources return inline literals; 3 are dynamic renders from `src/data` JSON (`contributo_unificato` lines 310-316 + `_render_contributo_unificato` 193-307, `irpef_detrazioni` 365-432, `interessi_legali` 494-500 + its helper). Module helpers `_DATA`, `_load`, `_eur`, `_soglia`, `_pct`, `_scaglioni_rows` live at lines 13-50.
- Marketplace installs consume the committed `plugin/` tree from GitHub → generated dirs MUST stay committed. `release.py` runs builds AFTER `check_clean_tree()` → drift checks must not dirty the tree (regenerate into tmp).
- No existing test covers server registration (list_tools) — this plan adds one.

## File structure (end state)

```
content/                                  # SOURCE corpus (new)
  tool-vocabulary.json                    # generated dump of the 218 tool names (committed)
  skills/<30 dirs>/SKILL.md [+ references/, scripts/, assets/]
  agents/<6>.md
  commands/<8>.md
  references/<12>.md                      # static resource texts
scripts/corpus/                           # toolkit (new)
  __init__.py
  frontmatter.py                          # text-level split/insert/strip
  toolnames.py                            # strip/add legal-it: prefixes
  dump_vocabulary.py                      # server -> content/tool-vocabulary.json
  project_claude.py                       # content -> plugin/{skills,agents,commands} + src/data/references
  generate_prompts.py                     # content -> src/prompts.py
  migrate_corpus.py                       # one-shot (kept for audit)
  extract_references.py                   # one-shot (kept for audit)
plugin/skills|agents|commands/            # GENERATED, committed (unchanged layout)
src/prompts.py                            # GENERATED, committed
src/data/references/<12>.md               # GENERATED copies, committed (ship in every distribution)
src/resources.py                          # hand-written loader (12 static entries + 3 dynamic, helpers kept)
tests/unit/test_corpus_frontmatter.py
tests/unit/test_corpus_toolnames.py
tests/unit/test_corpus_projection.py
tests/unit/test_corpus_build.py           # drift gate
tests/unit/test_server_registration.py    # 218 tools / 23 prompts / 15 resources
```

---

### Task 1: Frontmatter text toolkit

**Files:**
- Create: `scripts/corpus/__init__.py` (empty)
- Create: `scripts/corpus/frontmatter.py`
- Test: `tests/unit/test_corpus_frontmatter.py`

**Interfaces:**
- Produces: `split(text) -> tuple[list[str], str]`, `join(fm_lines, body) -> str`, `block_range(fm_lines, key) -> tuple[int,int] | None`, `strip_keys(fm_lines, keys) -> list[str]`, `append_lines(fm_lines, new_lines) -> list[str]`, `replace_line(fm_lines, key, new_line) -> list[str]`. Used by Tasks 3-7.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for scripts/corpus/frontmatter.py (loaded via importlib like test_release_script.py)."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "corpus_frontmatter", Path(__file__).parents[2] / "scripts" / "corpus" / "frontmatter.py"
)
fm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fm)

DOC = "---\nname: analisi-sinistro\ndescription: Analizza sinistri stradali,\n  sanitari e lavorativi.\n---\n\n# Corpo\n\nTesto.\n"

def test_split_join_roundtrip_is_byte_identical():
    lines, body = fm.split(DOC)
    assert lines[0] == "name: analisi-sinistro"
    assert body.startswith("\n# Corpo")
    assert fm.join(lines, body) == DOC

def test_split_rejects_missing_frontmatter():
    import pytest
    with pytest.raises(ValueError):
        fm.split("# no frontmatter\n")

def test_block_range_covers_continuation_lines():
    lines, _ = fm.split(DOC)
    start, end = fm.block_range(lines, "description")
    assert (start, end) == (1, 3)  # 'description:' + one indented continuation line
    assert fm.block_range(lines, "tools") is None

def test_strip_keys_removes_whole_blocks():
    lines, body = fm.split(DOC)
    lines2 = fm.append_lines(lines, ["tools: [cite_law]", 'prompt: {"name": "x", "args": []}'])
    stripped = fm.strip_keys(lines2, ["tools", "prompt"])
    assert stripped == lines
    assert fm.join(stripped, body) == DOC

def test_replace_line_swaps_in_place():
    lines = ["name: norma", "tools: cite_law, cerca_brocardi"]
    out = fm.replace_line(lines, "tools", "allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi")
    assert out[1].startswith("allowed-tools:")
    assert out[0] == "name: norma"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_frontmatter.py -q`
Expected: FAIL (file `scripts/corpus/frontmatter.py` does not exist → importlib error)

- [ ] **Step 3: Write the implementation**

```python
"""Text-level frontmatter handling for the content corpus.

Deliberately NOT YAML-based: the corpus round-trip (migrate -> project) must be
byte-identical, so we only ever split on delimiter lines and insert/remove
whole lines. Re-serializing YAML would reorder keys and rewrap strings.
"""
from __future__ import annotations


def split(text: str) -> tuple[list[str], str]:
    """Split a markdown document into (frontmatter lines, body).

    The delimiters are excluded; body starts right after the closing '---\\n'.
    Raises ValueError when the document has no leading frontmatter.
    """
    if not text.startswith("---\n"):
        raise ValueError("document has no leading frontmatter")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise ValueError("frontmatter is not closed")
    return text[4:end].split("\n"), text[end + len("\n---\n"):]


def join(fm_lines: list[str], body: str) -> str:
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def block_range(fm_lines: list[str], key: str) -> tuple[int, int] | None:
    """Half-open [start, end) index range of `key:` plus its indented continuation."""
    prefix = key + ":"
    for i, line in enumerate(fm_lines):
        if line == key or line.startswith(prefix):
            j = i + 1
            while j < len(fm_lines) and (fm_lines[j].startswith((" ", "\t")) or fm_lines[j] == ""):
                j += 1
            return i, j
    return None


def strip_keys(fm_lines: list[str], keys: list[str]) -> list[str]:
    out = list(fm_lines)
    for key in keys:
        rng = block_range(out, key)
        if rng is not None:
            del out[rng[0]:rng[1]]
    return out


def append_lines(fm_lines: list[str], new_lines: list[str]) -> list[str]:
    return list(fm_lines) + list(new_lines)


def replace_line(fm_lines: list[str], key: str, new_line: str) -> list[str]:
    rng = block_range(fm_lines, key)
    if rng is None:
        raise KeyError(key)
    if rng[1] - rng[0] != 1:
        raise ValueError(f"{key!r} spans multiple lines; replace_line handles single lines only")
    out = list(fm_lines)
    out[rng[0]] = new_line
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_frontmatter.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/corpus/__init__.py scripts/corpus/frontmatter.py tests/unit/test_corpus_frontmatter.py
git commit -m "feat(corpus): text-level frontmatter toolkit"
```

---

### Task 2: Tool vocabulary dump

**Files:**
- Create: `scripts/corpus/dump_vocabulary.py`
- Create (generated, committed): `content/tool-vocabulary.json`

**Interfaces:**
- Produces: `content/tool-vocabulary.json` = sorted JSON array of the 218 registered tool names. Consumed by Tasks 3, 5 and by the lint inside the projector.

- [ ] **Step 1: Write the script**

```python
"""Dump the registered MCP tool names to content/tool-vocabulary.json.

Run from the repo root:  python scripts/corpus/dump_vocabulary.py
Uses mcp.list_tools() (FastMCP 3.4.7 — get_tools() no longer exists).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


async def main() -> None:
    from src.server import mcp  # imports all 32 tool modules

    tools = await mcp.list_tools()
    names = sorted(t.name for t in tools)
    out = ROOT / "content" / "tool-vocabulary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(names, indent=0) + "\n", encoding="utf-8")
    print(f"{len(names)} tool names -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it and verify the output**

Run: `uv run --python 3.12 --extra dev python scripts/corpus/dump_vocabulary.py`
Expected: `218 tool names -> content/tool-vocabulary.json`. Then verify: `python3 -c "import json; v=json.load(open('content/tool-vocabulary.json')); print(len(v), 'cite_law' in v, 'leggi_sentenza' in v)"` → `218 True True`. If the count is not 218, STOP: the tool count in every manifest is 218 and a mismatch means the environment failed to import a tool module — investigate before continuing.

- [ ] **Step 3: Commit**

```bash
git add scripts/corpus/dump_vocabulary.py content/tool-vocabulary.json
git commit -m "feat(corpus): dump tool vocabulary (218 names)"
```

---

### Task 3: Tool-name rewriting

**Files:**
- Create: `scripts/corpus/toolnames.py`
- Test: `tests/unit/test_corpus_toolnames.py`

**Interfaces:**
- Produces: `strip_prefixes(text) -> tuple[str, list[str]]` (removes every `legal-it:` prefix, returns found tool names), `find_bare_tools(text, vocabulary) -> list[str]`, `add_prefixes(text, tools, template="legal-it:{}") -> str`. Consumed by Tasks 4, 5.

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "corpus_toolnames", Path(__file__).parents[2] / "scripts" / "corpus" / "toolnames.py"
)
tn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tn)

VOCAB = ["cite_law", "cerca_brocardi", "leggi_sentenza", "interessi_legali"]

def test_strip_prefixes_backticked_and_bare():
    text = "Chiama `legal-it:cite_law`, poi legal-it:cerca_giurisprudenza_unificata(q).\n"
    out, found = tn.strip_prefixes(text)
    assert out == "Chiama `cite_law`, poi cerca_giurisprudenza_unificata(q).\n"
    assert found == ["cerca_giurisprudenza_unificata", "cite_law"]

def test_add_prefixes_backticked_bare_and_called():
    text = "Usa `cite_law` e poi leggi_sentenza(numero, anno).\n"
    out = tn.add_prefixes(text, ["cite_law", "leggi_sentenza"])
    assert out == "Usa `legal-it:cite_law` e poi legal-it:leggi_sentenza(numero, anno).\n"

def test_add_prefixes_never_double_prefixes():
    text = "`legal-it:cite_law` e mcp__legal-it__cite_law restano intatti.\n"
    assert tn.add_prefixes(text, ["cite_law"]) == text

def test_roundtrip_is_byte_identical():
    original = "1. `legal-it:interessi_legali`\n2. legal-it:cite_law(rif)\n"
    stripped, found = tn.strip_prefixes(original)
    assert tn.add_prefixes(stripped, found) == original

def test_find_bare_tools_uses_vocabulary_only():
    text = "Chiama `cite_law`; il campo eta_vittima non è un tool.\n"
    assert tn.find_bare_tools(text, VOCAB) == ["cite_law"]

def test_word_boundaries_protect_similar_names():
    text = "interessi_legali_extra non è interessi_legali.\n"
    out = tn.add_prefixes(text, ["interessi_legali"])
    assert out == "interessi_legali_extra non è legal-it:interessi_legali.\n"

def test_file_paths_are_never_prefixed():
    text = "Vedi `data/contributo_unificato.json` per gli scaglioni.\n"
    assert tn.add_prefixes(text, ["contributo_unificato"]) == text
    assert tn.find_bare_tools(text, ["contributo_unificato"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_toolnames.py -q`
Expected: FAIL (module missing)

- [ ] **Step 3: Write the implementation**

```python
"""Symmetric tool-name prefix rewriting between corpus (bare) and targets."""
from __future__ import annotations

import re

_STRIP_RE = re.compile(r"legal-it:([a-z0-9_]+)")


def strip_prefixes(text: str) -> tuple[str, list[str]]:
    """Remove every 'legal-it:' prefix; return (new_text, sorted unique tool names found)."""
    found: set[str] = set()

    def repl(m: re.Match[str]) -> str:
        found.add(m.group(1))
        return m.group(1)

    return _STRIP_RE.sub(repl, text), sorted(found)


def find_bare_tools(text: str, vocabulary: list[str]) -> list[str]:
    """Vocabulary tool names that appear unprefixed in the text (word-bounded).

    The (?!\\w|\\.\\w) lookahead excludes file-path/extension contexts like
    `data/contributo_unificato.json` (tool name followed by .word).
    """
    hits = []
    for tool in vocabulary:
        if re.search(rf"(?<![\w:]){re.escape(tool)}(?!\w|\.\w)", text):
            hits.append(tool)
    return sorted(hits)


def add_prefixes(text: str, tools: list[str], template: str = "legal-it:{}") -> str:
    """Prefix every word-bounded occurrence of each tool name.

    The lookbehind excludes '_' and ':' so mcp__legal-it__X and legal-it:X are
    never touched — add_prefixes(strip_prefixes(t)) is byte-identical.
    """
    for tool in sorted(set(tools), key=len, reverse=True):
        text = re.sub(
            rf"(?<![\w:]){re.escape(tool)}(?!\w|\.\w)", template.format(tool), text
        )
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_toolnames.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/corpus/toolnames.py tests/unit/test_corpus_toolnames.py
git commit -m "feat(corpus): symmetric legal-it prefix rewriting"
```

---

### Task 4: Claude projector

**Files:**
- Create: `scripts/corpus/project_claude.py`
- Test: `tests/unit/test_corpus_projection.py`

**Interfaces:**
- Consumes: `frontmatter.py` (Task 1), `toolnames.py` (Task 3).
- Produces: `project(root: Path, out: Path) -> None` and a CLI `python scripts/corpus/project_claude.py [--out DIR]`. Projects `content/skills|agents|commands` → `<out>/plugin/...` and `content/references` → `<out>/plugin/server/src/data/references`. Consumed by Tasks 5, 7 and by the drift gate. NOTE: writes to the REAL path `plugin/server/src/...`, never through the repo-root `src` symlink, so `--out tmpdir` works.

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]

def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "corpus" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SKILL = (
    "---\n"
    "name: demo\n"
    "description: Demo skill.\n"
    "tools: [cite_law, leggi_sentenza]\n"
    'prompt: {"name": "demo", "description": "d", "args": []}\n'
    "---\n\nUsa `cite_law`, poi leggi_sentenza(n, a).\n"
)
COMMAND = (
    "---\n"
    "name: norma\n"
    "description: Cerca una norma.\n"
    "tools: cite_law, cerca_brocardi, Bash\n"
    "---\n\nUsa `cite_law`; poi proponi `cerca_brocardi`. Se serve, usa Bash.\n"
)
AGENT = "---\nname: civilista\ndescription: Civilista.\nmodel: sonnet\ntools: [cite_law]\n---\n\nUsa `cite_law`.\n"
REF = "Riferimento condiviso senza frontmatter.\n"

def _make_content(root: Path):
    (root / "content/skills/demo/references").mkdir(parents=True)
    (root / "content/tool-vocabulary.json").write_text(
        '["cerca_brocardi", "cite_law", "leggi_sentenza"]', encoding="utf-8"
    )
    (root / "content/skills/demo/SKILL.md").write_text(SKILL, encoding="utf-8")
    (root / "content/skills/demo/references/nota.md").write_text("Vedi `cite_law`.\n", encoding="utf-8")
    (root / "content/agents").mkdir(parents=True)
    (root / "content/agents/civilista.md").write_text(AGENT, encoding="utf-8")
    (root / "content/commands").mkdir(parents=True)
    (root / "content/commands/norma.md").write_text(COMMAND, encoding="utf-8")
    (root / "content/references").mkdir(parents=True)
    (root / "content/references/fonti.md").write_text(REF, encoding="utf-8")

def test_projection_shapes_all_four_asset_kinds(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    out = tmp_path / "out"
    _make_content(src_root)
    pc.project(src_root, out)

    skill = (out / "plugin/skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "tools:" not in skill and "prompt:" not in skill
    assert "`legal-it:cite_law`" in skill and "legal-it:leggi_sentenza(n, a)" in skill

    ref = (out / "plugin/skills/demo/references/nota.md").read_text(encoding="utf-8")
    assert "`legal-it:cite_law`" in ref

    cmd = (out / "plugin/commands/norma.md").read_text(encoding="utf-8")
    assert "allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi, Bash" in cmd
    assert not any(l.startswith("tools:") for l in cmd.splitlines())
    assert "`legal-it:cite_law`" in cmd and "legal-it:Bash" not in cmd

    ag = (out / "plugin/agents/civilista.md").read_text(encoding="utf-8")
    assert "model: sonnet" in ag and "tools:" not in ag and "`legal-it:cite_law`" in ag

    shared = (out / "plugin/server/src/data/references/fonti.md").read_text(encoding="utf-8")
    assert shared == REF

def test_projection_fails_on_leftover_prefix_in_content(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    bad = src_root / "content/skills/demo/SKILL.md"
    bad.write_text(SKILL.replace("`cite_law`", "`legal-it:cite_law`"), encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit):
        pc.project(src_root, tmp_path / "out")

def test_cli_runs_against_real_corpus_once_it_exists(tmp_path):
    if not (REPO / "content" / "skills").is_dir():
        import pytest
        pytest.skip("corpus not yet migrated (Task 5)")
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/corpus/project_claude.py"), "--out", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_projection.py -q`
Expected: FAIL (module missing)

- [ ] **Step 3: Write the implementation**

```python
"""Project the content/ corpus onto the Claude target tree.

content/skills   -> <out>/plugin/skills    (strip 'tools:'/'prompt:', prefix tool names)
content/agents   -> <out>/plugin/agents    (strip 'tools:', prefix tool names)
content/commands -> <out>/plugin/commands  ('tools:' line -> 'allowed-tools:' line, prefix)
content/references -> <out>/plugin/server/src/data/references (verbatim copy)

Run from the repo root:  python scripts/corpus/project_claude.py [--out DIR]
Without --out it writes into the working tree (the generated dirs are committed:
the Claude marketplace installs the plugin/ tree straight from git).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402
import toolnames as tn  # noqa: E402

ROOT = _HERE.parents[1]


def _parse_tools(fm_lines: list[str]) -> list[str]:
    rng = fm.block_range(fm_lines, "tools")
    if rng is None:
        return []
    raw = fm_lines[rng[0]].split(":", 1)[1].strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _check_no_prefix(path: Path, text: str) -> None:
    if "legal-it:" in text:
        raise SystemExit(f"{path}: corpus files must use bare tool names, found 'legal-it:'")


def _load_vocab(root: Path) -> set[str]:
    return set(json.loads((root / "content" / "tool-vocabulary.json").read_text(encoding="utf-8")))


def _project_doc(text: str, vocab: set[str], *, command: bool) -> str:
    lines, body = fm.split(text)
    tools = _parse_tools(lines)
    # allowed-tools may carry NON-MCP entries (Bash, CronCreate, ...): only
    # vocabulary members get the legal-it namespace; the rest pass through
    # verbatim, in both the allowed-tools line and the body rewrite.
    mcp_tools = [t for t in tools if t in vocab]
    if command and tools:
        allowed = ", ".join(f"mcp__legal-it__{t}" if t in vocab else t for t in tools)
        lines = fm.replace_line(lines, "tools", f"allowed-tools: {allowed}")
    else:
        lines = fm.strip_keys(lines, ["tools"])
    lines = fm.strip_keys(lines, ["prompt"])
    return fm.join(lines, tn.add_prefixes(body, mcp_tools))


def project(root: Path, out: Path) -> None:
    content = root / "content"
    vocab = _load_vocab(root)

    skills_out = out / "plugin" / "skills"
    if skills_out.exists():
        shutil.rmtree(skills_out)
    for skill_dir in sorted((content / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        dest = skills_out / skill_dir.name
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        _check_no_prefix(skill_dir / "SKILL.md", skill_text)
        fm_lines, _ = fm.split(skill_text)
        tools = _parse_tools(fm_lines)
        for src_file in sorted(skill_dir.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(skill_dir)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel == Path("SKILL.md"):
                target.write_text(_project_doc(skill_text, vocab, command=False), encoding="utf-8")
            elif src_file.suffix == ".md":
                text = src_file.read_text(encoding="utf-8")
                _check_no_prefix(src_file, text)
                target.write_text(
                    tn.add_prefixes(text, [t for t in tools if t in vocab]), encoding="utf-8"
                )
            else:
                shutil.copy2(src_file, target)

    for kind, is_command in (("agents", False), ("commands", True)):
        kind_out = out / "plugin" / kind
        if kind_out.exists():
            shutil.rmtree(kind_out)
        kind_out.mkdir(parents=True, exist_ok=True)
        src_kind = content / kind
        if not src_kind.is_dir():
            continue
        for src_file in sorted(src_kind.glob("*.md")):
            text = src_file.read_text(encoding="utf-8")
            _check_no_prefix(src_file, text)
            (kind_out / src_file.name).write_text(
                _project_doc(text, vocab, command=is_command), encoding="utf-8"
            )

    refs_src = content / "references"
    if refs_src.is_dir():
        refs_out = out / "plugin" / "server" / "src" / "data" / "references"
        if refs_out.exists():
            shutil.rmtree(refs_out)
        refs_out.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(refs_src.glob("*.md")):
            shutil.copy2(src_file, refs_out / src_file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    project(ROOT, args.out)
    print(f"projected content/ -> {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_projection.py -q`
Expected: 2 passed, 1 skipped (CLI test skips until the corpus exists)

- [ ] **Step 5: Commit**

```bash
git add scripts/corpus/project_claude.py tests/unit/test_corpus_projection.py
git commit -m "feat(corpus): claude target projector"
```

---

### Task 5: Migrate the corpus and prove the round trip

The riskiest task: `plugin/skills|agents|commands` move to `content/`, get rewritten to bare tool names, and are regenerated by the projector — all in ONE commit so no commit ever lacks a valid `plugin/` tree.

**Files:**
- Create: `scripts/corpus/migrate_corpus.py` (one-shot, kept for audit)
- Move: `plugin/skills/` → `content/skills/`, `plugin/agents/` → `content/agents/`, `plugin/commands/` → `content/commands/` (then regenerated at `plugin/`)
- Test: `tests/unit/test_corpus_build.py` (drift gate, first check)

**Interfaces:**
- Consumes: toolkit from Tasks 1-4, `content/tool-vocabulary.json` (Task 2).
- Produces: the `content/` corpus with `tools:` declarations; regenerated `plugin/` subtrees; `test_corpus_build.py::test_claude_projection_matches_committed` used by every later task as the drift gate.

- [ ] **Step 1: Write the migration script**

```python
"""ONE-SHOT migration: plugin corpus -> content corpus with bare tool names.

Run from the repo root AFTER:
  git mv plugin/skills content/skills
  git mv plugin/agents content/agents
  git mv plugin/commands content/commands

For every markdown file: strip 'legal-it:' prefixes. For skills/agents: declare
the union of stripped names + bare vocabulary names found in bodies as a
'tools: [...]' frontmatter line. For commands: turn the 'allowed-tools:' line
into a 'tools:' line (order preserved — the projector reverses it verbatim).
Kept in the repo for audit; rerunning on a migrated corpus is a no-op.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402
import toolnames as tn  # noqa: E402

ROOT = _HERE.parents[1]
VOCAB = json.loads((ROOT / "content" / "tool-vocabulary.json").read_text(encoding="utf-8"))


def migrate_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    md_files = [p for p in sorted(skill_dir.rglob("*.md"))]
    stripped: dict[Path, str] = {}
    tools: set[str] = set()
    for p in md_files:
        text, found = tn.strip_prefixes(p.read_text(encoding="utf-8"))
        stripped[p] = text
        tools.update(found)
    lines, body = fm.split(stripped[skill_md])
    tools.update(tn.find_bare_tools(body, VOCAB))
    for p in md_files:
        if p != skill_md:
            tools.update(tn.find_bare_tools(stripped[p], VOCAB))
            p.write_text(stripped[p], encoding="utf-8")
    if fm.block_range(lines, "tools") is None and tools:
        lines = fm.append_lines(lines, ["tools: [" + ", ".join(sorted(tools)) + "]"])
    skill_md.write_text(fm.join(lines, body), encoding="utf-8")


def migrate_agent(path: Path) -> None:
    text, found = tn.strip_prefixes(path.read_text(encoding="utf-8"))
    lines, body = fm.split(text)
    tools = set(found) | set(tn.find_bare_tools(body, VOCAB))
    if fm.block_range(lines, "tools") is None and tools:
        lines = fm.append_lines(lines, ["tools: [" + ", ".join(sorted(tools)) + "]"])
    path.write_text(fm.join(lines, body), encoding="utf-8")


def migrate_command(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines, body = fm.split(text)
    rng = fm.block_range(lines, "allowed-tools")
    declared: list[str] = []
    if rng is not None:
        raw = lines[rng[0]].split(":", 1)[1]
        # Entries without the mcp__legal-it__ prefix (Bash, CronCreate, ...)
        # are harness tools: kept verbatim, re-emitted verbatim by the projector.
        declared = [
            t.strip().removeprefix("mcp__legal-it__") for t in raw.split(",") if t.strip()
        ]
        lines = fm.replace_line(lines, "allowed-tools", "tools: " + ", ".join(declared))
    body, found = tn.strip_prefixes(body)
    missing = set(found) - set(declared)
    if missing:
        raise SystemExit(f"{path}: body uses tools missing from allowed-tools: {sorted(missing)}")
    path.write_text(fm.join(lines, body), encoding="utf-8")


def main() -> None:
    for d in sorted((ROOT / "content" / "skills").iterdir()):
        if d.is_dir():
            migrate_skill(d)
    for p in sorted((ROOT / "content" / "agents").glob("*.md")):
        migrate_agent(p)
    for p in sorted((ROOT / "content" / "commands").glob("*.md")):
        migrate_command(p)
    leftovers = [
        str(p) for p in (ROOT / "content").rglob("*.md")
        if "legal-it:" in p.read_text(encoding="utf-8")
    ]
    if leftovers:
        raise SystemExit(f"prefix leftovers in content/: {leftovers}")
    print("migration complete; content/ uses bare tool names")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Execute the move + migration + projection**

```bash
mkdir -p content
git mv plugin/skills content/skills
git mv plugin/agents content/agents
git mv plugin/commands content/commands
uv run --python 3.12 --extra dev python scripts/corpus/migrate_corpus.py
uv run --python 3.12 --extra dev python scripts/corpus/project_claude.py
git add -A
```

- [ ] **Step 3: Verify the round trip — THE gate of this task**

Run: `git diff --cached --stat -- plugin/`
Expected: `plugin/skills`, `plugin/agents`, `plugin/commands` fully re-created. All 8 commands round-trip BYTE-IDENTICAL — including `digest.md` (whose `allowed-tools` ends with the non-MCP `CronCreate, CronDelete`) and `release.md` (entirely harness tools: `Bash, Read, Edit, Write, Grep, Glob`): non-vocabulary entries pass through unprefixed, in the allowed-tools line AND in body prose. The only content differences are `legal-it:` prefixes ADDED to previously-bare tool names. Adversarial simulation on the real corpus measured this expected set (13 files):
- skills: `cookie-audit/SKILL.md`, `esporta-documento/SKILL.md`, `analisi-fornitori/SKILL.md` (genera_dpa, verifica_partita_iva_vies ×2, genera_report_fornitori), `analisi-giurisprudenziale/SKILL.md`, `analisi-articolo/SKILL.md`, `genera-atto/SKILL.md`
- skill references: `analisi-fornitori/references/dpa-whitelist.md`, `analisi-fornitori/references/metodologia.md`, `cookie-audit/references/compliance-checklist.md`, `procure-quotazioni/references/rilevamento-fase.md`
- agents: `digest-giuridico.md`, `redattore-atti.md`, `ricerca-giurisprudenziale.md`

The HARD gate — every changed line must be a PURE prefix insertion (strip `legal-it:` from both sides of the diff; the remainders must match):
```bash
diff <(git diff --cached -- plugin/ | grep '^-[^-]' | cut -c2- | sed 's/legal-it://g' | sort) \
     <(git diff --cached -- plugin/ | grep '^+[^+]' | cut -c2- | sed 's/legal-it://g' | sort)
```
Expected: empty output. Non-empty means some change is NOT a pure prefix insertion — STOP and debug the toolkit (superpowers:systematic-debugging); do not rationalize the diff.

Then eyeball the changed files: every new prefix must sit on a genuine tool invocation or mention — never on a file path, JSON filename or data column (the `(?!\w|\.\w)` lookahead protects `data/contributo_unificato.json`-style paths; anything path-like that still got prefixed is a toolkit bug). Files beyond the 13 listed are possible if the simulation missed a prose mention — the same two checks apply.

- [ ] **Step 4: Add the drift gate test**

```python
"""Drift gate: the committed generated artifacts must match a fresh projection."""
import filecmp
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]

def _assert_trees_equal(a: Path, b: Path) -> None:
    cmp = filecmp.dircmp(a, b)
    assert not cmp.left_only and not cmp.right_only and not cmp.diff_files, (
        f"{a} vs {b}: only_in_committed={cmp.left_only} only_in_fresh={cmp.right_only} "
        f"diff={cmp.diff_files}"
    )
    for sub in cmp.common_dirs:
        _assert_trees_equal(a / sub, b / sub)

def test_claude_projection_matches_committed(tmp_path):
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/corpus/project_claude.py"), "--out", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    for sub in ("plugin/skills", "plugin/agents", "plugin/commands"):
        _assert_trees_equal(REPO / sub, tmp_path / sub)
    refs = REPO / "plugin/server/src/data/references"
    if refs.is_dir():  # exists from Task 9 onward
        _assert_trees_equal(refs, tmp_path / "plugin/server/src/data/references")
```

- [ ] **Step 5: Run the full unit suite**

Run: `uv run --python 3.12 --extra dev pytest tests/unit -q`
Expected: all pass (including the new drift gate and the previously-skipped CLI projection test).

- [ ] **Step 6: Commit (single commit — tree stays consistent)**

```bash
git add -A
git commit -m "refactor(corpus)!: move skills/agents/commands to content/, regenerate plugin/ via projector

plugin/{skills,agents,commands} are now generated projections of content/
(bare tool names + tools: declarations). Byte-identical round trip except
the files where previously-bare tool names are normalized (measured: 13,
listed in the diff)."
```

---

### Task 6: Declare the 16 prompt blocks

Each of the 16 skills that duplicate an MCP prompt gets a single-line `prompt:` frontmatter entry (JSON payload — parsed with `json.loads`, no YAML library). The projector already strips it (Task 4), so `plugin/` output does not change and the drift gate stays green.

**Files:**
- Modify: `content/skills/<16 dirs>/SKILL.md` (append one line to frontmatter, after `tools:`)

**Interfaces:**
- Produces: `prompt:` lines consumed by `generate_prompts.py` (Task 8). Contract: `{"name": str, "description": str, "args": [{"name": str, "type": "str"|"float"|"int", "default"?: str}]}` — `default` present only for optional args.

- [ ] **Step 1: Append the exact lines** (one per file; signatures are verbatim from the current `src/prompts.py` — do not improvise)

`content/skills/analisi-sinistro/SKILL.md`:
```
prompt: {"name": "analisi_sinistro", "description": "Analisi completa sinistro stradale/sanitario/lavoro con quantificazione danni", "args": [{"name": "tipo_sinistro", "type": "str"}, {"name": "percentuale_invalidita", "type": "float"}, {"name": "eta_vittima", "type": "int"}]}
```
`content/skills/recupero-credito/SKILL.md`:
```
prompt: {"name": "recupero_credito", "description": "Workflow completo per recupero credito: interessi, rivalutazione, decreto ingiuntivo e parcella", "args": [{"name": "importo", "type": "float"}, {"name": "tipo_credito", "type": "str"}, {"name": "data_scadenza", "type": "str"}]}
```
`content/skills/causa-civile/SKILL.md`:
```
prompt: {"name": "causa_civile", "description": "Pianificazione causa civile: contributo unificato, scadenze, impugnazioni e preventivo", "args": [{"name": "valore_causa", "type": "float"}, {"name": "rito", "type": "str"}, {"name": "grado", "type": "str"}]}
```
`content/skills/pianificazione-successione/SKILL.md`:
```
prompt: {"name": "pianificazione_successione", "description": "Pianificazione successoria: quote ereditarie, imposte e adempimenti", "args": [{"name": "valore_asse", "type": "float"}, {"name": "grado_parentela", "type": "str"}, {"name": "numero_eredi", "type": "int"}]}
```
`content/skills/parere-legale/SKILL.md`:
```
prompt: {"name": "parere_legale", "description": "Struttura per parere legale: fatto, diritto, normativa e conclusioni con citazione norme", "args": [{"name": "area_diritto", "type": "str"}, {"name": "quesito", "type": "str"}]}
```
`content/skills/quantificazione-danni/SKILL.md`:
```
prompt: {"name": "quantificazione_danni", "description": "Quantificazione danni: biologico, patrimoniale o morale con personalizzazione e attualizzazione", "args": [{"name": "tipo_danno", "type": "str"}, {"name": "importo_o_percentuale", "type": "float"}, {"name": "eta_vittima", "type": "int"}]}
```
`content/skills/calcolo-parcella/SKILL.md`:
```
prompt: {"name": "calcolo_parcella", "description": "Calcolo parcella avvocato per attività civile, penale o stragiudiziale", "args": [{"name": "tipo_attivita", "type": "str"}, {"name": "valore_causa", "type": "float"}]}
```
`content/skills/verifica-prescrizione/SKILL.md`:
```
prompt: {"name": "verifica_prescrizione", "description": "Verifica prescrizione di un diritto civile o di un reato penale", "args": [{"name": "tipo", "type": "str"}, {"name": "descrizione_fatto", "type": "str"}, {"name": "data_fatto", "type": "str"}]}
```
`content/skills/ricerca-normativa/SKILL.md`:
```
prompt: {"name": "ricerca_normativa", "description": "Ricerca normativa completa su un tema giuridico: norme applicabili, gerarchia delle fonti e coordinamento", "args": [{"name": "tema", "type": "str"}, {"name": "area_diritto", "type": "str"}]}
```
`content/skills/analisi-articolo/SKILL.md`:
```
prompt: {"name": "analisi_articolo", "description": "Analisi approfondita di un singolo articolo di legge: testo, ratio, giurisprudenza e collegamenti", "args": [{"name": "riferimento_norma", "type": "str"}]}
```
`content/skills/confronto-norme/SKILL.md`:
```
prompt: {"name": "confronto_norme", "description": "Confronto tra due o più norme: differenze, sovrapposizioni, prevalenza e coordinamento", "args": [{"name": "norma_1", "type": "str"}, {"name": "norma_2", "type": "str"}, {"name": "contesto", "type": "str", "default": ""}]}
```
`content/skills/mappatura-normativa/SKILL.md`:
```
prompt: {"name": "mappatura_normativa", "description": "Mappatura del quadro normativo completo per un settore o attività: tutte le fonti applicabili organizzate per livello", "args": [{"name": "settore", "type": "str"}, {"name": "attivita_specifica", "type": "str", "default": ""}]}
```
`content/skills/analisi-giurisprudenziale/SKILL.md`:
```
prompt: {"name": "analisi_giurisprudenziale", "description": "Analisi giurisprudenziale strutturata su un tema: ricerca su Italgiure, lettura decisioni chiave e sintesi orientamenti", "args": [{"name": "tema", "type": "str"}, {"name": "archivio", "type": "str", "default": "tutti"}]}
```
`content/skills/analisi-delibere-consob/SKILL.md`:
```
prompt: {"name": "analisi_delibere_consob", "description": "Ricerca e analisi delibere CONSOB su un tema: provvedimenti, sanzioni, regolamenti mercati finanziari", "args": [{"name": "tema", "type": "str"}, {"name": "tipologia", "type": "str", "default": ""}, {"name": "argomento", "type": "str", "default": ""}]}
```
`content/skills/novita-consob/SKILL.md`:
```
prompt: {"name": "novita_consob", "description": "Ultime novità CONSOB: delibere recenti per tipologia o argomento con sintesi degli orientamenti", "args": [{"name": "tipologia", "type": "str", "default": ""}, {"name": "argomento", "type": "str", "default": ""}]}
```
`content/skills/compliance-privacy/SKILL.md` (description verified verbatim at `src/prompts.py:1189`):
```
prompt: {"name": "compliance_privacy", "description": "Workflow completo compliance privacy GDPR: analisi base giuridica, DPIA, registro, informativa e DPA", "args": [{"name": "titolare", "type": "str"}, {"name": "tipo_trattamento", "type": "str"}, {"name": "contesto", "type": "str"}]}
```

- [ ] **Step 2: Verify the drift gate still passes** (prompt: is stripped by projection)

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_build.py tests/unit/test_corpus_projection.py -q`
Expected: all pass, no `plugin/` diff (`git status --short -- plugin/` empty).

- [ ] **Step 3: Commit**

```bash
git add content/skills
git commit -m "feat(corpus): declare prompt blocks on the 16 skills that mirror MCP prompts"
```

---

### Task 7: Promote the 7 orphan prompts to skills

The 7 workflows that exist only in `src/prompts.py` become content skills (reachable on every harness). `src/prompts.py` is NOT touched here — it still carries all 23 hand-written prompts until Task 8 swaps it wholesale, so every commit keeps the full prompt surface.

**Files:**
- Create: `content/skills/{analisi-tributaria,analisi-giurisprudenza-amministrativa,analisi-giurisprudenza-europea,analisi-costituzionale,ricerca-gazzetta,orientamento-giurisprudenziale,attuazione-direttiva}/SKILL.md`
- Regenerate: `plugin/skills/` (projection → 30 skills)

**Interfaces:**
- Consumes: prompt bodies at `src/prompts.py` (line ranges below) as the text source; projector CLI.
- Produces: 7 skills each carrying a `prompt:` block, so Task 8 generates all 23 prompts.

**Body derivation rules (apply mechanically to the prompt's returned f-string):**
- R1. Body = the prompt's text between the opening and closing `"""`, verbatim, in the same order.
- R2. Prepend `# <Title>` (humanized skill name) + blank line + one-sentence scope line.
- R3. The leading data lines (`TEMA: {tema}`, conditional `ENTE:` lines, etc.) become a `## Dati richiesti` bullet list: one bullet per prompt arg — `- **arg** — <the note the original line carried>. Se non fornito, chiedilo.`; optional args add `(opzionale)` and the default.
- R4. Every remaining `{param}` interpolation becomes `<param>` inside the code-ish contexts (e.g. `query="{tema}"` → `query=<tema>`) or the backticked param name in prose; conditional f-string fragments (like `ente_filter`) become prose: «aggiungi `ente=...` se indicato».
- R5. `\\"` escape sequences in the Python source render as `\"` in the skill body (same text the prompt produced at runtime).
- R6. Tool names stay bare; declare them in `tools:`. Never add doctrine that is not in the source text.

**Worked example — `content/skills/analisi-tributaria/SKILL.md` (complete file, derived from `src/prompts.py:1053-1103` with R1-R6):**

```markdown
---
name: analisi-tributaria
description: Analisi della giurisprudenza tributaria su un tema fiscale — ricerca CeRDEF (CGT e Cassazione tributaria), lettura dei provvedimenti chiave e sintesi degli orientamenti con quadro normativo. Usa quando l'utente chiede giurisprudenza tributaria, sentenze su IVA, IRES, accertamento, riscossione, contenzioso fiscale o CGT.
tools: [cerca_giurisprudenza, cerca_giurisprudenza_tributaria, cerdef_leggi_provvedimento, cite_law]
prompt: {"name": "analisi_tributaria", "description": "Analisi giurisprudenza tributaria: ricerca CeRDEF, lettura provvedimenti e sintesi orientamenti fiscali", "args": [{"name": "tema", "type": "str"}, {"name": "ente", "type": "str", "default": ""}]}
---

# Analisi Tributaria

Esegui un'analisi della giurisprudenza tributaria sul tema indicato.

## Dati richiesti

- **tema** — il tema fiscale da analizzare. Se non fornito, chiedilo.
- **ente** (opzionale) — filtro ente: corte_suprema / cgt_primo_grado / cgt_secondo_grado.

## Workflow

### Fase 1 — Ricerca CeRDEF
Chiama `cerca_giurisprudenza_tributaria(query=<tema>)` — aggiungi `ente=<ente>` se indicato — per trovare
sentenze e provvedimenti nella banca dati del MEF.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia Cassazione se presente).
Per ciascuno, chiama `cerdef_leggi_provvedimento(guid)` per leggere massima e testo completo.

### Fase 3 — Quadro normativo
Per le norme tributarie citate nelle sentenze, chiama `cite_law(reference)` per il testo vigente.
Fonti tipiche: TUIR (DPR 917/1986), D.Lgs. 546/1992, DPR 633/1972 (IVA), D.Lgs. 472/1997.

### Fase 4 — Giurisprudenza Cassazione (se pertinente)
Se emergono principi di diritto rilevanti, cerca anche su Italgiure:
`cerca_giurisprudenza(query="\"<tema>\"", archivio="civile")` per sezione tributaria.

### Fase 5 — Sintesi

## Analisi Giurisprudenza Tributaria: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Ente | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Quadro Normativo
Norme tributarie rilevanti con testo da cite_law.

### 4. Indicazioni Operative
Raccomandazioni pratiche per il contribuente/professionista.

## Regole

- Usare `cerca_giurisprudenza_tributaria` e `cerdef_leggi_provvedimento` per i provvedimenti CeRDEF.
- Usare `cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza o GUID a memoria.
```

**The other 6 skills** — same rules; source line ranges and exact frontmatter below. `prompt:` descriptions: copy VERBATIM from each `@mcp.prompt(description=...)` decorator (line refs below), never from memory.

| Skill dir | Source lines | tools: | prompt name + args |
|---|---|---|---|
| `analisi-giurisprudenza-amministrativa` | 1278-1332 | `[cerca_giurisprudenza_amministrativa, cite_law, giurisprudenza_amm_su_norma, leggi_provvedimento_amm]` | `analisi_giurisprudenza_amministrativa` — `tema: str`, `sede: str = ""` |
| `analisi-giurisprudenza-europea` | 1106-1180 | `[cerca_giurisprudenza_cgue, cite_law, giurisprudenza_cgue_su_norma, leggi_sentenza_cgue]` | `analisi_giurisprudenza_europea` — `tema: str`, `corte: str = "tutte"` |
| `analisi-costituzionale` | 1340-1376 | `[cerca_pronuncia_costituzionale, cite_law, leggi_pronuncia_costituzionale, pronunce_cost_su_norma]` | `analisi_costituzionale` — `tema: str`, `tipo: str = ""` |
| `ricerca-gazzetta` | 1384-1414 | `[cerca_gazzetta_ufficiale, cite_law, leggi_atto_gazzetta, scarica_pdf_gazzetta, sommario_gazzetta, ultime_gazzette]` | `ricerca_gazzetta` — `tema: str`, `serie: str = "serie_generale"` |
| `orientamento-giurisprudenziale` | 1422-1459 | `[cite_law, leggi_sentenza, mappa_orientamento, orientamento_su_norma, orientamento_su_principio]` | `orientamento_giurisprudenziale` — `riferimento: str`, `archivio: str = "tutti"` |
| `attuazione-direttiva` | 1467-1500 | `[cite_law, get_eu_basis, get_italian_implementation, giurisprudenza_cgue_su_norma]` | `attuazione_direttiva` — `direttiva: str` |

**Frontmatter `description` (trigger-style, use these exact texts):**
- `analisi-giurisprudenza-amministrativa`: «Analisi della giurisprudenza amministrativa su un tema — ricerca TAR/Consiglio di Stato, lettura dei provvedimenti e sintesi degli orientamenti. Usa quando l'utente chiede sentenze TAR o CdS, appalti, urbanistica, edilizia, accesso agli atti, provvedimenti della PA o Adunanza Plenaria.»
- `analisi-giurisprudenza-europea`: «Analisi della giurisprudenza della Corte di Giustizia UE su un tema — ricerca CGUE/Tribunale UE, lettura delle sentenze chiave e sintesi degli orientamenti. Usa quando l'utente chiede sentenze CGUE, rinvio pregiudiziale, interpretazione di direttive o regolamenti UE o conclusioni dell'Avvocato generale.»
- `analisi-costituzionale`: «Analisi delle pronunce della Corte Costituzionale su un tema o una norma — ricerca, lettura delle pronunce chiave e sintesi con i parametri costituzionali invocati. Usa quando l'utente chiede sentenze della Consulta, questioni di legittimità costituzionale o pronunce additive/interpretative.»
- `ricerca-gazzetta`: «Ricerca e lettura di atti pubblicati in Gazzetta Ufficiale — novità per serie, ricerca parametrica, testo as-published e PDF ufficiale. Usa quando l'utente chiede cosa è uscito in Gazzetta, il testo di un decreto appena pubblicato, un atto per estremi di pubblicazione o il sommario di una GU.»
- `orientamento-giurisprudenziale`: «Mappa descrittiva degli orientamenti di legittimità su una norma o un principio — conformi vs contrasti, interventi delle Sezioni Unite, evoluzione temporale. Usa quando l'utente chiede se un orientamento è consolidato, se c'è contrasto in Cassazione o come si è evoluta la giurisprudenza su una norma.»
- `attuazione-direttiva`: «Recepimento di una direttiva UE in Italia — individua le misure nazionali di attuazione, il testo italiano vigente e la giurisprudenza CGUE collegata. Usa quando l'utente chiede come è stata recepita una direttiva, quale atto italiano la attua o la base UE di un atto nazionale.»

**YAML rule (hard):** frontmatter `description` values are unquoted plain scalars — they must NEVER contain `: ` (colon+space), which breaks YAML parsing. All 23 existing skills respect this; use `—` instead. (The `prompt:` JSON lines are exempt: `{...}` is a YAML flow mapping with quoted strings.)

- [ ] **Step 1: Write the 7 SKILL.md files** applying R1-R6 to each source range. Read each range first (`sed -n '<start>,<end>p' src/prompts.py`).
- [ ] **Step 2: Project and verify**

```bash
uv run --python 3.12 --extra dev python scripts/corpus/project_claude.py
ls plugin/skills | wc -l   # expect 30
uv run --python 3.12 --extra dev pytest tests/unit/test_corpus_build.py tests/unit/test_corpus_projection.py -q
```

- [ ] **Step 3: Commit**

```bash
git add content/skills plugin/skills
git commit -m "feat(corpus): promote 7 prompt-only workflows to skills (30 total)"
```

---

### Task 8: Generate src/prompts.py from the corpus

**Files:**
- Create: `scripts/corpus/generate_prompts.py`
- Replace (becomes generated): `src/prompts.py` — i.e. `plugin/server/src/prompts.py`
- Modify (if assertions break): `tests/unit/test_prompts.py`
- Create: `tests/unit/test_prompt_surface.py`
- Modify: `tests/unit/test_corpus_build.py` (add generated-prompts drift check)

**Interfaces:**
- Consumes: `prompt:` JSON lines (Tasks 6-7), skill bodies.
- Produces: `src/prompts.py` with 23 module-level functions whose names, parameter names, annotations and defaults are IDENTICAL to the current hand-written ones (the frozen table below is the contract). Each returns `"DATI:\n" + one f-line per arg + "\n" + <skill body>`.

- [ ] **Step 1: Write the generator**

```python
"""Generate src/prompts.py from content/skills/*/SKILL.md 'prompt:' blocks.

Run from the repo root:  python scripts/corpus/generate_prompts.py [--out FILE]
Deterministic: functions are emitted in alphabetical order of prompt name.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402

ROOT = _HERE.parents[1]
_TYPES = {"str": "str", "float": "float", "int": "int"}

_HEADER = '''"""MCP Prompts — GENERATED from content/skills/*/SKILL.md 'prompt:' blocks.

Do not edit by hand: run  python scripts/corpus/generate_prompts.py
23 guided legal workflow prompts, for MCP clients that support prompts.
"""

from src.server import mcp

'''


def _collect() -> list[tuple[dict, str]]:
    found = []
    for skill_dir in sorted((ROOT / "content" / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        lines, body = fm.split(skill_md.read_text(encoding="utf-8"))
        rng = fm.block_range(lines, "prompt")
        if rng is None:
            continue
        meta = json.loads(lines[rng[0]].split(":", 1)[1])
        found.append((meta, body.strip("\n") + "\n"))
    return sorted(found, key=lambda x: x[0]["name"])


def _emit(meta: dict, body: str) -> str:
    name = meta["name"]
    const = f"_BODY_{name.upper()}"
    escaped = body.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    params = []
    for a in meta["args"]:
        p = f"{a['name']}: {_TYPES[a['type']]}"
        if "default" in a:
            p += f" = {a['default']!r}"
        params.append(p)
    dati = "".join(
        f'        f"- {a["name"]}: {{{a["name"]}}}\\n"\n' for a in meta["args"]
    )
    return (
        f'{const} = """\\\n{escaped}"""\n\n\n'
        f"@mcp.prompt(description={meta['description']!r})\n"
        f"def {name}({', '.join(params)}) -> str:\n"
        f"    return (\n"
        f'        "DATI:\\n"\n'
        f"{dati}"
        f'        "\\n"\n'
        f"        + {const}\n"
        f"    )\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "plugin" / "server" / "src" / "prompts.py"
    )
    args = parser.parse_args()
    items = _collect()
    code = _HEADER + "\n\n".join(_emit(m, b) for m, b in items)
    args.out.write_text(code, encoding="utf-8")
    print(f"{len(items)} prompts -> {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the frozen-surface test BEFORE swapping the file** — it must pass against the CURRENT hand-written `src/prompts.py`, then keep passing against the generated one. That is the equivalence gate.

```python
"""The MCP prompt surface is frozen: 23 names with exact signatures.

Passes against the hand-written prompts.py AND against the generated one —
this is the no-regression contract for the corpus consolidation.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from src import prompts  # noqa: E402

E = inspect.Parameter.empty
EXPECTED = {
    "analisi_articolo": [("riferimento_norma", str, E)],
    "analisi_costituzionale": [("tema", str, E), ("tipo", str, "")],
    "analisi_delibere_consob": [("tema", str, E), ("tipologia", str, ""), ("argomento", str, "")],
    "analisi_giurisprudenza_amministrativa": [("tema", str, E), ("sede", str, "")],
    "analisi_giurisprudenza_europea": [("tema", str, E), ("corte", str, "tutte")],
    "analisi_giurisprudenziale": [("tema", str, E), ("archivio", str, "tutti")],
    "analisi_sinistro": [("tipo_sinistro", str, E), ("percentuale_invalidita", float, E), ("eta_vittima", int, E)],
    "analisi_tributaria": [("tema", str, E), ("ente", str, "")],
    "attuazione_direttiva": [("direttiva", str, E)],
    "calcolo_parcella": [("tipo_attivita", str, E), ("valore_causa", float, E)],
    "causa_civile": [("valore_causa", float, E), ("rito", str, E), ("grado", str, E)],
    "compliance_privacy": [("titolare", str, E), ("tipo_trattamento", str, E), ("contesto", str, E)],
    "confronto_norme": [("norma_1", str, E), ("norma_2", str, E), ("contesto", str, "")],
    "mappatura_normativa": [("settore", str, E), ("attivita_specifica", str, "")],
    "novita_consob": [("tipologia", str, ""), ("argomento", str, "")],
    "orientamento_giurisprudenziale": [("riferimento", str, E), ("archivio", str, "tutti")],
    "parere_legale": [("area_diritto", str, E), ("quesito", str, E)],
    "pianificazione_successione": [("valore_asse", float, E), ("grado_parentela", str, E), ("numero_eredi", int, E)],
    "quantificazione_danni": [("tipo_danno", str, E), ("importo_o_percentuale", float, E), ("eta_vittima", int, E)],
    "recupero_credito": [("importo", float, E), ("tipo_credito", str, E), ("data_scadenza", str, E)],
    "ricerca_gazzetta": [("tema", str, E), ("serie", str, "serie_generale")],
    "ricerca_normativa": [("tema", str, E), ("area_diritto", str, E)],
    "verifica_prescrizione": [("tipo", str, E), ("descrizione_fatto", str, E), ("data_fatto", str, E)],
}


def _underlying(obj):
    return getattr(obj, "fn", obj)  # FastMCP may wrap the function


def test_all_23_prompts_exist_with_frozen_signatures():
    for name, expected in EXPECTED.items():
        fn = _underlying(getattr(prompts, name))
        params = list(inspect.signature(fn).parameters.values())
        got = [(p.name, p.annotation, p.default) for p in params]
        assert got == [(n, a, d) for n, a, d in expected], f"{name}: {got}"


def test_rendered_prompt_carries_data_and_doctrine():
    fn = _underlying(prompts.analisi_sinistro)
    text = fn("stradale", 25.0, 40)
    assert "stradale" in text  # arg value flows into the render (old and generated formats differ)
    assert "26972/2008" in text  # San Martino — present in both old prompt and skill body
```

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_prompt_surface.py -q` → must PASS against the current hand-written file. If `getattr(prompts, name)` fails because `@mcp.prompt` replaces the function with a wrapper object, adapt `_underlying` to the actual FastMCP 3.4.7 attribute (inspect one prompt object interactively) — do NOT weaken the signature assertions.

- [ ] **Step 3: Generate and swap**

```bash
uv run --python 3.12 --extra dev python scripts/corpus/generate_prompts.py
git diff --stat -- plugin/server/src/prompts.py
```
Review the diff: same 23 function names; bodies now come from skill text. Sanity-render one prompt: `uv run --python 3.12 --extra dev python -c "import sys; sys.path.insert(0,'.'); from src import prompts; t=prompts.analisi_sinistro.fn('stradale',25.0,40) if hasattr(prompts.analisi_sinistro,'fn') else prompts.analisi_sinistro('stradale',25.0,40); print(t[:400])"`

- [ ] **Step 4: Run the prompt tests; repair test_prompts.py if needed**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_prompt_surface.py tests/unit/test_prompts.py -q`
`test_prompts.py` asserts phrases of the OLD prompt bodies. Measured against the real skill bodies: only the two "esplora" assertions break (lines 32-37 `ricerca_normativa` and 38-43 `analisi_delibere_consob` — "esplora" is absent from those skill bodies); replace them with "Mai citare a memoria" (capital M — ricerca-normativa body) and "TUF (D.Lgs. 58/1998)" respectively. The `analisi_giurisprudenziale` (lines 26-31) and `parere_legale` (lines 44-49) assertions keep passing unchanged. Do not delete tests; any OTHER failure means the generator emitted a wrong body — debug, don't adapt the test.

- [ ] **Step 5: Add the drift check for generated prompts** (append to `tests/unit/test_corpus_build.py`)

```python
def test_generated_prompts_match_committed(tmp_path):
    out = tmp_path / "prompts.py"
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/corpus/generate_prompts.py"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    committed = (REPO / "plugin/server/src/prompts.py").read_bytes()
    assert out.read_bytes() == committed, "src/prompts.py drifted from the corpus — rerun generate_prompts.py"
```

- [ ] **Step 6: Full unit suite, then commit**

```bash
uv run --python 3.12 --extra dev pytest tests/unit -q
git add scripts/corpus/generate_prompts.py plugin/server/src/prompts.py tests/unit/test_prompt_surface.py tests/unit/test_prompts.py tests/unit/test_corpus_build.py
git commit -m "feat(corpus)!: src/prompts.py is now generated from skill prompt blocks

All 23 prompt names/signatures preserved (frozen-surface test). Bodies now
derive from the single skill source; the 16 hand-written duplicates are gone."
```

---

### Task 9: Extract the 12 static resources; resources.py becomes a loader

The 3 data-driven resources (`contributo-unificato`, `irpef-detrazioni`, `interessi-legali`) render from `src/data/*.json` and STAY as code — this is a measured refinement of the spec, which assumed all 15 were static. The 12 inline-literal resources move to `content/references/`.

**Files:**
- Create: `scripts/corpus/extract_references.py` (one-shot, kept for audit)
- Create: `content/references/<12>.md` + generated copies `plugin/server/src/data/references/<12>.md`
- Modify: `src/resources.py` (= `plugin/server/src/resources.py`)
- Test: extend `tests/unit/test_corpus_build.py` reference-tree check (already guarded); `tests/unit/test_resources_static.py`

**Interfaces:**
- Consumes: current `src/resources.py` function bodies; projector (Task 4) copies `content/references/` → `plugin/server/src/data/references/`.
- Produces: `src/resources.py` keeps helpers `_DATA`, `_load`, `_eur`, `_soglia`, `_pct`, `_scaglioni_rows` and the renderers `_render_contributo_unificato` + the `irpef_detrazioni` / `interessi_legali` functions UNTOUCHED (`test_resources_dynamic.py` imports them by name). New `_STATIC_RESOURCES` table + `_make_reader` registration loop.

- [ ] **Step 1: Write and run the extraction script**

```python
"""ONE-SHOT: extract the 12 inline-literal resources to content/references/*.md."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATIC = [
    "procedura_civile", "termini_processuali", "checklist_decreto_ingiuntivo",
    "fonti_diritto_italiano", "codici_e_leggi_principali", "gdpr_checklist",
    "consob_delibere", "ricerca_giurisprudenziale", "cerdef_giurisprudenza",
    "modelli_atti_catalogo", "giustizia_amministrativa", "cgue_giurisprudenza",
]

def main() -> None:
    from src import resources as res
    out_dir = ROOT / "content" / "references"
    out_dir.mkdir(parents=True, exist_ok=True)
    for func_name in STATIC:
        fn = getattr(res, func_name)
        fn = getattr(fn, "fn", fn)  # unwrap FastMCP resource wrapper if present
        text = fn()
        (out_dir / (func_name.replace("_", "-") + ".md")).write_text(text, encoding="utf-8")
        print(f"{func_name} -> {func_name.replace('_', '-')}.md ({len(text)} chars)")

if __name__ == "__main__":
    main()
```

Run: `uv run --python 3.12 --extra dev python scripts/corpus/extract_references.py`
Expected: 12 files in `content/references/`, each non-empty. If `getattr(res, func_name)` fails because the decorator consumed the name, read the function body text directly from the file instead — but verify first; on FastMCP the decorated function usually remains accessible.

- [ ] **Step 2: Rewrite the 12 registrations in `src/resources.py`**

Delete the 12 `@mcp.resource(...)`-decorated inline-literal functions listed in Step 1 (KEEP the module docstring, imports, helpers at lines 13-50, `_render_contributo_unificato`, and the three dynamic resources `contributo_unificato`, `irpef_detrazioni`, `interessi_legali` exactly as they are). Append at the end of the module:

```python
# ---------------------------------------------------------------------------
# Static references — GENERATED copies of content/references/*.md live in
# src/data/references/ (projected by scripts/corpus/project_claude.py).
# One text, two consumers: the MCP resource below and any skill that needs it.
# ---------------------------------------------------------------------------
_REFERENCES_DIR = Path(__file__).parent / "data" / "references"

_STATIC_RESOURCES: list[tuple[str, str, str, str]] = [
    ("legal://riferimenti/procedura-civile", "procedura-civile.md",
     "Procedura Civile Ordinaria",
     "Schema fasi e termini della procedura civile post-Cartabia (D.Lgs. 149/2022)"),
    ("legal://riferimenti/termini-processuali", "termini-processuali.md",
     "Termini Processuali Chiave",
     "Tabella dei principali termini processuali civili post-Cartabia"),
    ("legal://riferimenti/checklist-decreto-ingiuntivo", "checklist-decreto-ingiuntivo.md",
     "Checklist Decreto Ingiuntivo",
     "Checklist operativa per il ricorso per decreto ingiuntivo (artt. 633 ss. c.p.c.)"),
    ("legal://riferimenti/fonti-diritto-italiano", "fonti-diritto-italiano.md",
     "Gerarchia Fonti del Diritto Italiano",
     "Sistema delle fonti, gerarchia normativa, criteri di risoluzione antinomie e formato citazione"),
    ("legal://riferimenti/codici-e-leggi-principali", "codici-e-leggi-principali.md",
     "Codici e Leggi Principali — Riferimento Rapido",
     "Indice ragionato dei principali codici, testi unici e leggi italiane ed europee con ambito e citazione"),
    ("legal://riferimenti/gdpr-checklist", "gdpr-checklist.md",
     "GDPR Compliance — Checklist Operativa",
     "Checklist completa per la conformità GDPR: adempimenti, documenti, scadenze e tool disponibili"),
    ("legal://riferimenti/consob-delibere", "consob-delibere.md",
     "CONSOB — Guida Ricerca Delibere",
     "Guida all'uso dei tool CONSOB: tipologie, argomenti, workflow e riferimenti normativi mercati finanziari"),
    ("legal://riferimenti/ricerca-giurisprudenziale", "ricerca-giurisprudenziale.md",
     "Ricerca Giurisprudenziale — Guida Italgiure",
     "Guida alla ricerca su Italgiure: strategia esplora→filtra→leggi, sintassi Solr, facets e workflow tipo"),
    ("legal://riferimenti/cerdef-giurisprudenza", "cerdef-giurisprudenza.md",
     "CeRDEF — Giurisprudenza Tributaria",
     "Guida ai tool CeRDEF: enti, criteri di ricerca, tipi provvedimento e norme fiscali principali"),
    ("legal://riferimenti/modelli-atti-catalogo", "modelli-atti-catalogo.md",
     "Catalogo Modelli Atti — 100 Tipi",
     "Indice di tutti i 100 tipi di atti legali generabili: routing, tool, resource e campi obbligatori per ciascun tipo"),
    ("legal://riferimenti/giustizia-amministrativa", "giustizia-amministrativa.md",
     "Giustizia Amministrativa — Guida Ricerca TAR/CdS",
     "Guida all'uso dei tool per la ricerca di sentenze TAR e Consiglio di Stato: sedi, tipi, workflow e normativa di riferimento"),
    ("legal://riferimenti/cgue-giurisprudenza", "cgue-giurisprudenza.md",
     "CGUE — Guida Giurisprudenza Europea",
     "Guida ai tool CGUE: corti, tipi documento, materie, formato CELEX/ECLI, workflow"),
]


def _make_reader(filename: str, description: str):
    def _read() -> str:
        return (_REFERENCES_DIR / filename).read_text(encoding="utf-8")

    _read.__name__ = filename[:-3].replace("-", "_")
    _read.__doc__ = description
    return _read


for _uri, _fname, _name, _desc in _STATIC_RESOURCES:
    mcp.resource(_uri, name=_name, description=_desc)(_make_reader(_fname, _desc))
```

(`Path` is already imported at the top of the module — verify; add `from pathlib import Path` if not.) The name/description strings above are verbatim from the current decorators — do not rephrase.

- [ ] **Step 3: Project (copies references into src/data), then write the failing test**

```bash
uv run --python 3.12 --extra dev python scripts/corpus/project_claude.py
ls plugin/server/src/data/references | wc -l   # expect 12
```

`tests/unit/test_resources_static.py`:
```python
"""Static resources are file-backed and byte-identical to the corpus."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

REPO = Path(__file__).parents[2]

def test_static_resources_serve_the_reference_files():
    from fastmcp import Client
    from src.server import mcp

    async def run():
        async with Client(mcp) as c:
            out = {}
            for uri in [u for u, *_ in _table()]:
                res = await c.read_resource(uri)
                out[uri] = res[0].text
            return out

    def _table():
        from src.resources import _STATIC_RESOURCES
        return _STATIC_RESOURCES

    served = asyncio.run(run())
    assert len(served) == 12
    for uri, fname, _n, _d in _table():
        expected = (REPO / "content" / "references" / fname).read_text(encoding="utf-8")
        assert served[uri] == expected, uri
```

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_resources_static.py tests/unit/test_resources_dynamic.py tests/unit/test_corpus_build.py -q`
Expected: all pass — including `test_resources_dynamic.py` UNTOUCHED (its imports must survive the rewrite).

- [ ] **Step 4: Commit**

```bash
git add scripts/corpus/extract_references.py content/references plugin/server/src/data/references plugin/server/src/resources.py tests/unit/test_resources_static.py
git commit -m "refactor(corpus): extract 12 static resources to content/references; resources.py loads them from src/data/references"
```

---

### Task 10: Server registration surface test

Closes a measured gap: no existing test covers registration (tools/prompts/resources counts).

**Files:**
- Test: `tests/unit/test_server_registration.py`

- [ ] **Step 1: Write the test**

```python
"""Frozen registration surface: 218 tools, 23 prompts, 15 resources.

Uses the in-process fastmcp Client (FastMCP 3.4.7 — get_tools() no longer exists).
Requires LEGAL_PROFILE unset/full (the default test environment).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

EXPECTED_RESOURCE_URIS = {
    "legal://riferimenti/procedura-civile", "legal://riferimenti/termini-processuali",
    "legal://riferimenti/contributo-unificato", "legal://riferimenti/irpef-detrazioni",
    "legal://riferimenti/interessi-legali", "legal://riferimenti/checklist-decreto-ingiuntivo",
    "legal://riferimenti/fonti-diritto-italiano", "legal://riferimenti/codici-e-leggi-principali",
    "legal://riferimenti/gdpr-checklist", "legal://riferimenti/consob-delibere",
    "legal://riferimenti/ricerca-giurisprudenziale", "legal://riferimenti/cerdef-giurisprudenza",
    "legal://riferimenti/modelli-atti-catalogo", "legal://riferimenti/giustizia-amministrativa",
    "legal://riferimenti/cgue-giurisprudenza",
}

def test_registration_surface():
    from fastmcp import Client
    from src.server import mcp
    from tests.unit.test_prompt_surface import EXPECTED as EXPECTED_PROMPTS

    async def run():
        async with Client(mcp) as c:
            return (
                await c.list_tools(), await c.list_prompts(), await c.list_resources()
            )

    tools, prompts, resources = asyncio.run(run())
    assert len(tools) == 218, f"tool count changed: {len(tools)}"
    assert {p.name for p in prompts} == set(EXPECTED_PROMPTS)
    assert {str(r.uri) for r in resources} == EXPECTED_RESOURCE_URIS
```

If `from tests.unit.test_prompt_surface import ...` fails (tests are not a package), inline the 23 prompt names as a set literal instead — copy them from the EXPECTED table in Task 8.

- [ ] **Step 2: Run it**

Run: `uv run --python 3.12 --extra dev pytest tests/unit/test_server_registration.py -q`
Expected: 1 passed. If tool count ≠ 218, STOP — a tool module failed to import; debug before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_server_registration.py
git commit -m "test: freeze server registration surface (218 tools / 23 prompts / 15 resources)"
```

---

### Task 11: Counts and documentation sweep

Skills went 23 → **30** (and two manifests wrongly said 22). Tools (218), prompts (23), resources (15), agents (6), commands (8) are UNCHANGED — touch only skill counts plus the structural docs.

**Files (exact sites, measured):**
- Modify: `.claude-plugin/marketplace.json:13` — `22 skill` → `30 skill`
- Modify: `plugin/.claude-plugin/plugin.json:4` — `22 skill` → `30 skill`
- Modify: `plugin/README.md:3` — `**23 skill**` → `**30 skill**`
- Modify: `README.md:32` — `**23 skill + 6 agenti**` → `**30 skill + 6 agenti**`
- Modify: `CLAUDE.md:553` — `23 skills + 8 comandi + 6 agenti` → `30 skills + 8 comandi + 6 agenti`
- Modify: `docs/README.md:121` — `23 skill` → `30 skill`
- Modify: `docs/plugin.md:3` (`23 skills` → `30 skills`), `:22` (`**23 skills**` → `**30 skills**`), `:35` (the quoted plugin.json description excerpt: `23 skill` → `30 skill`, keeping the excerpt in sync with the new plugin.json wording), `:75` (`### Tabella delle 23 skills` → `delle 30 skills` + append the 7 rows below), `:256` (`23 skills` → `30 skills`)
- Modify: `CLAUDE.md` — «Struttura» tree: add `content/` (skills/agents/commands/references + tool-vocabulary.json) and `scripts/corpus/`; mark `plugin/skills|agents|commands`, `src/prompts.py`, `src/data/references/` as GENERATED; update the `prompts.py` line comment from `# 23 workflow guidati (@mcp.prompt)` to `# GENERATED — 23 prompt dal corpus (scripts/corpus/generate_prompts.py)`
- Modify: `docs/architecture.md:246` — retitle `### src/prompts.py — 23 prompt guidati` to note it is generated from the corpus
- Modify: `docs/prompts-resources.md:3` — add: `> Dal 2026-08 i prompt sono GENERATI dai blocchi `prompt:` delle skill (scripts/corpus/generate_prompts.py) e 12 delle 15 risorse sono file in content/references/.`
- Modify: `CONTRIBUTING.md` — add a «Generated files» section (text below)
- Modify: `CHANGELOG.md` and `plugin/CHANGELOG.md` — add an `[Unreleased]` entry (text below)

**7 rows for the docs/plugin.md skill table** (match the existing table's format):
```
| `analisi-tributaria` | Giurisprudenza tributaria: ricerca CeRDEF, lettura provvedimenti, sintesi orientamenti |
| `analisi-giurisprudenza-amministrativa` | Giurisprudenza TAR/CdS: ricerca, lettura provvedimenti, sintesi orientamenti |
| `analisi-giurisprudenza-europea` | Giurisprudenza CGUE: ricerca, lettura sentenze chiave, sintesi orientamenti |
| `analisi-costituzionale` | Pronunce della Corte Costituzionale: ricerca, lettura, parametri invocati |
| `ricerca-gazzetta` | Atti in Gazzetta Ufficiale: novità per serie, ricerca, testo e PDF ufficiale |
| `orientamento-giurisprudenziale` | Orientamenti di legittimità: conformi vs contrasti, Sezioni Unite, evoluzione |
| `attuazione-direttiva` | Recepimento direttive UE: misure nazionali, testo vigente, giurisprudenza CGUE |
```

**CONTRIBUTING.md section:**
```markdown
## Generated files — edit the corpus, not the projections

`content/` is the single source of truth for skills, agents, commands and
static references. These paths are GENERATED from it and committed:

- `plugin/skills/`, `plugin/agents/`, `plugin/commands/` — run `python scripts/corpus/project_claude.py`
- `src/prompts.py` — run `python scripts/corpus/generate_prompts.py`
- `src/data/references/` — copied by the projector

Never edit those paths by hand: `tests/unit/test_corpus_build.py` fails the
suite when a committed projection drifts from the corpus. After ANY edit under
`content/`, run both scripts and commit source + projections together.
```

**CHANGELOG `[Unreleased]` entry (both files, adapt heading style to each):**
```markdown
### Changed
- Corpus consolidation (v3 phase 1): skills/agents/commands moved to `content/`
  as the single source; `plugin/` subtrees and `src/prompts.py` are now
  generated projections (`scripts/corpus/`). 7 prompt-only workflows promoted
  to skills (23 → 30). 12 of 15 static resources extracted to
  `content/references/`. MCP surface unchanged: 218 tools, 23 prompts,
  15 resources.
```

- [ ] **Step 1: Apply all edits above.** Line numbers may have drifted by a few lines — locate by the quoted text, not blindly by number.
- [ ] **Step 2: Verify no stale counts remain**

```bash
grep -rn "22 skill\|23 skill" README.md CLAUDE.md plugin/README.md docs/ .claude-plugin/ plugin/.claude-plugin/ | grep -v docs/specs/ ; true
```
Expected: no hits asserting 22 or 23 as the CURRENT skill count. `docs/specs/` is excluded (the spec and this plan quote the old strings by design); historical changelog entries are out of scope.

- [ ] **Step 3: Full suite + commit**

```bash
uv run --python 3.12 --extra dev pytest tests/unit -q
git add -A
git commit -m "docs: skill count 30, document the content/ corpus and generated projections"
```

---

### Task 12: Final verification (verifica-lavoro gate)

- [ ] **Step 1: Full non-live suite**

Run: `uv run --python 3.12 --extra dev pytest tests/ -m "not live" -q`
Expected: all pass, 0 failures. Paste the tail of the output in the completion report.

- [ ] **Step 2: Distribution smoke tests**

```bash
bash scripts/build-plugin.sh
unzip -l dist/legal-it-plugin-*.zip | grep -c "skills/.*/SKILL.md"   # expect 30
python3 plugin/build-web-skills.py                                   # expect "30 ZIP generati"
```
The repo is in a measured MIXED state: `.gitignore:25` ignores `plugin/dist/`, yet 23 legacy zips are tracked (`git ls-files plugin/dist/web-skills | wc -l` → 23). `git status` cannot answer here — the 7 NEW zips are untracked+ignored and invisible to it, and `git add plugin/dist` would silently skip them (a "30 zips" commit would contain 23). Align the repo with its declared .gitignore intent — untrack the legacy zips so the directory is pure build output:
```bash
git rm -r --cached plugin/dist
git commit -m "chore(build): stop tracking plugin/dist build artifacts (gitignored dir)"
```
Flag this in the final report: web-skills zips are no longer versioned — `plugin/build-web-skills.py` regenerates all 30 on demand and the release flow attaches them where needed. If the user objects, the reverse is `git add -f plugin/dist/web-skills/*.zip`.

- [ ] **Step 3: Registration snapshot**

```bash
uv run --python 3.12 --extra dev python - <<'EOF'
import asyncio, sys; sys.path.insert(0, ".")
from fastmcp import Client
from src.server import mcp
async def run():
    async with Client(mcp) as c:
        t, p, r = await c.list_tools(), await c.list_prompts(), await c.list_resources()
        print(f"tools={len(t)} prompts={len(p)} resources={len(r)}")
asyncio.run(run())
EOF
```
Expected: `tools=218 prompts=23 resources=15`

- [ ] **Step 4: History review**

Run: `git log --oneline develop..HEAD`
Expected: the spec commit + ~10 focused commits from this plan, no fixup noise (squash locally with `git rebase` ONLY if something is broken mid-history — otherwise leave as-is; the branch merges to develop with `--no-ff` per project Git Flow, after user approval).

- [ ] **Step 5: Report**

Report to the user (in Italian): counts before/after, the 4 normalized files, the drift-gate mechanism, what is deferred to Phase 2 (targets.yaml, build_targets.py absorbing sync/generator scripts, release.py integration, mcpb target) and Phase 3 (OpenAI bundle). Do NOT merge, do NOT run release.py — merging is the user's call.

---

## Deviations from the spec (measured, deliberate)

1. **"37 markdown files" is actually 34** (20 SKILL.md + 1 skill reference + 6 agents + 7 commands carry `legal-it:`; `release.md` and 3 skills don't). No scope change.
2. **3 of the 15 resources are dynamic** (rendered from `src/data/*.json`) and stay as code; 12 are extracted. The spec's "extract the 15" assumed all-static.
3. **`plugin/` is partially generated**: `plugin/server/`, `plugin/hooks/`, `plugin/settings.json`, `plugin/.mcp.json`, `plugin/start_server.sh`, `plugin/.claude-plugin/` remain hand-maintained (the server itself lives inside `plugin/server/` — full generation was never possible). Generated subtrees: `skills/`, `agents/`, `commands/`, plus `src/prompts.py` and `src/data/references/`.
4. **`release.py` is not modified** in Phase 1: the drift gate lives in pytest, which `release.py`'s existing `run_tests` gate already enforces. Builder integration happens in Phase 2.
5. **Shared-reference wiring into individual skills** (spec: "skills that need them reference them by path") is deferred: the extraction + loader land now; no current skill embeds a shared reference, and the Phase 2 manifest is the right place for the wiring key.
6. **Generated prompt bodies are the skill bodies** — thinner than the retired
   hand-written prompts for 13 of the 16 de-duplicated workflows (31%-63% of the
   old character count; e.g. `verifica_prescrizione` lost its FORMATO OUTPUT
   table and the Bonafede/Cartabia regime warning; only `analisi_sinistro`,
   `analisi_giurisprudenziale`, `parere_legale` are at parity). Names,
   signatures and descriptions are unchanged (frozen-surface test). Back-fill
   of the lost substantive material into the skill bodies is scheduled BEFORE
   the 3.0.0 release, with the user reviewing what to reintegrate.
7. **Resources runtime path**: `resources.py` reads the projected copies at
   `src/data/references/`, not `content/references/` directly — the projected
   copy is what keeps Docker/mcpb/marketplace distributions working unchanged.
