#!/usr/bin/env python3
"""Verify every launcher declares the same runtime dependencies as pyproject.toml.

The runtime dependency set is duplicated across the packaging manifests and the
bootstrap launchers, because each install path resolves dependencies on its own:

    pyproject.toml            <- single source of truth (Dockerfile: `pip install .`)
    plugin/server/pyproject.toml
    plugin/server/uv.lock     <- what the plugin installs (`uv run --frozen`)
    dxt/manifest.json         <- Claude Desktop `.mcpb` mcp_config

Nothing keeps those copies in sync automatically, and they have drifted before:
the now-deleted `requirements.txt` and `dxt/start_server.sh` both silently lost
`python-docx`, which broke the procura/quotazione tools for anyone installing
through them. This check makes that class of drift a CI failure.

Usage:
    python scripts/check_deps_sync.py

Exits 0 when every target matches, 1 otherwise (printing the exact delta).
Requires Python 3.11+ for `tomllib`.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE_OF_TRUTH = Path("pyproject.toml")


def normalize(spec: str) -> tuple[str, str]:
    """Key and version specifier of a requirement, per PEP 503/440.

    `python_docx >= 1.0` and `python-docx>=1.0` must compare equal. The marker
    is part of the key, its `and`/`or` clauses sorted (uv rewrites markers in
    its own order), so one package declared for two platforms (cryptography:
    <49 on Intel Macs, >=50 elsewhere) stays two entries.
    """
    requirement, _, marker = spec.partition(";")
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", requirement.strip())
    if not match:
        raise ValueError(f"unparseable requirement: {spec!r}")
    name, specifier = match.groups()
    key = re.sub(r"[-_.]+", "-", name).lower()
    marker = marker.replace(" ", "")
    if marker:
        joiner = "and" if "and" in marker else "or"
        key += ";" + joiner.join(sorted(marker.split(joiner)))
    return key, specifier.replace(" ", "")


def as_mapping(specs: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for spec in specs:
        key, specifier = normalize(spec)
        if key in mapping:
            raise ValueError(f"declared twice: {spec!r}")
        mapping[key] = specifier
    return mapping


def read_pyproject(path: Path) -> list[str]:
    data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
    return data["project"]["dependencies"]


def read_manifest_with_flags(path: Path) -> list[str]:
    """Extract `--with <spec>` pairs from the .mcpb manifest mcp_config args."""
    manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
    args = manifest["server"]["mcp_config"]["args"]
    return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--with"]


def read_uv_lock(path: Path) -> list[str]:
    """The requirements the lock was resolved from (its root package's metadata).

    `uv run --frozen` installs the lock without looking at pyproject.toml, so a
    range edited in pyproject but not relocked would silently never ship.
    """
    data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
    root = next(
        package for package in data["package"]
        if package.get("source", {}).get("virtual") == "."
    )
    return [
        f'{entry["name"]}{entry.get("specifier", "")}'
        + (f'; {entry["marker"]}' if entry.get("marker") else "")
        for entry in root["metadata"]["requires-dist"]
    ]


# Launchers that deliberately pin a narrower range than pyproject.toml, by name.
# Library installs (wheel, uvx) accept fastmcp>=3.4,<5 since 2.16.1, while the
# .mcpb launcher keeps its FastMCP 3 pin until it moves to FastMCP 4 in its own
# release: changing the string also invalidates every user's uv environment, so
# it must not ride along with an unrelated fix. (The plugin's lock holds FastMCP 3
# through a uv constraint instead.) The override must match exactly: drift in a
# launcher is still a failure.
LAUNCHER_OVERRIDES: dict[str, str] = {"fastmcp": ">=2.0,<4"}

TARGETS: list[tuple[str, Path, object]] = [
    ("plugin/server/pyproject.toml", Path("plugin/server/pyproject.toml"), read_pyproject),
    ("plugin/server/uv.lock (requires-dist)", Path("plugin/server/uv.lock"), read_uv_lock),
    ("dxt/manifest.json (mcp_config)", Path("dxt/manifest.json"), read_manifest_with_flags),
]


def report(label: str, expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    problems = []
    for name, specifier in expected.items():
        if name not in actual:
            problems.append(f"  MISSING  {name}{specifier}")
        elif actual[name] != specifier:
            problems.append(
                f"  DIFFERS  {name}: declares {actual[name]!r}, expected {specifier!r}"
            )
    for name, specifier in actual.items():
        if name not in expected:
            problems.append(f"  EXTRA    {name}{specifier}")
    if problems:
        print(f"\n{label}")
        print("\n".join(problems))
    return problems


def main() -> int:
    expected = as_mapping(read_pyproject(SOURCE_OF_TRUTH))

    print(f"Source of truth: {SOURCE_OF_TRUTH} ({len(expected)} runtime dependencies)")
    for name, specifier in sorted(expected.items()):
        print(f"  {name}{specifier}")

    if LAUNCHER_OVERRIDES:
        print("Launcher overrides (narrower on purpose):")
        for name, specifier in sorted(LAUNCHER_OVERRIDES.items()):
            print(f"  {name}{specifier}")

    failures = 0
    for label, path, reader in TARGETS:
        try:
            actual = as_mapping(reader(path))
        except (OSError, KeyError, ValueError, StopIteration) as exc:
            print(f"\n{label}\n  ERROR    could not read declarations: {exc}")
            failures += 1
            continue
        if reader is read_pyproject:
            wanted = expected
        elif reader is read_uv_lock:
            wanted = expected
        else:
            wanted = {**expected, **LAUNCHER_OVERRIDES}
        if report(label, wanted, actual):
            failures += 1

    if failures:
        print(
            f"\nFAIL: {failures} of {len(TARGETS)} launchers disagree with "
            f"{SOURCE_OF_TRUTH}.\nUpdate them so every install path resolves the "
            "same dependency set."
        )
        return 1

    print(f"\nOK: all {len(TARGETS)} launchers match {SOURCE_OF_TRUTH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
