#!/usr/bin/env python3
"""Entry point for Claude Desktop / Browser stdio transport.

Claude Desktop cannot set a working directory, so this script ensures
the project root is on sys.path regardless of cwd.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.server import mcp  # noqa: E402

mcp.run()
