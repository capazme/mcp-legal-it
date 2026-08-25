import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("build_targets")


# ---------------------------------------------------------------------------
# fake-root fixtures
# ---------------------------------------------------------------------------

_CLAUDE_CODE_PROJECTION = (
    "projections:\n"
    "  claude-code:\n"
    '    tool_namespace: "legal-it:{tool}"\n'
    '    command_tool_namespace: "mcp__legal-it__{tool}"\n'
    "    strip_frontmatter_keys: [tools, prompt]\n"
    "    out:\n"
    "      skills: plugin/skills\n"
    "      agents: plugin/agents\n"
    "      commands: plugin/commands\n"
    "      references: plugin/server/src/data/references\n"
)


def _write_targets_yaml(root: Path, packaging_block: str) -> None:
    (root / "content").mkdir(parents=True, exist_ok=True)
    text = "version: 1\n" + _CLAUDE_CODE_PROJECTION + packaging_block
    (root / "content" / "targets.yaml").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — claude-web emission rules
# ---------------------------------------------------------------------------

def test_web_zip_conversion_rules(tmp_path):
    _write_targets_yaml(
        tmp_path,
        "packaging:\n"
        "  claude-web:\n"
        "    from: claude-code\n"
        "    out_dir: plugin/dist/web-skills\n"
        "    description_max_chars: 200\n"
        "    keep_frontmatter: [name, description]\n"
        '    zip_member: "{name}/Skill.md"\n',
    )

    long_description = " ".join(f"parola{i}" for i in range(1, 40))
    assert len(long_description) > 200  # sanity: the fixture must exercise truncation

    skill_dir = tmp_path / "plugin" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        f"description: {long_description}\n"
        "argument-hint: <foo>\n"
        "---\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    count = bt.build_claude_web(tmp_path, out_dir=out_dir)
    assert count == 1

    zip_path = out_dir / "test-skill.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert names == ["test-skill/Skill.md"], names
        content = zf.read("test-skill/Skill.md").decode("utf-8")

    assert "argument-hint" not in content
    assert "description: >\n" in content

    lines = content.splitlines()
    desc_idx = lines.index("description: >")
    desc_line = lines[desc_idx + 1]
    assert desc_line.startswith("  ")
    desc_value = desc_line.strip()

    assert desc_value.endswith("...")
    assert len(desc_value) <= 200
    # cut on a word boundary: the text before "..." must be a clean prefix of
    # the normalized original (i.e. no word was cut mid-way)
    normalized_original = " ".join(long_description.split())
    prefix = desc_value[:-3]
    assert normalized_original.startswith(prefix)
    next_char = normalized_original[len(prefix)]
    assert next_char == " "


# ---------------------------------------------------------------------------
# Test 2 — plugin-zip staging, purge, version rewrite, source untouched
# ---------------------------------------------------------------------------

def _write_fake_plugin_tree(root: Path) -> None:
    plugin = root / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "legal-it-test", "version": "1.0.0"}, indent=2), encoding="utf-8"
    )
    (plugin / "skills").mkdir()
    (plugin / "skills" / "marker.txt").write_text("skills-marker\n", encoding="utf-8")
    (plugin / "agents").mkdir()
    (plugin / "agents" / "marker.txt").write_text("agents-marker\n", encoding="utf-8")
    (plugin / "commands").mkdir()
    (plugin / "commands" / "marker.txt").write_text("commands-marker\n", encoding="utf-8")
    (plugin / "hooks").mkdir()
    (plugin / "hooks" / "marker.txt").write_text("hooks-marker\n", encoding="utf-8")
    (plugin / "settings.json").write_text("{}\n", encoding="utf-8")
    (plugin / "start_server.sh").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    (plugin / "start_server.sh").chmod(0o755)
    (plugin / ".mcp.json").write_text("{}\n", encoding="utf-8")
    server = plugin / "server"
    server.mkdir()
    (server / "__init__.py").write_text("# server\n", encoding="utf-8")
    pycache = server / "__pycache__"
    pycache.mkdir()
    (pycache / "foo.cpython-312.pyc").write_bytes(b"\x00\x01")
    (server / "stray.pyc").write_bytes(b"\x00\x01")


