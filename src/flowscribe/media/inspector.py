"""Media inspection helpers for local files."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.tools import resolve_tool_path


@dataclass(frozen=True)
class LocalMediaInspection:
    source: Path
    exists: bool
    duration_seconds: float | None
    has_audio: bool
    has_video: bool
    audio_streams: int
    video_streams: int
    format_name: str | None
    size_bytes: int | None


class LocalMediaInspector:
    def __init__(self, *, ffprobe_executable: str | None = None, timeout_seconds: int = 30) -> None:
        self._ffprobe_executable = ffprobe_executable or resolve_tool_path("ffprobe")
        self._timeout_seconds = timeout_seconds

    def inspect(self, path: Path) -> LocalMediaInspection:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            return LocalMediaInspection(
                source=resolved,
                exists=False,
                duration_seconds=None,
                has_audio=False,
                has_video=False,
                audio_streams=0,
                video_streams=0,
                format_name=None,
                size_bytes=None,
            )

        command = [
            self._ffprobe_executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name,size",
            "-show_streams",
            "-of",
            "json",
            str(resolved),
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
            raise MediaPreparationError("ffprobe was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaPreparationError(f"Timed out while inspecting {resolved}.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise MediaPreparationError(f"ffprobe failed for {resolved}: {message}") from exc

        payload = json.loads(completed.stdout or "{}")
        streams = payload.get("streams") or []
        audio_streams = sum(1 for stream in streams if stream.get("codec_type") == "audio")
        video_streams = sum(1 for stream in streams if stream.get("codec_type") == "video")
        media_format = payload.get("format") or {}

        return LocalMediaInspection(
            source=resolved,
            exists=True,
            duration_seconds=_optional_float(media_format.get("duration")),
            has_audio=audio_streams > 0,
            has_video=video_streams > 0,
            audio_streams=audio_streams,
            video_streams=video_streams,
            format_name=media_format.get("format_name"),
            size_bytes=_optional_int(media_format.get("size")),
        )


def _optional_float(value) -> float | None:
    if value in {None, "", "N/A"}:
        return None
    return float(value)


def _optional_int(value) -> int | None:
    if value in {None, "", "N/A"}:
        return None
    return int(value)
