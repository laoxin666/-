#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$ROOT/PixelForge Studio.app"
APP_BIN="$APP_PATH/Contents/MacOS/PixelForgeStudio"

print_sep() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

host_arch="$(uname -m)"
mac_ver="$(sw_vers -productVersion 2>/dev/null || echo unknown)"

print_sep
echo "PixelForge 环境检查"
print_sep
echo "系统版本: $mac_ver"
echo "CPU 架构:  $host_arch"
echo ""

if [[ ! -d "$APP_PATH" ]]; then
  echo "❌ 未找到应用：PixelForge Studio.app"
  echo "请确认你已完整解压压缩包，并在同一文件夹运行本脚本。"
  exit 1
fi

if [[ ! -x "$APP_BIN" ]]; then
  echo "❌ 应用主程序不存在或不可执行：$APP_BIN"
  echo "建议重新解压一次压缩包后再试。"
  exit 1
fi

app_archs=""
if command -v lipo >/dev/null 2>&1; then
  app_archs="$(lipo -archs "$APP_BIN" 2>/dev/null || true)"
fi
if [[ -z "$app_archs" ]]; then
  file_out="$(file "$APP_BIN" 2>/dev/null || true)"
  if [[ "$file_out" == *"arm64"* && "$file_out" == *"x86_64"* ]]; then
    app_archs="arm64 x86_64"
  elif [[ "$file_out" == *"arm64"* ]]; then
    app_archs="arm64"
  elif [[ "$file_out" == *"x86_64"* ]]; then
    app_archs="x86_64"
  fi
fi

if [[ -n "$app_archs" ]]; then
  echo "应用架构: $app_archs"
else
  echo "应用架构: 未识别（将继续尝试运行）"
fi

echo ""
compatible="unknown"
if [[ "$app_archs" == *"$host_arch"* ]]; then
  compatible="yes"
elif [[ "$host_arch" == "arm64" && "$app_archs" == *"x86_64"* ]]; then
  compatible="rosetta"
else
  compatible="no"
fi

case "$compatible" in
  yes)
    echo "✅ 架构匹配，可直接运行。"
    ;;
  rosetta)
    echo "⚠️ 检测到 Intel 应用在 Apple Silicon 上运行。"
    echo "   可尝试运行，但建议让打包方提供 arm64 或 universal2 版本。"
    ;;
  no)
    echo "❌ 架构不匹配：当前 Mac 为 $host_arch，但应用为 [$app_archs]"
    echo "   请联系打包方索要与你电脑架构一致的版本。"
    exit 1
    ;;
  *)
    echo "ℹ️ 无法严格判断架构兼容性，将继续给出运行建议。"
    ;;
esac

echo ""
echo "下一步："
echo "1) 双击“PixelForge Studio.app”启动"
echo "2) 若提示无法验证开发者：按住 Control 点按 app -> 打开 -> 再打开"
echo "3) 若提示“已损坏/无法打开”，在终端执行："
echo "   xattr -dr com.apple.quarantine \"$APP_PATH\""
echo ""
print_sep
echo "检查完成"
print_sep
