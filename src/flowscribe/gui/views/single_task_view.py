"""Single task transcription view."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.icons import (
    get_add_icon,
    get_check_icon,
    get_close_icon,
    get_document_icon,
    get_microphone_icon,
    get_open_icon,
    get_play_icon,
    get_settings_icon,
    get_stop_icon,
)
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.widgets import CollapsibleSection
from flowscribe.gui.widgets.source_list_widget import SourceListWidget

from .single_task_view_dialog import SingleTaskViewDialogMixin
from .single_task_view_runtime import SingleTaskViewRuntimeMixin
from .single_task_view_sources import SingleTaskViewSourcesMixin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class SingleTaskView(
    QWidget,
    SingleTaskViewSourcesMixin,
    SingleTaskViewRuntimeMixin,
    SingleTaskViewDialogMixin,
):
    """View for single transcription task with source selection, controls, and results."""

    transcription_started = Signal()
    transcription_finished = Signal(object)
    transcription_error = Signal(str)
    settings_requested = Signal()
    transcript_loaded = Signal(Path)

    def __init__(self, settings: dict, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._settings = settings
        self._local_paths: list[Path] = []
        self._worker = None
        self._thread = None
        self._cancel_requested = False
        self._last_output_dir: Path | None = None
        self._last_transcript_path: Path | None = None
        self._last_output_paths: list[Path] = []
        self._current_run_output = ""
        self._last_result = None
        self._view_dialog = None
        self._current_output_dir: Path | None = None
        self._progress_event_count = 0
        self._transcription_start_time = 0.0
        self._setup_ui()
        self._create_view_dialog()
        self._refresh_action_buttons()

    def _setup_ui(self) -> None:
        self.setProperty("view", "single-task")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        content_splitter = QSplitter(Qt.Orientation.Vertical, self)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(6)
        layout.addWidget(content_splitter, 1)

        source_group = QGroupBox("Sources")
        source_group.setProperty("softCard", True)
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)
        source_layout.setContentsMargins(10, 12, 10, 10)
        self._apply_soft_shadow(source_group)

        source_splitter = QSplitter(Qt.Orientation.Horizontal, source_group)
        source_splitter.setChildrenCollapsible(False)
        source_splitter.setHandleWidth(6)

        local_panel = QGroupBox("Local Files")
        local_panel.setProperty("softCard", True)
        local_layout = QVBoxLayout(local_panel)
        local_layout.setSpacing(6)
        local_layout.setContentsMargins(10, 12, 10, 10)
        self._apply_soft_shadow(local_panel)

        local_header = QHBoxLayout()
        local_header.setSpacing(8)
        local_title = QLabel("Drop media here or add files manually.")
        local_title.setProperty("helperText", True)
        self.file_summary_label = QLabel("0 files selected")
        self.file_summary_label.setProperty("helperText", True)
        self.file_summary_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        local_header.addWidget(local_title, 1)
        local_header.addWidget(self.file_summary_label)
        local_layout.addLayout(local_header)

        self.file_list = SourceListWidget()
        self.file_list.setProperty("singleTaskSourceList", True)
        self.file_list.setMinimumHeight(180)
        self.file_list.setMinimumWidth(320)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSpacing(2)
        self.file_list.files_dropped.connect(self._add_dropped_files)
        self.file_list.itemChanged.connect(self._on_file_list_changed)
        local_layout.addWidget(self.file_list, 1)

        file_actions = QHBoxLayout()
        add_file_button = QPushButton(get_add_icon(theme), "Add Files")
        add_file_button.clicked.connect(self._choose_files)
        add_file_button.setProperty("primary", True)
        select_all_button = QPushButton(get_check_icon(theme), "Select All")
        select_all_button.clicked.connect(self._select_all_files)
        select_all_button.setProperty("secondary", True)
        clear_files_button = QPushButton(get_close_icon(theme), "Clear")
        clear_files_button.clicked.connect(self._clear_files)
        clear_files_button.setProperty("secondary", True)
        file_actions.addWidget(add_file_button)
        file_actions.addWidget(select_all_button)
        file_actions.addWidget(clear_files_button)
        file_actions.addStretch(1)
        local_layout.addLayout(file_actions)

        url_group = QGroupBox("Online Source")
        url_group.setProperty("softCard", True)
        url_layout = QVBoxLayout(url_group)
        url_layout.setSpacing(6)
        url_layout.setContentsMargins(10, 12, 10, 10)
        self._apply_soft_shadow(url_group)

        url_header = QLabel("Paste a video or audio URL for download and transcription.")
        url_header.setProperty("helperText", True)
        url_layout.addWidget(url_header)

        self.url_input = QLineEdit()
        self.url_input.setProperty("singleTaskInput", True)
        self.url_input.setPlaceholderText("https://example.com/video")
        self.url_input.returnPressed.connect(self._start_transcription)
        self.url_input.textChanged.connect(lambda _text: self._refresh_action_buttons())
        url_layout.addWidget(self.url_input)

        url_options_layout = QGridLayout()
        url_options_layout.setHorizontalSpacing(8)
        url_options_layout.setVerticalSpacing(6)
        self.url_media_preserve_check = QCheckBox("Preserve media")
        url_options_layout.addWidget(self.url_media_preserve_check, 0, 0, 1, 2)

        url_options_layout.addWidget(QLabel("Type"), 1, 0)
        self.url_media_type_combo = QComboBox()
        self.url_media_type_combo.setProperty("singleTaskInput", True)
        self.url_media_type_combo.addItems(["Audio", "Video"])
        self.url_media_type_combo.setCurrentText("Audio")
        url_options_layout.addWidget(self.url_media_type_combo, 1, 1)

        url_options_layout.addWidget(QLabel("Quality"), 1, 2)
        self.url_quality_combo = QComboBox()
        self.url_quality_combo.setProperty("singleTaskInput", True)
        self.url_quality_combo.addItems(["Best", "High", "Medium", "Low"])
        self.url_quality_combo.setCurrentText("Best")
        url_options_layout.addWidget(self.url_quality_combo, 1, 3)

        url_options_layout.addWidget(QLabel("Format"), 1, 4)
        self.url_format_combo = QComboBox()
        self.url_format_combo.setProperty("singleTaskInput", True)
        self.url_format_combo.addItems(["Auto", "mp4", "webm", "mp3", "m4a", "opus"])
        self.url_format_combo.setCurrentText("Auto")
        url_options_layout.addWidget(self.url_format_combo, 1, 5)
        url_options_layout.setColumnStretch(6, 1)
        url_layout.addLayout(url_options_layout)

        capture_section = CollapsibleSection("System Audio Capture", expanded=False)
        capture_layout = capture_section.content_layout
        capture_layout.setSpacing(6)
        capture_layout.setContentsMargins(10, 12, 10, 10)
        capture_hint = QLabel("Capture loopback audio directly when no local file or URL is available.")
        capture_hint.setProperty("helperText", True)
        capture_hint.setWordWrap(True)
        capture_layout.addWidget(capture_hint)

        capture_controls = QHBoxLayout()
        self.capture_start_button = QPushButton(get_microphone_icon(theme), "Start Capture")
        self.capture_start_button.clicked.connect(self._start_capture)
        self.capture_start_button.setProperty("secondary", True)
        self.capture_stop_button = QPushButton(get_stop_icon(theme), "Stop Capture")
        self.capture_stop_button.clicked.connect(self._stop_capture)
        self.capture_stop_button.setProperty("secondary", True)
        self.capture_status_label = QLabel("Not capturing")
        self.capture_status_label.setProperty("helperText", True)
        capture_controls.addWidget(self.capture_start_button)
        capture_controls.addWidget(self.capture_stop_button)
        capture_controls.addWidget(self.capture_status_label)
        capture_controls.addStretch(1)
        capture_layout.addLayout(capture_controls)

        source_splitter.addWidget(local_panel)
        right_container = QWidget(source_group)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(url_group)
        right_layout.addWidget(capture_section)
        right_layout.addStretch(1)
        source_splitter.addWidget(right_container)
        source_splitter.setStretchFactor(0, 4)
        source_splitter.setStretchFactor(1, 3)
        source_splitter.setSizes([600, 360])
        source_layout.addWidget(source_splitter)
        content_splitter.addWidget(source_group)

        lower_panel = QWidget(self)
        lower_layout = QVBoxLayout(lower_panel)
        lower_layout.setSpacing(8)
        lower_layout.setContentsMargins(0, 0, 0, 0)

        controls_layout = QHBoxLayout()
        self.start_button = QPushButton(get_play_icon(theme), "Start Transcription")
        self.start_button.clicked.connect(self._start_transcription)
        self.start_button.setProperty("primary", True)
        self.cancel_button = QPushButton(get_stop_icon(theme), "Cancel")
        self.cancel_button.clicked.connect(self._cancel_transcription)
        self.cancel_button.setProperty("secondary", True)
        self.settings_button = QPushButton(get_settings_icon(theme), "Settings")
        self.settings_button.clicked.connect(self._request_settings)
        self.settings_button.setProperty("secondary", True)
        self.open_transcript_button = QPushButton(get_document_icon(theme), "Open Transcript")
        self.open_transcript_button.clicked.connect(self._open_transcript)
        self.open_transcript_button.setProperty("secondary", True)
        self.open_view_button = QPushButton(get_open_icon(theme), "Open View")
        self.open_view_button.clicked.connect(self._open_view)
        self.open_view_button.setProperty("secondary", True)
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.cancel_button)
        controls_layout.addWidget(self.settings_button)
        controls_layout.addWidget(self.open_transcript_button)
        controls_layout.addWidget(self.open_view_button)
        controls_layout.addStretch(1)
        lower_layout.addLayout(controls_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("singleTaskProgress", True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lower_layout.addWidget(self.progress_bar)

        self.tabs = QTabWidget()
        run_details_widget = QWidget()
        run_details_layout = QVBoxLayout(run_details_widget)
        run_details_layout.setContentsMargins(8, 8, 8, 8)
        run_details_layout.setSpacing(6)
        self.preview_output = QPlainTextEdit()
        self.preview_output.setProperty("singleTaskLog", True)
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlaceholderText("Transcription progress will appear here...")
        run_details_layout.addWidget(self.preview_output)
        self.tabs.addTab(run_details_widget, "Run Details")
        lower_layout.addWidget(self.tabs, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setProperty("statusText", True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lower_layout.addWidget(self.status_label)

        content_splitter.addWidget(lower_panel)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setSizes([260, 560])
        self._refresh_file_summary()

    @staticmethod
    def _apply_soft_shadow(widget: QWidget) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 13))
        widget.setGraphicsEffect(shadow)

    def update_settings(self, settings: dict) -> None:
        self._settings = settings
