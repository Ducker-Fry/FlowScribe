from pathlib import Path

import pytest

from flowscribe.media.tools import resolve_tool_path


def test_resolve_bundled_tool_next_to_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "FlowScribe.exe"
    tool = tmp_path / "ffmpeg.exe"
    app.write_text("placeholder", encoding="utf-8")
    tool.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr("sys.executable", str(app))

    assert resolve_tool_path("ffmpeg") == str(tool)


def test_resolve_unknown_tool_falls_back_to_name() -> None:
    tool_name = "definitely-not-a-real-flowscribe-tool"

    assert resolve_tool_path(tool_name) == tool_name
