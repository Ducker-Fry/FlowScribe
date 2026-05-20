"""JSON-backed local transcript library storage."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .models import (
    LibraryMediaBinding,
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    normalize_library_path,
)

LIBRARY_STORE_VERSION = 1


class TranscriptLibraryStore:
    """Read and write the durable transcript library index."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    def list_entries(self) -> tuple[TranscriptLibraryEntry, ...]:
        return tuple(
            entry.refresh_missing_status()
            for entry in self._load_entries_from_disk()
        )

    def get_entry(self, entry_id: str) -> TranscriptLibraryEntry | None:
        for entry in self.list_entries():
            if entry.entry_id == entry_id:
                return entry
        return None

    def get_entry_by_transcript_path(self, transcript_path: Path) -> TranscriptLibraryEntry | None:
        normalized = normalize_library_path(transcript_path)
        for entry in self.list_entries():
            if entry.transcript_path == normalized:
                return entry
        return None

    def save_entries(self, entries: tuple[TranscriptLibraryEntry, ...]) -> None:
        payload = {
            "version": LIBRARY_STORE_VERSION,
            "entries": [self._entry_to_payload(entry.refresh_missing_status()) for entry in entries],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return

    def upsert_entry(self, entry: TranscriptLibraryEntry) -> TranscriptLibraryEntry:
        entries = list(self.list_entries())
        refreshed = entry.refresh_missing_status()
        for index, existing in enumerate(entries):
            if existing.entry_id == refreshed.entry_id:
                entries[index] = refreshed
                self.save_entries(tuple(entries))
                return refreshed
        entries.append(refreshed)
        self.save_entries(tuple(entries))
        return refreshed

    def remove_entry(self, entry_id: str) -> bool:
        entries = list(self.list_entries())
        remaining = [entry for entry in entries if entry.entry_id != entry_id]
        if len(remaining) == len(entries):
            return False
        self.save_entries(tuple(remaining))
        return True

    def remove_entry_by_transcript_path(self, transcript_path: Path) -> bool:
        entry = self.get_entry_by_transcript_path(transcript_path)
        if entry is None:
            return False
        return self.remove_entry(entry.entry_id)

    def mark_opened(
        self,
        entry_id: str,
        *,
        opened_at: datetime | None = None,
    ) -> TranscriptLibraryEntry | None:
        entries = list(self.list_entries())
        for index, entry in enumerate(entries):
            if entry.entry_id != entry_id:
                continue
            updated = replace(
                entry,
                last_opened_at=opened_at or datetime.now(),
                updated_at=opened_at or datetime.now(),
            ).refresh_missing_status()
            entries[index] = updated
            self.save_entries(tuple(entries))
            return updated
        return None

    def refresh_missing_statuses(self) -> tuple[TranscriptLibraryEntry, ...]:
        entries = tuple(entry.refresh_missing_status() for entry in self.list_entries())
        self.save_entries(entries)
        return entries

    def remove_missing_entries(self) -> tuple[TranscriptLibraryEntry, ...]:
        entries = list(self.list_entries())
        removed = tuple(entry for entry in entries if entry.missing)
        if not removed:
            return ()
        remaining = tuple(entry for entry in entries if not entry.missing)
        self.save_entries(remaining)
        return removed

    def _load_entries_from_disk(self) -> list[TranscriptLibraryEntry]:
        try:
            is_file = self.path.is_file()
        except OSError:
            return []
        if not is_file:
            return []

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError:
            return []
        except json.JSONDecodeError:
            self._recover_corrupt_store_file()
            return []

        entries_payload = payload.get("entries")
        if not isinstance(entries_payload, list):
            self._recover_corrupt_store_file()
            return []

        entries: list[TranscriptLibraryEntry] = []
        for raw_entry in entries_payload:
            try:
                entries.append(self._entry_from_payload(raw_entry))
            except (KeyError, TypeError, ValueError):
                continue
        return entries

    def _recover_corrupt_store_file(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = self.path.with_suffix(f"{self.path.suffix}.corrupt-{timestamp}")
        try:
            self.path.replace(backup_path)
        except OSError:
            return

    def _entry_from_payload(self, payload: object) -> TranscriptLibraryEntry:
        if not isinstance(payload, dict):
            raise ValueError("Library entry payload must be an object.")

        transcript_path = Path(str(payload["transcript_path"]))
        output_dir = Path(str(payload["output_dir"]))
        source_media_raw = payload.get("source_media_path")
        source_media_path = (
            None if source_media_raw in (None, "") else Path(str(source_media_raw))
        )

        media_binding_payload = payload.get("media_binding")
        media_binding = (
            None
            if not isinstance(media_binding_payload, dict)
            else LibraryMediaBinding.create(
                transcript_path=Path(str(media_binding_payload["transcript_path"])),
                media_path=Path(str(media_binding_payload["media_path"])),
                binding_type=str(media_binding_payload.get("binding_type") or "manual"),
                updated_at=_parse_datetime(media_binding_payload.get("updated_at")),
            )
        )

        outputs_payload = payload.get("outputs")
        outputs: list[LibraryOutputRecord] = []
        if isinstance(outputs_payload, list):
            for raw_output in outputs_payload:
                if not isinstance(raw_output, dict):
                    continue
                output_path = raw_output.get("path")
                if not isinstance(output_path, str) or not output_path.strip():
                    continue
                outputs.append(LibraryOutputRecord.from_path(Path(output_path)))

        entry = TranscriptLibraryEntry(
            entry_id=str(payload.get("entry_id") or ""),
            transcript_path=normalize_library_path(transcript_path),
            output_dir=normalize_library_path(output_dir),
            display_label=str(payload.get("display_label") or transcript_path.stem),
            source_kind=str(payload.get("source_kind") or "unknown"),
            source_media_path=(
                None if source_media_path is None else normalize_library_path(source_media_path)
            ),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
            last_opened_at=_parse_optional_datetime(payload.get("last_opened_at")),
            missing_paths=tuple(
                item
                for item in payload.get("missing_paths", [])
                if isinstance(item, str) and item.strip()
            ),
            media_binding=media_binding,
            outputs=tuple(outputs),
        )
        if not entry.entry_id:
            entry = replace(
                entry,
                entry_id=TranscriptLibraryEntry.create(
                    transcript_path=entry.transcript_path,
                    output_dir=entry.output_dir,
                    display_label=entry.display_label,
                    source_kind=entry.source_kind,
                    source_media_path=entry.source_media_path,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                    last_opened_at=entry.last_opened_at,
                    media_binding=entry.media_binding,
                    outputs=entry.outputs,
                ).entry_id,
            )
        return entry.refresh_missing_status()

    def _entry_to_payload(self, entry: TranscriptLibraryEntry) -> dict[str, object]:
        return {
            "entry_id": entry.entry_id,
            "transcript_path": str(entry.transcript_path),
            "output_dir": str(entry.output_dir),
            "display_label": entry.display_label,
            "source_kind": entry.source_kind,
            "source_media_path": (
                None if entry.source_media_path is None else str(entry.source_media_path)
            ),
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "last_opened_at": (
                None if entry.last_opened_at is None else entry.last_opened_at.isoformat()
            ),
            "missing_paths": list(entry.missing_paths),
            "media_binding": (
                None
                if entry.media_binding is None
                else {
                    "transcript_path": str(entry.media_binding.transcript_path),
                    "media_path": str(entry.media_binding.media_path),
                    "binding_type": entry.media_binding.binding_type,
                    "updated_at": entry.media_binding.updated_at.isoformat(),
                }
            ),
            "outputs": [
                {
                    "path": str(output.path),
                    "kind": output.kind,
                }
                for output in entry.outputs
            ],
        }


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Library datetime field is missing.")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Library optional datetime field must be a string.")
    return datetime.fromisoformat(value)
