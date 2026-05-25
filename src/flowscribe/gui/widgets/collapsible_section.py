"""Reusable collapsible section widget for compact control panels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A simple collapsible section with a toggle button and content area."""

    def __init__(
        self,
        title: str,
        *,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._toggle_button = QToolButton(self)
        self._toggle_button.setText(title)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(expanded)
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._toggle_button.toggled.connect(self._on_toggled)
        self._toggle_button.setProperty("role", "ghost")
        self._toggle_button.setProperty("sectionToggle", True)

        self._content_widget = QWidget(self)
        self._content_widget.setVisible(expanded)
        self._content_widget.setProperty("card", True)
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)
        root_layout.addWidget(self._toggle_button)
        root_layout.addWidget(self._content_widget)

    @property
    def content_layout(self) -> QVBoxLayout:
        """Return the layout used for the collapsible content."""
        return self._content_layout

    def set_expanded(self, expanded: bool) -> None:
        """Update the expanded state."""
        self._toggle_button.setChecked(expanded)

    def is_expanded(self) -> bool:
        """Return whether the section is expanded."""
        return self._toggle_button.isChecked()

    def _on_toggled(self, expanded: bool) -> None:
        self._toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._content_widget.setVisible(expanded)
