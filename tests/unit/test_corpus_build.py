"""Drift gate: the committed generated artifacts must match a fresh projection."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]

# OS metadata (Finder's .DS_Store) is outside the projection contract: it
# lives untracked in browsed checkouts and must not fail the gate.
_IGNORE_NAMES = {".DS_Store"}

def _relative_files(root: Path) -> set[Path]:
    return {
        p.relative_to(root)
        for p in root.rglob("*")
        if p.is_file() and p.name not in _IGNORE_NAMES
    }

def _assert_trees_equal(a: Path, b: Path) -> None:
    a_files = _relative_files(a)
    b_files = _relative_files(b)
    only_in_committed = sorted(a_files - b_files)
    only_in_fresh = sorted(b_files - a_files)
    assert not only_in_committed and not only_in_fresh, (
        f"{a} vs {b}: only_in_committed={only_in_committed} only_in_fresh={only_in_fresh}"
    )
    for rel in sorted(a_files):
        a_bytes = (a / rel).read_bytes()
        b_bytes = (b / rel).read_bytes()
        assert a_bytes == b_bytes, f"{a} vs {b}: content differs in {rel}"

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
