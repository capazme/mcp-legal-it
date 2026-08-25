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


def test_claude_web_out_dir_matches_release_py_consumer():
    # release.py stages this EXACT path with `git add -f` at release time
    # (three dist_dir sites). Changing out_dir here without updating release.py
    # silently ships stale web-skills zips into release commits.
    assert tg.get_target(REPO, "claude-web")["out_dir"] == "plugin/dist/web-skills"


# ---------------------------------------------------------------------------
# supports: + out-subkey validation (Phase 3 Task 2)
# ---------------------------------------------------------------------------

def _write(tmp_path, text):
    (tmp_path / "content").mkdir(exist_ok=True)
    (tmp_path / "content" / "targets.yaml").write_text(text, encoding="utf-8")


def test_supports_missing_fs_kind_out_key_raises_naming_the_kind(tmp_path):
    _write(
        tmp_path,
        "version: 1\n"
        "projections:\n"
        "  broken:\n"
        '    tool_namespace: "{tool}"\n'
        "    strip_frontmatter_keys: []\n"
        "    supports: [skills, agents]\n"
        "    out:\n"
        "      skills: out/skills\n",  # 'agents' out key missing
    )
    with pytest.raises(ValueError, match="agents"):
        tg.load_targets(tmp_path)


def test_supports_mcp_resources_requires_references_out_key(tmp_path):
    _write(
        tmp_path,
        "version: 1\n"
        "projections:\n"
        "  broken:\n"
        '    tool_namespace: "{tool}"\n'
        "    strip_frontmatter_keys: []\n"
        "    supports: [skills, mcp_resources]\n"
        "    out:\n"
        "      skills: out/skills\n",  # 'references' out key missing
    )
    with pytest.raises(ValueError, match="references"):
        tg.load_targets(tmp_path)


def test_supports_mcp_prompts_and_hooks_demand_no_out_key(tmp_path):
    _write(
        tmp_path,
        "version: 1\n"
        "projections:\n"
        "  minimal:\n"
        '    tool_namespace: "{tool}"\n'
        "    strip_frontmatter_keys: []\n"
        "    supports: [mcp_prompts, hooks]\n"
        "    out: {}\n",
    )
    data = tg.load_targets(tmp_path)  # must NOT raise
    assert data["projections"]["minimal"]["supports"] == ["mcp_prompts", "hooks"]


def test_supports_absent_is_backward_compatible(tmp_path):
    _write(
        tmp_path,
        "version: 1\n"
        "projections:\n"
        "  legacy:\n"
        '    tool_namespace: "{tool}"\n'
        "    strip_frontmatter_keys: []\n"
        "    out:\n"
        "      skills: out/skills\n",  # no agents/commands/references, no supports key at all
    )
    data = tg.load_targets(tmp_path)  # must NOT raise — absent supports = full claude behavior
    assert "supports" not in data["projections"]["legacy"]


def test_real_manifest_supports_out_keys_are_consistent():
    # claude-code's own supports/out must satisfy the same validation it enforces.
    tg.load_targets(REPO)  # must NOT raise


# ---------------------------------------------------------------------------
# openai projection and openai-zip packaging (Phase 3 Task 3)
# ---------------------------------------------------------------------------

def test_openai_projection_out_dir_is_under_dist():
    # dist/openai is gitignored (see .gitignore). openai projection stages skills there.
    openai = tg.get_target(REPO, "openai")
    assert openai["out"]["skills"] == "dist/openai/.agents/skills"


def test_openai_projection_exclude_list():
    # openai projection explicitly excludes these three items from projection.
    openai = tg.get_target(REPO, "openai")
    assert openai["exclude"] == ["commands/release", "commands/digest", "skills/cookie-audit"]


def test_openai_zip_artifact_matches_release_glob():
    # release.py packs all dist/*.zip files into a release artifact.
    # artifact name must match that glob pattern.
    openai_zip = tg.get_target(REPO, "openai-zip")
    artifact = openai_zip["artifact"]
    # Verify it matches the dist/*.zip pattern (will be dist/legal-it-openai-skills-{version}.zip)
    assert artifact.startswith("dist/")
    assert artifact.endswith(".zip")
