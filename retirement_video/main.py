from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from retirement_video.main_window import MainWindow


def main() -> int:
    log_dir = Path.home() / ".retirement_video"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "application.log", level=logging.INFO, encoding="utf-8")
    app = QApplication(sys.argv)
    app.setApplicationName("퇴임식 기념영상 제작기")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
