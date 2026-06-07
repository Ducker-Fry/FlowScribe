from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from flowscribe.input.url_downloader import DownloadOptions
from flowscribe.input.url_tool_bridge import (
    ExternalUrlAudioDownloader,
    ExternalUrlInspector,
    select_url_downloader_cls,
    select_url_inspector_cls,
)


def test_selectors_fall_back_without_external_tool(monkeypatch) -> None:
    monkeypatch.setattr("flowscribe.input.url_tool_bridge.resolve_external_url_tool", lambda: None)

    assert select_url_downloader_cls().__name__ == "UrlAudioDownloader"
    assert select_url_inspector_cls().__name__ == "UrlInspector"


def test_external_url_inspector_invokes_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "flowscribe.input.url_tool_bridge.resolve_external_url_tool",
        lambda: tmp_path / ("FlowScribeURL.exe" if sys.platform == "win32" else "FlowScribeURL"),
    )

    captured: dict[str, object] = {}

    def fake_run(command, capture_output, text, timeout, check, **kwargs):
        captured["command"] = command
        payload = {
            "type": "url",
            "source": "https://example.com/watch",
            "kind": "video-page-url",
            "title": "demo",
            "duration_seconds": 123,
            "has_audio_only": True,
            "has_combined_media": True,
            "selected_strategy": "download audio-only stream",
            "selected_format": {
                "format_id": "251",
                "extension": "webm",
                "protocol": "https",
                "resolution": None,
                "audio_codec": "opus",
                "video_codec": "none",
                "bitrate": 128.0,
                "size_bytes": 1024,
            },
            "format_count": 4,
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr("flowscribe.input.url_tool_bridge.subprocess.run", fake_run)

    result = ExternalUrlInspector(timeout_seconds=12, network_family="ipv4").inspect(
        "https://example.com/watch"
    )

    assert result.title == "demo"
    assert result.selected_format is not None
    assert result.selected_format.format_id == "251"
    assert "inspect" in captured["command"]


def test_external_url_downloader_invokes_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "flowscribe.input.url_tool_bridge.resolve_external_url_tool",
        lambda: tmp_path / ("FlowScribeURL.exe" if sys.platform == "win32" else "FlowScribeURL"),
    )

    captured: dict[str, object] = {}

    def fake_run(command, capture_output, text, timeout, check, **kwargs):
        captured["command"] = command
        payload = {
            "ok": True,
            "source": "https://example.com/watch",
            "output_dir": str(tmp_path / "downloads"),
            "downloaded_audio_path": str(tmp_path / "downloads" / "url-demo" / "remote-audio.m4a"),
            "saved_media_path": str(tmp_path / "downloads" / "url-demo" / "remote-media.mp4"),
            "saved_media_kind": "video",
            "cleanup_dir": str(tmp_path / "downloads" / "url-demo"),
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr("flowscribe.input.url_tool_bridge.subprocess.run", fake_run)

    downloader = ExternalUrlAudioDownloader(
        download_dir=tmp_path / "downloads",
        max_bytes=100 * 1024 * 1024,
        max_duration_seconds=300,
        timeout_seconds=15,
    )
    result = downloader.download_audio(
        "https://example.com/watch",
        saved_media_kind="video",
        download_options=DownloadOptions(media_kind="video", quality="high", prefer_format="mp4"),
    )

    assert result.saved_media_kind == "video"
    assert result.cleanup_dir.name == "url-demo"
    assert result.saved_media_path is not None
    assert "--media-kind" in captured["command"]
    assert "--format" in captured["command"]
