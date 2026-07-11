from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from flowscribe.url_cli import main


def test_url_cli_inspect_json(monkeypatch) -> None:
    class FakeInspector:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def inspect(self, url: str):
            from flowscribe.input.url_inspector import UrlInspection

            return UrlInspection(
                source=url,
                kind="video-page-url",
                title="demo",
                duration_seconds=120,
                has_audio_only=True,
                has_combined_media=True,
                selected_strategy="download audio-only stream",
                selected_format=None,
                format_count=3,
            )

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.url_cli.UrlInspector", FakeInspector)

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(["inspect", "https://example.com/watch", "--json"])

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["source"] == "https://example.com/watch"
    assert payload["selected_strategy"] == "download audio-only stream"


def test_url_cli_download_json(monkeypatch, tmp_path: Path) -> None:
    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str, *, saved_media_kind: str, download_options):
            from flowscribe.input.url_downloader import UrlDownloadResult

            cleanup_dir = tmp_path / ".flowscribe-url-work" / "url-demo"
            cleanup_dir.mkdir(parents=True, exist_ok=True)
            audio_path = cleanup_dir / "remote-audio.m4a"
            audio_path.write_bytes(b"audio")
            return UrlDownloadResult(
                path=audio_path,
                cleanup_dir=cleanup_dir,
                saved_media_path=audio_path,
                saved_media_kind=saved_media_kind,
            )

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.url_cli.UrlAudioDownloader", FakeDownloader)

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "download",
                "https://example.com/watch",
                "-o",
                str(tmp_path / "downloads"),
                "--json",
            ]
        )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    saved_path = Path(payload["downloaded_audio_path"])
    assert saved_path.exists()
    assert saved_path.parent.name == "url-demo"
    assert payload["saved_media_kind"] == "audio"


def test_url_cli_version() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(["version"])

    assert exit_code == 0
    assert "FlowScribeURL" in stdout.getvalue()
