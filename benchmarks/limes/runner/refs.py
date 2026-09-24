"""Materialize a pinned enhancement ref (DESIGN §3: `ref` is a pin that is
never deleted — the variant_sha lesson).

A plugin or MCP cell must run the enhancement AT ITS REF, not whatever the
working tree happens to contain: `git archive <ref>` extracts the ref's
content into a cache directory keyed by the ref's commit, so two runs of the
same ref share one immutable tree and a moved tag can never be served from a
stale cache (the key is the commit, not the tag name).
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path


class RefError(RuntimeError):
    """Raised when a ref cannot be resolved or materialized."""


def _git(args: list[str], cwd: Path, binary: bool = False):
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, check=True,
            text=not binary,
        )
    except FileNotFoundError as exc:
        raise RefError("git non disponibile") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
        raise RefError(f"git {' '.join(args)}: {stderr.strip()}") from exc
    return result.stdout


def resolve_commit(ref: str, repo: Path) -> str:
    """The commit a ref names (fail-closed on unknown refs)."""
    return _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], repo).strip()


def materialize(ref: str, repo: Path, cache_dir: Path, subpath: str = "plugin") -> Path:
    """Extract `subpath` of `ref` into `cache_dir/<commit>/` and return the
    extracted `subpath` directory. Idempotent: an existing complete tree is
    reused (a `.complete` marker guards against half-written extractions)."""
    repo = Path(_git(["rev-parse", "--show-toplevel"], repo).strip())
    commit = resolve_commit(ref, repo)
    target = cache_dir / commit
    marker = target / ".complete"
    out = target / subpath
    if marker.is_file() and out.is_dir():
        return out
    target.mkdir(parents=True, exist_ok=True)
    archive = _git(["archive", "--format=tar", commit, subpath], repo, binary=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target, filter="data")
    if not out.is_dir():
        raise RefError(f"{ref}: {subpath}/ assente nel ref")
    marker.write_text(f"{ref} {commit}\n", encoding="utf-8")
    return out
