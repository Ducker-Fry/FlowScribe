"""PySide6 desktop GUI skeleton for FlowScribe."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from flowscribe import __version__
from flowscribe.app.models import ProgressEvent
from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import MediaPreparationError, SearchError
from flowscribe.input.file_filter import is_supported_media
from flowscribe.gui.gui_logging import configure_gui_logging, get_gui_logger
from flowscribe.media.system_audio_capture_helper import CaptureController
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
    transcript_media_binding_warning,
    transcript_segment_index_for_seconds,
    transcript_search_hit_seek_seconds,
    transcript_segment_seek_seconds,
)

LOGGER = get_gui_logger(__name__)

GUI_MODEL_OPTIONS = ("small", "tiny", "base", "medium", "large-v3-turbo", "large-v3")
GUI_LANGUAGE_OPTIONS = ("auto", "zh", "en")
GUI_PRESET_OPTIONS = ("none", "zh")
GUI_NETWORK_OPTIONS = ("auto", "ipv4", "ipv6")
DEFAULT_GUI_PREFERENCES = {
    "output_dir": "outputs",
    "output_name_base": "",
    "model_name": "small",
    "language": "auto",
    "preset": "none",
    "output_formats": ["txt", "md", "json"],
    "timestamps": True,
    "word_timestamps": False,
    "overwrite": False,
    "keep_media": False,
    "network_family": "auto",
    "proxy": "",
}
MAX_RECENT_TRANSCRIPTS = 8
MAX_RECENT_OUTPUT_DIRS = 8
MAX_RECENT_JOBS = 10
MAX_RECENT_MEDIA_BINDINGS = 8


def _default_recent_work() -> dict[str, list[dict[str, object]] | list[str]]:
    return {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
    }


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


def _gui_preferences_payload(preferences: dict[str, object]) -> dict[str, object]:
    payload = _normalize_gui_preferences_payload(preferences)
    payload["output_formats"] = list(payload["output_formats"])
    return payload


def _normalize_gui_preferences_payload(payload: object) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    if isinstance(source.get("preferences"), dict):
        source = source["preferences"]

    output_formats = source.get("output_formats")
    normalized_formats = [
        output_format
        for output_format in (output_formats or [])
        if output_format in SUPPORTED_GUI_FORMATS
    ]

    output_dir = source.get("output_dir")
    output_name_base = source.get("output_name_base")
    model_name = source.get("model_name")
    language = source.get("language")
    preset = source.get("preset")
    network_family = source.get("network_family")
    proxy = source.get("proxy")

    return {
        "output_dir": output_dir if isinstance(output_dir, str) and output_dir.strip() else "outputs",
        "output_name_base": output_name_base if isinstance(output_name_base, str) else "",
        "model_name": model_name if model_name in GUI_MODEL_OPTIONS else "small",
        "language": language if language in GUI_LANGUAGE_OPTIONS else "auto",
        "preset": preset if preset in GUI_PRESET_OPTIONS else "none",
        "output_formats": normalized_formats or ["txt", "md", "json"],
        "timestamps": bool(source.get("timestamps", True)),
        "word_timestamps": bool(source.get("word_timestamps", False)),
        "overwrite": bool(source.get("overwrite", False)),
        "keep_media": bool(source.get("keep_media", False)),
        "network_family": network_family if network_family in GUI_NETWORK_OPTIONS else "auto",
        "proxy": proxy if isinstance(proxy, str) else "",
    }


def _gui_state_payload(
    paths: list[Path],
    checked_paths: list[Path],
    preferences: dict[str, object],
    recent_work: dict[str, list[dict[str, object]] | list[str]] | None = None,
) -> dict[str, object]:
    return {
        "version": 3,
        "preferences": _gui_preferences_payload(preferences),
        "local_sources": _local_source_state_payload(paths, checked_paths),
        "recent_work": _recent_work_payload(recent_work),
    }


def _normalize_recent_work_entry_paths(
    values: object,
    *,
    max_items: int,
    expect_directory: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        return []

    seen: set[str] = set()
    normalized: list[str] = []
    for raw_value in values:
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        try:
            path = Path(raw_value)
        except OSError:
            continue
        path_text = str(path)
        if path_text in seen:
            continue
        if path.exists():
            if expect_directory and not path.is_dir():
                continue
            if not expect_directory and not path.is_file():
                continue
        seen.add(path_text)
        normalized.append(path_text)
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_recent_job_entries(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for raw_value in values:
        if not isinstance(raw_value, dict):
            continue

        label = raw_value.get("label")
        status = raw_value.get("status")
        output_dir = raw_value.get("output_dir")
        transcript_path = raw_value.get("transcript_path")
        media_path = raw_value.get("media_path")

        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(status, str) or not status.strip():
            continue
        if not isinstance(output_dir, str) or not output_dir.strip():
            continue
        if transcript_path is not None and not isinstance(transcript_path, str):
            transcript_path = None
        if media_path is not None and not isinstance(media_path, str):
            media_path = None

        identity = (
            label.strip(),
            status.strip(),
            output_dir.strip(),
            (transcript_path or "").strip(),
            (media_path or "").strip(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "label": identity[0],
                "status": identity[1],
                "output_dir": identity[2],
                "transcript_path": identity[3],
                "media_path": identity[4],
            }
        )
        if len(normalized) >= MAX_RECENT_JOBS:
            break
    return normalized


def _normalize_recent_media_bindings(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_value in values:
        if not isinstance(raw_value, dict):
            continue
        transcript_path = raw_value.get("transcript_path")
        media_path = raw_value.get("media_path")
        if not isinstance(transcript_path, str) or not transcript_path.strip():
            continue
        if not isinstance(media_path, str) or not media_path.strip():
            continue
        identity = (transcript_path.strip(), media_path.strip())
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "transcript_path": identity[0],
                "media_path": identity[1],
            }
        )
        if len(normalized) >= MAX_RECENT_MEDIA_BINDINGS:
            break
    return normalized


def _recent_work_payload(payload: object) -> dict[str, list[dict[str, object]] | list[str]]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "recent_transcripts": _normalize_recent_work_entry_paths(
            source.get("recent_transcripts"),
            max_items=MAX_RECENT_TRANSCRIPTS,
        ),
        "recent_output_dirs": _normalize_recent_work_entry_paths(
            source.get("recent_output_dirs"),
            max_items=MAX_RECENT_OUTPUT_DIRS,
            expect_directory=True,
        ),
        "recent_jobs": _normalize_recent_job_entries(source.get("recent_jobs")),
        "recent_media_bindings": _normalize_recent_media_bindings(
            source.get("recent_media_bindings")
        ),
    }


def _normalize_gui_state_payload(
    payload: object,
) -> tuple[list[Path], set[str], dict[str, object], dict[str, list[dict[str, object]] | list[str]]]:
    if not isinstance(payload, dict):
        return [], set(), _gui_preferences_payload(DEFAULT_GUI_PREFERENCES), _default_recent_work()

    local_payload = payload.get("local_sources") if isinstance(payload.get("local_sources"), dict) else payload
    local_paths, checked = _normalize_local_source_state_payload(local_payload)
    preferences = _normalize_gui_preferences_payload(payload)
    recent_work = _recent_work_payload(payload.get("recent_work"))
    return local_paths, checked, preferences, recent_work


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
                self._cancel_requested = False

            @Slot()
            def request_cancel(self) -> None:
                self._cancel_requested = True

            @Slot()
            def run(self) -> None:
                try:
                    result = TranscriptionService().run(
                        self._job,
                        progress=self._handle_progress,
                        should_cancel=lambda: self._cancel_requested,
                    )
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

        def _load_gui_state() -> tuple[
            list[Path],
            set[str],
            dict[str, object],
            dict[str, list[dict[str, object]] | list[str]],
        ]:
            path = _gui_state_path()
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return [], set(), _gui_preferences_payload(DEFAULT_GUI_PREFERENCES), _default_recent_work()
            return _normalize_gui_state_payload(payload)

        def _save_gui_state(
            paths: list[Path],
            checked_paths: list[Path],
            preferences: dict[str, object],
            recent_work: dict[str, list[dict[str, object]] | list[str]],
        ) -> None:
            path = _gui_state_path()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        _gui_state_payload(paths, checked_paths, preferences, recent_work),
                        ensure_ascii=False,
                        indent=2,
                    )
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
                self._saved_preferences = _gui_preferences_payload(DEFAULT_GUI_PREFERENCES)
                self._thread: QThread | None = None
                self._worker: _TranscriptionWorker | None = None
                self._cancel_requested = False
                self._last_output_dir: Path | None = None
                self._transcript_path: Path | None = None
                self._transcript_view: TranscriptView | None = None
                self._search_hits: tuple[TranscriptSearchHitView, ...] = ()
                self._media_path: Path | None = None
                self._media_binding_mode = "unbound"
                self._active_segment_row = -1
                self._settings_dialog: object | None = None
                self._settings_viewer: object | None = None
                self._recent_work = _default_recent_work()
                self._recent_work_dialog: object | None = None
                self._recent_transcripts_list: object | None = None
                self._recent_output_dirs_list: object | None = None
                self._recent_jobs_list: object | None = None
                self._recent_media_bindings_list: object | None = None
                self._capture_controller = CaptureController()
                self._capture_default_device_name: str | None = None
                self._active_capture_path: Path | None = None
                self._temporary_capture_paths: set[Path] = set()
                self._capture_supported = False
                self._setup_window()
                self._restore_gui_state()
                self._refresh_capture_support()

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
                left_layout.addSpacing(8)
                left_layout.addWidget(QLabel("System audio capture"))

                capture_controls = QHBoxLayout()
                self.start_capture_button = QPushButton("Start Capture")
                self.start_capture_button.clicked.connect(self._start_system_capture)
                self.stop_capture_button = QPushButton("Stop Capture")
                self.stop_capture_button.clicked.connect(self._stop_system_capture)
                self.stop_capture_button.setEnabled(False)
                capture_controls.addWidget(self.start_capture_button)
                capture_controls.addWidget(self.stop_capture_button)

                self.keep_capture_file_check = QCheckBox("Keep capture file")
                self.capture_status_label = QLabel("System capture is idle.")
                self.capture_status_label.setWordWrap(True)

                left_layout.addLayout(capture_controls)
                left_layout.addWidget(self.keep_capture_file_check)
                left_layout.addWidget(self.capture_status_label)
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
                self.output_name_input = QLineEdit()
                self.output_name_input.setPlaceholderText("Optional custom output name")

                output_row = QHBoxLayout()
                output_row.addWidget(self.output_dir_input)
                output_row.addWidget(choose_output_button)

                self.model_combo = QComboBox()
                self.model_combo.addItems(list(GUI_MODEL_OPTIONS))

                self.language_combo = QComboBox()
                self.language_combo.addItems(list(GUI_LANGUAGE_OPTIONS))

                self.preset_combo = QComboBox()
                self.preset_combo.addItems(list(GUI_PRESET_OPTIONS))

                self.network_combo = QComboBox()
                self.network_combo.addItems(list(GUI_NETWORK_OPTIONS))

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
                settings_layout.addWidget(QLabel("Output name"), 1, 0)
                settings_layout.addWidget(self.output_name_input, 1, 1)
                settings_layout.addWidget(QLabel("Model"), 2, 0)
                settings_layout.addWidget(self.model_combo, 2, 1)
                settings_layout.addWidget(QLabel("Language"), 3, 0)
                settings_layout.addWidget(self.language_combo, 3, 1)
                settings_layout.addWidget(QLabel("Preset"), 4, 0)
                settings_layout.addWidget(self.preset_combo, 4, 1)
                settings_layout.addWidget(QLabel("Formats"), 5, 0)
                settings_layout.addLayout(format_row, 5, 1)
                settings_layout.addWidget(QLabel("Network"), 6, 0)
                settings_layout.addWidget(self.network_combo, 6, 1)
                settings_layout.addWidget(QLabel("Proxy"), 7, 0)
                settings_layout.addWidget(self.proxy_input, 7, 1)
                settings_layout.addWidget(QLabel("Cookies"), 8, 0)
                settings_layout.addLayout(cookies_row, 8, 1)
                settings_layout.addWidget(self.timestamps_check, 9, 1)
                settings_layout.addWidget(self.word_timestamps_check, 10, 1)
                settings_layout.addWidget(self.overwrite_check, 11, 1)
                settings_layout.addWidget(self.keep_media_check, 12, 1)

                action_layout = QGridLayout()
                action_layout.setHorizontalSpacing(8)
                action_layout.setVerticalSpacing(8)
                open_transcript_button = QPushButton("Open Transcript JSON")
                open_transcript_button.clicked.connect(self._open_transcript_json)
                self.open_transcript_button = open_transcript_button
                self.view_settings_button = QPushButton("View Settings")
                self.view_settings_button.clicked.connect(self._show_saved_settings)
                self.view_recent_work_button = QPushButton("Recent Work")
                self.view_recent_work_button.clicked.connect(self._show_recent_work)
                self.save_settings_button = QPushButton("Save Settings")
                self.save_settings_button.clicked.connect(self._save_settings)
                collect_button = QPushButton("Collect State")
                collect_button.clicked.connect(self._show_state_preview)
                self.collect_button = collect_button
                self.start_button = QPushButton("Start Transcription")
                self.start_button.clicked.connect(self._start_transcription)
                self.cancel_button = QPushButton("Cancel Transcription")
                self.cancel_button.clicked.connect(self._cancel_transcription)
                self.cancel_button.setEnabled(False)
                self.open_output_button = QPushButton("Open Output Folder")
                self.open_output_button.clicked.connect(self._open_output_dir)
                self.open_output_button.setEnabled(False)
                action_buttons = [
                    open_transcript_button,
                    self.view_settings_button,
                    self.view_recent_work_button,
                    self.save_settings_button,
                    collect_button,
                    self.start_button,
                    self.cancel_button,
                    self.open_output_button,
                ]
                for index, button in enumerate(action_buttons):
                    row = index // 4
                    column = index % 4
                    action_layout.addWidget(button, row, column)
                for column in range(4):
                    action_layout.setColumnStretch(column, 1)

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
                self.media_binding_label = QLabel("Binding: Unbound")
                self.media_binding_label.setWordWrap(True)

                media_layout.addWidget(self.video_widget)
                media_layout.addLayout(media_controls)
                media_layout.addWidget(self.media_position_slider)
                media_layout.addWidget(self.media_binding_label)
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
                right_layout.addLayout(action_layout)
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
                self._cleanup_temporary_capture_files()
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
                    self._remember_recent_output_dir(Path(path))

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
                    output_name_base=self.output_name_input.text(),
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

            def _current_gui_preferences(self) -> dict[str, object]:
                return {
                    "output_dir": self.output_dir_input.text().strip() or "outputs",
                    "output_name_base": self.output_name_input.text(),
                    "model_name": self.model_combo.currentText(),
                    "language": self.language_combo.currentText(),
                    "preset": self.preset_combo.currentText(),
                    "output_formats": [
                        output_format
                        for output_format, checkbox in self.format_checks.items()
                        if checkbox.isChecked()
                    ],
                    "timestamps": self.timestamps_check.isChecked(),
                    "word_timestamps": self.word_timestamps_check.isChecked(),
                    "overwrite": self.overwrite_check.isChecked(),
                    "keep_media": self.keep_media_check.isChecked(),
                    "network_family": self.network_combo.currentText(),
                    "proxy": self.proxy_input.text(),
                }

            def _apply_gui_preferences(self, preferences: dict[str, object]) -> None:
                self.output_dir_input.setText(str(preferences["output_dir"]))
                self.output_name_input.setText(str(preferences["output_name_base"]))
                self.model_combo.setCurrentText(str(preferences["model_name"]))
                self.language_combo.setCurrentText(str(preferences["language"]))
                self.preset_combo.setCurrentText(str(preferences["preset"]))
                self.network_combo.setCurrentText(str(preferences["network_family"]))
                self.proxy_input.setText(str(preferences["proxy"]))

                enabled_formats = {str(value) for value in preferences["output_formats"]}
                for output_format, checkbox in self.format_checks.items():
                    checkbox.setChecked(output_format in enabled_formats)

                self.timestamps_check.setChecked(bool(preferences["timestamps"]))
                self.word_timestamps_check.setChecked(bool(preferences["word_timestamps"]))
                self.overwrite_check.setChecked(bool(preferences["overwrite"]))
                self.keep_media_check.setChecked(bool(preferences["keep_media"]))

            def _save_settings(self) -> None:
                self._saved_preferences = _gui_preferences_payload(self._current_gui_preferences())
                self._persist_gui_state()
                self.status_label.setText("GUI settings saved.")

            def _show_saved_settings(self) -> None:
                from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

                current_preferences = _gui_preferences_payload(self._current_gui_preferences())
                payload = {
                    "saved_preferences": self._saved_preferences,
                    "current_preferences": current_preferences,
                }
                self.status_label.setText("Showing GUI preferences.")
                if self._settings_dialog is None:
                    dialog = QDialog(self)
                    dialog.setWindowTitle("GUI Preferences")
                    dialog.resize(720, 560)

                    layout = QVBoxLayout(dialog)
                    viewer = QPlainTextEdit(dialog)
                    viewer.setReadOnly(True)
                    layout.addWidget(viewer)

                    close_button = QPushButton("Close", dialog)
                    close_button.clicked.connect(dialog.accept)

                    button_row = QHBoxLayout()
                    button_row.addStretch(1)
                    button_row.addWidget(close_button)
                    layout.addLayout(button_row)

                    self._settings_dialog = dialog
                    self._settings_viewer = viewer

                if self._settings_viewer is not None:
                    self._settings_viewer.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

                self._settings_dialog.show()
                self._settings_dialog.raise_()
                self._settings_dialog.activateWindow()

            def _show_recent_work(self) -> None:
                from PySide6.QtWidgets import (
                    QDialog,
                    QGroupBox,
                    QHBoxLayout,
                    QListWidget,
                    QPushButton,
                    QVBoxLayout,
                )

                self.status_label.setText("Showing recent work history.")
                if self._recent_work_dialog is None:
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Recent Work")
                    dialog.resize(820, 720)

                    layout = QVBoxLayout(dialog)

                    transcripts_box = QGroupBox("Recent transcript JSON")
                    transcripts_layout = QVBoxLayout(transcripts_box)
                    recent_transcripts_list = QListWidget(transcripts_box)
                    recent_transcripts_list.itemActivated.connect(self._open_selected_recent_transcript)
                    transcripts_layout.addWidget(recent_transcripts_list)
                    open_transcript_button = QPushButton("Open Selected Transcript", transcripts_box)
                    open_transcript_button.clicked.connect(self._open_selected_recent_transcript)
                    transcripts_layout.addWidget(open_transcript_button)

                    outputs_box = QGroupBox("Recent output directories")
                    outputs_layout = QVBoxLayout(outputs_box)
                    recent_output_dirs_list = QListWidget(outputs_box)
                    recent_output_dirs_list.itemActivated.connect(self._open_selected_recent_output_dir)
                    outputs_layout.addWidget(recent_output_dirs_list)
                    open_output_button = QPushButton("Open Selected Output Directory", outputs_box)
                    open_output_button.clicked.connect(self._open_selected_recent_output_dir)
                    outputs_layout.addWidget(open_output_button)

                    jobs_box = QGroupBox("Recent transcription tasks")
                    jobs_layout = QVBoxLayout(jobs_box)
                    recent_jobs_list = QListWidget(jobs_box)
                    recent_jobs_list.itemActivated.connect(self._open_selected_recent_job)
                    jobs_layout.addWidget(recent_jobs_list)
                    open_job_button = QPushButton("Open Selected Job Result", jobs_box)
                    open_job_button.clicked.connect(self._open_selected_recent_job)
                    jobs_layout.addWidget(open_job_button)

                    bindings_box = QGroupBox("Recent transcript-media bindings")
                    bindings_layout = QVBoxLayout(bindings_box)
                    recent_media_bindings_list = QListWidget(bindings_box)
                    recent_media_bindings_list.itemActivated.connect(self._rebind_selected_recent_media)
                    bindings_layout.addWidget(recent_media_bindings_list)
                    rebind_button = QPushButton("Rebind Selected Media", bindings_box)
                    rebind_button.clicked.connect(self._rebind_selected_recent_media)
                    bindings_layout.addWidget(rebind_button)

                    layout.addWidget(transcripts_box)
                    layout.addWidget(outputs_box)
                    layout.addWidget(jobs_box)
                    layout.addWidget(bindings_box)

                    close_button = QPushButton("Close", dialog)
                    close_button.clicked.connect(dialog.accept)
                    button_row = QHBoxLayout()
                    button_row.addStretch(1)
                    button_row.addWidget(close_button)
                    layout.addLayout(button_row)

                    self._recent_work_dialog = dialog
                    self._recent_transcripts_list = recent_transcripts_list
                    self._recent_output_dirs_list = recent_output_dirs_list
                    self._recent_jobs_list = recent_jobs_list
                    self._recent_media_bindings_list = recent_media_bindings_list

                self._refresh_recent_work_lists()
                self._recent_work_dialog.show()
                self._recent_work_dialog.raise_()
                self._recent_work_dialog.activateWindow()

            def _show_state_preview(self) -> None:
                selection_error = self._local_selection_error()
                if selection_error:
                    self.status_label.setText(selection_error)
                    self.preview_output.clear()
                    return
                if self._capture_controller.is_recording():
                    self.status_label.setText("Stop system capture before collecting or starting transcription.")
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
                if self._capture_controller.is_recording():
                    self.status_label.setText("Stop system capture before starting transcription.")
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
                self._cancel_requested = False
                self._remember_recent_output_dir(job.output_dir)
                self.start_button.setEnabled(False)
                self.collect_button.setEnabled(False)
                self.cancel_button.setEnabled(True)
                self.open_output_button.setEnabled(False)

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

            def _cancel_transcription(self) -> None:
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
                self.preview_output.append("\nCancellation requested...")

            def _open_output_dir(self) -> None:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                target = self._last_output_dir or Path(self.output_dir_input.text().strip() or "outputs")
                try:
                    resolved = target.resolve()
                except OSError:
                    self.status_label.setText("Output directory is not available.")
                    return

                if not resolved.exists():
                    self.status_label.setText(f"Output directory does not exist yet: {resolved}")
                    return

                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved))):
                    self.status_label.setText(f"Could not open output directory: {resolved}")
                    return
                self.status_label.setText(f"Opened output directory: {resolved}")

            def _append_progress(self, message: str) -> None:
                self.preview_output.append(message)

            def _finish_transcription(self, result) -> None:
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0 if result.canceled else 1)
                self.start_button.setEnabled(True)
                self.collect_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                self.open_output_button.setEnabled(bool(result.outputs))
                if result.outputs:
                    self._last_output_dir = result.job.output_dir
                    self._remember_recent_output_dir(result.job.output_dir)

                if result.canceled:
                    self._remember_recent_job(result, "canceled")
                    self.status_label.setText(
                        f"Canceled. Succeeded before cancel: {result.succeeded}. Failed: {result.failed}."
                    )
                    self._cleanup_temporary_capture_files()
                    if result.outputs:
                        self.preview_output.append("\nOutput files before cancellation:")
                        for artifacts in result.outputs:
                            for path in artifacts.paths:
                                self.preview_output.append(str(path))
                    return

                if result.errors:
                    self._remember_recent_job(result, "failed")
                    self.status_label.setText(
                        f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}."
                    )
                    self.preview_output.append("\nFailures:")
                    for error in result.errors:
                        self.preview_output.append(f"- {error.source}: {error.message}")
                    self._cleanup_temporary_capture_files()
                    return

                self._remember_recent_job(result, "completed")
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
                self._cleanup_temporary_capture_files()

            def _fail_transcription(self, message: str) -> None:
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0)
                self.start_button.setEnabled(True)
                self.collect_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                self.status_label.setText("Transcription failed.")
                self.preview_output.append(f"\nError: {message}")
                self._remember_recent_failed_run(message)
                self._cleanup_temporary_capture_files()

            def _clear_worker_refs(self) -> None:
                self._thread = None
                self._worker = None
                self._cancel_requested = False
                self._refresh_capture_support()

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
                self._remember_recent_transcript(path)
                self._search_hits = ()
                self.search_results.clear()
                self._clear_media_binding()
                self.open_media_button.setEnabled(True)
                self.transcript_summary.setPlainText(render_transcript_summary(view))
                self.transcript_segments.clear()
                for segment in view.segments:
                    self.transcript_segments.addItem(render_segment_line(segment))
                self._active_segment_row = -1
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

                self._select_transcript_segment(hit.segment_index, follow=True, focus=True)
                self._seek_media_seconds(transcript_search_hit_seek_seconds(hit), autoplay=True)

            def _activate_selected_segment(self, *_args) -> None:
                if self._transcript_view is None:
                    return
                row = self.transcript_segments.currentRow()
                if row < 0 or row >= len(self._transcript_view.segments):
                    return
                self._select_transcript_segment(row, follow=True, focus=True)
                segment = self._transcript_view.segments[row]
                self._seek_media_seconds(transcript_segment_seek_seconds(segment), autoplay=True)

            def _load_media_for_transcript(self, view: TranscriptView) -> None:
                media_path = resolve_transcript_media_path(view)
                if media_path is None:
                    self._media_binding_mode = "unbound"
                    self._update_media_binding_feedback()
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
                self._media_binding_mode = "auto-bound" if auto_bound else "manually bound"
                self._media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
                self.media_position_slider.setValue(0)
                self.play_media_button.setEnabled(True)
                self.media_position_slider.setEnabled(True)
                self._update_media_binding_feedback()
                self._remember_recent_media_binding(path)
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
                self._sync_transcript_to_media_position(position)

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
                self._media_binding_mode = "unbound"
                self._media_player.stop()
                self._media_player.setSource(QUrl())
                self.media_position_slider.setRange(0, 0)
                self.media_position_slider.setValue(0)
                self.media_position_slider.setEnabled(False)
                self.play_media_button.setEnabled(False)
                self._active_segment_row = -1
                self._update_media_binding_feedback()

            def closeEvent(self, event) -> None:
                if self._capture_controller.is_recording():
                    self._capture_controller.abort_capture()
                self._cleanup_temporary_capture_files()
                super().closeEvent(event)

            def _select_transcript_segment(self, row: int, *, follow: bool, focus: bool = False) -> None:
                if row < 0 or row >= self.transcript_segments.count():
                    return
                self._active_segment_row = row
                self.transcript_segments.setCurrentRow(row)
                item = self.transcript_segments.item(row)
                if item is not None and follow:
                    self.transcript_segments.scrollToItem(item)
                if focus:
                    self.transcript_segments.setFocus()

            def _sync_transcript_to_media_position(self, position_milliseconds: int) -> None:
                if self._transcript_view is None or self._media_path is None:
                    return
                row = transcript_segment_index_for_seconds(
                    self._transcript_view,
                    position_milliseconds / 1000.0,
                )
                if row is None or row == self._active_segment_row:
                    return
                self._select_transcript_segment(row, follow=True, focus=False)

            def _update_media_binding_feedback(self) -> None:
                if self._media_path is None or self._transcript_view is None:
                    self.media_binding_label.setText("Binding: Unbound")
                    return

                mode = self._media_binding_mode.title()
                warning = transcript_media_binding_warning(self._transcript_view, self._media_path)
                if warning:
                    self.media_binding_label.setText(
                        f"Binding: {mode} - {self._media_path.name}\nWarning: {warning}"
                    )
                    return
                self.media_binding_label.setText(f"Binding: {mode} - {self._media_path.name}")

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

            def _capture_output_dir(self) -> Path:
                return Path(self.output_dir_input.text().strip() or "outputs") / ".flowscribe-capture"

            def _start_system_capture(self) -> None:
                self._refresh_capture_support()
                if not self._capture_supported:
                    self.status_label.setText("System audio capture is not available on this machine.")
                    return
                if self._capture_controller.is_recording():
                    self.capture_status_label.setText("System audio capture is already running.")
                    return
                if self._thread is not None:
                    self.capture_status_label.setText("Wait for the current transcription job to finish first.")
                    return

                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                output_path = self._capture_output_dir() / f"capture-{timestamp}.wav"
                try:
                    started = self._capture_controller.start_capture(output_path)
                except MediaPreparationError as exc:
                    self.capture_status_label.setText(str(exc))
                    self.status_label.setText("Could not start system audio capture.")
                    return

                self._active_capture_path = started.output_path
                self.start_capture_button.setEnabled(False)
                self.stop_capture_button.setEnabled(True)
                device_name = started.device.name if started.device is not None else self._capture_default_device_name
                device_text = device_name or "default output device"
                self.capture_status_label.setText(
                    f"Capturing system audio from {device_text}..."
                )
                self.status_label.setText("System audio capture started.")

            def _stop_system_capture(self) -> None:
                if not self._capture_controller.is_recording():
                    self.capture_status_label.setText("System audio capture is not running.")
                    return

                try:
                    completed = self._capture_controller.stop_capture()
                except MediaPreparationError as exc:
                    self.start_capture_button.setEnabled(True)
                    self.stop_capture_button.setEnabled(False)
                    self._active_capture_path = None
                    self.capture_status_label.setText(str(exc))
                    self.status_label.setText("System audio capture failed.")
                    return

                output_path = completed.output_path
                self.start_capture_button.setEnabled(True)
                self.stop_capture_button.setEnabled(False)
                self._active_capture_path = None
                self._add_local_file(output_path)
                self._check_newly_added_sources([output_path])
                if not self.keep_capture_file_check.isChecked():
                    self._temporary_capture_paths.add(output_path)
                    self.capture_status_label.setText(
                        f"Captured audio ready for transcription. It will be deleted after the run: {output_path.name}"
                    )
                else:
                    self.capture_status_label.setText(
                        f"Captured audio saved as local source: {output_path.name}"
                    )
                self.status_label.setText(f"Captured system audio: {output_path.name}")
                self._persist_local_source_state()

            def _cleanup_temporary_capture_files(self) -> None:
                if not self._temporary_capture_paths:
                    return

                removed_paths: list[Path] = []
                for path in list(self._temporary_capture_paths):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        continue
                    removed_paths.append(path)
                    self._temporary_capture_paths.discard(path)

                if not removed_paths:
                    return

                removed_set = {path.resolve() if path.exists() else path for path in removed_paths}
                self._local_paths = [
                    path
                    for path in self._local_paths
                    if (path.resolve() if path.exists() else path) not in removed_set
                ]
                for index in range(self.file_list.count() - 1, -1, -1):
                    item = self.file_list.item(index)
                    if item is None:
                        continue
                    item_path = Path(item.text())
                    comparable = item_path.resolve() if item_path.exists() else item_path
                    if comparable in removed_set:
                        self.file_list.takeItem(index)
                self._persist_local_source_state()

            def _refresh_capture_support(self) -> None:
                try:
                    status = self._capture_controller.support_status()
                    supported = status.supported
                    self._capture_default_device_name = (
                        status.default_device.name if status.default_device is not None else None
                    )
                    if supported:
                        device_text = self._capture_default_device_name or "default output device"
                        message = f"Ready to capture system playback from {device_text}."
                    else:
                        message = status.reason or "System audio capture is not available on this machine."
                except MediaPreparationError as exc:
                    supported = False
                    self._capture_default_device_name = None
                    message = str(exc)

                self._capture_supported = supported
                if self._capture_controller.is_recording():
                    self.start_capture_button.setEnabled(False)
                    self.stop_capture_button.setEnabled(True)
                    return

                self.start_capture_button.setEnabled(supported and self._thread is None)
                self.stop_capture_button.setEnabled(False)
                if not supported:
                    self.capture_status_label.setText(message)
                elif self.capture_status_label.text().startswith("Could not start system audio capture"):
                    self.capture_status_label.setText(message)
                elif self.capture_status_label.text() == "System capture is idle.":
                    self.capture_status_label.setText(message)

            def _restore_gui_state(self) -> None:
                from PySide6.QtCore import QSignalBlocker

                local_paths, checked, preferences, recent_work = _load_gui_state()
                self._saved_checked_local_paths = checked
                self._saved_preferences = preferences
                self._recent_work = _recent_work_payload(recent_work)
                blocker = QSignalBlocker(self.file_list)
                try:
                    self._apply_gui_preferences(preferences)
                    for path in local_paths:
                        self._add_local_file(path)
                    for index in range(self.file_list.count()):
                        item = self.file_list.item(index)
                        if item is not None and item.text() in self._saved_checked_local_paths:
                            item.setCheckState(Qt.CheckState.Checked)
                finally:
                    del blocker
                self._persist_gui_state()

            def _persist_gui_state(self) -> None:
                _save_gui_state(
                    self._local_paths,
                    self._checked_local_paths(),
                    self._saved_preferences,
                    self._recent_work,
                )

            def _persist_local_source_state(self) -> None:
                self._persist_gui_state()

            def _remember_recent_transcript(self, path: Path) -> None:
                self._remember_recent_path("recent_transcripts", path)

            def _remember_recent_output_dir(self, path: Path) -> None:
                self._remember_recent_path("recent_output_dirs", path, expect_directory=True)

            def _remember_recent_path(
                self,
                key: str,
                path: Path,
                *,
                expect_directory: bool = False,
            ) -> None:
                try:
                    normalized = str(path.resolve())
                except OSError:
                    normalized = str(path)
                entries = [item for item in self._recent_work.get(key, []) if isinstance(item, str)]
                entries = [item for item in entries if item != normalized]
                entries.insert(0, normalized)
                limit = MAX_RECENT_OUTPUT_DIRS if expect_directory else MAX_RECENT_TRANSCRIPTS
                self._recent_work[key] = entries[:limit]
                self._persist_gui_state()
                self._refresh_recent_work_lists()

            def _remember_recent_job(self, result, status: str) -> None:
                source_count = len(result.job.sources)
                label = f"{source_count} source(s) -> {result.job.output_dir.name}"
                transcript_path = ""
                for artifacts in result.outputs:
                    for path in artifacts.paths:
                        if path.suffix.lower() == ".json":
                            transcript_path = str(path)
                            break
                    if transcript_path:
                        break

                entry = {
                    "label": label,
                    "status": status,
                    "output_dir": str(result.job.output_dir),
                    "transcript_path": transcript_path,
                    "media_path": str(self._media_path) if self._media_path is not None else "",
                }
                self._prepend_recent_job_entry(entry)

            def _remember_recent_failed_run(self, message: str) -> None:
                entry = {
                    "label": message.strip() or "Transcription failed",
                    "status": "failed",
                    "output_dir": self.output_dir_input.text().strip() or "outputs",
                    "transcript_path": "",
                    "media_path": "",
                }
                self._prepend_recent_job_entry(entry)

            def _prepend_recent_job_entry(self, entry: dict[str, str]) -> None:
                entries = [
                    item
                    for item in self._recent_work.get("recent_jobs", [])
                    if isinstance(item, dict)
                ]
                entries = [
                    item
                    for item in entries
                    if not (
                        item.get("label") == entry["label"]
                        and item.get("status") == entry["status"]
                        and item.get("output_dir") == entry["output_dir"]
                        and item.get("transcript_path") == entry["transcript_path"]
                        and item.get("media_path") == entry["media_path"]
                    )
                ]
                entries.insert(0, entry)
                self._recent_work["recent_jobs"] = entries[:MAX_RECENT_JOBS]
                self._persist_gui_state()
                self._refresh_recent_work_lists()

            def _remember_recent_media_binding(self, media_path: Path) -> None:
                if self._transcript_path is None:
                    return
                entry = {
                    "transcript_path": str(self._transcript_path),
                    "media_path": str(media_path),
                }
                entries = [
                    item
                    for item in self._recent_work.get("recent_media_bindings", [])
                    if isinstance(item, dict)
                ]
                entries = [
                    item
                    for item in entries
                    if not (
                        item.get("transcript_path") == entry["transcript_path"]
                        and item.get("media_path") == entry["media_path"]
                    )
                ]
                entries.insert(0, entry)
                self._recent_work["recent_media_bindings"] = entries[:MAX_RECENT_MEDIA_BINDINGS]
                self._persist_gui_state()
                self._refresh_recent_work_lists()

            def _refresh_recent_work_lists(self) -> None:
                if self._recent_transcripts_list is not None:
                    self._recent_transcripts_list.clear()
                    for path_text in self._recent_work.get("recent_transcripts", []):
                        self._recent_transcripts_list.addItem(str(path_text))
                if self._recent_output_dirs_list is not None:
                    self._recent_output_dirs_list.clear()
                    for path_text in self._recent_work.get("recent_output_dirs", []):
                        self._recent_output_dirs_list.addItem(str(path_text))
                if self._recent_jobs_list is not None:
                    self._recent_jobs_list.clear()
                    for item in self._recent_work.get("recent_jobs", []):
                        if not isinstance(item, dict):
                            continue
                        label = (
                            f"[{item.get('status', 'unknown')}] "
                            f"{item.get('label', '')} | {item.get('output_dir', '')}"
                        )
                        self._recent_jobs_list.addItem(label)
                if self._recent_media_bindings_list is not None:
                    self._recent_media_bindings_list.clear()
                    for item in self._recent_work.get("recent_media_bindings", []):
                        if not isinstance(item, dict):
                            continue
                        transcript_path = str(item.get("transcript_path", ""))
                        media_path = str(item.get("media_path", ""))
                        self._recent_media_bindings_list.addItem(
                            f"{Path(transcript_path).name} -> {Path(media_path).name}"
                        )

            def _selected_recent_path(self, list_widget) -> str | None:
                if list_widget is None:
                    return None
                item = list_widget.currentItem()
                if item is None:
                    return None
                text = item.text().strip()
                return text or None

            def _drop_missing_recent_path(self, key: str, target: Path) -> None:
                target_text = str(target)
                entries = [item for item in self._recent_work.get(key, []) if isinstance(item, str)]
                self._recent_work[key] = [item for item in entries if item != target_text]
                self._persist_gui_state()
                self._refresh_recent_work_lists()

            def _drop_recent_media_binding(self, transcript_path: Path, media_path: Path) -> None:
                entries = [
                    item
                    for item in self._recent_work.get("recent_media_bindings", [])
                    if isinstance(item, dict)
                ]
                self._recent_work["recent_media_bindings"] = [
                    item
                    for item in entries
                    if not (
                        item.get("transcript_path") == str(transcript_path)
                        and item.get("media_path") == str(media_path)
                    )
                ]
                self._persist_gui_state()
                self._refresh_recent_work_lists()

            def _open_selected_recent_transcript(self, *_args) -> None:
                selected = self._selected_recent_path(self._recent_transcripts_list)
                if not selected:
                    self.status_label.setText("Select a recent transcript JSON first.")
                    return
                path = Path(selected)
                if not path.is_file():
                    self._drop_missing_recent_path("recent_transcripts", path)
                    self.status_label.setText(f"Recent transcript is missing and was removed: {path}")
                    return
                self._load_transcript_json(path)

            def _open_selected_recent_output_dir(self, *_args) -> None:
                selected = self._selected_recent_path(self._recent_output_dirs_list)
                if not selected:
                    self.status_label.setText("Select a recent output directory first.")
                    return
                self._open_recent_output_dir(Path(selected))

            def _open_recent_output_dir(self, path: Path) -> None:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                if not path.is_dir():
                    self._drop_missing_recent_path("recent_output_dirs", path)
                    self.status_label.setText(f"Recent output directory is missing and was removed: {path}")
                    return
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                    self.status_label.setText(f"Could not open output directory: {path}")
                    return
                self.status_label.setText(f"Opened output directory: {path}")

            def _open_selected_recent_job(self, *_args) -> None:
                if self._recent_jobs_list is None:
                    return
                row = self._recent_jobs_list.currentRow()
                jobs = [
                    item
                    for item in self._recent_work.get("recent_jobs", [])
                    if isinstance(item, dict)
                ]
                if row < 0 or row >= len(jobs):
                    self.status_label.setText("Select a recent job first.")
                    return
                entry = jobs[row]
                transcript_path = Path(str(entry.get("transcript_path", ""))) if entry.get("transcript_path") else None
                if transcript_path and transcript_path.is_file():
                    self._load_transcript_json(transcript_path)
                    return
                output_dir = Path(str(entry.get("output_dir", "")))
                self._open_recent_output_dir(output_dir)

            def _rebind_selected_recent_media(self, *_args) -> None:
                if self._recent_media_bindings_list is None:
                    return
                row = self._recent_media_bindings_list.currentRow()
                bindings = [
                    item
                    for item in self._recent_work.get("recent_media_bindings", [])
                    if isinstance(item, dict)
                ]
                if row < 0 or row >= len(bindings):
                    self.status_label.setText("Select a recent transcript-media binding first.")
                    return
                entry = bindings[row]
                transcript_path = Path(str(entry.get("transcript_path", "")))
                media_path = Path(str(entry.get("media_path", "")))
                if not transcript_path.is_file():
                    self._drop_recent_media_binding(transcript_path, media_path)
                    self.status_label.setText(f"Recent transcript is missing: {transcript_path}")
                    return
                if not media_path.is_file():
                    self._drop_recent_media_binding(transcript_path, media_path)
                    self.status_label.setText(f"Recent media is missing: {media_path}")
                    return
                if not self._load_transcript_json(transcript_path):
                    return
                if self._bind_media_path(media_path):
                    self.status_label.setText(
                        f"Reopened transcript and rebound media: {transcript_path.name} -> {media_path.name}"
                    )

            def _check_newly_added_sources(self, paths) -> None:
                added = {str(Path(path)) for path in paths}
                for index in range(self.file_list.count()):
                    item = self.file_list.item(index)
                    if item is not None and item.text() in added:
                        item.setCheckState(Qt.CheckState.Checked)

        return _Window()
