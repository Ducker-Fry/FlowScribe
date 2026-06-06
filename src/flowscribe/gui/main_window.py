"""Backward-compatible main window export.

The project now maintains a single GUI window implementation in
`flowscribe.gui.new_main_window`. This module keeps the historical import path
stable while avoiding a second diverging window implementation.
"""

from __future__ import annotations

from flowscribe.gui.new_main_window import NewMainWindow


class MainWindow(NewMainWindow):
    """Compatibility alias for the unified GUI main window."""


__all__ = ["MainWindow"]
