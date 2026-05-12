"""WebVTT subtitle writer."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import Transcript
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.time_format import format_timestamp


class VttTranscriptWriter:
    def __init__(self, path_builder: OutputPathBuilder | None = None) -> None:
        self._path_builder = path_builder or OutputPathBuilder()

    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        path = self._path_builder.build(transcript.source, output_dir, ".vtt")
        try:
            path.write_text(self._render(transcript), encoding="utf-8")
        except OSError as exc:
            raise OutputError(f"Could not write VTT transcript to {path}: {exc}") from exc
        return path

    def _render(self, transcript: Transcript) -> str:
        blocks = ["WEBVTT"]
        for segment in transcript.segments:
            text = segment.text.strip()
            if not text:
                continue
            start = format_timestamp(segment.start_seconds)
            end = format_timestamp(segment.end_seconds)
            blocks.append(f"{start} --> {end}\n{text}")
        return "\n\n".join(blocks) + "\n"
