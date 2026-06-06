"""Queue control methods mixin for MainWindow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QFileSystemWatcher, Qt

from flowscribe.tasks.models import SourceSpec
from flowscribe.gui.gui_logging import get_gui_logger
from flowscribe.tasks.queue_models import (
    QueueItem,
    QueueItemSettings,
    apply_source_edit_options,
    generate_queue_item_id,
)
from flowscribe.tasks.queue_importers import (
    deduplicate_sources,
    import_urls_from_file,
    parse_urls_from_text,
)
from flowscribe.gui.workers.queue_runner import QueueRunner

LOGGER = get_gui_logger(__name__)


class QueueControlsMixin:
    """Mixin providing batch queue control methods for MainWindow.

    Requires the following attributes from MainWindow:
    - file_list: SourceListWidget
    - language_combo, preset_combo, model_combo: QComboBox
    - format_checks: dict[str, QCheckBox]
    - output_dir_input: QLineEdit
    - timestamps_check, word_timestamps_check, overwrite_check: QCheckBox
    - network_combo, proxy_input, cookies_input: QComboBox/QLineEdit
    - status_label: QLabel
    - _queue_store: BatchQueueStore
    - _queue_tab: QueueTabWidget | None
    - _queue_thread: QThread | None
    - _queue_runner: QueueRunner | None
    - _queue_file_watcher: QFileSystemWatcher | None
    - _notification_player: QueueNotificationPlayer
    - _thread: QThread | None (for single transcription)
    """

    def _check_newly_added_sources(self, paths) -> None:
        added = {str(Path(path)) for path in paths}
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item is not None and item.text() in added:
                item.setCheckState(Qt.CheckState.Checked)

    def _current_queue_item_settings(self) -> QueueItemSettings:
        language_text = self.language_combo.currentText().strip()
        language = None if language_text == "auto" else (language_text or None)
        preset_text = self.preset_combo.currentText().strip()
        preset = None if preset_text == "none" else (preset_text or None)

        output_formats = tuple(
            fmt
            for fmt, checkbox in self.format_checks.items()
            if checkbox.isChecked()
        )
        # Default to JSON if no formats selected
        if not output_formats:
            output_formats = ("json",)

        return QueueItemSettings(
            output_dir=Path(self.output_dir_input.text().strip() or "outputs"),
            provider_name=(
                self.provider_combo.currentData()
                if hasattr(self, "provider_combo")
                else "local-whisper"
            ) or "local-whisper",
            model_name=self.model_combo.currentText().strip() or "small",
            language=language,
            preset=preset,
            output_formats=output_formats,
            timestamps=self.timestamps_check.isChecked(),
            word_timestamps=self.word_timestamps_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            network_family=self.network_combo.currentData() or "auto",
            proxy=self.proxy_input.text().strip() or None,
            cookies_path=Path(self.cookies_input.text().strip())
            if self.cookies_input.text().strip()
            else None,
            progressive_enabled=self.progressive_enabled_check.isChecked(),
            progressive_resume=self.progressive_resume_check.isChecked(),
            native_threads=(
                self.native_threads_spin.value()
                if hasattr(self, "native_threads_spin")
                and self.native_threads_spin.value() > 0
                else None
            ),
        )

    def _enqueue_urls_from_text(self, text: str) -> None:
        urls = parse_urls_from_text(text)
        if not urls:
            self.status_label.setText("No valid URLs found. URLs must start with http:// or https://")
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
        settings = self._current_queue_item_settings()
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
        output_dir = self.output_dir_input.text().strip() or "outputs"
        settings = self._current_queue_item_settings()
        self._queue_tab.set_output_dir_display(output_dir, settings.output_formats)

    def _setup_queue_file_watcher(self) -> None:
        """Setup file watcher to detect external queue changes (e.g., from Bookmarklet server)."""
        queue_path = self._queue_store._path
        if not queue_path.parent.exists():
            queue_path.parent.mkdir(parents=True, exist_ok=True)

        self._queue_file_watcher = QFileSystemWatcher()

        # Watch both the file and its parent directory
        # (watching directory helps detect file creation)
        if queue_path.exists():
            self._queue_file_watcher.addPath(str(queue_path))
        self._queue_file_watcher.addPath(str(queue_path.parent))

        # Connect to refresh handler
        self._queue_file_watcher.fileChanged.connect(self._on_queue_file_changed)
        self._queue_file_watcher.directoryChanged.connect(self._on_queue_directory_changed)

    def _on_queue_file_changed(self, path: str) -> None:
        """Handle queue file changes from external sources."""
        # Re-add the file to watcher (Qt removes it after change)
        queue_path = self._queue_store._path
        if queue_path.exists() and str(queue_path) not in self._queue_file_watcher.files():
            self._queue_file_watcher.addPath(str(queue_path))

        # Refresh queue display
        self._refresh_queue_tab()

    def _on_queue_directory_changed(self, path: str) -> None:
        """Handle queue directory changes (file creation)."""
        queue_path = self._queue_store._path
        if queue_path.exists() and str(queue_path) not in self._queue_file_watcher.files():
            self._queue_file_watcher.addPath(str(queue_path))
            self._refresh_queue_tab()

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
        item, result = payload
        self._index_queue_result_in_library(item, result)
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

    def _edit_queue_item_settings(self, item_ids: list[str]) -> None:
        """Open dialog to edit queue item settings (supports batch editing)."""
        if not item_ids:
            self.status_label.setText("No items selected")
            return

        # Get first item as template
        first_item = self._queue_store.get_item(item_ids[0])
        if not first_item:
            self.status_label.setText("Item not found")
            return

        from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog

        # Determine label for dialog
        is_batch = len(item_ids) > 1
        if is_batch:
            item_label = f"{len(item_ids)} items"
        else:
            item_label = first_item.display_label

        # Show dialog with first item's settings as template
        dialog = QueueItemSettingsDialog(
            self, first_item.settings, first_item.source, item_label, is_batch=is_batch
        )
        dialog.exec()

        result = dialog.get_settings()
        if result is not None:
            new_settings, new_source = result
            # Apply to all selected items
            for item_id in item_ids:
                current_item = self._queue_store.get_item(item_id)
                if current_item is None:
                    continue
                self._queue_store.update_item(
                    item_id,
                    settings=new_settings,
                    source=apply_source_edit_options(current_item.source, new_source),
                )
            self._refresh_queue_tab()
            if is_batch:
                self.status_label.setText(f"Updated settings for {len(item_ids)} items")
            else:
                self.status_label.setText(f"Updated settings for: {first_item.display_label}")

    def _remove_queue_items(self, item_ids: list[str]) -> None:
        """Remove multiple queue items."""
        if not item_ids:
            return

        from PySide6.QtWidgets import QMessageBox

        count = len(item_ids)
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove {count} item(s) from queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            removed = self._queue_store.remove_items(item_ids)
            self._refresh_queue_tab()
            self.status_label.setText(f"Removed {removed} item(s) from queue.")

    def _clear_completed_queue_items(self) -> None:
        removed = self._queue_store.remove_completed()
        self.status_label.setText(f"Cleared {removed} completed item(s) from queue.")
        self._refresh_queue_tab()

    def _reorder_queue_items(self, item_ids: list[str]) -> None:
        self._queue_store.reorder(item_ids)
