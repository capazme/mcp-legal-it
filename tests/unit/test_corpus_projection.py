import importlib.util
import shutil
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

TARGETS_YAML = (
    "version: 1\n"
    "projections:\n"
    "  claude-code:\n"
    '    tool_namespace: "legal-it:{tool}"\n'
    '    command_tool_namespace: "mcp__legal-it__{tool}"\n'
    "    strip_frontmatter_keys: [tools, prompt]\n"
    "    supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]\n"
    "    out:\n"
    "      skills: plugin/skills\n"
    "      agents: plugin/agents\n"
    "      commands: plugin/commands\n"
    "      references: plugin/server/src/data/references\n"
)

# Same shape, but WITHOUT command_tool_namespace — exercises the lazy read.
TARGETS_YAML_NO_COMMAND_NS = (
    "version: 1\n"
    "projections:\n"
    "  claude-code:\n"
    '    tool_namespace: "legal-it:{tool}"\n'
    "    strip_frontmatter_keys: [tools, prompt]\n"
    "    supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]\n"
    "    out:\n"
    "      skills: plugin/skills\n"
    "      agents: plugin/agents\n"
    "      commands: plugin/commands\n"
    "      references: plugin/server/src/data/references\n"
)

def _make_content(root: Path):
    (root / "content/skills/demo/references").mkdir(parents=True)
    (root / "content/tool-vocabulary.json").write_text(
        '["cerca_brocardi", "cite_law", "leggi_sentenza"]', encoding="utf-8"
    )
    (root / "content/targets.yaml").write_text(TARGETS_YAML, encoding="utf-8")
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


def test_tool_namespace_placeholder_conversion(tmp_path):
    """The manifest spells the placeholder as NAMED {tool}; toolnames.add_prefixes
    formats POSITIONALLY. project() must convert once when reading cfg, or every
    projected doc raises KeyError on the first str.format() call."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    out = tmp_path / "out"
    pc.project(src_root, out)
    skill = (out / "plugin/skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "`legal-it:cite_law`" in skill


def test_missing_command_tool_namespace_with_command_tools_raises(tmp_path):
    """Without command_tool_namespace, a command declaring vocab tools must
    fail loudly instead of silently emitting an un-namespaced allowed-tools
    line."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    (src_root / "content/targets.yaml").write_text(TARGETS_YAML_NO_COMMAND_NS, encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit, match="command_tool_namespace"):
        pc.project(src_root, tmp_path / "out")


def test_missing_command_tool_namespace_without_commands_succeeds(tmp_path):
    """The same manifest gap is harmless when the corpus has no commands at
    all — command_tool_namespace is never read/formatted."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    (src_root / "content/targets.yaml").write_text(TARGETS_YAML_NO_COMMAND_NS, encoding="utf-8")
    shutil.rmtree(src_root / "content/commands")
    pc.project(src_root, tmp_path / "out")
