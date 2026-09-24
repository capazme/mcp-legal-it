"""Variant provisioning: pinned worktrees for the plugin arms.

The happy paths talk to a REAL git repository (sandboxed in tmp_path with
two commits and one branch) because the whole point of `variants.py` is to
drive `git worktree` correctly; unit-testing it against mocks would only
test the mocks. The ref table itself is patched to point at the sandbox's
refs — nothing here touches the operator's real worktrees: every path the
module creates lives under tmp_path.
"""

import json
import subprocess

import pytest

from benchmarks.legalita.run import variants as variants_mod
from benchmarks.legalita.run.variants import (
    VARIANT_ARMS,
    VariantError,
    ensure_worktrees,
)
from benchmarks.legalita.schema import VARIANT_ARMS as SCHEMA_VARIANT_ARMS


def _git(repo, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


@pytest.fixture()
def sandbox_repo(tmp_path):
    """A real git repo with a branch (pin target) and a second commit."""
    repo = tmp_path / "repo"
    (repo / "plugin").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "bench@example.com")
    _git(repo, "config", "user.name", "bench")
    (repo / "plugin" / "skills.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    _git(repo, "branch", "release/sandbox")
    (repo / "plugin" / "skills.txt").write_text("v1\nv2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v2")
    branch_sha = _git(repo, "rev-list", "-n", "1", "release/sandbox")
    head_sha = _git(repo, "rev-list", "-n", "1", "HEAD")
    return {
        "repo": repo,
        "base": tmp_path / "variants",
        "branch_sha": branch_sha,
        "head_sha": head_sha,
    }


@pytest.fixture()
def patched_refs(monkeypatch, sandbox_repo):
    """Point the pin table at the sandbox refs: plugin-v2 -> the branch,
    plugin-v3 -> the tip commit (by SHA, as an annotated-ref stand-in)."""
    monkeypatch.setattr(
        variants_mod,
        "VARIANT_REFS",
        {
            "plugin-v2": "release/sandbox",
            "plugin-v3": sandbox_repo["head_sha"],
        },
    )


def test_pin_table_covers_exactly_the_schema_variant_arms():
    # A variant arm declared in the schema but missing from the pin table
    # would crash cmd_run at provisioning time; one pinned but not declared
    # would silently provision nothing runnable.
    assert set(variants_mod.VARIANT_REFS) == set(SCHEMA_VARIANT_ARMS)
    assert set(VARIANT_ARMS) == set(SCHEMA_VARIANT_ARMS)


def test_ensure_worktrees_materialises_both_variants(patched_refs, sandbox_repo):
    states = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert set(states) == set(VARIANT_ARMS)
    v2 = states["plugin-v2"]
    assert v2.sha == sandbox_repo["branch_sha"]
    assert (v2.worktree / "plugin" / "skills.txt").read_text(encoding="utf-8").startswith("v1")
    # plugin-v3 pins the tip: it sees the second commit's content.
    assert "v2" in (states["plugin-v3"].worktree / "plugin" / "skills.txt").read_text(encoding="utf-8")
    manifest = json.loads((sandbox_repo["base"] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["plugin-v2"]["sha"] == sandbox_repo["branch_sha"]


def test_ensure_worktrees_is_idempotent(patched_refs, sandbox_repo):
    first = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    second = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert first["plugin-v2"].sha == second["plugin-v2"].sha
    assert (second["plugin-v2"].worktree / "plugin" / "skills.txt").exists()


def test_ensure_worktrees_moves_a_stale_worktree_to_the_new_pin(
    patched_refs, sandbox_repo
):
    # Pin the branch at its first commit, provision, then advance the pin
    # (simulate the branch moving forward) and re-provision: the worktree
    # must MOVE, loudly, to the new SHA.
    monkey_refs = variants_mod.VARIANT_REFS
    states = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert states["plugin-v2"].sha == sandbox_repo["branch_sha"]

    _git(sandbox_repo["repo"], "branch", "release/sandbox2")
    # Advance the sandbox branch: a third commit on top of release/sandbox.
    worktree = states["plugin-v2"].worktree
    (worktree / "plugin" / "skills.txt").write_text("v1\nv2\nv3\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "v3", "--no-verify")
    _git(sandbox_repo["repo"], "update-ref", "refs/heads/release/sandbox", _git(worktree, "rev-parse", "HEAD"))
    # Back in the module, the pin table object must be unchanged by the
    # provisioning above; re-resolving now yields the new branch tip.
    assert variants_mod.VARIANT_REFS is monkey_refs

    states2 = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    new_sha = _git(sandbox_repo["repo"], "rev-list", "-n", "1", "release/sandbox")
    assert states2["plugin-v2"].sha == new_sha
    assert "v3" in (states2["plugin-v2"].worktree / "plugin" / "skills.txt").read_text(encoding="utf-8")


def test_ensure_worktrees_repairs_a_prunable_registration(patched_refs, sandbox_repo):
    states = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    worktree = states["plugin-v2"].worktree
    # Simulate an externally deleted checkout: git still registers the
    # worktree, the directory is gone.
    import shutil

    shutil.rmtree(worktree)
    repaired = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert (repaired["plugin-v2"].worktree / "plugin" / "skills.txt").exists()


def test_ensure_worktrees_refuses_a_foreign_directory(patched_refs, sandbox_repo):
    foreign = sandbox_repo["base"] / "plugin-v2"
    foreign.mkdir(parents=True)
    (foreign / "someone-elses-data.txt").write_text("do not delete\n", encoding="utf-8")
    with pytest.raises(VariantError, match="not this benchmark"):
        ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    # The foreign content must still be there: refusal, never deletion.
    assert (foreign / "someone-elses-data.txt").exists()


def test_ensure_worktrees_adopts_a_matching_manual_worktree(patched_refs, sandbox_repo):
    manual = sandbox_repo["base"] / "plugin-v2"
    manual.mkdir(parents=True)
    _git(sandbox_repo["repo"], "worktree", "add", "--detach", str(manual), sandbox_repo["branch_sha"])
    states = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert states["plugin-v2"].worktree == manual
    assert states["plugin-v2"].sha == sandbox_repo["branch_sha"]


def test_ensure_worktrees_removes_an_empty_leftover_directory(patched_refs, sandbox_repo):
    leftover = sandbox_repo["base"] / "plugin-v2"
    leftover.mkdir(parents=True)
    states = ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
    assert (states["plugin-v2"].worktree / "plugin").exists()


def test_unknown_ref_fails_loudly(patched_refs, sandbox_repo, monkeypatch):
    monkeypatch.setattr(
        variants_mod, "VARIANT_REFS", {"plugin-v2": "release/sandbox", "plugin-v3": "no/such/ref"}
    )
    with pytest.raises(VariantError, match="no/such/ref"):
        ensure_worktrees(sandbox_repo["repo"], base=sandbox_repo["base"])
