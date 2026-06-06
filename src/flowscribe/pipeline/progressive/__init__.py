"""Progressive transcription for long media files."""

# Re-export model classes for backward compatibility
from flowscribe.core.models import MediaDurationInfo
from flowscribe.pipeline.progressive.executor import (
    ProgressiveChunkCache,
    ProgressiveTranscriptionExecutor,
)
from flowscribe.pipeline.progressive.merger import (
    ChunkMergePolicy,
    ConservativeChunkMergePolicy,
    ProgressiveTranscriptConsistencyChecker,
)
from flowscribe.pipeline.progressive.planner import (
    CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS,
    DEFAULT_PROGRESSIVE_CHUNK_OVERLAP_SECONDS,
    ClipTranscriber,
    FixedDurationChunkPlanner,
    PreparedAudioDurationProbe,
    tuned_chunk_overlap_seconds,
)

__all__ = [
    # Constants
    "DEFAULT_PROGRESSIVE_CHUNK_OVERLAP_SECONDS",
    "CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS",
    # Protocols
    "ClipTranscriber",
    "ChunkMergePolicy",
    # Planner
    "PreparedAudioDurationProbe",
    "FixedDurationChunkPlanner",
    "tuned_chunk_overlap_seconds",
    # Merger
    "ConservativeChunkMergePolicy",
    "ProgressiveTranscriptConsistencyChecker",
    # Executor
    "ProgressiveTranscriptionExecutor",
    "ProgressiveChunkCache",
    # Models (re-exported for backward compatibility)
    "MediaDurationInfo",
]
