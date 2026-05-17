"""Drag-drop source file list widget for the GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget

from flowscribe.gui.state import is_acceptable_local_source


def dropped_local_paths(event) -> list[Path]:
    """Extract acceptable local file/folder paths from a drag-drop event."""
    if not event.mimeData().hasUrls():
        return []
    paths = [
        Path(url.toLocalFile())
        for url in event.mimeData().urls()
        if url.isLocalFile()
    ]
    return [path for path in paths if is_acceptable_local_source(path)]


class SourceListWidget(QListWidget):
    """QListWidget that accepts local media files via drag-and-drop."""

    files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if dropped_local_paths(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if dropped_local_paths(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = dropped_local_paths(event)
        if not paths:
            event.ignore()
            return
        self.files_dropped.emit(paths)
        event.acceptProposedAction()
