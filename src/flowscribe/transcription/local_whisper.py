"""Local Whisper transcription provider."""

from __future__ import annotations

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import (
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)
from flowscribe.nlp.segmenter import align_chinese_words

LOCAL_WHISPER_PROVIDER_NAME = "local-whisper"


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
        word_timestamps: bool = False,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._task = task
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._initial_prompt = initial_prompt
        self._preset = preset
        self._word_timestamps = word_timestamps
        self._model = None

    def transcribe(self, audio: PreparedAudio) -> Transcript:
        try:
            return self._transcribe_internal(audio)
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. Run: python -m pip install faster-whisper"
            ) from exc
        except Exception as exc:
            raise TranscriptionError(f"Local transcription failed for {audio.path}: {exc}") from exc

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
    ) -> Transcript:
        try:
            return self._transcribe_internal(
                audio,
                clip_start_seconds=start_seconds,
                clip_end_seconds=end_seconds,
            )
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. Run: python -m pip install faster-whisper"
            ) from exc
        except Exception as exc:
            raise TranscriptionError(
                f"Local clip transcription failed for {audio.path} [{start_seconds}, {end_seconds}]: {exc}"
            ) from exc

    def _transcribe_internal(
        self,
        audio: PreparedAudio,
        *,
        clip_start_seconds: float | None = None,
        clip_end_seconds: float | None = None,
    ) -> Transcript:
        model = self._load_model()
        kwargs = {
            "language": self._language,
            "task": self._task,
            "beam_size": self._beam_size,
            "vad_filter": self._vad_filter,
            "initial_prompt": self._initial_prompt,
            "word_timestamps": self._word_timestamps,
        }
        if clip_start_seconds is not None and clip_end_seconds is not None:
            kwargs["clip_timestamps"] = [clip_start_seconds, clip_end_seconds]
        segments, info = model.transcribe(str(audio.path), **kwargs)
        language = getattr(info, "language", None) or self._language
        transcript_segments = tuple(
            self._build_segment(segment, language=language)
            for segment in segments
            if segment.text.strip()
        )

        options = TranscriptionOptions(
            model_name=self._model_name,
            language=self._language,
            task=self._task,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            initial_prompt=self._initial_prompt,
            preset=self._preset,
            word_timestamps=self._word_timestamps,
            provider_name=LOCAL_WHISPER_PROVIDER_NAME,
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

    def fork_for_worker(self) -> "LocalWhisperTranscriber":
        """Create a new worker-compatible transcriber with the same settings."""

        return LocalWhisperTranscriber(
            model_name=self._model_name,
            language=self._language,
            task=self._task,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            initial_prompt=self._initial_prompt,
            preset=self._preset,
            word_timestamps=self._word_timestamps,
        )

    def _build_segment(self, segment, *, language: str | None) -> TranscriptSegment:
        text = segment.text.strip()
        raw_words = self._build_raw_words(segment)
        words = (
            align_chinese_words(text, raw_words)
            if self._should_align_chinese_words(language)
            else raw_words
        )
        return TranscriptSegment(
            text=text,
            start_seconds=float(segment.start),
            end_seconds=float(segment.end),
            raw_words=raw_words,
            words=words,
        )

    def _build_raw_words(self, segment) -> tuple[TranscriptWord, ...]:
        if not self._word_timestamps:
            return ()

        words = getattr(segment, "words", None) or ()
        transcript_words: list[TranscriptWord] = []
        for word in words:
            text = getattr(word, "word", None) or getattr(word, "text", "")
            text = str(text).strip()
            if not text:
                continue
            transcript_words.append(
                TranscriptWord(
                    text=text,
                    start_seconds=self._optional_float(getattr(word, "start", None)),
                    end_seconds=self._optional_float(getattr(word, "end", None)),
                    confidence=self._optional_float(getattr(word, "probability", None)),
                )
            )
        return tuple(transcript_words)

    def _should_align_chinese_words(self, language: str | None) -> bool:
        return self._preset == "zh" or language == "zh" or self._language == "zh"

    @staticmethod
    def _optional_float(value) -> float | None:
        if value is None:
            return None
        return float(value)
