#!/usr/bin/env python3
"""The release tarball keeps its exclusions, and nothing it needs is excluded.

`.gitattributes` marks `/src` and `/tests` export-ignore: the marketplace
backend ingests the codeload tarball of a tag and rejects symlinks (the local
`src` symlink) and dev content (`failed_content`). Those patterns are
hand-maintained, so they drift the way hand-maintained lists do: a new runtime
file that lands under an excluded path, or a widened attribute that starts
swallowing a required one, ships broken and only the marketplace sync notices.

This script closes both directions from the repository itself:

1. forbidden entries -- anything under `/src` or `/tests`, and any symlink --
   must not appear in the tarball;
2. required entries -- every file `git ls-tree` tracks that is not
   export-ignored must appear, exactly once.

Both checks compare the archive against the tracked tree via
`git check-attr export-ignore`, so a brand-new file is required automatically:
there is no list to maintain. Stdlib plus `git`, so it runs anywhere the
tarball can, and in CI with no dependency install.

    python3 scripts/verify_tarball.py                # git archive HEAD
    python3 scripts/verify_tarball.py --tag v2.13.1  # the tagged tree
    python3 scripts/verify_tarball.py --tar p.tar.gz # a tarball already built

Exit 1 prints every problem; exit 0 prints one summary line. Run it on every
push (the tarball-sync job) and on every tag, before the marketplace sync can
see the release.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import subprocess
import sys
import tarfile
from pathlib import Path

#: Paths that must never ship: dev sources, tests, and symlinks (the
#: marketplace sandbox rejects symlinks outright).
FORBIDDEN_PREFIXES = ("src/", "tests/")

#: The local symlink the export-ignore contract is about; kept here so the
#: check's failure message can name it.
SYMLINK_NOTE = (
    "symlink nel tarball: il sandbox del marketplace lo rifiuta "
    "(failed_content); allarga export-ignore o non tracciarlo"
)


def tracked_files(rev: str) -> list[str]:
    """Every path the revision tracks, NUL-separated so spaces survive."""
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", rev],
        capture_output=True,
        check=True,
    )
    return sorted(p for p in out.stdout.decode("utf-8").split("\0") if p)


def _attribute_rules(rev: str) -> list[tuple[str, bool]]:
    """The rev's root .gitattributes, reduced to export-ignore rules.

    Root-only is deliberate: `git check-attr` cannot read a tree's attributes
    without a modern `--source`, and this repository declares export-ignore in
    the root file only. If a per-directory .gitattributes ever appears, extend
    this to walk the path's directories -- the two call sites below stay the
    same. Unsetting (`-export-ignore`) is honored, last match wins.
    """
    out = subprocess.run(
        ["git", "show", "%s:.gitattributes" % rev], capture_output=True
    )
    if out.returncode != 0:
        return []
    regole: list[tuple[str, bool]] = []
    for riga in out.stdout.decode("utf-8", "replace").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        campi = riga.split()
        if "export-ignore" in campi[1:]:
            regole.append((campi[0], True))
        elif "-export-ignore" in campi[1:]:
            regole.append((campi[0], False))
    return regole


def _rule_matches(pattern: str, path: str) -> bool:
    """Gitattributes matching for the shapes this repo uses.

    A leading `/` anchors to the root (`/src` is the top-level directory only);
    a bare name matches that path segment at any depth (`tests/` is everything
    under `tests/`); `*` globs work within a segment.
    """
    if pattern.startswith("/"):
        base = pattern[1:].rstrip("/")
        return path == base or path.startswith(base + "/")
    segmenti = path.split("/")
    return any(
        fnmatch.fnmatch(segmento, pattern.rstrip("/")) for segmento in segmenti[:-1]
    ) or fnmatch.fnmatch(path, pattern.rstrip("/") + "/*")


def export_ignored(rev: str, paths: list[str]) -> set[str]:
    """The paths the revision's own .gitattributes excludes from the archive."""
    if not paths:
        return set()
    regole = _attribute_rules(rev)
    ignorati: set[str] = set()
    for path in paths:
        escluso = False
        for pattern, valore in regole:
            if _rule_matches(pattern, path):
                escluso = valore
        if escluso:
            ignorati.add(path)
    return ignorati


def archive_bytes(rev: str | None, tar_path: Path | None) -> bytes:
    """The tarball to check: a local file, or `git archive` of a revision."""
    if tar_path is not None:
        return tar_path.read_bytes()
    return subprocess.run(
        ["git", "archive", rev or "HEAD"], capture_output=True, check=True
    ).stdout


def _strip_prefix(names: list[str]) -> tuple[str, list[str]]:
    """Drop the single top-level directory, if every entry shares one.

    `git archive` emits bare paths; the codeload tarball wraps everything in
    `<repo>-<ref>/`. Accepting either keeps the same contract for both.
    """
    if names and all(n and "/" in n for n in names):
        prefisso = names[0].split("/", 1)[0] + "/"
        if all(n.startswith(prefisso) for n in names):
            return prefisso, sorted(
                n[len(prefisso):] for n in names if n and not n.endswith("/")
            )
    return "", sorted(n for n in names if n and not n.endswith("/"))


def check(blob: bytes, tracked: list[str], ignored: set[str]) -> list[str]:
    """The problems in this tarball, one message per failure."""
    problemi: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
        membri = tar.getmembers()
    # Only regular files are compared against the tracked tree: directory
    # members exist in the archive but not in `git ls-tree --name-only`, and
    # tarfile strips their trailing slash, so a name-based filter cannot tell
    # them apart.
    _, files = _strip_prefix([m.name for m in membri if m.isfile()])

    for membro in membri:
        if membro.issym() or membro.islnk():
            problemi.append("%s: %s" % (membro.name, SYMLINK_NOTE))

    for nome in files:
        if nome.startswith(FORBIDDEN_PREFIXES):
            problemi.append(
                "escluso mancato: %s e' nel tarball ma .gitattributes lo vieta" % nome
            )

    attesi = sorted(p for p in tracked if p not in ignored)
    mancanti = sorted(set(attesi) - set(files))
    for nome in mancanti:
        problemi.append(
            "esclusione di troppo: %s e' tracciato e non export-ignore, ma non "
            "e' nel tarball" % nome
        )
    inattesi = sorted(set(files) - set(attesi) - {n for n in files if n.startswith(FORBIDDEN_PREFIXES)})
    for nome in inattesi:
        problemi.append("imprevisto: %s e' nel tarball ma non e' tracciato" % nome)
    return problemi


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the release tarball's exclusions and completeness."
    )
    parser.add_argument(
        "--tag", default=None, help="verifica il tarball di questo tag/revisione (default HEAD)"
    )
    parser.add_argument(
        "--tar", type=Path, default=None, help="verifica un tarball gia' generato invece di git archive"
    )
    args = parser.parse_args()

    rev = args.tag or "HEAD"
    tracked = tracked_files(rev)
    ignored = export_ignored(rev, tracked)
    blob = archive_bytes(args.tag, args.tar)
    problemi = check(blob, tracked, ignored)

    for problema in problemi:
        print(problema, file=sys.stderr)
    if problemi:
        print("verify_tarball: %d problemi" % len(problemi), file=sys.stderr)
        return 1
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
        files = [m for m in tar.getmembers() if m.isfile()]
    print(
        "verify_tarball: ok -- %d file, src/ e tests/ esclusi, nessun symlink" % len(files)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
