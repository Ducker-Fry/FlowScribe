from pathlib import Path
import subprocess
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
            "--no-vad-filter",
            "--max-download-mb",
            "100",
            "--max-duration",
            "00:30:00",
            "--download-timeout",
            "15",
            "--network-family",
            "ipv4",
            "--cookies",
            "login.cookies.txt",
            "--proxy",
            "http://127.0.0.1:7890",
        ]
    )

    assert isinstance(options, UrlOptions)
    assert options.command == "url"
    assert options.url == "https://example.com/video"
    assert options.output_dir == Path("out")
    assert options.output_formats == ("json", "vtt")
    assert options.keep_media is True
    assert options.vad_filter is False
    assert options.no_vad_filter is True
    assert options.max_download_mb == 100
    assert options.max_duration_seconds == 1800
    assert options.download_timeout_seconds == 15
    assert options.network_family == "ipv4"
    assert options.cookies == Path("login.cookies.txt")
    assert options.proxy == "http://127.0.0.1:7890"


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


def test_validate_public_http_url_can_force_ipv4(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, family=0, type=0):
        assert family != 0
        return [(None, None, None, None, ("93.184.216.34", 443))]

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)

    validate_public_http_url("https://example.com/audio.mp3", network_family="ipv4")


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
        lambda url, **kwargs: None,
    )
    monkeypatch.setattr(
        "flowscribe.input.url_downloader._safe_url_opener",
        lambda proxy=None: FakeOpener(),
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
        lambda url, **kwargs: None,
    )
    monkeypatch.setattr(
        "flowscribe.input.url_downloader._safe_url_opener",
        lambda proxy=None: FakeOpener(),
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
        network_family="ipv4",
    )

    with pytest.raises(DownloadError, match="larger"):
        downloader.download_audio("https://example.com/audio.mp3")


def test_page_url_requests_audio_only_with_ytdlp(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            captured_options.update(options)
            self._output = (
                Path(str(options["outtmpl"]).replace("%(ext)s", "m4a"))
                if "outtmpl" in options
                else None
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def extract_info(self, url: str, download: bool):
            return {
                "duration": 30,
                "formats": [
                    {
                        "url": "https://cdn.example.com/audio.m4a",
                        "acodec": "aac",
                        "vcodec": "none",
                    }
                ],
            }

        def download(self, urls: list[str]) -> None:
            assert self._output is not None
            self._output.write_bytes(b"audio")

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url, **kwargs: None,
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
        network_family="ipv4",
        cookies_path=cookies,
        proxy="http://127.0.0.1:7890",
    )
    monkeypatch.setattr(downloader, "_ensure_duration", lambda path_or_url: None)

    result = downloader.download_audio("https://example.com/watch?id=123")

    assert captured_options["noprogress"] is True
    assert captured_options["source_address"] == "0.0.0.0"
    assert captured_options["cookiefile"] == str(cookies.resolve())
    assert captured_options["proxy"] == "http://127.0.0.1:7890"
    assert captured_options["format"] == "bestaudio"
    assert result.path.name == "remote-audio.m4a"


def test_downloader_rejects_missing_cookies_file(monkeypatch, tmp_path: Path) -> None:
    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = object
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url, **kwargs: None,
    )
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
        cookies_path=tmp_path / "missing.cookies.txt",
    )

    with pytest.raises(DownloadError, match="Cookies file does not exist"):
        downloader.download_audio("https://example.com/watch?id=123")


def test_page_url_extracts_audio_from_lowest_combined_stream(monkeypatch, tmp_path: Path) -> None:
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
                        "url": "https://cdn.example.com/high.m3u8",
                        "acodec": "unknown",
                        "vcodec": "unknown",
                        "filesize_approx": 1000,
                        "tbr": 1200,
                        "width": 1920,
                        "height": 1080,
                    },
                    {
                        "url": "https://cdn.example.com/low.m3u8",
                        "acodec": "unknown",
                        "vcodec": "unknown",
                        "filesize_approx": 100,
                        "tbr": 300,
                        "width": 480,
                        "height": 270,
                    },
                ],
            }

        def download(self, urls: list[str]) -> None:
            raise AssertionError("combined video should not be downloaded by yt-dlp")

    def fake_run(command, capture_output, text, timeout, check, env=None):
        assert command[command.index("-i") + 1] == "https://cdn.example.com/low.m3u8"
        Path(command[-1]).write_bytes(b"audio")
        return subprocess.CompletedProcess(command, 0, "", "")

    fake_ytdlp = ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    fake_utils = ModuleType("yt_dlp.utils")
    fake_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake_utils)
    monkeypatch.setattr(
        "flowscribe.input.url_downloader.validate_public_http_url",
        lambda url, **kwargs: None,
    )
    monkeypatch.setattr("subprocess.run", fake_run)
    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=10,
        max_duration_seconds=60,
        timeout_seconds=5,
    )
    monkeypatch.setattr(downloader, "_ensure_duration", lambda path_or_url: None)

    result = downloader.download_audio("https://example.com/watch?id=123")

    assert result.path.name == "remote-audio.m4a"
    assert result.path.read_bytes() == b"audio"
