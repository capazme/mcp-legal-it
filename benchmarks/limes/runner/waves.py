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

from benchmarks.limes.runner.shas import Shas, _git_root, ShaError


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
    # Bank slice: files under bank/ this wave loads (empty = every slice,
    # the wave-0 behaviour). A later wave must name its slices, or the
    # union of every wave's private items would leak into its denominators.
    bank_slices: tuple[str, ...] = ()
    # Validity cards (DESIGN §8) are mandatory from wave 1: an item without
    # one does not enter the wave.
    require_validity: bool = False
    # Item ids excluded after human review, decided BEFORE the freeze by the
    # pre-registered rule in `review` (never after seeing model answers).
    excluded: tuple[str, ...] = ()
    review: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)

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
    bank = raw.get("bank") or {}
    if not isinstance(bank, dict):
        raise WaveError(f"{path}: 'bank' must be a mapping")
    slices = bank.get("slices") or []
    if not isinstance(slices, list) or not all(isinstance(x, str) for x in slices):
        raise WaveError(f"{path}: bank.slices must be a list of paths under bank/")
    analysis = raw.get("analysis") or {}
    if not isinstance(analysis, dict):
        raise WaveError(f"{path}: 'analysis' must be a mapping")
    return Wave(
        id=wave_id,
        tag=tag,
        configs=configs,
        models=models,
        expected_cells=expected if expected is not None else 0,
        description=str(raw.get("description", "")),
        bank_slices=tuple(slices),
        require_validity=bool(bank.get("require_validity", False)),
        excluded=tuple(str(x) for x in (bank.get("excluded") or [])),
        review=dict(raw.get("review") or {}),
        analysis=analysis,
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


def freeze_guard(
    wave: Wave, frozen: Shas, repo: Path, paths: list[Path] | None = None
) -> dict:
    """Verify the wave is frozen: the tag exists AND the content the run is
    about to use (bank, protocol, config manifests — `paths`) is identical
    to what the tag froze, with nothing uncommitted or untracked on top.

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

    checked: list[str] = []
    for path in paths or []:
        rel = path.resolve().relative_to(root).as_posix()
        if not _git(["ls-tree", f"{wave.tag}", "--", rel], root):
            raise WaveError(
                f"wave {wave.id}: {rel} assente dal tag {wave.tag!r} — il run "
                f"userebbe contenuto mai congelato"
            )
        # Tag vs working tree: catches edits committed after the tag AND
        # uncommitted edits (both would make the record lie about content).
        changed = _git(["diff", "--name-only", wave.tag, "--", rel], root)
        untracked = _git(["ls-files", "--others", "--exclude-standard", "--", rel], root)
        if changed or untracked:
            drift = (changed + "\n" + untracked).strip().splitlines()
            raise WaveError(
                f"wave {wave.id}: {rel} diverge dal tag {wave.tag!r} "
                f"({', '.join(drift[:5])}{'…' if len(drift) > 5 else ''}) — "
                f"eseguire la wave dal suo tag (git worktree) o congelarne una nuova"
            )
        checked.append(rel)

    return {
        "wave": wave.id,
        "tag": wave.tag,
        "tag_commit": tag_commit,
        "frozen": frozen.to_dict(),
        "checked": checked,
    }


def freeze_status(bank_dir: Path, protocol_dir: Path) -> dict:
    """Diagnostic for `limes check`: which paths are frozen (committed and
    clean) vs pending. Never raises for pending paths — it reports them;
    outside a git repository every path is reported as not frozen."""
    try:
        root = _git_root(bank_dir)
    except ShaError:
        return {
            label: {"path": str(path), "committed": False, "dirty": True, "frozen": False}
            for label, path in (("bank", bank_dir), ("protocol", protocol_dir))
        }

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
