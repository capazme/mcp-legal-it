#!/usr/bin/env python3
"""Entry point for MCP server — supports stdio and SSE transports.

Transport is selected via MCP_TRANSPORT env var (default: stdio).
For SSE, MCP_HOST, MCP_PORT, and MCP_PATH_PREFIX control the server.

Path prefix is propagated to FastMCP via FASTMCP_SSE_PATH and
FASTMCP_MESSAGE_PATH env vars (native pydantic-settings support).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Derive FastMCP path settings from MCP_PATH_PREFIX before importing server
# (FastMCP reads env vars at Settings instantiation time)
prefix = os.environ.get("MCP_PATH_PREFIX", "").rstrip("/")
if prefix:
    os.environ.setdefault("FASTMCP_SSE_PATH", f"{prefix}/sse")
    os.environ.setdefault("FASTMCP_MESSAGE_PATH", f"{prefix}/messages/")

from src.server import mcp  # noqa: E402

transport = os.environ.get("MCP_TRANSPORT", "stdio")

if transport == "sse":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)
else:
    mcp.run(transport="stdio")
