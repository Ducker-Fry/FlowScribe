"""Tests for subprocess launch helpers."""

import subprocess

from flowscribe.utils import subprocess as subprocess_utils


def test_hidden_subprocess_kwargs_are_for_windowed_windows_processes(monkeypatch):
    monkeypatch.setattr(subprocess_utils.sys, "platform", "linux")

    assert subprocess_utils.hidden_subprocess_kwargs() == {}

    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.sys, "executable", r"C:\Python312\python.exe")
    monkeypatch.setattr(subprocess_utils.sys, "frozen", False, raising=False)

    assert subprocess_utils.hidden_subprocess_kwargs() == {}

    monkeypatch.setattr(subprocess_utils.sys, "frozen", True, raising=False)

    assert subprocess_utils.hidden_subprocess_kwargs() == {
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def test_hidden_subprocess_kwargs_support_pythonw(monkeypatch):
    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.sys, "executable", r"C:\Python312\pythonw.exe")
    monkeypatch.setattr(subprocess_utils.sys, "frozen", False, raising=False)

    assert subprocess_utils.hidden_subprocess_kwargs() == {
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }
