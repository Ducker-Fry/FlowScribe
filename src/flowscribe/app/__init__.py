"""Stable public application-layer API for FlowScribe."""

from flowscribe.tasks.models import (
    CancelAck,
    CancelRequest,
    ProgressCallback,
    ProgressEvent,
    SourceSpec,
    TaskSpec,
    TranscriptionJob,
    TranscriptionResult,
)

__all__ = [
    "CancelAck",
    "CancelRequest",
    "ProgressCallback",
    "ProgressEvent",
    "SourceSpec",
    "TaskSpec",
    "TranscriptionJob",
    "TranscriptionResult",
    "TranscriptionService",
]


def __getattr__(name: str):
    if name == "TranscriptionService":
        from flowscribe.app.service import TranscriptionService

        return TranscriptionService
    raise AttributeError(name)
