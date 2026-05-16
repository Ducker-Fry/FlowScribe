"""Prepare transcription-ready audio with ffmpeg."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from flowscribe.core.errors import MediaPreparationError
from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.media.ffmpeg_probe import FfmpegProbe
from flowscribe.media.tools import resolve_tool_path


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
            subprocess.run(command, capture_output=True, text=True, check=True)
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
