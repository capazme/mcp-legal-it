"""Guards the wheel actually ships the runtime data the server needs.

`uvx --from git+... mcp-legal-it` used to fail with a FileNotFoundError on
``mcp_legal_it/data/indici_foi.json`` because the wheel built by setuptools contained
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

        assert "mcp_legal_it/data/indici_foi.json" in names
        assert "mcp_legal_it/data/tabella_danno_bio.json" in names
        # the 3.x line projects the legal:// resources from content/references
        assert any(
            n.startswith("mcp_legal_it/data/references/") and n.endswith(".md") for n in names
        ), "no mcp_legal_it/data/references/*.md shipped in the wheel"
        assert "mcp_legal_it/cli.py" in names
        # the Italgiure intermediate: without it the client cannot verify TLS
        assert "mcp_legal_it/lib/italgiure/ti_trust_ov_ca.crt" in names
        # 3.0 renamed the package away from `src`: a published wheel must not
        # own a generic top-level name. A stale `build/` left by a pre-3.0
        # build would bring `src/` back in -- remove it and rebuild.
        top_level = {n.split("/", 1)[0] for n in names}
        packages = {t for t in top_level if not t.endswith(".dist-info")}
        assert packages == {"mcp_legal_it"}, sorted(top_level)

        entry_points_name = next(n for n in names if n.endswith(".dist-info/entry_points.txt"))
        entry_points = z.read(entry_points_name).decode("utf-8")
        assert "mcp-legal-it = mcp_legal_it.cli:main" in entry_points

        # MPL-2.0 from 3.0, Apache-2.0 for the 2.x contributions: NOTICE points at
        # LICENSES/Apache-2.0.txt, so the wheel must carry that text as well.
        licences = {n.split(".dist-info/licenses/", 1)[1] for n in names if ".dist-info/licenses/" in n}
        assert {"LICENSE", "NOTICE", "LICENSES/Apache-2.0.txt"} <= licences, sorted(licences)
