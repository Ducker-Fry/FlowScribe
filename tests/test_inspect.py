import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from flowscribe.input.url_inspector import UrlInspector
from flowscribe.media.inspector import LocalMediaInspector


def test_url_inspector_selects_audio_only_format(monkeypatch) -> None:
    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def extract_info(self, url: str, download: bool):
            return {
                "title": "Demo",
                "duration": 42,
                "formats": [
                    {
                        "format_id": "audio",
                        "url": "https://cdn.example.com/audio.m4a",
                        "ext": "m4a",
                        "protocol": "https",
                        "acodec": "aac",
                        "vcodec": "none",
                        "tbr": 96,
                    },
                    {
                        "format_id": "video",
                        "url": "https://cdn.example.com/video.m3u8",
                        "ext": "mp4",
                        "protocol": "m3u8",
                        "acodec": "aac",
                        "vcodec": "h264",
                        "tbr": 500,
                    },
                ],
            }

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_inspector.validate_public_http_url",
        lambda url, **kwargs: None,
    )

    result = UrlInspector().inspect("https://example.com/watch")

    assert result.kind == "video-page-url"
    assert result.has_audio_only is True
    assert result.selected_strategy == "download audio-only stream"
    assert result.selected_format is not None
    assert result.selected_format.format_id == "audio"


def test_url_inspector_selects_lowest_combined_stream(monkeypatch) -> None:
    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def extract_info(self, url: str, download: bool):
            return {
                "duration": 30,
                "formats": [
                    {
                        "format_id": "high",
                        "url": "https://cdn.example.com/high.m3u8",
                        "acodec": "aac",
                        "vcodec": "h264",
                        "filesize_approx": 1000,
                        "width": 1920,
                        "height": 1080,
                    },
                    {
                        "format_id": "low",
                        "url": "https://cdn.example.com/low.m3u8",
                        "acodec": "aac",
                        "vcodec": "h264",
                        "filesize_approx": 100,
                        "width": 480,
                        "height": 270,
                    },
                ],
            }

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_inspector.validate_public_http_url",
        lambda url, **kwargs: None,
    )

    result = UrlInspector().inspect("https://example.com/watch")

    assert result.has_audio_only is False
    assert result.has_combined_media is True
    assert result.selected_strategy == "stream lowest combined media and extract audio"
    assert result.selected_format is not None
    assert result.selected_format.format_id == "low"


def test_url_inspector_falls_back_to_selected_page_media(monkeypatch) -> None:
    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def extract_info(self, url: str, download: bool):
            return {
                "duration": 30,
                "url": "https://cdn.example.com/selected.m3u8",
                "format_id": "hls-460",
                "ext": "mp4",
                "protocol": "m3u8_native",
                "resolution": "480x270",
                "formats": [
                    {
                        "format_id": "hls-460",
                        "url": "https://cdn.example.com/selected.m3u8",
                        "audio_ext": "none",
                        "video_ext": "mp4",
                    },
                ],
            }

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_inspector.validate_public_http_url",
        lambda url, **kwargs: None,
    )

    result = UrlInspector().inspect("https://example.com/watch")

    assert result.has_audio_only is False
    assert result.has_combined_media is True
    assert result.selected_strategy == "stream selected page media and extract audio"
    assert result.selected_format is not None
    assert result.selected_format.format_id == "hls-460"


def test_local_media_inspector_parses_ffprobe_output(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    payload = {
        "streams": [
            {"codec_type": "video"},
            {"codec_type": "audio"},
        ],
        "format": {
            "duration": "12.5",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "size": "1024",
        },
    }

    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = LocalMediaInspector(ffprobe_executable="ffprobe").inspect(media)

    assert result.exists is True
    assert result.duration_seconds == 12.5
    assert result.has_audio is True
    assert result.has_video is True
    assert result.audio_streams == 1
    assert result.video_streams == 1
