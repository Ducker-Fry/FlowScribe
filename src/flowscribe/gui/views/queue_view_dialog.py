from __future__ import annotations


class QueueViewDialogMixin:
    """Dialog bridge for queue item transcript viewing."""

    def _create_view_dialog(self) -> None:
        from flowscribe.gui.dialogs import TranscriptionViewDialog

        self._view_dialog = TranscriptionViewDialog(
            self,
            transcript_path=None,
            run_output="",
            result=None,
            output_paths=None,
        )

    def _on_open_view(self) -> None:
        selected = self._get_selected_item_ids()
        if not selected:
            self._set_status_message("Please select a queue item first")
            return
        if len(selected) > 1:
            self._set_status_message("Please select only one item to open its view")
            return

        item_id = selected[0]
        item = self._items_cache.get(item_id)
        if not item:
            self._set_status_message("Selected item not found in queue")
            return
        if item.status == "pending":
            self._set_status_message("This item hasn't been transcribed yet. Start the queue to process it.")
            return
        if item.status == "failed":
            self._set_status_message("This item failed to transcribe. Check error message or retry.")
            return

        if self._view_dialog is None:
            self._create_view_dialog()

        self._view_dialog.clear_content()
        if item.status == "running":
            if item_id != self._current_running_item_id:
                self._set_status_message("Cannot open view: item status is inconsistent")
                return
            self._view_dialog.update_run_output(self._current_run_output)
            self._set_status_message(f"Opened live view for: {item.display_label}")
        elif item.status == "completed":
            if not item.transcript_path or not item.transcript_path.is_file():
                self._set_status_message(
                    "Transcript file not found. The file may have been moved or deleted."
                )
                return
            try:
                self._view_dialog._load_transcript(item.transcript_path)
                self._view_dialog.update_run_output(item.run_detail or "")
                self._set_status_message(f"Opened view for: {item.display_label}")
            except Exception as exc:
                self._set_status_message(f"Error loading transcript: {exc}")
                return
        else:
            self._set_status_message(f"Cannot open view for item with status: {item.status}")
            return

        self._view_dialog.show()
        self._view_dialog.raise_()
        self._view_dialog.activateWindow()