def test_plugin_zip_stages_and_excludes(tmp_path):
    _write_targets_yaml(
        tmp_path,
        "packaging:\n"
        "  plugin-zip:\n"
        "    from: claude-code\n"
        '    artifact: "dist/legal-it-plugin-{version}.zip"\n'
        "    include: [.claude-plugin, skills, agents, commands, hooks, settings.json, start_server.sh, .mcp.json, server]\n"
        "    root: plugin\n"
        '    version_manifest: ".claude-plugin/plugin.json"\n',
    )
    _write_fake_plugin_tree(tmp_path)

    output = bt.build_plugin_zip(tmp_path, version="9.9.9")
    assert output == tmp_path / "dist" / "legal-it-plugin-9.9.9.zip"
    assert output.exists()

    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
        for expected in (
            ".claude-plugin/plugin.json",
            "skills/marker.txt",
            "agents/marker.txt",
            "commands/marker.txt",
            "hooks/marker.txt",
            "settings.json",
            "start_server.sh",
            ".mcp.json",
            "server/__init__.py",
        ):
            assert expected in names, f"{expected} missing from {names}"

        assert not any(n.endswith(".pyc") for n in names), names
        assert not any("__pycache__" in n for n in names), names

        staged_manifest = json.loads(zf.read(".claude-plugin/plugin.json"))
        assert staged_manifest["version"] == "9.9.9"

    source_manifest = json.loads(
        (tmp_path / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert source_manifest["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Test 3 — mcpb fallback zip when the `mcpb` CLI is unavailable
# ---------------------------------------------------------------------------

def _write_fake_dxt_tree(root: Path) -> None:
    dxt = root / "dxt"
    dxt.mkdir(parents=True)
    (dxt / "manifest.json").write_text(
        json.dumps({"name": "legal-it-test", "version": "1.0.0"}, indent=2), encoding="utf-8"
    )
    (dxt / ".mcpbignore").write_text(".venv/\n__pycache__/\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname = \"legal-it-test\"\n", encoding="utf-8")
    plugin = root / "plugin"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "start_server.sh").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    (plugin / "start_server.sh").chmod(0o755)
    server = plugin / "server"
    server.mkdir()
    (server / "__init__.py").write_text("# server\n", encoding="utf-8")
    pycache = server / "__pycache__"
    pycache.mkdir()
    (pycache / "foo.cpython-312.pyc").write_bytes(b"\x00\x01")


def test_mcpb_fallback_zip(tmp_path, monkeypatch):
    _write_targets_yaml(
        tmp_path,
        "packaging:\n"
        "  mcpb:\n"
        "    from: claude-code\n"
        '    artifact: "dist/legal-it-{version}.mcpb"\n'
        '    version_manifest: "manifest.json"\n',
    )
    _write_fake_dxt_tree(tmp_path)

    monkeypatch.setattr(shutil, "which", lambda _name: None)

    output = bt.build_mcpb(tmp_path, version="1.2.3")
    assert output == tmp_path / "dist" / "legal-it-1.2.3.mcpb"
    assert output.exists()

    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
        for expected in ("manifest.json", ".mcpbignore", "pyproject.toml", "start_server.sh", "server/__init__.py"):
            assert expected in names, f"{expected} missing from {names}"
        assert not any(n.endswith(".pyc") for n in names), names
        assert not any("__pycache__" in n for n in names), names

        staged_manifest = json.loads(zf.read("manifest.json"))
        assert staged_manifest["version"] == "1.2.3"

    source_manifest = json.loads((tmp_path / "dxt" / "manifest.json").read_text(encoding="utf-8"))
    assert source_manifest["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Test 4 — CLI rejects unknown targets
# ---------------------------------------------------------------------------

def test_cli_rejects_unknown_target():
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_targets.py"), "nonsense"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "nonsense" in r.stderr or "invalid choice" in r.stderr
