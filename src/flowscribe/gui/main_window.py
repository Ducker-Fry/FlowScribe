"""PySide6 main window for the FlowScribe desktop GUI."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, QFileSystemWatcher
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QMainWindow, QListWidgetItem

from flowscribe.app.models import ProgressEvent
from flowscribe.cli.doctor import (
    check_command,
    check_faster_whisper_import,
    check_output_dir,
)
from flowscribe.core.errors import MediaPreparationError, OutputError, SearchError
from flowscribe.gui.export_profiles import (
    ExportProfile,
    apply_export_profile,
    create_export_profile,
    export_profiles_payload,
    profile_list_label,
    remove_export_profile,
    upsert_export_profile,
)
from flowscribe.gui.gui_logging import get_gui_logger
from flowscribe.input.file_filter import is_supported_media
from flowscribe.library import (
    TranscriptLibraryEntry,
    filter_transcript_library_entries,
    sort_transcript_library_entries,
)
from flowscribe.media.system_audio_capture_helper import CaptureController
from flowscribe.output.time_format import format_timestamp
from flowscribe.gui.state import (
    GuiTranscriptionForm,
    SUPPORTED_GUI_FORMATS,
    is_acceptable_local_source,
)
from flowscribe.transcript.editing import (
    EditableTranscriptDocument,
    load_editable_transcript,
    render_editable_segment_line,
    save_editable_transcript,
    suggested_corrected_transcript_path,
    update_editable_transcript_segment,
)
from flowscribe.transcript.reexport import reexport_transcript_json
from flowscribe.gui.transcript_viewer import (
    TranscriptSearchHitView,
    TranscriptView,
    load_transcript_view,
    render_transcript_summary,
    resolve_transcript_media_path,
    search_transcript_view,
    transcript_media_binding_warning,
    transcript_segment_index_for_seconds,
    transcript_search_hit_seek_seconds,
    transcript_segment_seek_seconds,
)
from flowscribe.gui.utils import (
    DEFAULT_GUI_PREFERENCES,
    DEFAULT_ONBOARDING_STATE,
    DEFAULT_VIEW_PREFERENCES,
    GUI_LANGUAGE_OPTIONS,
    GUI_MODEL_OPTIONS,
    GUI_NETWORK_OPTIONS,
    GUI_PRESET_OPTIONS,
    MAX_RECENT_JOBS,
    MAX_RECENT_MEDIA_BINDINGS,
    MAX_RECENT_OUTPUT_DIRS,
    MAX_RECENT_TRANSCRIPTS,
    _artifact_compare_group,
    _artifact_format_label,
    _artifact_selector_label,
    _artifact_summary,
    _build_library_entry,
    _default_recent_work,
    _discover_transcript_output_paths,
    _gui_preferences_payload,
    _infer_library_source_kind_from_result,
    _infer_library_source_media_path_from_result,
    _is_viewable_artifact_path,
    _library_entry_list_label,
    _library_results_summary,
    _model_access_guidance_text,
    _normalize_viewable_artifact_paths,
    _onboarding_state_payload,
    _onboarding_summary_text,
    _progress_event_status_line,
    _read_viewable_artifact_text,
    _recent_transcript_list_label,
    _recent_work_payload,
    _render_json_artifact_html,
    _render_progress_segment_line,
    _sort_workspace_artifact_paths,
    _url_media_status_suffix,
    _format_elapsed_time,
    _user_facing_doctor_message,
    _user_facing_folder_label,
    _user_facing_state_file_label,
    _view_preferences_payload,
    _view_tab_key_for_artifact,
    _view_tab_title_for_artifact,
)
from flowscribe.gui.state_manager import (
    batch_queue_store,
    transcript_library_store,
    load_gui_state,
    save_gui_state,
)
from flowscribe.gui.workers.transcription_worker import TranscriptionWorker
from flowscribe.gui.widgets.source_list_widget import (
    SourceListWidget,
    dropped_local_paths,
)
from flowscribe.gui.widgets.queue_tab_widget import QueueTabWidget
from flowscribe.gui.workers.queue_runner import QueueRunner
from flowscribe.gui.notifications import QueueNotificationPlayer
from flowscribe.queue.models import (
    BatchOutputStrategy,
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
)
from flowscribe.queue.importers import (
    deduplicate_sources,
    import_urls_from_file,
    parse_urls_from_text,
)
from flowscribe.gui.windows.transcription_controls import TranscriptionControlsMixin
from flowscribe.gui.windows.transcript_viewer_controls import TranscriptViewerControlsMixin
from flowscribe.gui.windows.library_controls import LibraryControlsMixin
from flowscribe.gui.windows.workspace_controls import WorkspaceControlsMixin
from flowscribe.gui.windows.capture_controls import CaptureControlsMixin
from flowscribe.gui.windows.settings_controls import SettingsControlsMixin
from flowscribe.gui.windows.queue_controls import QueueControlsMixin

LOGGER = get_gui_logger(__name__)


class MainWindow(
    TranscriptionControlsMixin,
    TranscriptViewerControlsMixin,
    LibraryControlsMixin,
    WorkspaceControlsMixin,
    CaptureControlsMixin,
    SettingsControlsMixin,
    QueueControlsMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self._local_paths: list[Path] = []
        self._saved_checked_local_paths: set[str] = set()
        self._saved_preferences = _gui_preferences_payload(DEFAULT_GUI_PREFERENCES)
        self._thread: QThread | None = None
        self._worker: TranscriptionWorker | None = None
        self._cancel_requested = False
        self._last_output_dir: Path | None = None
        self._transcript_path: Path | None = None
        self._transcript_view: TranscriptView | None = None
        self._editable_transcript: EditableTranscriptDocument | None = None
        self._transcript_edit_dirty = False
        self._updating_segment_editor = False
        self._search_hits: tuple[TranscriptSearchHitView, ...] = ()
        self._media_path: Path | None = None
        self._media_binding_mode = "unbound"
        self._active_segment_row = -1
        self._settings_dialog: object | None = None
        self._settings_viewer: object | None = None
        self._views_dialog: object | None = None
        self._views_tab_widget: object | None = None
        self._view_menu_button: object | None = None
        self._view_menu: object | None = None
        self._view_tab_pages: dict[str, object] = {}
        self._view_tab_titles: dict[str, str] = {}
        self._view_tab_visibility: dict[str, bool] = {}
        self._view_preferences = _view_preferences_payload(DEFAULT_VIEW_PREFERENCES)
        self._onboarding_state = _onboarding_state_payload(DEFAULT_ONBOARDING_STATE)
        self._state_load_warning: str | None = None
        self._artifact_viewers: dict[Path, object] = {}
        self._workspace_artifact_paths: tuple[Path, ...] = ()
        self._last_chunk_index = 0
        self._workspace_artifact_selector: object | None = None
        self._workspace_artifact_viewer_stack: object | None = None
        self._workspace_artifact_viewer: object | None = None
        self._workspace_artifact_markdown_viewer: object | None = None
        self._workspace_artifact_status_label: object | None = None
        self._workspace_artifact_format_label: object | None = None
        self._workspace_artifact_quick_buttons: dict[str, object] = {}
        self._progressive_transcription_active = False
        self._library_source_filter_combo: object | None = None
        self._library_missing_filter_combo: object | None = None
        self._library_opened_filter_combo: object | None = None
        self._library_sort_combo: object | None = None
        self._library_sort_direction_combo: object | None = None
        self._library_summary_label: object | None = None
        self._recent_work = _default_recent_work()
        self._help_dialog: object | None = None
        self._queue_file_watcher: QFileSystemWatcher | None = None
        self._server_thread: QThread | None = None
        self._server_worker: object | None = None
        self._server_port: int | None = None
        self._help_viewer: object | None = None
        self._recent_work_dialog: object | None = None
        self._recent_transcripts_list: object | None = None
        self._recent_output_dirs_list: object | None = None
        self._recent_jobs_list: object | None = None
        self._recent_media_bindings_list: object | None = None
        self._export_profiles: tuple[ExportProfile, ...] = ()
        self._export_profiles_dialog: object | None = None
        self._export_profiles_list: object | None = None
        self._library_dialog: object | None = None
        self._library_entries_list: object | None = None
        self._library_entries_cache: tuple[TranscriptLibraryEntry, ...] = ()
        self._capture_controller = CaptureController()
        self._capture_default_device_name: str | None = None
        self._active_capture_path: Path | None = None
        self._temporary_capture_paths: set[Path] = set()
        self._capture_supported = False
        self._capture_activity_timer = QTimer(self)
        self._capture_activity_timer.setInterval(1500)
        self._capture_activity_timer.timeout.connect(self._refresh_capture_activity_feedback)
        self._library_store = transcript_library_store()
        self._queue_store = batch_queue_store()
        self._queue_thread: QThread | None = None
        self._queue_runner: QueueRunner | None = None
        self._queue_tab: QueueTabWidget | None = None
        self._notification_player = QueueNotificationPlayer()
        self._setup_window()
        self._library_store.refresh_missing_statuses()
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
            QToolButton,
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

        self.file_list = SourceListWidget()
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
        self.url_media_mode_combo = QComboBox()
        self.url_media_mode_combo.addItem("Do not save media", "none")
        self.url_media_mode_combo.addItem("Save audio copy", "audio")
        self.url_media_mode_combo.addItem("Save video copy", "video")
        self.url_media_mode_combo.currentIndexChanged.connect(self._sync_url_media_controls)
        self.url_media_dir_input = QLineEdit()
        self.url_media_dir_input.setPlaceholderText("Save URL media into a custom folder")
        choose_url_media_button = QPushButton("Browse")
        choose_url_media_button.clicked.connect(self._choose_url_media_dir)
        self.url_auto_bind_check = QCheckBox("Auto-bind saved URL media")
        self.url_auto_bind_check.setChecked(True)
        url_media_dir_row = QHBoxLayout()
        url_media_dir_row.addWidget(self.url_media_dir_input)
        url_media_dir_row.addWidget(choose_url_media_button)
        url_media_layout = QGridLayout()
        url_media_layout.setHorizontalSpacing(8)
        url_media_layout.setVerticalSpacing(6)
        url_media_layout.addWidget(QLabel("Save media"), 0, 0)
        url_media_layout.addWidget(self.url_media_mode_combo, 0, 1)
        url_media_layout.addWidget(QLabel("Save folder"), 1, 0)
        url_media_layout.addLayout(url_media_dir_row, 1, 1)
        url_media_layout.addWidget(self.url_auto_bind_check, 2, 1)

        left_layout.addWidget(QLabel("Local files"))
        left_layout.addWidget(self.file_list, 1)
        left_layout.addLayout(file_actions)
        left_layout.addSpacing(8)
        left_layout.addWidget(QLabel("URL"))
        left_layout.addWidget(self.url_input)
        left_layout.addLayout(url_media_layout)
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
        self.output_dir_input.textChanged.connect(self._sync_url_media_controls)
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

        action_layout = QGridLayout()
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(8)
        open_transcript_button = QPushButton("Open Transcript JSON")
        open_transcript_button.clicked.connect(self._open_transcript_json)
        self.open_transcript_button = open_transcript_button
        self.open_artifact_button = QPushButton("Open Artifact View")
        self.open_artifact_button.clicked.connect(self._open_view_artifact)
        self.open_views_button = QPushButton("Views")
        self.open_views_button.clicked.connect(self._show_views_window)
        self.view_menu_button = QToolButton()
        self.view_menu_button.setText("View Menu")
        self.view_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.view_settings_button = QPushButton("View Settings")
        self.view_settings_button.clicked.connect(self._show_saved_settings)
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self._show_help)
        self.export_profiles_button = QPushButton("Export Profiles")
        self.export_profiles_button.clicked.connect(self._show_export_profiles)
        self.view_library_button = QPushButton("Transcript Library")
        self.view_library_button.clicked.connect(self._show_transcript_library)
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
            self.open_artifact_button,
            self.open_views_button,
            self.view_menu_button,
            self.view_settings_button,
            self.help_button,
            self.export_profiles_button,
            self.view_library_button,
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
        self.diagnostics_label = QLabel("")
        self.diagnostics_label.setWordWrap(True)

        media_box = QGroupBox("Media Sync")
        media_layout = QVBoxLayout(media_box)
        media_layout.setSpacing(10)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(180)
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
        self.transcript_summary.setMaximumHeight(96)
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
        self.search_results.setMinimumHeight(72)
        self.search_results.setMaximumHeight(140)
        self.search_results.itemActivated.connect(self._jump_to_selected_hit)
        self.search_results.itemClicked.connect(self._jump_to_selected_hit)

        self.transcript_segments = QListWidget()
        self.transcript_segments.setMinimumHeight(140)
        self.transcript_segments.itemActivated.connect(self._activate_selected_segment)
        self.transcript_segments.itemClicked.connect(self._activate_selected_segment)

        transcript_edit_box = QGroupBox("Transcript editing")
        transcript_edit_layout = QVBoxLayout(transcript_edit_box)
        self.segment_editor = QTextEdit()
        self.segment_editor.setPlaceholderText(
            "Select a transcript segment to edit its text."
        )
        self.segment_editor.textChanged.connect(self._on_segment_editor_text_changed)
        self.segment_editor.setEnabled(False)
        self.segment_editor.setMinimumHeight(120)
        transcript_edit_layout.addWidget(self.segment_editor)

        transcript_edit_actions = QHBoxLayout()
        self.segment_revert_button = QPushButton("Revert Segment")
        self.segment_revert_button.clicked.connect(self._revert_selected_segment_edit)
        self.segment_revert_button.setEnabled(False)
        self.save_transcript_button = QPushButton("Save Transcript")
        self.save_transcript_button.clicked.connect(self._save_transcript_edits)
        self.save_transcript_button.setEnabled(False)
        self.save_transcript_copy_button = QPushButton("Save As Copy")
        self.save_transcript_copy_button.clicked.connect(
            lambda: self._save_transcript_edits(force_save_as=True)
        )
        self.save_transcript_copy_button.setEnabled(False)
        self.reexport_transcript_button = QPushButton("Re-Export Transcript")
        self.reexport_transcript_button.clicked.connect(self._reexport_current_transcript)
        self.reexport_transcript_button.setEnabled(False)
        transcript_edit_actions.addWidget(self.segment_revert_button)
        transcript_edit_actions.addWidget(self.save_transcript_button)
        transcript_edit_actions.addWidget(self.save_transcript_copy_button)
        transcript_edit_actions.addWidget(self.reexport_transcript_button)
        transcript_edit_layout.addLayout(transcript_edit_actions)

        self.transcript_edit_status_label = QLabel("No transcript loaded for editing.")
        self.transcript_edit_status_label.setWordWrap(True)
        transcript_edit_layout.addWidget(self.transcript_edit_status_label)

        self.views_hint_label = QLabel(
            "Use Views to switch between run details, transcript review, and generated artifacts."
        )
        self.views_hint_label.setWordWrap(True)

        self._create_views_window(media_box, search_row, transcript_edit_box)

        right_layout.addWidget(settings_box)
        right_layout.addLayout(action_layout)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.diagnostics_label)
        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(self.views_hint_label)

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
        if dropped_local_paths(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = dropped_local_paths(event)
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

    def _create_views_window(self, media_box, search_row, transcript_edit_box) -> None:
        from PySide6.QtWidgets import (
            QDialog,
            QComboBox,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QMenu,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QStackedWidget,
            QGroupBox,
            QTabWidget,
            QTextBrowser,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Views")
        dialog.resize(980, 760)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        dialog.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(dialog)
        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(QLabel("Open and switch between run details, transcript review, and artifacts."))
        toolbar_row.addStretch(1)

        menu_button = QToolButton(dialog)
        menu_button.setText("View Menu")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar_row.addWidget(menu_button)

        close_button = QPushButton("Close", dialog)
        close_button.clicked.connect(dialog.accept)
        toolbar_row.addWidget(close_button)
        layout.addLayout(toolbar_row)

        tabs = QTabWidget(dialog)
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(tabs)

        run_details_page = QWidget(dialog)
        run_details_layout = QVBoxLayout(run_details_page)
        run_details_layout.setContentsMargins(8, 8, 8, 8)
        run_details_layout.addWidget(self.preview_output)

        transcript_page = QWidget(dialog)
        transcript_page_layout = QVBoxLayout(transcript_page)
        transcript_page_layout.setContentsMargins(8, 8, 8, 8)
        transcript_page_layout.setSpacing(10)

        workspace_summary_label = QLabel(
            "Keep playback, segment review, editing, and transcript artifacts in one workspace."
        )
        workspace_summary_label.setWordWrap(True)
        transcript_page_layout.addWidget(workspace_summary_label)

        workspace_splitter = QSplitter(Qt.Orientation.Vertical, transcript_page)
        workspace_splitter.setChildrenCollapsible(False)
        transcript_page_layout.addWidget(workspace_splitter, 1)

        review_splitter = QSplitter(Qt.Orientation.Horizontal, workspace_splitter)
        review_splitter.setChildrenCollapsible(False)

        review_left = QWidget(review_splitter)
        review_left_layout = QVBoxLayout(review_left)
        review_left_layout.setContentsMargins(0, 0, 0, 0)
        review_left_layout.setSpacing(8)
        review_left_layout.addWidget(media_box, 3)
        review_left_layout.addWidget(self.transcript_summary, 1)

        review_right = QSplitter(Qt.Orientation.Vertical, review_splitter)
        review_right.setChildrenCollapsible(False)

        search_box = QGroupBox("Transcript search")
        search_layout = QVBoxLayout(search_box)
        search_layout.addLayout(search_row)
        search_layout.addWidget(self.search_results)

        segments_box = QGroupBox("Transcript segments")
        segments_layout = QVBoxLayout(segments_box)
        segments_layout.addWidget(self.transcript_segments)

        review_right.addWidget(search_box)
        review_right.addWidget(segments_box)
        review_right.addWidget(transcript_edit_box)

        review_splitter.addWidget(review_left)
        review_splitter.addWidget(review_right)

        artifact_box = QGroupBox("Transcript artifacts")
        artifact_layout = QVBoxLayout(artifact_box)
        artifact_toolbar = QHBoxLayout()
        artifact_toolbar.addWidget(QLabel("Current artifact"))
        artifact_selector = QComboBox(artifact_box)
        artifact_selector.currentIndexChanged.connect(self._show_selected_workspace_artifact)
        artifact_toolbar.addWidget(artifact_selector, 1)
        artifact_format_label = QLabel("No artifact selected")
        artifact_toolbar.addWidget(artifact_format_label)
        open_artifact_tab_button = QPushButton("Open Tab", artifact_box)
        open_artifact_tab_button.clicked.connect(self._open_selected_workspace_artifact_tab)
        artifact_toolbar.addWidget(open_artifact_tab_button)
        artifact_layout.addLayout(artifact_toolbar)

        artifact_compare_row = QHBoxLayout()
        artifact_compare_row.addWidget(QLabel("Quick switch"))
        quick_buttons: dict[str, object] = {}
        for group, label in (
            ("transcript_json", "Transcript JSON"),
            ("corrected_json", "Corrected JSON"),
            ("srt", "SRT"),
            ("vtt", "VTT"),
            ("md", "Markdown"),
            ("txt", "Text"),
        ):
            button = QPushButton(label, artifact_box)
            button.clicked.connect(
                lambda _checked=False, target_group=group: self._show_workspace_artifact_group(target_group)
            )
            artifact_compare_row.addWidget(button)
            quick_buttons[group] = button
        artifact_compare_row.addStretch(1)
        artifact_layout.addLayout(artifact_compare_row)

        artifact_status_label = QLabel("Open a transcript or artifact to inspect generated files here.")
        artifact_status_label.setWordWrap(True)
        artifact_layout.addWidget(artifact_status_label)

        artifact_viewer_stack = QStackedWidget(artifact_box)
        artifact_viewer = QPlainTextEdit(artifact_box)
        artifact_viewer.setReadOnly(True)
        artifact_markdown_viewer = QTextBrowser(artifact_box)
        artifact_markdown_viewer.setOpenExternalLinks(False)
        artifact_viewer_stack.addWidget(artifact_viewer)
        artifact_viewer_stack.addWidget(artifact_markdown_viewer)
        artifact_layout.addWidget(artifact_viewer_stack, 1)

        workspace_splitter.addWidget(review_splitter)
        workspace_splitter.addWidget(artifact_box)
        workspace_splitter.setStretchFactor(0, 4)
        workspace_splitter.setStretchFactor(1, 3)
        review_splitter.setStretchFactor(0, 3)
        review_splitter.setStretchFactor(1, 4)
        review_right.setStretchFactor(0, 1)
        review_right.setStretchFactor(1, 3)
        review_right.setStretchFactor(2, 3)
        workspace_splitter.setSizes([520, 320])
        review_splitter.setSizes([360, 640])
        review_right.setSizes([150, 240, 240])

        library_page = QWidget(dialog)
        library_layout = QVBoxLayout(library_page)
        library_layout.setContentsMargins(8, 8, 8, 8)
        library_summary_label = QLabel(
            "Use the library to reopen transcript JSON, repair media bindings, and clean missing entries without leaving Views."
        )
        library_summary_label.setWordWrap(True)
        library_layout.addWidget(library_summary_label)

        library_filters_row = QHBoxLayout()
        library_filters_row.addWidget(QLabel("Source"))
        library_source_filter_combo = QComboBox(library_page)
        library_source_filter_combo.addItem("All sources", "all")
        library_source_filter_combo.addItem("Local", "local")
        library_source_filter_combo.addItem("URL", "url")
        library_source_filter_combo.addItem("Capture", "capture")
        library_source_filter_combo.addItem("Unknown", "unknown")
        library_source_filter_combo.currentIndexChanged.connect(
            self._refresh_transcript_library_list
        )
        library_filters_row.addWidget(library_source_filter_combo)

        library_filters_row.addWidget(QLabel("Missing"))
        library_missing_filter_combo = QComboBox(library_page)
        library_missing_filter_combo.addItem("All", "all")
        library_missing_filter_combo.addItem("Missing only", "missing_only")
        library_missing_filter_combo.addItem("Available only", "available_only")
        library_missing_filter_combo.currentIndexChanged.connect(
            self._refresh_transcript_library_list
        )
        library_filters_row.addWidget(library_missing_filter_combo)

        library_filters_row.addWidget(QLabel("Opened"))
        library_opened_filter_combo = QComboBox(library_page)
        library_opened_filter_combo.addItem("All", "all")
        library_opened_filter_combo.addItem("Opened before", "opened")
        library_opened_filter_combo.addItem("Never opened", "never_opened")
        library_opened_filter_combo.currentIndexChanged.connect(
            self._refresh_transcript_library_list
        )
        library_filters_row.addWidget(library_opened_filter_combo)

        library_filters_row.addWidget(QLabel("Sort"))
        library_sort_combo = QComboBox(library_page)
        library_sort_combo.addItem("Last opened", "last_opened")
        library_sort_combo.addItem("Updated", "updated")
        library_sort_combo.addItem("Created", "created")
        library_sort_combo.addItem("Label", "label")
        library_sort_combo.currentIndexChanged.connect(self._refresh_transcript_library_list)
        library_filters_row.addWidget(library_sort_combo)

        library_sort_direction_combo = QComboBox(library_page)
        library_sort_direction_combo.addItem("Newest first", "desc")
        library_sort_direction_combo.addItem("Oldest first", "asc")
        library_sort_direction_combo.currentIndexChanged.connect(
            self._refresh_transcript_library_list
        )
        library_filters_row.addWidget(library_sort_direction_combo)
        library_filters_row.addStretch(1)
        library_layout.addLayout(library_filters_row)

        library_results_label = QLabel("Library results will appear here.")
        library_results_label.setWordWrap(True)
        library_layout.addWidget(library_results_label)

        library_entries_list = QListWidget(library_page)
        library_entries_list.itemActivated.connect(self._open_selected_library_transcript)
        library_layout.addWidget(library_entries_list, 1)

        library_action_row = QHBoxLayout()
        open_transcript_button = QPushButton("Open Selected Transcript", library_page)
        open_transcript_button.clicked.connect(self._open_selected_library_transcript)
        open_output_button = QPushButton("Open Output Directory", library_page)
        open_output_button.clicked.connect(self._open_selected_library_output_dir)
        bind_media_button = QPushButton("Bind Or Rebind Media", library_page)
        bind_media_button.clicked.connect(self._rebind_selected_library_media)
        remove_button = QPushButton("Remove From Library", library_page)
        remove_button.clicked.connect(self._remove_selected_library_entry)
        cleanup_button = QPushButton("Clean Missing Entries", library_page)
        cleanup_button.clicked.connect(self._clean_missing_library_entries)
        library_action_row.addWidget(open_transcript_button)
        library_action_row.addWidget(open_output_button)
        library_action_row.addWidget(bind_media_button)
        library_action_row.addWidget(remove_button)
        library_action_row.addWidget(cleanup_button)
        library_layout.addLayout(library_action_row)

        self._views_dialog = dialog
        self._views_tab_widget = tabs
        self._view_menu_button = menu_button

        queue_page = QueueTabWidget(dialog)
        queue_page.enqueue_urls_requested.connect(self._enqueue_urls_from_text)
        queue_page.import_file_requested.connect(self._enqueue_from_file)
        queue_page.start_queue_requested.connect(self._start_queue_processing)
        queue_page.cancel_queue_requested.connect(self._stop_queue_processing)
        queue_page.skip_current_requested.connect(self._skip_current_queue_item)
        queue_page.retry_item_requested.connect(self._retry_queue_item)
        queue_page.remove_item_requested.connect(self._remove_queue_item)
        queue_page.clear_completed_requested.connect(self._clear_completed_queue_items)
        queue_page.reorder_requested.connect(self._reorder_queue_items)
        queue_page.server_start_requested.connect(self._start_bookmarklet_server)
        queue_page.server_stop_requested.connect(self._stop_bookmarklet_server)
        self._queue_tab = queue_page

        # Setup file watcher for queue file
        self._setup_queue_file_watcher()

        self._view_tab_pages = {
            "run_details": run_details_page,
            "transcript": transcript_page,
            "library": library_page,
            "queue": queue_page,
        }
        self._view_tab_titles = {
            "run_details": "Run Details",
            "transcript": "Workspace",
            "library": "Library",
            "queue": "Queue",
        }
        self._view_tab_visibility = dict(self._view_preferences["visible_tabs"])
        self._artifact_viewers = {}
        self._workspace_artifact_selector = artifact_selector
        self._workspace_artifact_viewer_stack = artifact_viewer_stack
        self._workspace_artifact_viewer = artifact_viewer
        self._workspace_artifact_markdown_viewer = artifact_markdown_viewer
        self._workspace_artifact_status_label = artifact_status_label
        self._workspace_artifact_format_label = artifact_format_label
        self._workspace_artifact_quick_buttons = quick_buttons
        self._library_source_filter_combo = library_source_filter_combo
        self._library_missing_filter_combo = library_missing_filter_combo
        self._library_opened_filter_combo = library_opened_filter_combo
        self._library_sort_combo = library_sort_combo
        self._library_sort_direction_combo = library_sort_direction_combo
        self._library_summary_label = library_results_label
        self._library_entries_list = library_entries_list

        for key in ("run_details", "transcript", "library", "queue"):
            if self._view_tab_visibility.get(key, False):
                tabs.addTab(self._view_tab_pages[key], self._view_tab_titles[key])
        if tabs.count() == 0:
            tabs.addTab(transcript_page, self._view_tab_titles["transcript"])
            self._view_tab_visibility["transcript"] = True

        menu = QMenu(menu_button)
        menu_button.setMenu(menu)
        self._view_menu = menu
        self.view_menu_button.setMenu(menu)
        self.view_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tabs.currentChanged.connect(self._on_views_tab_changed)
        self._refresh_view_menu()

    def _refresh_view_menu(self) -> None:
        from PySide6.QtGui import QAction

        if self._view_menu is None:
            return
        self._view_menu.clear()
        for key, title in self._view_tab_titles.items():
            action = QAction(title, self)
            action.setCheckable(True)
            action.setChecked(self._view_tab_visibility.get(key, False))
            action.toggled.connect(lambda checked, tab_key=key: self._set_view_tab_visible(tab_key, checked))
            self._view_menu.addAction(action)

    def _capture_view_preferences(self) -> dict[str, object]:
        current_tab = self._view_preferences.get("current_tab", "transcript")
        if self._views_tab_widget is not None:
            index = self._views_tab_widget.currentIndex()
            if index >= 0:
                current_page = self._views_tab_widget.widget(index)
                for key, page in self._view_tab_pages.items():
                    if page == current_page:
                        current_tab = key
                        break
        return _view_preferences_payload(
            {
                "visible_tabs": self._view_tab_visibility,
                "current_tab": current_tab,
            }
        )

    def _on_views_tab_changed(self, index: int) -> None:
        if index < 0 or self._views_tab_widget is None:
            return
        current_page = self._views_tab_widget.widget(index)
        for key, page in self._view_tab_pages.items():
            if page == current_page:
                self._view_preferences["current_tab"] = key
                self._persist_gui_state()
                break

    def _find_view_tab_index(self, key: str) -> int:
        if self._views_tab_widget is None:
            return -1
        page = self._view_tab_pages.get(key)
        if page is None:
            return -1
        return self._views_tab_widget.indexOf(page)

    def _set_view_tab_visible(self, key: str, visible: bool) -> None:
        if self._views_tab_widget is None:
            return
        page = self._view_tab_pages.get(key)
        title = self._view_tab_titles.get(key, key)
        if page is None:
            return
        index = self._views_tab_widget.indexOf(page)
        if visible:
            if index < 0:
                self._views_tab_widget.addTab(page, title)
            self._view_tab_visibility[key] = True
            self._view_preferences = self._capture_view_preferences()
            self._persist_gui_state()
            self._refresh_view_menu()
            return
        if index >= 0 and self._views_tab_widget.count() > 1:
            self._views_tab_widget.removeTab(index)
        self._view_tab_visibility[key] = self._views_tab_widget.indexOf(page) >= 0
        self._view_preferences = self._capture_view_preferences()
        self._persist_gui_state()
        self._refresh_view_menu()

    def _show_views_window(self) -> None:
        if self._views_dialog is None:
            return
        self._views_dialog.show()
        self._views_dialog.raise_()
        self._views_dialog.activateWindow()

    def _set_current_view_tab(self, key: str) -> None:
        if self._views_tab_widget is None:
            return
        self._set_view_tab_visible(key, True)
        index = self._find_view_tab_index(key)
        if index >= 0:
            self._views_tab_widget.setCurrentIndex(index)
            self._view_preferences["current_tab"] = key

    def _select_view_tab(self, key: str) -> None:
        self._set_current_view_tab(key)
        self._show_views_window()

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

    def _choose_url_media_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        start_dir = self.url_media_dir_input.text().strip() or str(self._default_url_media_dir())
        path = QFileDialog.getExistingDirectory(self, "Choose URL media save folder", start_dir)
        if path:
            self.url_media_dir_input.setText(path)

    def _current_url_media_kind(self) -> str:
        value = self.url_media_mode_combo.currentData()
        if value in {"audio", "video", "none"}:
            return str(value)
        return "none"

    def _default_url_media_dir(self) -> Path:
        return Path(self.output_dir_input.text().strip() or "outputs") / "url-media"

    def _sync_url_media_controls(self) -> None:
        save_enabled = self._current_url_media_kind() != "none"
        self.url_media_dir_input.setEnabled(save_enabled)
        self.url_auto_bind_check.setEnabled(save_enabled)
        if save_enabled and not self.url_media_dir_input.text().strip():
            self.url_media_dir_input.setPlaceholderText(str(self._default_url_media_dir()))
        elif not save_enabled:
            self.url_media_dir_input.setPlaceholderText("Save URL media into a custom folder")

    def _help_html(self) -> str:
        output_dir = Path(self.output_dir_input.text().strip() or "outputs")
        output_check = check_output_dir(output_dir)
        whisper_check = check_faster_whisper_import()
        ffmpeg_check = check_command("ffmpeg")
        capture_text = self.capture_status_label.text().strip()
        state_note = (
            f"<p><strong>State file:</strong> FlowScribe can read {_user_facing_state_file_label()}.</p>"
            if self._state_load_warning is None
            else (
                f"<p><strong>State file warning:</strong> {escape(self._state_load_warning)}</p>"
            )
        )
        return (
            "<html><body>"
            "<h2>FlowScribe Help And Diagnostics</h2>"
            "<p>FlowScribe turns local media, captured system playback, or public URL audio into transcript files that you can review, search, edit, and export.</p>"
            "<h3>First Run</h3>"
            "<ul>"
            "<li>Choose one or more local audio/video files, or paste a public URL.</li>"
            f"<li>Pick an output folder. Current folder: {_user_facing_folder_label(output_dir)}</li>"
            f"<li>{escape(_model_access_guidance_text(self.model_combo.currentText()))}</li>"
            "<li>Default outputs are TXT, Markdown, and JSON. Use <strong>Open Output Folder</strong> after a run to inspect them.</li>"
            "<li>System audio capture needs the bundled WASAPI helper and a Windows playback device that the helper can record.</li>"
            "</ul>"
            "<h3>Current Diagnostics</h3>"
            "<ul>"
            f"<li><strong>Output folder:</strong> {escape(_user_facing_doctor_message(output_check.name, output_check.ok, output_check.message))}</li>"
            f"<li><strong>faster-whisper:</strong> {escape(_user_facing_doctor_message(whisper_check.name, whisper_check.ok, whisper_check.message))}</li>"
            f"<li><strong>ffmpeg:</strong> {escape(_user_facing_doctor_message(ffmpeg_check.name, ffmpeg_check.ok, ffmpeg_check.message))}</li>"
            f"<li><strong>Capture:</strong> {escape(capture_text)}</li>"
            "</ul>"
            f"{state_note}"
            "<h3>Common Problems And Next Steps</h3>"
            "<ul>"
            "<li><strong>Model download feels stuck:</strong> try the `small` model first, check internet access, and keep the first run open long enough to download model files.</li>"
            "<li><strong>Capture helper missing:</strong> use a release bundle that includes <code>WasapiCaptureHelper.exe</code> or rebuild the GUI package.</li>"
            "<li><strong>System capture unsupported:</strong> use local files or URL transcription first, or switch to a machine/device path that supports Windows playback capture.</li>"
            "<li><strong>Transcript JSON opens but media is missing:</strong> bind a local media file again from the transcript workspace or rebind it from Library / Recent Work.</li>"
            "<li><strong>Library entry is stale:</strong> clean missing entries from Library or Recent Work so broken transcript records stop getting in the way.</li>"
            "<li><strong>Output folder problems:</strong> pick a writable folder, save settings, then retry the run.</li>"
            "</ul>"
            "<h3>Where To Look Next</h3>"
            "<ul>"
            "<li><strong>Workspace:</strong> review transcript text, playback, and artifacts together.</li>"
            "<li><strong>Library:</strong> reopen old transcripts, clean missing entries, and repair bindings.</li>"
            "<li><strong>Recent Work:</strong> jump back to the last transcript JSON or output folder quickly.</li>"
            "</ul>"
            "</body></html>"
        )

    def _refresh_diagnostics_summary(self) -> None:
        output_dir = Path(self.output_dir_input.text().strip() or "outputs")
        summary = _onboarding_summary_text(
            output_dir=output_dir,
            model_name=self.model_combo.currentText(),
            capture_message=self.capture_status_label.text().strip() or "No capture status yet.",
        )
        if self._state_load_warning:
            summary += " | State: FlowScribe started with default settings because the saved GUI state could not be reused."
        self.diagnostics_label.setText(summary)

    def _show_help(self, *_args) -> None:
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout

        self.status_label.setText("Showing help and diagnostics.")
        if self._help_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Help And Diagnostics")
            dialog.resize(860, 700)
            layout = QVBoxLayout(dialog)
            viewer = QTextBrowser(dialog)
            viewer.setOpenExternalLinks(False)
            layout.addWidget(viewer)
            close_button = QPushButton("Close", dialog)
            close_button.clicked.connect(dialog.accept)
            button_row = QHBoxLayout()
            button_row.addStretch(1)
            button_row.addWidget(close_button)
            layout.addLayout(button_row)
            self._help_dialog = dialog
            self._help_viewer = viewer

        if self._help_viewer is not None:
            self._help_viewer.setHtml(self._help_html())
        self._onboarding_state["help_seen"] = True
        self._persist_gui_state()
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _show_recent_work(self) -> None:
        """Show recent work by switching to the library view."""
        self._refresh_transcript_library_list()
        self._select_view_tab("library")
        self.status_label.setText("Showing recent work in Library.")

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
        self._select_view_tab("run_details")

    def closeEvent(self, event) -> None:
        if not self._confirm_unsaved_transcript_edits():
            event.ignore()
            return
        self._capture_activity_timer.stop()
        if self._capture_controller.is_recording():
            self._capture_controller.abort_capture()
        self._cleanup_temporary_capture_files()
        super().closeEvent(event)

    def _start_bookmarklet_server(self, port: int) -> None:
        """Start the Bookmarklet server in a background thread."""
        if self._server_thread is not None:
            self.status_label.setText("Server is already running.")
            return

        from flowscribe.gui.workers.server_worker import ServerWorker

        # Get current settings
        output_dir = Path(self.output_dir_input.text().strip() or "outputs")
        settings = self._current_queue_item_settings()

        self._server_worker = ServerWorker(
            queue_store_path=self._queue_store._path,
            port=port,
            output_dir=output_dir,
            output_formats=settings.output_formats,
            model_name=settings.model_name,
            language=settings.language,
        )

        self._server_thread = QThread()
        self._server_worker.moveToThread(self._server_thread)

        # Connect signals
        self._server_thread.started.connect(self._server_worker.run)
        self._server_worker.started.connect(self._on_server_started)
        self._server_worker.stopped.connect(self._on_server_stopped)
        self._server_worker.error.connect(self._on_server_error)

        self._server_thread.start()

    def _stop_bookmarklet_server(self) -> None:
        """Stop the Bookmarklet server."""
        if self._server_worker:
            self._server_worker.stop()

    def _on_server_started(self, port: int) -> None:
        """Handle server started event."""
        self._server_port = port
        if self._queue_tab:
            self._queue_tab.set_server_status(True, port)
        self.status_label.setText(f"Bookmarklet server started on port {port}")

    def _on_server_stopped(self) -> None:
        """Handle server stopped event."""
        if self._server_thread:
            self._server_thread.quit()
            self._server_thread.wait()
            self._server_thread = None

        self._server_worker = None
        self._server_port = None

        if self._queue_tab:
            self._queue_tab.set_server_status(False)
        self.status_label.setText("Bookmarklet server stopped")

    def _on_server_error(self, error_msg: str) -> None:
        """Handle server error."""
        if self._queue_tab:
            self._queue_tab.set_server_status(False)
        self.status_label.setText(f"Server error: {error_msg}")

