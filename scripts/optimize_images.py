#!/usr/bin/env python3
"""Generate and verify full-resolution, pixel-identical image assets.

Install scripts/requirements-images.txt, then run this file from any directory.
Use --check to validate the manifest and every decoded RGBA byte without encoding.
Original PNGs stay untouched. Only content-addressed delivery assets are generated.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys

from PIL import Image, features


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
OUTPUT = STATIC / "optimized"
MANIFEST = OUTPUT / "manifest.json"
SOURCE_DIRECTORIES = ("main", "case01", "case02", "case03", "ui")
MAX_WEBP_DIMENSION = 16383


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def source_files() -> list[Path]:
    return sorted(
        path
        for name in SOURCE_DIRECTORIES
        for path in (STATIC / name).glob("*.png")
    )


def source_url(path: Path) -> str:
    return "/static/" + path.relative_to(STATIC).as_posix()


def output_name(source: Path, extension: str, content_hash: str) -> Path:
    relative = source.relative_to(STATIC)
    return OUTPUT / relative.parent / f"{relative.stem}.{content_hash[:12]}.{extension}"


def verify_pixels(source: Image.Image, output_data: bytes, source_path: Path) -> None:
    with Image.open(BytesIO(output_data)) as output:
        if output.size != source.size:
            raise ValueError(f"Dimensions changed: {source_path}")
        if output.convert("RGBA").tobytes() != source.convert("RGBA").tobytes():
            raise ValueError(f"Decoded RGBA pixels changed: {source_path}")
        if output.info.get("icc_profile") != source.info.get("icc_profile"):
            raise ValueError(f"ICC profile changed: {source_path}")


def can_use_webp(image: Image.Image) -> bool:
    if max(image.size) > MAX_WEBP_DIMENSION:
        return False
    # WebP without ICC assumes sRGB. Preserve unusual PNG gamma by retaining PNG.
    # https://developers.google.com/speed/webp/docs/riff_container#color-profile
    return (
        bool(image.info.get("icc_profile"))
        or "srgb" in image.info
        or "gamma" not in image.info
        or abs(image.info["gamma"] - 0.45455) < 0.00001
    )


def optimize(source_path: Path) -> tuple[str, dict]:
    source_data = source_path.read_bytes()
    with Image.open(BytesIO(source_data)) as source:
        rgba = source.convert("RGBA")
        output_data = source_data
        extension = "png"
        # Keep future 16-bit or animated PNGs byte-for-byte rather than reducing
        # their precision or dropping frames in this still-image WebP pipeline.
        if source_data[24] <= 8 and not getattr(source, "is_animated", False) and can_use_webp(source):
            encoded = BytesIO()
            options = {"lossless": True, "quality": 100, "method": 6, "exact": True}
            for key in ("icc_profile", "exif", "xmp"):
                if source.info.get(key):
                    options[key] = source.info[key]
            rgba.save(encoded, format="WEBP", **options)
            candidate = encoded.getvalue()
            if len(candidate) < len(source_data):
                output_data = candidate
                extension = "webp"

        # Every selected delivery file must decode to the exact original pixels.
        verify_pixels(source, output_data, source_path)
        output_hash = digest(output_data)
        destination = output_name(source_path, extension, output_hash)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output_data)
        entry = {
            "src": "/static/optimized/" + destination.relative_to(OUTPUT).as_posix(),
            "width": source.width,
            "height": source.height,
            "sourceBytes": len(source_data),
            "outputBytes": len(output_data),
            "sourceSha256": digest(source_data),
            "outputSha256": output_hash,
            "pixelSha256": digest(rgba.tobytes()),
        }
    saved = (1 - entry["outputBytes"] / entry["sourceBytes"]) * 100
    print(f"{source_url(source_path)}: {entry['sourceBytes']:,} → {entry['outputBytes']:,} bytes ({saved:.1f}% smaller), RGBA identical", flush=True)
    return source_url(source_path), entry


def check_entry(source_path: Path, entry: dict) -> None:
    source_data = source_path.read_bytes()
    output_path = ROOT / entry["src"].lstrip("/")
    if not output_path.resolve().is_relative_to(OUTPUT.resolve()):
        raise ValueError(f"Output escapes optimized directory: {entry['src']}")
    output_data = output_path.read_bytes()
    source_hash, output_hash = digest(source_data), digest(output_data)
    if source_hash != entry["sourceSha256"] or len(source_data) != entry["sourceBytes"]:
        raise ValueError(f"Source changed: {source_path}")
    if output_hash != entry["outputSha256"] or len(output_data) != entry["outputBytes"]:
        raise ValueError(f"Output changed: {output_path}")
    expected_path = output_name(source_path, output_path.suffix.lstrip("."), output_hash)
    if output_path != expected_path:
        raise ValueError(f"Content hash does not match filename: {output_path}")
    if len(output_data) > len(source_data):
        raise ValueError(f"Optimized output is larger than the original: {output_path}")
    with Image.open(BytesIO(source_data)) as source:
        if (source.width, source.height) != (entry["width"], entry["height"]):
            raise ValueError(f"Manifest dimensions do not match source: {source_path}")
        if digest(source.convert("RGBA").tobytes()) != entry["pixelSha256"]:
            raise ValueError(f"Manifest pixel hash does not match source: {source_path}")
        verify_pixels(source, output_data, source_path)


def summarize(manifest: dict, action: str) -> None:
    source_bytes = sum(entry["sourceBytes"] for entry in manifest.values())
    output_bytes = sum(entry["outputBytes"] for entry in manifest.values())
    saved = (1 - output_bytes / source_bytes) * 100 if source_bytes else 0
    print(f"{action} {len(manifest)} images: {source_bytes:,} → {output_bytes:,} bytes ({saved:.2f}% smaller). Full dimensions, RGBA pixels and ICC profiles preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing output; do not encode or write files")
    parser.add_argument("--workers", type=int, choices=range(1, 4), default=3, help="Parallel encoders/checkers (1–3, default: 3)")
    args = parser.parse_args()
    paths = source_files()
    if not paths:
        raise ValueError("No source PNGs found")
    if args.check:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if set(manifest) != {source_url(path) for path in paths}:
            raise ValueError("Manifest sources do not match current source PNGs")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda path: check_entry(path, manifest[source_url(path)]), paths))
        summarize(manifest, "Verified")
        return
    if not features.check("webp"):
        raise RuntimeError("Pillow requires WebP support; install scripts/requirements-images.txt")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        manifest = dict(pool.map(optimize, paths))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Sorted sources and no timestamps make repeated output stable.
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summarize(manifest, "Generated and verified")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Image optimization failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
