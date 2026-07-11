"""Core domain models and pipeline orchestration."""

from __future__ import annotations

_MODEL_EXPORTS = {
    "ChunkTranscriptionResult",
    "MediaDurationInfo",
    "MediaItem",
    "OutputArtifacts",
    "PreparedAudio",
    "ProgressiveTranscriptionState",
    "ProgressiveTranscriptionUpdate",
    "Transcript",
    "TranscriptSegment",
    "TranscriptWord",
    "TranscriptionChunk",
    "TranscriptionChunkPlan",
    "TranscriptionOptions",
}
_ERROR_EXPORTS = {
    "FlowScribeError",
    "InputError",
    "MediaPreparationError",
    "OutputError",
    "TranscriptionError",
}
_PORT_EXPORTS = {"ArtifactWriter", "MediaPreparer", "Transcriber"}
_PIPELINE_EXPORTS = {"LocalTranscriptionPipeline", "TranscriptDeduplicator"}
_PROGRESSIVE_EXPORTS = {
    "ChunkMergePolicy",
    "ClipTranscriber",
    "ConservativeChunkMergePolicy",
    "FixedDurationChunkPlanner",
    "PreparedAudioDurationProbe",
    "ProgressiveChunkCache",
    "ProgressiveTranscriptConsistencyChecker",
    "ProgressiveTranscriptionExecutor",
    "tuned_chunk_overlap_seconds",
}

__all__ = sorted(
    _MODEL_EXPORTS
    | _ERROR_EXPORTS
    | _PORT_EXPORTS
    | _PIPELINE_EXPORTS
    | _PROGRESSIVE_EXPORTS
)


def __getattr__(name: str):
    if name in _MODEL_EXPORTS:
        from flowscribe.core import models

        return getattr(models, name)
    if name in _ERROR_EXPORTS:
        from flowscribe.core import errors

        return getattr(errors, name)
    if name in _PORT_EXPORTS:
        from flowscribe.core import ports

        return getattr(ports, name)
    if name == "LocalTranscriptionPipeline":
        from flowscribe.pipeline.transcription import LocalTranscriptionPipeline

        return LocalTranscriptionPipeline
    if name == "TranscriptDeduplicator":
        from flowscribe.pipeline.deduplication import TranscriptDeduplicator

        return TranscriptDeduplicator
    if name in _PROGRESSIVE_EXPORTS:
        from flowscribe.pipeline import progressive

        return getattr(progressive, name)
    raise AttributeError(name)
