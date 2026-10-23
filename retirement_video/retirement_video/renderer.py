from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .models import MediaItem, MediaType, VideoProject


class RenderError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RenderError("FFmpeg를 찾을 수 없습니다. FFmpeg를 설치하고 PATH에 추가하세요.")
    return executable


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        message = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise RenderError(message or "FFmpeg 실행에 실패했습니다.")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _card(path: Path, lines: list[str], width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), "#172033")
    draw = ImageDraw.Draw(image)
    fonts = [_font(max(28, width // (22 if i == 0 else 32))) for i in range(len(lines))]
    boxes = [draw.textbbox((0, 0), text, font=font) for text, font in zip(lines, fonts)]
    total = sum(box[3] - box[1] for box in boxes) + max(0, len(lines) - 1) * 30
    y = (height - total) // 2
    for text, font, box in zip(lines, fonts, boxes):
        draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill="white")
        y += box[3] - box[1] + 30
    image.save(path, quality=95)


def _prepared_photo(item: MediaItem, destination: Path) -> None:
    with Image.open(item.source_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        if item.rotation % 360:
            image = image.rotate(item.rotation % 360, expand=True)
        for region in item.mosaics:
            left = max(0, int(region.x * image.width))
            top = max(0, int(region.y * image.height))
            right = min(image.width, int((region.x + region.width) * image.width))
            bottom = min(image.height, int((region.y + region.height) * image.height))
            if right <= left or bottom <= top:
                continue
            crop = image.crop((left, top, right, bottom))
            small_w = max(1, crop.width // max(2, region.strength))
            small_h = max(1, crop.height // max(2, region.strength))
            pixelated = crop.resize((small_w, small_h), Image.Resampling.BILINEAR).resize(crop.size, Image.Resampling.NEAREST)
            if region.shape == "ellipse":
                mask = Image.new("L", crop.size, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, crop.width - 1, crop.height - 1), fill=255)
                image.paste(pixelated, (left, top), mask)
            else:
                image.paste(pixelated, (left, top))
        if item.subtitle.strip():
            draw = ImageDraw.Draw(image, "RGBA")
            font = _font(max(24, image.width // 28))
            text = item.subtitle.strip()
            box = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=8)
            text_width, text_height = box[2] - box[0], box[3] - box[1]
            x = (image.width - text_width) // 2
            y = image.height - text_height - max(30, image.height // 18)
            padding = max(12, image.width // 100)
            draw.rounded_rectangle((x-padding, y-padding, x+text_width+padding, y+text_height+padding), radius=padding, fill=(0, 0, 0, 155))
            draw.multiline_text((x, y), text, font=font, fill="white", align="center", spacing=8)
        image.save(destination, quality=95)


def _render_still(ffmpeg: str, image: Path, output: Path, duration: float, width: int, height: int, fps: int) -> None:
    fade_out = max(0, duration - 0.45)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps},fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out:.3f}:d=0.45,format=yuv420p"
    )
    _run([ffmpeg, "-y", "-loop", "1", "-i", str(image), "-t", f"{duration:.3f}", "-vf", vf,
          "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output)])


def _render_video(ffmpeg: str, item: MediaItem, output: Path, width: int, height: int, fps: int) -> None:
    end = item.trim_end if item.trim_end is not None else item.source_duration
    duration = max(0.1, end - item.trim_start) if end else item.duration
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps},format=yuv420p"
    _run([ffmpeg, "-y", "-ss", f"{item.trim_start:.3f}", "-i", item.source_path, "-t", f"{duration:.3f}",
          "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output)])


def render_project(project: VideoProject, destination: str | Path, progress: Callable[[int, str], None] | None = None) -> Path:
    if not project.items:
        raise RenderError("출력할 사진이나 동영상이 없습니다.")
    ffmpeg = find_ffmpeg()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    settings = project.settings
    with tempfile.TemporaryDirectory(prefix="retirement-video-") as temporary_name:
        temporary = Path(temporary_name)
        sources: list[tuple[Path, float, MediaItem | None]] = []
        title = temporary / "title.jpg"
        _card(title, [settings.title], settings.width, settings.height)
        sources.append((title, 3.0, None))
        chapter = None
        for item in project.items:
            if item.chapter != chapter and item.chapter != "날짜 미확인":
                chapter = item.chapter
                card = temporary / f"chapter_{len(sources):04d}.jpg"
                _card(card, [chapter], settings.width, settings.height)
                sources.append((card, 2.0, None))
            sources.append((Path(item.source_path), item.duration, item))
        ending = temporary / "ending.jpg"
        _card(ending, [settings.ending_line1, settings.ending_line2], settings.width, settings.height)
        sources.append((ending, 5.0, None))
        clips: list[Path] = []
        for index, (source, duration, item) in enumerate(sources):
            clip = temporary / f"clip_{index:04d}.mp4"
            if item and item.media_type == MediaType.VIDEO:
                _render_video(ffmpeg, item, clip, settings.width, settings.height, settings.fps)
            else:
                prepared = source
                if item:
                    prepared = temporary / f"photo_{index:04d}.jpg"
                    _prepared_photo(item, prepared)
                _render_still(ffmpeg, prepared, clip, duration, settings.width, settings.height, settings.fps)
            clips.append(clip)
            if progress:
                progress(int((index + 1) / (len(sources) + 1) * 90), f"장면 {index + 1}/{len(sources)} 처리 중")
        concat_file = temporary / "concat.txt"
        concat_file.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding="utf-8")
        silent = temporary / "silent.mp4"
        _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent)])
        if project.music:
            track = project.music[0]
            total = sum(duration for _, duration, _ in sources)
            fade_out = max(0, total - track.fade_out)
            af = f"volume={track.volume},afade=t=in:st=0:d={track.fade_in},afade=t=out:st={fade_out:.3f}:d={track.fade_out},atrim=duration={total:.3f}"
            _run([ffmpeg, "-y", "-i", str(silent), "-stream_loop", "-1", "-i", track.source_path,
                  "-filter:a", af, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(destination)])
        else:
            shutil.copy2(silent, destination)
        if progress:
            progress(100, "출력 완료")
    return destination
