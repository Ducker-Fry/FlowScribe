from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from flowscribe.gui.remote_targets import inspect_remote_target
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.gui.windows.new_main_window_queue import NewMainWindowQueueMixin


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_queue_view_loads_remote_execution_defaults(qapp, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))
    view = QueueView(
        {
            "execution_mode": "remote",
            "server_target": "http://127.0.0.1:18769",
            "remote_token": "secret",
            "remote_poll_seconds": 2.5,
            "download_artifacts": False,
        }
    )

    settings = view.get_execution_settings()

    assert settings["execution_mode"] == "remote"
    assert settings["server_target"] == "http://127.0.0.1:18769"
    assert settings["remote_token"] == "secret"
    assert settings["remote_poll_seconds"] == 2.5
    assert settings["download_artifacts"] is False
    assert "Direct URL" in view._resolved_target_label.text()


class _DummyStatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str) -> None:
        self.messages.append(message)


class _DummyQueueView:
    def get_download_options(self) -> dict[str, object]:
        return {
            "quality": "best",
            "prefer_format": None,
            "preserve_media": False,
            "media_kind": "audio",
        }


class _DummyQueueStore:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, item):
        self.items.append(item)
        return item

    def load_items(self):
        return list(self.items)


class _DummyWindow(NewMainWindowQueueMixin):
    def __init__(self) -> None:
        self._settings = {
            "output_dir": "outputs",
            "output_name_base": "",
            "execution_mode": "remote",
            "server_target": "http://127.0.0.1:18769",
            "remote_token": "secret",
            "remote_poll_seconds": 2.0,
            "download_artifacts": False,
            "provider_name": "local-whisper",
            "model_name": "small",
            "language": None,
            "preset": None,
            "output_formats": ("json",),
            "timestamps": True,
            "word_timestamps": False,
            "overwrite": False,
            "network_family": "auto",
            "proxy": None,
            "cookies_path": None,
            "progressive_enabled": True,
            "progressive_resume": True,
            "progressive_chunk_seconds": 30.0,
            "progressive_max_workers": 1,
            "native_threads": None,
        }
        self._queue_view = _DummyQueueView()
        self._queue_store = _DummyQueueStore()
        self._status_bar = _DummyStatusBar()

    def _refresh_queue_view(self) -> None:
        return None

    def statusBar(self) -> _DummyStatusBar:
        return self._status_bar


def test_enqueue_files_uses_remote_queue_settings(tmp_path: Path) -> None:
    window = _DummyWindow()
    media = tmp_path / "sample.wav"
    media.write_bytes(b"audio")

    window._on_enqueue_files([media])

    assert len(window._queue_store.items) == 1
    item = window._queue_store.items[0]
    assert item.settings.execution_mode == "remote"
    assert item.settings.server_target == "http://127.0.0.1:18769"
    assert item.settings.remote_token == "secret"
    assert item.settings.remote_poll_seconds == 2.0
    assert item.settings.download_artifacts is False


def test_enqueue_urls_uses_remote_queue_settings() -> None:
    window = _DummyWindow()

    window._on_enqueue_urls("https://example.com/one\nhttps://example.com/two")

    assert len(window._queue_store.items) == 2
    assert all(item.settings.execution_mode == "remote" for item in window._queue_store.items)
    assert all(
        item.settings.server_target == "http://127.0.0.1:18769"
        for item in window._queue_store.items
    )


def test_import_file_uses_remote_queue_settings(tmp_path: Path) -> None:
    window = _DummyWindow()
    import_file = tmp_path / "urls.txt"
    import_file.write_text("https://example.com/one\nhttps://example.com/two\n", encoding="utf-8")

    window._on_import_file(str(import_file))

    assert len(window._queue_store.items) == 2
    assert all(item.settings.execution_mode == "remote" for item in window._queue_store.items)
    assert all(
        item.settings.server_target == "http://127.0.0.1:18769"
        for item in window._queue_store.items
    )


def test_inspect_remote_target_rejects_host_without_scheme_or_port() -> None:
    inspection = inspect_remote_target("127.0.0.1")

    assert inspection.valid is False
    assert "full URL" in inspection.message
    assert inspection.error is not None
