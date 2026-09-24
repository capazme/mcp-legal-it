"""Variant provisioning for the plugin arms.

Each plugin arm (`plugin-v2`, `plugin-v3`) loads one pinned version of the
whole legal-it deliverable via `claude -p --plugin-dir`: the MCP server,
skills, agents, commands and hooks travel together, exactly as a real user
receives them from the marketplace. The pin lives in `VARIANT_REFS` below;
`ensure_worktrees()` materialises one detached git worktree per arm under
`benchmarks/legalita/variants/<arm>/` and returns the resolved state —
including the exact commit SHA each arm was pinned to at THIS
provisioning, which `cmd_run` stamps on every run record
(`RunRecord.variant_sha`).

Design notes:

- Refs, not SHAs, in the pin table: the table stays readable and a future
  `plugin-v4` (or a re-pin of `plugin-v3` to a newer beta) is a one-line
  change. Reproducibility does not depend on the table — it depends on the
  SHA recorded per run, which is why every run carries its own.
- Worktrees, not clones or archives: `git worktree add --detach` is cheap
  (no object re-download), fully checked out (skills/ and server/ are real
  files — the v2 line commits plugin/skills in-tree, the v3 line commits
  plugin/agents and plugin/commands in-tree), and isolated (an independent
  checkout can never be disturbed by a branch switch in the operator's
  main working tree).
- Dedup keyed on the resolved SHA: a re-invocation of `variants` after the
  pin moved forward MOVES the worktree to the new SHA — deliberately loud,
  because runs already recorded against the older SHA stay valid (each
  carries its own variant_sha) while any newly executed run would
  otherwise silently mix two versions inside one arm's label. `cmd_run`
  re-provisions (never silently reuses a stale checkout) before executing
  variant arms for exactly this reason.
- `--force`: re-check-out even when the worktree already sits at the pin —
  for recovering a checkout someone corrupted by hand. A worktree whose
  registration git considers prunable is repaired with or without the
  flag. A foreign directory at the arm's path (not ours, not empty) is
  refused, never deleted: this tool only ever touches its own artifacts.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from benchmarks.legalita.schema import VARIANT_ARMS

# The pin table. arm -> ref (branch, tag or any committish). Update here to
# re-pin an arm; every executed run records the SHA it actually ran against.
#
# Pin RELEASED TAGS, never the release/* branch a tag was cut from: those
# branches get deleted once the release ships (release/2.14.0 did, and left
# this stage unresolvable), while the tag is what the marketplace actually
# served. A tag that is later rewritten on purpose (v3.0.0-beta.1 lost the
# tracked CLAUDE.md) must be re-resolved here and the worktrees refreshed:
# the pin table is a moving pointer, and only RunRecord.variant_sha is the
# durable statement of what a run executed against.
VARIANT_REFS: dict[str, str] = {
    "plugin-v2": "v2.14.0",
    "plugin-v3": "v3.0.0-beta.3",
}


class VariantError(RuntimeError):
    """Raised when a variant worktree cannot be provisioned."""


@dataclass(frozen=True)
class VariantState:
    """One provisioned variant: the arm, its pin, and where to load it."""

    arm: str
    ref: str
    sha: str
    worktree: Path
    plugin_dir: Path

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "ref": self.ref,
            "sha": self.sha,
            "worktree": str(self.worktree),
            "plugin_dir": str(self.plugin_dir),
        }


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise VariantError(
            f"git {' '.join(args)} failed (rc={completed.returncode}): "
            f"{completed.stderr.strip()[:400]}"
        )
    return completed.stdout.strip()


def _resolve_sha(repo: Path, ref: str) -> str:
    # rev-list (not rev-parse) so a wrong ref fails loudly instead of
    # echoing the ref text back for an ambiguous or unknown name.
    sha = _git(repo, "rev-list", "-n", "1", ref)
    if not sha or not all(c in "0123456789abcdef" for c in sha):
        raise VariantError(f"cannot resolve variant ref {ref!r} to a commit (got {sha!r})")
    return sha


def _worktree_registry(repo: Path) -> tuple[set[str], set[str]]:
    """Absolute paths git registers as worktrees, and the subset it marks
    prunable (directory missing or unreadable on disk)."""
    out = _git(repo, "worktree", "list", "--porcelain")
    registered: set[str] = set()
    prunable: set[str] = set()
    current: str | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree "):]
            registered.add(current)
        elif line.startswith("prunable ") and current:
            prunable.add(current)
    return registered, prunable


def _worktree_is_at(worktree: Path, sha: str) -> bool:
    if not (worktree / ".git").exists():
        return False
    return _git(worktree, "rev-parse", "HEAD") == sha


def _state(arm: str, ref: str, sha: str, worktree: Path) -> VariantState:
    return VariantState(
        arm=arm, ref=ref, sha=sha, worktree=worktree, plugin_dir=worktree / "plugin"
    )


def ensure_worktrees(
    repo: Path,
    *,
    base: Path | None = None,
    force: bool = False,
) -> dict[str, VariantState]:
    """Materialise (or verify) one detached worktree per plugin arm.

    Returns one VariantState per arm in VARIANT_ARMS, plus a manifest.json
    snapshot in the variants base directory. The manifest is a convenience;
    the authoritative pin for reproducibility is RunRecord.variant_sha on
    every executed run. Never destructive outside the variants base
    directory, and never touches the operator's other worktrees.
    """
    if base is None:
        # Late import: cli.py owns the repo-relative path constant, and
        # cli.py imports this module — a module-level import would cycle.
        from benchmarks.legalita.run.cli import VARIANTS_DIR

        base = VARIANTS_DIR
    variants_dir = base.resolve()
    variants_dir.mkdir(parents=True, exist_ok=True)
    repo = repo.resolve()

    registered, prunable = _worktree_registry(repo)
    states: dict[str, VariantState] = {}

    for arm in VARIANT_ARMS:
        ref = VARIANT_REFS[arm]
        sha = _resolve_sha(repo, ref)
        worktree = variants_dir / arm
        str_path = str(worktree)

        if str_path in prunable:
            # git itself says the directory is gone or unreadable: drop the
            # stale registration so `worktree add` can recreate it below.
            _git(repo, "worktree", "remove", "--force", str_path)
            registered.discard(str_path)

        if str_path in registered:
            if not _worktree_is_at(worktree, sha) or force:
                # Move (or re-assert) the checkout onto the pin. Safe: the
                # worktree is detached, carries no local commits of ours,
                # and lives entirely inside the variants base directory.
                _git(repo, "-C", str_path, "checkout", "--detach", sha)
            states[arm] = _state(arm, ref, sha, worktree)
            continue

        if worktree.exists():
            if any(worktree.iterdir()):
                inside = (
                    _git(worktree, "rev-parse", "--show-toplevel")
                    if (worktree / ".git").exists()
                    else ""
                )
                if inside and _worktree_is_at(worktree, sha):
                    # A manually created worktree already sitting at the
                    # pin: adopt it instead of refusing.
                    states[arm] = _state(arm, ref, sha, worktree)
                    continue
                raise VariantError(
                    f"{worktree} exists and is not empty but is not this "
                    "benchmark's git worktree; remove it by hand and "
                    "re-run `variants`"
                )
            # Empty leftover directory (e.g. a crashed previous run): safe
            # to remove — it cannot hold anything we did not create.
            worktree.rmdir()

        _git(repo, "worktree", "add", "--detach", str_path, sha)
        states[arm] = _state(arm, ref, sha, worktree)

    manifest_path = variants_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({arm: s.to_dict() for arm, s in states.items()}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return states
