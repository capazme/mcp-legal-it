"""Console entry point and server version."""
import re
import shutil
from unittest.mock import patch

import pytest

from src import cli


def test_package_version_matches_pyproject():
    text = open("pyproject.toml", encoding="utf-8").read()
    expected = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    assert cli.package_version() == expected


def test_main_defaults_to_stdio(monkeypatch):
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    with patch("src.cli.mcp.run") as run:
        cli.main([])
    run.assert_called_once_with(transport="stdio")


def test_main_http_reads_env(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8123")
    monkeypatch.setenv("MCP_PATH", "/mcp")
    with patch("src.cli.mcp.run") as run:
        cli.main([])
    run.assert_called_once_with(transport="http", host="127.0.0.1", port=8123, path="/mcp")


def test_server_declares_version():
    from src.server import mcp
    assert mcp.version == cli.package_version()


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
@pytest.mark.asyncio
async def test_uv_run_entry_point_handshake():
    """The exact way librelex-core starts the server: uv run --project . mcp-legal-it."""
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport("uv", ["run", "--project", ".", "mcp-legal-it"],
                               env={"LEGAL_PROFILE": "normativa", "MCP_TRANSPORT": "stdio"})
    async with Client(transport, timeout=120) as client:
        info = client.initialize_result.serverInfo
        assert info.version == cli.package_version()
        names = {t.name for t in await client.list_tools()}
        assert {"cite_law", "verifica_citazioni"} <= names
