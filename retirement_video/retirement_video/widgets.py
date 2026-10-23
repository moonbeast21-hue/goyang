from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from .models import MediaItem, MediaType


class TimelineList(QListWidget):
    order_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(False)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QPixmap(120, 75).size())
        self.setMinimumHeight(155)
        self.model().rowsMoved.connect(lambda *_: self.order_changed.emit())

    def add_media(self, media: MediaItem) -> None:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, media.id)
        self.update_media(item, media)
        self.addItem(item)

    def update_media(self, item: QListWidgetItem, media: MediaItem) -> None:
        badge = "📷" if media.media_type == MediaType.PHOTO else "🎬"
        item.setText(f"{badge} {media.display_name}\n{media.duration:.1f}초 · {media.chapter}")
        item.setToolTip(f"{media.source_path}\n날짜: {media.capture_date or '미확인'} ({media.date_source})")
        if media.media_type == MediaType.PHOTO:
            pixmap = QPixmap(media.thumbnail_path) if media.thumbnail_path else QPixmap()
            if not pixmap.isNull():
                item.setIcon(pixmap.scaled(120, 75, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        item.setSizeHint(item.sizeHint().expandedTo(QPixmap(155, 125).size()))

