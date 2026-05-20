"""Single task transcription view."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flowscribe.app.models import ProgressEvent, SourceSpec, TranscriptionJob
from flowscribe.gui.state import is_acceptable_local_source
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
        self._current_run_output: str = ""
        self._view_dialog = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Source selection area
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(10)

        # Local files section
        local_label = QLabel("Local Files:")
        source_layout.addWidget(local_label)

        self.file_list = SourceListWidget()
        self.file_list.setMinimumHeight(180)
        self.file_list.files_dropped.connect(self._add_dropped_files)
        self.file_list.itemChanged.connect(self._on_file_list_changed)
        source_layout.addWidget(self.file_list)

        file_actions = QHBoxLayout()
        add_file_button = QPushButton("Add Files")
        add_file_button.clicked.connect(self._choose_files)
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self._select_all_files)
        clear_files_button = QPushButton("Clear")
        clear_files_button.clicked.connect(self._clear_files)
        file_actions.addWidget(add_file_button)
        file_actions.addWidget(select_all_button)
        file_actions.addWidget(clear_files_button)
        file_actions.addStretch(1)
        source_layout.addLayout(file_actions)

        # URL section
        url_label = QLabel("URL:")
        source_layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/video")
        source_layout.addWidget(self.url_input)

        self.url_media_preserve_check = QCheckBox("Preserve downloaded media file")
        source_layout.addWidget(self.url_media_preserve_check)

        # System audio capture section
        capture_label = QLabel("System Audio Capture:")
        source_layout.addWidget(capture_label)

        capture_controls = QHBoxLayout()
        self.capture_start_button = QPushButton("Start Capture")
        self.capture_start_button.clicked.connect(self._start_capture)
        self.capture_stop_button = QPushButton("Stop Capture")
        self.capture_stop_button.clicked.connect(self._stop_capture)
        self.capture_stop_button.setEnabled(False)
        self.capture_status_label = QLabel("Not capturing")
        capture_controls.addWidget(self.capture_start_button)
        capture_controls.addWidget(self.capture_stop_button)
        capture_controls.addWidget(self.capture_status_label)
        capture_controls.addStretch(1)
        source_layout.addLayout(capture_controls)

        layout.addWidget(source_group)

        # Transcription controls
        controls_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Transcription")
        self.start_button.clicked.connect(self._start_transcription)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_transcription)
        self.cancel_button.setEnabled(False)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._request_settings)
        self.open_transcript_button = QPushButton("Open Transcript")
        self.open_transcript_button.clicked.connect(self._open_transcript)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.cancel_button)
        controls_layout.addWidget(self.settings_button)
        controls_layout.addWidget(self.open_transcript_button)

        self.open_view_button = QPushButton("Open View")
        self.open_view_button.clicked.connect(self._open_view)
        self.open_view_button.setEnabled(False)
        controls_layout.addWidget(self.open_view_button)

        controls_layout.addStretch(1)
        layout.addLayout(controls_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Tabs for Run Details and Workspace
        self.tabs = QTabWidget()

        # Run Details tab
        run_details_widget = QWidget()
        run_details_layout = QVBoxLayout(run_details_widget)
        run_details_layout.setContentsMargins(8, 8, 8, 8)

        self.preview_output = QPlainTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlaceholderText("Transcription progress will appear here...")
        run_details_layout.addWidget(self.preview_output)

        self.tabs.addTab(run_details_widget, "Run Details")

        # Note: Workspace tab removed - full workspace is now in the View dialog
        # Access via "Open View" button after transcription completes

        layout.addWidget(self.tabs, 1)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

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
        self.status_label.setText("Files cleared")

    def _on_file_list_changed(self) -> None:
        """Handle file list changes."""
        pass

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

        # Build sources
        sources: list[SourceSpec] = []
        for path in selected_paths:
            sources.append(SourceSpec(kind="local", value=str(path)))
        if url:
            sources.append(SourceSpec(kind="url", value=url))

        if not sources:
            self.status_label.setText("No sources selected.")
            return None

        # Create job
        job = TranscriptionJob(
            sources=tuple(sources),
            output_dir=output_dir,
            output_name_base=output_name_base,
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
            if self._view_dialog is not None:
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

    def _on_finished(self, result: Any) -> None:
        """Handle transcription completion."""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0 if result.canceled else 1)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if result.canceled:
            self.status_label.setText(
                f"Canceled. Succeeded: {result.succeeded}. Failed: {result.failed}."
            )
            self.preview_output.appendPlainText("\nTranscription canceled by user.")
        elif result.errors:
            self.status_label.setText(
                f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}."
            )
            self.preview_output.appendPlainText("\n\nErrors occurred:")
            for error in result.errors:
                self.preview_output.appendPlainText(f"  - {error}")
        else:
            self.status_label.setText(
                f"Transcription complete! Succeeded: {result.succeeded}."
            )
            self.preview_output.appendPlainText("\n\nTranscription completed successfully!")

        if result.outputs:
            self._last_output_dir = result.job.output_dir
            self.preview_output.appendPlainText("\nOutput files:")
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    self.preview_output.appendPlainText(f"  {path}")
                    # Track transcript JSON path
                    if path.suffix.lower() == ".json" and self._last_transcript_path is None:
                        self._last_transcript_path = path

        # Enable View button if we have a transcript
        if self._last_transcript_path is not None:
            self.open_view_button.setEnabled(True)

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
        self.status_label.setText("Cancellation requested...")
        self.cancel_button.setEnabled(False)
        self.preview_output.appendPlainText("\nCancellation requested...")

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
                self.open_view_button.setEnabled(True)

                # Automatically open the View dialog
                self._open_view()

                self.transcript_loaded.emit(path)
            except Exception as e:
                self.status_label.setText(f"Error loading transcript: {e}")

    def _open_view(self) -> None:
        """Open transcription view dialog."""
        from flowscribe.gui.dialogs import TranscriptionViewDialog

        if self._last_transcript_path is None:
            self.status_label.setText("No transcript available. Complete a transcription first.")
            return

        # Create or show existing view dialog
        if self._view_dialog is None or not self._view_dialog.isVisible():
            self._view_dialog = TranscriptionViewDialog(
                self,
                transcript_path=self._last_transcript_path,
                run_output=self._current_run_output,
            )
            self._view_dialog.show()
        else:
            self._view_dialog.raise_()
            self._view_dialog.activateWindow()

        self.status_label.setText(f"Opened view for {self._last_transcript_path.name}")



