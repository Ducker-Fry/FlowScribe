"""Helpers for loading and rendering transcript JSON files in the GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from flowscribe.output.time_format import format_timestamp
from flowscribe.search.transcript_search import search_transcript_file


@dataclass(frozen=True)
class TranscriptSegmentView:
    index: int
    text: str
    start_seconds: float | None
    end_seconds: float | None


@dataclass(frozen=True)
class TranscriptView:
    path: Path
    source: str
    language: str | None
    model: str | None
    segments: tuple[TranscriptSegmentView, ...]


@dataclass(frozen=True)
class TranscriptSearchHitView:
    matched_text: str
    start_seconds: float | None
    end_seconds: float | None
    context: str
    segment_index: int


def load_transcript_view(path: Path) -> TranscriptView:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read transcript JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Transcript JSON is not valid JSON: {exc}") from exc

    segments_payload = payload.get("segments")
    if not isinstance(segments_payload, list):
        raise ValueError("Transcript JSON does not contain a valid segments list.")

    segments: list[TranscriptSegmentView] = []
    for raw_segment in segments_payload:
        if not isinstance(raw_segment, dict):
            raise ValueError("Transcript JSON contains an invalid segment entry.")
        segments.append(
            TranscriptSegmentView(
                index=_segment_index(raw_segment, len(segments) + 1),
                text=str(raw_segment.get("text") or "").strip(),
                start_seconds=_optional_number(
                    raw_segment.get("start_seconds", raw_segment.get("start"))
                ),
                end_seconds=_optional_number(raw_segment.get("end_seconds", raw_segment.get("end"))),
            )
        )

    return TranscriptView(
        path=path,
        source=str(payload.get("source") or path.name),
        language=_optional_text(payload.get("language")),
        model=_optional_text(payload.get("model")),
        segments=tuple(segments),
    )


def render_transcript_view(view: TranscriptView) -> str:
    lines = [
        f"Transcript: {view.path.name}",
        f"Source: {view.source}",
        f"Language: {view.language or 'unknown'}",
        f"Model: {view.model or 'unknown'}",
        f"Segments: {len(view.segments)}",
        "",
    ]

    if not view.segments:
        lines.append("No transcript segments found.")
        return "\n".join(lines)

    for segment in view.segments:
        lines.append(render_segment_line(segment))
    return "\n".join(lines)


def search_transcript_view(
    path: Path,
    view: TranscriptView,
    query: str,
    *,
    context_chars: int = 24,
) -> tuple[TranscriptSearchHitView, ...]:
    hits = search_transcript_file(path, query, context_chars=context_chars)
    return tuple(
        TranscriptSearchHitView(
            matched_text=hit.matched_text,
            start_seconds=hit.start_seconds,
            end_seconds=hit.end_seconds,
            context=hit.context,
            segment_index=_find_segment_index(view, hit.start_seconds, hit.end_seconds, hit.context, hit.matched_text),
        )
        for hit in hits
    )


def render_segment_line(segment: TranscriptSegmentView) -> str:
    return (
        f"[{format_timestamp(segment.start_seconds)} - {format_timestamp(segment.end_seconds)}] "
        f"{segment.text or '(empty segment)'}"
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


def _find_segment_index(
    view: TranscriptView,
    start_seconds: float | None,
    end_seconds: float | None,
    context: str,
    matched_text: str,
) -> int:
    for index, segment in enumerate(view.segments):
        if _segment_contains_time(segment, start_seconds, end_seconds):
            return index

    compact_context = _compact_for_lookup(context)
    compact_match = _compact_for_lookup(matched_text)
    for index, segment in enumerate(view.segments):
        compact_text = _compact_for_lookup(segment.text)
        if compact_context and compact_context in compact_text:
            return index
        if compact_match and compact_match in compact_text:
            return index
    return 0


def _segment_contains_time(
    segment: TranscriptSegmentView,
    start_seconds: float | None,
    end_seconds: float | None,
) -> bool:
    if start_seconds is None and end_seconds is None:
        return False
    segment_start = segment.start_seconds
    segment_end = segment.end_seconds
    if segment_start is None or segment_end is None:
        return False
    hit_start = segment_start if start_seconds is None else start_seconds
    hit_end = segment_end if end_seconds is None else end_seconds
    return segment_start <= hit_start <= segment_end and segment_start <= hit_end <= segment_end


def _compact_for_lookup(text: str) -> str:
    return "".join(text.replace("...", "").split())
