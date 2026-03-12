#!/usr/bin/env bash
# Build Desktop Extension (.mcpb) for Claude Desktop
# Usage: ./scripts/build-dxt.sh [version]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$ROOT_DIR/dist/dxt-build"
DIST_DIR="$ROOT_DIR/dist"

VERSION="${1:-$(python3 -c "import json; print(json.load(open('$ROOT_DIR/dxt/manifest.json'))['version'])")}"

echo "==> Building Desktop Extension v${VERSION}"

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Copy manifest
cp "$ROOT_DIR/dxt/manifest.json" "$BUILD_DIR/"

# Copy .mcpbignore
cp "$ROOT_DIR/dxt/.mcpbignore" "$BUILD_DIR/"

# Copy server source and bootstrap script
cp "$ROOT_DIR/pyproject.toml" "$BUILD_DIR/"
cp "$ROOT_DIR/run_server.py" "$BUILD_DIR/"
cp "$ROOT_DIR/dxt/start_server.sh" "$BUILD_DIR/"
chmod +x "$BUILD_DIR/start_server.sh"
cp -r "$ROOT_DIR/src" "$BUILD_DIR/src"

# Clean __pycache__ from copied source
find "$BUILD_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Update version in manifest if provided
if [ -n "${1:-}" ]; then
  python3 -c "
import json
with open('$BUILD_DIR/manifest.json', 'r+') as f:
    m = json.load(f)
    m['version'] = '$VERSION'
    f.seek(0)
    json.dump(m, f, indent=2, ensure_ascii=False)
    f.truncate()
"
fi

# Build .mcpb
OUTPUT="$DIST_DIR/legal-it-${VERSION}.mcpb"
if command -v mcpb &>/dev/null; then
  mcpb pack "$BUILD_DIR" "$OUTPUT"
else
  # Fallback: create ZIP manually (mcpb is just a ZIP with manifest.json)
  echo "==> mcpb CLI not found, creating ZIP manually"
  (cd "$BUILD_DIR" && zip -r "$OUTPUT" . -x "*.pyc" "__pycache__/*")
fi

# Cleanup build dir
rm -rf "$BUILD_DIR"

echo "==> Built: $OUTPUT"
echo "    Size: $(du -h "$OUTPUT" | cut -f1)"
