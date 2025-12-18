from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class TitleBar(QWidget):
    """
    Custom title bar for frameless window with window controls
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)  # macOS-like title bar height
        self.setStyleSheet("""
            TitleBar {
                background: #ECECEC;
                border-bottom: 1px solid rgba(60, 60, 67, 0.18);
            }
        """)
        
        # Track dragging
        self._drag_pos = QPoint()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        
        # Window controls (left side)
        self._btn_close = QPushButton()
        self._btn_minimize = QPushButton()
        self._btn_maximize = QPushButton()
        
        # Style the window control buttons (macOS style)
        btn_style = """
            QPushButton {
                background: #FF5F57;
                border: none;
                border-radius: 6px;
                width: 12px;
                height: 12px;
                min-width: 12px;
                max-width: 12px;
                min-height: 12px;
                max-height: 12px;
            }
            QPushButton:hover {
                background: #FF3B30;
            }
        """
        self._btn_close.setStyleSheet(btn_style)
        self._btn_close.clicked.connect(self._close_window)
        
        btn_style_minimize = """
            QPushButton {
                background: #FFBD2E;
                border: none;
                border-radius: 6px;
                width: 12px;
                height: 12px;
                min-width: 12px;
                max-width: 12px;
                min-height: 12px;
                max-height: 12px;
            }
            QPushButton:hover {
                background: #FF9500;
            }
        """
        self._btn_minimize.setStyleSheet(btn_style_minimize)
        self._btn_minimize.clicked.connect(self._minimize_window)
        
        btn_style_maximize = """
            QPushButton {
                background: #28C840;
                border: none;
                border-radius: 6px;
                width: 12px;
                height: 12px;
                min-width: 12px;
                max-width: 12px;
                min-height: 12px;
                max-height: 12px;
            }
            QPushButton:hover {
                background: #00C200;
            }
        """
        self._btn_maximize.setStyleSheet(btn_style_maximize)
        self._btn_maximize.clicked.connect(self._toggle_maximize)
        
        # Add buttons to layout
        layout.addWidget(self._btn_close)
        layout.addWidget(self._btn_minimize)
        layout.addWidget(self._btn_maximize)
        layout.addSpacing(8)
        
        # Title (centered)
        self._title_label = QLabel("微博逃生舱")
        self._title_label.setStyleSheet("""
            QLabel {
                color: #1d1d1f;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
        """)
        layout.addStretch(1)
        layout.addWidget(self._title_label)
        layout.addStretch(1)
        
        # Right spacer to balance the left controls
        right_spacer = QWidget()
        right_spacer.setFixedWidth(12 * 3 + 8 * 2 + 8)  # Same width as left controls
        layout.addWidget(right_spacer)
    
    def set_title(self, title: str):
        """Set window title"""
        self._title_label.setText(title)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging the window"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Drag the window"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-click to maximize/restore"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
    
    def _close_window(self):
        """Close the window"""
        self.window().close()
    
    def _minimize_window(self):
        """Minimize the window"""
        self.window().showMinimized()
    
    def _toggle_maximize(self):
        """Toggle maximize/restore window"""
        if self.window().isMaximized():
            self.window().showNormal()
        else:
            self.window().showMaximized()

