from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from flowscribe.execution.remote_config import load_remote_server_profiles
from flowscribe.gui.dialogs.remote_server_dialog import RemoteServerDialog


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_remote_server_dialog_saves_and_removes_profile(
    monkeypatch,
    tmp_path,
    qapp,
) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))

    dialog = RemoteServerDialog(None)
    dialog.name_input.setText("local-test")
    dialog.base_url_input.setText("http://127.0.0.1:18769")
    dialog.token_input.setText("secret")
    dialog.timeout_spin.setValue(45.0)
    dialog.download_artifacts_check.setChecked(False)

    dialog._save_profile()

    profiles = load_remote_server_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "local-test"
    assert profiles[0].base_url == "http://127.0.0.1:18769"
    assert profiles[0].token == "secret"
    assert profiles[0].timeout_seconds == 45.0
    assert profiles[0].download_artifacts_by_default is False

    dialog.name_input.setText("local-test")
    dialog._remove_profile()

    assert load_remote_server_profiles() == ()
