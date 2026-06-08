"""Bridge packaged URL acquisition through the standalone FlowScribeURL tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from flowscribe.core.errors import DownloadError
from flowscribe.input.url_downloader import DownloadOptions, UrlAudioDownloader, UrlDownloadResult
from flowscribe.input.url_inspector import UrlFormatInfo, UrlInspection, UrlInspector
from flowscribe.utils.runtime_layout import resolve_runtime_layout
from flowscribe.utils.subprocess import hidden_subprocess_kwargs


def resolve_external_url_tool() -> Path | None:
    layout = resolve_runtime_layout()
    for candidate in (
        layout.core_dir / _tool_name(),
        layout.app_root / _tool_name(),
    ):
        if candidate.exists():
            return candidate
    return None


def select_url_downloader_cls(default_cls=UrlAudioDownloader):
    if resolve_external_url_tool() is not None:
        return ExternalUrlAudioDownloader
    return default_cls


def select_url_inspector_cls(default_cls=UrlInspector):
    if resolve_external_url_tool() is not None:
        return ExternalUrlInspector
    return default_cls


class ExternalUrlInspector:
    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        network_family: str = "auto",
        cookies_path: Path | None = None,
        proxy: str | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._network_family = network_family
        self._cookies_path = cookies_path
        self._proxy = proxy

    def inspect(self, url: str) -> UrlInspection:
        command = [_require_external_url_tool(), "inspect", url, "--json"]
        command.extend(["--timeout", str(self._timeout_seconds)])
        command.extend(["--network-family", self._network_family])
        if self._cookies_path is not None:
            command.extend(["--cookies", str(self._cookies_path)])
        if self._proxy:
            command.extend(["--proxy", self._proxy])
        payload = _run_external_tool(command, timeout_seconds=self._timeout_seconds + 15)
        selected_format_payload = payload.get("selected_format")
        selected_format = (
            UrlFormatInfo(**selected_format_payload) if selected_format_payload is not None else None
        )
        return UrlInspection(
            source=payload["source"],
            kind=payload["kind"],
            title=payload.get("title"),
            duration_seconds=payload.get("duration_seconds"),
            has_audio_only=payload["has_audio_only"],
            has_combined_media=payload["has_combined_media"],
            selected_strategy=payload["selected_strategy"],
            selected_format=selected_format,
            format_count=payload["format_count"],
        )


class ExternalUrlAudioDownloader:
    def __init__(
        self,
        *,
        download_dir: Path,
        max_bytes: int,
        max_duration_seconds: float,
        timeout_seconds: int,
        network_family: str = "auto",
        cookies_path: Path | None = None,
        proxy: str | None = None,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
    ) -> None:
        self._download_dir = download_dir
        self._max_bytes = max_bytes
        self._max_duration_seconds = max_duration_seconds
        self._timeout_seconds = timeout_seconds
        self._network_family = network_family
        self._cookies_path = cookies_path
        self._proxy = proxy
        self._ffmpeg_executable = ffmpeg_executable
        self._ffprobe_executable = ffprobe_executable

    def download_audio(
        self,
        url: str,
        *,
        saved_media_kind: str = "audio",
        download_options: DownloadOptions | None = None,
    ) -> UrlDownloadResult:
        options = download_options or DownloadOptions(media_kind=saved_media_kind)
        work_dir = self._download_dir / ".flowscribe-url-tool-work"
        command = [
            _require_external_url_tool(),
            "download",
            url,
            "-o",
            str(self._download_dir),
            "--work-dir",
            str(work_dir),
            "--media-kind",
            options.media_kind,
            "--quality",
            options.quality,
            "--max-download-mb",
            str(max(1, self._max_bytes // (1024 * 1024))),
            "--max-duration",
            str(self._max_duration_seconds),
            "--timeout",
            str(self._timeout_seconds),
            "--network-family",
            self._network_family,
            "--json",
        ]
        if options.prefer_format:
            command.extend(["--format", options.prefer_format])
        if self._cookies_path is not None:
            command.extend(["--cookies", str(self._cookies_path)])
        if self._proxy:
            command.extend(["--proxy", self._proxy])
        payload = _run_external_tool(
            command,
            timeout_seconds=int(self._max_duration_seconds + self._timeout_seconds + 30),
        )
        downloaded_audio_path = Path(payload["downloaded_audio_path"])
        saved_media_path = (
            Path(payload["saved_media_path"]) if payload.get("saved_media_path") is not None else None
        )
        cleanup_dir = Path(payload["cleanup_dir"]) if payload.get("cleanup_dir") else downloaded_audio_path.parent
        return UrlDownloadResult(
            path=downloaded_audio_path,
            cleanup_dir=cleanup_dir,
            saved_media_path=saved_media_path,
            saved_media_kind=payload["saved_media_kind"],
        )


def _run_external_tool(command: list[str], *, timeout_seconds: int) -> dict:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except FileNotFoundError as exc:
        raise DownloadError("FlowScribeURL.exe was not found next to the current application.") from exc
    except subprocess.TimeoutExpired as exc:
        raise DownloadError("Timed out while waiting for FlowScribeURL.exe.") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "FlowScribeURL.exe failed."
        raise DownloadError(message)

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DownloadError("FlowScribeURL.exe returned invalid JSON output.") from exc


def _require_external_url_tool() -> str:
    tool = resolve_external_url_tool()
    if tool is None:
        raise DownloadError("FlowScribeURL.exe was not found next to the current application.")
    return str(tool)


def _tool_name() -> str:
    return "FlowScribeURL.exe" if sys.platform == "win32" else "FlowScribeURL"
