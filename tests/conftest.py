"""Shared pytest fixtures for FlowScribe tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _SimpleQtBot:
    def __init__(self) -> None:
        self._widgets = []

    def addWidget(self, widget) -> None:
        self._widgets.append(widget)

    def close_widgets(self) -> None:
        for widget in reversed(self._widgets):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
        self._widgets.clear()


@pytest.fixture
def qtbot():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    bot = _SimpleQtBot()
    yield bot
    bot.close_widgets()
