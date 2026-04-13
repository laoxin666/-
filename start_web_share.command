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

export IMG_TOOL_HOST="${IMG_TOOL_HOST:-0.0.0.0}"
export IMG_TOOL_PORT="${IMG_TOOL_PORT:-5000}"

echo "=========================================="
echo "  局域网分享模式（他人可访问本机处理服务）"
echo "=========================================="
echo ""
echo "监听: ${IMG_TOOL_HOST}:${IMG_TOOL_PORT}"
echo ""
LAN_IPS=()
while read -r ip; do
  [[ -n "$ip" ]] && LAN_IPS+=("$ip")
done < <(ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" { print $2 }' | sort -u)

if [[ ${#LAN_IPS[@]} -gt 0 ]]; then
  echo "请让同事在浏览器打开（同一 Wi‑Fi / 同一网段，任选其一）:"
  for ip in "${LAN_IPS[@]}"; do
    echo "  http://${ip}:${IMG_TOOL_PORT}/"
  done
else
  echo "未自动检测到局域网 IP，请在「系统设置 → 网络」查看本机地址，"
  echo "同事访问: http://你的IP:${IMG_TOOL_PORT}/"
fi
echo ""
echo "若同事打不开，请在本机检查:"
echo "  - 系统设置 → 网络 → 防火墙：关闭防火墙测试，或允许「python3」接受传入连接"
echo "  - 同事是否与你连同一 Wi‑Fi（访客网络常会隔离设备）"
echo ""
echo "注意:"
echo "  - 处理在你这台电脑上执行；上传/下载走你的机器。"
echo "  - 「选择文件夹」会弹出本机对话框，仅适合你在服务器电脑前操作。"
echo "  - 开发用服务器，勿长期暴露公网；同 Wi‑Fi 内分享即可。"
echo "=========================================="
echo ""

exec "$VPY" "$SCRIPT_DIR/web_app.py"
