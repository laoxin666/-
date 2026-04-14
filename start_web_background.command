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
TARGET_CMD="$SCRIPT_DIR/web_app.py"

is_service_ready() {
  "$VPY" - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=1.5)
PY
}

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

if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    if is_service_ready; then
      echo "服务已在运行中（PID $OLD_PID）。"
      echo "浏览器打开：http://127.0.0.1:5000/"
      echo "若要重启，请先双击 stop_web.command"
      echo "按回车关闭本窗口…"
      read -r
      exit 0
    fi
    echo "检测到旧进程无响应，尝试重启服务…"
    stop_pid "$OLD_PID"
  fi
  rm -f "$PIDFILE"
fi

FOUND_PIDS=("${(@f)$(collect_web_pids)}")
if [[ ${#FOUND_PIDS[@]} -gt 0 ]]; then
  if is_service_ready; then
    echo "${FOUND_PIDS[1]}" >"$PIDFILE"
    echo "检测到服务已在运行中（PID ${FOUND_PIDS[1]}）。"
    echo "浏览器打开：http://127.0.0.1:5000/"
    echo "若要重启，请先双击 stop_web.command"
    echo "按回车关闭本窗口…"
    read -r
    exit 0
  fi
  echo "检测到残留进程但服务无响应，清理后重启…"
  for pid in "${FOUND_PIDS[@]}"; do
    stop_pid "$pid"
  done
fi

nohup "$VPY" "$SCRIPT_DIR/web_app.py" >>"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"

READY=0
for _ in {1..15}; do
  if is_service_ready; then
    READY=1
    break
  fi
  sleep 0.5
done

echo ""
if [[ "$READY" == "1" ]]; then
  echo "已在后台启动（关掉终端不影响）。"
else
  echo "后台已启动，但服务尚未就绪，请稍后重试。"
fi
echo "  浏览器打开：http://127.0.0.1:5000/"
echo "  日志文件：$LOGFILE"
echo "  进程号：$(cat "$PIDFILE")"
echo ""
echo "停止服务：双击同目录下的 stop_web.command"
echo ""
echo "按回车关闭本窗口…"
read -r
