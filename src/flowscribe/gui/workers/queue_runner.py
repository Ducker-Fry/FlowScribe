"""Queue runner that processes items sequentially on a worker thread."""

from __future__ import annotations

from datetime import datetime
import logging

from PySide6.QtCore import QObject, Signal, Slot

from flowscribe.execution.factory import build_execution_backend
from flowscribe.tasks.models import ProgressEvent
from flowscribe.tasks.queue_models import QueueItem
from flowscribe.tasks.queue_store import BatchQueueStore

LOGGER = logging.getLogger(__name__)


class QueueRunner(QObject):

    item_started = Signal(object)
    item_progress = Signal(object)
    item_completed = Signal(object)
    item_failed = Signal(object)
    item_canceled = Signal(object)
    queue_finished = Signal()
    queue_progress = Signal(int, int)

    def __init__(self, store: BatchQueueStore, execution_backend_factory=None) -> None:
        super().__init__()
        self._store = store
        self._execution_backend_factory = execution_backend_factory
        self._cancel_all = False
        self._cancel_current = False
        self._current_run_output = ""

    @Slot()
    def run(self) -> None:
        LOGGER.info("Queue runner started.")
        items = self._store.load_items()
        total = sum(1 for i in items if i.status == "pending")
        completed = 0

        while not self._cancel_all:
            item = self._store.dequeue()
            if item is None:
                break
            self._cancel_current = False
            self._current_run_output = ""
            self.item_started.emit(item)
            success = self._process_item(item)
            if success:
                completed += 1
            self.queue_progress.emit(completed, total)

        LOGGER.info("Queue runner finished. Completed %s of %s pending item(s).", completed, total)
        self.queue_finished.emit()

    def _process_item(self, item: QueueItem) -> bool:
        job = item.to_job()
        effective_target = item.settings.server_target if item.settings.execution_mode == "remote" else None
        LOGGER.info(
            "Processing queue item %s: source=%s provider=%s model=%s output_dir=%s formats=%s execution_mode=%s server_target=%s",
            item.item_id,
            item.source.value,
            job.provider_name,
            job.model_name,
            job.output_dir,
            job.output_formats,
            item.settings.execution_mode,
            effective_target or "<none>",
        )
        try:
            backend = self._build_backend(item)
            result = backend.run(
                job,
                progress=self._handle_progress,
                should_cancel=lambda: self._cancel_current or self._cancel_all,
            )
        except Exception as exc:
            LOGGER.exception("Unhandled exception while processing queue item %s.", item.item_id)
            self._mark_failed(item, str(exc))
            return False

        LOGGER.info(
            "Queue item %s result: canceled=%s errors=%s outputs=%s",
            item.item_id,
            result.canceled,
            len(result.errors),
            len(result.outputs),
        )
        for idx, output in enumerate(result.outputs):
            LOGGER.debug("Queue item %s output %s: paths=%s", item.item_id, idx, output.paths)

        if result.canceled:
            self._store.update_item(
                item.item_id, status="canceled", finished_at=datetime.now()
            )
            self.item_canceled.emit(item)
            return False

        if result.errors:
            LOGGER.error("Queue item %s failed: %s", item.item_id, result.errors[0].message)
            self._mark_failed(item, result.errors[0].message)
            return False

        LOGGER.info("Queue item %s completed.", item.item_id)
        transcript_path = None
        if result.outputs:
            transcript_path = result.outputs[0].json_path
        self._store.update_item(
            item.item_id,
            status="completed",
            finished_at=datetime.now(),
            transcript_path=transcript_path,
            run_detail=self._current_run_output,
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
        if event.message:
            self._current_run_output += event.message + "\n"
        self.item_progress.emit(event)

    def _build_backend(self, item: QueueItem):
        if self._execution_backend_factory is not None:
            return self._execution_backend_factory(item)
        settings = item.settings
        return build_execution_backend(
            execution_mode=settings.execution_mode,
            server_target=settings.server_target,
            remote_token=settings.remote_token,
            remote_poll_seconds=settings.remote_poll_seconds,
            download_artifacts=settings.download_artifacts,
        )

    @Slot()
    def request_cancel_all(self) -> None:
        self._cancel_all = True
        self._cancel_current = True

    @Slot()
    def request_skip_current(self) -> None:
        self._cancel_current = True
