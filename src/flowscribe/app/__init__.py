"""Stable public application-layer API for FlowScribe."""

from __future__ import annotations

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
    if name in {
        "CancelAck",
        "CancelRequest",
        "ProgressCallback",
        "ProgressEvent",
        "SourceSpec",
        "TaskSpec",
        "TranscriptionJob",
        "TranscriptionResult",
    }:
        from flowscribe.tasks import models as task_models

        return getattr(task_models, name)
    raise AttributeError(name)
