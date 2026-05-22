"""Interfaces implemented by concrete pipeline adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from flowscribe.core.models import MediaItem, OutputArtifacts, PreparedAudio, Transcript


class InputSource(Protocol):
    def discover(self) -> list[MediaItem]:
        """Return media items to process."""


class MediaPreparer(Protocol):
    def prepare(self, item: MediaItem, work_dir: Path) -> PreparedAudio:
        """Prepare a media item as audio for transcription."""


class Transcriber(Protocol):
    def transcribe(
        self,
        audio: PreparedAudio,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Transcript:
        """Create a transcript from prepared audio."""


class TranscriptWriter(Protocol):
    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        """Write one transcript artifact."""


class ArtifactWriter(Protocol):
    def write_all(self, transcript: Transcript, output_dir: Path) -> OutputArtifacts:
        """Write all configured transcript artifacts."""
