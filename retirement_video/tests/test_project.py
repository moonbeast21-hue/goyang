from pathlib import Path

from retirement_video.auto_editor import auto_edit, sort_by_date
from retirement_video.models import MediaItem, MediaType, VideoProject
from retirement_video.project_io import load_project, save_project


def item(name: str, date: str | None = None):
    return MediaItem(name, MediaType.PHOTO, capture_date=date)


def test_stable_date_sort_keeps_unknown_last():
    project = VideoProject(items=[item("b.jpg", "2020-01-01T00:00:00"), item("x.jpg"), item("a.jpg", "2010-01-01T00:00:00")])
    sort_by_date(project)
    assert [x.source_path for x in project.items] == ["a.jpg", "b.jpg", "x.jpg"]


def test_project_round_trip(tmp_path: Path):
    project = VideoProject(name="테스트", items=[item("한글 사진.jpg", "2020-01-01T00:00:00")])
    project.items[0].rotation = 270
    output = tmp_path / "기념영상.retirevideo"
    save_project(project, output)
    loaded = load_project(output)
    assert loaded.name == "테스트"
    assert loaded.items[0].display_name == "한글 사진.jpg"
    assert loaded.items[0].rotation == 270


def test_auto_edit_respects_locks_and_limits():
    project = VideoProject(items=[item("1.jpg"), item("2.jpg")])
    project.items[0].locked = True
    project.items[0].duration = 9
    project.settings.target_seconds = 4
    warnings = auto_edit(project)
    assert project.items[0].duration == 9
    assert project.items[1].duration == 4.0
    assert not warnings

