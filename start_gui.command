#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -d ".venv" ]]; then
  source ".venv/bin/activate"
fi

python3 "image_tool_gui.py"
