"""JSON transcript writer."""

from __future__ import annotations

import json
from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe import __version__
from flowscribe.app.schema import TRANSCRIPT_JSON_SCHEMA_VERSION
from flowscribe.core.models import Transcript, TranscriptSegment, TranscriptWord
from flowscribe.output.paths import OutputPathBuilder

JSON_SCHEMA_VERSION = TRANSCRIPT_JSON_SCHEMA_VERSION


class JsonTranscriptWriter:
    def __init__(
        self,
        path_builder: OutputPathBuilder | None = None,
        media_path: Path | None = None,
        media_kind: str | None = None,
    ) -> None:
        self._path_builder = path_builder or OutputPathBuilder()
        self._media_path = media_path
        self._media_kind = media_kind

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
        source = transcript.source.path
        segments = [
            self._segment_to_payload(index, segment)
            for index, segment in enumerate(transcript.segments, start=1)
        ]
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "generator": {
                "name": "FlowScribe",
                "version": __version__,
            },
            "source": str(source),
            "source_info": {
                "path": str(source),
                "name": source.name,
                "stem": source.stem,
                "suffix": source.suffix,
            },
            "language": transcript.language,
            "model": transcript.model_name,
            "provider": options.provider_name if options is not None else None,
            "created_at": transcript.created_at.isoformat(timespec="seconds"),
            "duration_seconds": self._duration_seconds(transcript),
            "segment_count": len(transcript.segments),
            "word_count": sum(len(segment.words) for segment in transcript.segments),
            "raw_word_count": sum(len(segment.raw_words) for segment in transcript.segments),
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
                "word_timestamps": options.word_timestamps,
                "provider_name": options.provider_name,
            },
            "text": transcript.text,
            "segments": segments,
        }

        # Add media binding information if available
        if self._media_path is not None:
            payload["media_binding"] = {
                "path": str(self._media_path),
                "kind": self._media_kind,
            }

        return payload

    def _segment_to_payload(self, index: int, segment: TranscriptSegment) -> dict:
        return {
            "id": f"seg-{index:04d}",
            "index": index,
            "text": segment.text,
            "start": segment.start_seconds,
            "end": segment.end_seconds,
            "start_seconds": segment.start_seconds,
            "end_seconds": segment.end_seconds,
            "duration_seconds": self._span_duration(segment.start_seconds, segment.end_seconds),
            "raw_words": [
                self._word_to_payload(word, index=word_index)
                for word_index, word in enumerate(segment.raw_words, start=1)
            ],
            "words": [
                self._word_to_payload(word, index=word_index)
                for word_index, word in enumerate(segment.words, start=1)
            ],
        }

    def _word_to_payload(self, word: TranscriptWord, *, index: int) -> dict:
        return {
            "index": index,
            "word": word.text,
            "text": word.text,
            "start": word.start_seconds,
            "end": word.end_seconds,
            "start_seconds": word.start_seconds,
            "end_seconds": word.end_seconds,
            "duration_seconds": self._span_duration(word.start_seconds, word.end_seconds),
            "confidence": word.confidence,
        }

    def _duration_seconds(self, transcript: Transcript) -> float | None:
        starts = [
            segment.start_seconds
            for segment in transcript.segments
            if segment.start_seconds is not None
        ]
        ends = [
            segment.end_seconds
            for segment in transcript.segments
            if segment.end_seconds is not None
        ]
        if not starts or not ends:
            return None
        return self._span_duration(min(starts), max(ends))

    @staticmethod
    def _span_duration(start: float | None, end: float | None) -> float | None:
        if start is None or end is None:
            return None
        return max(0.0, end - start)
