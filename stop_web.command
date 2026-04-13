#!/bin/zsh
# 结束由 start_web_background.command 启动的后台服务
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$SCRIPT_DIR/.web_app.pid"

if [[ ! -f "$PIDFILE" ]]; then
  echo "未找到后台进程记录（.web_app.pid）。可能未启动过后台模式，或已停止。"
  echo "按回车关闭…"
  read -r
  exit 0
fi

PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
if [[ -z "$PID" ]]; then
  rm -f "$PIDFILE"
  echo "PID 文件为空，已清理。"
  echo "按回车关闭…"
  read -r
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "已停止后台服务（PID $PID）。"
else
  echo "进程 $PID 已不存在，已清理记录。"
fi
rm -f "$PIDFILE"
echo "按回车关闭…"
read -r
