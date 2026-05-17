"""PySide6 desktop GUI entry point for FlowScribe."""

from __future__ import annotations

import sys

from flowscribe import __version__
from flowscribe.gui.gui_logging import configure_gui_logging, get_gui_logger

LOGGER = get_gui_logger(__name__)


def run_gui(argv: list[str] | None = None) -> int:
    log_mode = configure_gui_logging()
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is not installed. Install GUI dependencies with: "
            "python -m pip install -e .[gui]",
            file=sys.stderr,
        )
        return 2

    app = QApplication(argv or sys.argv)
    app.setApplicationName("FlowScribe")
    app.setApplicationVersion(__version__)
    LOGGER.debug("Starting GUI in %s mode.", log_mode)
    from flowscribe.gui.main_window import MainWindow

    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    return app.exec()


class FlowScribeMainWindow:
    """Thin wrapper for backward compatibility.

    Previously used a __new__ pattern to defer PySide6 imports.
    Now delegates directly to MainWindow.
    """

    def __new__(cls):
        from flowscribe.gui.main_window import MainWindow

        return MainWindow()
