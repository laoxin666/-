#!/usr/bin/env python3
"""
Web UI for lossless image compression and format conversion.
"""

from __future__ import annotations

import io
import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_file, send_from_directory
from PIL import Image
from werkzeug.utils import secure_filename

from image_tool import convert_image, normalize_target_format, save_lossless


def _app_root() -> Path:
    """项目根目录；PyInstaller 打包后为 _MEIPASS。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


_APP_ROOT = _app_root()
_static = _APP_ROOT / "static"
_frontend = _APP_ROOT / "frontend"
_flask_kwargs: dict[str, str | None] = {"template_folder": str(_APP_ROOT / "templates")}
_flask_kwargs["static_folder"] = str(_static) if _static.is_dir() else None


def is_cloud_mode() -> bool:
    """云端/容器部署：禁用本机路径、仅上传+下载 ZIP。"""
    return os.getenv("IMG_TOOL_CLOUD", "").strip().lower() in {"1", "true", "yes", "on"}


def access_token_configured() -> bool:
    return bool(os.getenv("IMG_TOOL_ACCESS_TOKEN", "").strip())


app = Flask(__name__, **_flask_kwargs)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("IMG_TOOL_MAX_UPLOAD_MB", "200")) * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
_cloud = is_cloud_mode()
app.config["TEMPLATES_AUTO_RELOAD"] = not _cloud
app.jinja_env.auto_reload = not _cloud

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}
DOWNLOAD_CACHE: dict[str, dict[str, object]] = {}

FAILURE_REASON_META: dict[str, tuple[str, str]] = {
    "permission_error": ("权限不足", "请检查输入或输出目录权限后重试。"),
    "io_error": ("读写失败", "请确认磁盘空间和路径可访问性。"),
    "processing_error": ("处理失败", "建议更换格式或减小压缩强度后重试。"),
    "target_unmet": ("目标未达标", "建议提高目标体积，或改用 JPEG/WebP。"),
    "duplicate_file": ("重复文件已跳过", "同内容文件仅保留一份，避免重复处理。"),
}


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reason_payload(reason: str) -> tuple[str, str]:
    if not reason:
        return "", ""
    title, suggestion = FAILURE_REASON_META.get(reason, (reason, ""))
    return title, suggestion


def ensure_unique_output_path(output: Path, used_paths: set[str]) -> Path:
    candidate = output
    stem = output.stem
    suffix = output.suffix
    idx = 1
    while str(candidate) in used_paths:
        candidate = output.with_name(f"{stem}_{idx}{suffix}")
        idx += 1
    used_paths.add(str(candidate))
    return candidate


def get_ui_config() -> dict[str, object]:
    return {
        "app_name": os.getenv("IMG_TOOL_APP_NAME", "PixelForge Studio"),
        "tagline": os.getenv(
            "IMG_TOOL_TAGLINE",
            "专业级图像优化工作台，聚焦无损压缩与高质量格式转换，适合素材归档、设计交付和内容发布前处理。",
        ),
        "logo_text": os.getenv("IMG_TOOL_LOGO_TEXT", "PF"),
        "brand_color": os.getenv("IMG_TOOL_BRAND_COLOR", "#4f8cff"),
        "accent_color": os.getenv("IMG_TOOL_ACCENT_COLOR", "#19d4c5"),
        "cloud_mode": is_cloud_mode(),
        "access_token_required": access_token_configured(),
    }


def api_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


@app.after_request
def add_no_cache_headers(response):
    # Force browser to always request the latest page/assets.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.before_request
def require_access_token():
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    expected = os.getenv("IMG_TOOL_ACCESS_TOKEN", "").strip()
    if not expected:
        return None
    provided = (request.headers.get("X-Access-Token") or "").strip()
    if not provided and request.form:
        provided = (request.form.get("access_token") or "").strip()
    if provided != expected:
        return jsonify({"ok": False, "error": "需要正确的访问令牌（X-Access-Token 或表单 access_token）。"}), 401
    return None


def parse_optional_positive_int(raw_value: str | None, field_name: str) -> int | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是整数。") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} 必须大于 0。")
    return parsed


def parse_output_dir(raw_value: str | None) -> Path | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    out_dir = Path(value).expanduser()
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError("无法创建输出文件夹，请检查路径权限。") from exc
    if not out_dir.is_dir():
        raise ValueError("输出路径不是有效文件夹。")
    return out_dir


def parse_input_dir(raw_value: str | None) -> Path | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    in_dir = Path(value).expanduser()
    if not in_dir.is_absolute():
        in_dir = (Path.cwd() / in_dir).resolve()
    if not in_dir.exists() or not in_dir.is_dir():
        raise ValueError("输入文件夹不存在或不可访问。")
    return in_dir


def parse_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return str(raw_value).lower() in {"1", "true", "yes", "on"}


def default_export_root(output_mode: str) -> Path:
    desktop = Path.home() / "Desktop"
    if output_mode == "original":
        return desktop / "image-lossless-original-output"
    return desktop / "image-lossless-output"


def sanitize_suffix(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_"})
    if not cleaned:
        return ""
    if not cleaned.startswith("_"):
        cleaned = "_" + cleaned
    return cleaned


def apply_name_template(
    original_name: str,
    target_ext: str,
    template: str,
    index: int,
    target_size_kb: int | None,
    before_bytes: int,
) -> str:
    tmpl = (template or "").strip()
    if not tmpl:
        return Path(original_name).stem + target_ext
    now = datetime.now().strftime("%Y%m%d")
    stem = Path(original_name).stem
    ext = target_ext.replace(".", "")
    size_kb = int(before_bytes / 1024) if before_bytes else 0
    rendered = (
        tmpl.replace("{name}", stem)
        .replace("{ext}", ext)
        .replace("{date}", now)
        .replace("{sizeKB}", str(target_size_kb or size_kb))
        .replace("{index}", str(index))
    )
    safe = "".join(ch for ch in rendered if ch.isalnum() or ch in {"-", "_", "."})
    safe = safe.strip("._")
    if not safe:
        safe = f"image_{index}"
    return safe + target_ext


def apply_suffix(filename: str, suffix: str, target_ext: str | None = None) -> str:
    path = Path(filename)
    stem = path.stem
    ext = target_ext if target_ext is not None else path.suffix
    return f"{stem}{suffix}{ext}"


def add_download_to_cache(data: bytes) -> str:
    token = uuid.uuid4().hex
    now = time.time()
    # Remove stale items older than 30 minutes.
    stale = [key for key, item in DOWNLOAD_CACHE.items() if now - float(item["ts"]) > 1800]
    for key in stale:
        DOWNLOAD_CACHE.pop(key, None)
    DOWNLOAD_CACHE[token] = {"bytes": data, "ts": now}
    return token


@app.get("/")
def index():
    if _frontend.is_dir():
        return redirect("/frontend/", code=302)
    return send_from_directory(str(_APP_ROOT / "templates"), "index.html")


@app.get("/frontend/")
def frontend_index():
    if _frontend.is_dir():
        return send_from_directory(str(_frontend), "index.html")
    return send_from_directory(str(_APP_ROOT / "templates"), "index.html")


@app.get("/frontend/<path:filename>")
def frontend_assets(filename: str):
    if not _frontend.is_dir():
        return api_error("前端页面资源不存在，请重新打包应用。", 404)
    return send_from_directory(str(_frontend), filename)


@app.get("/config")
def ui_config():
    return jsonify({"ok": True, "ui": get_ui_config()})


@app.get("/health")
def health():
    return jsonify({"ok": True, "cloud": is_cloud_mode()})


@app.post("/pick-output-dir")
def pick_output_dir():
    if is_cloud_mode():
        return api_error("云端部署不支持系统目录选择，请使用「下载 ZIP」。")
    if os.name != "posix":
        return api_error("当前系统不支持该目录选择器，请手动输入路径。")
    try:
        completed = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "选择输出文件夹")',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return api_error("无法打开系统目录选择器，请手动输入路径。")

    if completed.returncode != 0:
        stderr = (completed.stderr or "").lower()
        if "cancel" in stderr:
            return jsonify({"ok": False, "cancelled": True})
        return api_error("目录选择失败，请重试或手动输入路径。")

    selected = (completed.stdout or "").strip()
    if not selected:
        return jsonify({"ok": False, "cancelled": True})
    return jsonify({"ok": True, "path": selected})


@app.post("/pick-input-dir")
def pick_input_dir():
    if is_cloud_mode():
        return api_error("云端部署不支持此功能，请使用浏览器上传或拖拽。")
    if os.name != "posix":
        return api_error("当前系统不支持该目录选择器，请手动输入路径。")
    try:
        completed = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "选择输入文件夹")',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return api_error("无法打开系统目录选择器，请手动输入路径。")
    if completed.returncode != 0:
        stderr = (completed.stderr or "").lower()
        if "cancel" in stderr:
            return jsonify({"ok": False, "cancelled": True})
        return api_error("目录选择失败，请重试或手动输入路径。")
    selected = (completed.stdout or "").strip()
    if not selected:
        return jsonify({"ok": False, "cancelled": True})
    return jsonify({"ok": True, "path": selected})


@app.post("/open-path")
def open_path():
    if is_cloud_mode():
        return api_error("云端部署无法在服务器上打开本地文件夹。")
    raw = (request.form.get("path") or "").strip()
    if not raw:
        return api_error("缺少路径参数。")
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_dir():
        return api_error("路径不存在或不是文件夹。")

    try:
        if os.name == "posix":
            completed = subprocess.run(["open", str(path)], capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                return api_error("打开目录失败。")
        else:
            return api_error("当前系统暂不支持自动打开目录。")
    except Exception:
        return api_error("打开目录失败。")
    return jsonify({"ok": True})


@app.post("/estimate")
def estimate():
    if is_cloud_mode():
        return api_error("云端部署不支持扫描服务器本地文件夹，请直接上传后使用策略预览。")
    try:
        input_dir = parse_input_dir(request.form.get("input_dir"))
        target_size_kb = parse_optional_positive_int(request.form.get("target_size_kb"), "目标体积(KB)")
        recursive = parse_bool(request.form.get("recursive"), True)
    except ValueError as exc:
        return api_error(str(exc))

    if not input_dir:
        return api_error("请先选择输入文件夹。")
    pattern = "**/*" if recursive else "*"
    files = [p for p in input_dir.glob(pattern) if p.is_file()]
    supported = [p for p in files if p.suffix.lower() in ALLOWED_EXTENSIONS]
    unsupported = len(files) - len(supported)

    total_before = sum(p.stat().st_size for p in supported)
    if target_size_kb:
        target_total = len(supported) * target_size_kb * 1024
        est_low = min(total_before, int(target_total * 0.85))
        est_high = min(total_before, int(target_total * 1.15))
    else:
        est_low = int(total_before * 0.55)
        est_high = int(total_before * 0.92)

    return jsonify(
        {
            "ok": True,
            "total_files": len(files),
            "supported_files": len(supported),
            "unsupported_files": unsupported,
            "before_bytes": total_before,
            "est_after_low": max(0, est_low),
            "est_after_high": max(0, est_high),
        }
    )


@app.post("/preview-size")
def preview_size():
    mode = request.form.get("mode", "compress")
    target = request.form.get("target", "png")
    compress_to = request.form.get("compress_to", "same").lower()
    strict_allow_placeholder = True
    try:
        target_size_kb = parse_optional_positive_int(
            request.form.get("target_size_kb"), "目标体积(KB)"
        )
    except ValueError as exc:
        return api_error(str(exc))
    preview_limit_raw = (request.form.get("preview_limit") or "").strip()
    preview_limit: int | None = None
    if preview_limit_raw:
        try:
            preview_limit = int(preview_limit_raw)
        except ValueError:
            return api_error("预览抽样数量必须是整数。")
        if preview_limit <= 0:
            return api_error("预览抽样数量必须大于 0。")

    if not target_size_kb:
        return api_error("请先填写目标输出体积(KB)再查看策略预览。")
    if mode == "convert":
        try:
            target = normalize_target_format(target)
        except ValueError as exc:
            return api_error(str(exc))
    elif compress_to != "same":
        try:
            compress_to = normalize_target_format(compress_to)
        except ValueError as exc:
            return api_error(str(exc))

    files = request.files.getlist("images")
    valid_files = [f for f in files if f and f.filename and allowed_file(f.filename)]
    if not valid_files:
        return api_error("请至少上传一张支持的图片。")
    total_candidates = len(valid_files)

    max_preview_files = preview_limit if preview_limit is not None else 120
    source_infos: list[tuple[Path, str]] = []
    with tempfile.TemporaryDirectory(prefix="img_preview_") as tmp:
        tmp_path = Path(tmp)
        upload_dir = tmp_path / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)

        for idx, file_storage in enumerate(valid_files[:max_preview_files], start=1):
            filename = secure_filename(file_storage.filename or f"image_{idx}")
            if not filename:
                continue
            source = upload_dir / f"{idx:03d}_{filename}"
            file_storage.save(source)
            source_infos.append((source, filename))

        target_bytes = target_size_kb * 1024
        preview_rows: list[dict[str, object]] = []
        for strategy in ("strict",):
            allow_quality_loss = True
            strict_mode = True
            total_before = 0
            total_after = 0
            failed = 0
            unmet = 0
            strategy_output_dir = tmp_path / f"out_{strategy}"
            strategy_output_dir.mkdir(parents=True, exist_ok=True)

            for idx, (source, filename) in enumerate(source_infos, start=1):
                try:
                    if mode == "compress":
                        with Image.open(source) as img:
                            src_pil_format = img.format or source.suffix.replace(".", "").upper()
                        source_ext = f".{(src_pil_format or '').lower()}" if src_pil_format else Path(filename).suffix
                        target_ext = source_ext if compress_to == "same" else f".{compress_to}"
                        output = strategy_output_dir / f"preview_{idx}{target_ext}"
                        if compress_to == "same":
                            result = save_lossless(
                                source,
                                output,
                                src_pil_format,
                                target_size_kb=target_size_kb,
                                allow_quality_loss=allow_quality_loss,
                                aggressive_target=strict_mode,
                                strict_allow_placeholder=strict_allow_placeholder,
                            )
                        else:
                            result = convert_image(
                                source,
                                output,
                                compress_to,
                                target_size_kb=target_size_kb,
                                allow_quality_loss=allow_quality_loss,
                                aggressive_target=strict_mode,
                                strict_allow_placeholder=strict_allow_placeholder,
                            )
                    else:
                        output = strategy_output_dir / f"preview_{idx}.{target}"
                        result = convert_image(
                            source,
                            output,
                            target,
                            target_size_kb=target_size_kb,
                            allow_quality_loss=allow_quality_loss,
                            aggressive_target=strict_mode,
                            strict_allow_placeholder=strict_allow_placeholder,
                        )
                    total_before += int(result.before_size)
                    total_after += int(result.after_size)
                    if int(result.after_size) > target_bytes:
                        unmet += 1
                except Exception:
                    failed += 1

            processed_count = max(0, len(source_infos) - failed)
            saved = total_before - total_after
            ratio = (saved / total_before * 100) if total_before else 0
            preview_rows.append(
                {
                    "strategy": strategy,
                    "before": total_before,
                    "after": total_after,
                    "saved": saved,
                    "ratio": round(ratio, 2),
                    "processed": processed_count,
                    "failed": failed,
                    "unmet": unmet,
                }
            )

    return jsonify(
        {
            "ok": True,
            "preview": preview_rows,
            "sampled_files": len(source_infos),
            "total_files": total_candidates,
        }
    )


@app.post("/process")
def process():
    input_mode = request.form.get("input_mode", "upload")
    mode = request.form.get("mode", "compress")
    target = request.form.get("target", "png")
    compress_to = request.form.get("compress_to", "same").lower()
    output_mode = request.form.get("output_mode", "download")
    if is_cloud_mode():
        input_mode = "upload"
        output_mode = "download"
    target_strategy = "strict"
    naming_template = (request.form.get("naming_template") or "").strip()
    keep_structure = parse_bool(request.form.get("keep_structure"), True)
    output_suffix = sanitize_suffix(request.form.get("output_suffix"))
    if output_mode not in {"download", "folder", "original"}:
        output_mode = "download"
    strict_mode = True
    strict_allow_placeholder = True
    allow_quality_loss = True
    if input_mode not in {"upload", "folder"}:
        input_mode = "upload"
    try:
        target_size_kb = parse_optional_positive_int(
            request.form.get("target_size_kb"), "目标体积(KB)"
        )
        output_dir_path = parse_output_dir(request.form.get("output_dir"))
        input_dir_path = parse_input_dir(request.form.get("input_dir"))
    except ValueError as exc:
        return api_error(str(exc))
    files = request.files.getlist("images")

    retry_sources: set[str] | None = None
    retry_raw = (request.form.get("retry_sources") or "").strip()
    if retry_raw:
        try:
            parsed = json.loads(retry_raw)
            if isinstance(parsed, list):
                retry_sources = {str(item) for item in parsed}
        except json.JSONDecodeError:
            retry_sources = None

    if mode == "convert":
        try:
            target = normalize_target_format(target)
        except ValueError as exc:
            return api_error(str(exc))
    else:
        if compress_to != "same":
            try:
                compress_to = normalize_target_format(compress_to)
            except ValueError as exc:
                return api_error(str(exc))
    if not target_size_kb:
        return api_error("严格达标模式需要填写目标输出体积(KB)。")

    results: list[tuple[str, int, int]] = []
    details: list[dict[str, object]] = []
    strict_failed: list[str] = []
    skipped_duplicates = 0
    target_bytes = target_size_kb * 1024 if target_size_kb else None

    with tempfile.TemporaryDirectory(prefix="img_web_") as tmp:
        tmp_path = Path(tmp)
        upload_dir = tmp_path / "upload"
        temp_output_dir = tmp_path / "output"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp_output_dir.mkdir(parents=True, exist_ok=True)

        source_entries: list[dict[str, object]] = []
        seen_hashes: set[str] = set()
        if input_mode == "upload":
            valid_files = [f for f in files if f and f.filename and allowed_file(f.filename)]
            if not valid_files:
                return api_error("请至少上传一张支持的图片。")
            for file_storage in valid_files:
                filename = secure_filename(file_storage.filename or "image")
                if not filename:
                    continue
                source = upload_dir / filename
                file_storage.save(source)
                digest = file_sha256(source)
                if digest in seen_hashes:
                    skipped_duplicates += 1
                    reason_text, suggestion = reason_payload("duplicate_file")
                    details.append(
                        {
                            "name": filename,
                            "source_name": filename,
                            "before": source.stat().st_size if source.exists() else 0,
                            "after": 0,
                            "ratio": 0,
                            "target_met": True,
                            "message": "重复文件已跳过",
                            "status": "skipped",
                            "reason": "duplicate_file",
                            "reason_text": reason_text,
                            "suggestion": suggestion,
                            "source_path": str(source),
                        }
                    )
                    continue
                seen_hashes.add(digest)
                source_entries.append(
                    {"source": source, "filename": filename, "rel_parent": Path("."), "source_key": str(source)}
                )
        else:
            if not input_dir_path:
                return api_error("请选择输入文件夹。")
            pattern = "**/*" if keep_structure else "*"
            for path in sorted(p for p in input_dir_path.glob(pattern) if p.is_file()):
                if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                digest = file_sha256(path)
                if digest in seen_hashes:
                    skipped_duplicates += 1
                    reason_text, suggestion = reason_payload("duplicate_file")
                    details.append(
                        {
                            "name": path.name,
                            "source_name": path.name,
                            "before": path.stat().st_size,
                            "after": 0,
                            "ratio": 0,
                            "target_met": True,
                            "message": "重复文件已跳过",
                            "status": "skipped",
                            "reason": "duplicate_file",
                            "reason_text": reason_text,
                            "suggestion": suggestion,
                            "source_path": str(path.resolve()),
                        }
                    )
                    continue
                seen_hashes.add(digest)
                source_key = str(path.resolve())
                if retry_sources is not None and source_key not in retry_sources:
                    continue
                rel_parent = path.relative_to(input_dir_path).parent if keep_structure else Path(".")
                source_entries.append(
                    {
                        "source": path,
                        "filename": path.name,
                        "rel_parent": rel_parent,
                        "source_key": source_key,
                    }
                )
            if not source_entries:
                return api_error("输入文件夹中没有可处理图片。")

        used_output_paths: set[str] = set()
        for idx, entry in enumerate(source_entries, start=1):
            source = entry["source"]
            filename = str(entry["filename"])
            rel_parent = Path(entry["rel_parent"])
            source_key = str(entry["source_key"])
            try:
                if mode == "compress":
                    with Image.open(source) as img:
                        src_pil_format = img.format or Path(source).suffix.replace(".", "").upper()
                        before_bytes = Path(source).stat().st_size
                    source_ext = f".{(src_pil_format or '').lower()}" if src_pil_format else Path(filename).suffix
                    target_ext = source_ext if compress_to == "same" else f".{compress_to}"
                    base_name = apply_name_template(
                        filename,
                        target_ext=target_ext,
                        template=naming_template,
                        index=idx,
                        target_size_kb=target_size_kb,
                        before_bytes=before_bytes,
                    )
                    output_name = apply_suffix(base_name, output_suffix, target_ext=target_ext)
                    output = temp_output_dir / rel_parent / output_name
                    output = ensure_unique_output_path(output, used_output_paths)
                    if compress_to == "same":
                        result = save_lossless(
                            source,
                            output,
                            src_pil_format,
                            target_size_kb=target_size_kb,
                            allow_quality_loss=allow_quality_loss,
                            aggressive_target=strict_mode,
                            strict_allow_placeholder=strict_allow_placeholder,
                        )
                    else:
                        result = convert_image(
                            source,
                            output,
                            compress_to,
                            target_size_kb=target_size_kb,
                            allow_quality_loss=allow_quality_loss,
                            aggressive_target=strict_mode,
                            strict_allow_placeholder=strict_allow_placeholder,
                        )
                else:
                    before_bytes = Path(source).stat().st_size
                    target_ext = f".{target}"
                    base_name = apply_name_template(
                        filename,
                        target_ext=target_ext,
                        template=naming_template,
                        index=idx,
                        target_size_kb=target_size_kb,
                        before_bytes=before_bytes,
                    )
                    output_name = apply_suffix(base_name, output_suffix, target_ext=target_ext)
                    output = temp_output_dir / rel_parent / output_name
                    output = ensure_unique_output_path(output, used_output_paths)
                    result = convert_image(
                        source,
                        output,
                        target,
                        target_size_kb=target_size_kb,
                        allow_quality_loss=allow_quality_loss,
                        aggressive_target=strict_mode,
                        strict_allow_placeholder=strict_allow_placeholder,
                    )
                results.append((str(result.output.relative_to(temp_output_dir)), result.before_size, result.after_size))

                delta = result.before_size - result.after_size
                ratio = (delta / result.before_size * 100) if result.before_size else 0
                target_met = True
                if target_bytes:
                    target_met = result.after_size <= target_bytes
                reason = "target_unmet" if (target_bytes and not target_met) else ""
                reason_text, suggestion = reason_payload(reason)
                details.append(
                    {
                        "name": str(result.output.relative_to(temp_output_dir)),
                        "source_name": filename,
                        "before": result.before_size,
                        "after": result.after_size,
                        "ratio": round(ratio, 2),
                        "target_met": target_met,
                        "message": result.message,
                        "status": "ok",
                        "reason": reason,
                        "reason_text": reason_text,
                        "suggestion": suggestion,
                        "source_path": source_key,
                    }
                )
                if strict_mode and target_bytes and not target_met:
                    strict_failed.append(str(result.output.relative_to(temp_output_dir)))
            except PermissionError:
                reason_text, suggestion = reason_payload("permission_error")
                details.append(
                    {
                        "name": filename,
                        "source_name": filename,
                        "before": 0,
                        "after": 0,
                        "ratio": 0,
                        "target_met": False,
                        "message": "权限不足",
                        "status": "failed",
                        "reason": "permission_error",
                        "reason_text": reason_text,
                        "suggestion": suggestion,
                        "source_path": source_key,
                    }
                )
            except OSError:
                reason_text, suggestion = reason_payload("io_error")
                details.append(
                    {
                        "name": filename,
                        "source_name": filename,
                        "before": 0,
                        "after": 0,
                        "ratio": 0,
                        "target_met": False,
                        "message": "读写失败",
                        "status": "failed",
                        "reason": "io_error",
                        "reason_text": reason_text,
                        "suggestion": suggestion,
                        "source_path": source_key,
                    }
                )
            except Exception:
                reason_text, suggestion = reason_payload("processing_error")
                details.append(
                    {
                        "name": filename,
                        "source_name": filename,
                        "before": 0,
                        "after": 0,
                        "ratio": 0,
                        "target_met": False,
                        "message": "处理失败",
                        "status": "failed",
                        "reason": "processing_error",
                        "reason_text": reason_text,
                        "suggestion": suggestion,
                        "source_path": source_key,
                    }
                )

        if strict_mode and strict_failed:
            sample = ", ".join(strict_failed[:5])
            extra = "" if len(strict_failed) <= 5 else f" 等 {len(strict_failed)} 个文件"
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "严格策略未通过：未达到目标体积 "
                        f"{target_size_kb}KB：{sample}{extra}。可尝试提高目标体积，"
                        "或改用 JPEG/WebP 以获得更强压缩。"
                    ),
                    "results": details,
                    "failed_sources": [
                        d.get("source_path")
                        for d in details
                        if d.get("status") == "failed" or d.get("target_met") is False
                    ],
                    "skipped_duplicates": skipped_duplicates,
                }
            )

        if output_mode in {"folder", "original"}:
            base_dir = output_dir_path or default_export_root(output_mode)
            base_dir.mkdir(parents=True, exist_ok=True)
            export_dir = base_dir / f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_dir.mkdir(parents=True, exist_ok=True)
            for out_file in sorted(temp_output_dir.rglob("*")):
                if not out_file.is_file():
                    continue
                rel = out_file.relative_to(temp_output_dir)
                target_file = export_dir / rel
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(out_file, target_file)

            summary_lines = ["处理结果："]
            for name, before, after in results:
                delta = before - after
                ratio = (delta / before * 100) if before else 0
                summary_lines.append(f"{name}: {before}B -> {after}B ({ratio:+.2f}%)")
            (export_dir / "result.txt").write_text("\n".join(summary_lines), encoding="utf-8")

            return jsonify(
                {
                    "ok": True,
                    "saved_to": str(export_dir),
                    "file_count": len(results),
                    "results": details,
                    "failed_sources": [
                        d.get("source_path")
                        for d in details
                        if d.get("status") == "failed" or d.get("target_met") is False
                    ],
                    "skipped_duplicates": skipped_duplicates,
                }
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for out_file in sorted(temp_output_dir.rglob("*")):
                if out_file.is_file():
                    zipf.write(out_file, arcname=str(out_file.relative_to(temp_output_dir)))

            summary_lines = ["处理结果："]
            for name, before, after in results:
                delta = before - after
                ratio = (delta / before * 100) if before else 0
                summary_lines.append(f"{name}: {before}B -> {after}B ({ratio:+.2f}%)")
            zipf.writestr("result.txt", "\n".join(summary_lines))

        token = add_download_to_cache(zip_buffer.getvalue())
        return jsonify(
            {
                "ok": True,
                "download_token": token,
                "file_count": len(results),
                "results": details,
                "failed_sources": [
                    d.get("source_path")
                    for d in details
                    if d.get("status") == "failed" or d.get("target_met") is False
                ],
                "skipped_duplicates": skipped_duplicates,
            }
        )


@app.get("/download/<token>")
def download(token: str):
    item = DOWNLOAD_CACHE.pop(token, None)
    if not item:
        return api_error("下载链接已失效，请重新处理。", status=404)
    content = item.get("bytes")
    if not isinstance(content, (bytes, bytearray)):
        return api_error("下载数据异常。", status=500)
    return send_file(
        io.BytesIO(bytes(content)),
        as_attachment=True,
        download_name="processed_images.zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    # 本机：`IMG_TOOL_HOST=127.0.0.1`（默认）
    # 局域网分享：`IMG_TOOL_HOST=0.0.0.0`（见 start_web_share.command）
    # 打包为 .app 后默认监听全网卡，便于同事访问；仍可用环境变量覆盖。
    # 与 macOS 隔空播放争用 5000 时，可把下面默认改成 "8080" 后重新打包。
    _FROZEN_DEFAULT_PORT = "5000"
    if getattr(sys, "frozen", False):
        os.environ.setdefault("IMG_TOOL_HOST", "0.0.0.0")
        os.environ.setdefault("IMG_TOOL_PORT", _FROZEN_DEFAULT_PORT)
    host = os.getenv("IMG_TOOL_HOST", "127.0.0.1")
    port = int(os.getenv("IMG_TOOL_PORT", "5000"))
    if getattr(sys, "frozen", False):
        import threading
        import webbrowser

        def _open_browser() -> None:
            import time

            time.sleep(1.2)
            webbrowser.open(f"http://127.0.0.1:{port}/")

        threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host=host, port=port, debug=False, threaded=True)
