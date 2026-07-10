"""QObject-based worker for running TranscriptionService on a QThread."""

from __future__ import annotations

import logging
import warnings

from PySide6.QtCore import QObject, Signal, Slot

from flowscribe.tasks.models import ProgressEvent
from flowscribe.app.service import TranscriptionService

LOGGER = logging.getLogger(__name__)


class TranscriptionWorker(QObject):
    """Runs a TranscriptionJob on a worker thread with progress and cancellation."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    warning = Signal(str)  # New signal for warnings

    def __init__(
        self,
        job,
        *,
        execution_backend=None,
        execution_mode: str = "local",
        server_target: str | None = None,
    ) -> None:
        super().__init__()
        self._job = job
        self._execution_backend = execution_backend
        self._execution_mode = execution_mode
        self._server_target = server_target
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        LOGGER.info(
            "Transcription worker started: sources=%s provider=%s model=%s output_dir=%s execution_mode=%s server_target=%s",
            len(self._job.sources),
            self._job.provider_name,
            self._job.model_name,
            self._job.output_dir,
            self._execution_mode,
            self._server_target or "<none>",
        )
        # Capture warnings during transcription
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")

            try:
                backend = self._execution_backend or TranscriptionService()
                result = backend.run(
                    self._job,
                    progress=self._handle_progress,
                    should_cancel=lambda: self._cancel_requested,
                )
            except Exception as exc:  # pragma: no cover - defensive GUI boundary
                LOGGER.exception("Unhandled exception in transcription worker.")
                self.failed.emit(str(exc))
                return

            # Emit any warnings that were captured
            for w in warning_list:
                LOGGER.warning("Transcription warning: %s", w.message)
                self.warning.emit(str(w.message))

            if result.errors:
                for error in result.errors:
                    LOGGER.error(
                        "Transcription failed: source=%s code=%s message=%s",
                        error.source,
                        error.code,
                        error.message,
                    )
            else:
                LOGGER.info("Transcription worker finished successfully.")
            self.finished.emit(result)

    def _handle_progress(self, event: ProgressEvent) -> None:
        self.progress.emit(event)
