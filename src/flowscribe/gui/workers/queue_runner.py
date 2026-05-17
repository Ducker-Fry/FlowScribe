"""Queue runner that processes items sequentially on a worker thread."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Signal, Slot

from flowscribe.app.models import ProgressEvent
from flowscribe.app.service import TranscriptionService
from flowscribe.queue.models import QueueItem
from flowscribe.queue.store import BatchQueueStore


class QueueRunner(QObject):

    item_started = Signal(object)
    item_progress = Signal(object)
    item_completed = Signal(object)
    item_failed = Signal(object)
    item_canceled = Signal(object)
    queue_finished = Signal()
    queue_progress = Signal(int, int)

    def __init__(self, store: BatchQueueStore) -> None:
        super().__init__()
        self._store = store
        self._cancel_all = False
        self._cancel_current = False

    @Slot()
    def run(self) -> None:
        items = self._store.load_items()
        total = sum(1 for i in items if i.status == "pending")
        completed = 0

        while not self._cancel_all:
            item = self._store.dequeue()
            if item is None:
                break
            self._cancel_current = False
            self.item_started.emit(item)
            success = self._process_item(item)
            if success:
                completed += 1
            self.queue_progress.emit(completed, total)

        self.queue_finished.emit()

    def _process_item(self, item: QueueItem) -> bool:
        job = item.to_job()
        try:
            result = TranscriptionService().run(
                job,
                progress=self._handle_progress,
                should_cancel=lambda: self._cancel_current or self._cancel_all,
            )
        except Exception as exc:
            self._mark_failed(item, str(exc))
            return False

        if result.canceled:
            self._store.update_item(
                item.item_id, status="canceled", finished_at=datetime.now()
            )
            self.item_canceled.emit(item)
            return False

        if result.errors:
            self._mark_failed(item, result.errors[0].message)
            return False

        self._store.update_item(
            item.item_id, status="completed", finished_at=datetime.now()
        )
        self.item_completed.emit((item, result))
        return True

    def _mark_failed(self, item: QueueItem, message: str) -> None:
        new_attempt = item.attempt_count + 1
        self._store.update_item(
            item.item_id,
            status="failed",
            error_message=message,
            attempt_count=new_attempt,
            finished_at=datetime.now(),
        )
        self.item_failed.emit((item, message))
        updated = self._store.load_items()
        for i in updated:
            if i.item_id == item.item_id and i.can_retry:
                self._store.update_item(i.item_id, status="pending", started_at=None)
                break

    def _handle_progress(self, event: ProgressEvent) -> None:
        self.item_progress.emit(event)

    @Slot()
    def request_cancel_all(self) -> None:
        self._cancel_all = True
        self._cancel_current = True

    @Slot()
    def request_skip_current(self) -> None:
        self._cancel_current = True
