#!/usr/bin/env bash
# Runs citation-gate.py with the first Python that actually works, so the
# Stop hook never fails a turn on a machine without one. On Windows `python3`
# usually resolves to the Microsoft Store alias, which prints an error and
# exits 9009 instead of running: probe each candidate before trusting it.
# Fallback: the uv that the MCP server needs anyway. Neither available: the
# gate stays silent (exit 0); it is advisory, the lawyer's review is not.
HERE="$(cd "$(dirname "$0")" && pwd)"
GATE="$HERE/citation-gate.py"

for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 \
     && "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' </dev/null >/dev/null 2>&1; then
    exec "$py" "$GATE"
  fi
done

for uv in "$(command -v uv 2>/dev/null || true)" "$HOME/.local/bin/uv" \
          /opt/homebrew/bin/uv /usr/local/bin/uv; do
  if [ -n "$uv" ] && [ -x "$uv" ]; then
    exec "$uv" run --no-project --python 3.12 --quiet "$GATE"
  fi
done

exit 0
