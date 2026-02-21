#!/usr/bin/env bash
# Stop/kill all Mobius processes and stragglers. Single source of truth.
# Called by mstop and by the master landing server (POST /api/stop-all).
# Use kill -9 throughout so nothing hangs (foolproof).
# Usage: run from repo root, or set MOBIUS_ROOT to repo root.

set -e
if [[ -n "$MOBIUS_ROOT" ]]; then
  ROOT="$MOBIUS_ROOT"
else
  SCRIPT="${BASH_SOURCE[0]:-$0}"
  while [[ -L "$SCRIPT" ]]; do
    TARGET="$(readlink "$SCRIPT")"
    [[ "$TARGET" == /* ]] && SCRIPT="$TARGET" || SCRIPT="$(dirname "$SCRIPT")/$TARGET"
  done
  ROOT="$(cd "$(dirname "$SCRIPT")/.." && pwd)"
fi
PIDFILE="$ROOT/.mobius_start_all.pids"
if [[ -n "$KEEP_LANDING" ]]; then
  MOBIUS_PORTS="5001 8000 8001 5173 6500 8002 8010 8020 8030"
else
  MOBIUS_PORTS="5001 8000 8001 5173 6500 3999 8002 8010 8020 8030"
fi

_log() { echo "[stop_all] $*"; }

# Kill process and all descendants with SIGKILL (no graceful shutdown — foolproof)
_kill_tree_9() {
  local pid=$1
  [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null && return
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    _kill_tree_9 "$child"
  done
  kill -9 "$pid" 2>/dev/null || true
}

# 1) Kill PIDs from mstart's PID file (and their process trees)
if [[ -f "$PIDFILE" ]]; then
  _log "Killing processes from PID file ..."
  landing_lines=""
  while read -r pid name; do
    [[ -z "$pid" ]] || [[ ! "$pid" =~ ^[0-9]+$ ]] && continue
    if [[ -n "$KEEP_LANDING" ]] && [[ "$name" == "mobius-landing" ]]; then
      landing_lines="${landing_lines}${pid} ${name}"$'\n'
      continue
    fi
    if kill -0 "$pid" 2>/dev/null; then
      _kill_tree_9 "$pid"
      _log "  Stopped $name (PID $pid)"
    fi
  done < "$PIDFILE"
  if [[ -n "$KEEP_LANDING" ]] && [[ -n "$landing_lines" ]]; then
    printf "%s" "$landing_lines" > "$PIDFILE"
  else
    rm -f "$PIDFILE"
  fi
else
  _log "No PID file (mstart may not have been run)."
fi

sleep 1

# 2) Kill anything bound to Mobius ports (SIGKILL so it always goes away)
for port in $MOBIUS_PORTS; do
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti ":$port" 2>/dev/null) || true
    for p in $pids; do
      [[ -z "$p" ]] && continue
      if kill -0 "$p" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
        _log "  Killed process on port $port (PID $p)"
      fi
    done
  fi
done

# 3) Kill workers and servers by pattern — only when cmdline contains ROOT (avoid killing unrelated processes)
if command -v pgrep >/dev/null 2>&1 && command -v ps >/dev/null 2>&1; then
  patterns="app\.worker app\.embedding_worker app\.main:app uvicorn vite mchatc mchatcw mragb mragw mrage server\.py landing_server"
  for pattern in $patterns; do
    pgrep -f "$pattern" 2>/dev/null | while read -r p; do
      [[ -z "$p" ]] && continue
      if ! kill -0 "$p" 2>/dev/null; then continue; fi
      cmd=$(ps -p "$p" -o command= 2>/dev/null) || true
      [[ -z "$cmd" ]] && continue
      if echo "$cmd" | grep -q "$ROOT"; then
        if [[ -n "$KEEP_LANDING" ]] && echo "$cmd" | grep -q "landing_server"; then
          continue
        fi
        kill -9 "$p" 2>/dev/null || true
        _log "  Killed straggler (PID $p)"
      fi
    done
  done
  # npm run dev (only under ROOT)
  pgrep -f "npm.*run.*dev\|node.*vite" 2>/dev/null | while read -r p; do
    [[ -z "$p" ]] && continue
    if ! kill -0 "$p" 2>/dev/null; then continue; fi
    cmd=$(ps -p "$p" -o command= 2>/dev/null) || true
    if echo "$cmd" | grep -q "$ROOT"; then
      kill -9 "$p" 2>/dev/null || true
      _log "  Killed npm/vite dev (PID $p)"
    fi
  done
fi

# 4) Kill Python processes using Postgres (orphaned Mobius DB clients)
if command -v lsof >/dev/null 2>&1 && command -v awk >/dev/null 2>&1; then
  lsof -i :5432 2>/dev/null | awk '$1=="Python" {print $2}' | sort -u | while read -r p; do
    [[ -z "$p" ]] || [[ ! "$p" =~ ^[0-9]+$ ]] && continue
    if kill -0 "$p" 2>/dev/null; then
      kill -9 "$p" 2>/dev/null || true
      _log "  Killed Postgres client (PID $p)"
    fi
  done
fi

# 5) Final pass: any process still on our ports gets SIGKILL
sleep 2
for port in $MOBIUS_PORTS; do
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti ":$port" 2>/dev/null) || true
    for p in $pids; do
      [[ -z "$p" ]] && continue
      if kill -0 "$p" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
        _log "  Force-killed on port $port (PID $p)"
      fi
    done
  fi
done

_log "Done. Check ports: lsof -i :8000 -i :8001 -i :5173 2>/dev/null || true"
