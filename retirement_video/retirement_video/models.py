from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"


class DatePrecision(str, Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


@dataclass
class MosaicRegion:
    shape: str = "rectangle"
    x: float = 0.0
    y: float = 0.0
    width: float = 0.2
    height: float = 0.2
    strength: int = 20


@dataclass
class MediaItem:
    source_path: str
    media_type: MediaType
    id: str = field(default_factory=lambda: str(uuid4()))
    display_name: str = ""
    capture_date: str | None = None
    date_precision: DatePrecision = DatePrecision.UNKNOWN
    date_source: str = "미확인"
    chapter: str = "날짜 미확인"
    duration: float = 4.0
    source_duration: float = 0.0
    trim_start: float = 0.0
    trim_end: float | None = None
    transition: str = "크로스 디졸브"
    importance: str = "일반"
    subtitle: str = ""
    locked: bool = False
    mosaics: list[MosaicRegion] = field(default_factory=list)
    width: int = 0
    height: int = 0
    content_hash: str = ""
    thumbnail_path: str = ""
    rotation: int = 0

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = Path(self.source_path).name

    @property
    def parsed_date(self) -> datetime | None:
        return datetime.fromisoformat(self.capture_date) if self.capture_date else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaItem":
        values = dict(data)
        values["media_type"] = MediaType(values["media_type"])
        values["date_precision"] = DatePrecision(values.get("date_precision", "unknown"))
        values["mosaics"] = [MosaicRegion(**x) for x in values.get("mosaics", [])]
        return cls(**values)


@dataclass
class MusicTrack:
    source_path: str
    volume: float = 0.65
    fade_in: float = 1.5
    fade_out: float = 3.0
    bpm: float | None = None
    beats: list[float] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class ProjectSettings:
    title: str = "함께한 시간, 소중한 추억"
    ending_line1: str = "함께한 모든 순간에 감사드립니다."
    ending_line2: str = "새로운 시작을 진심으로 응원합니다."
    style: str = "밝고 즐거운 퇴임식"
    default_duration: float = 4.0
    min_duration: float = 2.5
    max_duration: float = 6.0
    transition_duration: float = 0.7
    sync_strength: int = 70
    target_seconds: int | None = None
    width: int = 1920
    height: int = 1080
    fps: int = 30


@dataclass
class VideoProject:
    name: str = "새 퇴임식 영상"
    version: int = 1
    items: list[MediaItem] = field(default_factory=list)
    music: list[MusicTrack] = field(default_factory=list)
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    project_path: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoProject":
        values = dict(data)
        values["items"] = [MediaItem.from_dict(x) for x in values.get("items", [])]
        values["music"] = [MusicTrack(**x) for x in values.get("music", [])]
        values["settings"] = ProjectSettings(**values.get("settings", {}))
        return cls(**values)
