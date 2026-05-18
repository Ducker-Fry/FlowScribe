"""Stable application models used by CLI, future GUI, and automation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from flowscribe.core.models import OutputArtifacts, TranscriptSegment

SourceKind = Literal["local", "url", "capture"]
UrlMediaKind = Literal["audio", "video"]
ProgressStage = Literal[
    "discover",
    "download",
    "prepare",
    "transcribe",
    "write",
    "complete",
    "error",
    "canceled",
    "resume",
]


@dataclass(frozen=True)
class SourceSpec:
    """One user-provided source to process."""

    kind: SourceKind
    value: str
    recursive: bool = False
    keep_media: bool = False
    url_media_kind: UrlMediaKind = "audio"
    media_output_dir: Path | None = None
    auto_bind_media: bool = False


@dataclass(frozen=True)
class TranscriptionJob:
    """Stable request object for a transcription run."""

    sources: tuple[SourceSpec, ...]
    output_dir: Path = Path("outputs")
    output_name_base: str | None = None
    work_dir: Path | None = None
    model_name: str = "small"
    language: str | None = None
    preset: str | None = None
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = False
    no_vad_filter: bool = False
    initial_prompt: str | None = None
    timestamps: bool = False
    word_timestamps: bool = False
    output_formats: tuple[str, ...] = ("txt", "md")
    overwrite: bool = False
    keep_audio: bool = False
    max_download_mb: int = 2048
    max_duration_seconds: float = 4 * 60 * 60
    download_timeout_seconds: int = 30
    network_family: str = "auto"
    cookies_path: Path | None = None
    proxy: str | None = None
    progressive_enabled: bool = True
    progressive_resume: bool = True
    progressive_chunk_seconds: float = 30.0
    progressive_chunk_overlap_seconds: float = 3.0
    progressive_max_workers: int = 1
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ProgressEvent:
    """Structured progress event for UI and automation."""

    stage: ProgressStage
    message: str
    source: str | None = None
    current: int | None = None
    total: int | None = None
    path: Path | None = None
    processed_duration_seconds: float | None = None
    total_duration_seconds: float | None = None
    eta_seconds: float | None = None
    realtime_factor: float | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    completed_chunks: int | None = None
    failed_chunks: int | None = None
    segments: tuple[TranscriptSegment, ...] = ()
    resumed: bool = False


@dataclass(frozen=True)
class ErrorInfo:
    """Structured error information that can be displayed in a GUI."""

    code: str
    message: str
    source: str | None = None
    recoverable: bool = True


@dataclass(frozen=True)
class TranscriptionResult:
    """Stable response object returned by application services."""

    job: TranscriptionJob
    outputs: tuple[OutputArtifacts, ...] = ()
    errors: tuple[ErrorInfo, ...] = ()
    canceled: bool = False
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    @property
    def succeeded(self) -> int:
        return len(self.outputs)

    @property
    def failed(self) -> int:
        return len(self.errors)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.canceled

    @property
    def elapsed_seconds(self) -> float | None:
        """Total elapsed time in seconds, or None if not finished."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


ProgressCallback = Callable[[ProgressEvent], None]
