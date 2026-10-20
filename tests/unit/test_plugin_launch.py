"""How the distributed plugin starts its MCP server.

The plugin runs `uv run --frozen --project ${CLAUDE_PLUGIN_ROOT}/server`: the
exact versions in plugin/server/uv.lock, in an environment of the plugin's own.
Two earlier designs broke users: `uv run --with <ranges>` from the session's
working directory synced *the user's* project `.venv` whenever that folder held
a pyproject.toml, and a bash bootstrap needed Git Bash on Windows. The
directory also refuses a launcher without pinned versions.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # Python 3.11+

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugin"


def test_the_server_starts_from_the_lock_without_a_shell():
    server = json.loads((PLUGIN / ".mcp.json").read_text())["mcpServers"]["legal-it"]
    assert server["command"] == "uv"
    args = server["args"]
    assert args[0] == "run" and "--frozen" in args
    # --no-sync: Python only, so the bootstrap can answer Claude Code within its
    # 30-second start limit while it installs the libraries itself.
    assert "--no-sync" in args
    assert args[args.index("--project") + 1] == "${CLAUDE_PLUGIN_ROOT}/server"
    assert args[-2:] == ["python", "${CLAUDE_PLUGIN_ROOT}/server/bootstrap.py"]
    assert (PLUGIN / "server" / "bootstrap.py").exists()


def test_the_lock_fits_the_directory_file_limit_and_holds_fastmcp_3():
    lock = PLUGIN / "server" / "uv.lock"
    assert lock.stat().st_size < 256 * 1024, "the directory holds files over 256 KiB"
    packages = {p["name"]: p["version"] for p in tomllib.loads(lock.read_text())["package"]}
    assert packages["fastmcp"].startswith("3."), packages["fastmcp"]


def test_the_server_project_is_not_built_as_a_package():
    project = tomllib.loads((PLUGIN / "server" / "pyproject.toml").read_text())
    assert project["tool"]["uv"]["package"] is False


def test_the_server_does_not_ask_pypi_for_fastmcp_updates():
    """FastMCP's banner checks pypi.org for a newer release: an undeclared
    destination for a server whose egress is limited to _egress.py."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "FASTMCP_CHECK_FOR_UPDATES"}
    out = subprocess.run(
        [sys.executable, "-c",
         "import src.cli, fastmcp; print(fastmcp.settings.check_for_updates)"],
        capture_output=True, text=True, env=env, cwd=ROOT, check=True,
    )
    assert out.stdout.strip() == "off"
