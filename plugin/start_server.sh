#!/usr/bin/env bash
# Bootstrap script: ensures dependencies are installed, then starts the MCP server.
# Works in two modes:
#   1. GitHub install (Co-work): src/ and run_server.py are in ../../ relative to plugin/
#   2. ZIP install (Claude Code): server code is in ./server/
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect mode: if server/ subdir exists, use it (ZIP mode); otherwise go up to repo root (GitHub mode)
if [ -d "$DIR/server" ]; then
  SERVER="$DIR/server"
else
  SERVER="$(cd "$DIR/.." && pwd)"
fi

VENV="$SERVER/.venv"

# Create venv and install deps on first run (cached after that)
if [ ! -f "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" 2>/dev/null
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7"
fi

exec "$VENV/bin/python" "$SERVER/run_server.py"
