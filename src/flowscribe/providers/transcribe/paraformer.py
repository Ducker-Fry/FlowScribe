"""FunASR Paraformer transcription provider."""

from __future__ import annotations

import os
import subprocess
import sys
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import (
    MediaItem,
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)
from flowscribe.media.tools import resolve_tool_path
from flowscribe.utils.subprocess import hidden_subprocess_kwargs

PARAFORMER_PROVIDER_NAME = "paraformer"
PARAFORMER_MODEL_NAME = "paraformer-zh"
PARAFORMER_FUNASR_MODEL_ID = (
    "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
)
PARAFORMER_FUNASR_VAD_MODEL_ID = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
PARAFORMER_FUNASR_PUNC_MODEL_ID = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _default_models_root() -> Path:
    """Resolve bundled/source model root without pointing frozen builds at _internal."""
    if bool(getattr(sys, "frozen", False)):
        executable_dir = Path(sys.executable).resolve().parent
        return executable_dir / "models"
    return PROJECT_ROOT / "models"


MODELS_ROOT = Path(os.environ.get("FLOWSCRIBE_MODELS_DIR") or _default_models_root())
PARAFORMER_MODEL_DIR = MODELS_ROOT / PARAFORMER_MODEL_NAME
PARAFORMER_VAD_MODEL_DIR = MODELS_ROOT / "fsmn-vad"
PARAFORMER_PUNC_MODEL_DIR = MODELS_ROOT / "ct-punc"
DEFAULT_EXTERNAL_MODEL_CACHE_ROOT = Path("E:/Download Resource/FlowScribe/model-cache")
LOGGER = logging.getLogger(__name__)


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
        self._ffmpeg_executable = resolve_tool_path("ffmpeg")

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

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Transcript:
        clip_audio = self._extract_clip_audio(
            audio,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
        try:
            return self.transcribe(clip_audio, should_cancel=should_cancel)
        except TranscriptionError as exc:
            raise TranscriptionError(
                f"Paraformer clip transcription failed for {audio.path} "
                f"[{start_seconds}, {end_seconds}]: {exc}"
            ) from exc
        finally:
            clip_audio.path.unlink(missing_ok=True)

    def _load_model(self):
        if self._model is None:
            self._configure_external_model_cache()
            from funasr import AutoModel

            model_path = self._ensure_model_snapshot(
                self._resolve_model_id(self._model_name),
                PARAFORMER_MODEL_DIR,
            )
            vad_model_path = self._ensure_model_snapshot(
                PARAFORMER_FUNASR_VAD_MODEL_ID,
                PARAFORMER_VAD_MODEL_DIR,
            )
            punc_model_path = self._ensure_model_snapshot(
                PARAFORMER_FUNASR_PUNC_MODEL_ID,
                PARAFORMER_PUNC_MODEL_DIR,
            )
            LOGGER.info(
                "Loading Paraformer model: model=%s vad=%s punc=%s frozen=%s executable=%s",
                model_path,
                vad_model_path,
                punc_model_path,
                bool(getattr(sys, "frozen", False)),
                sys.executable,
            )
            self._model = AutoModel(
                model=str(model_path),
                vad_model=str(vad_model_path),
                punc_model=str(punc_model_path),
                disable_update=True,
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

    def _extract_clip_audio(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
    ) -> PreparedAudio:
        if end_seconds <= start_seconds:
            raise TranscriptionError("Clip end must be greater than clip start.")
        clip_dir = audio.path.parent / ".paraformer-clips"
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = clip_dir / (
            f"{audio.path.stem}-{_safe_timestamp(start_seconds)}-"
            f"{_safe_timestamp(end_seconds)}.wav"
        )
        duration_seconds = end_seconds - start_seconds
        command = [
            self._ffmpeg_executable,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            str(audio.path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(audio.sample_rate),
            "-acodec",
            "pcm_s16le",
            str(clip_path),
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
            raise TranscriptionError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise TranscriptionError(f"ffmpeg failed while slicing Paraformer clip: {message}") from exc
        return PreparedAudio(
            source=MediaItem(path=audio.source.path),
            path=clip_path,
            sample_rate=audio.sample_rate,
            duration_seconds=duration_seconds,
        )

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
    def _ensure_model_snapshot(model_id: str, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        if _looks_like_funasr_model_dir(target_dir):
            LOGGER.debug("Using existing Paraformer model directory for %s: %s", model_id, target_dir)
            return target_dir

        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except ImportError as exc:
            raise ImportError("modelscope is required to download Paraformer models") from exc

        snapshot_path = snapshot_download(
            model_id=model_id,
            local_dir=str(target_dir),
            cache_dir=str(DEFAULT_EXTERNAL_MODEL_CACHE_ROOT / "modelscope"),
        )
        return Path(snapshot_path)

    @staticmethod
    def _configure_external_model_cache() -> None:
        cache_root = DEFAULT_EXTERNAL_MODEL_CACHE_ROOT
        cache_root.mkdir(parents=True, exist_ok=True)
        defaults = {
            "HF_HOME": cache_root / "huggingface",
            "HUGGINGFACE_HUB_CACHE": cache_root / "huggingface" / "hub",
            "TRANSFORMERS_CACHE": cache_root / "huggingface" / "transformers",
            "MODELSCOPE_CACHE": cache_root / "modelscope",
        }
        for name, path in defaults.items():
            os.environ.setdefault(name, str(path))

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


def _looks_like_funasr_model_dir(path: Path) -> bool:
    return (path / "configuration.json").exists() or (path / "config.yaml").exists()


def _safe_timestamp(value: float) -> str:
    return f"{max(0.0, value):.3f}".replace(".", "p")
