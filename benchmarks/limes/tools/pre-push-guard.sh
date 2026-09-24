#!/usr/bin/env bash
# LIMES guard (local, not versioned): refuse any push whose content includes
# the private item bank. The repository is public; the private set's
# answers must never reach GitHub (contamination of future model training
# data). Installed on 2026-09-23 for feature/limes-wave-1. To publish the
# benchmark, first decide where the private bank lives (DESIGN §8.5).
set -euo pipefail
PRIVATE="benchmarks/limes/bank/private"
zero=0000000000000000000000000000000000000000
status=0
while read -r local_ref local_sha remote_ref remote_sha; do
  [ "$local_sha" = "$zero" ] && continue          # deletion: nothing leaves
  # 1) the pushed tree itself (branches AND tags, e.g. limes-wave-0)
  if [ -n "$(git ls-tree -r --name-only "$local_sha" -- "$PRIVATE" 2>/dev/null)" ]; then
    echo "pre-push LIMES: $local_ref contiene $PRIVATE — push rifiutato." >&2
    status=1; continue
  fi
  # 2) any commit in the pushed range that ever touched it (history leak)
  if [ "$remote_sha" = "$zero" ]; then range="$local_sha --not --remotes"; else range="$remote_sha..$local_sha"; fi
  if [ -n "$(git rev-list $range -- "$PRIVATE" 2>/dev/null | head -1)" ]; then
    echo "pre-push LIMES: la storia di $local_ref tocca $PRIVATE — push rifiutato." >&2
    status=1
  fi
done
exit $status
