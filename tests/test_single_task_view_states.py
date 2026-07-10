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


def test_single_task_view_uses_remote_execution_backend(qt_app, monkeypatch):
    class _FakeSignal:
        def connect(self, _callback) -> None:
            return None

    class _FakeThread:
        def __init__(self, _parent=None) -> None:
            self.started = _FakeSignal()
            self.finished = _FakeSignal()

        def start(self) -> None:
            return None

        def quit(self) -> None:
            return None

        def deleteLater(self) -> None:
            return None

        def requestInterruption(self) -> None:
            return None

    class _FakeWorker:
        def __init__(
            self,
            job,
            *,
            execution_backend=None,
            execution_mode="local",
            server_target=None,
        ) -> None:
            self.job = job
            self.execution_backend = execution_backend
            self.execution_mode = execution_mode
            self.server_target = server_target
            self.progress = _FakeSignal()
            self.finished = _FakeSignal()
            self.failed = _FakeSignal()
            self.warning = _FakeSignal()

        def moveToThread(self, _thread) -> None:
            return None

        def run(self) -> None:
            return None

        def deleteLater(self) -> None:
            return None

    backend_calls: list[dict[str, object]] = []
    backend_sentinel = object()

    def _fake_build_execution_backend(**kwargs):
        backend_calls.append(kwargs)
        return backend_sentinel

    monkeypatch.setattr(
        "flowscribe.gui.views.single_task_view_runtime.build_execution_backend",
        _fake_build_execution_backend,
    )
    monkeypatch.setattr(
        "flowscribe.gui.views.single_task_view_runtime.TranscriptionWorker",
        _FakeWorker,
    )
    monkeypatch.setattr(
        "flowscribe.gui.views.single_task_view_runtime.QThread",
        _FakeThread,
    )

    view = SingleTaskView(
        {
            "execution_mode": "remote",
            "server_target": "http://127.0.0.1:18769",
            "remote_token": "secret",
            "remote_poll_seconds": 2.5,
            "download_artifacts": False,
        }
    )
    view.url_input.setText("https://example.com/video")

    view._start_transcription()

    assert backend_calls == [
        {
            "execution_mode": "remote",
            "server_target": "http://127.0.0.1:18769",
            "remote_token": "secret",
            "remote_poll_seconds": 2.5,
            "download_artifacts": False,
        }
    ]
    assert view._worker is not None
    assert view._worker.execution_backend is backend_sentinel
    assert view._worker.execution_mode == "remote"
    assert view._worker.server_target == "http://127.0.0.1:18769"
    view.deleteLater()


def test_single_task_view_recovers_remote_result(qt_app, monkeypatch, tmp_path):
    recovered_json = tmp_path / "recovered.json"
    recovered_json.write_text('{"segments": []}', encoding="utf-8")

    class _FakeBackend:
        def recover_task_result(self, task_id, output_dir, overwrite=True, progress=None):
            assert task_id == "remote-task-1"
            assert output_dir == tmp_path
            return {
                "ok": True,
                "outputs": [
                    {
                        "paths": [str(recovered_json)],
                    }
                ],
            }

    monkeypatch.setattr(
        "flowscribe.gui.views.single_task_view_runtime.build_execution_backend",
        lambda **kwargs: _FakeBackend(),
    )
    monkeypatch.setattr(
        "flowscribe.gui.views.single_task_view_runtime.QInputDialog.getText",
        lambda *args, **kwargs: ("remote-task-1", True),
    )

    view = SingleTaskView(
        {
            "execution_mode": "remote",
            "server_target": "aliyun-bj",
            "output_dir": tmp_path,
        }
    )

    view._recover_remote_result()

    assert view._last_transcript_path == recovered_json
    assert recovered_json in view._last_output_paths
    assert "remote-task-1" in view.status_label.text()
    view.deleteLater()
