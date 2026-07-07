from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFileDialog, QWidget


class QueueViewControlsMixin:
    """Enqueue, import, server, and action button handlers for the queue view."""

    def _on_add_local_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Local Files to Queue",
            "",
            "Media files (*.mp3 *.mp4 *.wav *.m4a *.flac *.ogg *.webm);;All files (*.*)",
        )
        if not paths:
            return
        file_paths = [Path(path) for path in paths]
        self.enqueue_files_requested.emit(file_paths)
        self._set_status_message(f"Added {len(file_paths)} local file(s) to queue")

    def _on_add_urls(self) -> None:
        text = self._url_input.toPlainText().strip()
        if not text:
            self._set_status_message("Please enter at least one URL")
            return
        self.enqueue_urls_requested.emit(text)
        self._url_input.clear()
        self._set_status_message("Processing URLs...")

    def eventFilter(self, watched, event) -> bool:
        if watched is self._url_input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self._on_add_urls()
                    return True
        return QWidget.eventFilter(self, watched, event)

    def get_download_options(self) -> dict:
        quality_map = {"Best": "best", "High": "high", "Medium": "medium", "Low": "low"}
        prefer_format = (
            None if self._download_format_combo.currentText() == "Auto" else self._download_format_combo.currentText()
        )
        media_kind = "video" if self._media_type_combo.currentText() == "Video" else "audio"
        return {
            "quality": quality_map.get(self._download_quality_combo.currentText(), "best"),
            "prefer_format": prefer_format,
            "preserve_media": self._preserve_media_check.isChecked(),
            "media_kind": media_kind,
        }

    def _on_import_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import URLs from File",
            "",
            "Text files (*.txt);;CSV files (*.csv);;Excel files (*.xlsx);;All files (*.*)",
        )
        if not file_path:
            return
        self.import_file_requested.emit(file_path)
        self._set_status_message(f"Importing queue sources from: {Path(file_path).name}")

    def _on_server_toggle(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            self.server_start_requested.emit(self._server_port_spin.value())
            return
        self.server_stop_requested.emit()

    def _on_start_queue(self) -> None:
        self.start_queue_requested.emit()
        self._set_status_message("Queue started")
        self._update_button_states()

    def _on_cancel_queue(self) -> None:
        self.cancel_queue_requested.emit()
        self._set_status_message("Queue cancel requested")

    def _on_skip_current(self) -> None:
        self.skip_current_requested.emit()
        self._set_status_message("Skipping current queue item...")

    def _on_edit_settings(self) -> None:
        selected = self._get_selected_item_ids()
        if selected:
            self.edit_item_settings_requested.emit(selected)

    def _on_retry_failed(self) -> None:
        selected = self._get_selected_item_ids()
        retryable = [
            item_id
            for item_id in selected
            if (item := self._items_cache.get(item_id)) and item.status in {"failed", "canceled"}
        ]
        if retryable:
            self.retry_item_requested.emit(retryable[0])

    def _on_remove_selected(self) -> None:
        selected = self._get_selected_item_ids()
        if selected:
            self.remove_items_requested.emit(selected)

    def _on_retry_single_item(self, item_id: str) -> None:
        self.retry_item_requested.emit(item_id)

    def _on_remove_single_item(self, item_id: str) -> None:
        self.remove_items_requested.emit([item_id])

    def _on_clear_completed(self) -> None:
        self.clear_completed_requested.emit()

    def _on_select_all(self) -> None:
        self._checked_item_ids = set(self._item_ids)
        self._sync_all_card_check_states()
        self._update_button_states()

    def _set_status_message(self, message: str) -> None:
        self._status_label.setText(message)
