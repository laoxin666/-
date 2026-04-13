#!/bin/zsh
# 在桌面生成 zip：内含独立 .app，对方无需安装 Python（需与本机相同 CPU 架构的 Mac）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ARCH=$(uname -m)
STAMP=$(date +%Y%m%d)
OUT_NAME="PixelForge-发给同事-免Python-${ARCH}-${STAMP}.zip"
OUT_PATH="${HOME}/Desktop/${OUT_NAME}"

# 国内 pip 慢可取消下一行注释
# export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ① 准备打包专用环境（首次约 2～5 分钟）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v python3 &>/dev/null; then
  echo "错误：未找到 python3，请先安装 Python。"
  exit 1
fi

if [[ ! -d ".venv-pack" ]]; then
  python3 -m venv .venv-pack
fi
# shellcheck disable=SC1091
source ".venv-pack/bin/activate"
pip install -q -U pip
pip install -q -r requirements-web.txt -r requirements-build.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ② 构建独立应用 PixelForge Studio.app（约 1～2 分钟）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

export PIXELFORGE_MAC_ARCH=native
python -m PyInstaller --noconfirm PixelForge.spec

APP_SRC="$ROOT/dist/PixelForge Studio.app"
if [[ ! -d "$APP_SRC" ]]; then
  echo "错误：未找到构建产物 $APP_SRC"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ③ 写入 zip"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TDIR=$(mktemp -d)
trap 'rm -rf "$TDIR"' EXIT

mkdir -p "$TDIR/PixelForge"
rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.venv-share' \
  --exclude '.venv-universal' \
  --exclude '.venv-pack' \
  --exclude 'build' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'PixelForge-发给同事-*.zip' \
  "$ROOT/" "$TDIR/PixelForge/"

# 用构建好的 app 覆盖 rsync 可能带来的旧 dist 副本（rsync 已排除 dist）
rm -rf "$TDIR/PixelForge/PixelForge Studio.app"
cp -R "$APP_SRC" "$TDIR/PixelForge/"

( cd "$TDIR" && zip -r -q "$OUT_PATH" PixelForge )

echo ""
echo "已生成：$OUT_PATH"
echo "（内含独立应用，对方 Mac 需为 ${ARCH}，与当前打包机一致）"
echo ""
echo "发给同事：解压 → 先读「同事请看.txt」→ 双击 PixelForge Studio.app"
osascript -e "display notification \"已保存到桌面（免 Python）\" with title \"PixelForge 分享包\"" 2>/dev/null || true
