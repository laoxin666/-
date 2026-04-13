#!/bin/zsh
# 发给同事：解压文件夹后，双击本文件即可（首次会自动装依赖，需已安装 Python 3）
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
echo "  同事请在浏览器打开下面任意一个地址"
echo "  （需与你连同一 Wi‑Fi）"
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
    echo "  同事用 → http://${ip}:${IMG_TOOL_PORT}/"
  done
else
  echo "  （未自动检测到局域网 IP，请在「系统设置 → 网络」查看本机 IP）"
  echo "  同事用 → http://你的IP:${IMG_TOOL_PORT}/"
fi
echo ""
echo "  不要关这个窗口；关掉即停止服务。"
echo "  防火墙若拦截，请在「系统设置 → 网络 → 防火墙」中允许 Python。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 约 1 秒后帮本机打开页面
( sleep 1 && open "http://127.0.0.1:${IMG_TOOL_PORT}/" ) &

exec python3 "web_app.py"
