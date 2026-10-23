from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ExifTags

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # HEIC 외 형식은 계속 사용할 수 있다.
    pass

from .models import DatePrecision, MediaItem, MediaType

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}

DATE_PATTERNS = (
    (re.compile(r"(?<!\d)((?:19|20)\d{2})[._년\-/ ]+(0?[1-9]|1[0-2])[._월\-/ ]+(0?[1-9]|[12]\d|3[01])(?:일)?(?!\d)"), DatePrecision.DAY),
    (re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])(?!\d)"), DatePrecision.DAY),
    (re.compile(r"(?<!\d)((?:19|20)\d{2})[._년\-/ ]+(0?[1-9]|1[0-2])(?:월)?(?!\d)"), DatePrecision.MONTH),
    (re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(?!\d)"), DatePrecision.MONTH),
    (re.compile(r"(?<!\d)((?:19|20)\d{2})(?:년)?(?!\d)"), DatePrecision.YEAR),
)
CHAPTER_MARKER = re.compile(
    r"^(?:\[?\s*(?:chapter|chap|ch|챕터|장)\s*[-_. ]*\d+\s*\]?|\[?\s*\d+\s*(?:장|부)\s*\]?|\d{1,2}\s*[-_.])\s*(.*)$",
    re.IGNORECASE,
)
GENERIC_FOLDERS = {"사진", "동영상", "미디어", "퇴임식", "퇴임사진", "images", "photos", "videos", "media", "dcim", "camera"}


@dataclass(frozen=True)
class DateGuess:
    value: datetime | None
    precision: DatePrecision
    source: str


def parse_date_text(text: str, source: str) -> DateGuess:
    for pattern, precision in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = [int(x) for x in match.groups()]
        year, month, day = parts[0], 1, 1
        if precision in (DatePrecision.MONTH, DatePrecision.DAY):
            month = parts[1]
        if precision == DatePrecision.DAY:
            day = parts[2]
        try:
            return DateGuess(datetime(year, month, day), precision, source)
        except ValueError:
            continue
    return DateGuess(None, DatePrecision.UNKNOWN, "미확인")


def clean_chapter(text: str) -> str | None:
    stem = Path(text).stem.strip()
    match = CHAPTER_MARKER.match(stem)
    if match:
        label = match.group(1).strip(" _-.[]()")
        return label or stem.strip(" _-.[]()")
    # 날짜 뒤에 설명이 있으면 설명을 챕터로 사용한다.
    without_date = stem
    for pattern, _ in DATE_PATTERNS:
        without_date = pattern.sub("", without_date, count=1)
    label = without_date.strip(" _-.[]()")
    if label and label != stem and not label.isdigit():
        return label
    return None


def clean_folder_chapter(text: str) -> str | None:
    marked = clean_chapter(text)
    if marked:
        return marked
    label = Path(text).stem.strip(" _-.[]()")
    if label.casefold() in GENERIC_FOLDERS or label.isdigit():
        return None
    # 설명형 하위 폴더는 그 자체를 챕터로 인정한다.
    if re.search(r"[A-Za-z가-힣]", label):
        return label
    return None


def infer_from_path(path: Path, media_root: Path | None = None) -> tuple[DateGuess, str | None]:
    """가까운 폴더부터 검사한 뒤 파일명을 검사한다.

    날짜와 챕터는 서로 다른 경로 조각에서 찾아도 된다. 사용자가 선택한
    루트 폴더 이름까지 검사하지만 그 상위 경로는 프로젝트 분류에 쓰지 않는다.
    """
    folders: list[Path] = []
    current = path.parent
    stop = media_root.parent.resolve() if media_root else None
    while current != current.parent:
        folders.append(current)
        if stop and current.resolve() == stop:
            break
        if media_root and current.resolve() == media_root.resolve():
            break
        current = current.parent
    root_resolved = media_root.resolve() if media_root else None
    candidates = [(p.name, "폴더명", bool(root_resolved and p.resolve() == root_resolved)) for p in folders]
    candidates.append((path.stem, "파일명", False))
    guess = DateGuess(None, DatePrecision.UNKNOWN, "미확인")
    chapter = None
    for text, source, is_root in candidates:
        if not guess.value:
            guess = parse_date_text(text, source)
        if not chapter:
            if source == "폴더명" and not is_root:
                chapter = clean_folder_chapter(text)
            else:
                chapter = clean_chapter(text)
    return guess, chapter


def _photo_metadata(path: Path) -> tuple[DateGuess, int, int]:
    try:
        with Image.open(path) as image:
            width, height = image.size
            exif = image.getexif()
            named = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
            for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                raw = named.get(key)
                if raw:
                    try:
                        return DateGuess(datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S"), DatePrecision.DAY, "EXIF"), width, height
                    except ValueError:
                        pass
            return DateGuess(None, DatePrecision.UNKNOWN, "미확인"), width, height
    except Exception:
        return DateGuess(None, DatePrecision.UNKNOWN, "미확인"), 0, 0


def _probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags=creation_time:stream=width,height", "-of", "json", str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def _video_metadata(path: Path) -> tuple[DateGuess, float, int, int]:
    data = _probe(path)
    duration = float(data.get("format", {}).get("duration") or 0)
    stream = next((x for x in data.get("streams", []) if x.get("width")), {})
    raw = data.get("format", {}).get("tags", {}).get("creation_time")
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            guess = DateGuess(parsed, DatePrecision.DAY, "동영상 메타데이터")
        except ValueError:
            guess = DateGuess(None, DatePrecision.UNKNOWN, "미확인")
    else:
        guess = DateGuess(None, DatePrecision.UNKNOWN, "미확인")
    return guess, duration, int(stream.get("width", 0)), int(stream.get("height", 0))


def quick_hash(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    digest.update(str(size).encode())
    with path.open("rb") as file:
        digest.update(file.read(1024 * 1024))
        if size > 1024 * 1024:
            file.seek(max(0, size - 1024 * 1024))
            digest.update(file.read(1024 * 1024))
    return digest.hexdigest()


def analyze_media(path: str | Path, media_root: str | Path | None = None) -> MediaItem:
    path = Path(path).resolve()
    suffix = path.suffix.lower()
    media_type = MediaType.PHOTO if suffix in PHOTO_EXTENSIONS else MediaType.VIDEO
    path_guess, path_chapter = infer_from_path(path, Path(media_root).resolve() if media_root else None)
    if media_type == MediaType.PHOTO:
        metadata_guess, width, height = _photo_metadata(path)
        source_duration = 0.0
    else:
        metadata_guess, source_duration, width, height = _video_metadata(path)
    guess = metadata_guess if metadata_guess.value else path_guess
    chapter = path_chapter or (f"{guess.value.year}년" if guess.value else "날짜 미확인")
    return MediaItem(
        source_path=str(path), media_type=media_type,
        capture_date=guess.value.isoformat(timespec="seconds") if guess.value else None,
        date_precision=guess.precision, date_source=guess.source, chapter=chapter,
        duration=min(source_duration, 10.0) if media_type == MediaType.VIDEO and source_duration else 4.0,
        source_duration=source_duration, width=width, height=height,
        content_hash=quick_hash(path),
    )


def collect_media(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    supported = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
    return sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in supported), key=lambda p: str(p).lower())
