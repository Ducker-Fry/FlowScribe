"""Progressive transcription planning - chunk planning and duration probing."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Protocol

from flowscribe.core.errors import MediaPreparationError
from flowscribe.core.models import (
    MediaDurationInfo,
    PreparedAudio,
    Transcript,
    TranscriptionChunk,
    TranscriptionChunkPlan,
)

DEFAULT_PROGRESSIVE_CHUNK_OVERLAP_SECONDS = 3.0
CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS = 4.0


class ClipTranscriber(Protocol):
    """Transcriber that can operate on one audio clip range at a time."""

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
    ) -> Transcript:
        """Transcribe one clip range from prepared audio."""


class PreparedAudioDurationProbe:
    """Determine usable duration metadata from prepared WAV audio."""

    def probe(self, audio: PreparedAudio) -> MediaDurationInfo:
        duration_seconds = audio.duration_seconds
        if duration_seconds is None:
            duration_seconds = self._probe_wave_duration(audio.path)
        return MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=duration_seconds,
        )

    @staticmethod
    def _probe_wave_duration(path: Path) -> float:
        try:
            with wave.open(str(path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
        except (FileNotFoundError, wave.Error, OSError) as exc:
            raise MediaPreparationError(f"Could not determine audio duration for {path}: {exc}") from exc

        if frame_rate <= 0:
            raise MediaPreparationError(f"Could not determine audio duration for {path}: invalid frame rate.")
        return frame_count / float(frame_rate)


def tuned_chunk_overlap_seconds(
    *,
    requested_overlap_seconds: float,
    language: str | None = None,
    preset: str | None = None,
) -> float:
    overlap = float(requested_overlap_seconds)
    normalized_language = (language or "").strip().lower()
    normalized_preset = (preset or "").strip().lower()
    if (
        abs(overlap - DEFAULT_PROGRESSIVE_CHUNK_OVERLAP_SECONDS) < 1e-9
        and (normalized_language == "zh" or normalized_preset == "zh")
    ):
        return CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS
    return overlap


class FixedDurationChunkPlanner:
    """Plan overlapping clip windows across one prepared audio duration."""

    def __init__(
        self,
        *,
        chunk_duration_seconds: float = 30.0,
        chunk_overlap_seconds: float = 3.0,
    ) -> None:
        if chunk_duration_seconds <= 0:
            raise ValueError("chunk_duration_seconds must be greater than zero.")
        if chunk_overlap_seconds < 0:
            raise ValueError("chunk_overlap_seconds cannot be negative.")
        if chunk_overlap_seconds >= chunk_duration_seconds:
            raise ValueError("chunk_overlap_seconds must be smaller than chunk_duration_seconds.")
        self._chunk_duration_seconds = float(chunk_duration_seconds)
        self._chunk_overlap_seconds = float(chunk_overlap_seconds)

    def plan(self, duration_info: MediaDurationInfo) -> TranscriptionChunkPlan:
        duration_seconds = duration_info.duration_seconds
        if duration_seconds is None:
            raise MediaPreparationError(
                f"Prepared audio duration is unknown for {duration_info.prepared_audio_path}."
            )
        if duration_seconds <= 0:
            raise MediaPreparationError(
                f"Prepared audio duration is invalid for {duration_info.prepared_audio_path}."
            )

        step_seconds = self._chunk_duration_seconds - self._chunk_overlap_seconds
        chunks: list[TranscriptionChunk] = []
        chunk_index = 1
        start_seconds = 0.0
        while start_seconds < duration_seconds:
            end_seconds = min(duration_seconds, start_seconds + self._chunk_duration_seconds)
            chunks.append(
                TranscriptionChunk(
                    index=chunk_index,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    overlap_seconds=self._chunk_overlap_seconds,
                )
            )
            if end_seconds >= duration_seconds:
                break
            start_seconds += step_seconds
            chunk_index += 1

        return TranscriptionChunkPlan(
            duration_info=duration_info,
            chunks=tuple(chunks),
            chunk_duration_seconds=self._chunk_duration_seconds,
            chunk_overlap_seconds=self._chunk_overlap_seconds,
        )
