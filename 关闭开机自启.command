#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${AGENT_DIR}/com.pixelforge.webapp.plist"
LABEL="com.pixelforge.webapp"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

if [[ -x "$ROOT/scripts/stop-web-daemon.zsh" ]]; then
  "$ROOT/scripts/stop-web-daemon.zsh" || true
fi

echo ""
echo "已关闭开机自启，并停止后台服务。"
echo ""
echo "按回车关闭窗口…"
read -r
