"""Search structured transcript JSON files and locate keyword timestamps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from flowscribe.core.errors import SearchError


@dataclass(frozen=True)
class SearchHit:
    file: Path
    query: str
    matched_text: str
    start_seconds: float | None
    end_seconds: float | None
    context: str


def search_transcript_file(path: Path, query: str, *, context_chars: int = 24) -> tuple[SearchHit, ...]:
    query = query.strip()
    if not query:
        raise SearchError("Search query cannot be empty.")
    if not path.exists():
        raise SearchError(f"Transcript JSON does not exist: {path}")
    if path.suffix.lower() != ".json":
        raise SearchError(f"Search currently expects a .json transcript: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchError(f"Could not read transcript JSON {path}: {exc}") from exc

    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise SearchError(f"Transcript JSON has no segments list: {path}")

    hits: list[SearchHit] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        hits.extend(_search_segment(path, query, segment, context_chars=context_chars))
    return tuple(hits)


def _search_segment(
    path: Path,
    query: str,
    segment: dict,
    *,
    context_chars: int,
) -> tuple[SearchHit, ...]:
    text = str(segment.get("text") or "")
    if not text:
        return ()

    timed_hits = _search_timed_words(path, query, segment, text, context_chars=context_chars)
    if timed_hits:
        return timed_hits

    return tuple(
        SearchHit(
            file=path,
            query=query,
            matched_text=text[index : index + len(query)],
            start_seconds=_optional_float(segment.get("start_seconds")),
            end_seconds=_optional_float(segment.get("end_seconds")),
            context=_context(text, index, len(query), context_chars=context_chars),
        )
        for index in _find_all(text, query)
    )


def _search_timed_words(
    path: Path,
    query: str,
    segment: dict,
    text: str,
    *,
    context_chars: int,
) -> tuple[SearchHit, ...]:
    words = segment.get("words") or []
    if not isinstance(words, list):
        return ()

    indexed_words = [
        word
        for word in words
        if isinstance(word, dict) and str(word.get("text") or "").strip()
    ]
    if not indexed_words:
        return ()

    compact_query = _compact(query)
    compact_text = "".join(_compact(str(word.get("text") or "")) for word in indexed_words)
    hits: list[SearchHit] = []
    for compact_index in _find_all(compact_text, compact_query):
        start_word, end_word = _locate_word_span(indexed_words, compact_index, len(compact_query))
        text_index = text.find(query)
        hits.append(
            SearchHit(
                file=path,
                query=query,
                matched_text=query,
                start_seconds=_optional_float(start_word.get("start_seconds")),
                end_seconds=_optional_float(end_word.get("end_seconds")),
                context=_context(
                    text,
                    text_index if text_index >= 0 else 0,
                    len(query),
                    context_chars=context_chars,
                ),
            )
        )
    return tuple(hits)


def _locate_word_span(words: list[dict], compact_index: int, length: int) -> tuple[dict, dict]:
    offset = 0
    start_word = words[0]
    end_word = words[-1]
    span_end = compact_index + length

    for word in words:
        word_length = len(_compact(str(word.get("text") or "")))
        next_offset = offset + word_length
        if offset <= compact_index < next_offset:
            start_word = word
        if offset < span_end <= next_offset:
            end_word = word
            break
        offset = next_offset
    return start_word, end_word


def _find_all(text: str, query: str) -> tuple[int, ...]:
    if not query:
        return ()
    indexes: list[int] = []
    start = 0
    while True:
        index = text.find(query, start)
        if index < 0:
            break
        indexes.append(index)
        start = index + max(1, len(query))
    return tuple(indexes)


def _context(text: str, index: int, length: int, *, context_chars: int) -> str:
    start = max(0, index - context_chars)
    end = min(len(text), index + length + context_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _compact(text: str) -> str:
    return "".join(text.split())


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)
