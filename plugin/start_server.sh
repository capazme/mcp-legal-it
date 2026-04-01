#!/usr/bin/env bash
# Bootstrap script: ensures dependencies are installed, then starts the MCP server (stdio).
# Venv is created in MCP_CACHE_DIR (writable) — plugin dir may be read-only in Cowork.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect server location
if [ -d "$DIR/server" ]; then
  SERVER="$DIR/server"
else
  SERVER="$(cd "$DIR/.." && pwd)"
fi

# Use writable cache dir for venv (plugin dir is read-only in Cowork)
CACHE_DIR="${MCP_CACHE_DIR:-${HOME}/.cache/mcp-legal-it}"
VENV="$CACHE_DIR/venv"
mkdir -p "$CACHE_DIR"

# Create venv and install deps on first run (cached after that)
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.10+ not found. Install Python from python.org" >&2
  exit 1
fi

if [ ! -f "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7" "python-docx>=1.0"
fi

exec "$VENV/bin/python" "$SERVER/run_server.py"
