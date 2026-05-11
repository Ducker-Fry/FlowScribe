"""SRT subtitle writer."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import Transcript
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.time_format import format_srt_timestamp


class SrtTranscriptWriter:
    def __init__(self, path_builder: OutputPathBuilder | None = None) -> None:
        self._path_builder = path_builder or OutputPathBuilder()

    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        path = self._path_builder.build(transcript.source, output_dir, ".srt")
        try:
            path.write_text(self._render(transcript), encoding="utf-8")
        except OSError as exc:
            raise OutputError(f"Could not write SRT transcript to {path}: {exc}") from exc
        return path

    def _render(self, transcript: Transcript) -> str:
        blocks = []
        index = 1
        for segment in transcript.segments:
            text = segment.text.strip()
            if not text:
                continue
            start = format_srt_timestamp(segment.start_seconds)
            end = format_srt_timestamp(segment.end_seconds)
            blocks.append(f"{index}\n{start} --> {end}\n{text}")
            index += 1
        return "\n\n".join(blocks) + ("\n" if blocks else "")
