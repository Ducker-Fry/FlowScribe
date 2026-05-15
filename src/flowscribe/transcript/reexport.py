"""Re-export transcript artifacts from existing transcript JSON."""

from __future__ import annotations

import json
from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import (
    MediaItem,
    OutputArtifacts,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter


def reexport_transcript_json(
    transcript_path: Path,
    *,
    output_dir: Path,
    output_formats: tuple[str, ...],
    output_name_base: str | None = None,
    overwrite: bool = False,
    include_timestamps: bool = False,
) -> OutputArtifacts:
    payload = _load_transcript_payload(transcript_path)
    transcript = _transcript_from_payload(payload, transcript_path)
    path_builder = OutputPathBuilder(
        overwrite=overwrite,
        base_name=output_name_base or transcript_path.stem,
    )

    exported_paths: list[Path] = []
    artifact_formats = tuple(
        output_format
        for output_format in output_formats
        if output_format in {"txt", "md", "srt", "vtt"}
    )
    if artifact_formats:
        writer = TranscriptArtifactWriter(
            formats=artifact_formats,
            txt_writer=TxtTranscriptWriter(path_builder),
            md_writer=MarkdownTranscriptWriter(
                path_builder,
                include_timestamps=include_timestamps,
            ),
            srt_writer=SrtTranscriptWriter(path_builder),
            vtt_writer=VttTranscriptWriter(path_builder),
        )
        exported_paths.extend(writer.write_all(transcript, output_dir).paths)

    if "json" in output_formats:
        exported_paths.append(
            _write_transcript_json_copy(
                payload,
                transcript,
                transcript_path,
                output_dir=output_dir,
                path_builder=path_builder,
            )
        )

    return OutputArtifacts(paths=tuple(exported_paths))


def _load_transcript_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read transcript JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Transcript JSON is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Transcript JSON payload must be an object.")
    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Transcript JSON does not contain a valid segments list.")
    return payload


def _transcript_from_payload(payload: dict, path: Path) -> Transcript:
    source = _source_media_item(payload, path)
    options = _options_from_payload(payload.get("options"))
    segments_payload = payload.get("segments")
    if not isinstance(segments_payload, list):
        raise ValueError("Transcript JSON does not contain a valid segments list.")

    segments = tuple(_segment_from_payload(raw_segment) for raw_segment in segments_payload)
    return Transcript(
        source=source,
        segments=segments,
        language=_optional_text(payload.get("language")),
        model_name=_optional_text(payload.get("model")),
        options=options,
    )


def _source_media_item(payload: dict, path: Path) -> MediaItem:
    source_text = _optional_text(payload.get("source"))
    if source_text:
        source_path = Path(source_text)
        if not source_path.is_absolute():
            source_path = (path.parent / source_path).resolve()
    else:
        source_path = path.resolve()
    return MediaItem(path=source_path)


def _options_from_payload(value: object) -> TranscriptionOptions | None:
    if not isinstance(value, dict):
        return None
    model_name = _optional_text(value.get("model_name")) or "unknown"
    task = _optional_text(value.get("task")) or "transcribe"
    beam_size = value.get("beam_size")
    if not isinstance(beam_size, int):
        beam_size = 5
    return TranscriptionOptions(
        model_name=model_name,
        language=_optional_text(value.get("language")),
        task=task,
        beam_size=beam_size,
        vad_filter=bool(value.get("vad_filter", False)),
        initial_prompt=_optional_text(value.get("initial_prompt")),
        preset=_optional_text(value.get("preset")),
        word_timestamps=bool(value.get("word_timestamps", False)),
    )


def _segment_from_payload(value: object) -> TranscriptSegment:
    if not isinstance(value, dict):
        raise ValueError("Transcript JSON contains an invalid segment entry.")
    return TranscriptSegment(
        text=str(value.get("text") or "").strip(),
        start_seconds=_optional_number(value.get("start_seconds", value.get("start"))),
        end_seconds=_optional_number(value.get("end_seconds", value.get("end"))),
        raw_words=tuple(_word_from_payload(raw_word) for raw_word in value.get("raw_words", []) if isinstance(value.get("raw_words", []), list)),
        words=tuple(_word_from_payload(word) for word in value.get("words", []) if isinstance(value.get("words", []), list)),
    )


def _word_from_payload(value: object) -> TranscriptWord:
    if not isinstance(value, dict):
        raise ValueError("Transcript JSON contains an invalid word entry.")
    confidence = value.get("confidence")
    if confidence is not None and not isinstance(confidence, int | float):
        raise ValueError("Transcript JSON contains a non-numeric confidence value.")
    return TranscriptWord(
        text=str(value.get("text") or value.get("word") or "").strip(),
        start_seconds=_optional_number(value.get("start_seconds", value.get("start"))),
        end_seconds=_optional_number(value.get("end_seconds", value.get("end"))),
        confidence=None if confidence is None else float(confidence),
    )


def _write_transcript_json_copy(
    payload: dict,
    transcript: Transcript,
    transcript_path: Path,
    *,
    output_dir: Path,
    path_builder: OutputPathBuilder,
) -> Path:
    target = path_builder.build(transcript.source, output_dir, ".json")
    payload_copy = dict(payload)
    payload_copy["text"] = transcript.text
    payload_copy["segment_count"] = len(transcript.segments)
    try:
        target.write_text(
            json.dumps(payload_copy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise OutputError(
            f"Could not write JSON transcript to {target}: {exc}"
        ) from exc
    return target


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"Transcript JSON contains a non-numeric timestamp: {value!r}")
