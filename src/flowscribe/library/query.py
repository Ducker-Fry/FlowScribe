"""Filtering and sorting helpers for transcript library entries."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .models import LibrarySourceKind, TranscriptLibraryEntry

LibraryMissingFilter = Literal["all", "missing_only", "available_only"]
LibraryOpenedFilter = Literal["all", "opened", "never_opened"]
LibrarySortMode = Literal["last_opened", "updated", "created", "label"]


def filter_transcript_library_entries(
    entries: tuple[TranscriptLibraryEntry, ...],
    *,
    source_kind: LibrarySourceKind | Literal["all"] = "all",
    missing_filter: LibraryMissingFilter = "all",
    opened_filter: LibraryOpenedFilter = "all",
) -> tuple[TranscriptLibraryEntry, ...]:
    return tuple(
        entry
        for entry in entries
        if _matches_source_kind(entry, source_kind)
        and _matches_missing_filter(entry, missing_filter)
        and _matches_opened_filter(entry, opened_filter)
    )


def sort_transcript_library_entries(
    entries: tuple[TranscriptLibraryEntry, ...],
    *,
    sort_mode: LibrarySortMode = "last_opened",
    descending: bool = True,
) -> tuple[TranscriptLibraryEntry, ...]:
    return tuple(
        sorted(
            entries,
            key=lambda entry: _sort_key(entry, sort_mode),
            reverse=descending,
        )
    )


def _matches_source_kind(
    entry: TranscriptLibraryEntry,
    source_kind: LibrarySourceKind | Literal["all"],
) -> bool:
    return source_kind == "all" or entry.source_kind == source_kind


def _matches_missing_filter(
    entry: TranscriptLibraryEntry,
    missing_filter: LibraryMissingFilter,
) -> bool:
    if missing_filter == "missing_only":
        return entry.missing
    if missing_filter == "available_only":
        return not entry.missing
    return True


def _matches_opened_filter(
    entry: TranscriptLibraryEntry,
    opened_filter: LibraryOpenedFilter,
) -> bool:
    if opened_filter == "opened":
        return entry.last_opened_at is not None
    if opened_filter == "never_opened":
        return entry.last_opened_at is None
    return True


def _sort_key(
    entry: TranscriptLibraryEntry,
    sort_mode: LibrarySortMode,
) -> tuple[object, ...]:
    if sort_mode == "created":
        return (
            entry.created_at,
            entry.updated_at,
            entry.display_label.lower(),
        )
    if sort_mode == "updated":
        return (
            entry.updated_at,
            entry.last_opened_at or datetime.min,
            entry.display_label.lower(),
        )
    if sort_mode == "label":
        return (
            entry.display_label.lower(),
            entry.last_opened_at or datetime.min,
            entry.updated_at,
        )
    return (
        entry.last_opened_at is not None,
        entry.last_opened_at or datetime.min,
        entry.updated_at,
        entry.created_at,
        entry.display_label.lower(),
    )
