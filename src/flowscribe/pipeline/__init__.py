"""Pipeline-layer orchestration for media processing workflows."""

from __future__ import annotations

__all__ = ["LocalTranscriptionPipeline"]


def __getattr__(name: str):
    if name == "LocalTranscriptionPipeline":
        from flowscribe.pipeline.transcription import LocalTranscriptionPipeline

        return LocalTranscriptionPipeline
    raise AttributeError(name)
