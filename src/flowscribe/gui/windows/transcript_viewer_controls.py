"""Transcript viewer and media playback controls mixin for MainWindow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from flowscribe.core.errors import OutputError, SearchError
from flowscribe.gui.transcript_viewer import (
    TranscriptSearchHitView,
    TranscriptView,
    load_transcript_view,
    render_transcript_summary,
    resolve_transcript_media_path,
    search_transcript_view,
    transcript_media_binding_warning,
    transcript_search_hit_seek_seconds,
    transcript_segment_index_for_seconds,
    transcript_segment_seek_seconds,
)
from flowscribe.gui.utils import (
    _discover_transcript_output_paths,
    _is_viewable_artifact_path,
)
from flowscribe.input.file_filter import is_supported_media
from flowscribe.output.time_format import format_timestamp
from flowscribe.transcript.editing import (
    EditableTranscriptDocument,
    load_editable_transcript,
    render_editable_segment_line,
    save_editable_transcript,
    suggested_corrected_transcript_path,
    update_editable_transcript_segment,
)
from flowscribe.transcript.reexport import reexport_transcript_json


class TranscriptViewerControlsMixin:
    """Mixin providing transcript viewer, search, editing, and media playback controls."""

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

    def _bind_media_to_transcript(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        if self._transcript_view is None:
            self.media_status_label.setText("Open a transcript JSON file before binding media.")
            return

        path, _ = QFileDialog.getOpenFileName(self, "Bind media to transcript")
        if not path:
            return
        self._bind_media_path(Path(path))

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
