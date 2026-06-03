"""Library controls mixin for MainWindow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from flowscribe.library import (
    TranscriptLibraryEntry,
    filter_transcript_library_entries,
    sort_transcript_library_entries,
)
from flowscribe.gui.utils import (
    _build_library_entry,
    _infer_library_source_kind_from_result,
    _infer_library_source_media_path_from_result,
    _library_entry_list_label,
    _library_results_summary,
)

if TYPE_CHECKING:
    from flowscribe.gui.new_main_window import NewMainWindow as MainWindow


class LibraryControlsMixin:
    """Mixin providing transcript library management methods for MainWindow."""

    def _show_transcript_library(self: MainWindow) -> None:
        self._refresh_transcript_library_list()
        self._select_view_tab("library")
        self.status_label.setText("Showing transcript library in Views.")

    def _index_transcript_in_library(
        self: MainWindow,
        transcript_path: Path,
        *,
        output_dir: Path | None = None,
        display_label: str | None = None,
        source_kind: str = "unknown",
        source_media_path: Path | None = None,
        media_path: Path | None = None,
        output_paths: tuple[Path, ...] | None = None,
        opened_at: datetime | None = None,
    ) -> TranscriptLibraryEntry:
        existing = self._library_store.get_entry_by_transcript_path(transcript_path)
        entry = _build_library_entry(
            transcript_path,
            output_dir=output_dir,
            display_label=display_label,
            source_kind=source_kind,
            source_media_path=source_media_path,
            media_path=media_path,
            output_paths=output_paths,
            opened_at=opened_at,
            existing=existing,
        )
        saved = self._library_store.upsert_entry(entry)
        self._refresh_transcript_library_list()
        return saved

    def _index_result_in_library(self: MainWindow, result) -> None:
        source_kind = _infer_library_source_kind_from_result(result)
        for artifacts in result.outputs:
            transcript_paths = [
                path
                for path in artifacts.paths
                if path.suffix.lower() == ".json"
            ]
            for transcript_path in transcript_paths:
                self._index_transcript_in_library(
                    transcript_path,
                    output_dir=result.job.output_dir,
                    display_label=getattr(result.job, "output_name_base", None),
                    source_kind=source_kind,
                    source_media_path=(
                        artifacts.media_path
                        or _infer_library_source_media_path_from_result(
                            result,
                            transcript_path,
                        )
                    ),
                    media_path=artifacts.media_path if artifacts.auto_bind_media else None,
                    output_paths=tuple(artifacts.paths),
                )

    def _index_queue_result_in_library(self: MainWindow, item, result) -> None:
        source_kind = _infer_library_source_kind_from_result(result)
        display_label = item.title or item.display_label
        for artifacts in result.outputs:
            transcript_paths = [path for path in artifacts.paths if path.suffix.lower() == ".json"]
            for transcript_path in transcript_paths:
                self._index_transcript_in_library(
                    transcript_path,
                    output_dir=result.job.output_dir,
                    display_label=display_label,
                    source_kind=source_kind,
                    source_media_path=(
                        artifacts.media_path
                        or _infer_library_source_media_path_from_result(result, transcript_path)
                    ),
                    media_path=artifacts.media_path if artifacts.auto_bind_media else None,
                    output_paths=tuple(artifacts.paths),
                )

    def _remove_transcript_from_library(self: MainWindow, transcript_path: Path) -> bool:
        removed = self._library_store.remove_entry_by_transcript_path(transcript_path)
        if removed:
            self._refresh_transcript_library_list()
        return removed

    def _remove_missing_library_entries(self: MainWindow) -> int:
        removed = self._library_store.remove_missing_entries()
        return len(removed)

    def _clean_missing_library_entries(self: MainWindow) -> None:
        removed = self._remove_missing_library_entries()
        self._refresh_transcript_library_list()
        if removed:
            self.status_label.setText(
                f"Removed {removed} missing transcript entr{'y' if removed == 1 else 'ies'} from the library."
            )
        else:
            self.status_label.setText("No missing transcript entries needed cleanup.")

    def _refresh_transcript_library_list(self: MainWindow) -> None:
        all_entries = self._library_store.list_entries()
        source_kind = (
            self._library_source_filter_combo.currentData()
            if self._library_source_filter_combo is not None
            else "all"
        )
        missing_filter = (
            self._library_missing_filter_combo.currentData()
            if self._library_missing_filter_combo is not None
            else "all"
        )
        opened_filter = (
            self._library_opened_filter_combo.currentData()
            if self._library_opened_filter_combo is not None
            else "all"
        )
        sort_mode = (
            self._library_sort_combo.currentData()
            if self._library_sort_combo is not None
            else "last_opened"
        )
        descending = (
            self._library_sort_direction_combo.currentData() != "asc"
            if self._library_sort_direction_combo is not None
            else True
        )
        entries = sort_transcript_library_entries(
            filter_transcript_library_entries(
                all_entries,
                source_kind=source_kind,
                missing_filter=missing_filter,
                opened_filter=opened_filter,
            ),
            sort_mode=sort_mode,
            descending=descending,
        )
        self._library_entries_cache = entries
        if self._library_summary_label is not None:
            summary = _library_results_summary(entries, total_count=len(all_entries))
            if any(entry.missing for entry in all_entries):
                summary += " | Use Clean Missing Entries to drop broken transcript records."
            self._library_summary_label.setText(summary)
        if self._library_entries_list is None:
            return
        self._library_entries_list.clear()
        for entry in entries:
            self._library_entries_list.addItem(_library_entry_list_label(entry))

    def _selected_library_entry(self: MainWindow) -> TranscriptLibraryEntry | None:
        if self._library_entries_list is None:
            return None
        row = self._library_entries_list.currentRow()
        if row < 0 or row >= len(self._library_entries_cache):
            return None
        return self._library_entries_cache[row]

    def _open_selected_library_transcript(self: MainWindow, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        transcript_path = entry.transcript_path
        if not transcript_path.is_file():
            self.status_label.setText(
                f"Transcript is missing: {transcript_path}. Clean missing entries or restore the file before reopening it."
            )
            self._refresh_transcript_library_list()
            return
        self._load_transcript_json(transcript_path)

    def _open_selected_library_output_dir(self: MainWindow, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        self._open_recent_output_dir(entry.output_dir)

    def _rebind_selected_library_media(self: MainWindow, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        if not entry.transcript_path.is_file():
            self.status_label.setText(
                f"Transcript is missing: {entry.transcript_path}. Clean missing entries or restore the file before rebinding media."
            )
            self._refresh_transcript_library_list()
            return
        if not self._load_transcript_json(entry.transcript_path):
            return
        self._bind_media_to_transcript()

    def _remove_selected_library_entry(self: MainWindow, *_args) -> None:
        entry = self._selected_library_entry()
        if entry is None:
            self.status_label.setText("Select a transcript library entry first.")
            return
        removed = self._library_store.remove_entry(entry.entry_id)
        disk_removed = _remove_library_output_dir(entry.output_dir)
        self._refresh_transcript_library_list()
        if removed:
            self.status_label.setText(
                f"Removed transcript and deleted output directory: {entry.output_dir.name}"
            )
            if not disk_removed:
                self.status_label.setText(
                    f"Removed library entry, but could not fully delete output directory: {entry.output_dir}"
                )
            return
        self.status_label.setText("Could not remove the selected library entry.")


def _remove_library_output_dir(output_dir: Path) -> bool:
    try:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        return True
    except OSError:
        return False
