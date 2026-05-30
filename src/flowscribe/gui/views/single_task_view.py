"""Single task transcription view."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flowscribe.app.models import (
    DownloadOptions,
    ProgressEvent,
    SourceSpec,
    TranscriptionJob,
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
from flowscribe.gui.state import is_acceptable_local_source
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.widgets import CollapsibleSection
from flowscribe.gui.widgets.source_list_widget import SourceListWidget
from flowscribe.gui.workers.transcription_worker import TranscriptionWorker

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class SingleTaskView(QWidget):
    """View for single transcription task with source selection, controls, and results."""

    transcription_started = Signal()
    transcription_finished = Signal(object)
    transcription_error = Signal(str)
    settings_requested = Signal()
    transcript_loaded = Signal(Path)  # Emitted when transcript is loaded

    def __init__(self, settings: dict, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._settings = settings
        self._local_paths: list[Path] = []
        self._worker: TranscriptionWorker | None = None
        self._thread: QThread | None = None
        self._cancel_requested = False
        self._last_output_dir: Path | None = None
        self._last_transcript_path: Path | None = None
        self._last_output_paths: list[Path] = []  # Track all output paths
        self._current_run_output: str = ""
        self._last_result = None  # Store TranscriptionResult
        self._view_dialog = None
        self._current_output_dir: Path | None = None  # Track current transcription output dir
        self._progress_event_count = 0  # Counter for progress events
        self._transcription_start_time: float = 0.0  # Track when transcription started
        self._setup_ui()
        # Create View Dialog at initialization (like old version)
        self._create_view_dialog()

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        self.setProperty("view", "single-task")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Get current theme for icons
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        content_splitter = QSplitter(Qt.Orientation.Vertical, self)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(6)
        layout.addWidget(content_splitter, 1)

        # Source selection area
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
        file_actions.setSpacing(6)
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
        url_layout.addWidget(self.url_input)
        self.url_input.returnPressed.connect(self._start_transcription)

        # URL download options
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
        capture_controls.setSpacing(6)
        self.capture_start_button = QPushButton(get_microphone_icon(theme), "Start Capture")
        self.capture_start_button.clicked.connect(self._start_capture)
        self.capture_start_button.setProperty("secondary", True)
        self.capture_stop_button = QPushButton(get_stop_icon(theme), "Stop Capture")
        self.capture_stop_button.clicked.connect(self._stop_capture)
        self.capture_stop_button.setEnabled(False)
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

        # Transcription controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)
        self.start_button = QPushButton(get_play_icon(theme), "Start Transcription")
        self.start_button.clicked.connect(self._start_transcription)
        self.start_button.setProperty("primary", True)
        self.cancel_button = QPushButton(get_stop_icon(theme), "Cancel")
        self.cancel_button.clicked.connect(self._cancel_transcription)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setProperty("secondary", True)
        self.settings_button = QPushButton(get_settings_icon(theme), "Settings")
        self.settings_button.clicked.connect(self._request_settings)
        self.settings_button.setProperty("secondary", True)
        self.open_transcript_button = QPushButton(get_document_icon(theme), "Open Transcript")
        self.open_transcript_button.clicked.connect(self._open_transcript)
        self.open_transcript_button.setProperty("secondary", True)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.cancel_button)
        controls_layout.addWidget(self.settings_button)
        controls_layout.addWidget(self.open_transcript_button)

        self.open_view_button = QPushButton(get_open_icon(theme), "Open View")
        self.open_view_button.clicked.connect(self._open_view)
        # Always enabled - View Dialog shows current state
        self.open_view_button.setProperty("secondary", True)
        controls_layout.addWidget(self.open_view_button)

        controls_layout.addStretch(1)
        lower_layout.addLayout(controls_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("singleTaskProgress", True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lower_layout.addWidget(self.progress_bar)

        # Run details section
        self.tabs = QTabWidget()

        # Run Details tab
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

        # Note: Workspace tab removed - full workspace is now in the View dialog
        # Access via "Open View" button after transcription completes

        lower_layout.addWidget(self.tabs, 1)

        # Status label
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
        """Apply a subtle shadow to card-like panels in light mode."""
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 13))
        widget.setGraphicsEffect(shadow)

    def update_settings(self, settings: dict) -> None:
        """Update view with new settings."""
        self._settings = settings

    def _choose_files(self) -> None:
        """Open file chooser dialog."""
        from PySide6.QtWidgets import QFileDialog

        paths, _ = QFileDialog.getOpenFileNames(self, "Choose media files")
        if not paths:
            return
        for path in paths:
            self._add_local_file(Path(path))

    def _add_local_file(self, path: Path) -> bool:
        """Add a local file to the list."""
        if not is_acceptable_local_source(path):
            self.status_label.setText(f"Unsupported file: {path}")
            return False
        if path in self._local_paths:
            return False
        self._local_paths.append(path)
        item = QListWidgetItem(str(path))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.file_list.addItem(item)
        return True

    def _add_dropped_files(self, paths: list[Path]) -> None:
        """Handle dropped files."""
        added = 0
        for path in paths:
            if self._add_local_file(path):
                added += 1
        if added:
            self.status_label.setText(f"Added {added} file(s)")
        else:
            self.status_label.setText("No new files added")

    def _select_all_files(self) -> None:
        """Select all files in the list."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _clear_files(self) -> None:
        """Clear all files from the list."""
        self._local_paths.clear()
        self.file_list.clear()
        self._refresh_file_summary()
        self.status_label.setText("Files cleared")

    def _on_file_list_changed(self) -> None:
        """Handle file list changes."""
        self._refresh_file_summary()

    def _refresh_file_summary(self) -> None:
        """Refresh compact file selection summary."""
        total = self.file_list.count()
        checked = sum(
            1
            for i in range(total)
            if (item := self.file_list.item(i))
            and item.checkState() == Qt.CheckState.Checked
        )
        noun = "file" if total == 1 else "files"
        self.file_summary_label.setText(f"{checked}/{total} {noun} selected")

    def _start_capture(self) -> None:
        """Start system audio capture."""
        self.capture_start_button.setEnabled(False)
        self.capture_stop_button.setEnabled(True)
        self.capture_status_label.setText("Capturing...")
        self.status_label.setText("System audio capture started")

    def _stop_capture(self) -> None:
        """Stop system audio capture."""
        self.capture_start_button.setEnabled(True)
        self.capture_stop_button.setEnabled(False)
        self.capture_status_label.setText("Not capturing")
        self.status_label.setText("System audio capture stopped")

    def _start_transcription(self) -> None:
        """Start transcription process."""
        if self._thread is not None:
            self.status_label.setText("A transcription job is already running.")
            return

        # Validate sources
        selected_paths = self._get_checked_paths()
        url = self.url_input.text().strip()

        if not selected_paths and not url:
            self.status_label.setText("Please select local files or enter a URL.")
            return

        # Build job from settings and sources
        job = self._build_job(selected_paths, url)
        if job is None:
            return

        # Clear previous transcript path and output paths
        self._last_transcript_path = None
        self._last_output_paths = []

        # Clear View Dialog content (but keep it available)
        if self._view_dialog is not None:
            self._view_dialog.clear_content()

        # Track output directory and start time for progressive cache detection
        self._current_output_dir = job.output_dir
        self._progress_event_count = 0
        import time
        self._transcription_start_time = time.time()

        # Start transcription
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 0)
        self.preview_output.clear()
        self.preview_output.appendPlainText("Starting transcription...\n")
        self.status_label.setText("Transcription in progress...")
        self._cancel_requested = False

        self._thread = QThread(self)
        self._worker = TranscriptionWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.warning.connect(self._on_warning)  # Connect warning signal
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

        self.transcription_started.emit()

    def _build_job(self, selected_paths: list[Path], url: str) -> TranscriptionJob | None:
        """Build transcription job from settings and sources."""
        output_dir = Path(self._settings.get("output_dir", "outputs"))
        output_name_base = self._settings.get("output_name_base", "")
        provider_name = self._settings.get("provider_name", "local-whisper")
        model_name = self._settings.get("model_name", "small")
        language = self._settings.get("language")
        preset = self._settings.get("preset")
        output_formats = self._settings.get("output_formats", ("json",))
        timestamps = self._settings.get("timestamps", True)
        word_timestamps = self._settings.get("word_timestamps", False)
        overwrite = self._settings.get("overwrite", False)
        network_family = self._settings.get("network_family", "auto")
        proxy = self._settings.get("proxy")
        cookies_path = self._settings.get("cookies_path")
        progressive_enabled = self._settings.get("progressive_enabled", True)
        progressive_resume = self._settings.get("progressive_resume", True)
        progressive_chunk_seconds = self._settings.get("progressive_chunk_seconds", 30.0)
        progressive_max_workers = self._settings.get("progressive_max_workers", 1)
        native_threads = self._settings.get("native_threads")

        # Build sources
        sources: list[SourceSpec] = []
        for path in selected_paths:
            sources.append(SourceSpec(kind="local", value=str(path)))
        if url:
            # Build download options from UI
            quality_map = {"Best": "best", "High": "high", "Medium": "medium", "Low": "low"}
            quality = quality_map.get(self.url_quality_combo.currentText(), "best")
            prefer_format = None
            if self.url_format_combo.currentText() != "Auto":
                prefer_format = self.url_format_combo.currentText()

            download_opts = DownloadOptions(quality=quality, prefer_format=prefer_format)

            # Determine media kind from UI
            preserve_media = self.url_media_preserve_check.isChecked()
            media_kind = "video" if self.url_media_type_combo.currentText() == "Video" else "audio"

            sources.append(
                SourceSpec(
                    kind="url",
                    value=url,
                    keep_media=preserve_media,
                    url_media_kind=media_kind,
                    download_options=download_opts,
                    auto_bind_media=True,
                )
            )

        if not sources:
            self.status_label.setText("No sources selected.")
            return None

        # Create job
        job = TranscriptionJob(
            sources=tuple(sources),
            output_dir=output_dir,
            output_name_base=output_name_base,
            provider_name=provider_name,
            model_name=model_name,
            language=language,
            preset=preset,
            output_formats=output_formats,
            timestamps=timestamps,
            word_timestamps=word_timestamps,
            overwrite=overwrite,
            network_family=network_family,
            proxy=proxy,
            cookies_path=cookies_path,
            progressive_enabled=progressive_enabled,
            progressive_resume=progressive_resume,
            progressive_chunk_seconds=progressive_chunk_seconds,
            progressive_max_workers=progressive_max_workers,
            native_threads=native_threads,
        )

        return job

    def _get_checked_paths(self) -> list[Path]:
        """Get list of checked file paths."""
        checked = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(Path(item.text()))
        return checked

    def _on_progress(self, event: ProgressEvent) -> None:
        """Handle progress updates."""
        if event.message:
            self.preview_output.appendPlainText(event.message)
            self._current_run_output += event.message + "\n"
            # Update view dialog if open
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.update_run_output(self._current_run_output)

        if event.total_duration_seconds is not None:
            self.progress_bar.setRange(0, 1000)

        if (
            event.processed_duration_seconds is not None
            and event.total_duration_seconds is not None
            and event.total_duration_seconds > 0
        ):
            value = int(
                min(1.0, event.processed_duration_seconds / event.total_duration_seconds)
                * 1000
            )
            self.progress_bar.setValue(value)

        if event.stage == "transcribe" and event.message:
            self.status_label.setText(event.message)

        # Update View Dialog with progressive segments in real-time
        if event.segments and self._view_dialog is not None and self._view_dialog.isVisible():
            self._view_dialog.append_progress_segments(event)

        # Detect progressive cache file during transcription
        # Check every 3 progress events to avoid excessive file system access
        self._progress_event_count += 1
        if (
            self._last_transcript_path is None
            and self._current_output_dir is not None
            and self._progress_event_count % 3 == 0
        ):
            self._detect_progressive_cache()

    def _on_finished(self, result: Any) -> None:
        """Handle transcription completion."""
        # Store result for later use
        self._last_result = result

        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0 if result.canceled else 1)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        # Format elapsed time
        elapsed_time_str = ""
        if result.elapsed_seconds is not None:
            elapsed = result.elapsed_seconds
            if elapsed < 60:
                elapsed_time_str = f" (Time: {elapsed:.1f}s)"
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                elapsed_time_str = f" (Time: {minutes}m {seconds}s)"

        if result.canceled:
            self.status_label.setText(
                f"Canceled. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\nTranscription canceled by user.")
        elif result.errors:
            self.status_label.setText(
                f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\n\nErrors occurred:")
            for error in result.errors:
                self.preview_output.appendPlainText(f"  - {error}")
        else:
            self.status_label.setText(
                f"Transcription complete! Succeeded: {result.succeeded}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\n\nTranscription completed successfully!")

        # Add elapsed time to output
        if result.elapsed_seconds is not None:
            self.preview_output.appendPlainText(f"\nElapsed time: {elapsed_time_str.strip(' ()')}")

        # Collect all output paths from result
        self._last_output_paths = []
        if result.outputs:
            self._last_output_dir = result.job.output_dir
            self.preview_output.appendPlainText("\nOutput files:")
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    self.preview_output.appendPlainText(f"  {path}")
                    self._last_output_paths.append(path)
                    # Track transcript JSON path
                    if path.suffix.lower() == ".json" and self._last_transcript_path is None:
                        self._last_transcript_path = path

        # Auto-update the View dialog if it's currently open
        if self._last_transcript_path is not None and self._view_dialog is not None:
            if self._view_dialog.isVisible():
                # Pass all output paths to the dialog for workspace loading
                self._view_dialog._load_transcript_with_artifacts(
                    self._last_transcript_path,
                    tuple(self._last_output_paths)
                )

        self.transcription_finished.emit(result)

    def _on_failed(self, error: str) -> None:
        """Handle transcription failure."""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText(f"Transcription failed: {error}")
        self.preview_output.appendPlainText(f"\n\nFailed: {error}")
        self.transcription_error.emit(error)

    def _on_warning(self, warning: str) -> None:
        """Handle transcription warning."""
        # Display warning in preview output with yellow color
        self.preview_output.appendHtml(
            f'<span style="color: #FFA500;">⚠ Warning: {warning}</span>'
        )

    def _clear_worker_refs(self) -> None:
        """Clear worker and thread references."""
        self._worker = None
        self._thread = None

    def _cancel_transcription(self) -> None:
        """Cancel transcription process."""
        if self._thread is None or self._worker is None:
            self.status_label.setText("No transcription job is currently running.")
            return
        if self._cancel_requested:
            self.status_label.setText("Cancellation already requested...")
            return

        self._cancel_requested = True
        self._worker.request_cancel()
        self._thread.requestInterruption()
        self.status_label.setText("Canceling transcription... (may take a few seconds)")
        self.cancel_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.preview_output.appendPlainText("\n[Cancellation requested - stopping at next checkpoint...]")

    def _request_settings(self) -> None:
        """Request settings dialog to be shown."""
        self.settings_requested.emit()

    def _open_transcript(self) -> None:
        """Open transcript JSON file."""
        from PySide6.QtWidgets import QFileDialog
        import json

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Transcript JSON",
            "",
            "JSON files (*.json);;All files (*.*)"
        )
        if file_path:
            try:
                path = Path(file_path)
                with open(path, 'r', encoding='utf-8') as f:
                    transcript_data = json.load(f)

                # Verify it's a valid transcript JSON
                if 'segments' not in transcript_data:
                    self.status_label.setText("Invalid transcript format - missing segments")
                    return

                # Set as current transcript and open View
                self._last_transcript_path = path
                self._current_run_output = f"Opened existing transcript: {path.name}\n"

                # Update View dialog with the loaded transcript
                if self._view_dialog is not None:
                    self._view_dialog._load_transcript(path)
                    self._view_dialog.update_run_output(self._current_run_output)

                # Show the View dialog
                self._open_view()

                self.transcript_loaded.emit(path)
            except Exception as e:
                self.status_label.setText(f"Error loading transcript: {e}")

    def _create_view_dialog(self) -> None:
        """Create View Dialog at initialization (like old version)."""
        from flowscribe.gui.dialogs import TranscriptionViewDialog

        self._view_dialog = TranscriptionViewDialog(
            self,
            transcript_path=None,  # No transcript initially
            run_output="",
            result=None,
            output_paths=None,
        )
        # Don't show it yet - user will click "Open View" to show it

    def _open_view(self) -> None:
        """Open transcription view dialog."""
        if self._view_dialog is None:
            self._create_view_dialog()

        # Update dialog with current state before showing
        if self._last_transcript_path is not None and self._last_output_paths:
            self._view_dialog._load_transcript_with_artifacts(
                self._last_transcript_path,
                tuple(self._last_output_paths)
            )
        elif self._last_transcript_path is not None:
            self._view_dialog._load_transcript(self._last_transcript_path)

        # Always update run output
        self._view_dialog.update_run_output(self._current_run_output)

        # Show the dialog
        self._view_dialog.show()
        self._view_dialog.raise_()
        self._view_dialog.activateWindow()

        status_msg = f"Opened view for {self._last_transcript_path.name}" if self._last_transcript_path else "Opened view"
        self.status_label.setText(status_msg)

    def _detect_progressive_cache(self) -> None:
        """Detect progressive cache JSON file during transcription."""
        if self._current_output_dir is None:
            return

        try:
            # Progressive cache is stored in work_dir/item_stem/.progressive/partial-transcript.json
            # Search in the output directory's parent for progressive cache files
            search_root = self._current_output_dir.parent
            if not search_root.exists():
                search_root = self._current_output_dir

            # Look for .progressive/partial-transcript.json files (limit depth to 2 levels)
            progressive_files = []
            for item in search_root.iterdir():
                if item.is_dir():
                    progressive_path = item / ".progressive" / "partial-transcript.json"
                    if progressive_path.exists():
                        # Only consider files modified after transcription started
                        if progressive_path.stat().st_mtime >= self._transcription_start_time:
                            progressive_files.append(progressive_path)

            # Also check output directory itself for any JSON files (fallback)
            if not progressive_files and self._current_output_dir.exists():
                json_files = []
                for json_file in self._current_output_dir.glob("*.json"):
                    # Only consider files modified after transcription started
                    if json_file.stat().st_mtime >= self._transcription_start_time:
                        json_files.append(json_file)

                if json_files:
                    # Find the most recently modified JSON file
                    latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
                    progressive_files = [latest_json]

            if not progressive_files:
                return

            # Use the most recently modified progressive cache file
            latest_cache = max(progressive_files, key=lambda p: p.stat().st_mtime)

            # Verify it's a valid transcript JSON
            import json
            with open(latest_cache, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'segments' not in data or not data['segments']:
                    return

            # Set as current transcript
            self._last_transcript_path = latest_cache
            # Add to output paths if not already there
            if latest_cache not in self._last_output_paths:
                self._last_output_paths.append(latest_cache)

            # Auto-update the View dialog if it's currently open
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog._load_transcript_with_artifacts(
                    self._last_transcript_path,
                    tuple(self._last_output_paths)
                )

            # Update status to inform user
            self.status_label.setText(
                "Progressive cache detected - You can now open View to see progress"
            )

        except Exception:
            # Silently ignore errors during cache detection
            pass



