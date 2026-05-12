from pathlib import Path
import sys
from types import ModuleType

import pytest

from flowscribe.cli.args import UrlOptions, parse_args
from flowscribe.core.errors import DownloadError
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.input.url_security import validate_public_http_url


def test_parse_url_args() -> None:
    options = parse_args(
        [
            "url",
            "https://example.com/video",
            "-o",
            "out",
            "--format",
            "json,vtt",
            "--keep-media",
            "--max-download-mb",
            "100",
            "--max-duration",
            "00:30:00",
            "--download-timeout",
            "15",
        ]
    )

    assert isinstance(options, UrlOptions)
    assert options.command == "url"
    assert options.url == "https://example.com/video"
    assert options.output_dir == Path("out")
    assert options.output_formats == ("json", "vtt")
    assert options.keep_media is True
    assert options.max_download_mb == 100
    assert options.max_duration_seconds == 1800
    assert options.download_timeout_seconds == 15


def test_validate_public_http_url_blocks_localhost() -> None:
    with pytest.raises(DownloadError, match="Localhost"):
        validate_public_http_url("http://localhost/audio.mp3")


def test_validate_public_http_url_blocks_private_ip(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("192.168.1.10", 443))],
    )

    with pytest.raises(DownloadError, match="blocked network"):
        validate_public_http_url("https://example.com/audio.mp3")


def test_downloader_uses_safe_hashed_directory_and_downloads_audio(monkeypatch, tmp_path: Path) -> None:
    class FakeResponse:
        headers = {"Content-Length": "5"}
        url = "https://example.com/audio.mp3"

        def __init__(self) -> None:
            self._chunks = [b"hello", b""]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self, size: int) -> bytes:
            return self._chunks.pop(0)

    class FakeOpener:
        def open(self, request, timeout: int):
            return FakeResponse()

    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url: None,
    )
    monkeypatch.setattr(
        "flowscribe.input.url_downloader._safe_url_opener",
        lambda: FakeOpener(),
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
        ffprobe_executable="ffprobe",
    )
    monkeypatch.setattr(downloader, "_ensure_duration", lambda path_or_url: None)

    result = downloader.download_audio("https://example.com/nested/title/audio.mp3")

    assert result.path.read_bytes() == b"hello"
    assert result.path.name == "remote-audio.mp3"
    assert result.cleanup_dir.parent == tmp_path
    assert result.cleanup_dir.name.startswith("url-")
    assert "title" not in result.cleanup_dir.name


def test_downloader_rejects_large_direct_audio(monkeypatch, tmp_path: Path) -> None:
    class FakeResponse:
        headers = {"Content-Length": "11"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    class FakeOpener:
        def open(self, request, timeout: int):
            return FakeResponse()

    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url: None,
    )
    monkeypatch.setattr(
        "flowscribe.input.url_downloader._safe_url_opener",
        lambda: FakeOpener(),
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
    )

    with pytest.raises(DownloadError, match="larger"):
        downloader.download_audio("https://example.com/audio.mp3")


def test_page_url_requests_audio_only_with_ytdlp(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            captured_options.update(options)
            self._output = Path(str(options["outtmpl"]).replace("%(ext)s", "m4a"))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def extract_info(self, url: str, download: bool):
            return {"duration": 30}

        def download(self, urls: list[str]) -> None:
            self._output.write_bytes(b"audio")

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url: None,
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
    )
    monkeypatch.setattr(downloader, "_ensure_duration", lambda path_or_url: None)

    result = downloader.download_audio("https://example.com/watch?id=123")

    assert captured_options["format"] == "bestaudio"
    assert result.path.name == "remote-audio.m4a"
