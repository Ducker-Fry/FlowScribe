from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidgetItem

from flowscribe.core.errors import SearchError
from flowscribe.gui.transcript_viewer import search_transcript_view
from flowscribe.gui.utils.formatting import (
    _progress_event_status_line,
    _render_progress_segment_line,
)
from flowscribe.tasks.models import ProgressEvent
from flowscribe.transcript.editing import (
    render_editable_segment_line,
    save_editable_transcript,
    update_editable_transcript_segment,
)
from flowscribe.transcript.reexport import reexport_transcript_json


class TranscriptionViewDialogEditingMixin:
    """Transcript search, editing, and progressive update helpers."""

    def _run_transcript_search(self) -> None:
        if self._transcript_path is None or self._transcript_view is None:
            self.search_results.clear()
            self.search_results.addItem("Open a transcript JSON file before searching.")
            return

        query = self.search_input.text().strip()
        if not query:
            self.search_results.clear()
            self._search_hits = ()
            return

        try:
            hits = search_transcript_view(self._transcript_path, self._transcript_view, query)
        except SearchError as exc:
            self.search_results.clear()
            self.search_results.addItem(f"Search error: {exc}")
            self._search_hits = ()
            return

        self._search_hits = hits
        self.search_results.clear()
        if not hits:
            self.search_results.addItem(f'No matches found for "{query}".')
            return

        for hit in hits:
            start_time = f"{hit.start_seconds:.1f}s" if hit.start_seconds is not None else "?s"
            self.search_results.addItem(f"[{start_time}] {hit.matched_text}")
        self.search_results.setCurrentRow(0)

    def _jump_to_selected_hit(self) -> None:
        row = self.search_results.currentRow()
        if row < 0 or row >= len(self._search_hits):
            return
        hit = self._search_hits[row]
        if self._transcript_view is None or hit.segment_index >= len(self._transcript_view.segments):
            return

        self.transcript_segments.setCurrentRow(hit.segment_index)
        self._activate_selected_segment()
        self._seek_to_search_hit(row)

    def _activate_selected_segment(self) -> None:
        row = self.transcript_segments.currentRow()
        if row < 0 or not self._editable_transcript:
            return
        if row >= len(self._editable_transcript.segments):
            return

        segment = self._editable_transcript.segments[row]
        self._current_segment_index = row
        self._active_segment_row = row

        self.segment_editor.blockSignals(True)
        try:
            self.segment_editor.setPlainText(segment.text)
        finally:
            self.segment_editor.blockSignals(False)

        self._seek_to_segment(row)
        self._segment_modified = segment.edited
        self._transcript_edit_dirty = self._editable_transcript.dirty
        self._refresh_edit_controls()

        start_str = f"{segment.start_seconds:.2f}" if segment.start_seconds is not None else "?"
        end_str = f"{segment.end_seconds:.2f}" if segment.end_seconds is not None else "?"
        self.transcript_edit_status_label.setText(
            f"Editing segment {row + 1} of {len(self._editable_transcript.segments)} | "
            f"[{start_str}s - {end_str}s]"
        )

    def update_run_output(self, output: str) -> None:
        self.preview_output.setPlainText(output)

    def append_progress_segments(self, event: ProgressEvent) -> None:
        if not event.segments:
            return

        current_chunk = event.chunk_index or 0
        if current_chunk != self._last_chunk_index and self._last_chunk_index > 0:
            separator = QListWidgetItem("-" * 30)
            separator.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.transcript_segments.addItem(separator)

        if event.chunk_index is not None and event.chunk_count is not None:
            header = QListWidgetItem(f"Chunk {event.chunk_index}/{event.chunk_count}")
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            self.transcript_segments.addItem(header)

        self._last_chunk_index = current_chunk

        for segment in event.segments:
            self.transcript_segments.addItem(_render_progress_segment_line(segment))

        status_line = _progress_event_status_line(event)
        if status_line:
            self.transcript_summary.setPlainText(
                event.message + "\n\n" + status_line if event.message else status_line
            )
            self.transcript_edit_status_label.setText(status_line)

        self.segment_revert_button.setEnabled(True)
        self.save_transcript_button.setEnabled(True)
        self.save_transcript_copy_button.setEnabled(True)
        self.reexport_transcript_button.setEnabled(True)

    def _on_segment_editor_text_changed(self) -> None:
        if self._editable_transcript is None:
            return

        segments = getattr(self._editable_transcript, "segments", None)
        if segments is None:
            return
        try:
            segment_count = len(segments)
        except TypeError:
            return

        row = self._current_segment_index
        if row < 0 or row >= segment_count:
            return

        updated = update_editable_transcript_segment(
            self._editable_transcript,
            row,
            self.segment_editor.toPlainText(),
        )
        if updated == self._editable_transcript:
            return

        self._editable_transcript = updated
        self._segment_modified = True
        self._transcript_edit_dirty = updated.dirty
        item = self.transcript_segments.item(row)
        if item is not None:
            item.setText(render_editable_segment_line(updated.segments[row]))
        self._refresh_edit_controls()

    def _revert_selected_segment_edit(self) -> None:
        if not self._editable_transcript:
            return

        row = self._current_segment_index
        if row < 0 or row >= len(self._editable_transcript.segments):
            return

        segment = self._editable_transcript.segments[row]
        updated = update_editable_transcript_segment(
            self._editable_transcript,
            row,
            segment.original_text,
        )
        self._editable_transcript = updated
        self._segment_modified = False
        self._transcript_edit_dirty = updated.dirty
        self.segment_editor.blockSignals(True)
        try:
            self.segment_editor.setPlainText(updated.segments[row].text)
        finally:
            self.segment_editor.blockSignals(False)
        item = self.transcript_segments.item(row)
        if item is not None:
            item.setText(render_editable_segment_line(updated.segments[row]))
        self.transcript_edit_status_label.setText("Segment reverted to original text")
        self._refresh_edit_controls()

    def _save_transcript_edits(self, force_save_as: bool = False) -> bool:
        if not self._editable_transcript or not self._transcript_path:
            return False

        target_path = self._transcript_path
        if force_save_as:
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Transcript As",
                str(self._transcript_path.with_stem(self._transcript_path.stem + "_edited")),
                "JSON files (*.json)",
            )
            if not save_path:
                return False
            target_path = Path(save_path)

        try:
            saved_path = save_editable_transcript(self._editable_transcript, destination=target_path)
            self._transcript_edit_dirty = False
            self._segment_modified = False
            self._load_transcript_with_artifacts(saved_path, self._workspace_artifact_paths)
            self.transcript_edit_status_label.setText(
                f"Saved transcript: {saved_path.name}"
                if not force_save_as
                else f"Saved as: {saved_path.name}"
            )
            return True
        except Exception as exc:
            self.transcript_edit_status_label.setText(f"Error saving transcript: {exc}")
            return False

    def _reexport_current_transcript(self) -> None:
        if not self._transcript_path:
            return

        try:
            output_paths = reexport_transcript_json(self._transcript_path)
            self.transcript_edit_status_label.setText(
                f"Re-exported {len(output_paths)} files successfully"
            )
            artifact_paths = tuple(dict.fromkeys(self._workspace_artifact_paths + tuple(output_paths)))
            self._load_artifacts(artifact_paths)
        except Exception as exc:
            self.transcript_edit_status_label.setText(f"Error re-exporting: {exc}")
