"""JSON transcript writer."""

from __future__ import annotations

import json
from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import Transcript
from flowscribe.output.paths import OutputPathBuilder


class JsonTranscriptWriter:
    def __init__(self, path_builder: OutputPathBuilder | None = None) -> None:
        self._path_builder = path_builder or OutputPathBuilder()

    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        path = self._path_builder.build(transcript.source, output_dir, ".json")
        try:
            path.write_text(
                json.dumps(self._to_payload(transcript), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise OutputError(f"Could not write JSON transcript to {path}: {exc}") from exc
        return path

    def _to_payload(self, transcript: Transcript) -> dict:
        options = transcript.options
        return {
            "source": str(transcript.source.path),
            "language": transcript.language,
            "model": transcript.model_name,
            "created_at": transcript.created_at.isoformat(timespec="seconds"),
            "options": None
            if options is None
            else {
                "model_name": options.model_name,
                "language": options.language,
                "task": options.task,
                "beam_size": options.beam_size,
                "vad_filter": options.vad_filter,
                "initial_prompt": options.initial_prompt,
                "preset": options.preset,
            },
            "text": transcript.text,
            "segments": [
                {
                    "text": segment.text,
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "words": [
                        {
                            "text": word.text,
                            "start_seconds": word.start_seconds,
                            "end_seconds": word.end_seconds,
                        }
                        for word in segment.words
                    ],
                }
                for segment in transcript.segments
            ],
        }
