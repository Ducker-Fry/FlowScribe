import logging
import sys
from datetime import datetime

from flowscribe.utils import runtime_logging
from flowscribe.utils.runtime_logging import (
    configure_runtime_logging,
    flowscribe_log_dir,
    install_null_standard_streams,
    select_log_path,
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

    expected_name = f"FlowScribeTest-{datetime.now().strftime('%Y-%m-%d')}.log"
    assert log_path == tmp_path / expected_name
    assert log_path.exists()
    assert "runtime log smoke" in log_path.read_text(encoding="utf-8")


def test_select_log_path_uses_current_date_name(tmp_path) -> None:
    log_path = select_log_path(tmp_path, "FlowScribeTest", now=datetime(2026, 6, 3, 10, 30, 0))

    assert log_path == tmp_path / "FlowScribeTest-2026-06-03.log"


def test_select_log_path_rolls_to_numbered_file_when_day_log_is_full(tmp_path) -> None:
    first_log = tmp_path / "FlowScribeTest-2026-06-03.log"
    first_log.write_bytes(b"x" * 10)

    log_path = select_log_path(
        tmp_path,
        "FlowScribeTest",
        now=datetime(2026, 6, 3, 10, 30, 0),
        max_bytes=10,
    )

    assert log_path == tmp_path / "FlowScribeTest-2026-06-03-1.log"


def test_select_log_path_skips_full_numbered_logs(tmp_path) -> None:
    (tmp_path / "FlowScribeTest-2026-06-03.log").write_bytes(b"x" * 10)
    (tmp_path / "FlowScribeTest-2026-06-03-1.log").write_bytes(b"x" * 10)

    log_path = select_log_path(
        tmp_path,
        "FlowScribeTest",
        now=datetime(2026, 6, 3, 10, 30, 0),
        max_bytes=10,
    )

    assert log_path == tmp_path / "FlowScribeTest-2026-06-03-2.log"
