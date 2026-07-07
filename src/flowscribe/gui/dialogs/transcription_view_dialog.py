"""Transcription view dialog with Run Details and Workspace tabs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .transcription_view_dialog_editing import TranscriptionViewDialogEditingMixin
from .transcription_view_dialog_media import TranscriptionViewDialogMediaMixin
from .transcription_view_dialog_session import TranscriptionViewDialogSessionMixin
from .transcription_view_dialog_workspace import TranscriptionViewDialogWorkspaceMixin
from flowscribe.gui.windows.transcript_viewer_controls import TranscriptViewerControlsMixin
from flowscribe.gui.windows.workspace_controls import WorkspaceControlsMixin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class TranscriptionViewDialog(
    QDialog,
    TranscriptionViewDialogSessionMixin,
    TranscriptionViewDialogMediaMixin,
    TranscriptionViewDialogEditingMixin,
    TranscriptionViewDialogWorkspaceMixin,
    TranscriptViewerControlsMixin,
    WorkspaceControlsMixin,
):
    """View dialog for transcription with Run Details and Workspace tabs."""

    def __init__(
        self,
        parent: QWidgetType | None = None,
        *,
        transcript_path: Path | None = None,
        run_output: str = "",
        result=None,
        output_paths: tuple[Path, ...] | None = None,
    ):
        super().__init__(parent)
        self._transcript_path = transcript_path
        self._run_output = run_output
        self._result = result
        self._output_paths = output_paths

        self._transcript_view = None
        self._editable_transcript = None
        self._search_hits = ()
        self._workspace_artifacts = ()
        self._workspace_artifact_paths = ()
        self._workspace_artifact_quick_buttons = {}

        self._current_segment_index = -1
        self._segment_modified = False
        self._transcript_edit_dirty = False
        self._active_segment_row = -1
        self._last_chunk_index = 0

        self.setWindowTitle("Transcription View")
        self.resize(980, 760)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._setup_ui()

        if transcript_path and transcript_path.is_file():
            if output_paths:
                self._load_transcript_with_artifacts(transcript_path, output_paths)
            else:
                self._load_transcript(transcript_path)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(6)
        toolbar_row.addWidget(
            QLabel("Review run details, transcript workspace, and generated artifacts.")
        )
        toolbar_row.addStretch(1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        toolbar_row.addWidget(close_button)
        layout.addLayout(toolbar_row)

        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs)

        self._create_run_details_tab()
        self._create_workspace_tab()

    def _create_run_details_tab(self) -> None:
        run_details_page = QWidget(self)
        run_details_layout = QVBoxLayout(run_details_page)
        run_details_layout.setContentsMargins(6, 6, 6, 6)
        run_details_layout.setSpacing(6)

        if self._result is not None and self._result.elapsed_seconds is not None:
            elapsed = self._result.elapsed_seconds
            if elapsed < 60:
                elapsed_str = f"{elapsed:.1f}s"
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                elapsed_str = f"{minutes}m {seconds}s"

            time_label = QLabel(f"Elapsed Time: {elapsed_str}")
            time_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #4CAF50;")
            run_details_layout.addWidget(time_label)

        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlainText(self._run_output)
        self.preview_output.setPlaceholderText("Transcription progress and output will appear here.")
        run_details_layout.addWidget(self.preview_output)

        self.tabs.addTab(run_details_page, "Run Details")

    def _create_workspace_tab(self) -> None:
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(scroll_area.Shape.NoFrame)

        workspace_page = QWidget()
        workspace_layout = QVBoxLayout(workspace_page)
        workspace_layout.setContentsMargins(6, 6, 6, 6)
        workspace_layout.setSpacing(8)

        workspace_summary_label = QLabel(
            "Keep playback, segment review, editing, and transcript artifacts in one workspace."
        )
        workspace_summary_label.setWordWrap(True)
        workspace_summary_label.setStyleSheet("color: gray; font-size: 10px;")
        workspace_layout.addWidget(workspace_summary_label)

        workspace_splitter = QSplitter(Qt.Orientation.Vertical, workspace_page)
        workspace_splitter.setChildrenCollapsible(False)
        workspace_splitter.setHandleWidth(6)

        review_splitter = QSplitter(Qt.Orientation.Horizontal, workspace_splitter)
        review_splitter.setChildrenCollapsible(False)
        review_splitter.setHandleWidth(6)

        review_left = QWidget(review_splitter)
        review_left_layout = QVBoxLayout(review_left)
        review_left_layout.setContentsMargins(0, 0, 0, 0)
        review_left_layout.setSpacing(6)
        review_left_layout.addWidget(self._create_media_sync_section(), 1)

        self.transcript_summary = QTextBrowser()
        self.transcript_summary.setReadOnly(True)
        self.transcript_summary.setMaximumHeight(72)
        self.transcript_summary.setOpenExternalLinks(False)
        self.transcript_summary.setPlaceholderText("Transcript summary will appear here.")
        self.transcript_summary.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        review_left_layout.addWidget(self.transcript_summary, 1)

        review_right = QSplitter(Qt.Orientation.Vertical, review_splitter)
        review_right.setChildrenCollapsible(False)
        review_right.setHandleWidth(6)
        review_right.addWidget(self._create_search_section())
        review_right.addWidget(self._create_segments_section())
        review_right.addWidget(self._create_editing_section())

        review_splitter.addWidget(review_left)
        review_splitter.addWidget(review_right)

        artifact_box = self._create_artifacts_section()
        artifact_box.setMinimumHeight(460)
        workspace_splitter.addWidget(review_splitter)
        workspace_splitter.addWidget(artifact_box)

        workspace_splitter.setStretchFactor(0, 2)
        workspace_splitter.setStretchFactor(1, 5)
        review_splitter.setStretchFactor(0, 3)
        review_splitter.setStretchFactor(1, 4)
        review_right.setStretchFactor(0, 1)
        review_right.setStretchFactor(1, 4)
        review_right.setStretchFactor(2, 2)

        workspace_layout.addWidget(workspace_splitter, 1)
        workspace_splitter.setSizes([300, 560])
        scroll_area.setWidget(workspace_page)
        self.tabs.addTab(scroll_area, "Workspace")

    def _create_media_sync_section(self) -> QGroupBox:
        media_box = QGroupBox("Media Sync")
        media_layout = QVBoxLayout(media_box)
        media_layout.setSpacing(8)
        media_layout.setContentsMargins(10, 12, 10, 10)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(150)
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

        self.media_binding_label = QLabel("Binding: Unbound")
        self.media_binding_label.setWordWrap(True)
        self.media_status_label = QLabel("Open a transcript JSON file to bind media.")
        self.media_status_label.setWordWrap(True)

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

        self.open_media_button.setEnabled(False)
        self.play_media_button.setEnabled(False)
        self.media_position_slider.setEnabled(False)
        return media_box

    def _create_search_section(self) -> QGroupBox:
        search_box = QGroupBox("Transcript search")
        search_layout = QVBoxLayout(search_box)
        search_layout.setContentsMargins(10, 12, 10, 10)
        search_layout.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search transcript keyword")
        self.search_input.returnPressed.connect(self._run_transcript_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._run_transcript_search)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)

        self.search_results = QListWidget()
        self.search_results.setMinimumHeight(64)
        self.search_results.setMaximumHeight(96)
        self.search_results.itemActivated.connect(self._jump_to_selected_hit)
        self.search_results.itemClicked.connect(self._jump_to_selected_hit)

        search_layout.addLayout(search_row)
        search_layout.addWidget(self.search_results)
        return search_box

    def _create_segments_section(self) -> QGroupBox:
        segments_box = QGroupBox("Transcript segments")
        segments_layout = QVBoxLayout(segments_box)
        segments_layout.setContentsMargins(10, 12, 10, 10)
        segments_layout.setSpacing(6)

        self.transcript_segments = QListWidget()
        self.transcript_segments.setMinimumHeight(140)
        self.transcript_segments.itemActivated.connect(self._activate_selected_segment)
        self.transcript_segments.itemClicked.connect(self._activate_selected_segment)
        segments_layout.addWidget(self.transcript_segments)
        return segments_box

    def _create_editing_section(self) -> QGroupBox:
        edit_box = QGroupBox("Transcript editing")
        edit_layout = QVBoxLayout(edit_box)
        edit_layout.setContentsMargins(10, 12, 10, 10)
        edit_layout.setSpacing(6)

        self.segment_editor = QTextEdit()
        self.segment_editor.setPlaceholderText("Select a transcript segment to edit its text.")
        self.segment_editor.textChanged.connect(self._on_segment_editor_text_changed)
        self.segment_editor.setEnabled(False)
        self.segment_editor.setMinimumHeight(96)
        edit_layout.addWidget(self.segment_editor)

        edit_actions = QHBoxLayout()
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
        edit_actions.addWidget(self.segment_revert_button)
        edit_actions.addWidget(self.save_transcript_button)
        edit_actions.addWidget(self.save_transcript_copy_button)
        edit_actions.addWidget(self.reexport_transcript_button)
        edit_layout.addLayout(edit_actions)

        self.transcript_edit_status_label = QLabel("No transcript loaded for editing.")
        self.transcript_edit_status_label.setWordWrap(True)
        self.transcript_edit_status_label.setStyleSheet("color: gray; font-size: 10px;")
        edit_layout.addWidget(self.transcript_edit_status_label)

        edit_box.setMaximumHeight(220)
        return edit_box

    def _create_artifacts_section(self) -> QGroupBox:
        artifact_box = QGroupBox("Transcript artifacts")
        artifact_layout = QVBoxLayout(artifact_box)
        artifact_layout.setContentsMargins(10, 12, 10, 10)
        artifact_layout.setSpacing(6)

        artifact_toolbar = QHBoxLayout()
        artifact_toolbar.setSpacing(6)
        open_transcript_button = QPushButton("Open Transcript", artifact_box)
        open_transcript_button.clicked.connect(self._open_transcript_file)
        artifact_toolbar.addWidget(open_transcript_button)
        artifact_toolbar.addWidget(QLabel("Artifact"))
        self.artifact_selector = QComboBox(artifact_box)
        self.artifact_selector.currentIndexChanged.connect(self._show_selected_workspace_artifact)
        artifact_toolbar.addWidget(self.artifact_selector, 1)

        self.artifact_format_label = QLabel("No artifact selected")
        artifact_toolbar.addWidget(self.artifact_format_label)

        open_artifact_button = QPushButton("Open Artifact", artifact_box)
        open_artifact_button.clicked.connect(self._open_selected_workspace_artifact_tab)
        artifact_toolbar.addWidget(open_artifact_button)
        artifact_layout.addLayout(artifact_toolbar)

        artifact_compare_row = QHBoxLayout()
        artifact_compare_row.setSpacing(4)
        artifact_compare_row.addWidget(QLabel("Quick switch"))
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
                lambda _checked=False, target_group=group: self._show_workspace_artifact_group(
                    target_group
                )
            )
            artifact_compare_row.addWidget(button)
            self._workspace_artifact_quick_buttons[group] = button
        artifact_compare_row.addStretch(1)
        artifact_layout.addLayout(artifact_compare_row)

        self.artifact_status_label = QLabel(
            "Open a transcript or artifact to inspect generated files here."
        )
        self.artifact_status_label.setWordWrap(True)
        self.artifact_status_label.setStyleSheet("color: gray; font-size: 10px;")
        self.artifact_status_label.setMaximumHeight(34)
        artifact_layout.addWidget(self.artifact_status_label)

        artifact_viewer_stack = QStackedWidget(artifact_box)
        self.artifact_viewer = QPlainTextEdit(artifact_box)
        self.artifact_viewer.setReadOnly(True)
        self.artifact_markdown_viewer = QTextBrowser(artifact_box)
        self.artifact_markdown_viewer.setReadOnly(True)
        self.artifact_markdown_viewer.setOpenExternalLinks(False)
        artifact_viewer_stack.addWidget(self.artifact_viewer)
        artifact_viewer_stack.addWidget(self.artifact_markdown_viewer)
        artifact_layout.addWidget(artifact_viewer_stack, 1)

        self._workspace_artifact_viewer_stack = artifact_viewer_stack
        return artifact_box
