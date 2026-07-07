from __future__ import annotations

from flowscribe.tasks.models import ProgressEvent


class QueueViewRuntimeMixin:
    """Running-item presenter and server state helpers for the queue view."""

    def set_server_status(self, running: bool, port: int | None = None) -> None:
        if running and port:
            self._server_status_label.setText(f"Server: Running on port {port}")
            self._server_status_label.setStyleSheet("color: green;")
            self._server_enabled_check.setChecked(True)
            self._set_status_message(f"Bookmarklet server running on port {port}")
            return

        self._server_status_label.setText("Server: Stopped")
        self._server_status_label.setStyleSheet("color: gray;")
        self._server_enabled_check.setChecked(False)
        self._set_status_message("Bookmarklet server stopped")

    def set_queue_running(self, running: bool) -> None:
        if not running:
            self._current_running_item_id = None
        self._update_button_states()

    def on_item_started(self, item) -> None:
        self._current_running_item_id = item.item_id
        self._current_run_output = ""
        self._set_status_message(f"Processing: {item.display_label}")
        self._update_button_states()

    def on_item_progress(self, event) -> None:
        if isinstance(event, ProgressEvent) and event.message:
            self._current_run_output += event.message + "\n"
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.update_run_output(self._current_run_output)

        if isinstance(event, ProgressEvent) and event.segments:
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.append_progress_segments(event)

    def on_item_completed(self, data: tuple) -> None:
        self._current_running_item_id = None
        self._current_run_output = ""
        self._update_button_states()

    def on_item_failed(self, data: tuple) -> None:
        self._current_running_item_id = None
        self._current_run_output = ""
        self._update_button_states()

    def on_item_canceled(self, item) -> None:
        self._current_running_item_id = None
        self._current_run_output = ""
        self._update_button_states()
