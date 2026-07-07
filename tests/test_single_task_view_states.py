"""State-management tests for SingleTaskView."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 not available", allow_module_level=True)

from flowscribe.gui.views.single_task_view import SingleTaskView


@pytest.fixture
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_single_task_view_capture_state_disables_start(qt_app):
    view = SingleTaskView({})

    assert view.start_button.isEnabled()
    assert not view.capture_stop_button.isEnabled()

    view._start_capture()

    assert not view.start_button.isEnabled()
    assert not view.capture_start_button.isEnabled()
    assert view.capture_stop_button.isEnabled()

    view._stop_capture()

    assert view.start_button.isEnabled()
    assert view.capture_start_button.isEnabled()
    assert not view.capture_stop_button.isEnabled()
    view.deleteLater()


def test_single_task_view_buttons_reset_after_finished(qt_app, tmp_path):
    view = SingleTaskView({})
    transcript_path = tmp_path / "done.json"
    transcript_path.write_text('{"segments": []}', encoding="utf-8")

    view._thread = object()
    view._worker = object()
    view._cancel_requested = False
    view._refresh_action_buttons()
    assert not view.start_button.isEnabled()
    assert view.cancel_button.isEnabled()

    result = SimpleNamespace(
        canceled=False,
        succeeded=1,
        failed=0,
        elapsed_seconds=2.5,
        errors=[],
        outputs=[SimpleNamespace(paths=[transcript_path])],
        job=SimpleNamespace(output_dir=tmp_path),
    )

    view._on_finished(result)

    assert view.start_button.isEnabled()
    assert not view.cancel_button.isEnabled()
    assert view._last_transcript_path == transcript_path
    view.deleteLater()


def test_single_task_view_failure_restores_buttons(qt_app):
    view = SingleTaskView({})
    view._thread = object()
    view._worker = object()
    view._cancel_requested = False
    view._refresh_action_buttons()

    view._on_failed("boom")

    assert view.start_button.isEnabled()
    assert not view.cancel_button.isEnabled()
    assert "boom" in view.status_label.text()
    view.deleteLater()
