#!/usr/bin/env bash
# Bootstrap: starts the MCP server (stdio). Prefers `uv` when available
# (cross-platform, pins Python 3.12, no manual venv); falls back to a
# Python venv — the path that works in the Cowork sandbox, which does not
# provide `uv`. Venv lives in MCP_CACHE_DIR because the plugin dir may be
# read-only in Cowork.
#
# PATH-independent: GUI hosts (Claude Desktop, Cowork, Freebuff, …) spawn
# MCP servers with launchd's minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin),
# which hides Homebrew, ~/.local/bin and cargo installs. The usual install
# locations are therefore probed by absolute path, and a Python candidate
# is only accepted if it actually runs (a Python shipped by the Xcode CLT
# without an accepted licence exits with an error instead of a version).
# Set MCP_FORCE_VENV=1 to skip `uv` and exercise the venv path.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Rebuild a usable PATH for hosts that launch us with launchd's bare one.
for d in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.bun/bin" \
         /opt/homebrew/bin /usr/local/bin /opt/homebrew/sbin /usr/local/sbin; do
  if [ -d "$d" ]; then
    case ":$PATH:" in
      *":$d:"*) ;;
      *) PATH="$d:$PATH" ;;
    esac
  fi
done
export PATH

# Detect server location (plugin/server/ in the marketplace layout)
if [ -d "$DIR/server" ]; then
  SERVER="$DIR/server"
else
  SERVER="$(cd "$DIR/.." && pwd)"
fi

find_uv() {
  local candidate
  for candidate in "$(command -v uv 2>/dev/null || true)" \
                   /opt/homebrew/bin/uv /usr/local/bin/uv \
                   "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

# Preferred path: uv (handles Python 3.12 + deps without a manual venv)
UV=""
if [ "${MCP_FORCE_VENV:-0}" != "1" ]; then
  UV="$(find_uv || true)"
fi
if [ -n "$UV" ]; then
  exec "$UV" run --python 3.12 \
    --with "fastmcp>=2.0,<4" --with "httpx>=0.27" --with "beautifulsoup4>=4.12" \
    --with "lxml>=5.0" --with "fpdf2>=2.7" --with "python-docx>=1.0" --with "openpyxl>=3.1" \
    --with "cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'" \
    "$SERVER/run_server.py"
fi

# Fallback: Python + venv (the 2.6.1 path; works in the Cowork sandbox)
CACHE_DIR="${MCP_CACHE_DIR:-${HOME}/.cache/mcp-legal-it}"
VENV="$CACHE_DIR/venv"
mkdir -p "$CACHE_DIR"

find_python() {
  local name candidate
  for name in python3.12 python3.11 python3.10 python3.13 python3; do
    for candidate in "$(command -v "$name" 2>/dev/null || true)" \
                     "/opt/homebrew/bin/$name" "/usr/local/bin/$name" \
                     "$HOME/.local/bin/$name"; do
      # An unaccepted Xcode licence turns the CLT python3 into a shim that
      # only prints a licence error, so probe instead of trusting the path.
      if [ -n "$candidate" ] && [ -x "$candidate" ] \
         && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
  done
  return 1
}

PYTHON="$(find_python || true)"
if [ -z "$PYTHON" ]; then
  echo "ERROR: neither uv nor a working Python 3.10+ found. Install uv (https://astral.sh/uv) or Python 3.12." >&2
  exit 1
fi

# Reuse the cached venv only if it is genuinely usable: an old interpreter or
# a half-finished install (interrupted download, deps added in a later release)
# would otherwise make the server start and fail on its first import.
venv_is_usable() {
  [ -x "$VENV/bin/python" ] || return 1
  "$VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 || return 1
  "$VENV/bin/python" -c 'import fastmcp, httpx, bs4, lxml, fpdf, docx, openpyxl' >/dev/null 2>&1 || return 1
  return 0
}

if ! venv_is_usable; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check \
    "fastmcp>=2.0,<4" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7" "python-docx>=1.0" "openpyxl>=3.1" \
    "cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'"
fi

exec "$VENV/bin/python" "$SERVER/run_server.py"
