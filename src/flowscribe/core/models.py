"""Domain models shared by the FlowScribe pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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

    @property
    def txt_path(self) -> Path | None:
        return self._find_by_suffix(".txt")

    @property
    def md_path(self) -> Path | None:
        return self._find_by_suffix(".md")

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
