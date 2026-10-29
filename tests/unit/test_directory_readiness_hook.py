"""The directory check and the citation hook (ported from the 3.0 line, cbed0a5).

The hook runs `uv run --no-project --python 3.12 python <gate>`: a bare interpreter, nothing
resolved or installed, so the check accepts it. `--no-project` with `--with` still installs
packages and still needs --frozen/--locked.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _checker():
    spec = importlib.util.spec_from_file_location("check_directory_readiness",
                                                  REPO / "scripts" / "check_directory_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_bare_no_project_run_is_not_blocked():
    chk = _checker()
    report = chk.Report()
    chk.check_command("hooks.json Stop", "uv",
                      ["run", "--no-project", "--python", "3.12", "python", "${CLAUDE_PLUGIN_ROOT}/hooks/citation-gate.py"],
                      report)
    assert report.blocks == []


@pytest.mark.parametrize("args", [
    ["run", "--no-project", "--with", "httpx", "python", "x.py"],
    ["run", "--python", "3.12", "python", "x.py"],
])
def test_a_run_that_installs_still_needs_a_lock(args):
    chk = _checker()
    report = chk.Report()
    chk.check_command("hooks.json Stop", "uv", args, report)
    assert any("without --frozen or --locked" in b for b in report.blocks)
