from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from flowscribe.gui.utils.library import _discover_transcript_output_paths


class TranscriptionViewDialogSessionMixin:
    """Transcript session and workspace reset helpers for the view dialog."""

    def _load_transcript(self, path: Path) -> None:
        self._load_transcript_session(path, discover_artifacts=True)

    def _load_transcript_with_artifacts(
        self,
        transcript_path: Path,
        artifact_paths: tuple[Path, ...],
    ) -> None:
        self._load_transcript_session(
            transcript_path,
            artifact_paths=artifact_paths,
            discover_artifacts=False,
        )

    def _load_transcript_session(
        self,
        transcript_path: Path,
        *,
        artifact_paths: tuple[Path, ...] | None = None,
        discover_artifacts: bool,
    ) -> None:
        if not self._prepare_for_transcript_switch(transcript_path):
            return

        self._reset_workspace_state(reset_run_output=False, disable_controls=False)
        self._transcript_path = transcript_path
        self.setWindowTitle(f"Transcription View - {transcript_path.name}")

        try:
            from flowscribe.gui import transcript_viewer
            from flowscribe.transcript import editing

            self._transcript_view = transcript_viewer.load_transcript_view(transcript_path)
            self._editable_transcript = editing.load_editable_transcript(transcript_path)
            self._transcript_edit_dirty = self._editable_transcript.dirty

            self.transcript_summary.setHtml(
                transcript_viewer.render_transcript_summary(self._transcript_view)
            )
            self._populate_segments()

            resolved_artifacts = (
                tuple(_discover_transcript_output_paths(transcript_path))
                if discover_artifacts
                else tuple(artifact_paths or ())
            )
            self._load_artifacts(resolved_artifacts)

            media_path = transcript_viewer.resolve_transcript_media_path(self._transcript_view)
            if media_path and media_path.is_file():
                self._bind_media(media_path)
            else:
                self.media_binding_label.setText("Binding: Unbound")
                self.media_status_label.setText(
                    "Transcript loaded. Bind media manually to enable playback sync."
                )

            self.open_media_button.setEnabled(True)
            self.search_button.setEnabled(True)
            self.search_input.setEnabled(True)
            self._set_workspace_status(f"Loaded transcript: {transcript_path.name}")
            self._refresh_edit_controls()
        except Exception as exc:
            self._transcript_path = None
            self._transcript_view = None
            self._editable_transcript = None
            self._transcript_edit_dirty = False
            self.transcript_summary.setPlainText(f"Error loading transcript: {exc}")
            self.media_status_label.setText(f"Failed to load transcript: {exc}")
            self._set_workspace_status(f"Error loading transcript: {exc}")
            self._refresh_edit_controls()

    def _open_transcript_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Transcript JSON",
            "",
            "JSON files (*.json);;All files (*.*)",
        )
        if not file_path:
            return

        try:
            path = Path(file_path)
            transcript_data = json.loads(path.read_text(encoding="utf-8"))
            if "segments" not in transcript_data:
                self._set_workspace_status("Invalid transcript format - missing segments")
                return
            self._load_transcript(path)
            self._set_workspace_status(f"Loaded transcript: {path.name}")
        except Exception as exc:
            self._set_workspace_status(f"Error loading transcript: {exc}")

    def _populate_segments(self) -> None:
        from flowscribe.transcript import editing

        if not self._editable_transcript:
            return

        self.transcript_segments.clear()
        for segment in self._editable_transcript.segments:
            self.transcript_segments.addItem(editing.render_editable_segment_line(segment))

    def clear_content(self) -> None:
        self._transcript_path = None
        self._transcript_view = None
        self._editable_transcript = None
        self._search_hits = ()
        self._workspace_artifact_paths = ()
        self._last_chunk_index = 0
        self._current_segment_index = -1
        self._segment_modified = False
        self._transcript_edit_dirty = False
        self._active_segment_row = -1

        if hasattr(self, "_media_player"):
            self._media_player.stop()
            self._media_player.setSource(self._empty_media_source())

        self._reset_workspace_state(reset_run_output=True, disable_controls=True)

    def _reset_workspace_state(
        self,
        *,
        reset_run_output: bool,
        disable_controls: bool,
    ) -> None:
        self._search_hits = ()
        self._workspace_artifact_paths = ()
        self._current_segment_index = -1
        self._segment_modified = False
        self._transcript_edit_dirty = False
        self._active_segment_row = -1

        if reset_run_output and hasattr(self, "preview_output"):
            self.preview_output.clear()

        if hasattr(self, "transcript_summary"):
            self.transcript_summary.setPlainText("Transcription will appear here...")
        if hasattr(self, "transcript_segments"):
            self.transcript_segments.clear()
        if hasattr(self, "search_results"):
            self.search_results.clear()

        if hasattr(self, "segment_editor"):
            self.segment_editor.blockSignals(True)
            try:
                self.segment_editor.clear()
            finally:
                self.segment_editor.blockSignals(False)
            self.segment_editor.setEnabled(False)

        if hasattr(self, "artifact_selector"):
            self.artifact_selector.blockSignals(True)
            try:
                self.artifact_selector.clear()
            finally:
                self.artifact_selector.blockSignals(False)
        if hasattr(self, "artifact_viewer"):
            self.artifact_viewer.clear()
        if hasattr(self, "artifact_markdown_viewer"):
            self.artifact_markdown_viewer.clear()

        if hasattr(self, "media_position_slider"):
            self.media_position_slider.setValue(0)
            self.media_position_slider.setRange(0, 0)
            if disable_controls:
                self.media_position_slider.setEnabled(False)
        if disable_controls and hasattr(self, "open_media_button"):
            self.open_media_button.setEnabled(False)
        if disable_controls and hasattr(self, "play_media_button"):
            self.play_media_button.setEnabled(False)
        if disable_controls and hasattr(self, "search_button"):
            self.search_button.setEnabled(False)
        if hasattr(self, "search_input"):
            if disable_controls:
                self.search_input.setEnabled(False)
            self.search_input.clear()

        if hasattr(self, "media_binding_label"):
            self.media_binding_label.setText("Binding: Unbound")
        if hasattr(self, "media_status_label"):
            self.media_status_label.setText("Open a transcript JSON file to bind media.")
        if hasattr(self, "transcript_edit_status_label"):
            self.transcript_edit_status_label.setText("No transcript loaded for editing.")
        if hasattr(self, "artifact_format_label"):
            self.artifact_format_label.setText("No artifact selected")
        self._set_workspace_status("Open a transcript or artifact to inspect generated files here.")
        self._refresh_edit_controls()
        self._refresh_workspace_artifact_buttons()

    def _prepare_for_transcript_switch(self, target_path: Path) -> bool:
        if self._transcript_path is None or self._transcript_path == target_path:
            return True
        if not self._transcript_edit_dirty:
            return True

        prompt = QMessageBox(self)
        prompt.setWindowTitle("Unsaved transcript edits")
        prompt.setText("The current transcript has unsaved edits.")
        prompt.setInformativeText("Save changes before switching transcripts?")
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

    def _refresh_edit_controls(self) -> None:
        has_document = self._editable_transcript is not None
        has_selection = has_document and 0 <= self._current_segment_index < len(
            self._editable_transcript.segments
        )
        if hasattr(self, "segment_editor"):
            self.segment_editor.setEnabled(bool(has_selection))
        if hasattr(self, "segment_revert_button"):
            self.segment_revert_button.setEnabled(bool(has_selection))
        if hasattr(self, "save_transcript_button"):
            self.save_transcript_button.setEnabled(bool(has_document and self._transcript_edit_dirty))
        if hasattr(self, "save_transcript_copy_button"):
            self.save_transcript_copy_button.setEnabled(bool(has_document))
        if hasattr(self, "reexport_transcript_button"):
            self.reexport_transcript_button.setEnabled(bool(has_document))

    def _set_workspace_status(self, message: str) -> None:
        if hasattr(self, "artifact_status_label"):
            self.artifact_status_label.setText(message)
