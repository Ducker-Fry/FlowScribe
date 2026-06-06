"""Core domain models and pipeline orchestration."""

from flowscribe.pipeline.deduplication import TranscriptDeduplicator
from flowscribe.core.errors import (
    FlowScribeError,
    InputError,
    MediaPreparationError,
    OutputError,
    TranscriptionError,
)
from flowscribe.core.models import (
    ChunkTranscriptionResult,
    MediaDurationInfo,
    MediaItem,
    OutputArtifacts,
    PreparedAudio,
    ProgressiveTranscriptionState,
    ProgressiveTranscriptionUpdate,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionChunk,
    TranscriptionChunkPlan,
    TranscriptionOptions,
)
from flowscribe.pipeline.transcription import LocalTranscriptionPipeline
from flowscribe.core.ports import ArtifactWriter, MediaPreparer, Transcriber
from flowscribe.pipeline.progressive import (
    ChunkMergePolicy,
    ClipTranscriber,
    ConservativeChunkMergePolicy,
    FixedDurationChunkPlanner,
    PreparedAudioDurationProbe,
    ProgressiveChunkCache,
    ProgressiveTranscriptConsistencyChecker,
    ProgressiveTranscriptionExecutor,
    tuned_chunk_overlap_seconds,
)

__all__ = [
    "ArtifactWriter",
    "ChunkMergePolicy",
    "ChunkTranscriptionResult",
    "ClipTranscriber",
    "ConservativeChunkMergePolicy",
    "FixedDurationChunkPlanner",
    "FlowScribeError",
    "InputError",
    "LocalTranscriptionPipeline",
    "MediaDurationInfo",
    "MediaItem",
    "MediaPreparer",
    "MediaPreparationError",
    "OutputArtifacts",
    "OutputError",
    "PreparedAudio",
    "PreparedAudioDurationProbe",
    "ProgressiveChunkCache",
    "ProgressiveTranscriptConsistencyChecker",
    "ProgressiveTranscriptionExecutor",
    "ProgressiveTranscriptionState",
    "ProgressiveTranscriptionUpdate",
    "Transcript",
    "TranscriptDeduplicator",
    "TranscriptSegment",
    "TranscriptWord",
    "Transcriber",
    "TranscriptionChunk",
    "TranscriptionChunkPlan",
    "TranscriptionError",
    "TranscriptionOptions",
    "tuned_chunk_overlap_seconds",
]
