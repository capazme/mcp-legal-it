"""Package version helper.

Kept separate from ``mcp_legal_it.cli`` (which imports ``mcp_legal_it.server``) so that
``mcp_legal_it.server`` can import ``package_version()`` without creating a circular
import between ``mcp_legal_it.server`` and ``mcp_legal_it.cli``.
"""
from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path


def package_version() -> str:
    """Version of the code that is actually running.

    A source checkout wins over installed metadata: an editable install keeps
    the version of whatever branch was checked out when it was installed, so
    `metadata.version()` lies as soon as the tree moves (it reported 2.14.0
    while develop was at 3.0.0). The pyproject next to the package is the
    truth for a checkout; the metadata is the truth for an installed wheel,
    where no pyproject ships.
    """
    # In a checkout the package lives in plugin/server/mcp_legal_it/, so
    # parent.parent is plugin/server/ (which ships its own pyproject.toml). The
    # extra parent.parent.parent fallback covers a copy of the package placed
    # at the repo root.
    here = Path(__file__).resolve()
    for pyproject in (here.parent.parent / "pyproject.toml", here.parent.parent.parent / "pyproject.toml"):
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r'^version = "([^"]+)"', text, re.M)
        if m:
            return m.group(1)
    try:
        return metadata.version("mcp-legal-it")
    except metadata.PackageNotFoundError:
        return "0.0.0"
