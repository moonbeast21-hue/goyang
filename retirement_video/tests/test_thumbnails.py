from pathlib import Path

from PIL import Image

from retirement_video.metadata import analyze_media
from retirement_video.thumbnails import THUMBNAIL_SIZE, create_thumbnail


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
