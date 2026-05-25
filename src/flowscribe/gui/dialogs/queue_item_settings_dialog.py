"""Dialog for editing queue item settings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from flowscribe.app.models import SourceSpec
from flowscribe.gui.state import SUPPORTED_GUI_FORMATS
from flowscribe.queue.models import QueueItemSettings

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

GUI_MODEL_OPTIONS = ("tiny", "base", "small", "medium", "large-v3-turbo", "large-v3")
GUI_LANGUAGE_OPTIONS = ("auto", "en", "zh", "ja", "ko", "es", "fr", "de", "ru", "pt")
GUI_PRESET_OPTIONS = ("none", "best_quality", "fast")
GUI_NETWORK_OPTIONS = ("auto", "ipv4", "ipv6")
GUI_MEDIA_KIND_OPTIONS = ("audio", "video")


class QueueItemSettingsDialog(QDialog):
    """Dialog for editing queue item transcription settings."""

    def __init__(
        self,
        parent: QWidget | None,
        settings: QueueItemSettings,
        source: SourceSpec,
        item_label: str,
        is_batch: bool = False,
    ):
        super().__init__(parent)
        title = f"Batch Edit Settings ({item_label})" if is_batch else f"Edit Settings - {item_label}"
        self.setWindowTitle(title)
        self.resize(600, 700)

        self._settings = settings
        self._source = source
        self._is_batch = is_batch
        self._setup_ui()
        self._load_settings(settings, source)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

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
        self.model_combo.addItems(GUI_MODEL_OPTIONS)

        self.language_combo = QComboBox()
        self.language_combo.addItems(GUI_LANGUAGE_OPTIONS)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(GUI_PRESET_OPTIONS)

        model_layout.addWidget(QLabel("Model"), 0, 0)
        model_layout.addWidget(self.model_combo, 0, 1)
        model_layout.addWidget(QLabel("Language"), 1, 0)
        model_layout.addWidget(self.language_combo, 1, 1)
        model_layout.addWidget(QLabel("Preset"), 2, 0)
        model_layout.addWidget(self.preset_combo, 2, 1)

        # Timestamp Settings
        timestamp_group = QGroupBox("Timestamp Settings")
        timestamp_layout = QVBoxLayout(timestamp_group)
        self.timestamps_check = QCheckBox("Segment timestamps")
        self.word_timestamps_check = QCheckBox("Word timestamps")
        timestamp_layout.addWidget(self.timestamps_check)
        timestamp_layout.addWidget(self.word_timestamps_check)

        # Progressive Settings
        progressive_group = QGroupBox("Progressive Transcription")
        progressive_group.setCheckable(True)
        progressive_layout = QGridLayout(progressive_group)
        progressive_layout.setHorizontalSpacing(10)
        progressive_layout.setVerticalSpacing(8)

        self.progressive_resume_check = QCheckBox("Enable resume (skip completed chunks)")
        self.progressive_chunk_spin = QSpinBox()
        self.progressive_chunk_spin.setRange(15, 120)
        self.progressive_chunk_spin.setSuffix(" seconds")
        self.progressive_workers_spin = QSpinBox()
        self.progressive_workers_spin.setRange(1, 8)

        progressive_layout.addWidget(self.progressive_resume_check, 0, 0, 1, 2)
        progressive_layout.addWidget(QLabel("Chunk duration"), 1, 0)
        progressive_layout.addWidget(self.progressive_chunk_spin, 1, 1)
        progressive_layout.addWidget(QLabel("Max workers"), 2, 0)
        progressive_layout.addWidget(self.progressive_workers_spin, 2, 1)

        # Network Settings
        network_group = QGroupBox("Network Settings")
        network_group.setCheckable(False)
        network_layout = QGridLayout(network_group)
        network_layout.setHorizontalSpacing(10)
        network_layout.setVerticalSpacing(8)

        self.network_combo = QComboBox()
        self.network_combo.addItems(GUI_NETWORK_OPTIONS)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")

        self.cookies_input = QLineEdit()
        cookies_button = QPushButton("Browse")
        cookies_button.clicked.connect(self._choose_cookies)
        cookies_row = QHBoxLayout()
        cookies_row.addWidget(self.cookies_input)
        cookies_row.addWidget(cookies_button)

        self.max_download_spin = QSpinBox()
        self.max_download_spin.setRange(100, 10000)
        self.max_download_spin.setSuffix(" MB")

        self.max_duration_spin = QSpinBox()
        self.max_duration_spin.setRange(60, 86400)
        self.max_duration_spin.setSuffix(" seconds")

        self.download_timeout_spin = QSpinBox()
        self.download_timeout_spin.setRange(10, 300)
        self.download_timeout_spin.setSuffix(" seconds")

        network_layout.addWidget(QLabel("Network family"), 0, 0)
        network_layout.addWidget(self.network_combo, 0, 1)
        network_layout.addWidget(QLabel("Proxy"), 1, 0)
        network_layout.addWidget(self.proxy_input, 1, 1)
        network_layout.addWidget(QLabel("Cookies file"), 2, 0)
        network_layout.addLayout(cookies_row, 2, 1)
        network_layout.addWidget(QLabel("Max download size"), 3, 0)
        network_layout.addWidget(self.max_download_spin, 3, 1)
        network_layout.addWidget(QLabel("Max duration"), 4, 0)
        network_layout.addWidget(self.max_duration_spin, 4, 1)
        network_layout.addWidget(QLabel("Download timeout"), 5, 0)
        network_layout.addWidget(self.download_timeout_spin, 5, 1)

        # URL Media Settings (only for URL sources)
        media_group = QGroupBox("URL Media Settings")
        media_layout = QGridLayout(media_group)
        media_layout.setHorizontalSpacing(10)
        media_layout.setVerticalSpacing(8)

        self.keep_media_check = QCheckBox("Preserve downloaded media")
        self.media_kind_combo = QComboBox()
        self.media_kind_combo.addItems(GUI_MEDIA_KIND_OPTIONS)
        self.auto_bind_media_check = QCheckBox("Auto-bind media to transcript")

        media_layout.addWidget(self.keep_media_check, 0, 0, 1, 2)
        media_layout.addWidget(QLabel("Media kind"), 1, 0)
        media_layout.addWidget(self.media_kind_combo, 1, 1)
        media_layout.addWidget(self.auto_bind_media_check, 2, 0, 1, 2)

        # Add all groups to main layout
        layout.addWidget(output_group)
        layout.addWidget(model_group)
        layout.addWidget(timestamp_group)
        layout.addWidget(progressive_group)
        layout.addWidget(network_group)
        layout.addWidget(media_group)

        # Store reference to media group for conditional visibility
        self._media_group = media_group

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.accept)
        apply_button.setDefault(True)
        button_layout.addWidget(apply_button)

        layout.addLayout(button_layout)

        # Store reference to progressive group for enabled state
        self._progressive_group = progressive_group

    def _load_settings(self, settings: QueueItemSettings, source: SourceSpec) -> None:
        """Load settings into UI controls."""
        self.output_dir_input.setText(str(settings.output_dir))
        self.output_name_input.setText(settings.output_name_base)

        for fmt in SUPPORTED_GUI_FORMATS:
            self.format_checks[fmt].setChecked(fmt in settings.output_formats)

        self.overwrite_check.setChecked(settings.overwrite)

        self.model_combo.setCurrentText(settings.model_name)
        self.language_combo.setCurrentText(settings.language or "auto")
        self.preset_combo.setCurrentText(settings.preset or "none")

        self.timestamps_check.setChecked(settings.timestamps)
        self.word_timestamps_check.setChecked(settings.word_timestamps)

        self._progressive_group.setChecked(settings.progressive_enabled)
        self.progressive_resume_check.setChecked(settings.progressive_resume)
        self.progressive_chunk_spin.setValue(int(settings.progressive_chunk_seconds))
        self.progressive_workers_spin.setValue(settings.progressive_max_workers)

        self.network_combo.setCurrentText(settings.network_family)
        self.proxy_input.setText(settings.proxy or "")
        self.cookies_input.setText(str(settings.cookies_path) if settings.cookies_path else "")
        self.max_download_spin.setValue(settings.max_download_mb)
        self.max_duration_spin.setValue(int(settings.max_duration_seconds))
        self.download_timeout_spin.setValue(settings.download_timeout_seconds)

        # Load URL media settings
        self.keep_media_check.setChecked(source.keep_media)
        self.media_kind_combo.setCurrentText(source.url_media_kind)
        self.auto_bind_media_check.setChecked(source.auto_bind_media)

        # Hide media group for non-URL sources
        if source.kind != "url":
            self._media_group.hide()

    def _reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        defaults = QueueItemSettings()
        default_source = SourceSpec(kind=self._source.kind, value=self._source.value)
        self._load_settings(defaults, default_source)

    def _choose_output_dir(self) -> None:
        """Open directory chooser for output directory."""
        current = self.output_dir_input.text().strip()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Output Directory",
            current or str(Path.home()),
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _choose_cookies(self) -> None:
        """Open file chooser for cookies file."""
        current = self.cookies_input.text().strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Cookies File",
            current or str(Path.home()),
            "Text Files (*.txt);;All Files (*.*)",
        )
        if file_path:
            self.cookies_input.setText(file_path)

    def get_settings(self) -> tuple[QueueItemSettings, SourceSpec] | None:
        """Return updated settings and source if Apply was clicked, None if canceled."""
        if self.result() != QDialog.DialogCode.Accepted:
            return None

        output_formats = tuple(
            fmt for fmt, checkbox in self.format_checks.items() if checkbox.isChecked()
        )
        if not output_formats:
            output_formats = ("json",)

        language_text = self.language_combo.currentText().strip()
        language = None if language_text == "auto" else (language_text or None)

        preset_text = self.preset_combo.currentText().strip()
        preset = None if preset_text == "none" else (preset_text or None)

        proxy_text = self.proxy_input.text().strip()
        proxy = proxy_text or None

        cookies_text = self.cookies_input.text().strip()
        cookies_path = Path(cookies_text) if cookies_text else None

        settings = QueueItemSettings(
            output_dir=Path(self.output_dir_input.text().strip() or "outputs"),
            output_name_base=self.output_name_input.text().strip(),
            model_name=self.model_combo.currentText().strip() or "small",
            language=language,
            preset=preset,
            output_formats=output_formats,
            timestamps=self.timestamps_check.isChecked(),
            word_timestamps=self.word_timestamps_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            network_family=self.network_combo.currentText(),
            proxy=proxy,
            cookies_path=cookies_path,
            progressive_enabled=self._progressive_group.isChecked(),
            progressive_resume=self.progressive_resume_check.isChecked(),
            progressive_chunk_seconds=float(self.progressive_chunk_spin.value()),
            progressive_max_workers=self.progressive_workers_spin.value(),
            max_download_mb=self.max_download_spin.value(),
            max_duration_seconds=float(self.max_duration_spin.value()),
            download_timeout_seconds=self.download_timeout_spin.value(),
        )

        # Create updated source with new media settings
        source = SourceSpec(
            kind=self._source.kind,
            value=self._source.value,
            recursive=self._source.recursive,
            keep_media=self.keep_media_check.isChecked(),
            url_media_kind=self.media_kind_combo.currentText(),
            media_output_dir=self._source.media_output_dir,
            auto_bind_media=self.auto_bind_media_check.isChecked(),
            download_options=self._source.download_options,
        )

        return settings, source
