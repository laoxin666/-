#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PIXELFORGE_PACKAGE_TARGET=arm64
exec zsh "$ROOT/scripts/打成分享压缩包.command"
