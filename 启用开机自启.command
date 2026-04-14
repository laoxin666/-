#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${AGENT_DIR}/com.pixelforge.webapp.plist"
LABEL="com.pixelforge.webapp"
SCRIPT_DIR="$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/ensure-web-venv.zsh"
ensure_web_venv || {
  echo ""
  echo "按回车关闭窗口…"
  read -r
  exit 1
}
VPY="$ROOT/.venv/bin/python3"
PIDFILE="$ROOT/.web_app.pid"
LOGFILE="$ROOT/web_app.log"
LAUNCH_LOG_DIR="${HOME}/Library/Logs"
LAUNCH_LOG_FILE="${LAUNCH_LOG_DIR}/pixelforge-web.log"

mkdir -p "$AGENT_DIR"
mkdir -p "$LAUNCH_LOG_DIR"

cat >"$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${VPY}</string>
    <string>${ROOT}/web_app.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>IMG_TOOL_QUIET</key>
    <string>1</string>
    <key>IMG_TOOL_HOST</key>
    <string>127.0.0.1</string>
    <key>IMG_TOOL_PORT</key>
    <string>5000</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${LAUNCH_LOG_FILE}</string>
  <key>StandardErrorPath</key>
  <string>${LAUNCH_LOG_FILE}</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
if [[ -x "$ROOT/scripts/stop-web-daemon.zsh" ]]; then
  "$ROOT/scripts/stop-web-daemon.zsh" >/dev/null 2>&1 || true
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/${LABEL}" || true

READY=0
for _ in {1..15}; do
  if python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=1)
PY
  then
    READY=1
    break
  fi
  sleep 0.5
done

if [[ "$READY" != "1" ]]; then
  # Fallback: start a local background process right now, so users can use it immediately.
  nohup "$VPY" "$ROOT/web_app.py" >>"$LOGFILE" 2>&1 &
  echo $! >"$PIDFILE"
  for _ in {1..15}; do
    if python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=1)
PY
    then
      READY=2
      break
    fi
    sleep 0.5
  done
fi

echo ""
if [[ "$READY" == "1" ]]; then
  echo "已启用开机自启，服务已启动。"
elif [[ "$READY" == "2" ]]; then
  echo "已启用开机自启；launchd 暂未就绪，已回退为后台启动。"
else
  echo "已启用开机自启，但服务尚未就绪。可稍后访问或查看日志：${LAUNCH_LOG_FILE}"
fi
echo "服务地址：http://127.0.0.1:5000/"
echo "关闭自启：双击「关闭开机自启.command」"
echo ""
echo "按回车关闭窗口…"
read -r
