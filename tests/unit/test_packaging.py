"""Guards the wheel actually ships the runtime data the server needs.

`uvx --from git+... mcp-legal-it` used to fail with a FileNotFoundError on
``src/data/indici_foi.json`` because the wheel built by setuptools contained
only ``.py`` files — ``[tool.setuptools.package-data]`` was missing. This
test builds a real wheel with ``uv build`` and inspects its contents.
"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_wheel_ships_data_and_entry_point(tmp_path):
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )

    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"

    with zipfile.ZipFile(wheels[0]) as z:
        names = z.namelist()

        assert "src/data/indici_foi.json" in names
        # the 2.x line keeps the legal:// resources inline in src/resources.py;
        # the src/data/references/*.md layout belongs to the 3.x corpus projection
        assert "src/resources.py" in names
        assert "src/data/tabella_danno_bio.json" in names
        assert "src/cli.py" in names

        entry_points_name = next(n for n in names if n.endswith(".dist-info/entry_points.txt"))
        entry_points = z.read(entry_points_name).decode("utf-8")
        assert "mcp-legal-it = src.cli:main" in entry_points
