"""FunASR Paraformer transcription provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import (
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)

PARAFORMER_PROVIDER_NAME = "paraformer"
PARAFORMER_MODEL_NAME = "paraformer-zh"
PARAFORMER_FUNASR_MODEL_ID = "paraformer-zh"
PARAFORMER_FUNASR_VAD_MODEL_ID = "fsmn-vad"
PARAFORMER_FUNASR_PUNC_MODEL_ID = "ct-punc"


class ParaformerTranscriber:
    """Transcribe prepared audio with FunASR Paraformer."""

    def __init__(
        self,
        *,
        model_name: str = PARAFORMER_MODEL_NAME,
        language: str | None = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = False,
        initial_prompt: str | None = None,
        preset: str | None = None,
        word_timestamps: bool = False,
    ) -> None:
        self._model_name = model_name or PARAFORMER_MODEL_NAME
        self._language = language
        self._task = task
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._initial_prompt = initial_prompt
        self._preset = preset
        self._word_timestamps = word_timestamps
        self._model = None

    def transcribe(
        self,
        audio: PreparedAudio,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Transcript:
        try:
            if should_cancel is not None and should_cancel():
                raise CancellationError("Transcription canceled.")
            model = self._load_model()
            result = model.generate(**self._generate_kwargs(audio))
            if should_cancel is not None and should_cancel():
                raise CancellationError("Transcription canceled.")
            return self._build_transcript(audio, result, should_cancel=should_cancel)
        except ImportError as exc:
            raise TranscriptionError(
                "FunASR is not installed. Run: python -m pip install funasr modelscope"
            ) from exc
        except CancellationError:
            raise
        except Exception as exc:
            raise TranscriptionError(f"Paraformer transcription failed for {audio.path}: {exc}") from exc

    def _load_model(self):
        if self._model is None:
            from funasr import AutoModel

            self._model = AutoModel(
                model=self._resolve_model_id(self._model_name),
                vad_model=PARAFORMER_FUNASR_VAD_MODEL_ID,
                punc_model=PARAFORMER_FUNASR_PUNC_MODEL_ID,
            )
        return self._model

    def _generate_kwargs(self, audio: PreparedAudio) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "input": str(audio.path),
            "use_itn": True,
            "batch_size_s": 300,
            "return_sentence": True,
        }
        if self._language:
            kwargs["language"] = self._language
        return kwargs

    def _build_transcript(
        self,
        audio: PreparedAudio,
        result: Any,
        *,
        should_cancel: Callable[[], bool] | None,
    ) -> Transcript:
        payload = self._primary_payload(result)
        segments = self._segments_from_payload(
            payload,
            audio_duration_seconds=audio.duration_seconds,
            should_cancel=should_cancel,
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
            provider_name=PARAFORMER_PROVIDER_NAME,
        )
        return Transcript(
            source=audio.source,
            segments=segments,
            language=self._language or "zh",
            model_name=self._model_name,
            options=options,
            metadata={"provider_result_type": type(result).__name__},
        )

    def _segments_from_payload(
        self,
        payload: dict[str, Any],
        *,
        audio_duration_seconds: float | None,
        should_cancel: Callable[[], bool] | None,
    ) -> tuple[TranscriptSegment, ...]:
        raw_sentences = (
            payload.get("sentence_info")
            or payload.get("sentences")
            or payload.get("segments")
            or ()
        )
        segments: list[TranscriptSegment] = []
        if isinstance(raw_sentences, list):
            for sentence in raw_sentences:
                if should_cancel is not None and should_cancel():
                    raise CancellationError("Transcription canceled.")
                if not isinstance(sentence, dict):
                    continue
                text = str(sentence.get("text") or sentence.get("sentence") or "").strip()
                if not text:
                    continue
                segments.append(
                    TranscriptSegment(
                        text=text,
                        start_seconds=self._timestamp_seconds(
                            self._first_present(sentence, "start", "start_time")
                        ),
                        end_seconds=self._timestamp_seconds(
                            self._first_present(sentence, "end", "end_time")
                        ),
                        raw_words=self._words_from_sentence(sentence),
                        words=self._words_from_sentence(sentence),
                    )
                )
        if segments:
            return tuple(segments)

        text = str(payload.get("text") or "").strip()
        if not text:
            return ()
        return (
            TranscriptSegment(
                text=text,
                start_seconds=0.0 if audio_duration_seconds is not None else None,
                end_seconds=audio_duration_seconds,
            ),
        )

    def _words_from_sentence(self, sentence: dict[str, Any]) -> tuple[TranscriptWord, ...]:
        if not self._word_timestamps:
            return ()
        raw_words = sentence.get("words") or sentence.get("word_info") or ()
        if not isinstance(raw_words, list):
            return ()
        words: list[TranscriptWord] = []
        for raw_word in raw_words:
            if not isinstance(raw_word, dict):
                continue
            text = str(raw_word.get("word") or raw_word.get("text") or "").strip()
            if not text:
                continue
            words.append(
                TranscriptWord(
                    text=text,
                    start_seconds=self._timestamp_seconds(
                        self._first_present(raw_word, "start", "start_time")
                    ),
                    end_seconds=self._timestamp_seconds(
                        self._first_present(raw_word, "end", "end_time")
                    ),
                    confidence=self._optional_float(
                        self._first_present(raw_word, "confidence", "probability")
                    ),
                )
            )
        return tuple(words)

    @staticmethod
    def _primary_payload(result: Any) -> dict[str, Any]:
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    return item
            return {}
        if isinstance(result, dict):
            return result
        return {}

    @staticmethod
    def _resolve_model_id(model_name: str) -> str:
        if model_name in {"", PARAFORMER_MODEL_NAME}:
            return PARAFORMER_FUNASR_MODEL_ID
        return model_name

    @staticmethod
    def _timestamp_seconds(value: Any) -> float | None:
        number = ParaformerTranscriber._optional_float(value)
        if number is None:
            return None
        if number > 1000:
            return number / 1000.0
        return number

    @staticmethod
    def _first_present(payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
