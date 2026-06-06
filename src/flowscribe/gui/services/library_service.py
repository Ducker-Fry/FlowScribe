"""Shared library operations for GUI windows."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil

from flowscribe.gui.utils.library import _discover_transcript_output_paths
from flowscribe.library import LibraryOutputRecord, TranscriptLibraryEntry, TranscriptLibraryStore
from flowscribe.library.models import LibraryMediaBinding


def build_library_entry_from_artifacts(
    transcript_path: Path,
    *,
    display_label: str | None = None,
    artifacts=None,
    output_dir: Path | None = None,
) -> TranscriptLibraryEntry:
    output_paths = _discover_transcript_output_paths(transcript_path)
    outputs = tuple(LibraryOutputRecord.from_path(p) for p in output_paths)

    media_path = None
    source_media_path = None
    media_binding = None
    if artifacts is not None:
        if artifacts.media_path is not None:
            media_path = (
                Path(artifacts.media_path)
                if isinstance(artifacts.media_path, str)
                else artifacts.media_path
            )
            source_media_path = media_path
            if artifacts.auto_bind_media:
                media_binding = LibraryMediaBinding.create(
                    transcript_path=transcript_path,
                    media_path=media_path,
                    binding_type="auto",
                )
        source_kind = artifacts.source_kind or "local"
    else:
        source_kind = "local"

    return TranscriptLibraryEntry.create(
        transcript_path=transcript_path,
        output_dir=output_dir or transcript_path.parent,
        display_label=display_label or transcript_path.stem,
        source_kind=source_kind,
        outputs=outputs,
        source_media_path=source_media_path,
        media_binding=media_binding,
    )


def upsert_library_entry_from_artifacts(
    store: TranscriptLibraryStore,
    transcript_path: Path,
    *,
    display_label: str | None = None,
    artifacts=None,
    output_dir: Path | None = None,
) -> TranscriptLibraryEntry:
    entry = build_library_entry_from_artifacts(
        transcript_path,
        display_label=display_label,
        artifacts=artifacts,
        output_dir=output_dir,
    )
    return store.upsert_entry(entry)


def ensure_library_entry_outputs(
    store: TranscriptLibraryStore,
    entry: TranscriptLibraryEntry,
) -> TranscriptLibraryEntry:
    if entry.outputs:
        return entry
    output_paths = _discover_transcript_output_paths(entry.transcript_path)
    if not output_paths:
        return entry
    updated = replace(
        entry,
        outputs=tuple(LibraryOutputRecord.from_path(path) for path in output_paths),
    ).refresh_missing_status()
    return store.upsert_entry(updated)


def remove_library_entry_and_output_dir(
    store: TranscriptLibraryStore,
    entry: TranscriptLibraryEntry,
) -> tuple[bool, bool]:
    removed = store.remove_entry(entry.entry_id)
    disk_removed = True
    try:
        if entry.output_dir.exists():
            shutil.rmtree(entry.output_dir)
    except OSError:
        disk_removed = False
    return removed, disk_removed
