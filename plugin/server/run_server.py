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

from src.cli import main  # noqa: E402

main([])
