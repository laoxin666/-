#!/bin/zsh
# 后台运行：可关掉终端，服务仍在本机继续；停止请双击 stop_web.command
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/scripts/ensure-web-venv.zsh"
ensure_web_venv || {
  echo ""
  echo "按回车关闭窗口…"
  read -r
  exit 1
}

VPY="$SCRIPT_DIR/.venv/bin/python3"
PIDFILE="$SCRIPT_DIR/.web_app.pid"
LOGFILE="$SCRIPT_DIR/web_app.log"

if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "服务已在运行中（PID $OLD_PID）。"
    echo "浏览器打开：http://127.0.0.1:5000/"
    echo "若要重启，请先双击 stop_web.command"
    echo "按回车关闭本窗口…"
    read -r
    exit 0
  fi
  rm -f "$PIDFILE"
fi

nohup "$VPY" "$SCRIPT_DIR/web_app.py" >>"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"

echo ""
echo "已在后台启动（关掉终端不影响）。"
echo "  浏览器打开：http://127.0.0.1:5000/"
echo "  日志文件：$LOGFILE"
echo "  进程号：$(cat "$PIDFILE")"
echo ""
echo "停止服务：双击同目录下的 stop_web.command"
echo ""
echo "按回车关闭本窗口…"
read -r
