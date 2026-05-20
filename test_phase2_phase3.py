"""Test script for new UI components (Phase 2 & 3)."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QToolBar

from flowscribe.gui.dialogs.settings_dialog import SettingsDialog
from flowscribe.gui.views.single_task_view import SingleTaskView


def default_settings() -> dict:
    """Return default settings for testing."""
    return {
        "output_dir": "outputs",
        "output_name_base": "",
        "model_name": "small",
        "language": None,
        "preset": None,
        "output_formats": ("txt", "md", "json"),
        "timestamps": True,
        "word_timestamps": False,
        "overwrite": False,
        "network_family": "auto",
        "proxy": None,
        "cookies_path": None,
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
    }


class TestMainWindow(QMainWindow):
    """Test main window for Phase 2 & 3 components."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowScribe UI Refactor Test - Phase 2 & 3")
        self.resize(1200, 800)

        self._settings = default_settings()

        # Toolbar
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        settings_action = toolbar.addAction("Settings")
        settings_action.triggered.connect(self._show_settings_dialog)

        # Main view
        self._view_stack = QStackedWidget()
        self._single_task_view = SingleTaskView(self._settings)
        self._single_task_view.settings_requested.connect(self._show_settings_dialog)
        self._single_task_view.transcription_started.connect(self._on_transcription_started)
        self._single_task_view.transcription_finished.connect(self._on_transcription_finished)
        self._single_task_view.transcription_error.connect(self._on_transcription_error)

        self._view_stack.addWidget(self._single_task_view)
        self.setCentralWidget(self._view_stack)

        self.statusBar().showMessage("Ready - Phase 2 & 3 Test")

    def _show_settings_dialog(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self, self._settings)
        dialog.settings_changed.connect(self._on_settings_changed)
        if dialog.exec():
            self._settings = dialog.get_settings()
            self._single_task_view.update_settings(self._settings)
            self.statusBar().showMessage("Settings updated")

    def _on_settings_changed(self, settings: dict):
        """Handle settings changes."""
        self._settings = settings
        self._single_task_view.update_settings(settings)
        self.statusBar().showMessage("Settings applied")

    def _on_transcription_started(self):
        """Handle transcription start."""
        self.statusBar().showMessage("Transcription started")

    def _on_transcription_finished(self, result):
        """Handle transcription completion."""
        self.statusBar().showMessage("Transcription finished")

    def _on_transcription_error(self, error: str):
        """Handle transcription error."""
        self.statusBar().showMessage(f"Error: {error}")


def main():
    """Run test application."""
    app = QApplication(sys.argv)
    window = TestMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
