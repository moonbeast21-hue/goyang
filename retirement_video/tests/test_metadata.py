from datetime import datetime
from pathlib import Path

from retirement_video.metadata import clean_chapter, infer_from_path, parse_date_text
from retirement_video.models import DatePrecision


def test_date_formats():
    assert parse_date_text("IMG_20240317_120000", "파일명").value == datetime(2024, 3, 17)
    assert parse_date_text("2019년 8월 송별회", "폴더명").precision == DatePrecision.MONTH
    assert parse_date_text("1998 추억", "폴더명").precision == DatePrecision.YEAR


def test_folder_date_has_priority_over_filename(tmp_path: Path):
    folder = tmp_path / "2005년_함께 걸어온 시간"
    path = folder / "IMG_20240101.jpg"
    guess, chapter = infer_from_path(path, folder)
    assert guess.value == datetime(2005, 1, 1)
    assert guess.source == "폴더명"
    assert chapter == "함께 걸어온 시간"


def test_chapter_markers():
    assert clean_chapter("01_공직생활의 시작") == "공직생활의 시작"
    assert clean_chapter("챕터 3 새로운 출발") == "새로운 출발"
    assert clean_chapter("2026-새로운 출발") == "새로운 출발"


def test_date_and_chapter_can_come_from_different_parts(tmp_path: Path):
    root = tmp_path / "2장 동료들과의 추억"
    path = root / "2015.04.03_행사.jpg"
    guess, chapter = infer_from_path(path, root)
    assert guess.value == datetime(2015, 4, 3)
    assert guess.source == "파일명"
    assert chapter == "동료들과의 추억"


def test_plain_subfolder_is_a_chapter(tmp_path: Path):
    root = tmp_path / "퇴임사진"
    path = root / "가족과 함께" / "IMG_20200102.jpg"
    guess, chapter = infer_from_path(path, root)
    assert guess.value == datetime(2020, 1, 2)
    assert chapter == "가족과 함께"

