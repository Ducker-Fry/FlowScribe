"""Editable transcript JSON helpers."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flowscribe.output.time_format import format_timestamp


@dataclass(frozen=True)
class EditableTranscriptSegment:
    index: int
    text: str
    start_seconds: float | None
    end_seconds: float | None
    original_text: str
    segment_id: str | None = None

    @property
    def edited(self) -> bool:
        return self.text != self.original_text


@dataclass(frozen=True)
class EditableTranscriptDocument:
    path: Path
    source: str
    language: str | None
    model: str | None
    payload: dict
    segments: tuple[EditableTranscriptSegment, ...]

    @property
    def dirty(self) -> bool:
        return any(segment.edited for segment in self.segments)

    @property
    def text(self) -> str:
        return "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())


def load_editable_transcript(path: Path) -> EditableTranscriptDocument:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read transcript JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Transcript JSON is not valid JSON: {exc}") from exc

    segments_payload = payload.get("segments")
    if not isinstance(segments_payload, list):
        raise ValueError("Transcript JSON does not contain a valid segments list.")

    segments: list[EditableTranscriptSegment] = []
    for offset, raw_segment in enumerate(segments_payload, start=1):
        if not isinstance(raw_segment, dict):
            raise ValueError("Transcript JSON contains an invalid segment entry.")
        text = str(raw_segment.get("text") or "").strip()
        segments.append(
            EditableTranscriptSegment(
                index=_segment_index(raw_segment, offset),
                text=text,
                original_text=text,
                start_seconds=_optional_number(
                    raw_segment.get("start_seconds", raw_segment.get("start"))
                ),
                end_seconds=_optional_number(
                    raw_segment.get("end_seconds", raw_segment.get("end"))
                ),
                segment_id=_optional_text(raw_segment.get("id")),
            )
        )

    return EditableTranscriptDocument(
        path=path.expanduser().resolve(),
        source=str(payload.get("source") or path.name),
        language=_optional_text(payload.get("language")),
        model=_optional_text(payload.get("model")),
        payload=payload,
        segments=tuple(segments),
    )


def update_editable_transcript_segment(
    document: EditableTranscriptDocument,
    segment_index: int,
    text: str,
) -> EditableTranscriptDocument:
    if segment_index < 0 or segment_index >= len(document.segments):
        raise IndexError("Transcript segment index is out of range.")

    normalized_text = text.strip()
    updated_segments = list(document.segments)
    segment = updated_segments[segment_index]
    updated_segments[segment_index] = EditableTranscriptSegment(
        index=segment.index,
        text=normalized_text,
        original_text=segment.original_text,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        segment_id=segment.segment_id,
    )
    return EditableTranscriptDocument(
        path=document.path,
        source=document.source,
        language=document.language,
        model=document.model,
        payload=document.payload,
        segments=tuple(updated_segments),
    )


def suggested_corrected_transcript_path(path: Path) -> Path:
    normalized = path.expanduser().resolve()
    return normalized.with_name(f"{normalized.stem}.corrected{normalized.suffix}")


def save_editable_transcript(
    document: EditableTranscriptDocument,
    *,
    destination: Path | None = None,
    corrected_at: datetime | None = None,
) -> Path:
    if destination is None:
        destination = document.path
    target = destination.expanduser().resolve()
    timestamp = corrected_at or datetime.now()

    payload = copy.deepcopy(document.payload)
    segments_payload = payload.get("segments")
    if not isinstance(segments_payload, list) or len(segments_payload) != len(document.segments):
        raise ValueError("Transcript JSON segments no longer match the editable transcript.")

    edited_segment_count = 0
    for offset, segment in enumerate(document.segments):
        raw_segment = segments_payload[offset]
        if not isinstance(raw_segment, dict):
            raise ValueError("Transcript JSON contains an invalid segment entry.")
        raw_segment["text"] = segment.text
        if segment.edited:
            edited_segment_count += 1
            raw_segment["correction"] = {
                "edited": True,
                "original_text": segment.original_text,
                "corrected_text": segment.text,
                "corrected_at": timestamp.isoformat(timespec="seconds"),
            }
        else:
            raw_segment.pop("correction", None)

    payload["text"] = document.text
    payload["segment_count"] = len(document.segments)
    if edited_segment_count:
        payload["corrections"] = {
            "corrected_at": timestamp.isoformat(timespec="seconds"),
            "edited_segment_count": edited_segment_count,
        }
    else:
        payload.pop("corrections", None)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def render_editable_segment_line(segment: EditableTranscriptSegment) -> str:
    suffix = " [edited]" if segment.edited else ""
    return (
        f"[{format_timestamp(segment.start_seconds)} - {format_timestamp(segment.end_seconds)}] "
        f"{segment.text or '(empty segment)'}{suffix}"
    )


def _segment_index(raw_segment: dict, fallback: int) -> int:
    value = raw_segment.get("index")
    if isinstance(value, int):
        return value
    return fallback


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
