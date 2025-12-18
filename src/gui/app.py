from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .style import apply_app_style
from pathlib import Path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("微博逃生舱")
    app.setOrganizationName("weibo-backup")

    # Better macOS feel: rely on system theme/palette and enable HiDPI.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    apply_app_style(app)

    # App icon (place your png at assets/app_icon.png)
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()
    if icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


