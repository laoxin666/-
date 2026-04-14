#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$ROOT/.web_app.pid"
LABEL="com.pixelforge.webapp"
TARGET_CMD="$ROOT/web_app.py"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true

collect_web_pids() {
  ps -axo pid=,args= | awk -v target="$TARGET_CMD" '
    index($0, target) > 0 { print $1 }
  '
}

stop_pid() {
  local pid="$1"
  [[ -z "$pid" ]] && return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  kill "$pid" 2>/dev/null || true
  for _ in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.2
  done
  kill -9 "$pid" 2>/dev/null || true
}

if [[ ! -f "$PIDFILE" ]]; then
  FOUND_PIDS=("${(@f)$(collect_web_pids)}")
  if [[ ${#FOUND_PIDS[@]} -gt 0 ]]; then
    for pid in "${FOUND_PIDS[@]}"; do
      stop_pid "$pid"
    done
  fi
  exit 0
fi

PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
  stop_pid "$PID"
fi
rm -f "$PIDFILE"

FOUND_PIDS=("${(@f)$(collect_web_pids)}")
if [[ ${#FOUND_PIDS[@]} -gt 0 ]]; then
  for pid in "${FOUND_PIDS[@]}"; do
    stop_pid "$pid"
  done
fi
