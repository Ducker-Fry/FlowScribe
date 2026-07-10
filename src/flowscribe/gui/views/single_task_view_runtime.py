from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QInputDialog

from flowscribe.core.errors import FlowScribeError
from flowscribe.execution.factory import build_execution_backend
from flowscribe.gui.workers.transcription_worker import TranscriptionWorker
from flowscribe.tasks.models import DownloadOptions, ProgressEvent, SourceSpec, TranscriptionJob


class SingleTaskViewRuntimeMixin:
    """Runtime orchestration and state refresh helpers for the single-task view."""

    def _start_transcription(self) -> None:
        if self._thread is not None:
            self.status_label.setText("A transcription job is already running.")
            return
        if self._is_capture_running():
            self.status_label.setText("Stop system audio capture before starting transcription.")
            return

        selected_paths = self._get_checked_paths()
        url = self.url_input.text().strip()
        if not selected_paths and not url:
            self.status_label.setText("Please select local files or enter a URL.")
            return

        job = self._build_job(selected_paths, url)
        if job is None:
            return

        self._last_transcript_path = None
        self._last_output_paths = []
        if self._view_dialog is not None:
            self._view_dialog.clear_content()

        self._current_output_dir = job.output_dir
        self._progress_event_count = 0
        self._transcription_start_time = time.time()
        self._current_run_output = ""
        self._cancel_requested = False
        self._last_remote_task_id = None

        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 0)
        self.preview_output.clear()
        self.preview_output.appendPlainText("Starting transcription...\n")
        self.status_label.setText("Transcription in progress...")

        execution_mode = str(self._settings.get("execution_mode") or "local")
        server_target = self._settings.get("server_target")
        try:
            execution_backend = build_execution_backend(
                execution_mode=execution_mode,
                server_target=server_target,
                remote_token=self._settings.get("remote_token"),
                remote_poll_seconds=float(self._settings.get("remote_poll_seconds", 1.0)),
                download_artifacts=self._settings.get("download_artifacts"),
            )
        except FlowScribeError as exc:
            message = str(exc)
            self.status_label.setText(f"Transcription failed: {message}")
            self.preview_output.appendPlainText(f"\nFailed: {message}")
            self.transcription_error.emit(message)
            self._refresh_action_buttons()
            return

        self._thread = QThread(self)
        self._worker = TranscriptionWorker(
            job,
            execution_backend=execution_backend,
            execution_mode=execution_mode,
            server_target=server_target if execution_mode == "remote" else None,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.warning.connect(self._on_warning)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

        self._refresh_action_buttons()
        self.transcription_started.emit()

    def _build_job(self, selected_paths: list[Path], url: str) -> TranscriptionJob | None:
        output_dir = Path(self._settings.get("output_dir", "outputs"))
        output_name_base = self._settings.get("output_name_base", "")
        provider_name = self._settings.get("provider_name", "local-whisper")
        model_name = self._settings.get("model_name", "small")
        language = self._settings.get("language")
        preset = self._settings.get("preset")
        output_formats = self._settings.get("output_formats", ("json",))
        timestamps = self._settings.get("timestamps", True)
        word_timestamps = self._settings.get("word_timestamps", False)
        overwrite = self._settings.get("overwrite", False)
        network_family = self._settings.get("network_family", "auto")
        proxy = self._settings.get("proxy")
        cookies_path = self._settings.get("cookies_path")
        progressive_enabled = self._settings.get("progressive_enabled", True)
        progressive_resume = self._settings.get("progressive_resume", True)
        progressive_chunk_seconds = self._settings.get("progressive_chunk_seconds", 30.0)
        progressive_max_workers = self._settings.get("progressive_max_workers", 1)
        native_threads = self._settings.get("native_threads")

        sources = [SourceSpec(kind="local", value=str(path)) for path in selected_paths]
        if url:
            quality_map = {"Best": "best", "High": "high", "Medium": "medium", "Low": "low"}
            prefer_format = (
                None if self.url_format_combo.currentText() == "Auto" else self.url_format_combo.currentText()
            )
            sources.append(
                SourceSpec(
                    kind="url",
                    value=url,
                    keep_media=self.url_media_preserve_check.isChecked(),
                    url_media_kind=(
                        "video" if self.url_media_type_combo.currentText() == "Video" else "audio"
                    ),
                    download_options=DownloadOptions(
                        quality=quality_map.get(self.url_quality_combo.currentText(), "best"),
                        prefer_format=prefer_format,
                    ),
                    auto_bind_media=True,
                )
            )

        if not sources:
            self.status_label.setText("No sources selected.")
            return None

        return TranscriptionJob(
            sources=tuple(sources),
            output_dir=output_dir,
            output_name_base=output_name_base,
            provider_name=provider_name,
            model_name=model_name,
            language=language,
            preset=preset,
            output_formats=output_formats,
            timestamps=timestamps,
            word_timestamps=word_timestamps,
            overwrite=overwrite,
            network_family=network_family,
            proxy=proxy,
            cookies_path=cookies_path,
            progressive_enabled=progressive_enabled,
            progressive_resume=progressive_resume,
            progressive_chunk_seconds=progressive_chunk_seconds,
            progressive_max_workers=progressive_max_workers,
            native_threads=native_threads,
        )

    def _on_progress(self, event: ProgressEvent) -> None:
        if event.message:
            self.preview_output.appendPlainText(event.message)
            self._current_run_output += event.message + "\n"
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.update_run_output(self._current_run_output)
            if event.message.startswith("Remote task accepted: ") and event.task_id:
                self._last_remote_task_id = str(event.task_id)

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

        if event.stage == "transcribe" and event.message:
            self.status_label.setText(event.message)

        if event.segments and self._view_dialog is not None and self._view_dialog.isVisible():
            self._view_dialog.append_progress_segments(event)

        self._progress_event_count += 1
        if (
            self._last_transcript_path is None
            and self._current_output_dir is not None
            and self._progress_event_count % 3 == 0
        ):
            self._detect_progressive_cache()

    def _on_finished(self, result: Any) -> None:
        self._last_result = result
        self._worker = None
        self._thread = None
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0 if result.canceled else 1)

        elapsed_time_str = ""
        if result.elapsed_seconds is not None:
            elapsed = result.elapsed_seconds
            elapsed_time_str = f" (Time: {elapsed:.1f}s)" if elapsed < 60 else (
                f" (Time: {int(elapsed // 60)}m {int(elapsed % 60)}s)"
            )

        if result.canceled:
            self.status_label.setText(
                f"Canceled. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\nTranscription canceled by user.")
        elif result.errors:
            self.status_label.setText(
                f"Done with errors. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\n\nErrors occurred:")
            for error in result.errors:
                self.preview_output.appendPlainText(f"  - {error}")
        else:
            self.status_label.setText(
                f"Transcription complete! Succeeded: {result.succeeded}.{elapsed_time_str}"
            )
            self.preview_output.appendPlainText("\n\nTranscription completed successfully!")

        if result.elapsed_seconds is not None:
            self.preview_output.appendPlainText(f"\nElapsed time: {elapsed_time_str.strip(' ()')}")

        self._last_output_paths = []
        if result.outputs:
            self._last_output_dir = result.job.output_dir
            self.preview_output.appendPlainText("\nOutput files:")
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    self.preview_output.appendPlainText(f"  {path}")
                    self._last_output_paths.append(path)
                    if path.suffix.lower() == ".json" and self._last_transcript_path is None:
                        self._last_transcript_path = path

        self._refresh_action_buttons()
        self._sync_view_dialog_from_result()
        self.transcription_finished.emit(result)

    def _on_failed(self, error: str) -> None:
        self._worker = None
        self._thread = None
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Transcription failed: {error}")
        self.preview_output.appendPlainText(f"\n\nFailed: {error}")
        self._refresh_action_buttons()
        self.transcription_error.emit(error)

    def _on_warning(self, warning: str) -> None:
        self.preview_output.appendHtml(f'<span style="color: #FFA500;">Warning: {warning}</span>')

    def _clear_worker_refs(self) -> None:
        self._worker = None
        self._thread = None
        self._refresh_action_buttons()

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
        self.status_label.setText("Canceling transcription... (may take a few seconds)")
        self.preview_output.appendPlainText(
            "\n[Cancellation requested - stopping at next checkpoint...]"
        )
        self._refresh_action_buttons()

    def _request_settings(self) -> None:
        self.settings_requested.emit()

    def _recover_remote_result(self) -> None:
        if self._thread is not None:
            self.status_label.setText("Wait for the current task to finish before recovering a remote result.")
            return

        execution_mode = str(self._settings.get("execution_mode") or "local")
        server_target = self._settings.get("server_target")
        if execution_mode != "remote" or not server_target:
            self.status_label.setText("Remote result recovery requires remote execution with a saved server target.")
            return

        task_id, ok = QInputDialog.getText(
            self,
            "Recover Remote Result",
            "Enter remote task ID:",
            text=self._last_remote_task_id or "",
        )
        task_id = task_id.strip()
        if not ok or not task_id:
            self.status_label.setText("Remote result recovery canceled.")
            return

        try:
            backend = build_execution_backend(
                execution_mode="remote",
                server_target=server_target,
                remote_token=self._settings.get("remote_token"),
                remote_poll_seconds=float(self._settings.get("remote_poll_seconds", 1.0)),
                download_artifacts=True,
            )
            payload = backend.recover_task_result(
                task_id,
                Path(self._settings.get("output_dir", "outputs")),
                overwrite=True,
                progress=self._on_progress,
            )
        except (AttributeError, FlowScribeError) as exc:
            message = str(exc)
            self.status_label.setText(f"Remote recovery failed: {message}")
            self.preview_output.appendPlainText(f"\nRemote recovery failed: {message}")
            self.transcription_error.emit(message)
            return

        self._last_remote_task_id = task_id
        self._apply_recovered_remote_payload(payload, task_id=task_id)

    def _apply_recovered_remote_payload(self, payload: dict[str, Any], *, task_id: str) -> None:
        output_dir = Path(self._settings.get("output_dir", "outputs"))
        outputs = payload.get("outputs", [])
        if not isinstance(outputs, list):
            outputs = []

        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self._last_output_dir = output_dir
        self._last_output_paths = []
        self._last_transcript_path = None
        self.preview_output.appendPlainText(f"\nRecovered remote result for task {task_id}.")

        for output in outputs:
            if not isinstance(output, dict):
                continue
            for raw_path in output.get("paths", []):
                if not isinstance(raw_path, str) or not raw_path.strip():
                    continue
                path = Path(raw_path)
                self._last_output_paths.append(path)
                self.preview_output.appendPlainText(f"  {path}")
                if path.suffix.lower() == ".json" and self._last_transcript_path is None:
                    self._last_transcript_path = path

        self.status_label.setText(
            f"Remote result recovered for task {task_id}. Outputs: {len(self._last_output_paths)}"
        )
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        running = self._thread is not None
        capture_running = self._is_capture_running()
        has_transcript = self._last_transcript_path is not None
        remote_recovery_enabled = (
            not running and str(self._settings.get("execution_mode") or "local") == "remote"
        )

        self.start_button.setEnabled(not running and not capture_running)
        self.cancel_button.setEnabled(running and not self._cancel_requested)
        self.open_transcript_button.setEnabled(not running)
        self.recover_remote_result_button.setEnabled(remote_recovery_enabled)
        self.open_view_button.setEnabled(True)
        self.capture_start_button.setEnabled(not running and not capture_running)
        self.capture_stop_button.setEnabled(not running and capture_running)

        if running or has_transcript:
            return
        if self._has_selected_sources():
            self.status_label.setText(self.status_label.text() or "Ready")
