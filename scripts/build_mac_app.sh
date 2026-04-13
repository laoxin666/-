#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing build dependency (PyInstaller)…"
python3 -m pip install -q -r requirements-build.txt

echo "==> Building dist/PixelForge Studio.app …"
echo "    (PIXELFORGE_MAC_ARCH=${PIXELFORGE_MAC_ARCH:-universal2}: universal2=Intel+M1 通用; native=仅当前 Mac 架构)"
if ! python3 -m PyInstaller --noconfirm PixelForge.spec; then
  echo ""
  echo "构建失败？若出现 “is not a fat binary”，说明当前 Python/依赖不是 universal2。"
  echo "  方案 A：安装 python.org 的 macOS「universal2」Python，新建 venv 后重装依赖再执行本脚本。"
  echo "  方案 B：仅打当前 CPU 可用的单架构包："
  echo "    PIXELFORGE_MAC_ARCH=native $0"
  exit 1
fi

echo ""
echo "Done. Open or copy:"
echo "  $ROOT/dist/PixelForge Studio.app"
echo ""
if [[ "${PIXELFORGE_MAC_ARCH:-universal2}" != "native" ]]; then
  echo "此为 universal2 时，同一 .app 可在 Intel 与 Apple Silicon Mac 上运行（需成功完成构建）。"
else
  echo "此为单架构包，仅适合与打包所用 Mac 相同 CPU 的机器。"
fi
