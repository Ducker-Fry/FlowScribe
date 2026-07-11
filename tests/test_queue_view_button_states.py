"""Button-state tests for QueueView selection and running state."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 not available", allow_module_level=True)

from flowscribe.gui.views.queue_view import QueueView
from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings


@pytest.fixture
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_queue_view_updates_buttons_for_completed_selection(qt_app, tmp_path):
    view = QueueView({})
    transcript = tmp_path / "item.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    item = QueueItem(
        item_id="completed",
        source=SourceSpec(kind="local", value=str(transcript)),
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="completed",
        transcript_path=transcript,
    )

    view.refresh_queue([item])
    view._checked_item_ids.add(item.item_id)
    view._sync_all_card_check_states()
    view._update_button_states()

    assert view._open_view_btn.isEnabled()
    assert not view._retry_btn.isEnabled()
    view.deleteLater()


def test_queue_view_updates_buttons_for_failed_selection(qt_app):
    view = QueueView({})
    item = QueueItem(
        item_id="failed",
        source=SourceSpec(kind="url", value="https://example.com/video"),
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="failed",
        error_message="network error",
    )

    view.refresh_queue([item])
    view._checked_item_ids.add(item.item_id)
    view._sync_all_card_check_states()
    view._update_button_states()

    assert not view._open_view_btn.isEnabled()
    assert view._retry_btn.isEnabled()
    view.deleteLater()
