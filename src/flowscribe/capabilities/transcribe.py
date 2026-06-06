"""Transcription capability wrapper."""

from __future__ import annotations

from collections.abc import Callable

from flowscribe.capabilities.protocol import CancelToken
from flowscribe.tasks.models import CapabilityResult, ProgressEvent, TaskSpec


class TranscribeCapability:
    """Marker capability used by the app/pipeline bridge."""

    name = "transcribe"

    def run(
        self,
        task: TaskSpec,
        *,
        progress_cb: Callable[[ProgressEvent], None] | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CapabilityResult:
        if progress_cb is not None:
            progress_cb(
                ProgressEvent(
                    task_id=task.task_id,
                    capability=self.name,
                    stage="transcribe",
                    percent=0.0,
                    message="Routing to transcription capability.",
                    source=task.source.value,
                )
            )
        return CapabilityResult(
            task_id=task.task_id,
            capability=self.name,
            supported=True,
            status="success",
        )
