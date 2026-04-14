#!/bin/zsh
# 解压后可双击本文件启动（首次会自动装依赖，需已安装 Python 3）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 国内下载慢时，可去掉下一行开头的 # 改用镜像
# export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

if ! command -v python3 &>/dev/null; then
  osascript -e 'display alert "未找到 Python 3" message "请先从 python.org 安装 macOS 版 Python，再重新双击本文件。" as warning' 2>/dev/null || \
    echo "请先安装 Python 3：https://www.python.org/downloads/macos/"
  exit 1
fi

if [[ ! -d ".venv-share" ]]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  首次运行：正在安装依赖（只需一次，约 1～3 分钟）"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  python3 -m venv .venv-share
  source ".venv-share/bin/activate"
  pip install -U pip -q
  pip install -r requirements-web.txt
  echo "依赖已就绪。"
else
  source ".venv-share/bin/activate"
fi

export IMG_TOOL_HOST="0.0.0.0"
# 优先避开被占用的端口
export IMG_TOOL_PORT="5000"
for try_port in 5000 8080 8765; do
  if ! lsof -i ":${try_port}" -sTCP:LISTEN -Pn &>/dev/null; then
    export IMG_TOOL_PORT="${try_port}"
    break
  fi
done

clear 2>/dev/null || true
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  请在浏览器打开下面任意一个地址"
echo "  （需与你连同一 Wi‑Fi；本次将后台启动，可关闭终端）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  本机预览: http://127.0.0.1:${IMG_TOOL_PORT}/"
echo ""
LAN_IPS=()
while read -r ip; do
  [[ -n "$ip" ]] && LAN_IPS+=("$ip")
done < <(ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" { print $2 }' | sort -u)
if [[ ${#LAN_IPS[@]} -gt 0 ]]; then
  for ip in "${LAN_IPS[@]}"; do
    echo "  局域网访问 → http://${ip}:${IMG_TOOL_PORT}/"
  done
else
  echo "  （未自动检测到局域网 IP，请在「系统设置 → 网络」查看本机 IP）"
  echo "  局域网访问 → http://你的IP:${IMG_TOOL_PORT}/"
fi
echo ""
echo "  防火墙若拦截，请在「系统设置 → 网络 → 防火墙」中允许 Python。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PIDFILE="$SCRIPT_DIR/.web_app.pid"
LOGFILE="$SCRIPT_DIR/web_app.log"
TARGET_CMD="$SCRIPT_DIR/web_app.py"
is_service_ready() {
  python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:${IMG_TOOL_PORT}/health", timeout=1.5)
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
      echo "检测到服务已在运行（PID $OLD_PID），无需重复启动。"
      echo "停止服务：双击 stop_web.command"
      ( sleep 1 && open "http://127.0.0.1:${IMG_TOOL_PORT}/" ) &
      echo "按回车关闭窗口…"
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
    echo "检测到服务已在运行（PID ${FOUND_PIDS[1]}），无需重复启动。"
    echo "停止服务：双击 stop_web.command"
    ( sleep 1 && open "http://127.0.0.1:${IMG_TOOL_PORT}/" ) &
    echo "按回车关闭窗口…"
    read -r
    exit 0
  fi
  echo "检测到残留进程但服务无响应，清理后重启…"
  for pid in "${FOUND_PIDS[@]}"; do
    stop_pid "$pid"
  done
fi

nohup python3 "web_app.py" >>"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"

READY=0
for _ in {1..15}; do
  if is_service_ready; then
    READY=1
    break
  fi
  sleep 0.5
done

if [[ "$READY" == "1" ]]; then
  echo "已在后台启动（PID $(cat "$PIDFILE")）。"
else
  echo "后台已启动，但服务尚未就绪，请稍后重试。"
fi
echo "日志文件：$LOGFILE"
echo "停止服务：双击 stop_web.command"
( sleep 1 && open "http://127.0.0.1:${IMG_TOOL_PORT}/" ) &
echo "按回车关闭窗口…"
read -r
