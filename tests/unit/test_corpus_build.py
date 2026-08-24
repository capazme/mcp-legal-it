"""Drift gate: the committed generated artifacts must match a fresh projection."""
import filecmp
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]

def _assert_trees_equal(a: Path, b: Path) -> None:
    # OS metadata (Finder's .DS_Store) is outside the projection contract:
    # it lives untracked in browsed checkouts and must not fail the gate.
    cmp = filecmp.dircmp(a, b, ignore=filecmp.DEFAULT_IGNORES + [".DS_Store"])
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

def test_generated_prompts_match_committed(tmp_path):
    out = tmp_path / "prompts.py"
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/corpus/generate_prompts.py"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    committed = (REPO / "plugin/server/src/prompts.py").read_bytes()
    assert out.read_bytes() == committed, "src/prompts.py drifted from the corpus — rerun generate_prompts.py"
