"""Download or extract remote URL audio for transcription."""

from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flowscribe.core.errors import DownloadError
from flowscribe.input.cookies import resolve_cookies_path
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.input.proxy import proxy_environment, proxy_handler, yt_dlp_proxy_options
from flowscribe.input.url_inspector import friendly_ytdlp_error
from flowscribe.input.url_security import NetworkFamily, validate_public_http_url
from flowscribe.input.yt_dlp_site_options import yt_dlp_site_options
from flowscribe.media.tools import resolve_tool_path
from flowscribe.utils.subprocess import hidden_subprocess_kwargs

AUDIO_EXTENSIONS = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma"}
VIDEO_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS - AUDIO_EXTENSIONS


UrlSavedMediaKind = Literal["audio", "video"]
DownloadQuality = Literal["best", "high", "medium", "low"]


@dataclass(frozen=True)
class DownloadOptions:
    """Options for remote media download."""

    media_kind: UrlSavedMediaKind = "audio"
    quality: DownloadQuality = "best"
    prefer_format: str | None = None


@dataclass(frozen=True)
class UrlDownloadResult:
    path: Path
    cleanup_dir: Path
    saved_media_path: Path | None = None
    saved_media_kind: UrlSavedMediaKind = "audio"


class UrlAudioDownloader:
    def __init__(
        self,
        *,
        download_dir: Path,
        max_bytes: int,
        max_duration_seconds: float,
        timeout_seconds: int,
        network_family: NetworkFamily = "auto",
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
        self._ffmpeg_executable = ffmpeg_executable or resolve_tool_path("ffmpeg")
        self._ffprobe_executable = ffprobe_executable or resolve_tool_path("ffprobe")

    def download_audio(
        self,
        url: str,
        *,
        saved_media_kind: UrlSavedMediaKind = "audio",
        download_options: DownloadOptions | None = None,
    ) -> UrlDownloadResult:
        options = download_options or DownloadOptions()
        effective_media_kind = options.media_kind if download_options else saved_media_kind

        validate_public_http_url(url, network_family=self._network_family)
        item_dir = self._download_dir / self._safe_id(url)
        if item_dir.exists():
            shutil.rmtree(item_dir)
        item_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(urlparse(url).path).suffix.lower()
        bindable_media_path: Path | None = None
        actual_media_kind: UrlSavedMediaKind = effective_media_kind
        if suffix in AUDIO_EXTENSIONS:
            path = self._download_direct_audio(url, item_dir, suffix)
            bindable_media_path = path
            actual_media_kind = "audio"
        elif suffix in VIDEO_EXTENSIONS:
            if effective_media_kind == "video":
                bindable_media_path = self._download_direct_video_copy(url, item_dir)
                if bindable_media_path is not None:
                    actual_media_kind = "video"
            path = self._extract_direct_video_audio(url, item_dir)
            if bindable_media_path is None:
                bindable_media_path = path
                actual_media_kind = "audio"
        else:
            path, bindable_media_path, actual_media_kind = self._download_page_audio(
                url,
                item_dir,
                saved_media_kind=effective_media_kind,
                download_options=options,
            )
        return UrlDownloadResult(
            path=path,
            cleanup_dir=item_dir,
            saved_media_path=bindable_media_path,
            saved_media_kind=actual_media_kind,
        )

    def _download_direct_audio(self, url: str, item_dir: Path, suffix: str) -> Path:
        request = Request(url, headers={"User-Agent": "FlowScribe/0.1"})
        path = item_dir / f"remote-audio{suffix}"
        try:
            with _safe_url_opener(self._proxy).open(request, timeout=self._timeout_seconds) as response:
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
            raise DownloadError(
                "Could not download remote audio.\n"
                f"Original error: {exc}\n"
                "Possible causes: network/proxy issue, blocked URL, expired URL, or unsupported redirect.\n"
                "Try opening the URL in a browser or run `flowscribe inspect <url>` first."
            ) from exc
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
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=process_timeout,
                check=True,
                env=proxy_environment(self._proxy),
                **hidden_subprocess_kwargs(),
            )
        except FileNotFoundError as exc:
            raise DownloadError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("Timed out while extracting audio from the video URL.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise DownloadError(
                "Could not extract audio from the direct video URL.\n"
                f"Original error: {message}\n"
                "Possible causes: missing audio stream, unsupported protocol, expired URL, "
                "network/proxy issue, or protected media.\n"
                "Run `flowscribe inspect <url>` to check the source before transcribing."
            ) from exc
        self._ensure_size(path)
        self._ensure_duration(path)
        return path

    def _download_page_audio(
        self,
        url: str,
        item_dir: Path,
        *,
        saved_media_kind: UrlSavedMediaKind,
        download_options: DownloadOptions,
    ) -> tuple[Path, Path | None, UrlSavedMediaKind]:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError as YtDlpDownloadError
        except ImportError as exc:
            raise DownloadError("yt-dlp is not installed. Run `python -m pip install -e .`.") from exc

        base_options = {
            "noplaylist": True,
            "socket_timeout": self._timeout_seconds,
            "retries": 1,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            **_network_options(self._network_family),
            **yt_dlp_proxy_options(self._proxy),
            **yt_dlp_site_options(url),
        }
        cookiefile = resolve_cookies_path(self._cookies_path)
        if cookiefile:
            base_options["cookiefile"] = cookiefile
        try:
            with YoutubeDL(base_options) as ydl:
                info = ydl.extract_info(url, download=False)
        except YtDlpDownloadError as exc:
            raise DownloadError(friendly_ytdlp_error(exc)) from exc

        duration = info.get("duration")
        if duration is not None and float(duration) > self._max_duration_seconds:
            raise DownloadError("Remote media is longer than the configured duration limit.")

        if not self._has_audio_only_format(info):
            stream_url = self._select_smallest_combined_stream_url(info)
            if stream_url is None:
                raise DownloadError(
                    "No usable audio stream was found for this URL.\n"
                    "Possible causes: video has no audio, unsupported media format, DRM/protected media, "
                    "site-specific extraction limits, or missing/expired cookies for login-only media.\n"
                    "Run `flowscribe inspect <url>` to see available formats before transcribing. "
                    "If the page requires login, retry with `--cookies path\\to\\cookies.txt`."
                )
            validate_public_http_url(stream_url, network_family=self._network_family)
            saved_media_path = None
            actual_kind: UrlSavedMediaKind = "audio"
            if saved_media_kind == "video":
                saved_media_path = self._download_page_video(
                    url, item_dir, base_options, download_options
                )
                if saved_media_path is not None:
                    actual_kind = "video"
            audio_path = self._extract_page_stream_audio(stream_url, item_dir)
            if saved_media_path is None:
                saved_media_path = audio_path
                actual_kind = "audio"
            return audio_path, saved_media_path, actual_kind

        output_template = str(item_dir / "remote-audio.%(ext)s")
        format_selector = self._build_format_selector(
            media_kind="audio",
            quality=download_options.quality,
            prefer_format=download_options.prefer_format,
        )
        options = {
            **base_options,
            "format": format_selector,
            "outtmpl": output_template,
            "max_filesize": self._max_bytes,
            "progress_hooks": [self._yt_dlp_progress_hook],
        }
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([url])
        except YtDlpDownloadError as exc:
            raise DownloadError(
                "yt-dlp failed to download the selected audio stream.\n"
                f"Original error: {exc}\n"
                "Possible causes: network/proxy issue, site throttling, expired media URL, "
                "missing/expired cookies for login-only media, or a changed site extractor.\n"
                "Try `flowscribe inspect <url>` first, retry with `--cookies path\\to\\cookies.txt`, "
                "or update yt-dlp."
            ) from exc

        files = [path for path in item_dir.iterdir() if path.is_file()]
        if not files:
            raise DownloadError("yt-dlp did not produce an audio file.")
        path = max(files, key=lambda candidate: candidate.stat().st_size)
        self._ensure_size(path)
        self._ensure_duration(path)
        saved_media_path: Path | None = path
        actual_kind: UrlSavedMediaKind = "audio"
        if saved_media_kind == "video":
            video_path = self._download_page_video(url, item_dir, base_options, download_options)
            if video_path is not None:
                saved_media_path = video_path
                actual_kind = "video"
        return path, saved_media_path, actual_kind

    def _download_page_video(
        self,
        url: str,
        item_dir: Path,
        base_options: dict,
        download_options: DownloadOptions | None = None,
    ) -> Path | None:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError as YtDlpDownloadError
        except ImportError:
            import warnings
            warnings.warn(
                "yt-dlp is not installed. Cannot download video file. "
                "Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None

        output_template = str(item_dir / "remote-media.%(ext)s")
        options_obj = download_options or DownloadOptions(media_kind="video")
        format_selector = self._build_format_selector(
            media_kind="video",
            quality=options_obj.quality,
            prefer_format=options_obj.prefer_format,
        )
        options = {
            **base_options,
            "format": format_selector,
            "outtmpl": output_template,
            "max_filesize": self._max_bytes,
            "progress_hooks": [self._yt_dlp_progress_hook],
        }
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([url])
        except YtDlpDownloadError as exc:
            import warnings
            warnings.warn(
                f"Failed to download video file: {exc}\n"
                f"Audio extraction will continue. "
                f"Possible causes: video format not available, site restrictions, "
                f"file size limit exceeded, or network issue.",
                UserWarning,
                stacklevel=2,
            )
            return None

        candidates = [
            path
            for path in item_dir.iterdir()
            if path.is_file() and path.name.startswith("remote-media.")
        ]
        if not candidates:
            import warnings
            warnings.warn(
                "Video download completed but no video file was created. "
                "Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        path = max(candidates, key=lambda candidate: candidate.stat().st_size)
        try:
            self._ensure_size(path)
        except DownloadError as exc:
            import warnings
            warnings.warn(
                f"Downloaded video file exceeds size limit: {exc}\n"
                f"Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        return path

    def _download_direct_video_copy(self, url: str, item_dir: Path) -> Path | None:
        path = item_dir / "remote-media.mp4"
        command = [
            self._ffmpeg_executable,
            "-y",
            "-timeout",
            str(self._timeout_seconds * 1_000_000),
            "-i",
            url,
            "-t",
            str(self._max_duration_seconds),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-c",
            "copy",
            str(path),
        ]
        try:
            process_timeout = self._max_duration_seconds + self._timeout_seconds
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=process_timeout,
                check=True,
                env=proxy_environment(self._proxy),
                **hidden_subprocess_kwargs(),
            )
        except FileNotFoundError:
            import warnings
            warnings.warn(
                "ffmpeg not found. Cannot copy video file. Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        except subprocess.TimeoutExpired:
            import warnings
            warnings.warn(
                "Timeout while copying video file. Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        except subprocess.CalledProcessError as exc:
            import warnings
            error_msg = exc.stderr.strip() if exc.stderr else str(exc)
            warnings.warn(
                f"Failed to copy video file: {error_msg}\n"
                f"Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        if not path.exists():
            import warnings
            warnings.warn(
                "Video copy completed but file was not created. Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        try:
            self._ensure_size(path)
        except DownloadError as exc:
            import warnings
            warnings.warn(
                f"Copied video file exceeds size limit: {exc}\n"
                f"Audio extraction will continue.",
                UserWarning,
                stacklevel=2,
            )
            return None
        return path
        self._ensure_size(path)
        return path

    def _extract_page_stream_audio(self, stream_url: str, item_dir: Path) -> Path:
        path = item_dir / "remote-audio.m4a"
        command = [
            self._ffmpeg_executable,
            "-y",
            "-timeout",
            str(self._timeout_seconds * 1_000_000),
            "-i",
            stream_url,
            "-t",
            str(self._max_duration_seconds),
            "-vn",
            "-c:a",
            "aac",
            str(path),
        ]
        try:
            process_timeout = self._max_duration_seconds + self._timeout_seconds
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=process_timeout,
                check=True,
                env=proxy_environment(self._proxy),
                **hidden_subprocess_kwargs(),
            )
        except FileNotFoundError as exc:
            raise DownloadError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("Timed out while extracting page audio stream.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise DownloadError(
                "Could not extract audio from the page media stream.\n"
                f"Original error: {message}\n"
                "Possible causes: expired HLS/DASH stream, network/proxy issue, site throttling, "
                "protected media, missing/expired cookies, or missing audio in the selected stream.\n"
                "Run `flowscribe inspect <url>` to review available formats. If the page requires login, "
                "retry with `--cookies path\\to\\cookies.txt`."
            ) from exc
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
                env=proxy_environment(self._proxy),
                **hidden_subprocess_kwargs(),
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

    @staticmethod
    def _has_audio_only_format(info: dict) -> bool:
        return any(
            item.get("url")
            and item.get("acodec") not in {None, "none"}
            and item.get("vcodec") in {None, "none"}
            for item in info.get("formats") or []
        )

    @staticmethod
    def _select_smallest_combined_stream_url(info: dict) -> str | None:
        formats = info.get("formats") or []
        candidates = [
            item
            for item in formats
            if item.get("url")
            and item.get("acodec") not in {None, "none"}
            and item.get("vcodec") not in {None, "none"}
        ]
        if not candidates and info.get("url"):
            return str(info["url"])
        if not candidates:
            return None

        def sort_key(item: dict) -> tuple[float, float, float]:
            size = item.get("filesize") or item.get("filesize_approx") or math.inf
            bitrate = item.get("tbr") or math.inf
            pixels = (item.get("width") or math.inf) * (item.get("height") or math.inf)
            return float(size), float(bitrate), float(pixels)

        return str(min(candidates, key=sort_key)["url"])

    @staticmethod
    def _build_format_selector(
        media_kind: UrlSavedMediaKind,
        quality: DownloadQuality,
        prefer_format: str | None = None,
    ) -> str:
        """Build yt-dlp format selector based on quality and format preferences."""
        if media_kind == "audio":
            quality_map = {
                "best": "bestaudio",
                "high": "bestaudio[abr>=128]",
                "medium": "bestaudio[abr>=64][abr<128]",
                "low": "worstaudio",
            }
            base_selector = quality_map.get(quality, "bestaudio")
            if prefer_format:
                return f"{base_selector}[ext={prefer_format}]/{base_selector}"
            return base_selector
        else:
            quality_map = {
                "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "high": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "medium": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "low": "worstvideo+worstaudio/worst",
            }
            base_selector = quality_map.get(quality, "best")
            if prefer_format:
                return f"{base_selector}[ext={prefer_format}]/{base_selector}"
            return base_selector



class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_url_opener(proxy: str | None = None):
    handler = proxy_handler(proxy)
    if handler is None:
        return build_opener(_SafeRedirectHandler)
    return build_opener(_SafeRedirectHandler, handler)


def _network_options(network_family: NetworkFamily) -> dict:
    if network_family == "ipv4":
        return {"source_address": "0.0.0.0"}
    if network_family == "ipv6":
        return {"source_address": "::"}
    return {}
