from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .models import VideoProject


def save_project(project: VideoProject, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    project.project_path = str(destination.resolve())
    project.modified_at = datetime.now().isoformat(timespec="seconds")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_project(source: str | Path) -> VideoProject:
    source = Path(source)
    project = VideoProject.from_dict(json.loads(source.read_text(encoding="utf-8")))
    project.project_path = str(source.resolve())
    return project


def package_project(project: VideoProject, destination: str | Path) -> Path:
    destination = Path(destination)
    media_dir = destination / "media"
    music_dir = destination / "music"
    media_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)
    clone = VideoProject.from_dict(project.to_dict())
    for index, item in enumerate(clone.items, 1):
        source = Path(item.source_path)
        target = media_dir / f"{index:04d}_{source.name}"
        shutil.copy2(source, target)
        item.source_path = str(Path("media") / target.name)
    for index, track in enumerate(clone.music, 1):
        source = Path(track.source_path)
        target = music_dir / f"{index:02d}_{source.name}"
        shutil.copy2(source, target)
        track.source_path = str(Path("music") / target.name)
    clone.project_path = None
    return save_project(clone, destination / "project.retirevideo")


def resolve_project_paths(project: VideoProject) -> None:
    if not project.project_path:
        return
    root = Path(project.project_path).parent
    for item in project.items:
        if not Path(item.source_path).is_absolute():
            item.source_path = str((root / item.source_path).resolve())
    for track in project.music:
        if not Path(track.source_path).is_absolute():
            track.source_path = str((root / track.source_path).resolve())

