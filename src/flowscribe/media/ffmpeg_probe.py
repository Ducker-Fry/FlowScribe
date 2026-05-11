"""Small wrapper around ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.tools import resolve_tool_path


class FfmpegProbe:
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or resolve_tool_path("ffprobe")

    def has_audio_stream(self, path: Path) -> bool:
        command = [
            self._executable,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise MediaPreparationError("ffprobe was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise MediaPreparationError(f"ffprobe failed for {path}: {message}") from exc

        payload = json.loads(completed.stdout or "{}")
        return bool(payload.get("streams"))
