"""QObject-based worker for running TranscriptionService on a QThread."""

from __future__ import annotations

import warnings

from PySide6.QtCore import QObject, Signal, Slot

from flowscribe.app.models import ProgressEvent
from flowscribe.app.service import TranscriptionService


class TranscriptionWorker(QObject):
    """Runs a TranscriptionJob on a worker thread with progress and cancellation."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    warning = Signal(str)  # New signal for warnings

    def __init__(self, job) -> None:
        super().__init__()
        self._job = job
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        # Capture warnings during transcription
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")

            try:
                result = TranscriptionService().run(
                    self._job,
                    progress=self._handle_progress,
                    should_cancel=lambda: self._cancel_requested,
                )
            except Exception as exc:  # pragma: no cover - defensive GUI boundary
                self.failed.emit(str(exc))
                return

            # Emit any warnings that were captured
            for w in warning_list:
                self.warning.emit(str(w.message))

            self.finished.emit(result)

    def _handle_progress(self, event: ProgressEvent) -> None:
        self.progress.emit(event)
