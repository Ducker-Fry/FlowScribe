"""Library-related functions for the GUI layer.

All functions here are stateless pure functions that handle library operations.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flowscribe.gui.transcript_viewer import (
    load_transcript_view,
    resolve_transcript_media_path,
)
from flowscribe.library import (
    LibraryMediaBinding,
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    sort_transcript_library_entries,
)

LIBRARY_OUTPUT_SUFFIXES = (".txt", ".md", ".json", ".srt", ".vtt")


def _resolve_library_source_media_path(transcript_path: Path) -> Path | None:
    try:
        view = load_transcript_view(transcript_path)
    except ValueError:
        return None
    return resolve_transcript_media_path(view)


def _infer_library_source_kind_from_result(result) -> str:
    kinds = {
        source.kind
        for source in result.job.sources
        if getattr(source, "kind", None) in {"local", "url", "capture"}
    }
    if len(kinds) == 1:
        return next(iter(kinds))
    return "unknown"


def _infer_library_source_media_path_from_result(result, transcript_path: Path) -> Path | None:
    if len(result.job.sources) == 1:
        source = result.job.sources[0]
        if source.kind == "local":
            candidate = Path(source.value)
            if candidate.is_file():
                return candidate.resolve()
    return _resolve_library_source_media_path(transcript_path)


def _merge_library_output_records(
    existing: tuple[LibraryOutputRecord, ...],
    incoming: tuple[LibraryOutputRecord, ...],
) -> tuple[LibraryOutputRecord, ...]:
    merged: dict[Path, LibraryOutputRecord] = {}
    for record in existing + incoming:
        merged[record.path] = record
    return tuple(merged.values())


def _transcript_output_records_from_paths(paths: tuple[Path, ...]) -> tuple[LibraryOutputRecord, ...]:
    seen: set[Path] = set()
    records: list[LibraryOutputRecord] = []
    for path in paths:
        try:
            normalized = path.expanduser().resolve()
        except OSError:
            normalized = path
        if normalized in seen:
            continue
        seen.add(normalized)
        records.append(LibraryOutputRecord.from_path(normalized))
    return tuple(records)


def _discover_transcript_output_paths(transcript_path: Path) -> tuple[Path, ...]:
    try:
        normalized = transcript_path.expanduser().resolve()
    except OSError:
        normalized = transcript_path
    discovered: list[Path] = []
    if normalized.is_file():
        discovered.append(normalized)
    for suffix in LIBRARY_OUTPUT_SUFFIXES:
        candidate = normalized.with_suffix(suffix)
        if candidate == normalized:
            continue
        if candidate.is_file():
            discovered.append(candidate)
    return tuple(discovered)


def _build_library_entry(
    transcript_path: Path,
    *,
    output_dir: Path | None = None,
    display_label: str | None = None,
    source_kind: str = "unknown",
    source_media_path: Path | None = None,
    media_path: Path | None = None,
    output_paths: tuple[Path, ...] | None = None,
    opened_at: datetime | None = None,
    existing: TranscriptLibraryEntry | None = None,
) -> TranscriptLibraryEntry:
    normalized_transcript = transcript_path.expanduser().resolve()
    resolved_output_dir = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else normalized_transcript.parent.resolve()
    )
    discovered_output_paths = (
        output_paths
        if output_paths is not None
        else _discover_transcript_output_paths(normalized_transcript)
    )
    merged_outputs = _merge_library_output_records(
        existing.outputs if existing is not None else (),
        _transcript_output_records_from_paths(discovered_output_paths),
    )
    effective_source_media_path = (
        source_media_path
        or (existing.source_media_path if existing is not None else None)
        or _resolve_library_source_media_path(normalized_transcript)
    )
    effective_source_kind = source_kind
    if effective_source_kind == "unknown" and existing is not None:
        effective_source_kind = existing.source_kind
    media_binding = existing.media_binding if existing is not None else None
    if media_path is not None:
        media_binding = LibraryMediaBinding.create(
            transcript_path=normalized_transcript,
            media_path=media_path,
            binding_type="manual",
            updated_at=opened_at or datetime.now(),
        )
    last_opened_at = opened_at if opened_at is not None else (existing.last_opened_at if existing else None)
    created_at = existing.created_at if existing is not None else (opened_at or datetime.now())

    return TranscriptLibraryEntry.create(
        transcript_path=normalized_transcript,
        output_dir=resolved_output_dir,
        display_label=(
            display_label
            or (existing.display_label if existing is not None else "")
            or normalized_transcript.stem
        ),
        source_kind=effective_source_kind,
        source_media_path=effective_source_media_path,
        created_at=created_at,
        updated_at=opened_at or datetime.now(),
        last_opened_at=last_opened_at,
        media_binding=media_binding,
        outputs=merged_outputs,
    )


def _library_entry_missing_summary(entry: TranscriptLibraryEntry) -> str:
    if not entry.missing_paths:
        return "ok"
    return ", ".join(entry.missing_paths)


def _sort_library_entries(
    entries: tuple[TranscriptLibraryEntry, ...],
) -> tuple[TranscriptLibraryEntry, ...]:
    return sort_transcript_library_entries(entries)


def _library_results_summary(
    entries: tuple[TranscriptLibraryEntry, ...],
    *,
    total_count: int,
) -> str:
    missing_count = sum(1 for entry in entries if entry.missing)
    opened_count = sum(1 for entry in entries if entry.last_opened_at is not None)
    return (
        f"Showing {len(entries)} of {total_count} transcript entr{'y' if total_count == 1 else 'ies'}"
        f" | missing: {missing_count}"
        f" | opened: {opened_count}"
    )


def _library_entry_list_label(entry: TranscriptLibraryEntry) -> str:
    from flowscribe.gui.utils.formatting import (
        _format_library_datetime,
    )

    return "\n".join(
        [
            entry.display_label,
            (
                f"Source: {entry.source_kind} | "
                f"Created: {_format_library_datetime(entry.created_at)} | "
                f"Last opened: {_format_library_datetime(entry.last_opened_at)}"
            ),
            (
                f"Output dir: {entry.output_dir} | "
                f"Missing: {_library_entry_missing_summary(entry)}"
            ),
        ]
    )


def _recent_transcript_list_label(
    transcript_path: Path,
    *,
    entry: TranscriptLibraryEntry | None = None,
) -> str:
    from flowscribe.gui.utils.formatting import (
        _format_library_datetime,
    )

    if entry is None:
        return f"{transcript_path.name}\n{transcript_path}"
    return "\n".join(
        [
            f"{transcript_path.name} | Source: {entry.source_kind} | Missing: {_library_entry_missing_summary(entry)}",
            f"Last opened: {_format_library_datetime(entry.last_opened_at)} | Output dir: {entry.output_dir}",
        ]
    )
