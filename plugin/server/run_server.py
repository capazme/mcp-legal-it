#!/usr/bin/env python3
"""Entry point for MCP server — supports stdio, SSE, and Streamable HTTP transports.

Transport is selected via MCP_TRANSPORT env var (default: stdio).
For HTTP/SSE, MCP_HOST and MCP_PORT control the server.

Transport options:
  stdio  — local subprocess (Claude Desktop/Code, default)
  http   — Streamable HTTP (ChatGPT, Manus, any MCP client)
  sse    — legacy SSE (deprecated, kept for backwards compatibility)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.server import mcp  # noqa: E402

transport = os.environ.get("MCP_TRANSPORT", "stdio")
host = os.environ.get("MCP_HOST", "0.0.0.0")
port = int(os.environ.get("MCP_PORT", "8000"))
path = os.environ.get("MCP_PATH", "/mcp")

if transport == "http":
    mcp.run(transport="http", host=host, port=port, path=path)
elif transport == "sse":
    mcp.run(transport="sse", host=host, port=port)
else:
    mcp.run(transport="stdio")
