"""Plain text transcript writer."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import Transcript
from flowscribe.output.paths import OutputPathBuilder


class TxtTranscriptWriter:
    def __init__(self, path_builder: OutputPathBuilder | None = None) -> None:
        self._path_builder = path_builder or OutputPathBuilder()

    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        path = self._path_builder.build(transcript.source, output_dir, ".txt")
        try:
            path.write_text(transcript.text + "\n", encoding="utf-8")
        except OSError as exc:
            raise OutputError(f"Could not write TXT transcript to {path}: {exc}") from exc
        return path
