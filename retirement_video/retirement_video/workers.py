from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .metadata import analyze_media
from .renderer import render_project


class ImportWorker(QObject):
    item_ready = Signal(object)
    progress = Signal(int, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, paths: list[str], root: str | None = None):
        super().__init__()
        self.paths = paths
        self.root = root
        self.cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            for index, path in enumerate(self.paths):
                if self.cancelled:
                    break
                self.item_ready.emit(analyze_media(path, self.root))
                self.progress.emit(int((index + 1) / len(self.paths) * 100), Path(path).name)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class RenderWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, project, destination: str):
        super().__init__()
        self.project = project
        self.destination = destination

    @Slot()
    def run(self) -> None:
        try:
            result = render_project(self.project, self.destination, lambda p, m: self.progress.emit(p, m))
            self.finished.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))

