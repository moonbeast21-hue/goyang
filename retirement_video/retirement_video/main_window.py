from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDateTimeEdit, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QInputDialog, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSlider, QSpinBox,
    QDoubleSpinBox, QSplitter, QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

from .audio import analyze_music
from .auto_editor import auto_edit, sort_by_date
from .metadata import AUDIO_EXTENSIONS, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS, collect_media
from .models import DatePrecision, MusicTrack, VideoProject
from .project_io import load_project, package_project, resolve_project_paths, save_project
from .thumbnails import create_thumbnail
from .widgets import TimelineList
from .workers import ImportWorker, RenderWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = VideoProject()
        self.undo_stack: list[VideoProject] = []
        self.redo_stack: list[VideoProject] = []
        self.settings = QSettings("RetirementVideo", "RetirementVideoMaker")
        self.worker_thread: QThread | None = None
        self.import_worker: ImportWorker | None = None
        self.render_worker: RenderWorker | None = None
        self.render_progress: QProgressDialog | None = None
        self.setWindowTitle("퇴임식 기념영상 제작기")
        self.resize(1440, 900)
        self.setAcceptDrops(True)
        self._build_actions()
        self._build_ui()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(60_000)
        self._refresh_all()

    def _build_actions(self) -> None:
        definitions = [
            ("새 프로젝트", self.new_project, QKeySequence.New),
            ("프로젝트 열기", self.open_project, QKeySequence.Open),
            ("프로젝트 저장", self.save_project, QKeySequence.Save),
            ("미디어 불러오기", self.import_files, "Ctrl+I"),
            ("폴더 불러오기", self.import_folder, "Ctrl+Shift+I"),
            ("촬영 날짜순 정렬", self.sort_items, None),
            ("음악에 맞춰 자동 편집", self.run_auto_edit, "Ctrl+E"),
            ("MP4 출력", self.export_video, "Ctrl+R"),
        ]
        self.actions = {}
        menu = self.menuBar().addMenu("파일")
        toolbar = QToolBar("주요 기능", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, callback, shortcut in definitions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(shortcut)
            self.actions[text] = action
            toolbar.addAction(action)
            if text in {"새 프로젝트", "프로젝트 열기", "프로젝트 저장", "미디어 불러오기", "MP4 출력"}:
                menu.addAction(action)
        menu.addSeparator()
        package = menu.addAction("프로젝트 패키징")
        package.triggered.connect(self.package_project)
        edit = self.menuBar().addMenu("편집")
        undo = edit.addAction("실행 취소")
        undo.setShortcut(QKeySequence.Undo)
        undo.triggered.connect(self.undo)
        redo = edit.addAction("다시 실행")
        redo.setShortcut(QKeySequence.Redo)
        redo.triggered.connect(self.redo)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        upper = QSplitter(Qt.Horizontal)
        upper.addWidget(self._media_panel())
        upper.addWidget(self._preview_panel())
        upper.addWidget(self._properties_panel())
        upper.setSizes([360, 650, 340])
        layout.addWidget(upper, 1)
        self.timeline = TimelineList()
        self.timeline.currentItemChanged.connect(self._timeline_selection)
        self.timeline.order_changed.connect(self._sync_order)
        layout.addWidget(QLabel("타임라인 — 끌어서 순서를 바꿀 수 있습니다"))
        layout.addWidget(self.timeline)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

    def _media_panel(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.search = QLineEdit(); self.search.setPlaceholderText("파일명·챕터 검색")
        self.search.textChanged.connect(self._filter_media)
        self.media_table = QTableWidget(0, 5)
        self.media_table.setHorizontalHeaderLabels(["파일", "날짜", "출처", "챕터", "중요도"])
        self.media_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.media_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.media_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.media_table.itemSelectionChanged.connect(self._table_selection)
        buttons = QHBoxLayout()
        add = QPushButton("파일 추가"); add.clicked.connect(self.import_files)
        remove = QPushButton("선택 삭제"); remove.clicked.connect(self.remove_selected)
        date = QPushButton("날짜 수정"); date.clicked.connect(self.edit_date)
        buttons.addWidget(add); buttons.addWidget(remove); buttons.addWidget(date)
        layout.addWidget(self.search); layout.addWidget(self.media_table); layout.addLayout(buttons)
        return widget

    def _preview_panel(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.preview = QLabel("미디어를 불러오세요")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#111827;color:#e5e7eb;border-radius:6px;min-height:360px")
        self.preview.setScaledContents(False)
        self.preview_caption = QLabel(""); self.preview_caption.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview, 1); layout.addWidget(self.preview_caption)
        return widget

    def _properties_panel(self) -> QWidget:
        tabs = QTabWidget()
        photo = QWidget(); form = QFormLayout(photo)
        self.duration = QDoubleSpinBox(); self.duration.setRange(1, 15); self.duration.setSuffix(" 초"); self.duration.setSingleStep(.5)
        self.transition = QComboBox(); self.transition.addItems(["효과 없음", "페이드", "크로스 디졸브", "좌우 슬라이드", "상하 슬라이드", "부드러운 확대", "부드러운 축소", "Ken Burns"])
        self.importance = QComboBox(); self.importance.addItems(["일반", "중요", "하이라이트"])
        self.chapter = QLineEdit(); self.subtitle = QTextEdit(); self.subtitle.setMaximumHeight(80)
        rotate_row = QHBoxLayout()
        rotate_left = QPushButton("↶ 왼쪽 90°"); rotate_left.clicked.connect(lambda: self.rotate_selected(90))
        rotate_right = QPushButton("↷ 오른쪽 90°"); rotate_right.clicked.connect(lambda: self.rotate_selected(-90))
        rotate_180 = QPushButton("↕ 180°"); rotate_180.clicked.connect(lambda: self.rotate_selected(180))
        rotate_row.addWidget(rotate_left); rotate_row.addWidget(rotate_right); rotate_row.addWidget(rotate_180)
        rotate_widget = QWidget(); rotate_widget.setLayout(rotate_row)
        apply_photo = QPushButton("선택 항목에 적용"); apply_photo.clicked.connect(self.apply_properties)
        form.addRow("재생시간", self.duration); form.addRow("전환", self.transition); form.addRow("중요도", self.importance)
        form.addRow("사진 회전", rotate_widget); form.addRow("챕터", self.chapter); form.addRow("자막", self.subtitle); form.addRow(apply_photo)
        music = QWidget(); music_form = QFormLayout(music)
        self.music_label = QLabel("선택된 음악 없음")
        choose_music = QPushButton("음악 선택 및 분석"); choose_music.clicked.connect(self.choose_music)
        self.music_volume = QSlider(Qt.Horizontal); self.music_volume.setRange(0, 100); self.music_volume.setValue(65)
        self.bpm_label = QLabel("-")
        music_form.addRow("음악", self.music_label); music_form.addRow(choose_music); music_form.addRow("배경음악 볼륨", self.music_volume); music_form.addRow("분석 BPM", self.bpm_label)
        text_tab = QWidget(); text_form = QFormLayout(text_tab)
        self.intro_text = QLineEdit()
        self.ending_text1 = QLineEdit()
        self.ending_text2 = QLineEdit()
        save_text = QPushButton("시작·마지막 문구 적용")
        save_text.clicked.connect(self.apply_text_settings)
        text_help = QLabel("사진별 자막과 챕터 제목은 ‘사진/영상’ 탭에서 선택 항목마다 수정합니다.")
        text_help.setWordWrap(True)
        text_form.addRow("시작 화면", self.intro_text)
        text_form.addRow("마지막 문구 1", self.ending_text1)
        text_form.addRow("마지막 문구 2", self.ending_text2)
        text_form.addRow(save_text)
        text_form.addRow(text_help)
        auto = QWidget(); auto_form = QFormLayout(auto)
        self.style = QComboBox(); self.style.addItems(["감동적인 퇴임식", "밝고 즐거운 퇴임식", "영화 같은 추억 영상", "사용자 직접 설정"])
        self.style.setCurrentText("밝고 즐거운 퇴임식")
        self.min_duration = QDoubleSpinBox(); self.min_duration.setRange(1, 15); self.min_duration.setValue(2.5)
        self.max_duration = QDoubleSpinBox(); self.max_duration.setRange(1, 15); self.max_duration.setValue(6)
        self.sync = QSlider(Qt.Horizontal); self.sync.setRange(0, 100); self.sync.setValue(70)
        self.target_minutes = QDoubleSpinBox(); self.target_minutes.setRange(0, 60); self.target_minutes.setValue(0); self.target_minutes.setSpecialValueText("자동")
        run = QPushButton("음악에 맞춰 자동 편집"); run.clicked.connect(self.run_auto_edit)
        auto_form.addRow("스타일", self.style); auto_form.addRow("목표 길이(분)", self.target_minutes)
        auto_form.addRow("최소 재생시간", self.min_duration); auto_form.addRow("최대 재생시간", self.max_duration)
        auto_form.addRow("음악 동기화", self.sync); auto_form.addRow(run)
        tabs.addTab(photo, "사진/영상"); tabs.addTab(music, "음악"); tabs.addTab(text_tab, "자막/문구"); tabs.addTab(auto, "자동 편집")
        return tabs

    def _snapshot(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.project)); self.undo_stack = self.undo_stack[-30:]; self.redo_stack.clear()

    def _item_by_id(self, item_id: str):
        return next((x for x in self.project.items if x.id == item_id), None)

    def _selected_ids(self) -> list[str]:
        return [self.media_table.item(row, 0).data(Qt.UserRole) for row in sorted({x.row() for x in self.media_table.selectedItems()})]

    def _refresh_all(self) -> None:
        self.media_table.setUpdatesEnabled(False); self.timeline.setUpdatesEnabled(False)
        self.media_table.setRowCount(0); self.timeline.clear()
        for media in self.project.items:
            row = self.media_table.rowCount(); self.media_table.insertRow(row)
            values = [media.display_name, media.capture_date[:10] if media.capture_date else "미확인", media.date_source, media.chapter, media.importance]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value); cell.setData(Qt.UserRole, media.id); self.media_table.setItem(row, col, cell)
            self.timeline.add_media(media)
        self.media_table.setUpdatesEnabled(True); self.timeline.setUpdatesEnabled(True)
        if self.project.music:
            track = self.project.music[0]; self.music_label.setText(Path(track.source_path).name); self.bpm_label.setText(str(track.bpm or "-")); self.music_volume.setValue(int(track.volume * 100))
        self.intro_text.setText(self.project.settings.title)
        self.ending_text1.setText(self.project.settings.ending_line1)
        self.ending_text2.setText(self.project.settings.ending_line2)
        self.statusBar().showMessage(f"미디어 {len(self.project.items)}개 · 예상 길이 {sum(x.duration for x in self.project.items):.1f}초")

    def import_files(self) -> None:
        extensions = " ".join(f"*{x}" for x in sorted(PHOTO_EXTENSIONS | VIDEO_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(self, "사진 및 동영상 불러오기", "", f"미디어 ({extensions})")
        if paths: self._start_import(paths)

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "미디어 폴더 선택")
        if folder:
            paths = [str(x) for x in collect_media(folder)]
            if paths: self._start_import(paths, folder)

    def _start_import(self, paths: list[str], root: str | None = None) -> None:
        existing = {x.content_hash for x in self.project.items}; self._snapshot()
        progress = QProgressDialog("미디어 분석 중", "취소", 0, 100, self); progress.setWindowModality(Qt.WindowModal)
        thread = QThread(self); worker = ImportWorker(paths, root); worker.moveToThread(thread)
        self.import_worker = worker
        def add(item):
            if item.content_hash not in existing:
                existing.add(item.content_hash); self.project.items.append(item)
        worker.item_ready.connect(add); worker.progress.connect(lambda p, m: (progress.setValue(p), progress.setLabelText(m)))
        worker.failed.connect(lambda m: QMessageBox.critical(self, "불러오기 오류", m))
        worker.finished.connect(lambda: (progress.close(), self._refresh_all(), thread.quit()))
        progress.canceled.connect(lambda: setattr(worker, "cancelled", True)); thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: setattr(self, "import_worker", None))
        thread.finished.connect(thread.deleteLater)
        self.worker_thread = thread; thread.start()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        files: list[str] = []
        for path in paths:
            files.extend(str(x) for x in collect_media(path)) if path.is_dir() else files.append(str(path))
        supported = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
        files = [x for x in files if Path(x).suffix.lower() in supported]
        if files: self._start_import(files, str(paths[0]) if len(paths) == 1 and paths[0].is_dir() else None)

    def _table_selection(self) -> None:
        ids = self._selected_ids()
        if ids: self._show_item(self._item_by_id(ids[0]))

    def _timeline_selection(self, current, previous) -> None:
        if current: self._show_item(self._item_by_id(current.data(Qt.UserRole)))

    def _show_item(self, media) -> None:
        if not media: return
        self.duration.setValue(media.duration); self.transition.setCurrentText(media.transition)
        self.importance.setCurrentText(media.importance); self.chapter.setText(media.chapter); self.subtitle.setPlainText(media.subtitle)
        self.preview_caption.setText(f"{media.display_name} · {media.capture_date or '날짜 미확인'} · {media.chapter}")
        pixmap = QPixmap(media.thumbnail_path or media.source_path)
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not pixmap.isNull() else self.preview.setText("동영상 미리보기는 출력 영상에서 확인하세요")

    def apply_properties(self) -> None:
        ids = self._selected_ids()
        if not ids and self.timeline.currentItem(): ids = [self.timeline.currentItem().data(Qt.UserRole)]
        if not ids: return
        self._snapshot()
        for item_id in ids:
            item = self._item_by_id(item_id); item.duration = self.duration.value(); item.transition = self.transition.currentText()
            item.importance = self.importance.currentText(); item.chapter = self.chapter.text().strip() or "날짜 미확인"; item.subtitle = self.subtitle.toPlainText()
        self._refresh_all()

    def rotate_selected(self, degrees: int) -> None:
        ids = self._selected_ids()
        if not ids and self.timeline.currentItem():
            ids = [self.timeline.currentItem().data(Qt.UserRole)]
        photos = [self._item_by_id(item_id) for item_id in ids]
        photos = [item for item in photos if item and item.media_type.value == "photo"]
        if not photos:
            QMessageBox.information(self, "사진 회전", "회전할 사진을 먼저 선택하세요.")
            return
        self._snapshot()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for item in photos:
                item.rotation = (item.rotation + degrees) % 360
                item.thumbnail_path = create_thumbnail(item)
        finally:
            QApplication.restoreOverrideCursor()
        self._refresh_all()
        self._show_item(photos[0])

    def apply_text_settings(self) -> None:
        title = self.intro_text.text().strip()
        ending1 = self.ending_text1.text().strip()
        ending2 = self.ending_text2.text().strip()
        if not title or not ending1:
            QMessageBox.warning(self, "문구 입력", "시작 화면과 마지막 문구 1은 비워둘 수 없습니다.")
            return
        self._snapshot()
        self.project.settings.title = title
        self.project.settings.ending_line1 = ending1
        self.project.settings.ending_line2 = ending2
        self.statusBar().showMessage("시작·마지막 문구를 적용했습니다.", 5000)

    def remove_selected(self) -> None:
        ids = set(self._selected_ids())
        if ids: self._snapshot(); self.project.items = [x for x in self.project.items if x.id not in ids]; self._refresh_all()

    def edit_date(self) -> None:
        ids = self._selected_ids()
        if not ids: return
        dialog = QDialog(self); dialog.setWindowTitle("촬영 날짜 수정"); form = QFormLayout(dialog)
        date = QDateTimeEdit(datetime.now()); date.setCalendarPopup(True); precision = QComboBox(); precision.addItems(["일", "월", "연도"])
        ok = QPushButton("적용"); ok.clicked.connect(dialog.accept); form.addRow("날짜", date); form.addRow("정밀도", precision); form.addRow(ok)
        if dialog.exec():
            self._snapshot(); mapping = {"일": DatePrecision.DAY, "월": DatePrecision.MONTH, "연도": DatePrecision.YEAR}
            for item_id in ids:
                item = self._item_by_id(item_id); item.capture_date = date.dateTime().toPython().isoformat(timespec="seconds"); item.date_precision = mapping[precision.currentText()]; item.date_source = "사용자 입력"
            self._refresh_all()

    def _sync_order(self) -> None:
        order = [self.timeline.item(i).data(Qt.UserRole) for i in range(self.timeline.count())]
        by_id = {x.id: x for x in self.project.items}; self.project.items = [by_id[x] for x in order]
        self._refresh_all()

    def sort_items(self) -> None:
        self._snapshot(); sort_by_date(self.project); self._refresh_all()

    def choose_music(self) -> None:
        extensions = " ".join(f"*{x}" for x in sorted(AUDIO_EXTENSIONS))
        path, _ = QFileDialog.getOpenFileName(self, "배경음악 선택", "", f"음악 ({extensions})")
        if not path: return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            analysis = analyze_music(path, Path.home() / ".retirement_video" / "audio_cache")
            self._snapshot(); self.project.music = [MusicTrack(path, volume=self.music_volume.value()/100, bpm=analysis["bpm"], beats=analysis["beats"], duration=analysis["duration"])]
            self.music_label.setText(Path(path).name); self.bpm_label.setText(f"{analysis['bpm']:.1f}")
        except Exception as exc: QMessageBox.critical(self, "음악 분석 오류", str(exc))
        finally: QApplication.restoreOverrideCursor()

    def run_auto_edit(self) -> None:
        if not self.project.items: return
        self._snapshot(); s = self.project.settings; s.style = self.style.currentText(); s.min_duration = self.min_duration.value(); s.max_duration = self.max_duration.value(); s.sync_strength = self.sync.value(); s.target_seconds = round(self.target_minutes.value()*60) or None
        if self.project.music: self.project.music[0].volume = self.music_volume.value()/100
        warnings = auto_edit(self.project); self._refresh_all()
        QMessageBox.information(self, "자동 편집 완료", "타임라인 초안을 만들었습니다." + ("\n\n" + "\n".join(warnings) if warnings else ""))

    def new_project(self) -> None:
        if self.project.items and QMessageBox.question(self, "새 프로젝트", "현재 작업을 닫고 새 프로젝트를 만드시겠습니까?") != QMessageBox.Yes: return
        self.project = VideoProject(); self.undo_stack.clear(); self.redo_stack.clear(); self._refresh_all()

    def save_project(self) -> None:
        path = self.project.project_path
        if not path: path, _ = QFileDialog.getSaveFileName(self, "프로젝트 저장", "퇴임식영상.retirevideo", "퇴임식 프로젝트 (*.retirevideo)")
        if path: save_project(self.project, path); self.statusBar().showMessage(f"저장 완료: {path}", 5000)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "프로젝트 열기", "", "퇴임식 프로젝트 (*.retirevideo)")
        if path:
            self.project = load_project(path); resolve_project_paths(self.project); self.undo_stack.clear(); self.redo_stack.clear(); self._refresh_all()

    def package_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "패키지 저장 폴더")
        if folder:
            try: result = package_project(self.project, Path(folder) / self.project.name); QMessageBox.information(self, "패키징 완료", str(result))
            except Exception as exc: QMessageBox.critical(self, "패키징 오류", str(exc))

    def export_video(self) -> None:
        if not self.project.items: QMessageBox.warning(self, "출력", "먼저 미디어를 불러오세요."); return
        quality, accepted = QInputDialog.getItem(
            self, "출력 방식", "출력 품질을 선택하세요.",
            ["빠른 출력 (1280×720, 권장)", "Full HD 출력 (1920×1080)"], 0, False,
        )
        if not accepted: return
        path, _ = QFileDialog.getSaveFileName(self, "MP4 출력", "퇴임식_기념영상.mp4", "MP4 영상 (*.mp4)")
        if not path: return
        render_project_copy = copy.deepcopy(self.project)
        if quality.startswith("빠른"):
            render_project_copy.settings.width = 1280; render_project_copy.settings.height = 720
            render_project_copy.settings.fps = 24; render_project_copy.settings.encoder_preset = "superfast"
        else:
            render_project_copy.settings.width = 1920; render_project_copy.settings.height = 1080
            render_project_copy.settings.fps = 30; render_project_copy.settings.encoder_preset = "veryfast"
        progress = QProgressDialog("출력 작업을 시작하는 중", "", 0, 100, self); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModal); progress.setMinimumDuration(0); progress.show()
        self.render_progress = progress
        thread = QThread(self); worker = RenderWorker(render_project_copy, path); worker.moveToThread(thread)
        self.render_worker = worker
        worker.progress.connect(self._render_progress_changed)
        worker.failed.connect(self._render_failed)
        worker.finished.connect(self._render_finished)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: setattr(self, "render_worker", None))
        thread.finished.connect(thread.deleteLater)
        self.worker_thread = thread; thread.start()

    def _render_progress_changed(self, percent: int, message: str) -> None:
        if self.render_progress:
            self.render_progress.setLabelText(message)
            self.render_progress.setValue(percent)

    def _render_failed(self, message: str) -> None:
        if self.render_progress:
            self.render_progress.close()
            self.render_progress = None
        if self.worker_thread:
            self.worker_thread.quit()
        QMessageBox.critical(self, "출력 오류", message)

    def _render_finished(self, path: str) -> None:
        if self.render_progress:
            self.render_progress.close()
            self.render_progress = None
        if self.worker_thread:
            self.worker_thread.quit()
        QMessageBox.information(self, "출력 완료", f"영상이 저장되었습니다.\n{path}")

    def _filter_media(self, text: str) -> None:
        text = text.casefold()
        for row in range(self.media_table.rowCount()):
            self.media_table.setRowHidden(row, text not in " ".join(self.media_table.item(row, c).text() for c in range(5)).casefold())

    def undo(self) -> None:
        if self.undo_stack: self.redo_stack.append(copy.deepcopy(self.project)); self.project = self.undo_stack.pop(); self._refresh_all()

    def redo(self) -> None:
        if self.redo_stack: self.undo_stack.append(copy.deepcopy(self.project)); self.project = self.redo_stack.pop(); self._refresh_all()

    def _autosave(self) -> None:
        if self.project.items:
            try: save_project(copy.deepcopy(self.project), Path.home() / ".retirement_video" / "autosave.retirevideo")
            except OSError: pass

    def closeEvent(self, event) -> None:
        self._autosave(); event.accept()

