from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QEvent
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
        
        # Install event filter on button to monitor state changes
        self.button.installEventFilter(self)
        self.button.destroyed.connect(self._on_button_destroyed)
        
    def _on_button_destroyed(self):
        """Handle button being destroyed"""
        self.button = None
    
    def eventFilter(self, obj, event):
        """Monitor button events to trigger repaint when needed"""
        if obj == self.button:
            # Repaint when button state changes
            if event.type() in (
                QEvent.Type.EnabledChange,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.Enter,
                QEvent.Type.Leave,
            ):
                # Use QTimer to defer update to avoid recursive paint events
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.update)
        return super().eventFilter(obj, event)
    
    def showEvent(self, event):
        """Force repaint when container becomes visible"""
        super().showEvent(event)
        self.update()
    
    def changeEvent(self, event):
        """Repaint when enabled state changes"""
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self.update()

    def paintEvent(self, event):
        """
        Draw shadow BEHIND the button.
        The button will draw itself normally on top.
        """
        painter = QPainter(self)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get button's geometry within container
        btn_rect = self.button.geometry() if self.button else self.rect()
        # Convert to QRectF for precise drawing
        btn_rectf = QRectF(btn_rect)
        
        # Draw shadow in all states (enabled, disabled, pressed)
        # Just adjust opacity based on state
        is_enabled = self.button.isEnabled() if self.button else False
        is_pressed = self.button.isDown() if self.button else False
        
        # Shadow parameters (matching sidebar tabs)
        shadow_blur = 8
        shadow_offset_x = 2
        shadow_offset_y = 2
        # Reduce opacity when disabled or pressed
        if not is_enabled:
            base_opacity = 0.01  # Lighter shadow for disabled state
        elif is_pressed:
            base_opacity = 0.015  # Slightly lighter when pressed
        else:
            base_opacity = 0.02  # Full shadow when enabled
        
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

