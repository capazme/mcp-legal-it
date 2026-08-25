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
