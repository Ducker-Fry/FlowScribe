"""Prepare transcription-ready audio with ffmpeg."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

from flowscribe.core.errors import MediaPreparationError
from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.media.ffmpeg_probe import FfmpegProbe
from flowscribe.media.tools import resolve_tool_path
from flowscribe.utils.subprocess import hidden_subprocess_kwargs


class FfmpegAudioExtractor:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        ffmpeg_executable: str | None = None,
        probe: FfmpegProbe | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._ffmpeg_executable = ffmpeg_executable or resolve_tool_path("ffmpeg")
        self._probe = probe or FfmpegProbe()

    def prepare(self, item: MediaItem, work_dir: Path) -> PreparedAudio:
        if not self._probe.has_audio_stream(item.path):
            raise MediaPreparationError(f"No audio stream found in {item.path}")

        work_dir.mkdir(parents=True, exist_ok=True)
        audio_path = work_dir / f"{item.path.stem}.wav"
        command = [
            self._ffmpeg_executable,
            "-y",
            "-i",
            str(item.path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(self._sample_rate),
            "-acodec",
            "pcm_s16le",
            str(audio_path),
        ]
        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                **hidden_subprocess_kwargs(),
            )
        except FileNotFoundError as exc:
            raise MediaPreparationError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise MediaPreparationError(f"ffmpeg failed for {item.path}: {message}") from exc

        return PreparedAudio(
            source=item,
            path=audio_path,
            sample_rate=self._sample_rate,
            duration_seconds=self._probe_duration_seconds(audio_path),
        )

    @staticmethod
    def _probe_duration_seconds(audio_path: Path) -> float | None:
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
        except (wave.Error, OSError):
            return None
        if frame_rate <= 0:
            return None
        return frame_count / float(frame_rate)


class PreparedAudioCache:
    """Cache prepared WAV files to avoid redundant ffmpeg extraction.

    Uses the source file's modification time and size as cache validation.
    One cache entry per source file, keyed by a hash of the resolved path.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir

    def get(self, item: MediaItem) -> PreparedAudio | None:
        """Return a cached PreparedAudio if the source file is unchanged."""
        marker = self._read_marker(item)
        if marker is None:
            return None
        current_stat = self._source_stat(item)
        if current_stat is None:
            return None
        if (
            marker.get("source_mtime") != current_stat.st_mtime
            or marker.get("source_size") != current_stat.st_size
        ):
            return None
        wav_path = self._marker_path(item).with_suffix(".wav")
        if not wav_path.exists():
            return None
        return PreparedAudio(
            source=item,
            path=wav_path,
            sample_rate=int(marker["sample_rate"]),
            duration_seconds=marker.get("duration_seconds"),
        )

    def put(self, audio: PreparedAudio) -> None:
        """Store a prepared audio file in the cache."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        source_stat = self._source_stat(audio.source)
        if source_stat is None:
            return
        marker_path = self._marker_path(audio.source)
        wav_path = marker_path.with_suffix(".wav")
        shutil.copy2(str(audio.path), str(wav_path))
        marker_path.write_text(
            json.dumps(
                {
                    "source_path": str(audio.source.path.resolve()),
                    "source_mtime": source_stat.st_mtime,
                    "source_size": source_stat.st_size,
                    "sample_rate": audio.sample_rate,
                    "duration_seconds": audio.duration_seconds,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def clear(self, item: MediaItem) -> None:
        """Remove the cached entry for a specific source file."""
        marker_path = self._marker_path(item)
        marker_path.unlink(missing_ok=True)
        marker_path.with_suffix(".wav").unlink(missing_ok=True)

    def clear_all(self) -> None:
        """Remove all cached prepared audio files."""
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir, ignore_errors=True)

    def _marker_path(self, item: MediaItem) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(item.path.resolve()).encode("utf-8")).hexdigest()[:16]
        return self._cache_dir / f"{key}.json"

    def _read_marker(self, item: MediaItem) -> dict | None:
        path = self._marker_path(item)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _source_stat(item: MediaItem) -> os.stat_result | None:
        try:
            return item.path.stat()
        except OSError:
            return None
