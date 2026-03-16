#!/usr/bin/env bash
# Ensures the legal-it MCP server is configured in claude_desktop_config.json.
# Called by SessionStart hook. Idempotent — skips if already present.
set -euo pipefail

CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# Only macOS (Claude Desktop)
[ "$(uname)" = "Darwin" ] || exit 0
[ -d "$HOME/Library/Application Support/Claude" ] || exit 0

# Find the plugin's server location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -d "$PLUGIN_DIR/server" ]; then
  SERVER_DIR="$PLUGIN_DIR/server"
else
  SERVER_DIR="$(cd "$PLUGIN_DIR/.." && pwd)"
fi

VENV="$SERVER_DIR/.venv"

# Ensure venv exists
if [ ! -f "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" 2>/dev/null
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0.0" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7"
fi

PYTHON_PATH="$VENV/bin/python"
SERVER_SCRIPT="$SERVER_DIR/run_server.py"

# Create config file if missing
if [ ! -f "$CONFIG" ]; then
  echo '{"mcpServers":{}}' > "$CONFIG"
fi

# Check if legal-it is already configured (using python for safe JSON handling)
"$PYTHON_PATH" -c "
import json, sys

config_path = '$CONFIG'
python_path = '$PYTHON_PATH'
server_script = '$SERVER_SCRIPT'

with open(config_path) as f:
    config = json.load(f)

servers = config.setdefault('mcpServers', {})

# Already present and pointing to valid python? Skip.
if 'legal-it' in servers:
    existing_cmd = servers['legal-it'].get('command', '')
    if existing_cmd == python_path:
        sys.exit(0)

# Add or update the server entry
servers['legal-it'] = {
    'command': python_path,
    'args': [server_script],
    'env': {
        'MCP_CACHE_DIR': '$HOME/.cache/mcp-legal-it'
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('legal-it server added to claude_desktop_config.json', file=sys.stderr)
print('Restart Claude Desktop to activate the MCP server.', file=sys.stderr)
"
