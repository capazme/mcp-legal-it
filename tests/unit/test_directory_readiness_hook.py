"""The directory check and the citation hook (ported from the 3.0 line, cbed0a5).

The hook runs `uv run --no-project --isolated --no-config --python 3.12 python <gate>`: a bare
interpreter, nothing resolved or installed, so the check accepts it. Only uv's own options count,
the ones before the executed command: `--no-project` with `--with`/`-w` or `--script`/`-s` still
installs packages and still needs --frozen/--locked, and a `--no-project` passed to the command
proves nothing.
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
                      ["run", "--no-project", "--isolated", "--no-config", "--python", "3.12", "python",
                       "${CLAUDE_PLUGIN_ROOT}/hooks/citation-gate.py"],
                      report)
    assert report.blocks == []


@pytest.mark.parametrize("args", [
    ["run", "--no-project", "--with", "httpx", "python", "x.py"],
    ["run", "--no-project", "--with=httpx", "python", "x.py"],
    ["run", "--no-project", "-w", "httpx", "python", "x.py"],
    ["run", "--no-project", "-whttpx", "python", "x.py"],
    ["run", "--no-project", "--with-requirements", "r.txt", "python", "x.py"],
    ["run", "--no-project", "--script", "x.py"],
    ["run", "--no-project", "-s", "x.py"],
    ["run", "--python", "3.12", "python", "x.py"],
    ["run", "--python", "3.12", "python", "x.py", "--no-project"],
    ["run", "python", "--no-project", "x.py"],
])
def test_a_run_that_installs_still_needs_a_lock(args):
    chk = _checker()
    report = chk.Report()
    chk.check_command("hooks.json Stop", "uv", args, report)
    assert any("without --frozen or --locked" in b for b in report.blocks)


def test_only_options_before_the_command_are_uv_s():
    chk = _checker()
    assert chk.uv_run_options(["run", "--no-project", "--python", "3.12", "python", "x.py", "--frozen"]) == [
        "--no-project", "--python", "3.12"]
    assert not chk.uv_run_installs(chk.uv_run_options(
        ["run", "--no-project", "python", "x.py", "--with", "httpx", "-s"]))
