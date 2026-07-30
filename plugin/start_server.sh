#!/usr/bin/env bash
# Bootstrap: starts the MCP server (stdio). Prefers `uv` when available
# (cross-platform, pins Python 3.12, no manual venv); falls back to a
# system-Python venv — the path that works in the Cowork sandbox, which
# does not provide `uv`. Venv lives in MCP_CACHE_DIR because the plugin
# dir may be read-only in Cowork.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect server location (plugin/server/ in the marketplace layout)
if [ -d "$DIR/server" ]; then
  SERVER="$DIR/server"
else
  SERVER="$(cd "$DIR/.." && pwd)"
fi

# Preferred path: uv (handles Python 3.12 + deps without a manual venv)
if command -v uv &>/dev/null; then
  exec uv run --python 3.12 \
    --with "fastmcp>=2.0,<4" --with "httpx>=0.27" --with "beautifulsoup4>=4.12" \
    --with "lxml>=5.0" --with "fpdf2>=2.7" --with "python-docx>=1.0" --with "openpyxl>=3.1" \
    "$SERVER/run_server.py"
fi

# Fallback: system Python + venv (the 2.6.1 path; works in the Cowork sandbox)
CACHE_DIR="${MCP_CACHE_DIR:-${HOME}/.cache/mcp-legal-it}"
VENV="$CACHE_DIR/venv"
mkdir -p "$CACHE_DIR"

PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "ERROR: neither uv nor Python 3.10+ found. Install uv (https://astral.sh/uv) or Python 3.12." >&2
  exit 1
fi

if [ ! -f "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0,<4" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7" "python-docx>=1.0" "openpyxl>=3.1"
fi

exec "$VENV/bin/python" "$SERVER/run_server.py"
