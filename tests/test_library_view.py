"""Tests for the top-level library view."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from flowscribe.library import TranscriptLibraryEntry, TranscriptLibraryStore

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QListWidget
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 not available", allow_module_level=True)


@pytest.fixture
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _write_transcript(path: Path) -> None:
    path.write_text('{"segments": []}', encoding="utf-8")


def _entry(path: Path, label: str, *, opened: bool = False) -> TranscriptLibraryEntry:
    return TranscriptLibraryEntry.create(
        transcript_path=path,
        output_dir=path.parent,
        display_label=label,
        source_kind="local",
        created_at=datetime(2026, 5, 15, 10, 0, 0),
        last_opened_at=datetime(2026, 5, 15, 11, 0, 0) if opened else None,
    )


def test_library_view_filters_use_query_enum_values(qt_app, tmp_path):
    from flowscribe.gui.views.library_view import LibraryView

    available_path = tmp_path / "alpha.json"
    missing_path = tmp_path / "beta.json"
    _write_transcript(available_path)
    _write_transcript(missing_path)
    available = _entry(available_path, "Alpha", opened=True)
    missing = _entry(missing_path, "Beta")
    missing_path.unlink()

    store = TranscriptLibraryStore(tmp_path / "library.json")
    store.save_entries((available, missing))
    view = LibraryView(library_store=store)

    view._missing_filter_combo.setCurrentIndex(
        view._missing_filter_combo.findData("missing_only")
    )
    assert [entry.display_label for entry in view._entries_cache] == ["Beta"]

    view._missing_filter_combo.setCurrentIndex(view._missing_filter_combo.findData("all"))
    view._opened_filter_combo.setCurrentIndex(
        view._opened_filter_combo.findData("never_opened")
    )
    assert [entry.display_label for entry in view._entries_cache] == ["Beta"]

    view._opened_filter_combo.setCurrentIndex(view._opened_filter_combo.findData("all"))
    view._search_input.setText("alpha")
    assert [entry.display_label for entry in view._entries_cache] == ["Alpha"]

    view.deleteLater()


def test_library_view_multiselect_emits_batch_remove(qt_app, tmp_path):
    from flowscribe.gui.views.library_view import LibraryView

    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    _write_transcript(first_path)
    _write_transcript(second_path)
    first = _entry(first_path, "First")
    second = _entry(second_path, "Second")
    store = TranscriptLibraryStore(tmp_path / "library.json")
    store.save_entries((first, second))
    view = LibraryView(library_store=store)

    emitted: list[list[TranscriptLibraryEntry]] = []
    view.entries_remove_requested.connect(lambda entries: emitted.append(entries))
    view._entries_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    view._entries_list.item(0).setSelected(True)
    view._entries_list.item(1).setSelected(True)

    view._on_remove_entry()

    assert len(emitted) == 1
    assert {entry.display_label for entry in emitted[0]} == {"First", "Second"}
    assert first_path.is_file()
    assert second_path.is_file()
    view.deleteLater()


def test_library_view_detail_lists_outputs(qt_app, tmp_path):
    from flowscribe.library import LibraryOutputRecord
    from flowscribe.gui.views.library_view import LibraryView

    transcript = tmp_path / "lesson.json"
    txt = tmp_path / "lesson.txt"
    _write_transcript(transcript)
    txt.write_text("hello", encoding="utf-8")
    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=tmp_path,
        display_label="Lesson",
        outputs=(LibraryOutputRecord.from_path(transcript), LibraryOutputRecord.from_path(txt)),
    )
    store = TranscriptLibraryStore(tmp_path / "library.json")
    store.save_entries((entry,))
    view = LibraryView(library_store=store)

    view._entries_list.setCurrentRow(0)
    view._on_selection_changed()

    assert view._outputs_list.count() == 2
    assert "JSON" in view._outputs_list.item(0).text()
    view.deleteLater()
