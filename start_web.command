#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/scripts/ensure-web-venv.zsh"
ensure_web_venv || {
  echo "按回车关闭窗口…"
  read -r
  exit 1
}

VPY="$SCRIPT_DIR/.venv/bin/python3"

echo ""
echo "服务启动后请在浏览器打开：http://127.0.0.1:5000/"
echo "（不要关本窗口；关掉即停止服务）"
echo ""

exec "$VPY" "$SCRIPT_DIR/web_app.py"
