"""Icon gallery - displays all available icons for testing.

Run this script to see all available icons in both light and dark themes.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.icons import get_icon, get_icon_names
from flowscribe.gui.theme_manager import apply_theme


class IconGallery(QMainWindow):
    """Window displaying all available icons."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowScribe Icon Gallery")
        self.resize(800, 600)

        # Main widget
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Light theme group
        light_group = QGroupBox("Light Theme")
        light_layout = QGridLayout(light_group)
        self._populate_icons(light_layout, "light")
        content_layout.addWidget(light_group)

        # Dark theme group
        dark_group = QGroupBox("Dark Theme")
        dark_layout = QGridLayout(dark_group)
        self._populate_icons(dark_layout, "dark")
        content_layout.addWidget(dark_group)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.setCentralWidget(main_widget)

    def _populate_icons(self, layout: QGridLayout, theme: str) -> None:
        """Populate grid with icons."""
        icon_names = get_icon_names()
        cols = 4
        for i, name in enumerate(icon_names):
            row = i // cols
            col = i % cols

            # Icon label
            icon = get_icon(name, theme, size=32)
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(32, 32))

            # Name label
            name_label = QLabel(name)

            # Container
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.addWidget(icon_label)
            container_layout.addWidget(name_label)
            container_layout.setSpacing(4)

            layout.addWidget(container, row, col)


def main():
    """Run icon gallery."""
    app = QApplication(sys.argv)

    # Apply light theme by default
    apply_theme(app, "light")

    gallery = IconGallery()
    gallery.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
