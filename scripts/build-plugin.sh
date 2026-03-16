#!/usr/bin/env bash
# Build Claude Code Plugin ZIP for marketplace distribution
# Usage: ./scripts/build-plugin.sh [version]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$ROOT_DIR/dist/plugin-build"
DIST_DIR="$ROOT_DIR/dist"

VERSION="${1:-$(python3 -c "import json; print(json.load(open('$ROOT_DIR/plugin/.claude-plugin/plugin.json'))['version'])")}"

echo "==> Building Claude Code Plugin v${VERSION}"

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Copy plugin structure
cp -r "$ROOT_DIR/plugin/.claude-plugin" "$BUILD_DIR/.claude-plugin"
cp -r "$ROOT_DIR/plugin/skills" "$BUILD_DIR/skills"
cp -r "$ROOT_DIR/plugin/agents" "$BUILD_DIR/agents"
cp -r "$ROOT_DIR/plugin/commands" "$BUILD_DIR/commands"
cp -r "$ROOT_DIR/plugin/hooks" "$BUILD_DIR/hooks"
cp "$ROOT_DIR/plugin/settings.json" "$BUILD_DIR/"
cp "$ROOT_DIR/plugin/start_server.sh" "$BUILD_DIR/"
chmod +x "$BUILD_DIR/start_server.sh"

# .mcp.json is now portable (uses ${CLAUDE_PLUGIN_ROOT})
cp "$ROOT_DIR/plugin/.mcp.json" "$BUILD_DIR/.mcp.json"

# Server code is already in plugin/server/ — copy it
cp -r "$ROOT_DIR/plugin/server" "$BUILD_DIR/server"

# Clean __pycache__
find "$BUILD_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Update version in plugin.json if provided
if [ -n "${1:-}" ]; then
  python3 -c "
import json
with open('$BUILD_DIR/.claude-plugin/plugin.json', 'r+') as f:
    m = json.load(f)
    m['version'] = '$VERSION'
    f.seek(0)
    json.dump(m, f, indent=2, ensure_ascii=False)
    f.truncate()
"
fi

# Build ZIP
OUTPUT="$DIST_DIR/legal-it-plugin-${VERSION}.zip"
(cd "$BUILD_DIR" && zip -r "$OUTPUT" . -x "*.pyc" "__pycache__/*")

# Cleanup build dir
rm -rf "$BUILD_DIR"

echo "==> Built: $OUTPUT"
echo "    Size: $(du -h "$OUTPUT" | cut -f1)"
