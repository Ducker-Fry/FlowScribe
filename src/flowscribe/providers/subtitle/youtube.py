"""YouTube native subtitle provider."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, build_opener
import xml.etree.ElementTree as ET

from flowscribe.core.errors import DownloadError, SubtitleUnavailableError, TranscriptionError
from flowscribe.core.models import (
    MediaItem,
    Transcript,
    TranscriptSegment,
    TranscriptionOptions,
)
from flowscribe.input.cookies import resolve_cookies_path
from flowscribe.input.proxy import proxy_handler, yt_dlp_proxy_options
from flowscribe.input.yt_dlp_site_options import yt_dlp_site_options

YOUTUBE_SUBTITLE_PROVIDER_NAME = "youtube-native-subtitle"
_YOUTUBE_HOST_SUFFIXES = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SubtitleFetchResult:
    """Resolved subtitle payload and metadata."""

    transcript: Transcript
    language: str
    source_kind: str
    title: str | None
    subtitle_format: str


class YouTubeNativeSubtitleProvider:
    """Extract native YouTube subtitles without downloading media audio."""

    def supports(self, url: str) -> bool:
        hostname = (urlparse(url).hostname or "").lower()
        return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in _YOUTUBE_HOST_SUFFIXES)

    def fetch(
        self,
        url: str,
        *,
        language: str | None = None,
        cookies_path: Path | None = None,
        proxy: str | None = None,
        task: str = "transcribe",
        initial_prompt: str | None = None,
        preset: str | None = None,
        word_timestamps: bool = False,
        source_name: str | None = None,
    ) -> SubtitleFetchResult:
        if not self.supports(url):
            raise DownloadError("URL is not supported by the YouTube subtitle provider.")

        info = self._extract_info(url, cookies_path=cookies_path, proxy=proxy)
        track = self._select_track(info, preferred_language=language)
        if track is None:
            raise SubtitleUnavailableError("No usable native subtitles were found for this YouTube URL.")

        payload = self._download_text(track["url"], proxy=proxy)
        transcript_language = str(track.get("language") or language or "unknown")
        title = _clean_title(info.get("title"))
        media_name = source_name or title or _youtube_media_name(info, url)
        transcript = self._build_transcript(
            media_name=media_name,
            subtitle_payload=payload,
            subtitle_format=str(track.get("ext") or ""),
            transcript_language=transcript_language,
            provider_name=YOUTUBE_SUBTITLE_PROVIDER_NAME,
            task=task,
            initial_prompt=initial_prompt,
            preset=preset,
            word_timestamps=word_timestamps,
            source_url=url,
            title=title,
            source_kind=str(track.get("source_kind") or "subtitles"),
        )
        return SubtitleFetchResult(
            transcript=transcript,
            language=transcript_language,
            source_kind=str(track.get("source_kind") or "subtitles"),
            title=title,
            subtitle_format=str(track.get("ext") or ""),
        )

    def _extract_info(self, url: str, *, cookies_path: Path | None, proxy: str | None) -> dict:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError as YtDlpDownloadError
        except ImportError as exc:
            raise DownloadError("yt-dlp is not installed. Run `python -m pip install -e .`.") from exc

        options = {
            "skip_download": True,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            **yt_dlp_proxy_options(proxy),
            **yt_dlp_site_options(url),
        }
        cookiefile = resolve_cookies_path(cookies_path)
        if cookiefile:
            options["cookiefile"] = cookiefile
        try:
            with YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False)
        except YtDlpDownloadError as exc:
            raise DownloadError(f"Could not inspect YouTube subtitles: {exc}") from exc

    def _select_track(self, info: Mapping[str, object], *, preferred_language: str | None) -> dict[str, str] | None:
        subtitles = info.get("subtitles") or {}
        automatic_captions = info.get("automatic_captions") or {}
        normalized_preferred = (preferred_language or "").strip().lower()
        if normalized_preferred:
            manual_preferred = self._best_track_from_map(
                subtitles,
                normalized_preferred,
                source_kind="subtitles",
                preferred_only=True,
            )
            if manual_preferred is not None:
                return manual_preferred
            automatic_preferred = self._best_track_from_map(
                automatic_captions,
                normalized_preferred,
                source_kind="automatic_captions",
                preferred_only=True,
            )
            if automatic_preferred is not None:
                return automatic_preferred

        manual_any = self._best_track_from_map(
            subtitles,
            normalized_preferred,
            source_kind="subtitles",
            preferred_only=False,
        )
        if manual_any is not None:
            return manual_any
        return self._best_track_from_map(
            automatic_captions,
            normalized_preferred,
            source_kind="automatic_captions",
            preferred_only=False,
        )

    def _best_track_from_map(
        self,
        track_map: object,
        preferred_language: str,
        *,
        source_kind: str,
        preferred_only: bool,
    ) -> dict[str, str] | None:
        if not isinstance(track_map, Mapping):
            return None
        ordered_languages = list(track_map.keys())
        if preferred_only and preferred_language:
            ordered_languages = [
                language
                for language in ordered_languages
                if self._language_matches_preference(str(language), preferred_language)
            ]
        elif preferred_language:
            ordered_languages.sort(key=lambda item: self._language_sort_key(str(item), preferred_language))
        for language in ordered_languages:
            entries = track_map.get(language) or ()
            best_entry = self._best_supported_entry(entries)
            if best_entry is not None:
                return {
                    "language": str(language),
                    "url": str(best_entry["url"]),
                    "ext": str(best_entry["ext"]),
                    "source_kind": source_kind,
                }
        return None

    def _best_supported_entry(self, entries: object) -> dict[str, str] | None:
        if not isinstance(entries, list):
            return None
        for ext in ("vtt", "json3", "ttml"):
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                entry_ext = str(entry.get("ext") or "").lower()
                entry_url = entry.get("url")
                if entry_ext == ext and entry_url:
                    return {"ext": entry_ext, "url": str(entry_url)}
        return None

    @staticmethod
    def _language_sort_key(language: str, preferred_language: str) -> tuple[int, str]:
        normalized = language.lower()
        if normalized == preferred_language:
            return (0, normalized)
        if YouTubeNativeSubtitleProvider._language_matches_preference(normalized, preferred_language):
            return (1, normalized)
        return (2, normalized)

    @staticmethod
    def _language_matches_preference(language: str, preferred_language: str) -> bool:
        normalized = language.lower()
        preferred = preferred_language.lower()
        if normalized == preferred:
            return True
        return normalized.split("-")[0] == preferred.split("-")[0]

    def _download_text(self, url: str, *, proxy: str | None) -> str:
        opener = build_opener(*(filter(None, [proxy_handler(proxy)])))
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
            },
        )
        try:
            with opener.open(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except OSError as exc:
            raise DownloadError(f"Could not download subtitle track: {exc}") from exc

    def _build_transcript(
        self,
        *,
        media_name: str,
        subtitle_payload: str,
        subtitle_format: str,
        transcript_language: str,
        provider_name: str,
        task: str,
        initial_prompt: str | None,
        preset: str | None,
        word_timestamps: bool,
        source_url: str,
        title: str | None,
        source_kind: str,
    ) -> Transcript:
        source = MediaItem(path=Path(f"{media_name}.youtube"))
        subtitle_format = subtitle_format.lower()
        if subtitle_format == "vtt":
            segments = _parse_vtt_segments(subtitle_payload)
        elif subtitle_format == "json3":
            segments = _parse_json3_segments(subtitle_payload)
        elif subtitle_format == "ttml":
            segments = _parse_ttml_segments(subtitle_payload)
        else:
            raise TranscriptionError(f"Unsupported YouTube subtitle format: {subtitle_format}")
        if not segments:
            raise TranscriptionError("YouTube subtitle payload did not contain any transcript segments.")

        options = TranscriptionOptions(
            model_name=subtitle_format,
            language=transcript_language,
            task=task,
            beam_size=0,
            vad_filter=False,
            initial_prompt=initial_prompt,
            preset=preset,
            word_timestamps=word_timestamps,
            provider_name=provider_name,
        )
        metadata = {
            "source_url": source_url,
            "source_kind": "url",
            "subtitle_source_kind": source_kind,
            "subtitle_format": subtitle_format,
        }
        if title:
            metadata["title"] = title
        return Transcript(
            source=source,
            segments=segments,
            language=transcript_language,
            model_name=subtitle_format,
            options=options,
            metadata=metadata,
        )


def _parse_vtt_segments(payload: str) -> tuple[TranscriptSegment, ...]:
    blocks = re.split(r"\r?\n\r?\n", payload.strip())
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.rstrip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE") or lines[0].startswith("STYLE"):
            continue
        timestamp_index = 0
        if "-->" not in lines[0]:
            if len(lines) < 2 or "-->" not in lines[1]:
                continue
            timestamp_index = 1
        start_text, end_text = [part.strip().split(" ")[0] for part in lines[timestamp_index].split("-->")]
        text_lines = lines[timestamp_index + 1 :]
        text = _normalize_subtitle_text("\n".join(text_lines))
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                text=text,
                start_seconds=_parse_timestamp(start_text),
                end_seconds=_parse_timestamp(end_text),
            )
        )
    return tuple(segments)


def _parse_json3_segments(payload: str) -> tuple[TranscriptSegment, ...]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TranscriptionError("Could not parse YouTube json3 subtitle payload.") from exc
    events = data.get("events") or ()
    segments: list[TranscriptSegment] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        segs = event.get("segs") or ()
        parts: list[str] = []
        for seg in segs:
            if not isinstance(seg, Mapping):
                continue
            text = str(seg.get("utf8") or "")
            if text:
                parts.append(text)
        text = _normalize_subtitle_text("".join(parts))
        if not text:
            continue
        start_ms = event.get("tStartMs")
        duration_ms = event.get("dDurationMs")
        start_seconds = float(start_ms) / 1000.0 if start_ms is not None else None
        end_seconds = (
            start_seconds + (float(duration_ms) / 1000.0)
            if start_seconds is not None and duration_ms is not None
            else None
        )
        segments.append(
            TranscriptSegment(
                text=text,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )
        )
    return tuple(segments)


def _parse_ttml_segments(payload: str) -> tuple[TranscriptSegment, ...]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise TranscriptionError("Could not parse YouTube TTML subtitle payload.") from exc
    segments: list[TranscriptSegment] = []
    for node in root.iter():
        if not node.tag.endswith("p"):
            continue
        text = _normalize_subtitle_text("".join(node.itertext()))
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                text=text,
                start_seconds=_parse_timestamp(node.attrib.get("begin")),
                end_seconds=_parse_timestamp(node.attrib.get("end")),
            )
        )
    return tuple(segments)


def _normalize_subtitle_text(value: str) -> str:
    text = html.unescape(value.replace("\r", "").replace("\n", " "))
    text = _TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_timestamp(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    if text.endswith("s") and text.count(":") == 0:
        return float(text[:-1])
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(text)
    except ValueError as exc:
        raise TranscriptionError(f"Invalid subtitle timestamp: {value}") from exc


def _youtube_media_name(info: Mapping[str, object], url: str) -> str:
    video_id = info.get("id")
    if video_id:
        return f"youtube-{video_id}"
    hostname = (urlparse(url).hostname or "youtube").replace(".", "-")
    return hostname


def _clean_title(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
