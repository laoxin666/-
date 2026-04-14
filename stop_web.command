#!/bin/zsh
# 结束由 start_web_background.command 启动的后台服务
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$SCRIPT_DIR/.web_app.pid"
TARGET_CMD="$SCRIPT_DIR/web_app.py"

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
  if [[ ${#FOUND_PIDS[@]} -eq 0 ]]; then
    echo "未找到后台进程记录（.web_app.pid），也未发现正在运行的服务。"
    echo "按回车关闭…"
    read -r
    exit 0
  fi
  for pid in "${FOUND_PIDS[@]}"; do
    stop_pid "$pid"
  done
  echo "已停止后台服务（通过进程扫描）。"
  echo "按回车关闭…"
  read -r
  exit 0
fi

PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
if [[ -z "$PID" ]]; then
  rm -f "$PIDFILE"
  FOUND_PIDS=("${(@f)$(collect_web_pids)}")
  if [[ ${#FOUND_PIDS[@]} -gt 0 ]]; then
    for pid in "${FOUND_PIDS[@]}"; do
      stop_pid "$pid"
    done
    echo "PID 文件为空，已通过进程扫描停止服务。"
  else
    echo "PID 文件为空，已清理。"
  fi
  echo "按回车关闭…"
  read -r
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  stop_pid "$PID"
  echo "已停止后台服务（PID $PID）。"
else
  FOUND_PIDS=("${(@f)$(collect_web_pids)}")
  if [[ ${#FOUND_PIDS[@]} -gt 0 ]]; then
    for pid in "${FOUND_PIDS[@]}"; do
      stop_pid "$pid"
    done
    echo "PID $PID 无效，已通过进程扫描停止服务。"
  else
    echo "进程 $PID 已不存在，已清理记录。"
  fi
fi
rm -f "$PIDFILE"
echo "按回车关闭…"
read -r
