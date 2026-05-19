"""Artifact-related functions for the GUI layer.

All functions here are stateless pure functions that handle artifact operations.
"""

from __future__ import annotations

from pathlib import Path

from flowscribe.library import LibraryOutputRecord

VIEW_ARTIFACT_SUFFIXES = (".json", ".txt", ".md", ".srt", ".vtt")


def _transcript_output_records_from_paths(paths: tuple[Path, ...]) -> tuple[LibraryOutputRecord, ...]:
    """Convert paths to LibraryOutputRecord objects.

    Note: This function is duplicated in library.py for organizational reasons.
    Both modules need this functionality independently.
    """
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
    """Discover all output files related to a transcript.

    Note: This function is duplicated in library.py for organizational reasons.
    Both modules need this functionality independently.
    """
    from flowscribe.gui.utils.library import LIBRARY_OUTPUT_SUFFIXES

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


def _is_viewable_artifact_path(path: Path) -> bool:
    return path.suffix.lower() in VIEW_ARTIFACT_SUFFIXES


def _normalize_viewable_artifact_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if not _is_viewable_artifact_path(path):
            continue
        try:
            candidate = path.expanduser().resolve()
        except OSError:
            candidate = path
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(normalized)


def _sort_workspace_artifact_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    from flowscribe.gui.utils.formatting import _artifact_compare_group

    priorities = {
        "transcript_json": 0,
        "corrected_json": 1,
        "srt": 2,
        "vtt": 3,
        "md": 4,
        "txt": 5,
        "other": 6,
    }
    return tuple(
        sorted(
            paths,
            key=lambda path: (
                priorities.get(_artifact_compare_group(path), 99),
                path.name.lower(),
            ),
        )
    )


def _read_viewable_artifact_text(path: Path) -> str:
    from flowscribe.gui.utils.formatting import _render_viewable_artifact_text

    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return _render_viewable_artifact_text(path, path.read_text(encoding=encoding))
        except UnicodeError:
            continue
    return _render_viewable_artifact_text(
        path,
        path.read_text(encoding="utf-8", errors="replace"),
    )
