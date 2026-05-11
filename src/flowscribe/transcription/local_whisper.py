"""Local Whisper transcription provider."""

from __future__ import annotations

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import (
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptionOptions,
)


class LocalWhisperTranscriber:
    def __init__(
        self,
        *,
        model_name: str = "small",
        language: str | None = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = False,
        initial_prompt: str | None = None,
        preset: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._task = task
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._initial_prompt = initial_prompt
        self._preset = preset
        self._model = None

    def transcribe(self, audio: PreparedAudio) -> Transcript:
        try:
            model = self._load_model()
            segments, info = model.transcribe(
                str(audio.path),
                language=self._language,
                task=self._task,
                beam_size=self._beam_size,
                vad_filter=self._vad_filter,
                initial_prompt=self._initial_prompt,
            )
            transcript_segments = tuple(
                TranscriptSegment(
                    text=segment.text.strip(),
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                )
                for segment in segments
                if segment.text.strip()
            )
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. Run: python -m pip install faster-whisper"
            ) from exc
        except Exception as exc:
            raise TranscriptionError(f"Local transcription failed for {audio.path}: {exc}") from exc

        language = getattr(info, "language", None) or self._language
        options = TranscriptionOptions(
            model_name=self._model_name,
            language=self._language,
            task=self._task,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            initial_prompt=self._initial_prompt,
            preset=self._preset,
        )
        return Transcript(
            source=audio.source,
            segments=transcript_segments,
            language=language,
            model_name=self._model_name,
            options=options,
        )

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self._model_name, device="auto", compute_type="auto")
        return self._model
