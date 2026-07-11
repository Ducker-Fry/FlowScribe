"""Tests for subprocess launch helpers."""

import logging
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

    kwargs = subprocess_utils.hidden_subprocess_kwargs()

    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


def test_hidden_subprocess_kwargs_support_pythonw(monkeypatch):
    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.sys, "executable", r"C:\Python312\pythonw.exe")
    monkeypatch.setattr(subprocess_utils.sys, "frozen", False, raising=False)

    kwargs = subprocess_utils.hidden_subprocess_kwargs()

    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


def test_hidden_subprocess_kwargs_logs_when_windowed(monkeypatch, caplog):
    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.sys, "executable", r"C:\Portable\gui-core.exe")
    monkeypatch.setattr(subprocess_utils.sys, "frozen", True, raising=False)
    monkeypatch.setenv(subprocess_utils.TRACE_ENV_NAME, "1")

    with caplog.at_level(logging.INFO):
        kwargs = subprocess_utils.hidden_subprocess_kwargs()

    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE
    assert "applying hidden child process flags" in caplog.text


def test_subprocess_trace_disabled_by_default(monkeypatch, caplog):
    monkeypatch.delenv(subprocess_utils.TRACE_ENV_NAME, raising=False)
    monkeypatch.setattr(subprocess_utils.sys, "platform", "win32")
    monkeypatch.setattr(subprocess_utils.sys, "executable", r"C:\Portable\gui-core.exe")
    monkeypatch.setattr(subprocess_utils.sys, "frozen", True, raising=False)

    with caplog.at_level(logging.INFO):
        kwargs = subprocess_utils.hidden_subprocess_kwargs()

    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert "hidden_subprocess_kwargs" not in caplog.text
