#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCRIPT_DIR="$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/ensure-web-venv.zsh"
ensure_web_venv || exit 1

VPY="$ROOT/.venv/bin/python3"

export IMG_TOOL_QUIET="${IMG_TOOL_QUIET:-1}"
export IMG_TOOL_HOST="${IMG_TOOL_HOST:-127.0.0.1}"
export IMG_TOOL_PORT="${IMG_TOOL_PORT:-5000}"

# For launchd mode, keep the process in foreground and let launchd manage restarts.
exec "$VPY" "$ROOT/web_app.py"
