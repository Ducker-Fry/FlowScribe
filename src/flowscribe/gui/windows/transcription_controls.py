"""Transcription control methods for MainWindow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QListWidgetItem

from flowscribe.app.models import ProgressEvent
from flowscribe.gui.state import GuiTranscriptionForm
from flowscribe.gui.utils import (
    _format_elapsed_time,
    _progress_event_status_line,
    _render_progress_segment_line,
    _url_media_status_suffix,
)
from flowscribe.gui.workers.transcription_worker import TranscriptionWorker

if TYPE_CHECKING:
    from typing import Any


class TranscriptionControlsMixin:
    """Mixin providing transcription start/stop/progress methods."""

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

    def _finish_transcription(self, result: Any) -> None:
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
        elapsed_str = _format_elapsed_time(result.elapsed_seconds)
        time_suffix = f" Time: {elapsed_str}." if elapsed_str else ""
        self.status_label.setText(f"Done. Succeeded: {result.succeeded}.{time_suffix}")
        self.preview_output.append(f"\nDone. Succeeded: {result.succeeded}. Failed: {result.failed}.{time_suffix}")
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
            elapsed_str = _format_elapsed_time(result.elapsed_seconds)
            time_suffix = f" Time: {elapsed_str}." if elapsed_str else ""
            if auto_bound_media and self._media_path is not None:
                status = (
                    f"Done. Succeeded: {result.succeeded}. "
                    f"Auto-bound saved media: {self._media_path.name}.{time_suffix}"
                )
                if url_media_notes:
                    status += " " + " ".join(url_media_notes)
                self.status_label.setText(status)
            elif url_media_notes:
                self.status_label.setText(
                    f"Done. Succeeded: {result.succeeded}.{time_suffix} " + " ".join(url_media_notes)
                )
            else:
                self.status_label.setText(f"Done. Succeeded: {result.succeeded}.{time_suffix}")
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
