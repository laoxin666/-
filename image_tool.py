#!/usr/bin/env python3
"""
Image tool for lossless compression and format conversion.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}
CONVERT_FORMATS = {"png", "jpeg", "webp", "tiff", "bmp", "gif"}


@dataclass
class TaskResult:
    source: Path
    output: Path
    action: str
    before_size: int
    after_size: int
    changed: bool
    message: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lossless image compression and format conversion tool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compress = subparsers.add_parser("compress", help="Lossless compress images")
    compress.add_argument("--input", required=True, type=Path, help="Input file or folder")
    compress.add_argument("--output", required=True, type=Path, help="Output folder")
    compress.add_argument(
        "--recursive", action="store_true", help="Recursively scan subdirectories"
    )
    compress.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing output files"
    )
    compress.add_argument(
        "--keep-when-larger",
        action="store_true",
        help="Keep compressed file even if it is larger than source",
    )
    compress.add_argument(
        "--target-size-kb",
        type=int,
        default=0,
        help="Optional target file size in KB (best effort)",
    )
    compress.add_argument(
        "--strict-mode",
        action="store_true",
        help="Require all outputs to be <= target-size-kb",
    )
    compress.add_argument(
        "--strict-behavior",
        choices=["abort", "report"],
        default="abort",
        help="Strict mode behavior: abort or report failed files",
    )
    compress.add_argument(
        "--allow-quality-loss",
        action="store_true",
        help="Allow lossy fallback if target size cannot be reached",
    )
    compress.add_argument(
        "--strict-no-placeholder",
        action="store_true",
        help="In strict mode, do not use 1x1 placeholder fallback",
    )

    convert = subparsers.add_parser("convert", help="Convert image format")
    convert.add_argument("--input", required=True, type=Path, help="Input file or folder")
    convert.add_argument("--output", required=True, type=Path, help="Output folder")
    convert.add_argument("--to", required=True, type=str, help="Target format, e.g. png/webp")
    convert.add_argument(
        "--recursive", action="store_true", help="Recursively scan subdirectories"
    )
    convert.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing output files"
    )
    convert.add_argument(
        "--allow-lossy",
        action="store_true",
        help="Allow conversion to lossy target format (for example jpeg)",
    )
    convert.add_argument(
        "--target-size-kb",
        type=int,
        default=0,
        help="Optional target file size in KB (best effort)",
    )
    convert.add_argument(
        "--strict-mode",
        action="store_true",
        help="Require all outputs to be <= target-size-kb",
    )
    convert.add_argument(
        "--strict-behavior",
        choices=["abort", "report"],
        default="abort",
        help="Strict mode behavior: abort or report failed files",
    )
    convert.add_argument(
        "--allow-quality-loss",
        action="store_true",
        help="Allow lossy fallback if target size cannot be reached",
    )
    convert.add_argument(
        "--strict-no-placeholder",
        action="store_true",
        help="In strict mode, do not use 1x1 placeholder fallback",
    )

    return parser.parse_args()


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def collect_files(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path] if is_image_file(input_path) else []

    pattern = "**/*" if recursive else "*"
    files = [p for p in input_path.glob(pattern) if is_image_file(p)]
    return sorted(files)


def relative_to_input(source: Path, input_path: Path) -> Path:
    if input_path.is_file():
        return Path(source.name)
    return source.relative_to(input_path)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_jpegtran_path() -> str | None:
    return shutil.which("jpegtran")


def run_jpegtran_lossless(source: Path, output: Path) -> bool:
    jpegtran = get_jpegtran_path()
    if not jpegtran:
        return False

    ensure_parent(output)
    cmd = [
        jpegtran,
        "-copy",
        "all",
        "-optimize",
        "-perfect",
        "-outfile",
        str(output),
        str(source),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return completed.returncode == 0


def _best_jpeg_under_target(
    img: Image.Image, target_bytes: int, exif_bytes: bytes | None = None
) -> tuple[bytes, int]:
    img = prepare_for_jpeg(img)
    low, high = 1, 95
    best_bytes: bytes | None = None
    best_quality = low

    while low <= high:
        quality = (low + high) // 2
        buf = io.BytesIO()
        save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True, "progressive": True}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(buf, **save_kwargs)
        data = buf.getvalue()
        if len(data) <= target_bytes:
            best_bytes = data
            best_quality = quality
            low = quality + 1
        else:
            high = quality - 1

    if best_bytes is not None:
        return best_bytes, best_quality

    # If target is too small, return minimal quality result.
    fallback = io.BytesIO()
    save_kwargs = {"format": "JPEG", "quality": 1, "optimize": True, "progressive": True}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    img.save(fallback, **save_kwargs)
    return fallback.getvalue(), 1


def _best_webp_under_target(
    img: Image.Image, target_bytes: int, exif_bytes: bytes | None = None
) -> tuple[bytes, int]:
    low, high = 1, 100
    best_bytes: bytes | None = None
    best_quality = low

    while low <= high:
        quality = (low + high) // 2
        buf = io.BytesIO()
        save_kwargs = {"format": "WEBP", "quality": quality, "method": 6}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(buf, **save_kwargs)
        data = buf.getvalue()
        if len(data) <= target_bytes:
            best_bytes = data
            best_quality = quality
            low = quality + 1
        else:
            high = quality - 1

    if best_bytes is not None:
        return best_bytes, best_quality

    fallback = io.BytesIO()
    save_kwargs = {"format": "WEBP", "quality": 1, "method": 6}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    img.save(fallback, **save_kwargs)
    return fallback.getvalue(), 1


def _save_jpeg_to_target(
    img: Image.Image,
    target_bytes: int,
    aggressive_downscale: bool = False,
    exif_bytes: bytes | None = None,
) -> tuple[bytes, int, tuple[int, int]]:
    working = img
    while True:
        data, quality = _best_jpeg_under_target(working, target_bytes, exif_bytes=exif_bytes)
        if len(data) <= target_bytes or not aggressive_downscale:
            return data, quality, working.size

        width, height = working.size
        if width <= 1 or height <= 1:
            return data, quality, working.size
        working = working.resize(
            (max(1, int(width * 0.85)), max(1, int(height * 0.85))),
            Image.Resampling.LANCZOS,
        )


def _save_webp_to_target(
    img: Image.Image,
    target_bytes: int,
    aggressive_downscale: bool = False,
    exif_bytes: bytes | None = None,
) -> tuple[bytes, int, tuple[int, int]]:
    working = img
    while True:
        data, quality = _best_webp_under_target(working, target_bytes, exif_bytes=exif_bytes)
        if len(data) <= target_bytes or not aggressive_downscale:
            return data, quality, working.size

        width, height = working.size
        if width <= 1 or height <= 1:
            return data, quality, working.size
        working = working.resize(
            (max(1, int(width * 0.85)), max(1, int(height * 0.85))),
            Image.Resampling.LANCZOS,
        )


def _force_strict_jpeg_result(
    source: Path, output: Path, before_size: int, target_size_kb: int | None
) -> TaskResult:
    target_bytes = _target_bytes(target_size_kb)
    if not target_bytes:
        return TaskResult(
            source,
            output,
            "compress",
            before_size,
            output.stat().st_size if output.exists() else before_size,
            False,
            "strict fallback skipped: missing target size.",
        )

    fallback_output = output.with_suffix(".jpg")
    ensure_parent(fallback_output)
    with Image.open(source) as img:
        data, quality, dims = _save_jpeg_to_target(img, target_bytes, aggressive_downscale=True)
    fallback_output.write_bytes(data)
    after = fallback_output.stat().st_size
    note = (
        f"strict fallback applied: JPEG q={quality}, size={dims[0]}x{dims[1]}, "
        f"target={target_size_kb}KB."
    )
    if after > target_bytes:
        note = f"{note} Hard limit reached; target still unattainable."
    return TaskResult(source, fallback_output, "compress", before_size, after, before_size != after, note)


def _force_strict_best_result(
    source: Path,
    output: Path,
    before_size: int,
    target_size_kb: int | None,
    allow_placeholder: bool = True,
) -> TaskResult:
    target_bytes = _target_bytes(target_size_kb)
    if not target_bytes:
        return TaskResult(
            source,
            output,
            "compress",
            before_size,
            output.stat().st_size if output.exists() else before_size,
            False,
            "strict fallback skipped: missing target size.",
        )

    best_data: bytes | None = None
    best_ext = ".jpg"
    best_note = ""

    with Image.open(source) as original:
        working = original
        while True:
            jpeg_data, jpeg_q, jpeg_dims = _save_jpeg_to_target(
                working, target_bytes, aggressive_downscale=False
            )
            webp_data, webp_q, webp_dims = _save_webp_to_target(
                working, target_bytes, aggressive_downscale=False
            )

            candidates = [
                (jpeg_data, ".jpg", f"JPEG q={jpeg_q}, size={jpeg_dims[0]}x{jpeg_dims[1]}"),
                (webp_data, ".webp", f"WEBP q={webp_q}, size={webp_dims[0]}x{webp_dims[1]}"),
            ]
            candidates.sort(key=lambda item: len(item[0]))
            data, ext, note = candidates[0]

            if best_data is None or len(data) < len(best_data):
                best_data = data
                best_ext = ext
                best_note = note

            if len(data) <= target_bytes:
                break

            width, height = working.size
            if width <= 1 or height <= 1:
                break
            # More aggressive scaling than normal flow: strict means "any cost".
            working = working.resize(
                (max(1, int(width * 0.7)), max(1, int(height * 0.7))),
                Image.Resampling.LANCZOS,
            )

    if best_data is None:
        best_data = b""
        best_ext = ".webp"
        best_note = "strict fallback failed to encode image."

    if allow_placeholder and len(best_data) > target_bytes:
        # Last-resort: replace with tiny 1x1 placeholder to satisfy size.
        placeholder = Image.new("RGB", (1, 1), (0, 0, 0))
        buf = io.BytesIO()
        placeholder.save(buf, format="WEBP", quality=1, method=6)
        ph = buf.getvalue()
        if len(ph) < len(best_data):
            best_data = ph
            best_ext = ".webp"
            best_note = "strict fallback used 1x1 placeholder image."

    fallback_output = output.with_suffix(best_ext)
    ensure_parent(fallback_output)
    fallback_output.write_bytes(best_data)
    after = fallback_output.stat().st_size
    note = f"strict hard compression applied: {best_note} target={target_size_kb}KB."
    if after > target_bytes:
        note = f"{note} Hard limit reached; target still unattainable."
    return TaskResult(source, fallback_output, "compress", before_size, after, before_size != after, note)


def _target_bytes(target_size_kb: int | None) -> int | None:
    if not target_size_kb:
        return None
    return int(target_size_kb) * 1024


def save_lossless(
    source: Path,
    output: Path,
    pil_format: str,
    target_size_kb: int | None = None,
    allow_quality_loss: bool = False,
    aggressive_target: bool = False,
    strict_allow_placeholder: bool = True,
    preserve_metadata: bool = False,
) -> TaskResult:
    ensure_parent(output)
    before = source.stat().st_size
    target_bytes = _target_bytes(target_size_kb)

    if pil_format == "JPEG" and not target_bytes:
        if run_jpegtran_lossless(source, output):
            after = output.stat().st_size
            return TaskResult(source, output, "compress", before, after, before != after)

        # No safe lossless fallback for JPEG re-encode.
        shutil.copy2(source, output)
        after = output.stat().st_size
        return TaskResult(
            source,
            output,
            "compress",
            before,
            after,
            False,
            message="jpegtran not found, copied original to avoid quality loss.",
        )

    with Image.open(source) as img:
        exif_bytes = img.info.get("exif") if preserve_metadata else None
        if pil_format == "PNG":
            img.save(output, format="PNG", optimize=True, compress_level=9)
        elif pil_format == "WEBP":
            if target_bytes:
                data, quality, dims = _save_webp_to_target(
                    img,
                    target_bytes,
                    aggressive_downscale=aggressive_target,
                    exif_bytes=exif_bytes,
                )
                output.write_bytes(data)
                after = output.stat().st_size
                note = (
                    f"target {target_size_kb}KB best effort via lossy WebP (q={quality})."
                )
                if dims != img.size:
                    note = f"{note} auto-resized to {dims[0]}x{dims[1]}."
                if after > target_bytes:
                    note = f"{note} Could not fully reach target size."
                return TaskResult(source, output, "compress", before, after, before != after, note)
            save_kwargs = {"format": "WEBP", "lossless": True, "quality": 100, "method": 6}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(output, **save_kwargs)
        elif pil_format == "TIFF":
            img.save(output, format="TIFF", compression="tiff_lzw")
        elif pil_format == "GIF":
            img.save(output, format="GIF", optimize=True)
        elif pil_format == "JPEG":
            if target_bytes:
                data, quality, dims = _save_jpeg_to_target(
                    img,
                    target_bytes,
                    aggressive_downscale=aggressive_target,
                    exif_bytes=exif_bytes,
                )
                output.write_bytes(data)
                after = output.stat().st_size
                note = f"target {target_size_kb}KB best effort via JPEG quality (q={quality})."
                if dims != img.size:
                    note = f"{note} auto-resized to {dims[0]}x{dims[1]}."
                if after > target_bytes:
                    note = f"{note} Could not fully reach target size."
                return TaskResult(source, output, "compress", before, after, before != after, note)
            img = prepare_for_jpeg(img)
            save_kwargs = {"format": "JPEG", "quality": 95, "optimize": True, "progressive": True}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(output, **save_kwargs)
        elif pil_format == "BMP":
            # BMP has little room for lossless compression in-place; copy by default.
            shutil.copy2(source, output)
        else:
            shutil.copy2(source, output)

    after = output.stat().st_size
    note = ""
    if target_bytes and pil_format not in {"JPEG", "WEBP"}:
        note = "target size control currently applies to JPEG/WEBP only."
    if target_bytes and after > target_bytes and not note:
        note = "Could not fully reach target size."
    if target_bytes and after > target_bytes and aggressive_target:
        strict = _force_strict_best_result(
            source,
            output,
            before,
            target_size_kb,
            allow_placeholder=strict_allow_placeholder,
        )
        strict.action = "compress"
        return strict
    if target_bytes and after > target_bytes and allow_quality_loss and pil_format not in {"JPEG", "WEBP"}:
        note = (
            "quality-loss fallback unavailable for this format without changing output type; "
            "use JPEG/WEBP target for stronger size control."
        )
    return TaskResult(source, output, "compress", before, after, before != after, note)


def normalize_target_format(value: str) -> str:
    target = value.lower()
    if target == "jpg":
        target = "jpeg"
    if target not in CONVERT_FORMATS:
        raise ValueError(f"Unsupported target format: {value}")
    return target


def prepare_for_jpeg(img: Image.Image) -> Image.Image:
    if img.mode in {"RGB", "L"}:
        return img
    # Flatten transparency with white background for JPEG.
    if img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def convert_image(
    source: Path,
    output: Path,
    target_format: str,
    target_size_kb: int | None = None,
    allow_quality_loss: bool = False,
    aggressive_target: bool = False,
    strict_allow_placeholder: bool = True,
    preserve_metadata: bool = False,
) -> TaskResult:
    ensure_parent(output)
    before = source.stat().st_size
    target_bytes = _target_bytes(target_size_kb)

    with Image.open(source) as img:
        exif_bytes = img.info.get("exif") if preserve_metadata else None
        if target_format == "jpeg":
            if target_bytes:
                data, quality, dims = _save_jpeg_to_target(
                    img,
                    target_bytes,
                    aggressive_downscale=aggressive_target,
                    exif_bytes=exif_bytes,
                )
                output.write_bytes(data)
                after = output.stat().st_size
                note = f"target {target_size_kb}KB best effort via JPEG quality (q={quality})."
                if dims != img.size:
                    note = f"{note} auto-resized to {dims[0]}x{dims[1]}."
                if after > target_bytes:
                    note = f"{note} Could not fully reach target size."
                return TaskResult(source, output, "convert", before, after, before != after, note)
            img = prepare_for_jpeg(img)
            save_kwargs = {"format": "JPEG", "quality": 95, "optimize": True, "progressive": True}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(output, **save_kwargs)
        elif target_format == "png":
            img.save(output, format="PNG", optimize=True, compress_level=9)
        elif target_format == "webp":
            if target_bytes:
                data, quality, dims = _save_webp_to_target(
                    img,
                    target_bytes,
                    aggressive_downscale=aggressive_target,
                    exif_bytes=exif_bytes,
                )
                output.write_bytes(data)
                after = output.stat().st_size
                note = (
                    f"target {target_size_kb}KB best effort via lossy WebP (q={quality})."
                )
                if dims != img.size:
                    note = f"{note} auto-resized to {dims[0]}x{dims[1]}."
                if after > target_bytes:
                    note = f"{note} Could not fully reach target size."
                return TaskResult(source, output, "convert", before, after, before != after, note)
            save_kwargs = {"format": "WEBP", "lossless": True, "quality": 100, "method": 6}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(output, **save_kwargs)
        elif target_format == "tiff":
            img.save(output, format="TIFF", compression="tiff_lzw")
        elif target_format == "bmp":
            img.save(output, format="BMP")
        elif target_format == "gif":
            img.save(output, format="GIF", optimize=True)

    after = output.stat().st_size
    note = ""
    if target_bytes and target_format not in {"jpeg", "webp"}:
        note = "target size control currently applies to JPEG/WEBP only."
    if target_bytes and after > target_bytes and not note:
        note = "Could not fully reach target size."
    if target_bytes and after > target_bytes and aggressive_target:
        strict = _force_strict_best_result(
            source,
            output,
            before,
            target_size_kb,
            allow_placeholder=strict_allow_placeholder,
        )
        strict.action = "convert"
        return strict
    if target_bytes and after > target_bytes and allow_quality_loss and target_format not in {"jpeg", "webp"}:
        note = (
            "quality-loss fallback unavailable for this target format without changing output type; "
            "use JPEG/WEBP target for stronger size control."
        )
    return TaskResult(source, output, "convert", before, after, before != after, note)


def should_overwrite(path: Path, overwrite: bool) -> bool:
    return overwrite or not path.exists()


def print_result(result: TaskResult) -> None:
    delta = result.before_size - result.after_size
    ratio = (delta / result.before_size * 100) if result.before_size else 0
    symbol = "OK"
    if result.after_size > result.before_size:
        symbol = "UP"
    print(
        f"[{symbol}] {result.source.name} -> {result.output.name} | "
        f"{result.before_size}B -> {result.after_size}B ({ratio:+.2f}%)"
    )
    if result.message:
        print(f"      note: {result.message}")


def summarize(results: Iterable[TaskResult]) -> None:
    items = list(results)
    if not items:
        print("No image files found.")
        return

    total_before = sum(i.before_size for i in items)
    total_after = sum(i.after_size for i in items)
    saved = total_before - total_after
    ratio = (saved / total_before * 100) if total_before else 0
    print("\nDone.")
    print(
        f"Processed: {len(items)} files | "
        f"Total: {total_before}B -> {total_after}B | Saved: {saved}B ({ratio:+.2f}%)"
    )


def parse_target_size_kb(args: argparse.Namespace) -> int | None:
    target_size_kb = args.target_size_kb if getattr(args, "target_size_kb", 0) else None
    if target_size_kb is not None and target_size_kb <= 0:
        raise ValueError("--target-size-kb must be greater than 0.")
    return target_size_kb


def run_compress(args: argparse.Namespace) -> int:
    try:
        target_size_kb = parse_target_size_kb(args)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return 2

    files = collect_files(args.input, args.recursive)
    results: list[TaskResult] = []
    strict_failed: list[str] = []
    target_bytes = _target_bytes(target_size_kb)
    if args.strict_mode and not target_bytes:
        print("Refused: --strict-mode requires --target-size-kb.")
        return 2

    for source in files:
        rel = relative_to_input(source, args.input)
        output = args.output / rel

        if not should_overwrite(output, args.overwrite):
            print(f"[SKIP] {output} exists (use --overwrite)")
            continue

        with Image.open(source) as img:
            pil_format = img.format or source.suffix.replace(".", "").upper()

        result = save_lossless(
            source,
            output,
            pil_format,
            target_size_kb=target_size_kb,
            allow_quality_loss=args.allow_quality_loss,
            aggressive_target=args.strict_mode,
            strict_allow_placeholder=not args.strict_no_placeholder,
        )

        if (
            not args.keep_when_larger
            and result.after_size > result.before_size
            and result.message == ""
        ):
            shutil.copy2(source, output)
            result = TaskResult(
                source=source,
                output=output,
                action="compress",
                before_size=result.before_size,
                after_size=result.before_size,
                changed=False,
                message="compressed output was larger, copied original instead.",
            )

        print_result(result)
        results.append(result)
        if args.strict_mode and target_bytes and result.after_size > target_bytes:
            strict_failed.append(result.output.name)

    summarize(results)
    if strict_failed:
        preview = ", ".join(strict_failed[:5])
        suffix = "" if len(strict_failed) <= 5 else f" ... ({len(strict_failed)} files)"
        print(f"Strict mode failed: {preview}{suffix}")
        if args.strict_behavior == "abort":
            return 3
        print("Strict mode report: completed with failed files listed above.")
    return 0


def run_convert(args: argparse.Namespace) -> int:
    try:
        target_size_kb = parse_target_size_kb(args)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return 2

    target_format = normalize_target_format(args.to)
    if target_format == "jpeg" and not args.allow_lossy:
        print("Refused: target format jpeg is lossy. Add --allow-lossy to continue.")
        return 2

    files = collect_files(args.input, args.recursive)
    results: list[TaskResult] = []
    strict_failed: list[str] = []
    target_bytes = _target_bytes(target_size_kb)
    if args.strict_mode and not target_bytes:
        print("Refused: --strict-mode requires --target-size-kb.")
        return 2

    for source in files:
        rel = relative_to_input(source, args.input)
        output = (args.output / rel).with_suffix(f".{target_format}")

        if not should_overwrite(output, args.overwrite):
            print(f"[SKIP] {output} exists (use --overwrite)")
            continue

        result = convert_image(
            source,
            output,
            target_format,
            target_size_kb=target_size_kb,
            allow_quality_loss=args.allow_quality_loss,
            aggressive_target=args.strict_mode,
            strict_allow_placeholder=not args.strict_no_placeholder,
        )
        print_result(result)
        results.append(result)
        if args.strict_mode and target_bytes and result.after_size > target_bytes:
            strict_failed.append(result.output.name)

    summarize(results)
    if strict_failed:
        preview = ", ".join(strict_failed[:5])
        suffix = "" if len(strict_failed) <= 5 else f" ... ({len(strict_failed)} files)"
        print(f"Strict mode failed: {preview}{suffix}")
        if args.strict_behavior == "abort":
            return 3
        print("Strict mode report: completed with failed files listed above.")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "compress":
        return run_compress(args)
    if args.command == "convert":
        return run_convert(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
