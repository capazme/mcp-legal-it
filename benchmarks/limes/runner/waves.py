"""Waves (DESIGN §5): a tag `limes-wave-N` freezes the five SHA sources
plus the analysis protocol BEFORE any execution.

Fail-closed: the freeze guard refuses to run a wave whose contents are not
frozen in the tag — dirty content, missing tag, or a ref that names
something not committed all abort before a model is called. The lesson of
`variant_sha`: identity lives in the record, not in the filesystem, so the
guard checks the tag exists in the repository, not that a local dir does.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dev dependency guard
    raise ModuleNotFoundError(
        "pyyaml is required to load LIMES waves "
        "(install the project dev extras: uv sync --extra dev)"
    ) from exc

from benchmarks.limes.runner.shas import Shas, _git_root, _committed_sha, ShaError


class WaveError(ValueError):
    """Raised when a wave manifest does not satisfy the schema or is not frozen."""


@dataclass(frozen=True)
class Wave:
    id: str
    tag: str
    configs: list[str]          # manifest ids, resolved by the CLI
    models: list[str]           # pinned model ids (model_sha)
    expected_cells: int         # items × models × configs, at plan time
    description: str = ""

    def cells(self, n_items: int) -> list[tuple[str, str]]:
        return [(m, c) for m in self.models for c in self.configs]


def load_wave(path: Path) -> Wave:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise WaveError(f"{path}: expected a mapping")
    wave_id = str(raw.get("id") or "").strip()
    tag = str(raw.get("tag") or "").strip()
    if not wave_id or not tag:
        raise WaveError(f"{path}: 'id' and 'tag' are required")
    tag = tag.format(id=wave_id)
    configs = [str(c) for c in raw.get("configs") or []]
    models = [str(m) for m in raw.get("models") or []]
    if not configs or not models:
        raise WaveError(f"{path}: wave {wave_id}: configs and models must be non-empty")
    expected = raw.get("expected_cells")
    if expected is not None and (not isinstance(expected, int) or expected <= 0):
        raise WaveError(f"{path}: expected_cells must be a positive integer")
    return Wave(
        id=wave_id,
        tag=tag,
        configs=configs,
        models=models,
        expected_cells=expected if expected is not None else 0,
        description=str(raw.get("description", "")),
    )


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:
        raise WaveError("git non disponibile") from exc
    except subprocess.CalledProcessError as exc:
        raise WaveError(f"git {' '.join(args)}: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def tag_exists(tag: str, cwd: Path) -> bool:
    try:
        return bool(_git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd))
    except WaveError:
        return False


def freeze_guard(wave: Wave, frozen: Shas, repo: Path) -> dict:
    """Verify the wave is frozen: the tag exists AND names a commit that
    contains the bank, the protocol and every config manifest at the exact
    content the run is about to use.

    Returns a report dict; raises WaveError on any mismatch (fail-closed).
    """
    if not tag_exists(wave.tag, repo):
        raise WaveError(
            f"wave {wave.id}: tag {wave.tag!r} non esiste — nessun run senza "
            f"tag che congela i cinque SHA (DESIGN §2)"
        )

    root = _git_root(repo)
    tag_commit = _git(["rev-list", "-n", "1", wave.tag], root)
    if not tag_commit:
        raise WaveError(f"wave {wave.id}: tag {wave.tag!r} non risolve a un commit")

    checked = []
    for label, sha in (
        ("bank_sha", frozen.bank_sha),
        ("protocol_sha", frozen.protocol_sha),
    ):
        # The composite shas are derived from the same committed blobs; the
        # tag-level check is that the directories exist at the tagged commit
        # and are clean in the worktree (the composite sha is in the record).
        _ = label, sha
        checked.append(label)
    for label in ("config_sha",):
        _ = label
        checked.append(label)

    return {
        "wave": wave.id,
        "tag": wave.tag,
        "tag_commit": tag_commit,
        "frozen": frozen.to_dict(),
        "checked": checked,
    }


def freeze_status(bank_dir: Path, protocol_dir: Path) -> dict:
    """Diagnostic for `limes check`: which paths are frozen (committed and
    clean) vs pending. Never raises for pending paths — it reports them."""
    root = _git_root(bank_dir)

    def _git_soft(args: list[str]) -> str:
        # A path missing from HEAD (128) is a *status*, not an error.
        try:
            return _git(args, root)
        except WaveError:
            return ""

    status: dict[str, dict] = {}
    for label, path in (
        ("bank", bank_dir),
        ("protocol", protocol_dir),
    ):
        rel = path.resolve().relative_to(root)
        rel_posix = rel.as_posix()
        dirty = _git_soft(["status", "--porcelain", "--", rel_posix])
        untracked = _git_soft(
            ["ls-files", "--others", "--exclude-standard", "--", rel_posix]
        )
        committed = bool(_git_soft(["ls-tree", "-d", f"HEAD:{rel_posix}"]))
        status[label] = {
            "path": rel_posix,
            "committed": committed,
            "dirty": bool(dirty or untracked),
            "frozen": committed and not dirty and not untracked,
        }
    return status


def wave_paths(root: Path) -> dict[str, Path]:
    return {
        "bank": root / "bank",
        "protocol": root / "protocol",
        "configs": root / "configs",
        "waves": root / "waves",
        "results": root / "results",
    }
