"""PySide6 desktop GUI skeleton for FlowScribe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from flowscribe import __version__
from flowscribe.app.models import ProgressEvent
from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import SearchError
from flowscribe.input.file_filter import is_supported_media
from flowscribe.output.time_format import format_timestamp
from flowscribe.gui.state import (
    GuiTranscriptionForm,
    SUPPORTED_GUI_FORMATS,
    is_acceptable_local_source,
)
from flowscribe.gui.transcript_viewer import (
    TranscriptSearchHitView,
    TranscriptView,
    load_transcript_view,
    render_segment_line,
    render_transcript_summary,
    resolve_transcript_media_path,
    search_transcript_view,
    transcript_search_hit_seek_seconds,
    transcript_segment_seek_seconds,
)


def _normalize_local_source_state_payload(payload: object) -> tuple[list[Path], set[str]]:
    if not isinstance(payload, dict):
        return [], set()

    saved_paths = payload.get("local_paths")
    checked_paths = payload.get("checked_paths")
    if checked_paths is None:
        checked_paths = payload.get("selected_paths")
    if not isinstance(saved_paths, list):
        return [], set()

    local_paths: list[Path] = []
    for raw_path in saved_paths:
        candidate = Path(str(raw_path))
        if is_acceptable_local_source(candidate):
            local_paths.append(candidate)

    checked = {
        str(Path(str(raw_path)))
        for raw_path in (checked_paths or [])
        if isinstance(raw_path, str)
    }
    return local_paths, checked


def _local_source_state_payload(paths: list[Path], checked_paths: list[Path]) -> dict:
    return {
        "local_paths": [str(item) for item in paths],
        "checked_paths": [str(item) for item in checked_paths],
    }


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
        from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, QUrl, Signal, Slot
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMainWindow

        class _SourceListWidget(QListWidget):
            files_dropped = Signal(object)

            def __init__(self) -> None:
                super().__init__()
                self.setAcceptDrops(True)

            def dragEnterEvent(self, event) -> None:
                if _dropped_local_paths(event):
                    event.acceptProposedAction()
                    return
                event.ignore()

            def dragMoveEvent(self, event) -> None:
                if _dropped_local_paths(event):
                    event.acceptProposedAction()
                    return
                event.ignore()

            def dropEvent(self, event) -> None:
                paths = _dropped_local_paths(event)
                if not paths:
                    event.ignore()
                    return
                self.files_dropped.emit(paths)
                event.acceptProposedAction()

        def _dropped_local_paths(event) -> list[Path]:
            if not event.mimeData().hasUrls():
                return []
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile()
            ]
            return [path for path in paths if is_acceptable_local_source(path)]

        class _TranscriptionWorker(QObject):
            progress = Signal(str)
            finished = Signal(object)
            failed = Signal(str)

            def __init__(self, job) -> None:
                super().__init__()
                self._job = job

            @Slot()
            def run(self) -> None:
                try:
                    result = TranscriptionService().run(self._job, progress=self._handle_progress)
                except Exception as exc:  # pragma: no cover - defensive GUI boundary
                    self.failed.emit(str(exc))
                    return
                self.finished.emit(result)

            def _handle_progress(self, event: ProgressEvent) -> None:
                if event.stage == "complete":
                    self.progress.emit(event.message)
                    return
                if event.message:
                    self.progress.emit(event.message)

        def _gui_state_path() -> Path:
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            base_dir = Path(app_data) if app_data else (Path.home() / ".flowscribe")
            return base_dir / "gui-state.json"

        def _load_gui_local_source_state() -> tuple[list[Path], set[str]]:
            path = _gui_state_path()
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return [], set()
            return _normalize_local_source_state_payload(payload)

        def _save_gui_local_source_state(paths: list[Path], checked_paths: list[Path]) -> None:
            path = _gui_state_path()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(_local_source_state_payload(paths, checked_paths), ensure_ascii=False, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
            except OSError:
                return

        class _Window(QMainWindow):
            def __init__(self) -> None:
                super().__init__()
                self._local_paths: list[Path] = []
                self._saved_checked_local_paths: set[str] = set()
                self._thread: QThread | None = None
                self._worker: _TranscriptionWorker | None = None
                self._transcript_path: Path | None = None
                self._transcript_view: TranscriptView | None = None
                self._search_hits: tuple[TranscriptSearchHitView, ...] = ()
                self._media_path: Path | None = None
                self._setup_window()
                self._restore_local_sources()

            def _setup_window(self) -> None:
                from PySide6.QtWidgets import (
                    QCheckBox,
                    QComboBox,
                    QFrame,
                    QGridLayout,
                    QGroupBox,
                    QHBoxLayout,
                    QLabel,
                    QLineEdit,
                    QListWidget,
                    QProgressBar,
                    QPushButton,
                    QScrollArea,
                    QSlider,
                    QSizePolicy,
                    QTextBrowser,
                    QTextEdit,
                    QVBoxLayout,
                    QWidget,
                )

                self.setWindowTitle("FlowScribe")
                self.resize(1200, 820)
                self.setAcceptDrops(True)

                root = QWidget()
                root_layout = QHBoxLayout(root)
                root_layout.setContentsMargins(16, 16, 16, 16)
                root_layout.setSpacing(16)

                left_panel = QGroupBox("Sources")
                left_layout = QVBoxLayout(left_panel)
                left_layout.setSpacing(10)
                left_layout.setContentsMargins(12, 16, 12, 12)

                self.file_list = _SourceListWidget()
                self.file_list.setMinimumWidth(300)
                self.file_list.setMinimumHeight(240)
                self.file_list.files_dropped.connect(self._add_dropped_files)
                self.file_list.itemChanged.connect(self._persist_local_source_state)

                file_actions = QHBoxLayout()
                add_file_button = QPushButton("Add Files")
                add_file_button.clicked.connect(self._choose_files)
                select_all_button = QPushButton("Select All")
                select_all_button.clicked.connect(self._select_all_local_files)
                clear_files_button = QPushButton("Clear")
                clear_files_button.clicked.connect(self._clear_files)
                file_actions.addWidget(add_file_button)
                file_actions.addWidget(select_all_button)
                file_actions.addWidget(clear_files_button)

                self.url_input = QLineEdit()
                self.url_input.setPlaceholderText("https://example.com/video")

                left_layout.addWidget(QLabel("Local files"))
                left_layout.addWidget(self.file_list, 1)
                left_layout.addLayout(file_actions)
                left_layout.addSpacing(8)
                left_layout.addWidget(QLabel("URL"))
                left_layout.addWidget(self.url_input)
                left_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

                right_panel = QWidget()
                right_layout = QVBoxLayout(right_panel)
                right_layout.setSpacing(12)
                right_layout.setContentsMargins(0, 0, 0, 0)

                settings_box = QGroupBox("Settings")
                settings_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
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
                open_transcript_button = QPushButton("Open Transcript JSON")
                open_transcript_button.clicked.connect(self._open_transcript_json)
                self.open_transcript_button = open_transcript_button
                collect_button = QPushButton("Collect State")
                collect_button.clicked.connect(self._show_state_preview)
                self.collect_button = collect_button
                self.start_button = QPushButton("Start Transcription")
                self.start_button.clicked.connect(self._start_transcription)
                action_row.addWidget(open_transcript_button)
                action_row.addWidget(collect_button)
                action_row.addWidget(self.start_button)
                action_row.addStretch(1)

                self.status_label = QLabel("Ready. Add a local media file, choose outputs, then start transcription.")
                self.status_label.setWordWrap(True)

                media_box = QGroupBox("Media Sync")
                media_layout = QVBoxLayout(media_box)
                media_layout.setSpacing(10)
                self.video_widget = QVideoWidget()
                self.video_widget.setMinimumHeight(220)
                self.video_widget.setSizePolicy(
                    QSizePolicy.Policy.Preferred,
                    QSizePolicy.Policy.Expanding,
                )

                media_controls = QHBoxLayout()
                self.open_media_button = QPushButton("Bind Media To Transcript")
                self.open_media_button.clicked.connect(self._bind_media_to_transcript)
                self.play_media_button = QPushButton("Play")
                self.play_media_button.clicked.connect(self._toggle_media_playback)
                media_controls.addWidget(self.open_media_button)
                media_controls.addWidget(self.play_media_button)
                media_controls.addStretch(1)

                self.media_position_slider = QSlider(Qt.Orientation.Horizontal)
                self.media_position_slider.setRange(0, 0)
                self.media_position_slider.sliderMoved.connect(self._seek_media_milliseconds)

                self.media_status_label = QLabel("Open a transcript JSON file to bind media.")
                self.media_status_label.setWordWrap(True)

                media_layout.addWidget(self.video_widget)
                media_layout.addLayout(media_controls)
                media_layout.addWidget(self.media_position_slider)
                media_layout.addWidget(self.media_status_label)

                self._audio_output = QAudioOutput(self)
                self._media_player = QMediaPlayer(self)
                self._media_player.setAudioOutput(self._audio_output)
                self._media_player.setVideoOutput(self.video_widget)
                self._media_player.positionChanged.connect(self._on_media_position_changed)
                self._media_player.durationChanged.connect(self._on_media_duration_changed)
                self._media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)
                self._media_player.errorOccurred.connect(self._on_media_error)
                self.open_media_button.setEnabled(False)
                self.play_media_button.setEnabled(False)
                self.media_position_slider.setEnabled(False)

                self.progress_bar = QProgressBar()
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0)

                self.preview_output = QTextEdit()
                self.preview_output.setReadOnly(True)
                self.preview_output.setMinimumHeight(140)
                self.preview_output.setPlaceholderText("Progress and output files will appear here.")
                self.preview_output.setSizePolicy(
                    QSizePolicy.Policy.Preferred,
                    QSizePolicy.Policy.Expanding,
                )

                self.transcript_summary = QTextBrowser()
                self.transcript_summary.setReadOnly(True)
                self.transcript_summary.setMaximumHeight(110)
                self.transcript_summary.setOpenExternalLinks(False)
                self.transcript_summary.setPlaceholderText(
                    "Transcript summary will appear here."
                )
                self.transcript_summary.setSizePolicy(
                    QSizePolicy.Policy.Preferred,
                    QSizePolicy.Policy.Maximum,
                )

                search_row = QHBoxLayout()
                self.search_input = QLineEdit()
                self.search_input.setPlaceholderText("Search transcript keyword")
                self.search_input.returnPressed.connect(self._run_transcript_search)
                self.search_button = QPushButton("Search")
                self.search_button.clicked.connect(self._run_transcript_search)
                search_row.addWidget(self.search_input)
                search_row.addWidget(self.search_button)

                self.search_results = QListWidget()
                self.search_results.setMinimumHeight(110)
                self.search_results.setMaximumHeight(180)
                self.search_results.itemActivated.connect(self._jump_to_selected_hit)
                self.search_results.itemClicked.connect(self._jump_to_selected_hit)

                self.transcript_segments = QListWidget()
                self.transcript_segments.setMinimumHeight(220)
                self.transcript_segments.itemActivated.connect(self._activate_selected_segment)
                self.transcript_segments.itemClicked.connect(self._activate_selected_segment)

                right_layout.addWidget(settings_box)
                right_layout.addWidget(media_box, 1)
                right_layout.addLayout(action_row)
                right_layout.addWidget(self.status_label)
                right_layout.addWidget(self.progress_bar)
                right_layout.addWidget(QLabel("Run details"))
                right_layout.addWidget(self.preview_output)
                right_layout.addWidget(QLabel("Transcript viewer"))
                right_layout.addWidget(self.transcript_summary)
                right_layout.addLayout(search_row)
                right_layout.addWidget(QLabel("Search results"))
                right_layout.addWidget(self.search_results)
                right_layout.addWidget(QLabel("Transcript segments"))
                right_layout.addWidget(self.transcript_segments, 1)

                left_scroll = QScrollArea()
                left_scroll.setWidgetResizable(True)
                left_scroll.setFrameShape(QFrame.Shape.NoFrame)
                left_scroll.setWidget(left_panel)

                right_scroll = QScrollArea()
                right_scroll.setWidgetResizable(True)
                right_scroll.setFrameShape(QFrame.Shape.NoFrame)
                right_scroll.setWidget(right_panel)

                root_layout.addWidget(left_scroll, 1)
                root_layout.addWidget(right_scroll, 2)
                self.setCentralWidget(root)

            def dragEnterEvent(self, event) -> None:
                if _dropped_local_paths(event):
                    event.acceptProposedAction()
                    return
                event.ignore()

            def dropEvent(self, event) -> None:
                paths = _dropped_local_paths(event)
                if not paths:
                    event.ignore()
                    return
                self._add_dropped_files(paths)
                event.acceptProposedAction()

            def _add_dropped_files(self, paths: list[Path]) -> None:
                added = 0
                for path in paths:
                    if self._add_local_file(path):
                        added += 1
                if added:
                    self.status_label.setText(f"Added {added} local source(s).")
                    self._check_newly_added_sources(paths)
                    self._persist_local_source_state()
                else:
                    self.status_label.setText("No new supported local sources were added.")

            def _choose_files(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                paths, _ = QFileDialog.getOpenFileNames(self, "Choose media files")
                if not paths:
                    return
                for path in paths:
                    self._add_local_file(Path(path))
                self._check_newly_added_sources(Path(path) for path in paths)
                self._persist_local_source_state()

            def _add_local_file(self, path: Path) -> bool:
                if not is_acceptable_local_source(path):
                    self.status_label.setText(f"Unsupported local source: {path}")
                    return False
                if path in self._local_paths:
                    return False
                self._local_paths.append(path)
                item = QListWidgetItem(str(path))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.file_list.addItem(item)
                return True

            def _clear_files(self) -> None:
                self._local_paths.clear()
                self.file_list.clear()
                self._persist_local_source_state()

            def _select_all_local_files(self) -> None:
                for index in range(self.file_list.count()):
                    item = self.file_list.item(index)
                    if item is not None:
                        item.setCheckState(Qt.CheckState.Checked)
                self._persist_local_source_state()

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

            def _open_transcript_json(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Open transcript JSON",
                    self.output_dir_input.text().strip() or "outputs",
                    "JSON files (*.json)",
                )
                if not path:
                    return
                self._load_transcript_json(Path(path))

            def _bind_media_to_transcript(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                if self._transcript_view is None:
                    self.media_status_label.setText("Open a transcript JSON file before binding media.")
                    return

                path, _ = QFileDialog.getOpenFileName(self, "Bind media to transcript")
                if not path:
                    return
                self._bind_media_path(Path(path))

            def _form(self) -> GuiTranscriptionForm:
                selected_local_paths = tuple(self._checked_local_paths())
                output_formats = tuple(
                    output_format
                    for output_format, checkbox in self.format_checks.items()
                    if checkbox.isChecked()
                )
                language = self.language_combo.currentText()
                preset = self.preset_combo.currentText()
                cookies_text = self.cookies_input.text().strip()

                return GuiTranscriptionForm(
                    local_paths=selected_local_paths,
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
                selection_error = self._local_selection_error()
                if selection_error:
                    self.status_label.setText(selection_error)
                    self.preview_output.clear()
                    return

                form = self._form()
                errors = form.validate()
                if errors:
                    self.status_label.setText(" ".join(errors))
                    self.preview_output.clear()
                    return

                preview = form.preview()
                self.status_label.setText("State collected successfully.")
                self.preview_output.setPlainText(json.dumps(preview, ensure_ascii=False, indent=2))

            def _start_transcription(self) -> None:
                if self._thread is not None:
                    self.status_label.setText("A transcription job is already running.")
                    return

                selection_error = self._local_selection_error()
                if selection_error:
                    self.status_label.setText(selection_error)
                    self.preview_output.clear()
                    return

                form = self._form()
                errors = form.validate()
                if errors:
                    self.status_label.setText(" ".join(errors))
                    self.preview_output.clear()
                    return

                job = form.to_job()
                self.preview_output.setPlainText(
                    "Starting transcription...\n\n"
                    + json.dumps(form.preview(), ensure_ascii=False, indent=2)
                    + "\n"
                )
                self.status_label.setText("Running transcription in the background...")
                self.progress_bar.setRange(0, 0)
                self.start_button.setEnabled(False)
                self.collect_button.setEnabled(False)

                self._thread = QThread(self)
                self._worker = _TranscriptionWorker(job)
                self._worker.moveToThread(self._thread)
                self._thread.started.connect(self._worker.run)
                self._worker.progress.connect(self._append_progress)
                self._worker.finished.connect(self._finish_transcription)
                self._worker.failed.connect(self._fail_transcription)
                self._worker.finished.connect(self._thread.quit)
                self._worker.failed.connect(self._thread.quit)
                self._thread.finished.connect(self._worker.deleteLater)
                self._thread.finished.connect(self._thread.deleteLater)
                self._thread.finished.connect(self._clear_worker_refs)
                self._thread.start()

            def _append_progress(self, message: str) -> None:
                self.preview_output.append(message)

            def _finish_transcription(self, result) -> None:
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(1)
                self.start_button.setEnabled(True)
                self.collect_button.setEnabled(True)

                if result.errors:
                    self.status_label.setText(
                        f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}."
                    )
                    self.preview_output.append("\nFailures:")
                    for error in result.errors:
                        self.preview_output.append(f"- {error.source}: {error.message}")
                    return

                self.status_label.setText(f"Done. Succeeded: {result.succeeded}.")
                self.preview_output.append("\nOutput files:")
                transcript_loaded = False
                for artifacts in result.outputs:
                    for path in artifacts.paths:
                        self.preview_output.append(str(path))
                        if not transcript_loaded and path.suffix.lower() == ".json":
                            transcript_loaded = self._load_transcript_json(path)
                if not transcript_loaded:
                    self.transcript_summary.setPlainText("No transcript JSON output was generated for this run.")
                    self.transcript_segments.clear()

            def _fail_transcription(self, message: str) -> None:
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0)
                self.start_button.setEnabled(True)
                self.collect_button.setEnabled(True)
                self.status_label.setText("Transcription failed.")
                self.preview_output.append(f"\nError: {message}")

            def _clear_worker_refs(self) -> None:
                self._thread = None
                self._worker = None

            def _load_transcript_json(self, path: Path) -> bool:
                try:
                    view = load_transcript_view(path)
                except ValueError as exc:
                    self.status_label.setText("Could not open transcript JSON.")
                    self.transcript_summary.setPlainText(str(exc))
                    self.transcript_segments.clear()
                    self.search_results.clear()
                    self._search_hits = ()
                    return False

                self._transcript_path = path
                self._transcript_view = view
                self._search_hits = ()
                self.search_results.clear()
                self._clear_media_binding()
                self.open_media_button.setEnabled(True)
                self.transcript_summary.setPlainText(render_transcript_summary(view))
                self.transcript_segments.clear()
                for segment in view.segments:
                    self.transcript_segments.addItem(render_segment_line(segment))
                self._load_media_for_transcript(view)
                self.status_label.setText(f"Loaded transcript JSON: {path.name}")
                return True

            def _run_transcript_search(self) -> None:
                if self._transcript_path is None or self._transcript_view is None:
                    self.status_label.setText("Open a transcript JSON file before searching.")
                    return

                query = self.search_input.text().strip()
                if not query:
                    self.status_label.setText("Enter a keyword to search.")
                    self.search_results.clear()
                    self._search_hits = ()
                    return

                try:
                    hits = search_transcript_view(
                        self._transcript_path,
                        self._transcript_view,
                        query,
                    )
                except SearchError as exc:
                    self.status_label.setText(str(exc))
                    self.search_results.clear()
                    self._search_hits = ()
                    return

                self._search_hits = hits
                self.search_results.clear()
                if not hits:
                    self.status_label.setText(f'No matches found for "{query}".')
                    return

                for hit in hits:
                    label = (
                        f"[{hit.segment_index + 1}] "
                        f"{hit.context} "
                        f"({format_timestamp(hit.start_seconds)}"
                        f" - {format_timestamp(hit.end_seconds)})"
                    )
                    self.search_results.addItem(label)
                self.status_label.setText(f'Found {len(hits)} match(es) for "{query}".')
                self.search_results.setCurrentRow(0)
                self._jump_to_hit(hits[0])

            def _jump_to_selected_hit(self, *_args) -> None:
                row = self.search_results.currentRow()
                if row < 0 or row >= len(self._search_hits):
                    return
                self._jump_to_hit(self._search_hits[row])

            def _jump_to_hit(self, hit: TranscriptSearchHitView) -> None:
                if self._transcript_view is None:
                    return
                if hit.segment_index >= len(self._transcript_view.segments):
                    return

                self.transcript_segments.setCurrentRow(hit.segment_index)
                item = self.transcript_segments.currentItem()
                if item is not None:
                    self.transcript_segments.scrollToItem(item)
                self.transcript_segments.setFocus()
                self._seek_media_seconds(transcript_search_hit_seek_seconds(hit), autoplay=True)

            def _activate_selected_segment(self, *_args) -> None:
                if self._transcript_view is None:
                    return
                row = self.transcript_segments.currentRow()
                if row < 0 or row >= len(self._transcript_view.segments):
                    return
                segment = self._transcript_view.segments[row]
                self._seek_media_seconds(transcript_segment_seek_seconds(segment), autoplay=True)

            def _load_media_for_transcript(self, view: TranscriptView) -> None:
                media_path = resolve_transcript_media_path(view)
                if media_path is None:
                    self.media_status_label.setText(
                        "Transcript loaded. Bind a local media file to enable sync playback."
                    )
                    return
                self._bind_media_path(media_path, auto_bound=True)

            def _bind_media_path(
                self,
                path: Path,
                *,
                auto_bound: bool = False,
            ) -> bool:
                if not path.is_file() or not is_supported_media(path):
                    self.media_status_label.setText(f"Unsupported media file: {path}")
                    return False

                self._media_path = path
                self._media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
                self.media_position_slider.setValue(0)
                self.play_media_button.setEnabled(True)
                self.media_position_slider.setEnabled(True)
                if auto_bound:
                    self.media_status_label.setText(f"Auto-bound media: {path.name}")
                else:
                    self.media_status_label.setText(f"Bound media to transcript: {path.name}")
                return True

            def _seek_media_seconds(self, seconds: float, *, autoplay: bool) -> None:
                if self._media_path is None:
                    self.media_status_label.setText(
                        "Bind a local media file to this transcript before syncing playback."
                    )
                    return

                self._media_player.setPosition(int(max(0.0, seconds) * 1000))
                if autoplay:
                    self._media_player.play()

            def _seek_media_milliseconds(self, value: int) -> None:
                self._media_player.setPosition(value)

            def _toggle_media_playback(self) -> None:
                if self._media_path is None:
                    self.media_status_label.setText("Bind a local media file to this transcript before playback.")
                    return
                if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self._media_player.pause()
                    return
                self._media_player.play()

            def _on_media_position_changed(self, position: int) -> None:
                if not self.media_position_slider.isSliderDown():
                    self.media_position_slider.setValue(position)

            def _on_media_duration_changed(self, duration: int) -> None:
                self.media_position_slider.setRange(0, max(0, duration))

            def _on_media_playback_state_changed(self, state) -> None:
                if state == QMediaPlayer.PlaybackState.PlayingState:
                    self.play_media_button.setText("Pause")
                    return
                self.play_media_button.setText("Play")

            def _on_media_error(self, *_args) -> None:
                message = self._media_player.errorString().strip() or "Unknown media playback error."
                self.media_status_label.setText(f"Media error: {message}")

            def _clear_media_binding(self) -> None:
                self._media_path = None
                self._media_player.stop()
                self._media_player.setSource(QUrl())
                self.media_position_slider.setRange(0, 0)
                self.media_position_slider.setValue(0)
                self.media_position_slider.setEnabled(False)
                self.play_media_button.setEnabled(False)

            def _checked_local_paths(self) -> list[Path]:
                checked_paths: list[Path] = []
                for index in range(self.file_list.count()):
                    item = self.file_list.item(index)
                    if item is None or item.checkState() != Qt.CheckState.Checked:
                        continue
                    try:
                        checked_paths.append(Path(item.text()))
                    except OSError:
                        continue
                return checked_paths

            def _local_selection_error(self) -> str | None:
                if self.url_input.text().strip():
                    return None
                if not self._local_paths:
                    return None
                if self._checked_local_paths():
                    return None
                return "Check at least one local source or paste a URL."

            def _restore_local_sources(self) -> None:
                from PySide6.QtCore import QSignalBlocker

                local_paths, checked = _load_gui_local_source_state()
                self._saved_checked_local_paths = checked
                if not local_paths:
                    return

                blocker = QSignalBlocker(self.file_list)
                try:
                    for path in local_paths:
                        self._add_local_file(path)
                    for index in range(self.file_list.count()):
                        item = self.file_list.item(index)
                        if item is not None and item.text() in self._saved_checked_local_paths:
                            item.setCheckState(Qt.CheckState.Checked)
                finally:
                    del blocker
                self._persist_local_source_state()

            def _persist_local_source_state(self) -> None:
                _save_gui_local_source_state(self._local_paths, self._checked_local_paths())

            def _check_newly_added_sources(self, paths) -> None:
                added = {str(Path(path)) for path in paths}
                for index in range(self.file_list.count()):
                    item = self.file_list.item(index)
                    if item is not None and item.text() in added:
                        item.setCheckState(Qt.CheckState.Checked)

        return _Window()
