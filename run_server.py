#!/usr/bin/env python3
"""Entry point for MCP server — supports stdio and SSE transports.

Transport is selected via MCP_TRANSPORT env var (default: stdio).
For SSE, MCP_HOST and MCP_PORT control the bind address.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.server import mcp  # noqa: E402

transport = os.environ.get("MCP_TRANSPORT", "stdio")

if transport == "sse":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)
else:
    mcp.run(transport="stdio")
