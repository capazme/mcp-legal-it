#!/usr/bin/env python3
"""Verify every launcher declares the same runtime dependencies as pyproject.toml.

The runtime dependency set is duplicated across the packaging manifests and the
bootstrap launchers, because each install path resolves dependencies on its own:

    pyproject.toml            <- single source of truth (Dockerfile: `pip install .`)
    plugin/server/pyproject.toml
    plugin/start_server.sh    <- `uv run --with ...` path
    plugin/start_server.sh    <- system-venv fallback path (no `uv` available)
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

# A PEP 508 requirement, loose enough for the specs we declare (name + specifier).
_REQUIREMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\s*[<>=!~]")


def normalize(spec: str) -> tuple[str, str]:
    """Split a requirement into (canonical name, specifier) per PEP 503/440.

    `python_docx >= 1.0` and `python-docx>=1.0` must compare equal.
    """
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", spec.strip())
    if not match:
        raise ValueError(f"unparseable requirement: {spec!r}")
    name, specifier = match.groups()
    canonical = re.sub(r"[-_.]+", "-", name).lower()
    return canonical, specifier.replace(" ", "")


def as_mapping(specs: list[str]) -> dict[str, str]:
    return dict(normalize(spec) for spec in specs)


def read_pyproject(path: Path) -> list[str]:
    data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
    return data["project"]["dependencies"]


def read_uv_with_flags(path: Path) -> list[str]:
    """Extract every `--with "<spec>"` argument from a shell launcher."""
    text = (ROOT / path).read_text(encoding="utf-8")
    return re.findall(r'--with\s+"([^"]+)"', text)


def read_pip_install_args(path: Path) -> list[str]:
    """Extract the quoted requirements of the `pip install` fallback command.

    The command spans continuation lines, so join them before scanning, and keep
    only tokens that look like requirements (drops flags and the interpreter path).
    """
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if "pip" not in line or " install" not in line:
            continue
        command = line
        while command.rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            command = command.rstrip().rstrip("\\") + " " + lines[index]
        return [
            token
            for token in re.findall(r'"([^"]+)"', command)
            if _REQUIREMENT.match(token)
        ]
    raise ValueError(f"no `pip install` command found in {path}")


def read_manifest_with_flags(path: Path) -> list[str]:
    """Extract `--with <spec>` pairs from the .mcpb manifest mcp_config args."""
    manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
    args = manifest["server"]["mcp_config"]["args"]
    return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--with"]


TARGETS: list[tuple[str, Path, object]] = [
    ("plugin/server/pyproject.toml", Path("plugin/server/pyproject.toml"), read_pyproject),
    ("plugin/start_server.sh (uv path)", Path("plugin/start_server.sh"), read_uv_with_flags),
    ("plugin/start_server.sh (venv fallback)", Path("plugin/start_server.sh"), read_pip_install_args),
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

    failures = 0
    for label, path, reader in TARGETS:
        try:
            actual = as_mapping(reader(path))
        except (OSError, KeyError, ValueError) as exc:
            print(f"\n{label}\n  ERROR    could not read declarations: {exc}")
            failures += 1
            continue
        if report(label, expected, actual):
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
