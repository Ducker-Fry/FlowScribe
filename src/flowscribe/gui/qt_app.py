"""PySide6 desktop GUI skeleton for FlowScribe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from flowscribe import __version__
from flowscribe.gui.state import GuiTranscriptionForm, SUPPORTED_GUI_FORMATS


def run_gui(argv: list[str] | None = None) -> int:
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
    window = FlowScribeMainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    return app.exec()


class FlowScribeMainWindow:
    """Thin Qt view that delegates state conversion to GuiTranscriptionForm."""

    def __new__(cls):
        from PySide6.QtWidgets import QMainWindow

        class _Window(QMainWindow):
            def __init__(self) -> None:
                super().__init__()
                self._local_paths: list[Path] = []
                self._setup_window()

            def _setup_window(self) -> None:
                from PySide6.QtWidgets import (
                    QCheckBox,
                    QComboBox,
                    QGridLayout,
                    QGroupBox,
                    QHBoxLayout,
                    QLabel,
                    QLineEdit,
                    QListWidget,
                    QPushButton,
                    QTextEdit,
                    QVBoxLayout,
                    QWidget,
                )

                self.setWindowTitle("FlowScribe")
                self.resize(1040, 680)

                root = QWidget()
                root_layout = QHBoxLayout(root)
                root_layout.setContentsMargins(16, 16, 16, 16)
                root_layout.setSpacing(16)

                left_panel = QGroupBox("Sources")
                left_layout = QVBoxLayout(left_panel)
                left_layout.setSpacing(10)

                self.file_list = QListWidget()
                self.file_list.setMinimumWidth(300)
                self.file_list.setAcceptDrops(False)

                file_actions = QHBoxLayout()
                add_file_button = QPushButton("Add Files")
                add_file_button.clicked.connect(self._choose_files)
                clear_files_button = QPushButton("Clear")
                clear_files_button.clicked.connect(self._clear_files)
                file_actions.addWidget(add_file_button)
                file_actions.addWidget(clear_files_button)

                self.url_input = QLineEdit()
                self.url_input.setPlaceholderText("https://example.com/video")

                left_layout.addWidget(QLabel("Local files"))
                left_layout.addWidget(self.file_list)
                left_layout.addLayout(file_actions)
                left_layout.addSpacing(8)
                left_layout.addWidget(QLabel("URL"))
                left_layout.addWidget(self.url_input)

                right_panel = QWidget()
                right_layout = QVBoxLayout(right_panel)
                right_layout.setSpacing(12)

                settings_box = QGroupBox("Settings")
                settings_layout = QGridLayout(settings_box)
                settings_layout.setHorizontalSpacing(10)
                settings_layout.setVerticalSpacing(10)

                self.output_dir_input = QLineEdit("outputs")
                choose_output_button = QPushButton("Browse")
                choose_output_button.clicked.connect(self._choose_output_dir)

                output_row = QHBoxLayout()
                output_row.addWidget(self.output_dir_input)
                output_row.addWidget(choose_output_button)

                self.model_combo = QComboBox()
                self.model_combo.addItems(["small", "tiny", "base", "medium", "large-v3-turbo", "large-v3"])

                self.language_combo = QComboBox()
                self.language_combo.addItems(["auto", "zh", "en"])

                self.preset_combo = QComboBox()
                self.preset_combo.addItems(["none", "zh"])

                self.network_combo = QComboBox()
                self.network_combo.addItems(["auto", "ipv4", "ipv6"])

                self.proxy_input = QLineEdit()
                self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")

                self.cookies_input = QLineEdit()
                self.cookies_input.setPlaceholderText("D:\\private\\cookies.txt")
                choose_cookies_button = QPushButton("Browse")
                choose_cookies_button.clicked.connect(self._choose_cookies)

                cookies_row = QHBoxLayout()
                cookies_row.addWidget(self.cookies_input)
                cookies_row.addWidget(choose_cookies_button)

                self.format_checks: dict[str, QCheckBox] = {}
                format_row = QHBoxLayout()
                for output_format in SUPPORTED_GUI_FORMATS:
                    checkbox = QCheckBox(output_format)
                    checkbox.setChecked(output_format in {"txt", "md", "json"})
                    self.format_checks[output_format] = checkbox
                    format_row.addWidget(checkbox)
                format_row.addStretch(1)

                self.timestamps_check = QCheckBox("Segment timestamps")
                self.timestamps_check.setChecked(True)
                self.word_timestamps_check = QCheckBox("Word timestamps")
                self.overwrite_check = QCheckBox("Overwrite outputs")
                self.keep_media_check = QCheckBox("Keep URL media")

                settings_layout.addWidget(QLabel("Output directory"), 0, 0)
                settings_layout.addLayout(output_row, 0, 1)
                settings_layout.addWidget(QLabel("Model"), 1, 0)
                settings_layout.addWidget(self.model_combo, 1, 1)
                settings_layout.addWidget(QLabel("Language"), 2, 0)
                settings_layout.addWidget(self.language_combo, 2, 1)
                settings_layout.addWidget(QLabel("Preset"), 3, 0)
                settings_layout.addWidget(self.preset_combo, 3, 1)
                settings_layout.addWidget(QLabel("Formats"), 4, 0)
                settings_layout.addLayout(format_row, 4, 1)
                settings_layout.addWidget(QLabel("Network"), 5, 0)
                settings_layout.addWidget(self.network_combo, 5, 1)
                settings_layout.addWidget(QLabel("Proxy"), 6, 0)
                settings_layout.addWidget(self.proxy_input, 6, 1)
                settings_layout.addWidget(QLabel("Cookies"), 7, 0)
                settings_layout.addLayout(cookies_row, 7, 1)
                settings_layout.addWidget(self.timestamps_check, 8, 1)
                settings_layout.addWidget(self.word_timestamps_check, 9, 1)
                settings_layout.addWidget(self.overwrite_check, 10, 1)
                settings_layout.addWidget(self.keep_media_check, 11, 1)

                action_row = QHBoxLayout()
                collect_button = QPushButton("Collect State")
                collect_button.clicked.connect(self._show_state_preview)
                disabled_start_button = QPushButton("Start Transcription")
                disabled_start_button.setEnabled(False)
                action_row.addWidget(collect_button)
                action_row.addWidget(disabled_start_button)
                action_row.addStretch(1)

                self.status_label = QLabel("GUI skeleton ready. Transcription execution is planned for Milestone 3.2.")
                self.status_label.setWordWrap(True)

                self.preview_output = QTextEdit()
                self.preview_output.setReadOnly(True)
                self.preview_output.setMinimumHeight(180)
                self.preview_output.setPlaceholderText("Collected TranscriptionJob preview will appear here.")

                right_layout.addWidget(settings_box)
                right_layout.addLayout(action_row)
                right_layout.addWidget(self.status_label)
                right_layout.addWidget(QLabel("State preview"))
                right_layout.addWidget(self.preview_output)

                root_layout.addWidget(left_panel, 1)
                root_layout.addWidget(right_panel, 2)
                self.setCentralWidget(root)

            def _choose_files(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                paths, _ = QFileDialog.getOpenFileNames(self, "Choose media files")
                if not paths:
                    return
                for path in paths:
                    parsed = Path(path)
                    if parsed not in self._local_paths:
                        self._local_paths.append(parsed)
                        self.file_list.addItem(str(parsed))

            def _clear_files(self) -> None:
                self._local_paths.clear()
                self.file_list.clear()

            def _choose_output_dir(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                path = QFileDialog.getExistingDirectory(self, "Choose output directory")
                if path:
                    self.output_dir_input.setText(path)

            def _choose_cookies(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                path, _ = QFileDialog.getOpenFileName(self, "Choose cookies.txt")
                if path:
                    self.cookies_input.setText(path)

            def _form(self) -> GuiTranscriptionForm:
                output_formats = tuple(
                    output_format
                    for output_format, checkbox in self.format_checks.items()
                    if checkbox.isChecked()
                )
                language = self.language_combo.currentText()
                preset = self.preset_combo.currentText()
                cookies_text = self.cookies_input.text().strip()

                return GuiTranscriptionForm(
                    local_paths=tuple(self._local_paths),
                    url=self.url_input.text(),
                    output_dir=Path(self.output_dir_input.text().strip() or "outputs"),
                    model_name=self.model_combo.currentText(),
                    language="" if language == "auto" else language,
                    preset="" if preset == "none" else preset,
                    output_formats=output_formats,
                    timestamps=self.timestamps_check.isChecked(),
                    word_timestamps=self.word_timestamps_check.isChecked(),
                    overwrite=self.overwrite_check.isChecked(),
                    keep_media=self.keep_media_check.isChecked(),
                    network_family=self.network_combo.currentText(),
                    proxy=self.proxy_input.text(),
                    cookies_path=Path(cookies_text) if cookies_text else None,
                )

            def _show_state_preview(self) -> None:
                form = self._form()
                errors = form.validate()
                if errors:
                    self.status_label.setText(" ".join(errors))
                    self.preview_output.clear()
                    return

                preview = form.preview()
                self.status_label.setText(
                    "State collected successfully. Execution will be connected in Milestone 3.2."
                )
                self.preview_output.setPlainText(json.dumps(preview, ensure_ascii=False, indent=2))

        return _Window()
