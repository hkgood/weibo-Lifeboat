from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .style import apply_app_style
from pathlib import Path


def main() -> int:
    # 在打包环境中设置日志文件
    if getattr(sys, 'frozen', False):
        # 根据平台设置日志目录
        if sys.platform == "darwin":
            log_dir = Path.home() / "Library" / "Logs" / "WeiboLifeboat"
        elif sys.platform == "win32":
            log_dir = Path.home() / "AppData" / "Local" / "WeiboLifeboat" / "Logs"
        else:
            log_dir = Path.home() / ".weibo-lifeboat" / "logs"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        
        # 重定向 stdout 和 stderr 到日志文件
        log_handle = open(log_file, 'w', buffering=1, encoding='utf-8')
        sys.stdout = log_handle
        sys.stderr = log_handle
        
        print(f"=== Weibo Lifeboat Started at {datetime.now()} ===")
        print(f"Platform: {sys.platform}")
        print(f"Log file: {log_file}")
    
    print("[APP] Starting application...")
    app = QApplication(sys.argv)
    print("[APP] QApplication created")
    
    app.setApplicationName("微博逃生舱")
    app.setOrganizationName("weibo-backup")

    # Better macOS feel: rely on system theme/palette and enable HiDPI.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    apply_app_style(app)
    print("[APP] Styles applied")

    # App icon - 使用 PyInstaller 兼容的路径
    try:
        # PyInstaller 打包后的资源路径
        if getattr(sys, 'frozen', False):
            # 打包后的路径
            import os
            base_path = sys._MEIPASS
            icon_path = Path(base_path) / "assets" / "app_icon.png"
        else:
            # 开发环境路径
            icon_path = Path(__file__).resolve().parents[2] / "assets" / "app_icon.png"
        
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            print(f"[APP] Icon loaded from {icon_path}")
        else:
            print(f"[APP] Icon not found at {icon_path}")
    except Exception as e:
        print(f"[APP] Error loading icon: {e}")

    print("[APP] Creating MainWindow...")
    try:
        win = MainWindow()
        print("[APP] MainWindow created")
    except Exception as e:
        print(f"[APP] Error creating MainWindow: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    if 'icon_path' in locals() and icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))
    
    # 强制窗口显示并激活
    print("[APP] Showing window...")
    win.show()
    win.raise_()  # 将窗口提到最前
    win.activateWindow()  # 激活窗口
    print("[APP] Window shown, starting event loop...")
    
    result = app.exec()
    print(f"[APP] Event loop ended with code {result}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())


