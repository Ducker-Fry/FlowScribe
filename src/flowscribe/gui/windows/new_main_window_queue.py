from __future__ import annotations

from pathlib import Path

from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog
from flowscribe.gui.remote_targets import validate_remote_execution_settings
from flowscribe.gui.services.queue_service import build_local_queue_items, build_url_queue_items
from flowscribe.gui.services.runtime_service import start_queue_runtime
from flowscribe.tasks.queue_importers import import_urls_from_file, parse_urls_from_text
from flowscribe.tasks.queue_models import QueueItemSettings, apply_source_edit_options


class NewMainWindowQueueMixin:
    """Queue orchestration helpers for the stacked main window."""

    def _on_enqueue_urls(self, text: str) -> None:
        try:
            urls = parse_urls_from_text(text)
            if not urls:
                self.statusBar().showMessage("No valid URLs found in input")
                return

            settings = self._settings_to_queue_settings()
            items = build_url_queue_items(
                urls,
                settings=settings,
                download_options=self._queue_view.get_download_options(),
            )
            for item in items:
                self._queue_store.enqueue(item)
            self._refresh_queue_view()
            self.statusBar().showMessage(f"Added {len(items)} URL(s) to queue")
        except Exception as exc:
            self.statusBar().showMessage(f"Error adding URLs: {exc}")

    def _on_enqueue_files(self, paths: list[Path]) -> None:
        try:
            settings = self._settings_to_queue_settings()
            items = build_local_queue_items(paths, settings=settings)
            for item in items:
                self._queue_store.enqueue(item)
            self._refresh_queue_view()
            self.statusBar().showMessage(f"Added {len(items)} file(s) to queue")
        except Exception as exc:
            self.statusBar().showMessage(f"Error adding files: {exc}")

    def _on_import_file(self, file_path: str) -> None:
        try:
            urls = import_urls_from_file(Path(file_path))
            settings = self._settings_to_queue_settings()
            items = build_url_queue_items(
                urls,
                settings=settings,
                download_options=self._queue_view.get_download_options(),
            )
            for item in items:
                self._queue_store.enqueue(item)
            self._refresh_queue_view()
            self.statusBar().showMessage(f"Imported {len(items)} URL(s) from file")
        except Exception as exc:
            self.statusBar().showMessage(f"Import failed: {exc}")

    def _on_start_queue(self) -> None:
        if self._queue_thread is not None:
            self.statusBar().showMessage("Queue is already running")
            return
        validation_error = self._validate_pending_queue_items()
        if validation_error:
            self.statusBar().showMessage(validation_error)
            return

        self._queue_thread, self._queue_runner = start_queue_runtime(
            self,
            self._queue_store,
            self._on_queue_item_started,
            self._on_queue_item_progress,
            self._on_queue_item_completed,
            self._on_queue_item_failed,
            self._on_queue_item_canceled,
            self._on_queue_finished,
        )
        self._queue_view.set_queue_running(True)
        self.statusBar().showMessage("Queue processing started")

    def _on_cancel_queue(self) -> None:
        if self._queue_runner:
            self._queue_runner.request_cancel_all()
        self.statusBar().showMessage("Queue cancellation requested")

    def _on_skip_current(self) -> None:
        if self._queue_runner:
            self._queue_runner.request_skip_current()
        self.statusBar().showMessage("Skip requested")

    def _on_retry_item(self, item_id: str) -> None:
        self._queue_store.update_item(item_id, status="pending", started_at=None, error_message=None)
        self._refresh_queue_view()
        self.statusBar().showMessage("Item marked for retry")

    def _on_remove_items(self, item_ids: list[str]) -> None:
        for item_id in item_ids:
            self._queue_store.remove_item(item_id)
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Removed {len(item_ids)} item(s)")

    def _on_clear_completed(self) -> None:
        removed = self._queue_store.remove_completed()
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Cleared {removed} completed item(s)")

    def _on_reorder_queue(self, item_ids: list[str]) -> None:
        self._queue_store.reorder_items(item_ids)
        self._refresh_queue_view()

    def _on_edit_item_settings(self, item_ids: list[str]) -> None:
        if not item_ids:
            self.statusBar().showMessage("No items selected")
            return

        first_item = self._queue_store.get_item(item_ids[0])
        if first_item is None:
            self.statusBar().showMessage("Item not found")
            return

        is_batch = len(item_ids) > 1
        item_label = f"{len(item_ids)} items" if is_batch else first_item.display_label
        dialog = QueueItemSettingsDialog(
            self,
            first_item.settings,
            first_item.source,
            item_label,
            is_batch=is_batch,
        )
        if not dialog.exec():
            return

        result = dialog.get_settings()
        if result is None:
            return
        updated_settings, updated_source = result
        for item_id in item_ids:
            current_item = self._queue_store.get_item(item_id)
            if current_item is None:
                continue
            self._queue_store.update_item(
                item_id,
                settings=updated_settings,
                source=apply_source_edit_options(current_item.source, updated_source),
            )
        self._refresh_queue_view()
        if is_batch:
            self.statusBar().showMessage(f"Updated settings for {len(item_ids)} items")
        else:
            self.statusBar().showMessage("Item settings updated")

    def _on_queue_finished(self) -> None:
        self._queue_thread = None
        self._queue_runner = None
        self._queue_view.set_queue_running(False)
        self._refresh_queue_view()
        self._library_view.refresh_library()
        self.statusBar().showMessage("Queue processing finished")

    def _on_queue_item_started(self, item) -> None:
        self._queue_view.on_item_started(item)
        self._refresh_queue_view()

    def _on_queue_item_progress(self, event) -> None:
        self._queue_view.on_item_progress(event)

    def _on_queue_item_completed(self, data: tuple) -> None:
        item, result = data
        if result.outputs:
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    if path.suffix.lower() == ".json":
                        self._add_transcript_to_library_with_label(
                            path,
                            item.title or item.display_label,
                            artifacts,
                            result.job.output_dir,
                        )
        self._queue_view.on_item_completed(data)
        self._refresh_queue_view()
        self._library_view.refresh_library()

    def _on_queue_item_failed(self, data: tuple) -> None:
        self._queue_view.on_item_failed(data)
        self._refresh_queue_view()

    def _on_queue_item_canceled(self, item) -> None:
        self._queue_view.on_item_canceled(item)
        self._refresh_queue_view()

    def _refresh_queue_view(self) -> None:
        self._queue_view.refresh_queue(self._queue_store.load_items())

    def _settings_to_queue_settings(self) -> QueueItemSettings:
        remote_settings = {
            "execution_mode": self._settings.get("execution_mode", "local"),
            "server_target": self._settings.get("server_target"),
            "remote_token": self._settings.get("remote_token"),
            "remote_poll_seconds": float(self._settings.get("remote_poll_seconds", 1.0)),
            "download_artifacts": self._settings.get("download_artifacts", True),
        }
        validation_error = validate_remote_execution_settings(remote_settings)
        if validation_error is not None:
            raise ValueError(validation_error)
        return QueueItemSettings(
            output_dir=Path(self._settings["output_dir"]),
            output_name_base=self._settings.get("output_name_base", ""),
            **remote_settings,
            provider_name=self._settings.get("provider_name", "local-whisper"),
            model_name=self._settings["model_name"],
            language=self._settings["language"],
            preset=self._settings["preset"],
            output_formats=self._settings["output_formats"],
            timestamps=self._settings["timestamps"],
            word_timestamps=self._settings["word_timestamps"],
            overwrite=self._settings["overwrite"],
            network_family=self._settings["network_family"],
            proxy=self._settings["proxy"],
            cookies_path=self._settings["cookies_path"],
            progressive_enabled=self._settings["progressive_enabled"],
            progressive_resume=self._settings["progressive_resume"],
            progressive_chunk_seconds=self._settings["progressive_chunk_seconds"],
            progressive_max_workers=self._settings["progressive_max_workers"],
            native_threads=self._settings.get("native_threads"),
        )

    def _validate_pending_queue_items(self) -> str | None:
        for item in self._queue_store.load_items():
            if item.status != "pending":
                continue
            validation_error = validate_remote_execution_settings(
                {
                    "execution_mode": item.settings.execution_mode,
                    "server_target": item.settings.server_target,
                }
            )
            if validation_error is not None:
                return f"Queue item '{item.display_label}' has invalid remote settings: {validation_error}"
        return None
