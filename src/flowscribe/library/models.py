"""Models for the local transcript library."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Literal

LibrarySourceKind = Literal["local", "url", "capture", "unknown"]
LibraryOutputKind = Literal["txt", "md", "json", "srt", "vtt", "other"]


def normalize_library_path(path: Path) -> Path:
    """Normalize a path before persisting it in the library."""

    return path.expanduser().resolve()


def derive_library_entry_id(transcript_path: Path) -> str:
    normalized = str(normalize_library_path(transcript_path)).encode("utf-8")
    return sha1(normalized).hexdigest()


def detect_output_kind(path: Path) -> LibraryOutputKind:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return "txt"
    if suffix == ".md":
        return "md"
    if suffix == ".json":
        return "json"
    if suffix == ".srt":
        return "srt"
    if suffix == ".vtt":
        return "vtt"
    return "other"


@dataclass(frozen=True)
class LibraryOutputRecord:
    """One output artifact associated with a transcript entry."""

    path: Path
    kind: LibraryOutputKind

    @classmethod
    def from_path(cls, path: Path) -> "LibraryOutputRecord":
        normalized = normalize_library_path(path)
        return cls(path=normalized, kind=detect_output_kind(normalized))

    @property
    def missing(self) -> bool:
        return not self.path.is_file()


@dataclass(frozen=True)
class LibraryMediaBinding:
    """Media association stored alongside a transcript entry."""

    transcript_path: Path
    media_path: Path
    binding_type: str = "manual"
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        *,
        transcript_path: Path,
        media_path: Path,
        binding_type: str = "manual",
        updated_at: datetime | None = None,
    ) -> "LibraryMediaBinding":
        return cls(
            transcript_path=normalize_library_path(transcript_path),
            media_path=normalize_library_path(media_path),
            binding_type=binding_type.strip() or "manual",
            updated_at=updated_at or datetime.now(),
        )

    @property
    def missing(self) -> bool:
        return not self.media_path.is_file()


@dataclass(frozen=True)
class TranscriptLibraryEntry:
    """Durable metadata for one transcript and its related files."""

    entry_id: str
    transcript_path: Path
    output_dir: Path
    display_label: str
    source_kind: LibrarySourceKind = "unknown"
    source_media_path: Path | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_opened_at: datetime | None = None
    missing_paths: tuple[str, ...] = ()
    media_binding: LibraryMediaBinding | None = None
    outputs: tuple[LibraryOutputRecord, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        transcript_path: Path,
        output_dir: Path,
        display_label: str,
        source_kind: LibrarySourceKind = "unknown",
        source_media_path: Path | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_opened_at: datetime | None = None,
        media_binding: LibraryMediaBinding | None = None,
        outputs: tuple[LibraryOutputRecord, ...] = (),
    ) -> "TranscriptLibraryEntry":
        normalized_transcript = normalize_library_path(transcript_path)
        normalized_output_dir = normalize_library_path(output_dir)
        normalized_source_media = (
            normalize_library_path(source_media_path)
            if source_media_path is not None
            else None
        )
        timestamp = created_at or datetime.now()
        entry = cls(
            entry_id=derive_library_entry_id(normalized_transcript),
            transcript_path=normalized_transcript,
            output_dir=normalized_output_dir,
            display_label=display_label.strip() or normalized_transcript.stem,
            source_kind=source_kind,
            source_media_path=normalized_source_media,
            created_at=timestamp,
            updated_at=updated_at or timestamp,
            last_opened_at=last_opened_at,
            media_binding=media_binding,
            outputs=tuple(outputs),
        )
        return entry.refresh_missing_status()

    @property
    def missing(self) -> bool:
        return bool(self.missing_paths)

    def refresh_missing_status(self) -> "TranscriptLibraryEntry":
        missing_paths: list[str] = []
        if not self.transcript_path.is_file():
            missing_paths.append("transcript")
        if self.source_media_path is not None and not self.source_media_path.is_file():
            missing_paths.append("source_media")
        if not self.output_dir.is_dir():
            missing_paths.append("output_dir")
        if self.media_binding is not None and self.media_binding.missing:
            missing_paths.append("bound_media")
        if any(output.missing for output in self.outputs):
            missing_paths.append("outputs")

        return TranscriptLibraryEntry(
            entry_id=self.entry_id,
            transcript_path=self.transcript_path,
            output_dir=self.output_dir,
            display_label=self.display_label,
            source_kind=self.source_kind,
            source_media_path=self.source_media_path,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_opened_at=self.last_opened_at,
            missing_paths=tuple(missing_paths),
            media_binding=self.media_binding,
            outputs=self.outputs,
        )
