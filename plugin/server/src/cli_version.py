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
    """Version from installed metadata, else from the pyproject next to this package."""
    try:
        return metadata.version("mcp-legal-it")
    except metadata.PackageNotFoundError:
        pass
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
    return "0.0.0"
