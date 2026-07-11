from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from flowscribe.tasks.queue_models import QueueItem


class QueueViewSelectionMixin:
    """Selection, reorder, summary, and button-state helpers for the queue view."""

    def _on_rows_moved(self, parent, start: int, end: int, dest, row: int) -> None:
        self._item_ids = self._collect_item_order()
        self.reorder_requested.emit(self._item_ids)

    def _get_selected_item_ids(self) -> list[str]:
        selected: list[str] = []
        selected_rows = {index.row() for index in self._queue_list.selectedIndexes()}
        for row in range(self._queue_list.count()):
            item_id = self._list_item_id(row)
            if item_id is None:
                continue
            if item_id in self._checked_item_ids or row in selected_rows:
                selected.append(item_id)
        return selected

    def _collect_item_order(self) -> list[str]:
        return [
            item_id
            for row in range(self._queue_list.count())
            if (item_id := self._list_item_id(row)) is not None
        ]

    def _list_item_id(self, row: int) -> str | None:
        list_item = self._queue_list.item(row)
        if list_item is None:
            return None
        value = list_item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) and value else None

    def _update_button_states(self) -> None:
        has_items = self._queue_list.count() > 0
        selected_ids = self._get_selected_item_ids()
        selected_items = [
            self._items_cache[item_id] for item_id in selected_ids if item_id in self._items_cache
        ]
        has_selection = bool(selected_items)
        has_running = self._current_running_item_id is not None
        has_completed = any(item.status == "completed" for item in self._items_cache.values())
        can_open_view = len(selected_items) == 1 and selected_items[0].status in {"running", "completed"}
        can_retry = any(item.status in {"failed", "canceled"} for item in selected_items)

        self._start_queue_btn.setEnabled(has_items and not has_running)
        self._cancel_queue_btn.setEnabled(has_running)
        self._skip_current_btn.setEnabled(has_running)
        self._open_view_btn.setEnabled(can_open_view)
        self._edit_settings_btn.setEnabled(has_selection)
        self._retry_btn.setEnabled(can_retry)
        self._remove_btn.setEnabled(has_selection)
        self._clear_completed_btn.setEnabled(has_completed)
        self._select_all_btn.setEnabled(has_items)

    def _sync_all_card_check_states(self) -> None:
        from .queue_view import QueueItemCard

        for row in range(self._queue_list.count()):
            item_id = self._list_item_id(row)
            if item_id is None:
                continue
            list_item = self._queue_list.item(row)
            if list_item is None:
                continue
            card = self._queue_list.itemWidget(list_item)
            if isinstance(card, QueueItemCard):
                card.set_checked(item_id in self._checked_item_ids)

    def _sync_card_selection_states(self) -> None:
        from .queue_view import QueueItemCard

        selected_rows = {index.row() for index in self._queue_list.selectedIndexes()}
        for row in range(self._queue_list.count()):
            list_item = self._queue_list.item(row)
            if list_item is None:
                continue
            card = self._queue_list.itemWidget(list_item)
            if isinstance(card, QueueItemCard):
                card.set_selected(row in selected_rows)

    def refresh_queue(self, items: list[QueueItem]) -> None:
        from .queue_view import QueueItemCard

        self._queue_list.clear()
        self._item_ids.clear()
        self._items_cache.clear()
        self._checked_item_ids.clear()

        for item in items:
            self._item_ids.append(item.item_id)
            self._items_cache[item.item_id] = item
            list_item = QListWidgetItem()
            list_item.setToolTip(self._format_item_display(item))
            list_item.setData(Qt.ItemDataRole.UserRole, item.item_id)
            self._queue_list.addItem(list_item)
            card = QueueItemCard(item, self._queue_list)
            card.set_checked(False)
            card.checked_changed.connect(self._on_card_checked_changed)
            card.retry_requested.connect(self._on_retry_single_item)
            card.remove_requested.connect(self._on_remove_single_item)
            list_item.setSizeHint(card.sizeHint())
            self._queue_list.setItemWidget(list_item, card)

        count = len(items)
        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")
        self._queue_summary_label.setText(
            f"{count} total | {pending} pending | {running} running | {completed} completed | {failed} failed"
        )
        self._set_status_message("Queue is empty" if count == 0 else "Select items to manage the queue")
        self._sync_card_selection_states()
        self._update_button_states()

    def _on_card_checked_changed(self, item_id: str, checked: bool) -> None:
        if checked:
            self._checked_item_ids.add(item_id)
        else:
            self._checked_item_ids.discard(item_id)
        self._sync_all_card_check_states()
        self._update_button_states()

    def _format_item_display(self, item: QueueItem) -> str:
        from .queue_view import _STATUS_ICONS

        icon = _STATUS_ICONS.get(item.status, "[?]")
        if item.source.kind == "local":
            source_label = f"[FILE] {Path(item.source.value).name}"
        else:
            display_name = item.display_label
            if len(display_name) > 80:
                display_name = display_name[:77] + "..."
            source_label = f"[URL] {display_name}"
        return f"{icon} {source_label}"
