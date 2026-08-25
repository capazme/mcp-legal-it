"""Bundle content tests for the openai build target — the real content/
corpus projected through the real content/targets.yaml manifest, run into a
tmp dir so the committed tree is never touched.

These are the actual release gate for the openai bundle deliverable: unlike
tests/unit/test_corpus_projection.py (engine mechanics, fake fixtures), this
file asserts on the real 40-skill corpus.
"""
import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("build_targets")

_EXCLUDED_SKILL_NAMES = {"release", "digest", "cookie-audit", "esporta-documento"}


def _project_real_openai(tmp_path):
    cfg = bt.tg.get_target(REPO, "openai")
    bt.pc.project(REPO, tmp_path, cfg)
    return tmp_path / cfg["out"]["skills"]


# ---------------------------------------------------------------------------
# Skill count + exclusions
# ---------------------------------------------------------------------------

def test_openai_projection_has_40_skills(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    dirs = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
    assert len(dirs) == 40, dirs


def test_excluded_names_absent(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    dirs = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    present_excluded = dirs & _EXCLUDED_SKILL_NAMES
    assert present_excluded == set(), present_excluded


# ---------------------------------------------------------------------------
# Frontmatter shape: name + description only, description capped
# ---------------------------------------------------------------------------

def _frontmatter_keys(fm_lines: list[str]) -> list[str]:
    return [
        line.split(":", 1)[0]
        for line in fm_lines
        if line and not line.startswith((" ", "\t"))
    ]


def test_frontmatter_is_name_and_description_only_with_capped_description(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    cfg = bt.tg.get_target(REPO, "openai")
    max_chars = cfg["description_max_chars"]
    skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    assert skill_dirs, "no skills projected"

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file(), skill_dir.name
        fm_lines, _ = bt.fm.split(skill_md.read_text(encoding="utf-8"))
        keys = _frontmatter_keys(fm_lines)
        assert keys == ["name", "description"], (skill_dir.name, keys)

        desc = bt.fm.read_field(fm_lines, "description")
        assert desc, skill_dir.name
        # +3 slack: the dangling-connector trim (project_claude._cap_description)
        # can re-append "..." after trimming, never pushing past max_chars + 3.
        assert len(desc) <= max_chars + 3, (skill_dir.name, len(desc), desc)


# ---------------------------------------------------------------------------
# Agent-derived skills use standalone-description, not description
# ---------------------------------------------------------------------------

def test_agent_skills_use_standalone_description(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    cfg = bt.tg.get_target(REPO, "openai")
    max_chars = cfg["description_max_chars"]

    agents_dir = REPO / "content" / "agents"
    agent_files = sorted(agents_dir.glob("*.md"))
    assert agent_files, "no source agents found — fixture drifted from content/agents"

    for agent_md in agent_files:
        fm_lines, _ = bt.fm.split(agent_md.read_text(encoding="utf-8"))
        name = bt.fm.read_field(fm_lines, "name")
        standalone = bt.fm.read_field(fm_lines, "standalone-description")
        assert standalone is not None, agent_md.name  # every agent must declare one

        expected = bt.pc._cap_description(standalone, max_chars)

        skill_md = skills_dir / name / "SKILL.md"
        assert skill_md.is_file(), name
        skill_fm_lines, _ = bt.fm.split(skill_md.read_text(encoding="utf-8"))
        actual = bt.fm.read_field(skill_fm_lines, "description")
        assert actual == expected, (name, actual, expected)


# ---------------------------------------------------------------------------
# No leaked Claude-only namespace, MCP-prefixed tool names, Claude-only
# runtime env vars, or backticked slash-commands anywhere
# ---------------------------------------------------------------------------

# Backticked slash-command reference, e.g. `/parere` — Codex has no
# slash-command concept, so a body referencing one is a dead pointer outside
# Claude Code (this is exactly the class of bug F3 fixed at the source).
_SLASH_COMMAND_RE = re.compile(r"`/[a-z][a-z-]*`")


def test_no_leaked_claude_namespace_or_mcp_prefix(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    offenders = []
    for f in skills_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if (
            "legal-it:" in text
            or "mcp__" in text
            # Claude Code-only runtime env vars: meaningless (and unresolved)
            # outside a Claude plugin process — see esporta-documento's old
            # ${CLAUDE_PLUGIN_ROOT} paths, which is why it is excluded (F1).
            or "CLAUDE_PLUGIN_ROOT" in text
            or "CLAUDE_PROJECT_DIR" in text
            or _SLASH_COMMAND_RE.search(text)
        ):
            offenders.append(str(f.relative_to(skills_dir)))
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# AGENTS.md — generated from the real server.py instructions string
# ---------------------------------------------------------------------------

def test_agents_md_contains_regole_cite_law_and_bare_tool_namespace():
    text = bt.am.generate(REPO)
    assert "REGOLE" in text
    assert "cite_law" in text
    assert "legal_it__" in text
    assert len(text.encode("utf-8")) < 32 * 1024


# ---------------------------------------------------------------------------
# config.toml.example — stdio server key
# ---------------------------------------------------------------------------

def test_config_example_declares_underscore_server_key():
    assert "[mcp_servers.legal_it]" in bt._OPENAI_CONFIG_TOML_EXAMPLE


# ---------------------------------------------------------------------------
# Skills-list budget: names + capped descriptions must fit Codex's context
# reservation, not just each individual description.
#
# Measured fact (docs/specs/2026-08-25-openai-target-plan.md): Codex reserves
# 2% of context for the skills list, or 8,000 chars when context size is
# unknown; past that budget descriptions are shortened further or skills are
# silently OMITTED. description_max_chars caps each description individually
# but says nothing about the bundle total — this gate is the one that
# actually backs the "no silent truncation/omission" requirement.
# ---------------------------------------------------------------------------

def test_bundle_name_and_description_budget_under_8000_chars(tmp_path):
    skills_dir = _project_real_openai(tmp_path)
    skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    assert skill_dirs, "no skills projected"

    total = 0
    for skill_dir in skill_dirs:
        fm_lines, _ = bt.fm.split((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
        name = bt.fm.read_field(fm_lines, "name")
        desc = bt.fm.read_field(fm_lines, "description")
        total += len(name) + len(desc)

    assert total < 8000, total


# ---------------------------------------------------------------------------
# Determinism (backs Deviation 3 in docs/specs/2026-08-25-openai-target-plan.md
# — no committed projection for openai, so determinism is test-asserted).
# ---------------------------------------------------------------------------

def test_projection_is_deterministic(tmp_path):
    cfg = bt.tg.get_target(REPO, "openai")
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    bt.pc.project(REPO, out_a, cfg)
    bt.pc.project(REPO, out_b, cfg)
    skills_a, skills_b = out_a / cfg["out"]["skills"], out_b / cfg["out"]["skills"]

    rel_a = {p.relative_to(skills_a) for p in skills_a.rglob("*") if p.is_file()}
    rel_b = {p.relative_to(skills_b) for p in skills_b.rglob("*") if p.is_file()}
    assert rel_a == rel_b, (rel_a - rel_b, rel_b - rel_a)
    for rel in rel_a:
        assert (skills_a / rel).read_bytes() == (skills_b / rel).read_bytes(), rel
