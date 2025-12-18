from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QRect, Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QPixmap, QPen, QBrush, QColor, QPainterPath, QFont
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PySide6.QtCore import QModelIndex


class SidebarItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for sidebar items:
    Fully custom paint to control all aspects (background, border, dot, text positioning)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Load dot images
        assets_dir = Path(__file__).parent.parent.parent / "assets"
        self.dot_gray = QPixmap(str(assets_dir / "dot_gray.svg"))
        self.dot_orange = QPixmap(str(assets_dir / "dot_orange.svg"))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Determine state
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hover = option.state & QStyle.StateFlag.State_MouseOver
        
        # Colors (matching QSS theme)
        bg_color = QColor("#FCFCFC") if is_selected else QColor("#F4F4F4")
        border_color = QColor(255, 255, 255, int(0.18 * 255))
        border_selected = QColor(255, 255, 255, int(0.18 * 255))
        text_color = QColor("#1d1d1f")
        
        rect = QRectF(option.rect)
        radius = 6.0
        
        # Shadow base rect: 4px smaller than button (2px inset on each side)
        shadow_base_rect = rect.adjusted(8, 8, -4, -4)
        
        # Draw shadow with offset left and down
        # Create multiple concentric rounded rectangles with decreasing opacity
        shadow_blur = 12 if (is_hover or is_selected) else 12
        shadow_offset_x = 2  # Move right 2px
        shadow_offset_y = 2   # Move down 2px
        base_opacity = 0.015   # Base opacity
        
        # Draw shadow layers from outer to inner for proper blending
        for i in range(shadow_blur, 0, -1):
            # Calculate opacity for this layer (gaussian-like falloff)
            layer_opacity = base_opacity * (1.0 - (i / shadow_blur) ** 2)
            shadow_color = QColor(0, 0, 0, int(layer_opacity * 255))
            
            # Shadow rectangle expands outward from the smaller base and shifts
            shadow_rect = shadow_base_rect.adjusted(
                -i + shadow_offset_x, 
                -i + shadow_offset_y, 
                i + shadow_offset_x, 
                i + shadow_offset_y
            )
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, radius + i * 0.5, radius + i * 0.5)
            painter.fillPath(shadow_path, QBrush(shadow_color))
        
        # Draw background
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QBrush(bg_color))
        
        # Draw border
        painter.setPen(QPen(border_selected if is_selected else border_color, 1.0))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        
        # Draw dot
        dot = self.dot_orange if is_selected else self.dot_gray
        if not dot.isNull():
            # Draw at bottom-left (background-position: left bottom)
            dot_x = rect.left()
            dot_y = rect.bottom() - dot.height()
            painter.drawPixmap(int(dot_x), int(dot_y), dot)
        
        # Draw text (top-left aligned, 12px from edges)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text:
            # Set text color
            painter.setPen(QPen(text_color))
            
            # Set font
            font = option.font
            font.setPixelSize(14)
            if is_selected:
                font.setWeight(QFont.Weight.DemiBold)  # 600
            else:
                font.setWeight(QFont.Weight.Normal)    # 400
            painter.setFont(font)
            
            text_rect = QRect(
                option.rect.left() + 12,
                option.rect.top() + 12,
                option.rect.width() - 24,
                option.rect.height() - 24
            )
            
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
                text
            )
        
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # Return fixed size: height increased by 20 (60 -> 80)
        return QSize(option.rect.width(), 80)

