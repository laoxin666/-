#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -d ".venv" ]]; then
  source ".venv/bin/activate"
fi

export IMG_TOOL_HOST="${IMG_TOOL_HOST:-0.0.0.0}"
export IMG_TOOL_PORT="${IMG_TOOL_PORT:-5000}"

echo "=========================================="
echo "  局域网分享模式（他人可访问本机处理服务）"
echo "=========================================="
echo ""
echo "监听: ${IMG_TOOL_HOST}:${IMG_TOOL_PORT}"
echo ""
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [[ -z "$LAN_IP" ]]; then
  LAN_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [[ -n "$LAN_IP" ]]; then
  echo "请让同事在浏览器打开:"
  echo "  http://${LAN_IP}:${IMG_TOOL_PORT}/"
else
  echo "未检测到常见网卡 IP，请在「系统设置 → 网络」查看本机 IP，"
  echo "他人访问: http://你的IP:${IMG_TOOL_PORT}/"
fi
echo ""
echo "注意:"
echo "  - 处理在你这台电脑上执行；上传/下载走你的机器。"
echo "  - 「选择文件夹」会弹出本机对话框，仅适合你在服务器电脑前操作。"
echo "  - 开发用服务器，勿长期暴露公网；同 Wi‑Fi 内分享即可。"
echo "=========================================="
echo ""

python3 "web_app.py"
