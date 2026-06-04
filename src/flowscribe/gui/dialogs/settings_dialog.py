"""Settings dialog for global application settings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.state import SUPPORTED_GUI_FORMATS
from flowscribe.gui.utils.state import (
    GUI_LANGUAGE_OPTIONS,
    GUI_MODEL_OPTIONS,
    GUI_NETWORK_OPTIONS,
    GUI_PRESET_OPTIONS,
    GUI_PROVIDER_LABELS,
    GUI_PROVIDER_OPTIONS,
    GUI_THEME_OPTIONS,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class SettingsDialog(QDialog):
    """Dialog for editing global application settings."""

    settings_changed = Signal(dict)
    model_manager_requested = Signal()

    def __init__(self, parent: QWidget | None, settings: dict):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(650, 750)

        self._settings = settings.copy()
        self._setup_ui()
        self._load_settings(settings)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Create tab widget
        self.tabs = QTabWidget()

        # Appearance tab
        appearance_tab = self._create_appearance_tab()
        self.tabs.addTab(appearance_tab, "Appearance")

        # Transcription tab
        transcription_tab = self._create_transcription_tab()
        self.tabs.addTab(transcription_tab, "Transcription")

        # Network tab
        network_tab = self._create_network_tab()
        self.tabs.addTab(network_tab, "Network")

        # Advanced tab
        advanced_tab = self._create_advanced_tab()
        self.tabs.addTab(advanced_tab, "Advanced")

        layout.addWidget(self.tabs)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._apply_settings
        )
        layout.addWidget(button_box)

    def _create_appearance_tab(self) -> QWidget:
        """Create appearance settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Theme settings
        theme_group = QGroupBox("Theme")
        theme_layout = QGridLayout(theme_group)
        theme_layout.setHorizontalSpacing(10)
        theme_layout.setVerticalSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(GUI_THEME_OPTIONS)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)

        theme_layout.addWidget(QLabel("Theme"), 0, 0)
        theme_layout.addWidget(self.theme_combo, 0, 1)

        layout.addWidget(theme_group)
        layout.addStretch(1)

        return tab

    def _create_transcription_tab(self) -> QWidget:
        """Create transcription settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Output Settings
        output_group = QGroupBox("Output Settings")
        output_layout = QGridLayout(output_group)
        output_layout.setHorizontalSpacing(10)
        output_layout.setVerticalSpacing(8)

        self.output_dir_input = QLineEdit()
        output_dir_button = QPushButton("Browse")
        output_dir_button.clicked.connect(self._choose_output_dir)
        output_dir_row = QHBoxLayout()
        output_dir_row.addWidget(self.output_dir_input)
        output_dir_row.addWidget(output_dir_button)

        self.output_name_input = QLineEdit()
        self.output_name_input.setPlaceholderText("Optional custom output name")

        self.format_checks: dict[str, QCheckBox] = {}
        format_row = QHBoxLayout()
        for fmt in SUPPORTED_GUI_FORMATS:
            checkbox = QCheckBox(fmt)
            self.format_checks[fmt] = checkbox
            format_row.addWidget(checkbox)
        format_row.addStretch(1)

        self.overwrite_check = QCheckBox("Overwrite existing outputs")

        output_layout.addWidget(QLabel("Output directory"), 0, 0)
        output_layout.addLayout(output_dir_row, 0, 1)
        output_layout.addWidget(QLabel("Output name"), 1, 0)
        output_layout.addWidget(self.output_name_input, 1, 1)
        output_layout.addWidget(QLabel("Output formats"), 2, 0)
        output_layout.addLayout(format_row, 2, 1)
        output_layout.addWidget(self.overwrite_check, 3, 1)

        # Model Settings
        model_group = QGroupBox("Model Settings")
        model_layout = QGridLayout(model_group)
        model_layout.setHorizontalSpacing(10)
        model_layout.setVerticalSpacing(8)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(GUI_MODEL_OPTIONS)
        model_browse_button = QPushButton("Browse")
        model_browse_button.clicked.connect(self._choose_model_file)
        model_center_button = QPushButton("Model Center")
        model_center_button.clicked.connect(self.model_manager_requested.emit)
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(model_browse_button)
        model_row.addWidget(model_center_button)
        self.model_browse_button = model_browse_button

        self.provider_combo = QComboBox()
        for provider_name in GUI_PROVIDER_OPTIONS:
            self.provider_combo.addItem(GUI_PROVIDER_LABELS[provider_name], provider_name)
        self.provider_combo.currentIndexChanged.connect(self._sync_provider_controls)

        self.language_combo = QComboBox()
        self.language_combo.addItems(GUI_LANGUAGE_OPTIONS)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(GUI_PRESET_OPTIONS)

        model_layout.addWidget(QLabel("Engine"), 0, 0)
        model_layout.addWidget(self.provider_combo, 0, 1)
        model_layout.addWidget(QLabel("Model"), 1, 0)
        model_layout.addLayout(model_row, 1, 1)
        model_layout.addWidget(QLabel("Language"), 2, 0)
        model_layout.addWidget(self.language_combo, 2, 1)
        model_layout.addWidget(QLabel("Preset"), 3, 0)
        model_layout.addWidget(self.preset_combo, 3, 1)

        # Timestamp Settings
        timestamp_group = QGroupBox("Timestamp Settings")
        timestamp_layout = QVBoxLayout(timestamp_group)
        timestamp_layout.setSpacing(6)

        self.timestamps_check = QCheckBox("Segment timestamps")
        self.word_timestamps_check = QCheckBox("Word timestamps")

        timestamp_layout.addWidget(self.timestamps_check)
        timestamp_layout.addWidget(self.word_timestamps_check)

        layout.addWidget(output_group)
        layout.addWidget(model_group)
        layout.addWidget(timestamp_group)
        layout.addStretch(1)

        return tab

    def _create_network_tab(self) -> QWidget:
        """Create network settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Network Settings
        network_group = QGroupBox("Network Settings (for URL sources)")
        network_layout = QGridLayout(network_group)
        network_layout.setHorizontalSpacing(10)
        network_layout.setVerticalSpacing(8)

        self.network_combo = QComboBox()
        self.network_combo.addItems(GUI_NETWORK_OPTIONS)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")

        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("Path to cookies.txt file")
        cookies_button = QPushButton("Browse")
        cookies_button.clicked.connect(self._choose_cookies)
        cookies_row = QHBoxLayout()
        cookies_row.addWidget(self.cookies_input)
        cookies_row.addWidget(cookies_button)

        network_layout.addWidget(QLabel("Network family"), 0, 0)
        network_layout.addWidget(self.network_combo, 0, 1)
        network_layout.addWidget(QLabel("Proxy"), 1, 0)
        network_layout.addWidget(self.proxy_input, 1, 1)
        network_layout.addWidget(QLabel("Cookies file"), 2, 0)
        network_layout.addLayout(cookies_row, 2, 1)

        layout.addWidget(network_group)
        layout.addStretch(1)

        return tab

    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Progressive Transcription Settings
        progressive_group = QGroupBox("Progressive Transcription")
        progressive_layout = QGridLayout(progressive_group)
        progressive_layout.setHorizontalSpacing(10)
        progressive_layout.setVerticalSpacing(8)

        self.progressive_enabled_check = QCheckBox("Enable progressive transcription")
        self.progressive_resume_check = QCheckBox("Enable resume (skip completed chunks)")

        self.progressive_chunk_seconds_spin = QSpinBox()
        self.progressive_chunk_seconds_spin.setRange(10, 300)
        self.progressive_chunk_seconds_spin.setSuffix(" seconds")

        self.progressive_max_workers_spin = QSpinBox()
        self.progressive_max_workers_spin.setRange(1, 16)

        self.native_threads_spin = QSpinBox()
        self.native_threads_spin.setRange(0, 128)
        self.native_threads_spin.setSpecialValueText("Auto")

        progressive_layout.addWidget(self.progressive_enabled_check, 0, 0, 1, 2)
        progressive_layout.addWidget(self.progressive_resume_check, 1, 0, 1, 2)
        progressive_layout.addWidget(QLabel("Chunk duration"), 2, 0)
        progressive_layout.addWidget(self.progressive_chunk_seconds_spin, 2, 1)
        progressive_layout.addWidget(QLabel("Max workers"), 3, 0)
        progressive_layout.addWidget(self.progressive_max_workers_spin, 3, 1)
        progressive_layout.addWidget(QLabel("Native threads"), 4, 0)
        progressive_layout.addWidget(self.native_threads_spin, 4, 1)

        layout.addWidget(progressive_group)
        layout.addStretch(1)

        return tab

    def _load_settings(self, settings: dict) -> None:
        """Load settings into UI widgets."""
        theme = settings.get("theme", "light")
        if theme in GUI_THEME_OPTIONS:
            self.theme_combo.setCurrentText(theme)

        self.output_dir_input.setText(settings.get("output_dir", "outputs"))
        self.output_name_input.setText(settings.get("output_name_base", ""))

        provider = settings.get("provider_name", "local-whisper")
        provider_index = self.provider_combo.findData(provider)
        self.provider_combo.setCurrentIndex(provider_index if provider_index >= 0 else 0)

        model = settings.get("model_name", "small")
        self.model_combo.setCurrentText(model)

        language = settings.get("language", "auto")
        if language is None:
            language = "auto"
        if language in GUI_LANGUAGE_OPTIONS:
            self.language_combo.setCurrentText(language)

        preset = settings.get("preset", "none")
        if preset is None:
            preset = "none"
        if preset in GUI_PRESET_OPTIONS:
            self.preset_combo.setCurrentText(preset)

        formats = settings.get("output_formats", ("txt", "md", "json"))
        for fmt, checkbox in self.format_checks.items():
            checkbox.setChecked(fmt in formats)

        self.timestamps_check.setChecked(settings.get("timestamps", True))
        self.word_timestamps_check.setChecked(settings.get("word_timestamps", False))
        self.overwrite_check.setChecked(settings.get("overwrite", False))

        network = settings.get("network_family", "auto")
        if network in GUI_NETWORK_OPTIONS:
            self.network_combo.setCurrentText(network)

        self.proxy_input.setText(settings.get("proxy", "") or "")

        cookies_path = settings.get("cookies_path")
        if cookies_path:
            self.cookies_input.setText(str(cookies_path))

        self.progressive_enabled_check.setChecked(
            settings.get("progressive_enabled", True)
        )
        self.progressive_resume_check.setChecked(
            settings.get("progressive_resume", True)
        )
        self.progressive_chunk_seconds_spin.setValue(
            int(settings.get("progressive_chunk_seconds", 30))
        )
        self.progressive_max_workers_spin.setValue(
            settings.get("progressive_max_workers", 1)
        )
        self.native_threads_spin.setValue(settings.get("native_threads") or 0)
        self._sync_provider_controls()

    def _collect_settings(self) -> dict:
        """Collect settings from UI widgets."""
        language = self.language_combo.currentText()
        if language == "auto":
            language = None

        preset = self.preset_combo.currentText()
        if preset == "none":
            preset = None

        formats = tuple(
            fmt for fmt, checkbox in self.format_checks.items() if checkbox.isChecked()
        )
        if not formats:
            formats = ("json",)

        proxy = self.proxy_input.text().strip()
        if not proxy:
            proxy = None

        cookies_text = self.cookies_input.text().strip()
        cookies_path = Path(cookies_text) if cookies_text else None

        native_threads = self.native_threads_spin.value()

        return {
            "theme": self.theme_combo.currentText(),
            "output_dir": self.output_dir_input.text(),
            "output_name_base": self.output_name_input.text(),
            "provider_name": self.provider_combo.currentData() or "local-whisper",
            "model_name": self.model_combo.currentText().strip() or "small",
            "language": language,
            "preset": preset,
            "output_formats": formats,
            "timestamps": self.timestamps_check.isChecked(),
            "word_timestamps": self.word_timestamps_check.isChecked(),
            "overwrite": self.overwrite_check.isChecked(),
            "network_family": self.network_combo.currentText(),
            "proxy": proxy,
            "cookies_path": cookies_path,
            "progressive_enabled": self.progressive_enabled_check.isChecked(),
            "progressive_resume": self.progressive_resume_check.isChecked(),
            "progressive_chunk_seconds": float(
                self.progressive_chunk_seconds_spin.value()
            ),
            "progressive_max_workers": self.progressive_max_workers_spin.value(),
            "native_threads": native_threads if native_threads > 0 else None,
        }

    def _choose_output_dir(self) -> None:
        """Open directory chooser for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Choose output directory", self.output_dir_input.text()
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _choose_cookies(self) -> None:
        """Open file chooser for cookies file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose cookies file",
            self.cookies_input.text(),
            "Text files (*.txt);;All files (*.*)",
        )
        if file_path:
            self.cookies_input.setText(file_path)

    def _choose_model_file(self) -> None:
        """Choose a local native-engine ggml model file."""
        current = self.model_combo.currentText().strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose native engine model",
            current or str(Path.home()),
            "Whisper.cpp Models (*.bin);;All files (*.*)",
        )
        if file_path:
            self.model_combo.setCurrentText(file_path)

    def _sync_provider_controls(self) -> None:
        """Adjust model input affordances for the selected transcription engine."""
        provider_name = self.provider_combo.currentData()
        is_native = provider_name == "native-engine"
        is_paraformer = provider_name == "paraformer"
        self.model_browse_button.setEnabled(is_native)
        if is_native:
            self.model_combo.setToolTip("Use a local whisper.cpp ggml .bin model file.")
            if self.model_combo.currentText() in GUI_MODEL_OPTIONS:
                self.model_combo.setCurrentText("models/ggml-base.en.bin")
        elif is_paraformer:
            self.model_combo.setToolTip("Use the local FunASR Paraformer Chinese model.")
            if self.model_combo.currentText() in GUI_MODEL_OPTIONS or not self.model_combo.currentText().strip():
                self.model_combo.setCurrentText("paraformer-zh")
        else:
            self.model_combo.setToolTip("Use a faster-whisper model name or local model path.")
            if not self.model_combo.currentText().strip():
                self.model_combo.setCurrentText("small")

    def _on_theme_changed(self, theme_name: str) -> None:
        """Apply theme immediately when changed."""
        from PySide6.QtWidgets import QApplication

        from flowscribe.gui.theme_manager import apply_theme

        try:
            app = QApplication.instance()
            if app:
                apply_theme(app, theme_name)
        except (ValueError, FileNotFoundError) as exc:
            from flowscribe.gui.gui_logging import get_gui_logger

            logger = get_gui_logger(__name__)
            logger.warning("Failed to apply theme '%s': %s", theme_name, exc)

    def _apply_settings(self) -> None:
        """Apply settings without closing dialog."""
        self._settings = self._collect_settings()
        self.settings_changed.emit(self._settings)

    def accept(self) -> None:
        """Accept dialog and save settings."""
        self._settings = self._collect_settings()
        self.settings_changed.emit(self._settings)
        super().accept()

    def get_settings(self) -> dict:
        """Return current settings."""
        return self._settings
