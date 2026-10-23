from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from .models import MediaItem, MediaType


THUMBNAIL_SIZE = (240, 135)


def thumbnail_cache_dir() -> Path:
    path = Path.home() / ".retirement_video" / "thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_thumbnail(item: MediaItem) -> str:
    """원본을 GUI에 올리지 않도록 작은 JPEG 썸네일을 디스크에 만든다."""
    if not item.content_hash:
        return ""
    destination = thumbnail_cache_dir() / f"{item.content_hash}.jpg"
    if destination.exists() and destination.stat().st_size:
        return str(destination)
    temporary = destination.with_suffix(".tmp.jpg")
    try:
        if item.media_type == MediaType.PHOTO:
            with Image.open(item.source_path) as source:
                # JPEG는 전체 해상도 디코딩 전에 축소 힌트를 적용해 메모리를 줄인다.
                source.draft("RGB", (480, 270))
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS, reducing_gap=3.0)
                canvas = Image.new("RGB", THUMBNAIL_SIZE, "#111827")
                canvas.paste(image, ((THUMBNAIL_SIZE[0] - image.width) // 2, (THUMBNAIL_SIZE[1] - image.height) // 2))
                canvas.save(temporary, "JPEG", quality=82, optimize=True)
        else:
            command = [
                "ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", item.source_path,
                "-frames:v", "1", "-vf",
                "scale=240:135:force_original_aspect_ratio=decrease,pad=240:135:(ow-iw)/2:(oh-ih)/2:color=#111827",
                str(temporary),
            ]
            subprocess.run(command, capture_output=True, timeout=30, check=True)
        temporary.replace(destination)
        return str(destination)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        return ""
