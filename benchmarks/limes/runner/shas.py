"""The five SHA (DESIGN §2): identity of a measurement.

Every SHA is computed from immutable references — git commits for content,
explicitly pinned strings for models. Fail-closed: a path that is dirty or
untracked raises instead of producing a SHA whose provenance cannot be
stated, and a missing git context aborts the run. The lesson of
`variant_sha` lives here: the pin must name refs that are not deleted, so
identity lives in the record (these functions return strings into the
record; they never rewrite history).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class ShaError(ValueError):
    """Raised when a SHA cannot be honestly computed."""


@dataclass(frozen=True)
class Shas:
    bank_sha: str
    protocol_sha: str
    model_sha: str
    config_sha: str
    judge_sha: str  # "none" on the mechanical-only protocol

    def to_dict(self) -> dict[str, str]:
        return {
            "bank_sha": self.bank_sha,
            "protocol_sha": self.protocol_sha,
            "model_sha": self.model_sha,
            "config_sha": self.config_sha,
            "judge_sha": self.judge_sha,
        }


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:
        raise ShaError("git non disponibile: impossibile dichiarare la provenienza") from exc
    except subprocess.CalledProcessError as exc:
        raise ShaError(f"git {' '.join(args)}: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def _git_root(cwd: Path) -> Path:
    out = _git(["rev-parse", "--show-toplevel"], cwd)
    if not out:
        raise ShaError("fuori da un repository git: nessuna identità possibile")
    return Path(out)


def _committed_sha(root: Path, relpath: Path) -> str:
    """Blob sha of a path at HEAD, failing closed on dirty/untracked content."""
    path_arg = relpath.as_posix()

    tracked = _git(["ls-files", "--error-unmatch", path_arg], root)
    if not tracked:
        raise ShaError(
            f"{path_arg}: non tracciato da git — bank_sha/protocol_sha non "
            f"dichiarabile (committare o congelare nel tag prima del run)"
        )
    dirty = _git(["status", "--porcelain", "--", path_arg], root)
    if dirty:
        raise ShaError(
            f"{path_arg}: modifiche non committate — eseguire il run solo su "
            f"contenuto congelato (DESIGN §2)"
        )
    blob = _git(["rev-parse", f"HEAD:{path_arg}"], root)
    if not blob:
        raise ShaError(f"{path_arg}: assente da HEAD")
    return blob


def bank_sha(bank_dir: Path) -> str:
    """Identity of the bank slice: one sha over every tracked file."""
    root = _git_root(bank_dir)
    rel = bank_dir.resolve().relative_to(root)
    # Paths relative to the scanned directory only: joining them onto `rel`
    # yields the repo-relative path without mixing absolute/relative bases
    # (an absolute prefix here breaks `relative_to` for any non-root cwd).
    files = sorted(
        p.relative_to(bank_dir.resolve())
        for p in bank_dir.rglob("*")
        if p.is_file()
    )
    if not files:
        raise ShaError(f"{bank_dir}: banca vuota")
    parts = [
        f"{_committed_sha(root, rel / p.as_posix())}"
        for p in files
    ]
    # One sha over the sorted list of blob shas: order-independent, stable.
    blob_list = "\n".join(f"{p.as_posix()} {s}" for p, s in zip(files, parts))
    import hashlib

    return hashlib.sha256(blob_list.encode("utf-8")).hexdigest()[:16]


def protocol_sha(protocol_dir: Path) -> str:
    """Identity of the protocol directory (same discipline as the bank)."""
    return bank_sha(protocol_dir)


def model_sha(model: str) -> str:
    """Pinned model identity: an explicit string, never a moving alias
    resolved at run time (DESIGN §2: 'alias + versione dichiarata dal
    fornitore al momento della run'). The caller passes the pinned id from
    the wave manifest; nothing here queries the network."""
    if not model or not model.strip():
        raise ShaError("model_sha: modello non pinnato")
    return model.strip()


def judge_sha(protocol_dir: Path) -> str:
    """Identity of the judging panel; 'none' while the protocol runs
    mechanical-only (judge.models == [])."""
    protocol = None
    try:
        import yaml

        raw = yaml.safe_load(
            (protocol_dir / "protocol.yaml").read_text(encoding="utf-8")
        )
        models = (raw.get("judge") or {}).get("models") or []
        if not models:
            return "none"
        protocol = models
    except FileNotFoundError as exc:
        raise ShaError(f"{protocol_dir}: protocol.yaml mancante") from exc
    import hashlib

    return hashlib.sha256(repr(sorted(map(str, protocol))).encode()).hexdigest()[:16]


def collect(
    bank_dir: Path,
    protocol_dir: Path,
    model: str,
    manifest_source: Path,
) -> Shas:
    """The five SHA of a run, all fail-closed."""
    return Shas(
        bank_sha=bank_sha(bank_dir),
        protocol_sha=protocol_sha(protocol_dir),
        model_sha=model_sha(model),
        config_sha=_committed_sha(_git_root(manifest_source), manifest_source),
        judge_sha=judge_sha(protocol_dir),
    )
