"""Transcription view dialog for reviewing individual transcription results."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
    QToolButton,
    QGroupBox,
    QSplitter,
    QTextEdit,
    QTextBrowser,
    QLineEdit,
    QListWidget,
    QComboBox,
    QPlainTextEdit,
    QStackedWidget,
    QSlider,
    QSizePolicy,
    QMenu,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class TranscriptionViewDialog(QDialog):
    """Dialog for viewing transcription run details, workspace, and artifacts."""

    def __init__(
        self,
        parent: QWidgetType | None = None,
        *,
        transcript_path: Path | None = None,
        run_output: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Transcription View")
        self.resize(1100, 800)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._transcript_path = transcript_path
        self._transcript_view = None
        self._editable_transcript = None
        self._search_hits: tuple = ()
        self._workspace_artifact_paths: tuple[Path, ...] = ()
        self._workspace_artifact_quick_buttons: dict[str, QPushButton] = {}

        self._setup_ui(run_output)

        if transcript_path and transcript_path.is_file():
            self._load_transcript(transcript_path)

    def _setup_ui(self, run_output: str) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(
            QLabel("Review run details, transcript workspace, and generated artifacts.")
        )
        toolbar_row.addStretch(1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        toolbar_row.addWidget(close_button)
        layout.addLayout(toolbar_row)

        # Tab widget
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs)

        # Run Details tab
        self._create_run_details_tab(run_output)

        # Workspace tab
        self._create_workspace_tab()

    def _create_run_details_tab(self, run_output: str) -> None:
        """Create run details tab."""
        run_details_page = QWidget(self)
        run_details_layout = QVBoxLayout(run_details_page)
        run_details_layout.setContentsMargins(8, 8, 8, 8)

        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlainText(run_output)
        self.preview_output.setPlaceholderText("Transcription progress and output will appear here.")
        run_details_layout.addWidget(self.preview_output)

        self.tabs.addTab(run_details_page, "Run Details")

    def _create_workspace_tab(self) -> None:
        """Create workspace tab with media sync, search, segments, editing, and artifacts."""
        workspace_page = QWidget(self)
        workspace_layout = QVBoxLayout(workspace_page)
        workspace_layout.setContentsMargins(8, 8, 8, 8)
        workspace_layout.setSpacing(10)

        workspace_summary_label = QLabel(
            "Keep playback, segment review, editing, and transcript artifacts in one workspace."
        )
        workspace_summary_label.setWordWrap(True)
        workspace_layout.addWidget(workspace_summary_label)

        workspace_splitter = QSplitter(Qt.Orientation.Vertical, workspace_page)
        workspace_splitter.setChildrenCollapsible(False)

        # Top section: Media + Transcript review
        review_splitter = QSplitter(Qt.Orientation.Horizontal, workspace_splitter)
        review_splitter.setChildrenCollapsible(False)

        # Left: Media Sync + Summary
        review_left = QWidget(review_splitter)
        review_left_layout = QVBoxLayout(review_left)
        review_left_layout.setContentsMargins(0, 0, 0, 0)
        review_left_layout.setSpacing(8)

        media_box = self._create_media_sync_section()
        review_left_layout.addWidget(media_box, 3)

        self.transcript_summary = QTextBrowser()
        self.transcript_summary.setReadOnly(True)
        self.transcript_summary.setMaximumHeight(96)
        self.transcript_summary.setOpenExternalLinks(False)
        self.transcript_summary.setPlaceholderText("Transcript summary will appear here.")
        self.transcript_summary.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        review_left_layout.addWidget(self.transcript_summary, 1)

        # Right: Search + Segments + Editing
        review_right = QSplitter(Qt.Orientation.Vertical, review_splitter)
        review_right.setChildrenCollapsible(False)

        search_box = self._create_search_section()
        review_right.addWidget(search_box)

        segments_box = self._create_segments_section()
        review_right.addWidget(segments_box)

        edit_box = self._create_editing_section()
        review_right.addWidget(edit_box)

        review_splitter.addWidget(review_left)
        review_splitter.addWidget(review_right)

        # Bottom section: Artifacts
        artifact_box = self._create_artifacts_section()

        workspace_splitter.addWidget(review_splitter)
        workspace_splitter.addWidget(artifact_box)

        # Set stretch factors
        workspace_splitter.setStretchFactor(0, 4)
        workspace_splitter.setStretchFactor(1, 3)
        review_splitter.setStretchFactor(0, 3)
        review_splitter.setStretchFactor(1, 4)
        review_right.setStretchFactor(0, 1)
        review_right.setStretchFactor(1, 3)
        review_right.setStretchFactor(2, 3)

        workspace_layout.addWidget(workspace_splitter, 1)

        self.tabs.addTab(workspace_page, "Workspace")

    def _create_media_sync_section(self) -> QGroupBox:
        """Create media sync section."""
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

        self.media_binding_label = QLabel("Binding: Unbound")
        self.media_binding_label.setWordWrap(True)
        self.media_status_label = QLabel("Open a transcript JSON file to bind media.")
        self.media_status_label.setWordWrap(True)

        media_layout.addWidget(self.video_widget)
        media_layout.addLayout(media_controls)
        media_layout.addWidget(self.media_position_slider)
        media_layout.addWidget(self.media_binding_label)
        media_layout.addWidget(self.media_status_label)

        # Media player setup
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
        """Create transcript search section."""
        search_box = QGroupBox("Transcript search")
        search_layout = QVBoxLayout(search_box)

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

        search_layout.addLayout(search_row)
        search_layout.addWidget(self.search_results)

        return search_box

    def _create_segments_section(self) -> QGroupBox:
        """Create transcript segments section."""
        segments_box = QGroupBox("Transcript segments")
        segments_layout = QVBoxLayout(segments_box)

        self.transcript_segments = QListWidget()
        self.transcript_segments.setMinimumHeight(140)
        self.transcript_segments.itemActivated.connect(self._activate_selected_segment)
        self.transcript_segments.itemClicked.connect(self._activate_selected_segment)

        segments_layout.addWidget(self.transcript_segments)

        return segments_box

    def _create_editing_section(self) -> QGroupBox:
        """Create transcript editing section."""
        edit_box = QGroupBox("Transcript editing")
        edit_layout = QVBoxLayout(edit_box)

        self.segment_editor = QTextEdit()
        self.segment_editor.setPlaceholderText("Select a transcript segment to edit its text.")
        self.segment_editor.textChanged.connect(self._on_segment_editor_text_changed)
        self.segment_editor.setEnabled(False)
        self.segment_editor.setMinimumHeight(120)
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
        edit_layout.addWidget(self.transcript_edit_status_label)

        return edit_box

    def _create_artifacts_section(self) -> QGroupBox:
        """Create transcript artifacts section."""
        artifact_box = QGroupBox("Transcript artifacts")
        artifact_layout = QVBoxLayout(artifact_box)

        artifact_toolbar = QHBoxLayout()
        artifact_toolbar.addWidget(QLabel("Current artifact"))
        self.artifact_selector = QComboBox(artifact_box)
        self.artifact_selector.currentIndexChanged.connect(self._show_selected_workspace_artifact)
        artifact_toolbar.addWidget(self.artifact_selector, 1)

        self.artifact_format_label = QLabel("No artifact selected")
        artifact_toolbar.addWidget(self.artifact_format_label)

        open_artifact_tab_button = QPushButton("Open Tab", artifact_box)
        open_artifact_tab_button.clicked.connect(self._open_selected_workspace_artifact_tab)
        artifact_toolbar.addWidget(open_artifact_tab_button)
        artifact_layout.addLayout(artifact_toolbar)

        artifact_compare_row = QHBoxLayout()
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

    def _load_transcript(self, path: Path) -> None:
        """Load transcript and discover artifacts."""
        self._transcript_path = path
        self.setWindowTitle(f"Transcription View - {path.name}")

        # TODO: Implement full transcript loading with:
        # - load_transcript_view()
        # - load_editable_transcript()
        # - discover artifacts
        # - populate segments list
        # - enable editing controls

        self.open_media_button.setEnabled(True)

    # Placeholder methods (to be implemented with full functionality)
    def _bind_media_to_transcript(self) -> None:
        """Bind media file to transcript."""
        pass

    def _toggle_media_playback(self) -> None:
        """Toggle media playback."""
        pass

    def _seek_media_milliseconds(self, position: int) -> None:
        """Seek media to position."""
        pass

    def _on_media_position_changed(self, position: int) -> None:
        """Handle media position change."""
        pass

    def _on_media_duration_changed(self, duration: int) -> None:
        """Handle media duration change."""
        pass

    def _on_media_playback_state_changed(self, state) -> None:
        """Handle media playback state change."""
        pass

    def _run_transcript_search(self) -> None:
        """Run transcript search."""
        pass

    def _jump_to_selected_hit(self) -> None:
        """Jump to selected search hit."""
        pass

    def _activate_selected_segment(self) -> None:
        """Activate selected segment."""
        pass

    def _on_segment_editor_text_changed(self) -> None:
        """Handle segment editor text change."""
        pass

    def _revert_selected_segment_edit(self) -> None:
        """Revert selected segment edit."""
        pass

    def _save_transcript_edits(self, force_save_as: bool = False) -> None:
        """Save transcript edits."""
        pass

    def _reexport_current_transcript(self) -> None:
        """Re-export current transcript."""
        pass

    def _show_selected_workspace_artifact(self, index: int) -> None:
        """Show selected workspace artifact."""
        pass

    def _open_selected_workspace_artifact_tab(self) -> None:
        """Open selected workspace artifact in tab."""
        pass

    def _show_workspace_artifact_group(self, group: str) -> None:
        """Show workspace artifact by group."""
        pass

    def update_run_output(self, output: str) -> None:
        """Update run details output."""
        self.preview_output.setPlainText(output)
