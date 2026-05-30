"""Generate arrow icons for combo boxes and spin boxes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap


def create_arrow_icon(direction: str, color: str, size: int = 12) -> QIcon:
    """Create an arrow icon pointing in the specified direction.

    Args:
        direction: Arrow direction ("up" or "down")
        color: Arrow color as hex string (e.g., "#cccccc")
        size: Icon size in pixels

    Returns:
        QIcon with the arrow
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen()
    pen.setColor(color)
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    center_x = size // 2
    if direction == "down":
        # Draw V shape pointing down
        y_top = size // 3
        y_bottom = size * 2 // 3
        painter.drawLine(size // 4, y_top, center_x, y_bottom)
        painter.drawLine(center_x, y_bottom, size * 3 // 4, y_top)
    elif direction == "up":
        # Draw ^ shape pointing up
        y_top = size // 3
        y_bottom = size * 2 // 3
        painter.drawLine(size // 4, y_bottom, center_x, y_top)
        painter.drawLine(center_x, y_top, size * 3 // 4, y_bottom)

    painter.end()
    return QIcon(pixmap)


def get_combo_arrow_icon(theme: str = "light") -> QIcon:
    """Get combo box down arrow icon for the specified theme."""
    color = "#333333" if theme == "light" else "#cccccc"
    return create_arrow_icon("down", color)


def get_spin_up_arrow_icon(theme: str = "light") -> QIcon:
    """Get spin box up arrow icon for the specified theme."""
    color = "#333333" if theme == "light" else "#cccccc"
    return create_arrow_icon("up", color)


def get_spin_down_arrow_icon(theme: str = "light") -> QIcon:
    """Get spin box down arrow icon for the specified theme."""
    color = "#333333" if theme == "light" else "#cccccc"
    return create_arrow_icon("down", color)
