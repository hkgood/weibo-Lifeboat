from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QBrush, QColor, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class ShadowContainer(QWidget):
    """
    Container widget that draws shadow and contains a button.
    The button itself uses standard QPushButton - no custom paintEvent.
    This is safe because we only customize the container, not the button.
    """

    def __init__(self, button: QPushButton, parent=None):
        super().__init__(parent)
        self.button = button
        
        # Setup layout with padding for shadow
        layout = QVBoxLayout(self)
        # Asymmetric padding: shadow is offset right+down, so need more space on right/bottom
        # Left/Top: blur - offset = 8 - 2 = 6px
        # Right/Bottom: blur + offset = 8 + 2 = 10px
        layout.setContentsMargins(2, 2, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(button)
        
        # Make container transparent so shadow shows through
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAutoFillBackground(False)

    def paintEvent(self, event):
        """
        Draw shadow BEHIND the button.
        The button will draw itself normally on top.
        """
        painter = QPainter(self)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get button's geometry within container
        btn_rect = self.button.geometry()
        # Convert to QRectF for precise drawing
        btn_rectf = QRectF(btn_rect)
        
        # Only draw shadow if button is enabled
        if self.button.isEnabled() and not self.button.isDown():
            # Shadow parameters (matching sidebar tabs)
            shadow_blur = 8
            shadow_offset_x = 2
            shadow_offset_y = 2
            base_opacity = 0.02
            radius = 6.0
            
            # Shadow base rect: 2px smaller than button (1px inset on each side)
            shadow_base_rect = btn_rectf.adjusted(1, 1, -1, -1)
            
            # Draw shadow layers from outer to inner
            for i in range(shadow_blur, 0, -1):
                # Calculate opacity for this layer (gaussian-like falloff)
                layer_opacity = base_opacity * (1.0 - (i / shadow_blur) ** 2)
                shadow_color = QColor(0, 0, 0, int(layer_opacity * 255))
                
                # Shadow rectangle expands outward and shifts
                shadow_rect = shadow_base_rect.adjusted(
                    -i + shadow_offset_x,
                    -i + shadow_offset_y,
                    i + shadow_offset_x,
                    i + shadow_offset_y
                )
                shadow_path = QPainterPath()
                shadow_path.addRoundedRect(shadow_rect, radius + i * 0.5, radius + i * 0.5)
                painter.fillPath(shadow_path, QBrush(shadow_color))
        
        painter.restore()
        # Don't call super().paintEvent() - we want transparent background


def create_shadow_button(text: str, parent=None) -> tuple[ShadowContainer, QPushButton]:
    """
    Helper function to create a button with shadow.
    
    Returns:
        (container, button) - Use container.button to access the actual button
    """
    button = QPushButton(text, parent)
    container = ShadowContainer(button, parent)
    return container, button

