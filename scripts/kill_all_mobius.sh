#!/usr/bin/env bash
# Force-kill all Mobius processes. Delegates to stop_all_mobius.sh (single source of truth).
# Use this or mstop — both do the same thing.
# Run from Mobius root: ./scripts/kill_all_mobius.sh  or  ./mstop

SCRIPT="${BASH_SOURCE[0]:-$0}"
while [[ -L "$SCRIPT" ]]; do
  TARGET="$(readlink "$SCRIPT")"
  [[ "$TARGET" == /* ]] && SCRIPT="$TARGET" || SCRIPT="$(dirname "$SCRIPT")/$TARGET"
done
ROOT="$(cd "$(dirname "$SCRIPT")/.." && pwd)"

MOBIUS_ROOT="$ROOT" exec bash "$ROOT/scripts/stop_all_mobius.sh"
