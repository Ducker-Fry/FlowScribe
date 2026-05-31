import logging
import sys

from flowscribe.utils import runtime_logging
from flowscribe.utils.runtime_logging import (
    configure_runtime_logging,
    flowscribe_log_dir,
    install_null_standard_streams,
)


def test_flowscribe_log_dir_prefers_override() -> None:
    assert flowscribe_log_dir({"FLOWSCRIBE_LOG_DIR": r"D:\logs"}) == runtime_logging.Path(r"D:\logs")


def test_flowscribe_log_dir_uses_project_logs_for_source_runs(monkeypatch) -> None:
    monkeypatch.setattr(runtime_logging.sys, "frozen", False, raising=False)

    assert flowscribe_log_dir({}) == runtime_logging.Path(__file__).resolve().parents[1] / "logs"


def test_flowscribe_log_dir_uses_executable_logs_for_frozen_runs(monkeypatch) -> None:
    monkeypatch.setattr(runtime_logging.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_logging.sys, "executable", r"E:\Software\FlowScribeGUI\FlowScribeGUI.exe")

    assert flowscribe_log_dir({}) == runtime_logging.Path(r"E:\Software\FlowScribeGUI\logs")


def test_install_null_standard_streams_replaces_missing_streams(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    install_null_standard_streams()

    assert sys.stdout.write("hello") == 5
    assert sys.stderr.write("hello") == 5


def test_configure_runtime_logging_writes_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_LOG_DIR", str(tmp_path))

    log_path = configure_runtime_logging("FlowScribeTest")
    logging.getLogger("flowscribe.test").error("runtime log smoke")

    assert log_path == tmp_path / "FlowScribeTest.log"
    assert log_path.exists()
    assert "runtime log smoke" in log_path.read_text(encoding="utf-8")
