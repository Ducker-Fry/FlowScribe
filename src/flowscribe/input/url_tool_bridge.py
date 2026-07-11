"""Bridge packaged URL acquisition through the standalone FlowScribeURL tool."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from flowscribe.core.errors import CancellationError, DownloadError
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
    if _should_use_external_url_tool():
        return ExternalUrlAudioDownloader
    return default_cls


def select_url_inspector_cls(default_cls=UrlInspector):
    if _should_use_external_url_tool():
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
        progress_callback: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
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
        self._progress_callback = progress_callback
        self._should_cancel = should_cancel

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
        if self._progress_callback is not None or self._should_cancel is not None:
            command.append("--jsonl-progress")
        if options.prefer_format:
            command.extend(["--format", options.prefer_format])
        if self._cookies_path is not None:
            command.extend(["--cookies", str(self._cookies_path)])
        if self._proxy:
            command.extend(["--proxy", self._proxy])
        payload = _run_external_tool(
            command,
            timeout_seconds=int(self._max_duration_seconds + self._timeout_seconds + 30),
            progress_callback=self._progress_callback,
            should_cancel=self._should_cancel,
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


def _run_external_tool(
    command: list[str],
    *,
    timeout_seconds: int,
    progress_callback: Callable[[str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    if progress_callback is None and should_cancel is None:
        return _run_external_tool_once(command, timeout_seconds=timeout_seconds)
    return _run_external_tool_streaming(
        command,
        timeout_seconds=timeout_seconds,
        progress_callback=progress_callback,
        should_cancel=should_cancel,
    )


def _run_external_tool_once(command: list[str], *, timeout_seconds: int) -> dict:
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


def _run_external_tool_streaming(
    command: list[str],
    *,
    timeout_seconds: int,
    progress_callback: Callable[[str], None] | None,
    should_cancel: Callable[[], bool] | None,
) -> dict:
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **hidden_subprocess_kwargs(),
        )
    except FileNotFoundError as exc:
        raise DownloadError("FlowScribeURL.exe was not found next to the current application.") from exc

    stdout_queue: queue.Queue[str | None] = queue.Queue()
    stderr_queue: queue.Queue[str | None] = queue.Queue()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    final_payload: dict | None = None

    stdout_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stdout, stdout_queue),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stderr, stderr_queue),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    started_at = time.monotonic()

    try:
        while True:
            if time.monotonic() - started_at > timeout_seconds:
                process.kill()
                raise DownloadError("Timed out while waiting for FlowScribeURL.exe.")
            if should_cancel is not None and should_cancel():
                process.terminate()
                raise CancellationError("Remote media acquisition canceled.")

            _drain_text_queue(stderr_queue, stderr_lines)
            for line in _drain_text_queue(stdout_queue, stdout_lines):
                payload = _parse_json_line(line)
                if payload is None:
                    continue
                if payload.get("type") == "progress":
                    if progress_callback is not None and payload.get("message"):
                        progress_callback(str(payload["message"]))
                    continue
                final_payload = payload

            if process.poll() is not None and stdout_queue.empty() and stderr_queue.empty():
                break

            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    if process.returncode != 0:
        message = "\n".join(line for line in (stderr_lines + stdout_lines) if line).strip()
        raise DownloadError(message or "FlowScribeURL.exe failed.")

    if final_payload is None:
        raise DownloadError("FlowScribeURL.exe returned no final JSON payload.")
    return final_payload


def _enqueue_stream_lines(stream, target_queue: queue.Queue[str | None]) -> None:
    if stream is None:
        target_queue.put(None)
        return
    try:
        for line in stream:
            target_queue.put(line.rstrip("\r\n"))
    finally:
        target_queue.put(None)


def _drain_text_queue(source_queue: queue.Queue[str | None], sink_lines: list[str]) -> list[str]:
    drained: list[str] = []
    while True:
        try:
            item = source_queue.get_nowait()
        except queue.Empty:
            return drained
        if item is None:
            continue
        sink_lines.append(item)
        drained.append(item)


def _parse_json_line(line: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _require_external_url_tool() -> str:
    tool = resolve_external_url_tool()
    if tool is None:
        raise DownloadError("FlowScribeURL.exe was not found next to the current application.")
    return str(tool)


def _tool_name() -> str:
    return "FlowScribeURL.exe" if sys.platform == "win32" else "FlowScribeURL"


def _should_use_external_url_tool() -> bool:
    layout = resolve_runtime_layout()
    if not layout.frozen:
        return False

    env_value = os.environ.get("FLOWSCRIBE_PREFER_EXTERNAL_URL_TOOL")
    if env_value is not None:
        normalized = env_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    # Layered portable builds already ship the Python URL runtime in-process.
    # Prefer that path so GUI/CLI behavior matches source runs and avoids an
    # extra packaged helper hop for every URL task.
    if layout.layered and (layout.code_dir / "flowscribe").exists():
        return False

    return resolve_external_url_tool() is not None
