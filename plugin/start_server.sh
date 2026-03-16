#!/usr/bin/env bash
# Bootstrap script: ensures dependencies are installed, then starts the MCP server.
# Modes:
#   --daemon: start SSE server in background on localhost:8000 (used by SessionStart hook)
#   (default): stdio transport (used by Claude Code CLI / DXT)
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect server location
if [ -d "$DIR/server" ]; then
  SERVER="$DIR/server"
else
  SERVER="$(cd "$DIR/.." && pwd)"
fi

VENV="$SERVER/.venv"
PORT="${MCP_PORT:-8000}"

# Create venv and install deps on first run (cached after that)
if [ ! -f "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" 2>/dev/null
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7"
fi

# Daemon mode: start SSE server in background if not already running
if [ "${1:-}" = "--daemon" ]; then
  # Already running? Skip.
  if curl -sf "http://localhost:$PORT/sse" -o /dev/null 2>/dev/null; then
    exit 0
  fi
  MCP_TRANSPORT=sse MCP_PORT="$PORT" nohup "$VENV/bin/python" "$SERVER/run_server.py" \
    > /tmp/mcp-legal-it-sse.log 2>&1 &
  # Wait up to 15s for server to be ready
  for _ in $(seq 1 15); do
    sleep 1
    if curl -sf "http://localhost:$PORT/sse" -o /dev/null 2>/dev/null; then
      exit 0
    fi
  done
  exit 1
fi

# Default: stdio
exec "$VENV/bin/python" "$SERVER/run_server.py"
