#!/usr/bin/env bash
# Install the LIMES pre-push guard into this clone's git hooks (hooks are
# not versioned: rerun after every fresh clone). Refuses to overwrite a
# different existing pre-push hook.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hook="$(git rev-parse --git-path hooks)/pre-push"
src="$root/benchmarks/limes/tools/pre-push-guard.sh"
if [ -e "$hook" ] && ! cmp -s "$hook" "$src"; then
  echo "esiste già un hook pre-push diverso in $hook: integralo a mano" >&2
  exit 1
fi
cp "$src" "$hook" && chmod +x "$hook"
echo "guardia LIMES installata in $hook"
