# -*- mode: python ; coding: utf-8 -*-
# 用法：在项目根目录执行  pyinstaller --noconfirm PixelForge.spec
# 产出：dist/PixelForge Studio.app
#
# 默认打 universal2（一份 .app 可在 Intel 与 Apple Silicon 上运行）。
# 要求：构建用的 Python 与 Pillow 等带原生扩展的 wheel 须为 fat/universal2。
# 推荐：从 https://www.python.org/downloads/macos/ 安装「macOS 64-bit universal2」，
#       新建 venv 后再 pip install -r requirements.txt 与 PyInstaller。
#
# 若报错 “is not a fat binary”：说明当前解释器或某依赖仅为单架构。可临时改为仅本机构架：
#   PIXELFORGE_MAC_ARCH=native pyinstaller --noconfirm PixelForge.spec

import os

spec_dir = os.path.dirname(os.path.abspath(SPEC))

_mac = os.environ.get("PIXELFORGE_MAC_ARCH", "universal2").strip().lower()
if _mac in ("native", "single", "current", "host"):
    TARGET_ARCH = None
elif _mac in ("universal2", "universal", "fat"):
    TARGET_ARCH = "universal2"
else:
    raise SystemExit(
        "Invalid PIXELFORGE_MAC_ARCH={!r}; use 'universal2' or 'native'.".format(_mac)
    )

a = Analysis(
    [os.path.join(spec_dir, "web_app.py")],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(spec_dir, "templates"), "templates"),
    ],
    hiddenimports=["image_tool", "PIL._imaging", "PIL._webp"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PixelForgeStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PixelForgeStudio",
)
app = BUNDLE(
    coll,
    name="PixelForge Studio.app",
    icon=None,
    bundle_identifier="studio.pixelforge.imagetool",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHumanReadableCopyright": "Local image processing; runs a small web server on your Mac.",
    },
)
