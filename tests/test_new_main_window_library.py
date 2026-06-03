"""Tests for new main window library integration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from flowscribe.library import LibraryOutputRecord, TranscriptLibraryEntry, TranscriptLibraryStore

try:
    from PySide6.QtWidgets import QApplication
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


def test_library_open_transcript_loads_dialog_and_marks_opened(qt_app, tmp_path):
    from flowscribe.gui.new_main_window import NewMainWindow

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

    window = NewMainWindow()
    window._library_store = store
    window._library_view._library_store = store
    dialog = Mock()
    window._library_view_dialog = dialog

    window._on_library_open_transcript(entry)

    dialog.clear_content.assert_called_once()
    dialog._load_transcript_with_artifacts.assert_called_once_with(
        transcript.resolve(),
        (transcript.resolve(), txt.resolve()),
    )
    assert store.get_entry(entry.entry_id).last_opened_at is not None
    window.deleteLater()


def test_library_rebind_media_updates_binding(qt_app, tmp_path):
    from flowscribe.gui.new_main_window import NewMainWindow

    transcript = tmp_path / "lesson.json"
    media = tmp_path / "lesson.mp4"
    _write_transcript(transcript)
    media.write_bytes(b"media")
    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=tmp_path,
        display_label="Lesson",
        created_at=datetime(2026, 5, 15, 10, 0, 0),
    )
    store = TranscriptLibraryStore(tmp_path / "library.json")
    store.save_entries((entry,))

    window = NewMainWindow()
    window._library_store = store
    window._library_view._library_store = store
    with patch(
        "flowscribe.gui.new_main_window.QFileDialog.getOpenFileName",
        return_value=(str(media), ""),
    ):
        window._on_library_rebind_media(entry)

    updated = store.get_entry(entry.entry_id)
    assert updated is not None
    assert updated.media_binding is not None
    assert updated.media_binding.media_path == media.resolve()
    assert updated.transcript_path == transcript.resolve()
    window.deleteLater()
