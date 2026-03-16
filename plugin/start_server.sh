#!/usr/bin/env bash
# Bootstrap script: ensures dependencies are installed, then starts the MCP server.
# Called by Claude Code via .mcp.json — works on any machine with Python 3.10+.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$DIR/server"
VENV="$SERVER/.venv"

# Create venv and install deps on first run (cached after that)
if [ ! -f "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" 2>/dev/null
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7"
fi

exec "$VENV/bin/python" "$SERVER/run_server.py"
