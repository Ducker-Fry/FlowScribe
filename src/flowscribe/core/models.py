"""Domain models shared by the FlowScribe pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class MediaItem:
    """A local media file selected for transcription."""

    path: Path


@dataclass(frozen=True)
class PreparedAudio:
    """Audio artifact prepared for a transcription provider."""

    source: MediaItem
    path: Path
    sample_rate: int
    duration_seconds: float | None = None


@dataclass(frozen=True)
class TranscriptWord:
    """A word- or character-level timing unit returned by a transcription provider."""

    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptSegment:
    """One transcript segment produced by a speech-to-text provider."""

    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    raw_words: tuple[TranscriptWord, ...] = ()
    words: tuple[TranscriptWord, ...] = ()


@dataclass(frozen=True)
class TranscriptionOptions:
    """Speech-to-text options used for one transcript."""

    model_name: str
    language: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None = None
    preset: str | None = None
    word_timestamps: bool = False
    provider_name: str = "local-whisper"


@dataclass(frozen=True)
class Transcript:
    """The full transcript for a media item."""

    source: MediaItem
    segments: tuple[TranscriptSegment, ...]
    language: str | None = None
    model_name: str | None = None
    options: TranscriptionOptions | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def text(self) -> str:
        return "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())


@dataclass(frozen=True)
class OutputArtifacts:
    """Files written for a transcript."""

    paths: tuple[Path, ...]
    media_path: Path | None = None
    media_kind: str | None = None
    requested_media_kind: str | None = None
    media_fallback: bool = False
    source_kind: str | None = None
    source_value: str | None = None
    auto_bind_media: bool = False

    @property
    def txt_path(self) -> Path | None:
        return self._find_by_suffix(".txt")

    @property
    def md_path(self) -> Path | None:
        return self._find_by_suffix(".md")

    @property
    def json_path(self) -> Path | None:
        return self._find_by_suffix(".json")

    def _find_by_suffix(self, suffix: str) -> Path | None:
        for path in self.paths:
            if path.suffix.lower() == suffix:
                return path
        return None


@dataclass(frozen=True)
class JobFailure:
    """A recoverable item-level failure during batch processing."""

    source: Path
    message: str


@dataclass(frozen=True)
class JobResult:
    """Summary returned after a transcription run."""

    outputs: tuple[OutputArtifacts, ...]
    failures: tuple[JobFailure, ...]

    @property
    def succeeded(self) -> int:
        return len(self.outputs)

    @property
    def failed(self) -> int:
        return len(self.failures)


ChunkStatus = Literal["pending", "running", "done", "failed", "skipped"]


@dataclass(frozen=True)
class MediaDurationInfo:
    """Stable duration metadata for one prepared audio item."""

    source: MediaItem
    prepared_audio_path: Path
    sample_rate: int
    duration_seconds: float | None


@dataclass(frozen=True)
class TranscriptionChunk:
    """One planned progressive transcription time slice."""

    index: int
    start_seconds: float
    end_seconds: float
    overlap_seconds: float = 0.0

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    @property
    def content_start_seconds(self) -> float:
        if self.index <= 1:
            return self.start_seconds
        return min(self.end_seconds, self.start_seconds + self.overlap_seconds)

    @property
    def content_duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.content_start_seconds)


@dataclass(frozen=True)
class TranscriptionChunkPlan:
    """Chunk planning metadata for one progressive transcription run."""

    duration_info: MediaDurationInfo
    chunks: tuple[TranscriptionChunk, ...]
    chunk_duration_seconds: float
    chunk_overlap_seconds: float


@dataclass(frozen=True)
class ChunkTranscriptionResult:
    """Transcript result captured for one chunk execution."""

    chunk: TranscriptionChunk
    status: ChunkStatus
    transcript: Transcript | None = None
    elapsed_seconds: float | None = None
    error_message: str | None = None
    merged_segment_count: int = 0


@dataclass(frozen=True)
class ProgressiveTranscriptionState:
    """Serializable summary of a progressive transcription pass."""

    source: MediaItem
    duration_info: MediaDurationInfo
    chunk_plan: TranscriptionChunkPlan
    chunk_results: tuple[ChunkTranscriptionResult, ...]
    transcript: Transcript
    processed_duration_seconds: float
    cache_dir: Path | None = None

    @property
    def completed_chunks(self) -> int:
        return sum(1 for result in self.chunk_results if result.status == "done")

    @property
    def failed_chunks(self) -> int:
        return sum(1 for result in self.chunk_results if result.status == "failed")


@dataclass(frozen=True)
class ProgressiveTranscriptionUpdate:
    """One progressive execution update emitted after a flushable chunk merge."""

    state: ProgressiveTranscriptionState
    chunk_result: ChunkTranscriptionResult
    appended_segments: tuple[TranscriptSegment, ...]
    resumed: bool = False
