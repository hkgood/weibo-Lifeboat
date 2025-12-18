from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PySide6.QtWidgets import QPushButton


class ShadowButton(QPushButton):
    """
    QPushButton with subtle shadow effect (similar to sidebar tabs)
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        # Track hover state properly instead of using underMouse() in paintEvent
        self._is_hover = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        """Track hover state on enter"""
        self._is_hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Track hover state on leave"""
        self._is_hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        # Use save/restore instead of end() - this is the delegate pattern
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get state (use tracked hover state instead of underMouse())
        is_enabled = self.isEnabled()
        is_down = self.isDown()
        is_hover = self._is_hover
        is_primary = self.objectName() == "PrimaryButton"
        
        # Colors based on theme (matching style.py)
        if is_primary:
            if not is_enabled:
                bg_color = QColor("#FF4A00")
                bg_color.setAlphaF(0.4)
            elif is_down:
                bg_color = QColor("#005FCC")
            elif is_hover:
                bg_color = QColor("#006FE6")
            else:
                bg_color = QColor("#007AFF")
            border_color = QColor(0, 0, 0, int(0.08 * 255))
            text_color = QColor(255, 255, 255)
        else:
            if not is_enabled:
                bg_color = QColor(255, 255, 255, 80)
            elif is_down:
                bg_color = QColor("#EEF2F7")
            elif is_hover:
                bg_color = QColor("#F1F5F9")
            else:
                bg_color = QColor("#F4F4F4")
            border_color = QColor(60, 60, 67, int(0.18 * 255))
            text_color = QColor("#1d1d1f") if is_enabled else QColor(60, 60, 67, 128)
        
        rect = QRectF(self.rect())
        radius = 6.0
        
        # Only draw shadow if enabled and not pressed
        if is_enabled and not is_down:
            # Shadow base rect: 4px smaller than button (2px inset on each side)
            shadow_base_rect = rect.adjusted(2, 2, -2, -2)
            
            # Draw shadow with offset right and down
            shadow_blur = 12 if (is_hover or is_primary) else 12
            shadow_offset_x = 2  # Move right 2px
            shadow_offset_y = 2  # Move down 2px
            base_opacity = 0.01  # Base opacity
            
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
        painter.setPen(QPen(border_color, 1.0))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        
        # Draw text
        text = self.text()
        if text:
            painter.setPen(QPen(text_color))
            font = self.font()
            if is_primary:
                font.setWeight(600)
            painter.setFont(font)
            
            painter.drawText(
                rect.toRect(),
                int(Qt.AlignmentFlag.AlignCenter),
                text
            )
        
        # Use restore() instead of end() - safer and follows delegate pattern
        painter.restore()

