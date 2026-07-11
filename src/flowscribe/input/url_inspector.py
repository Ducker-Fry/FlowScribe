"""Inspect public URLs without downloading media."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from flowscribe.core.errors import DownloadError
from flowscribe.input.cookies import resolve_cookies_path
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.input.proxy import yt_dlp_proxy_options
from flowscribe.input.url_security import NetworkFamily, validate_public_http_url
from flowscribe.input.yt_dlp_site_options import yt_dlp_site_options

AUDIO_EXTENSIONS = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma"}
VIDEO_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS - AUDIO_EXTENSIONS


@dataclass(frozen=True)
class UrlFormatInfo:
    format_id: str | None
    extension: str | None
    protocol: str | None
    resolution: str | None
    audio_codec: str | None
    video_codec: str | None
    bitrate: float | None
    size_bytes: int | None


@dataclass(frozen=True)
class UrlInspection:
    source: str
    kind: str
    title: str | None
    duration_seconds: float | None
    has_audio_only: bool
    has_combined_media: bool
    selected_strategy: str
    selected_format: UrlFormatInfo | None
    format_count: int


class UrlInspector:
    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        network_family: NetworkFamily = "auto",
        cookies_path: Path | None = None,
        proxy: str | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._network_family = network_family
        self._cookies_path = cookies_path
        self._proxy = proxy

    def inspect(self, url: str) -> UrlInspection:
        validate_public_http_url(url, network_family=self._network_family)
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix in AUDIO_EXTENSIONS:
            return UrlInspection(
                source=url,
                kind="direct-audio-url",
                title=None,
                duration_seconds=None,
                has_audio_only=True,
                has_combined_media=False,
                selected_strategy="download audio directly",
                selected_format=None,
                format_count=0,
            )
        if suffix in VIDEO_EXTENSIONS:
            return UrlInspection(
                source=url,
                kind="direct-video-url",
                title=None,
                duration_seconds=None,
                has_audio_only=False,
                has_combined_media=True,
                selected_strategy="stream URL with ffmpeg and extract audio",
                selected_format=None,
                format_count=0,
            )

        info = self._extract_page_info(url)
        formats = info.get("formats") or []
        audio_only = [item for item in formats if _is_audio_only(item)]
        combined = [item for item in formats if _is_combined_media(item)]

        if audio_only:
            selected = min(audio_only, key=_format_sort_key)
            strategy = "download audio-only stream"
        elif combined:
            selected = min(combined, key=_format_sort_key)
            strategy = "stream lowest combined media and extract audio"
        elif info.get("url"):
            selected = info
            strategy = "stream selected page media and extract audio"
        else:
            selected = None
            strategy = "unsupported: no usable audio or combined media stream"

        return UrlInspection(
            source=url,
            kind="video-page-url",
            title=info.get("title"),
            duration_seconds=_optional_float(info.get("duration")),
            has_audio_only=bool(audio_only),
            has_combined_media=bool(combined or info.get("url")),
            selected_strategy=strategy,
            selected_format=_format_info(selected) if selected else None,
            format_count=len(formats),
        )

    def _extract_page_info(self, url: str) -> dict:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError as YtDlpDownloadError
        except ModuleNotFoundError as exc:
            if exc.name != "yt_dlp":
                raise DownloadError(
                    "yt-dlp is present but failed to import one of its runtime dependencies.\n"
                    f"Original error: {exc.__class__.__name__}: {exc}"
                ) from exc
            raise DownloadError("yt-dlp is not installed. Run `python -m pip install -e .`.") from exc
        except ImportError as exc:
            raise DownloadError(
                "yt-dlp is present but failed to initialize correctly.\n"
                f"Original error: {exc.__class__.__name__}: {exc}"
            ) from exc

        options = {
            "noplaylist": True,
            "socket_timeout": self._timeout_seconds,
            "retries": 1,
            "quiet": True,
            "no_warnings": True,
            **_network_options(self._network_family),
            **yt_dlp_proxy_options(self._proxy),
            **yt_dlp_site_options(url),
        }
        cookiefile = resolve_cookies_path(self._cookies_path)
        if cookiefile:
            options["cookiefile"] = cookiefile
        try:
            with YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False)
        except YtDlpDownloadError as exc:
            raise DownloadError(friendly_ytdlp_error(exc)) from exc


def friendly_ytdlp_error(exc: Exception) -> str:
    message = str(exc)
    suggestions = [
        "Could not inspect URL media with yt-dlp.",
        f"Original error: {message}",
        "Possible causes: unsupported site, missing/expired cookies for login-only media, DRM/protected media, network/proxy issue, or site anti-bot rules.",
        "Try opening the URL in a browser, using a public direct media URL, passing `--cookies path\\to\\cookies.txt`, passing `--proxy http://127.0.0.1:7890`, or updating yt-dlp.",
    ]
    return "\n".join(suggestions)


def _network_options(network_family: NetworkFamily) -> dict:
    if network_family == "ipv4":
        return {"source_address": "0.0.0.0"}
    if network_family == "ipv6":
        return {"source_address": "::"}
    return {}


def _is_audio_only(item: dict) -> bool:
    return bool(
        item.get("url")
        and item.get("acodec") not in {None, "none"}
        and item.get("vcodec") in {None, "none"}
    )


def _is_combined_media(item: dict) -> bool:
    return bool(
        item.get("url")
        and item.get("acodec") not in {None, "none"}
        and item.get("vcodec") not in {None, "none"}
    )


def _format_sort_key(item: dict) -> tuple[float, float, float]:
    size = item.get("filesize") or item.get("filesize_approx") or math.inf
    bitrate = item.get("tbr") or math.inf
    pixels = (item.get("width") or math.inf) * (item.get("height") or math.inf)
    return float(size), float(bitrate), float(pixels)


def _format_info(item: dict) -> UrlFormatInfo:
    width = item.get("width")
    height = item.get("height")
    resolution = f"{width}x{height}" if width and height else item.get("resolution")
    return UrlFormatInfo(
        format_id=item.get("format_id"),
        extension=item.get("ext"),
        protocol=item.get("protocol"),
        resolution=resolution,
        audio_codec=item.get("acodec"),
        video_codec=item.get("vcodec"),
        bitrate=_optional_float(item.get("tbr")),
        size_bytes=_optional_int(item.get("filesize") or item.get("filesize_approx")),
    )


def _optional_float(value) -> float | None:
    if value in {None, "", "N/A"}:
        return None
    return float(value)


def _optional_int(value) -> int | None:
    if value in {None, "", "N/A"}:
        return None
    return int(value)
