#!/usr/bin/env bash
# Bootstrap script: ensures dependencies are installed, then starts the MCP server.
# Modes:
#   --daemon: start HTTPS SSE server in background on localhost:8000 (used by SessionStart hook)
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
CERT_DIR="${HOME}/.cache/mcp-legal-it/ssl"

# Create venv and install deps on first run (cached after that)
if [ ! -f "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" 2>/dev/null
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7"
fi

# Generate self-signed cert for localhost if not present
ensure_ssl_cert() {
  if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
    return 0
  fi
  mkdir -p "$CERT_DIR"
  # Use openssl CLI — available on macOS and Linux, no Python deps needed
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
    -days 3650 -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    2>/dev/null
}

# Daemon mode: start HTTPS SSE server in background if not already running
if [ "${1:-}" = "--daemon" ]; then
  # Already running? Skip.
  if curl -skf "https://localhost:$PORT/sse" -o /dev/null 2>/dev/null; then
    exit 0
  fi
  ensure_ssl_cert
  MCP_TRANSPORT=sse MCP_PORT="$PORT" MCP_SSL_CERT="$CERT_DIR/cert.pem" MCP_SSL_KEY="$CERT_DIR/key.pem" \
    nohup "$VENV/bin/python" "$SERVER/run_server.py" > /tmp/mcp-legal-it-sse.log 2>&1 &
  # Wait up to 15s for server to be ready
  for _ in $(seq 1 15); do
    sleep 1
    if curl -skf "https://localhost:$PORT/sse" -o /dev/null 2>/dev/null; then
      exit 0
    fi
  done
  exit 1
fi

# Default: stdio
exec "$VENV/bin/python" "$SERVER/run_server.py"
