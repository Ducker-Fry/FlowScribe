"""Stable public application-layer API for FlowScribe."""

from flowscribe.app.service import TranscriptionService
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
