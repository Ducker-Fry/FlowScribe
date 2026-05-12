"""Download or extract remote URL audio for transcription."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flowscribe.core.errors import DownloadError
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.input.url_security import validate_public_http_url
from flowscribe.media.tools import resolve_tool_path

AUDIO_EXTENSIONS = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma"}
VIDEO_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS - AUDIO_EXTENSIONS


@dataclass(frozen=True)
class UrlDownloadResult:
    path: Path
    cleanup_dir: Path


class UrlAudioDownloader:
    def __init__(
        self,
        *,
        download_dir: Path,
        max_bytes: int,
        max_duration_seconds: float,
        timeout_seconds: int,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
    ) -> None:
        self._download_dir = download_dir
        self._max_bytes = max_bytes
        self._max_duration_seconds = max_duration_seconds
        self._timeout_seconds = timeout_seconds
        self._ffmpeg_executable = ffmpeg_executable or resolve_tool_path("ffmpeg")
        self._ffprobe_executable = ffprobe_executable or resolve_tool_path("ffprobe")

    def download_audio(self, url: str) -> UrlDownloadResult:
        validate_public_http_url(url)
        item_dir = self._download_dir / self._safe_id(url)
        if item_dir.exists():
            shutil.rmtree(item_dir)
        item_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix in AUDIO_EXTENSIONS:
            path = self._download_direct_audio(url, item_dir, suffix)
        elif suffix in VIDEO_EXTENSIONS:
            path = self._extract_direct_video_audio(url, item_dir)
        else:
            path = self._download_page_audio(url, item_dir)
        return UrlDownloadResult(path=path, cleanup_dir=item_dir)

    def _download_direct_audio(self, url: str, item_dir: Path, suffix: str) -> Path:
        request = Request(url, headers={"User-Agent": "FlowScribe/0.1"})
        path = item_dir / f"remote-audio{suffix}"
        try:
            with _safe_url_opener().open(request, timeout=self._timeout_seconds) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > self._max_bytes:
                    raise DownloadError("Remote audio is larger than the configured size limit.")

                downloaded = 0
                with path.open("wb") as file:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > self._max_bytes:
                            raise DownloadError("Remote audio exceeded the configured size limit.")
                        file.write(chunk)
        except OSError as exc:
            raise DownloadError(f"Could not download remote audio: {exc}") from exc
        self._ensure_duration(path)
        return path

    def _extract_direct_video_audio(self, url: str, item_dir: Path) -> Path:
        self._ensure_duration(url)
        path = item_dir / "remote-audio.m4a"
        command = [
            self._ffmpeg_executable,
            "-y",
            "-timeout",
            str(self._timeout_seconds * 1_000_000),
            "-i",
            url,
            "-t",
            str(self._max_duration_seconds),
            "-vn",
            "-c:a",
            "aac",
            str(path),
        ]
        try:
            process_timeout = self._max_duration_seconds + self._timeout_seconds
            subprocess.run(command, capture_output=True, text=True, timeout=process_timeout, check=True)
        except FileNotFoundError as exc:
            raise DownloadError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("Timed out while extracting audio from the video URL.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise DownloadError(f"Could not extract audio from video URL: {message}") from exc
        self._ensure_size(path)
        self._ensure_duration(path)
        return path

    def _download_page_audio(self, url: str, item_dir: Path) -> Path:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError as YtDlpDownloadError
        except ImportError as exc:
            raise DownloadError("yt-dlp is not installed. Run `python -m pip install -e .`.") from exc

        output_template = str(item_dir / "remote-audio.%(ext)s")
        options = {
            # Strictly request audio-only media for page URLs. If a site cannot
            # provide an audio stream, fail clearly instead of downloading video.
            "format": "bestaudio",
            "outtmpl": output_template,
            "noplaylist": True,
            "socket_timeout": self._timeout_seconds,
            "retries": 1,
            "quiet": True,
            "no_warnings": True,
            "max_filesize": self._max_bytes,
            "progress_hooks": [self._yt_dlp_progress_hook],
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get("duration")
                if duration is not None and float(duration) > self._max_duration_seconds:
                    raise DownloadError("Remote media is longer than the configured duration limit.")
                ydl.download([url])
        except YtDlpDownloadError as exc:
            raise DownloadError(f"yt-dlp failed to download audio: {exc}") from exc

        files = [path for path in item_dir.iterdir() if path.is_file()]
        if not files:
            raise DownloadError("yt-dlp did not produce an audio file.")
        path = max(files, key=lambda candidate: candidate.stat().st_size)
        self._ensure_size(path)
        self._ensure_duration(path)
        return path

    def _yt_dlp_progress_hook(self, status: dict) -> None:
        downloaded = status.get("downloaded_bytes") or 0
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        if total and int(total) > self._max_bytes:
            raise DownloadError("Remote audio is larger than the configured size limit.")
        if downloaded and int(downloaded) > self._max_bytes:
            raise DownloadError("Remote audio exceeded the configured size limit.")

    def _ensure_size(self, path: Path) -> None:
        if not path.exists():
            raise DownloadError(f"Expected downloaded media was not created: {path}")
        if path.stat().st_size > self._max_bytes:
            raise DownloadError("Downloaded audio exceeded the configured size limit.")

    def _ensure_duration(self, path_or_url: Path | str) -> None:
        command = [
            self._ffprobe_executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path_or_url),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=True,
            )
        except FileNotFoundError as exc:
            raise DownloadError("ffprobe was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("Timed out while checking remote media duration.") from exc
        except subprocess.CalledProcessError:
            return

        duration_text = completed.stdout.strip()
        if not duration_text or duration_text == "N/A":
            return
        if float(duration_text) > self._max_duration_seconds:
            raise DownloadError("Remote media is longer than the configured duration limit.")

    @staticmethod
    def _safe_id(url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        return f"url-{digest}"


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_url_opener():
    return build_opener(_SafeRedirectHandler)
