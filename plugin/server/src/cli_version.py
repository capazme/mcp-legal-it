"""Package version helper.

Kept separate from ``src.cli`` (which imports ``src.server``) so that
``src.server`` can import ``package_version()`` without creating a circular
import between ``src.server`` and ``src.cli``.
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
    # ``src`` is a tracked symlink to ``plugin/server/src`` on this branch, so
    # __file__ resolves under plugin/server/src/ and parent.parent is
    # plugin/server/ (which ships its own pyproject.toml). The extra
    # parent.parent.parent fallback covers the repo root, in case the symlink
    # is ever replaced by a plain copy of the package.
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
