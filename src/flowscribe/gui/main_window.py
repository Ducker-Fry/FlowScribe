"""PySide6 main window for the FlowScribe desktop GUI."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl
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

LOGGER = get_gui_logger(__name__)


class MainWindow(QMainWindow):
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
        self._queue_tab = queue_page

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

    def _set_workspace_artifact_paths(
        self,
        paths: tuple[Path, ...],
        *,
        replace: bool,
        preferred_path: Path | None = None,
    ) -> None:
        normalized = _sort_workspace_artifact_paths(
            _normalize_viewable_artifact_paths(paths)
        )
        if replace:
            merged = normalized
        else:
            merged = _sort_workspace_artifact_paths(
                _normalize_viewable_artifact_paths(
                    self._workspace_artifact_paths + normalized
                )
            )
        self._workspace_artifact_paths = merged
        selector = self._workspace_artifact_selector
        if selector is None:
            return
        selector.blockSignals(True)
        try:
            selector.clear()
            for path in merged:
                selector.addItem(_artifact_selector_label(path), str(path))
        finally:
            selector.blockSignals(False)

        if not merged:
            if self._workspace_artifact_viewer is not None:
                self._workspace_artifact_viewer.clear()
            if self._workspace_artifact_markdown_viewer is not None:
                self._workspace_artifact_markdown_viewer.clear()
            if self._workspace_artifact_format_label is not None:
                self._workspace_artifact_format_label.setText("No artifact selected")
            if self._workspace_artifact_status_label is not None:
                self._workspace_artifact_status_label.setText(
                    "Open a transcript or artifact to inspect generated files here."
                )
            self._refresh_workspace_artifact_buttons()
            return

        selected_path = preferred_path if preferred_path in merged else merged[0]
        selector.setCurrentIndex(merged.index(selected_path))
        self._show_workspace_artifact(selected_path)

    def _show_selected_workspace_artifact(self, index: int) -> None:
        if index < 0 or index >= len(self._workspace_artifact_paths):
            return
        self._show_workspace_artifact(self._workspace_artifact_paths[index])

    def _refresh_workspace_artifact_buttons(self) -> None:
        for group, button in self._workspace_artifact_quick_buttons.items():
            if button is None:
                continue
            button.setEnabled(
                any(
                    _artifact_compare_group(path) == group
                    for path in self._workspace_artifact_paths
                )
            )

    def _show_workspace_artifact_group(self, group: str) -> None:
        for index, path in enumerate(self._workspace_artifact_paths):
            if _artifact_compare_group(path) != group:
                continue
            if self._workspace_artifact_selector is not None:
                self._workspace_artifact_selector.setCurrentIndex(index)
            self._show_workspace_artifact(path)
            return
        self.status_label.setText(f"No {group.replace('_', ' ')} artifact is available yet.")

    def _show_workspace_artifact(self, path: Path) -> None:
        viewer = self._workspace_artifact_viewer
        markdown_viewer = self._workspace_artifact_markdown_viewer
        viewer_stack = self._workspace_artifact_viewer_stack
        status_label = self._workspace_artifact_status_label
        format_label = self._workspace_artifact_format_label
        if viewer is None or markdown_viewer is None or status_label is None:
            return
        if not path.is_file():
            viewer.clear()
            markdown_viewer.clear()
            if format_label is not None:
                format_label.setText("Missing artifact")
            status_label.setText(f"Artifact is missing: {path}")
            self._refresh_workspace_artifact_buttons()
            return
        rendered = _read_viewable_artifact_text(path)
        if path.suffix.lower() == ".json":
            markdown_viewer.setHtml(_render_json_artifact_html(path, rendered))
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(markdown_viewer)
        elif path.suffix.lower() == ".md":
            markdown_viewer.setMarkdown(rendered)
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(markdown_viewer)
        else:
            viewer.setPlainText(rendered)
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(viewer)
        if format_label is not None:
            format_label.setText(_artifact_format_label(path))
        status_label.setText(
            f"{_artifact_summary(path, rendered)} | Inspecting {path.name} in the current transcript workspace."
        )
        self._refresh_workspace_artifact_buttons()

    def _open_selected_workspace_artifact_tab(self) -> None:
        selector = self._workspace_artifact_selector
        if selector is None:
            return
        index = selector.currentIndex()
        if index < 0 or index >= len(self._workspace_artifact_paths):
            self.status_label.setText("Select an artifact first.")
            return
        path = self._workspace_artifact_paths[index]
        self._ensure_artifact_view_tab(path)
        self._select_view_tab(_view_tab_key_for_artifact(path))

    def _ensure_artifact_view_tab(self, path: Path) -> None:
        from PySide6.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout

        if not _is_viewable_artifact_path(path):
            return
        normalized = path.expanduser().resolve()
        key = _view_tab_key_for_artifact(normalized)
        title = _view_tab_title_for_artifact(normalized)
        viewer = self._artifact_viewers.get(normalized)
        page = self._view_tab_pages.get(key)
        if viewer is None or page is None:
            page = QWidget(self._views_dialog)
            page_layout = QVBoxLayout(page)
            viewer = QPlainTextEdit(page)
            viewer.setReadOnly(True)
            page_layout.addWidget(viewer)
            self._artifact_viewers[normalized] = viewer
            self._view_tab_pages[key] = page
        viewer.setPlainText(_read_viewable_artifact_text(normalized))
        self._view_tab_titles[key] = title
        self._view_tab_visibility[key] = True
        self._set_view_tab_visible(key, True)
        index = self._find_view_tab_index(key)
        if index >= 0:
            self._views_tab_widget.setTabText(index, title)
        self._refresh_view_menu()

    def _clear_artifact_view_tabs(self) -> None:
        artifact_keys = [key for key in self._view_tab_pages if key.startswith("artifact:")]
        for key in artifact_keys:
            page = self._view_tab_pages.get(key)
            if self._views_tab_widget is not None and page is not None:
                index = self._views_tab_widget.indexOf(page)
                if index >= 0:
                    self._views_tab_widget.removeTab(index)
            self._view_tab_pages.pop(key, None)
            self._view_tab_titles.pop(key, None)
            self._view_tab_visibility.pop(key, None)
        self._artifact_viewers = {}
        self._workspace_artifact_paths = ()
        self._set_workspace_artifact_paths((), replace=True)
        self._refresh_view_menu()

    def _load_artifact_views(self, paths: tuple[Path, ...], *, replace: bool = False) -> None:
        normalized_paths = _normalize_viewable_artifact_paths(paths)
        if replace:
            self._clear_artifact_view_tabs()
        for path in normalized_paths:
            if path.is_file():
                self._ensure_artifact_view_tab(path)
        preferred_path = normalized_paths[0] if normalized_paths else None
        self._set_workspace_artifact_paths(
            normalized_paths,
            replace=replace,
            preferred_path=preferred_path,
        )

    def _open_view_artifact(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open transcript artifact",
            self.output_dir_input.text().strip() or "outputs",
            "Viewable artifacts (*.json *.txt *.md *.srt *.vtt)",
        )
        if not path:
            return
        self._open_transcript_or_artifact(Path(path))

    def _open_transcript_or_artifact(self, path: Path) -> bool:
        normalized = path.expanduser().resolve()
        if normalized.suffix.lower() == ".json" and self._load_transcript_json(normalized):
            self._select_view_tab("transcript")
            return True
        if not normalized.is_file():
            self.status_label.setText(f"Artifact file is missing: {normalized}")
            return False
        if not _is_viewable_artifact_path(normalized):
            self.status_label.setText(
                f"Artifact format is not viewable yet: {normalized.suffix or normalized.name}"
            )
            return False
        self._load_artifact_views((normalized,), replace=True)
        self.status_label.setText(f"Opened artifact view: {normalized.name}")
        self._select_view_tab("transcript")
        return True

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
        self._open_transcript_or_artifact(Path(path))

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
        url_media_kind = self._current_url_media_kind()
        url_media_dir_text = self.url_media_dir_input.text().strip()
        keep_media = url_media_kind != "none"

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
            keep_media=keep_media,
            url_media_kind="audio" if url_media_kind == "none" else url_media_kind,
            url_media_output_dir=(
                Path(url_media_dir_text)
                if url_media_dir_text
                else self._default_url_media_dir()
            )
            if keep_media
            else None,
            auto_bind_media=self.url_auto_bind_check.isChecked(),
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
            "keep_media": self._current_url_media_kind() != "none",
            "url_media_kind": (
                "audio"
                if self._current_url_media_kind() == "none"
                else self._current_url_media_kind()
            ),
            "url_media_output_dir": self.url_media_dir_input.text().strip(),
            "url_auto_bind_media": self.url_auto_bind_check.isChecked(),
            "network_family": self.network_combo.currentText(),
            "proxy": self.proxy_input.text(),
        }

    def _current_export_preferences(self) -> dict[str, object]:
        preferences = self._current_gui_preferences()
        return {
            "output_formats": preferences["output_formats"],
            "timestamps": preferences["timestamps"],
            "word_timestamps": preferences["word_timestamps"],
        }

    def _apply_export_preferences(self, preferences: dict[str, object]) -> None:
        enabled_formats = {str(value) for value in preferences["output_formats"]}
        for output_format, checkbox in self.format_checks.items():
            checkbox.setChecked(output_format in enabled_formats)
        self.timestamps_check.setChecked(bool(preferences["timestamps"]))
        self.word_timestamps_check.setChecked(bool(preferences["word_timestamps"]))

    def _apply_gui_preferences(self, preferences: dict[str, object]) -> None:
        self.output_dir_input.setText(str(preferences["output_dir"]))
        self.output_name_input.setText(str(preferences["output_name_base"]))
        self.model_combo.setCurrentText(str(preferences["model_name"]))
        self.language_combo.setCurrentText(str(preferences["language"]))
        self.preset_combo.setCurrentText(str(preferences["preset"]))
        target_url_media_kind = (
            str(preferences["url_media_kind"])
            if preferences.get("keep_media", False)
            else "none"
        )
        index = self.url_media_mode_combo.findData(target_url_media_kind)
        if index >= 0:
            self.url_media_mode_combo.setCurrentIndex(index)
        self.url_media_dir_input.setText(str(preferences.get("url_media_output_dir", "")))
        self.url_auto_bind_check.setChecked(bool(preferences.get("url_auto_bind_media", True)))
        self.network_combo.setCurrentText(str(preferences["network_family"]))
        self.proxy_input.setText(str(preferences["proxy"]))
        self._apply_export_preferences(preferences)
        self.overwrite_check.setChecked(bool(preferences["overwrite"]))
        self._sync_url_media_controls()
        self._refresh_diagnostics_summary()

    def _save_settings(self) -> None:
        self._saved_preferences = _gui_preferences_payload(self._current_gui_preferences())
        self._persist_gui_state()
        self._refresh_diagnostics_summary()
        self.status_label.setText("GUI settings saved. Output, model, and export defaults are ready for the next run.")

    def _show_saved_settings(self) -> None:
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

        current_preferences = _gui_preferences_payload(self._current_gui_preferences())
        payload = {
            "saved_preferences": self._saved_preferences,
            "current_preferences": current_preferences,
            "export_profiles": export_profiles_payload(self._export_profiles),
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

    def _show_export_profiles(self) -> None:
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QPushButton, QVBoxLayout

        self.status_label.setText("Showing export profiles.")
        if self._export_profiles_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Export Profiles")
            dialog.resize(760, 560)

            layout = QVBoxLayout(dialog)
            export_profiles_list = QListWidget(dialog)
            layout.addWidget(export_profiles_list)

            action_row = QHBoxLayout()
            save_current_button = QPushButton("Save Current As New", dialog)
            save_current_button.clicked.connect(self._save_current_export_profile_as_new)
            update_selected_button = QPushButton("Update Selected", dialog)
            update_selected_button.clicked.connect(self._update_selected_export_profile)
            apply_selected_button = QPushButton("Apply Selected", dialog)
            apply_selected_button.clicked.connect(self._apply_selected_export_profile)
            delete_selected_button = QPushButton("Delete Selected", dialog)
            delete_selected_button.clicked.connect(self._delete_selected_export_profile)
            action_row.addWidget(save_current_button)
            action_row.addWidget(update_selected_button)
            action_row.addWidget(apply_selected_button)
            action_row.addWidget(delete_selected_button)
            layout.addLayout(action_row)

            close_button = QPushButton("Close", dialog)
            close_button.clicked.connect(dialog.accept)
            close_row = QHBoxLayout()
            close_row.addStretch(1)
            close_row.addWidget(close_button)
            layout.addLayout(close_row)

            self._export_profiles_dialog = dialog
            self._export_profiles_list = export_profiles_list

        self._refresh_export_profiles_list()
        self._export_profiles_dialog.show()
        self._export_profiles_dialog.raise_()
        self._export_profiles_dialog.activateWindow()

    def _show_transcript_library(self) -> None:
        self._refresh_transcript_library_list()
        self._select_view_tab("library")
        self.status_label.setText("Showing transcript library in Views.")

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

            clean_library_button = QPushButton("Clean Missing Library Entries", dialog)
            clean_library_button.clicked.connect(self._clean_missing_library_entries)
            open_library_button = QPushButton("Open Library In Views", dialog)
            open_library_button.clicked.connect(self._show_transcript_library)

            close_button = QPushButton("Close", dialog)
            close_button.clicked.connect(dialog.accept)
            button_row = QHBoxLayout()
            button_row.addWidget(clean_library_button)
            button_row.addWidget(open_library_button)
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
        self._select_view_tab("run_details")

    def _start_transcription(self) -> None:
        if self._thread is not None:
            self.status_label.setText("A transcription job is already running.")
            return
        if self._queue_thread is not None:
            self.status_label.setText("Wait for the queue to finish before starting a single job.")
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
        self._select_view_tab("run_details")
        self.status_label.setText("Running transcription in the background...")
        self.progress_bar.setRange(0, 0)
        self._cancel_requested = False
        self._progressive_transcription_active = True
        self._transcript_view = None
        self._editable_transcript = None
        self._transcript_edit_dirty = False
        self.transcript_segments.clear()
        self.search_results.clear()
        self.transcript_summary.setPlainText(
            "Progressive transcript output will appear here while the job is running."
        )
        self._clear_transcript_editor(
            message="Transcript editing becomes available after a transcript JSON is written."
        )
        self._remember_recent_output_dir(job.output_dir)
        self.start_button.setEnabled(False)
        self.collect_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_output_button.setEnabled(False)

        self._thread = QThread(self)
        self._worker = TranscriptionWorker(job)
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
            self.status_label.setText("Output directory is not available. Choose a writable folder in Settings or open Help for setup guidance.")
            return

        if not resolved.exists():
            self.status_label.setText(f"Output directory does not exist yet: {resolved}. Start a run first or choose another folder.")
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved))):
            self.status_label.setText(f"Could not open output directory: {resolved}. Check permissions or choose another output path.")
            return
        self.status_label.setText(f"Opened output directory: {resolved}")

    def _append_progress(self, event: ProgressEvent) -> None:
        if event.message:
            self.preview_output.append(event.message)
        if event.total_duration_seconds is not None:
            self.progress_bar.setRange(0, 1000)
        if (
            event.processed_duration_seconds is not None
            and event.total_duration_seconds is not None
            and event.total_duration_seconds > 0
        ):
            value = int(
                min(1.0, event.processed_duration_seconds / event.total_duration_seconds) * 1000
            )
            self.progress_bar.setValue(value)
        if event.segments:
            current_chunk = event.chunk_index or 0
            if current_chunk != self._last_chunk_index and self._last_chunk_index > 0:
                separator = QListWidgetItem("─" * 30)
                separator.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.transcript_segments.addItem(separator)
            if event.chunk_index is not None and event.chunk_count is not None:
                header = QListWidgetItem(
                    f"╾ Chunk {event.chunk_index}/{event.chunk_count} ╼"
                )
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)
                bold_font = header.font()
                bold_font.setBold(True)
                header.setFont(bold_font)
                self.transcript_segments.addItem(header)
            self._last_chunk_index = current_chunk
            for segment in event.segments:
                self.transcript_segments.addItem(_render_progress_segment_line(segment))
            self._select_view_tab("transcript")
        status_line = _progress_event_status_line(event)
        if status_line:
            self.transcript_summary.setPlainText(
                event.message + "\n\n" + status_line if event.message else status_line
            )
            self.transcript_edit_status_label.setText(status_line)
        if event.stage == "resume" and event.segments:
            self.status_label.setText("Resuming progressive transcription...")
        elif event.stage == "transcribe" and event.message:
            self.status_label.setText(event.message)

    def _finish_transcription(self, result) -> None:
        self._progressive_transcription_active = False
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0 if result.canceled else 1)
        self.start_button.setEnabled(True)
        self.collect_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.open_output_button.setEnabled(bool(result.outputs))
        if result.outputs:
            self._last_output_dir = result.job.output_dir
            self._remember_recent_output_dir(result.job.output_dir)
            self._index_result_in_library(result)

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
                self._load_artifact_views(
                    tuple(path for artifacts in result.outputs for path in artifacts.paths),
                    replace=True,
                )
                self._select_view_tab("run_details")
            return

        if result.errors:
            self._remember_recent_job(result, "failed")
            self.status_label.setText(
                f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}."
            )
            self.preview_output.append("\nFailures:")
            for error in result.errors:
                self.preview_output.append(f"- {error.source}: {error.message}")
            self._select_view_tab("run_details")
            self._cleanup_temporary_capture_files()
            return

        self._remember_recent_job(result, "completed")
        self.status_label.setText(f"Done. Succeeded: {result.succeeded}.")
        self.preview_output.append("\nOutput files:")
        transcript_loaded = False
        auto_bound_media = False
        url_media_notes: list[str] = []
        output_paths: list[Path] = []
        for artifacts in result.outputs:
            media_note = _url_media_status_suffix(artifacts)
            if media_note:
                url_media_notes.append(media_note)
            for path in artifacts.paths:
                output_paths.append(path)
                self.preview_output.append(str(path))
                if not transcript_loaded and path.suffix.lower() == ".json":
                    transcript_loaded = self._load_transcript_json(path)
                    if (
                        transcript_loaded
                        and artifacts.media_path is not None
                        and artifacts.auto_bind_media
                        and Path(artifacts.media_path).is_file()
                    ):
                        auto_bound_media = self._bind_media_path(
                            Path(artifacts.media_path),
                            auto_bound=True,
                        )
        self._load_artifact_views(tuple(output_paths), replace=True)
        if not transcript_loaded:
            self._transcript_view = None
            self._editable_transcript = None
            self._transcript_edit_dirty = False
            self.transcript_summary.setPlainText("No transcript JSON output was generated for this run.")
            self.transcript_segments.clear()
            self._clear_transcript_editor(message="No transcript loaded for editing.")
            self._select_view_tab("run_details")
        else:
            self._select_view_tab("transcript")
            if auto_bound_media and self._media_path is not None:
                status = (
                    f"Done. Succeeded: {result.succeeded}. "
                    f"Auto-bound saved media: {self._media_path.name}."
                )
                if url_media_notes:
                    status += " " + " ".join(url_media_notes)
                self.status_label.setText(status)
            elif url_media_notes:
                self.status_label.setText(
                    f"Done. Succeeded: {result.succeeded}. " + " ".join(url_media_notes)
                )
        self._cleanup_temporary_capture_files()

    def _fail_transcription(self, message: str) -> None:
        self._progressive_transcription_active = False
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)
        self.collect_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Transcription failed.")
        self.preview_output.append(f"\nError: {message}")
        self._select_view_tab("run_details")
        self._remember_recent_failed_run(message)
        self._cleanup_temporary_capture_files()

    def _clear_worker_refs(self) -> None:
        self._thread = None
        self._worker = None
        self._cancel_requested = False
        self._refresh_capture_support()

    def _load_transcript_json(
        self,
        path: Path,
        *,
        allow_unsaved_prompt: bool = True,
    ) -> bool:
        if (
            allow_unsaved_prompt
            and self._transcript_path is not None
            and self._transcript_path != path
            and not self._confirm_unsaved_transcript_edits()
        ):
            return False

        try:
            view = load_transcript_view(path)
            editable = load_editable_transcript(path)
        except ValueError as exc:
            self.status_label.setText(
                "Could not open transcript JSON. Make sure the file still exists and contains valid transcript JSON."
            )
            self.transcript_summary.setPlainText(str(exc))
            self.transcript_segments.clear()
            self.search_results.clear()
            self._search_hits = ()
            self._editable_transcript = None
            self._transcript_edit_dirty = False
            self._clear_transcript_editor(message="Transcript editing is unavailable.")
            return False

        self._transcript_path = path
        self._transcript_view = view
        self._editable_transcript = editable
        self._transcript_edit_dirty = editable.dirty
        self._index_transcript_in_library(
            path,
            opened_at=datetime.now(),
        )
        self._remember_recent_transcript(path)
        self._search_hits = ()
        self.search_results.clear()
        self._clear_media_binding()
        self.open_media_button.setEnabled(True)
        self._refresh_transcript_summary_panel()
        self._refresh_transcript_segments_list()
        self._active_segment_row = -1
        self._clear_transcript_editor(message="Select a transcript segment to edit its text.")
        self._refresh_transcript_edit_state()
        self._load_media_for_transcript(view)
        self._load_artifact_views(_discover_transcript_output_paths(path), replace=True)
        self._select_view_tab("transcript")
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
        self._select_view_tab("transcript")
        self._seek_media_seconds(transcript_search_hit_seek_seconds(hit), autoplay=True)

    def _activate_selected_segment(self, *_args) -> None:
        if self._transcript_view is None:
            return
        row = self.transcript_segments.currentRow()
        if row < 0 or row >= len(self._transcript_view.segments):
            return
        self._select_transcript_segment(row, follow=True, focus=True)
        self._select_view_tab("transcript")
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
            self.media_status_label.setText(
                f"Unsupported media file: {path}. Choose a local audio or video file that matches this transcript."
            )
            return False

        self._media_path = path
        self._media_binding_mode = "auto-bound" if auto_bound else "manually bound"
        self._media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.media_position_slider.setValue(0)
        self.play_media_button.setEnabled(True)
        self.media_position_slider.setEnabled(True)
        self._update_media_binding_feedback()
        self._remember_recent_media_binding(path)
        if self._transcript_path is not None:
            self._index_transcript_in_library(
                self._transcript_path,
                media_path=path,
                opened_at=datetime.now(),
            )
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
        if not self._confirm_unsaved_transcript_edits():
            event.ignore()
            return
        self._capture_activity_timer.stop()
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
        self._populate_segment_editor(row)

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

    def _capture_support_message(self, supported: bool, reason: str | None) -> str:
        if supported:
            device_text = self._capture_default_device_name or "the default output device"
            return (
                f"Ready to capture Windows system playback from {device_text}. "
                "Start playback before or during capture so the helper has audio to record."
            )

        detail = (reason or "").strip()
        if "wasapicapturehelper.exe was not found" in detail.lower():
            return (
                "System audio capture helper is missing. Rebuild the GUI package or "
                "use a release bundle that includes WasapiCaptureHelper.exe."
            )
        if detail:
            return f"System audio capture is unavailable: {detail}"
        return "System audio capture is unavailable on this machine."

    def _refresh_capture_activity_feedback(self) -> None:
        if not self._capture_controller.is_recording():
            self._capture_activity_timer.stop()
            return
        status = self._capture_controller.activity_status()
        device_text = self._capture_default_device_name or "default output device"
        if status.state == "active":
            self.capture_status_label.setText(
                f"Capturing system audio from {device_text}. {status.message}"
            )
            return
        if status.state == "stalled":
            self.capture_status_label.setText(
                f"Capturing system audio from {device_text}. {status.message}"
            )

    def _start_system_capture(self) -> None:
        self._refresh_capture_support()
        if not self._capture_supported:
            self.status_label.setText("System audio capture is not available. Open Help for capture requirements and fallback options.")
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
            self.status_label.setText("Could not start system audio capture. Open Help for helper and environment checks.")
            self._refresh_diagnostics_summary()
            return

        self._active_capture_path = started.output_path
        self.start_capture_button.setEnabled(False)
        self.stop_capture_button.setEnabled(True)
        device_name = started.device.name if started.device is not None else self._capture_default_device_name
        device_text = device_name or "default output device"
        self.capture_status_label.setText(
            f"Capturing system audio from {device_text}. Waiting for audio activity..."
        )
        self.status_label.setText("System audio capture started.")
        self._capture_activity_timer.start()
        self._refresh_diagnostics_summary()

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
            self._capture_activity_timer.stop()
            self.capture_status_label.setText(str(exc))
            self.status_label.setText("System audio capture failed. Open Help for next-step diagnostics.")
            self._refresh_diagnostics_summary()
            return

        output_path = completed.output_path
        self.start_capture_button.setEnabled(True)
        self.stop_capture_button.setEnabled(False)
        self._active_capture_path = None
        self._capture_activity_timer.stop()
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
        self._refresh_diagnostics_summary()

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
            message = self._capture_support_message(supported, status.reason)
        except MediaPreparationError as exc:
            supported = False
            self._capture_default_device_name = None
            message = self._capture_support_message(False, str(exc))

        self._capture_supported = supported
        if self._capture_controller.is_recording():
            self.start_capture_button.setEnabled(False)
            self.stop_capture_button.setEnabled(True)
            self._capture_activity_timer.start()
            return

        self.start_capture_button.setEnabled(supported and self._thread is None)
        self.stop_capture_button.setEnabled(False)
        self._capture_activity_timer.stop()
        if not supported:
            self.capture_status_label.setText(message)
        elif self.capture_status_label.text().startswith("Could not start system audio capture"):
            self.capture_status_label.setText(message)
        elif self.capture_status_label.text() == "System capture is idle.":
            self.capture_status_label.setText(message)
        self._refresh_diagnostics_summary()

    def _restore_gui_state(self) -> None:
        from PySide6.QtCore import QSignalBlocker

        (
            local_paths,
            checked,
            preferences,
            recent_work,
            export_profiles,
            view_preferences,
            onboarding_state,
            state_load_warning,
        ) = load_gui_state()
        self._saved_checked_local_paths = checked
        self._saved_preferences = preferences
        self._recent_work = _recent_work_payload(recent_work)
        self._export_profiles = export_profiles
        self._view_preferences = view_preferences
        self._onboarding_state = onboarding_state
        self._state_load_warning = state_load_warning
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
        self._view_tab_visibility.update(
            self._view_preferences.get("visible_tabs", {})
        )
        for key, visible in self._view_preferences.get("visible_tabs", {}).items():
            self._set_view_tab_visible(key, visible)
        self._set_current_view_tab(self._view_preferences.get("current_tab", "transcript"))
        self._refresh_diagnostics_summary()
        self._persist_gui_state()
        if not self._onboarding_state.get("help_seen", False):
            self._show_help()
        self._refresh_queue_tab()

    def _persist_gui_state(self) -> None:
        self._view_preferences = self._capture_view_preferences()
        save_gui_state(
            self._local_paths,
            self._checked_local_paths(),
            self._saved_preferences,
            self._recent_work,
            self._export_profiles,
            self._view_preferences,
            self._onboarding_state,
        )

    def _persist_local_source_state(self) -> None:
        self._persist_gui_state()

    def _index_transcript_in_library(
        self,
        transcript_path: Path,
        *,
        output_dir: Path | None = None,
        source_kind: str = "unknown",
        source_media_path: Path | None = None,
        media_path: Path | None = None,
        output_paths: tuple[Path, ...] | None = None,
        opened_at: datetime | None = None,
    ) -> TranscriptLibraryEntry:
        existing = self._library_store.get_entry_by_transcript_path(transcript_path)
        entry = _build_library_entry(
            transcript_path,
            output_dir=output_dir,
            source_kind=source_kind,
            source_media_path=source_media_path,
            media_path=media_path,
            output_paths=output_paths,
            opened_at=opened_at,
            existing=existing,
        )
        saved = self._library_store.upsert_entry(entry)
        self._refresh_transcript_library_list()
        return saved

    def _index_result_in_library(self, result) -> None:
        source_kind = _infer_library_source_kind_from_result(result)
        for artifacts in result.outputs:
            transcript_paths = [
                path
                for path in artifacts.paths
                if path.suffix.lower() == ".json"
            ]
            for transcript_path in transcript_paths:
                self._index_transcript_in_library(
                    transcript_path,
                    output_dir=result.job.output_dir,
                    source_kind=source_kind,
                    source_media_path=(
                        artifacts.media_path
                        or _infer_library_source_media_path_from_result(
                            result,
                            transcript_path,
                        )
                    ),
                    media_path=artifacts.media_path if artifacts.auto_bind_media else None,
                    output_paths=tuple(artifacts.paths),
                )

    def _remove_transcript_from_library(self, transcript_path: Path) -> bool:
        removed = self._library_store.remove_entry_by_transcript_path(transcript_path)
        if removed:
            self._refresh_transcript_library_list()
        return removed

    def _remove_missing_library_entries(self) -> int:
        removed = self._library_store.remove_missing_entries()
        return len(removed)

    def _clean_missing_library_entries(self) -> None:
        removed = self._remove_missing_library_entries()
        self._refresh_transcript_library_list()
        if removed:
            self.status_label.setText(
                f"Removed {removed} missing transcript entr{'y' if removed == 1 else 'ies'} from the library."
            )
        else:
            self.status_label.setText("No missing transcript entries needed cleanup.")

    def _refresh_transcript_library_list(self) -> None:
        all_entries = self._library_store.list_entries()
        source_kind = (
            self._library_source_filter_combo.currentData()
            if self._library_source_filter_combo is not None
            else "all"
        )
        missing_filter = (
            self._library_missing_filter_combo.currentData()
            if self._library_missing_filter_combo is not None
            else "all"
        )
        opened_filter = (
            self._library_opened_filter_combo.currentData()
            if self._library_opened_filter_combo is not None
            else "all"
        )
        sort_mode = (
            self._library_sort_combo.currentData()
            if self._library_sort_combo is not None
            else "last_opened"
        )
        descending = (
            self._library_sort_direction_combo.currentData() != "asc"
            if self._library_sort_direction_combo is not None
            else True
        )
        entries = sort_transcript_library_entries(
            filter_transcript_library_entries(
                all_entries,
                source_kind=source_kind,
                missing_filter=missing_filter,
                opened_filter=opened_filter,
            ),
            sort_mode=sort_mode,
            descending=descending,
        )
        self._library_entries_cache = entries
        if self._library_summary_label is not None:
            summary = _library_results_summary(entries, total_count=len(all_entries))
            if any(entry.missing for entry in all_entries):
                summary += " | Use Clean Missing Entries to drop broken transcript records."
            self._library_summary_label.setText(summary)
        if self._library_entries_list is None:
            return
        self._library_entries_list.clear()
        for entry in entries:
            self._library_entries_list.addItem(_library_entry_list_label(entry))

    def _refresh_export_profiles_list(self) -> None:
        if self._export_profiles_list is None:
            return
        self._export_profiles_list.clear()
        for profile in self._export_profiles:
            self._export_profiles_list.addItem(profile_list_label(profile))

    def _selected_export_profile(self) -> ExportProfile | None:
        if self._export_profiles_list is None:
            return None
        row = self._export_profiles_list.currentRow()
        if row < 0 or row >= len(self._export_profiles):
            return None
        return self._export_profiles[row]

    def _prompt_export_profile_name(self, *, title: str, text: str, value: str = "") -> str | None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, title, text, text=value)
        if not ok:
            return None
        normalized = str(name).strip()
        return normalized or None

    def _save_current_export_profile_as_new(self) -> None:
        name = self._prompt_export_profile_name(
            title="Save export profile",
            text="Profile name:",
        )
        if not name:
            self.status_label.setText("Export profile save canceled.")
            return
        try:
            profile = create_export_profile(name, self._current_export_preferences())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._export_profiles = upsert_export_profile(self._export_profiles, profile)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Saved export profile: {profile.name}")

    def _update_selected_export_profile(self) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        updated = create_export_profile(profile.name, self._current_export_preferences())
        self._export_profiles = upsert_export_profile(self._export_profiles, updated)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Updated export profile: {updated.name}")

    def _apply_selected_export_profile(self) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        updated_preferences = apply_export_profile(profile, self._current_gui_preferences())
        self._apply_export_preferences(updated_preferences)
        self.status_label.setText(f"Applied export profile: {profile.name}")

    def _delete_selected_export_profile(self) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        self._export_profiles = remove_export_profile(self._export_profiles, profile.name)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Deleted export profile: {profile.name}")

    def _selected_library_entry(self) -> TranscriptLibraryEntry | None:
        if self._library_entries_list is None:
            return None
        row = self._library_entries_list.currentRow()
        if row < 0 or row >= len(self._library_entries_cache):
            return None
        return self._library_entries_cache[row]

    def _open_selected_library_transcript(self, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        transcript_path = entry.transcript_path
        if not transcript_path.is_file():
            self.status_label.setText(
                f"Transcript is missing: {transcript_path}. Clean missing entries or restore the file before reopening it."
            )
            self._refresh_transcript_library_list()
            return
        self._load_transcript_json(transcript_path)

    def _open_selected_library_output_dir(self, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        self._open_recent_output_dir(entry.output_dir)

    def _rebind_selected_library_media(self, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        if not entry.transcript_path.is_file():
            self.status_label.setText(
                f"Transcript is missing: {entry.transcript_path}. Clean missing entries or restore the file before rebinding media."
            )
            self._refresh_transcript_library_list()
            return
        if not self._load_transcript_json(entry.transcript_path):
            return
        self._bind_media_to_transcript()

    def _remove_selected_library_entry(self, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        removed = self._library_store.remove_entry(entry.entry_id)
        self._refresh_transcript_library_list()
        if removed:
            self.status_label.setText(
                f"Removed transcript from library only: {entry.transcript_path.name}"
            )
            return
        self.status_label.setText("Could not remove the selected library entry.")

    def _refresh_transcript_summary_panel(self) -> None:
        if self._transcript_view is None:
            self.transcript_summary.setPlainText("No transcript is loaded.")
            return
        summary = render_transcript_summary(self._transcript_view)
        if self._transcript_edit_dirty:
            summary += "\nUnsaved edits: yes"
        self.transcript_summary.setPlainText(summary)

    def _refresh_transcript_segments_list(self) -> None:
        self.transcript_segments.clear()
        if self._editable_transcript is None:
            return
        for segment in self._editable_transcript.segments:
            self.transcript_segments.addItem(render_editable_segment_line(segment))

    def _clear_transcript_editor(self, *, message: str) -> None:
        self._updating_segment_editor = True
        try:
            self.segment_editor.clear()
        finally:
            self._updating_segment_editor = False
        self.segment_editor.setEnabled(False)
        self.segment_revert_button.setEnabled(False)
        self.save_transcript_button.setEnabled(False)
        self.save_transcript_copy_button.setEnabled(False)
        self.transcript_edit_status_label.setText(message)

    def _refresh_transcript_edit_state(self) -> None:
        has_document = self._editable_transcript is not None
        has_selection = (
            has_document
            and 0 <= self._active_segment_row < len(self._editable_transcript.segments)
        )
        self.segment_editor.setEnabled(bool(has_selection))
        self.segment_revert_button.setEnabled(bool(has_selection))
        self.save_transcript_button.setEnabled(bool(has_document and self._transcript_edit_dirty))
        self.save_transcript_copy_button.setEnabled(bool(has_document))
        self.reexport_transcript_button.setEnabled(bool(has_document))
        if not has_document:
            self.transcript_edit_status_label.setText("No transcript loaded for editing.")
        elif self._transcript_edit_dirty:
            self.transcript_edit_status_label.setText(
                "Transcript has unsaved edits. Save to overwrite or create a corrected copy."
            )
        elif has_selection:
            self.transcript_edit_status_label.setText(
                "Editing transcript segment text preserves segment order and timestamps."
            )
        else:
            self.transcript_edit_status_label.setText(
                "Select a transcript segment to edit its text."
            )
        self._refresh_transcript_summary_panel()

    def _populate_segment_editor(self, row: int) -> None:
        if self._editable_transcript is None:
            self._clear_transcript_editor(message="No transcript loaded for editing.")
            return
        if row < 0 or row >= len(self._editable_transcript.segments):
            self._clear_transcript_editor(message="Select a transcript segment to edit its text.")
            return
        segment = self._editable_transcript.segments[row]
        self._updating_segment_editor = True
        try:
            self.segment_editor.setPlainText(segment.text)
        finally:
            self._updating_segment_editor = False
        self._refresh_transcript_edit_state()

    def _on_segment_editor_text_changed(self) -> None:
        if self._updating_segment_editor or self._editable_transcript is None:
            return
        row = self._active_segment_row
        if row < 0 or row >= len(self._editable_transcript.segments):
            return
        updated = update_editable_transcript_segment(
            self._editable_transcript,
            row,
            self.segment_editor.toPlainText(),
        )
        if updated == self._editable_transcript:
            return
        self._editable_transcript = updated
        self._transcript_edit_dirty = updated.dirty
        item = self.transcript_segments.item(row)
        if item is not None:
            item.setText(render_editable_segment_line(updated.segments[row]))
        self._refresh_transcript_edit_state()

    def _revert_selected_segment_edit(self) -> None:
        if self._editable_transcript is None:
            return
        row = self._active_segment_row
        if row < 0 or row >= len(self._editable_transcript.segments):
            return
        segment = self._editable_transcript.segments[row]
        self._editable_transcript = update_editable_transcript_segment(
            self._editable_transcript,
            row,
            segment.original_text,
        )
        self._transcript_edit_dirty = self._editable_transcript.dirty
        self._populate_segment_editor(row)
        self._refresh_transcript_segments_list()
        self._select_transcript_segment(row, follow=False, focus=False)

    def _prompt_for_transcript_save_destination(self) -> Path | None:
        from PySide6.QtWidgets import QFileDialog

        if self._editable_transcript is None:
            return None
        suggested = suggested_corrected_transcript_path(self._editable_transcript.path)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save corrected transcript JSON",
            str(suggested),
            "JSON files (*.json)",
        )
        if not path:
            return None
        return Path(path)

    def _save_transcript_edits(self, force_save_as: bool = False) -> bool:
        from PySide6.QtWidgets import QMessageBox

        if self._editable_transcript is None:
            self.status_label.setText("Open a transcript JSON file before saving edits.")
            return False
        if not self._editable_transcript.dirty and not force_save_as:
            self.status_label.setText("There are no transcript edits to save.")
            return True

        target_path: Path | None = None
        if force_save_as:
            target_path = self._prompt_for_transcript_save_destination()
            if target_path is None:
                self.status_label.setText("Save canceled.")
                return False
        else:
            choice_box = QMessageBox(self)
            choice_box.setWindowTitle("Save transcript edits")
            choice_box.setText(
                "Choose whether to overwrite the current transcript or save a corrected copy."
            )
            overwrite_button = choice_box.addButton("Overwrite Original", QMessageBox.ButtonRole.AcceptRole)
            copy_button = choice_box.addButton("Save As Copy", QMessageBox.ButtonRole.ActionRole)
            cancel_button = choice_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            choice_box.exec()
            clicked = choice_box.clickedButton()
            if clicked == cancel_button:
                self.status_label.setText("Save canceled.")
                return False
            if clicked == copy_button:
                target_path = self._prompt_for_transcript_save_destination()
                if target_path is None:
                    self.status_label.setText("Save canceled.")
                    return False
            elif clicked == overwrite_button:
                target_path = self._editable_transcript.path
            else:
                return False

        saved_path = save_editable_transcript(
            self._editable_transcript,
            destination=target_path,
        )
        self._load_transcript_json(saved_path, allow_unsaved_prompt=False)
        if self._media_path is not None:
            self._index_transcript_in_library(
                saved_path,
                media_path=self._media_path,
                opened_at=datetime.now(),
            )
        self.status_label.setText(f"Saved corrected transcript: {saved_path.name}")
        return True

    def _reexport_current_transcript(self) -> bool:
        if self._editable_transcript is None:
            self.status_label.setText("Open a transcript JSON file before re-exporting.")
            return False
        if self._transcript_edit_dirty:
            self.status_label.setText(
                "Save transcript edits before re-exporting so outputs include the latest text."
            )
            return False

        output_formats = tuple(
            output_format
            for output_format, checkbox in self.format_checks.items()
            if checkbox.isChecked()
        )
        if not output_formats:
            self.status_label.setText("Select at least one output format for re-export.")
            return False

        output_dir = Path(self.output_dir_input.text().strip() or "outputs")
        output_name_base = self.output_name_input.text().strip() or None
        try:
            artifacts = reexport_transcript_json(
                self._editable_transcript.path,
                output_dir=output_dir,
                output_formats=output_formats,
                output_name_base=output_name_base,
                overwrite=self.overwrite_check.isChecked(),
                include_timestamps=self.timestamps_check.isChecked(),
            )
        except (ValueError, OutputError) as exc:
            self.status_label.setText(str(exc))
            return False

        self._last_output_dir = output_dir
        self._remember_recent_output_dir(output_dir)
        self.preview_output.append("\nRe-exported transcript outputs:")
        for path in artifacts.paths:
            self.preview_output.append(str(path))
        self._load_artifact_views(tuple(artifacts.paths), replace=True)

        transcript_paths = [
            path
            for path in artifacts.paths
            if path.suffix.lower() == ".json"
        ]
        if transcript_paths:
            for transcript_path in transcript_paths:
                self._index_transcript_in_library(
                    transcript_path,
                    output_dir=output_dir,
                    source_kind="unknown",
                    source_media_path=self._media_path,
                    media_path=self._media_path,
                    output_paths=tuple(artifacts.paths),
                    opened_at=datetime.now(),
                )
        else:
            self._index_transcript_in_library(
                self._editable_transcript.path,
                output_dir=output_dir,
                source_kind="unknown",
                source_media_path=self._media_path,
                media_path=self._media_path,
                output_paths=tuple(artifacts.paths),
                opened_at=datetime.now(),
            )

        self.open_output_button.setEnabled(True)
        self.status_label.setText(
            f"Re-exported {len(artifacts.paths)} transcript artifact(s) from JSON."
        )
        if artifacts.paths or transcript_paths:
            self._select_view_tab("transcript")
        return True

    def _confirm_unsaved_transcript_edits(self) -> bool:
        from PySide6.QtWidgets import QMessageBox

        if not self._transcript_edit_dirty or self._editable_transcript is None:
            return True

        prompt = QMessageBox(self)
        prompt.setWindowTitle("Unsaved transcript edits")
        prompt.setText("The current transcript has unsaved edits.")
        prompt.setInformativeText("Save changes before continuing?")
        save_button = prompt.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = prompt.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        prompt.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        prompt.exec()
        clicked = prompt.clickedButton()
        if clicked == save_button:
            return self._save_transcript_edits()
        if clicked == discard_button:
            return True
        return False

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
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem

        if self._recent_transcripts_list is not None:
            self._recent_transcripts_list.clear()
            for path_text in self._recent_work.get("recent_transcripts", []):
                transcript_path = Path(str(path_text))
                entry = self._library_store.get_entry_by_transcript_path(transcript_path)
                item = QListWidgetItem(
                    _recent_transcript_list_label(transcript_path, entry=entry)
                )
                item.setData(Qt.ItemDataRole.UserRole, str(transcript_path))
                self._recent_transcripts_list.addItem(item)
        if self._recent_output_dirs_list is not None:
            self._recent_output_dirs_list.clear()
            for path_text in self._recent_work.get("recent_output_dirs", []):
                item = QListWidgetItem(str(path_text))
                item.setData(Qt.ItemDataRole.UserRole, str(path_text))
                self._recent_output_dirs_list.addItem(item)
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
        from PySide6.QtCore import Qt

        if list_widget is None:
            return None
        item = list_widget.currentItem()
        if item is None:
            return None
        stored = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
        text = item.text().strip()
        return text or None

    def _drop_missing_recent_path(self, key: str, target: Path) -> None:
        target_text = str(target)
        entries = [item for item in self._recent_work.get(key, []) if isinstance(item, str)]
        self._recent_work[key] = [item for item in entries if item != target_text]
        if key == "recent_transcripts":
            self._remove_transcript_from_library(target)
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
            self.status_label.setText(
                f"Recent output directory is missing and was removed: {path}. Choose another output folder or run a new transcription."
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.status_label.setText(
                f"Could not open output directory: {path}. Check folder permissions or choose another output path."
            )
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

    # --- Batch Queue Methods ---

    def _current_queue_item_settings(self) -> QueueItemSettings:
        return QueueItemSettings(
            output_dir=Path(self.output_dir_input.text().strip() or "outputs"),
            model_name=self.model_combo.currentText().strip() or "small",
            language=self.language_combo.currentText().strip() or None,
            preset=self.preset_combo.currentText().strip() or None,
            output_formats=tuple(
                fmt
                for fmt in SUPPORTED_GUI_FORMATS
                if getattr(self, f"format_{fmt}_check", None) is not None
                and getattr(self, f"format_{fmt}_check").isChecked()
            ),
            timestamps=self.timestamps_check.isChecked(),
            word_timestamps=self.word_timestamps_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            network_family=self.network_combo.currentData() or "auto",
            proxy=self.proxy_input.text().strip() or None,
            cookies_path=Path(self.cookies_input.text().strip())
            if self.cookies_input.text().strip()
            else None,
        )

    def _current_output_strategy(self) -> BatchOutputStrategy:
        mode = "unified"
        if self._queue_tab is not None:
            mode = self._queue_tab.output_strategy_mode
        base_dir = Path(self.output_dir_input.text().strip() or "outputs")
        return BatchOutputStrategy(mode=mode, base_dir=base_dir)

    def _enqueue_urls_from_text(self, text: str) -> None:
        urls = parse_urls_from_text(text)
        if not urls:
            self.status_label.setText("No valid URLs found in the pasted text.")
            return
        self._enqueue_url_list(urls)

    def _enqueue_from_file(self, file_path: str) -> None:
        try:
            urls = import_urls_from_file(Path(file_path))
        except Exception as exc:
            self.status_label.setText(f"Import failed: {exc}")
            return
        if not urls:
            self.status_label.setText("No valid URLs found in the imported file.")
            return
        self._enqueue_url_list(urls)

    def _enqueue_url_list(self, urls: list[str]) -> None:
        from flowscribe.app.models import SourceSpec

        settings = self._current_queue_item_settings()
        strategy = self._current_output_strategy()
        max_retries = self._queue_tab.max_retries if self._queue_tab else 2
        sources = [SourceSpec(kind="url", value=url) for url in urls]
        existing = self._queue_store.load_items()
        unique = deduplicate_sources(sources, existing)
        if not unique:
            self.status_label.setText("All URLs are already in the queue.")
            return
        added = 0
        for source in unique:
            item = QueueItem(
                item_id=generate_queue_item_id(source),
                source=source,
                settings=settings,
                output_strategy=strategy,
                max_retries=max_retries,
            )
            if self._queue_store.enqueue(item) is not None:
                added += 1
        self.status_label.setText(f"Added {added} URL(s) to queue.")
        self._refresh_queue_tab()

    def _refresh_queue_tab(self) -> None:
        if self._queue_tab is None:
            return
        items = self._queue_store.load_items()
        self._queue_tab.refresh_queue_list(items)

    def _start_queue_processing(self) -> None:
        if self._queue_thread is not None:
            self.status_label.setText("Queue is already running.")
            return
        if self._thread is not None:
            self.status_label.setText("Wait for the current transcription to finish first.")
            return
        if self._queue_store.pending_count() == 0:
            self.status_label.setText("No pending items in the queue.")
            return

        self._queue_thread = QThread(self)
        self._queue_runner = QueueRunner(self._queue_store)
        self._queue_runner.moveToThread(self._queue_thread)

        self._queue_thread.started.connect(self._queue_runner.run)
        self._queue_runner.item_started.connect(self._on_queue_item_started)
        self._queue_runner.item_progress.connect(self._on_queue_item_progress)
        self._queue_runner.item_completed.connect(self._on_queue_item_completed)
        self._queue_runner.item_failed.connect(self._on_queue_item_failed)
        self._queue_runner.item_canceled.connect(self._on_queue_item_canceled)
        self._queue_runner.queue_progress.connect(self._on_queue_progress)
        self._queue_runner.queue_finished.connect(self._on_queue_finished)
        self._queue_runner.queue_finished.connect(self._queue_thread.quit)
        self._queue_thread.finished.connect(self._queue_runner.deleteLater)
        self._queue_thread.finished.connect(self._queue_thread.deleteLater)
        self._queue_thread.finished.connect(self._clear_queue_refs)

        if self._queue_tab:
            self._queue_tab.set_running(True)
        self._queue_thread.start()
        self.status_label.setText("Queue processing started.")

    def _stop_queue_processing(self) -> None:
        if self._queue_runner is not None:
            self._queue_runner.request_cancel_all()

    def _skip_current_queue_item(self) -> None:
        if self._queue_runner is not None:
            self._queue_runner.request_skip_current()

    def _on_queue_item_started(self, item) -> None:
        if self._queue_tab:
            self._queue_tab.set_current_item_status(f"Processing: {item.display_label}")
        self._refresh_queue_tab()

    def _on_queue_item_progress(self, event) -> None:
        if self._queue_tab and event.message:
            self._queue_tab.set_current_item_status(event.message)

    def _on_queue_item_completed(self, payload) -> None:
        self._refresh_queue_tab()

    def _on_queue_item_failed(self, payload) -> None:
        item, message = payload
        LOGGER.warning("Queue item failed: %s — %s", item.display_label, message)
        self._refresh_queue_tab()

    def _on_queue_item_canceled(self, item) -> None:
        self._refresh_queue_tab()

    def _on_queue_progress(self, completed: int, total: int) -> None:
        if self._queue_tab:
            self._queue_tab.set_overall_progress(completed, total)

    def _on_queue_finished(self) -> None:
        self._notification_player.play_completion_sound()
        if self._queue_tab:
            self._queue_tab.set_running(False)
        self.status_label.setText("Queue processing finished.")
        self._refresh_queue_tab()

    def _clear_queue_refs(self) -> None:
        self._queue_thread = None
        self._queue_runner = None

    def _retry_queue_item(self, item_id: str) -> None:
        self._queue_store.update_item(item_id, status="pending", started_at=None, error_message=None)
        self._refresh_queue_tab()

    def _remove_queue_item(self, item_id: str) -> None:
        self._queue_store.remove_item(item_id)
        self._refresh_queue_tab()

    def _clear_completed_queue_items(self) -> None:
        removed = self._queue_store.remove_completed()
        self.status_label.setText(f"Cleared {removed} completed item(s) from queue.")
        self._refresh_queue_tab()

    def _reorder_queue_items(self, item_ids: list[str]) -> None:
        self._queue_store.reorder(item_ids)

