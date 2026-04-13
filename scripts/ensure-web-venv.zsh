# 先设置 SCRIPT_DIR 并 cd 到项目根，再：source 本文件 && ensure_web_venv

ensure_web_venv() {
  VPY="$SCRIPT_DIR/.venv/bin/python3"
  VPIP="$SCRIPT_DIR/.venv/bin/pip"

  # export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

  if [[ ! -x "$VPY" ]]; then
    echo "首次运行：正在创建虚拟环境并安装依赖（需要联网，约 1～3 分钟）…"
    if ! command -v python3 &>/dev/null; then
      echo ""
      echo "【错误】未找到 python3。请安装：https://www.python.org/downloads/macos/"
      return 1
    fi
    if ! python3 -m venv .venv; then
      echo ""
      echo "【错误】无法创建 .venv，请把上面英文报错截图发给人排查。"
      return 1
    fi
    "$VPIP" install -q -U pip || echo "【警告】pip 升级失败，继续…"
    if ! "$VPIP" install -q -r requirements-web.txt; then
      echo ""
      echo "【错误】安装依赖失败。可换网络后删除 .venv 再试。"
      return 1
    fi
    echo "依赖已就绪。"
  fi
  return 0
}
