#!/usr/bin/env bash
# Inspect the REAL Google Tag Manager container server side (no ad-blocker in the way).
# Thin wrapper kept for the command documented in SKILL.md: the analysis lives in
# inspect_container.py (standard library only), which parses the container as data
# and reports pixels, IDs, user data and consent conditions tag by tag.
#
# Usage:  bash inspect_container.sh GTM-XXXXXXX [GTM-YYYYYYY ...]
#         bash inspect_container.sh G-XXXXXXXXXX      # also a direct GA4/Ads Google tag
#         bash inspect_container.sh --json GTM-XXXXXXX
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
  echo "Serve python3 (lo stesso usato dal plugin per il gate delle citazioni)." >&2
  exit 1
fi
exec python3 "$(cd "$(dirname "$0")" && pwd)/inspect_container.py" "$@"
