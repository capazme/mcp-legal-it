#!/usr/bin/env bash
# Build both Desktop Extension and Claude Code Plugin
# Usage: ./scripts/build-all.sh [version]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-}"

echo "========================================="
echo "  Legal IT — Build All Distributions"
echo "========================================="
echo ""

"$SCRIPT_DIR/build-dxt.sh" $VERSION
echo ""
"$SCRIPT_DIR/build-plugin.sh" $VERSION

echo ""
echo "========================================="
echo "  Build complete. Artifacts in dist/"
echo "========================================="
ls -lh "$(dirname "$SCRIPT_DIR")/dist/"*.{mcpb,zip} 2>/dev/null
