from pathlib import Path

from PIL import Image

from retirement_video.metadata import analyze_media
from retirement_video.thumbnails import THUMBNAIL_SIZE, create_thumbnail
from retirement_video.models import DatePrecision, MediaItem, MediaType
from retirement_video.renderer import _date_label


def test_large_photo_uses_small_cached_thumbnail(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("retirement_video.thumbnails.thumbnail_cache_dir", lambda: tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    source = tmp_path / "2020년_행사사진.jpg"
    Image.new("RGB", (4000, 3000), "red").save(source)
    item = analyze_media(source, tmp_path)
    item.thumbnail_path = create_thumbnail(item)
    with Image.open(item.thumbnail_path) as thumbnail:
        assert thumbnail.size == THUMBNAIL_SIZE
    assert Path(item.thumbnail_path).stat().st_size < source.stat().st_size


def test_thumbnail_rotation_changes_orientation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("retirement_video.thumbnails.thumbnail_cache_dir", lambda: tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    source = tmp_path / "portrait.jpg"
    Image.new("RGB", (300, 600), "blue").save(source)
    item = analyze_media(source, tmp_path)
    item.rotation = 90
    rotated = Path(create_thumbnail(item))
    assert rotated.name.endswith("_r90.jpg")
    with Image.open(rotated) as thumbnail:
        # 가로 사진으로 회전되어 위아래 여백이 생긴다.
        center = thumbnail.getpixel((120, 67))
        top = thumbnail.getpixel((120, 5))
        assert center[2] > 150
        assert top[2] < 100


def test_photo_date_label_respects_precision():
    item = MediaItem("photo.jpg", MediaType.PHOTO, capture_date="2005-03-17T00:00:00", date_precision=DatePrecision.YEAR)
    assert _date_label(item) == "2005년"
    item.date_precision = DatePrecision.MONTH
    assert _date_label(item) == "2005년 3월"
    item.date_precision = DatePrecision.DAY
    assert _date_label(item) == "2005년 3월 17일"
