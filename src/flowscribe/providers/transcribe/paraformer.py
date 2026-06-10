"""FunASR Paraformer transcription provider."""

from __future__ import annotations

import os
import subprocess
import logging
import sys
import wave
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any

from flowscribe.config.resources import resolve_resource_paths
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
from flowscribe.model_manager import paraformer_component_paths, runtime_model_reference
from flowscribe.utils.subprocess import hidden_subprocess_kwargs, subprocess_trace_enabled

PARAFORMER_PROVIDER_NAME = "paraformer"
PARAFORMER_MODEL_NAME = "paraformer-zh"
PARAFORMER_FUNASR_MODEL_ID = (
    "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
)
PARAFORMER_FUNASR_VAD_MODEL_ID = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
PARAFORMER_FUNASR_PUNC_MODEL_ID = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"


def _default_models_root() -> Path:
    """Compatibility helper for tests and legacy callers."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "models"
    return resolve_resource_paths().models_dir


def _default_external_model_cache_root() -> Path:
    """Use a per-user cache directory instead of a machine-specific drive path."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "FlowScribe" / "model-cache"
    return Path.home() / ".flowscribe" / "model-cache"


MODELS_ROOT = resolve_resource_paths().models_dir
PARAFORMER_MODEL_DIR = MODELS_ROOT / PARAFORMER_MODEL_NAME
PARAFORMER_VAD_MODEL_DIR = MODELS_ROOT / "fsmn-vad"
PARAFORMER_PUNC_MODEL_DIR = MODELS_ROOT / "ct-punc"
DEFAULT_EXTERNAL_MODEL_CACHE_ROOT = Path(
    os.environ.get("FLOWSCRIBE_MODEL_CACHE_DIR") or _default_external_model_cache_root()
)
LOGGER = logging.getLogger(__name__)
_SHARED_MODEL_CACHE: dict[tuple[str, str, str, str], Any] = {}
_SHARED_MODEL_CACHE_LOCK = Lock()


def ensure_funasr_runtime_importable() -> None:
    """Validate the concrete FunASR import path used by runtime transcription."""

    try:
        from funasr import AutoModel  # noqa: F401
    except ImportError as exc:
        raise TranscriptionError(
            "FunASR is not installed. Run: python -m pip install funasr modelscope"
        ) from exc


def validate_paraformer_runtime(
    model_name: str = PARAFORMER_MODEL_NAME,
    *,
    ensure_model_download: bool = True,
) -> None:
    """Raise a clear error before any job starts when Paraformer runtime is unavailable."""

    ensure_funasr_runtime_importable()
    runtime_model_reference(PARAFORMER_PROVIDER_NAME, model_name or PARAFORMER_MODEL_NAME)
    paraformer_component_paths(ensure_download=ensure_model_download)


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
        self._clip_fallback_window_seconds = 12.0
        self._clip_min_fallback_window_seconds = 6.0

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
        return self._transcribe_clip_resilient(
            audio,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            should_cancel=should_cancel,
        )

    def _transcribe_clip_resilient(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel: Callable[[], bool] | None = None,
        subdivision_window_seconds: float | None = None,
        subdivision_label: str = "",
        accurate_seek: bool = False,
        pad_silence_seconds: float = 0.0,
        file_suffix: str = "",
    ) -> Transcript:
        clip_duration_seconds = max(0.0, end_seconds - start_seconds)
        try:
            return self._transcribe_clip_attempt(
                audio,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                should_cancel=should_cancel,
                accurate_seek=accurate_seek,
                pad_silence_seconds=pad_silence_seconds,
                file_suffix=file_suffix,
            )
        except TranscriptionError as exc:
            if self._should_retry_clip_transcription(exc):
                if (
                    subdivision_label
                    and clip_duration_seconds <= self._clip_min_fallback_window_seconds + 1e-6
                ):
                    LOGGER.warning(
                        "Skipping irrecoverable tiny Paraformer sub-clip after known bad-window failure: "
                        "source=%s start=%.3f end=%.3f reason=%s",
                        audio.path,
                        start_seconds,
                        end_seconds,
                        exc,
                    )
                    return self._empty_transcript(audio)
                LOGGER.warning(
                    "Retrying Paraformer clip transcription with accurate seek and tail padding: "
                    "source=%s start=%.3f end=%.3f reason=%s",
                    audio.path,
                    start_seconds,
                    end_seconds,
                    exc,
                )
                try:
                    return self._transcribe_clip_attempt(
                        audio,
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        should_cancel=should_cancel,
                        accurate_seek=True,
                        pad_silence_seconds=0.2,
                        file_suffix=f"{file_suffix}-retry" if file_suffix else "-retry",
                    )
                except TranscriptionError as retry_exc:
                    exc = retry_exc
                    fallback = self._transcribe_clip_with_subdivide_fallback(
                        audio,
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        should_cancel=should_cancel,
                        subdivision_window_seconds=subdivision_window_seconds,
                        subdivision_label=subdivision_label,
                    )
                    if fallback is not None:
                        return fallback
            raise TranscriptionError(
                f"Paraformer clip transcription failed for {audio.path} "
                f"[{start_seconds}, {end_seconds}]: {exc}"
            ) from exc

    def _transcribe_clip_attempt(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel: Callable[[], bool] | None = None,
        accurate_seek: bool = False,
        pad_silence_seconds: float = 0.0,
        file_suffix: str = "",
    ) -> Transcript:
        clip_audio = self._extract_clip_audio(
            audio,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            accurate_seek=accurate_seek,
            pad_silence_seconds=pad_silence_seconds,
            file_suffix=file_suffix,
        )
        try:
            return self.transcribe(clip_audio, should_cancel=should_cancel)
        finally:
            clip_audio.path.unlink(missing_ok=True)

    def _load_model(self):
        if self._model is None:
            self._configure_external_model_cache()
            ensure_funasr_runtime_importable()
            from funasr import AutoModel
            runtime_model_reference("paraformer", self._model_name)

            model_path, vad_model_path, punc_model_path = paraformer_component_paths(
                ensure_download=True
            )
            LOGGER.info(
                "Loading Paraformer model: model=%s vad=%s punc=%s frozen=%s executable=%s",
                model_path,
                vad_model_path,
                punc_model_path,
                bool(getattr(sys, "frozen", False)),
                sys.executable,
            )

            device = self._resolve_device()
            cache_key = (
                str(model_path),
                str(vad_model_path),
                str(punc_model_path),
                device,
            )
            with _SHARED_MODEL_CACHE_LOCK:
                cached_model = _SHARED_MODEL_CACHE.get(cache_key)
                if cached_model is None:
                    LOGGER.info("Using device=%s for FunASR AutoModel", device)
                    cached_model = AutoModel(
                        model=str(model_path),
                        vad_model=str(vad_model_path),
                        punc_model=str(punc_model_path),
                        disable_update=True,
                        device=device,
                    )
                    _SHARED_MODEL_CACHE[cache_key] = cached_model
                else:
                    LOGGER.info("Reusing cached Paraformer model: device=%s", device)
            self._model = cached_model
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
        accurate_seek: bool = False,
        pad_silence_seconds: float = 0.0,
        file_suffix: str = "",
    ) -> PreparedAudio:
        if end_seconds <= start_seconds:
            raise TranscriptionError("Clip end must be greater than clip start.")
        clip_dir = audio.path.parent / ".paraformer-clips"
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = clip_dir / (
            f"{audio.path.stem}-{_safe_timestamp(start_seconds)}-"
            f"{_safe_timestamp(end_seconds)}{file_suffix}.wav"
        )
        duration_seconds = end_seconds - start_seconds
        output_duration_seconds = duration_seconds + max(0.0, pad_silence_seconds)
        if accurate_seek or pad_silence_seconds > 0.0:
            command = [
                self._ffmpeg_executable,
                "-y",
                "-i",
                str(audio.path),
                "-ss",
                f"{start_seconds:.3f}",
                "-t",
                f"{output_duration_seconds:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(audio.sample_rate),
            ]
            if pad_silence_seconds > 0.0:
                command.extend(["-af", f"apad=pad_dur={pad_silence_seconds:.3f}"])
            command.extend(
                [
                    "-acodec",
                    "pcm_s16le",
                    str(clip_path),
                ]
            )
        else:
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
        hidden_kwargs = hidden_subprocess_kwargs()
        try:
            if subprocess_trace_enabled():
                LOGGER.info(
                    "Paraformer clip extraction: start=%.3fs end=%.3fs output=%.3fs command=%s hidden_kwargs=%s",
                    start_seconds,
                    end_seconds,
                    output_duration_seconds,
                    command,
                    hidden_kwargs,
                )
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                **hidden_kwargs,
            )
            if subprocess_trace_enabled():
                LOGGER.info(
                    "Paraformer clip extraction finished: start=%.3fs end=%.3fs clip=%s",
                    start_seconds,
                    end_seconds,
                    clip_path,
                )
        except FileNotFoundError as exc:
            raise TranscriptionError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise TranscriptionError(f"ffmpeg failed while slicing Paraformer clip: {message}") from exc
        actual_duration_seconds = self._probe_wave_duration_seconds(clip_path)
        if actual_duration_seconds is None or actual_duration_seconds <= 0.0:
            raise TranscriptionError(
                f"Paraformer clip extraction produced an empty or unreadable clip: {clip_path}"
            )
        if actual_duration_seconds + 0.25 < duration_seconds:
            LOGGER.warning(
                "Paraformer clip shorter than expected after extraction: clip=%s expected=%.3fs actual=%.3fs",
                clip_path,
                duration_seconds,
                actual_duration_seconds,
            )
        return PreparedAudio(
            source=MediaItem(path=audio.source.path),
            path=clip_path,
            sample_rate=audio.sample_rate,
            duration_seconds=actual_duration_seconds,
        )

    def _empty_transcript(self, audio: PreparedAudio) -> Transcript:
        return Transcript(
            source=audio.source,
            segments=(),
            language=self._language or "zh",
            model_name=self._model_name,
            options=TranscriptionOptions(
                model_name=self._model_name,
                language=self._language,
                task=self._task,
                beam_size=self._beam_size,
                vad_filter=self._vad_filter,
                initial_prompt=self._initial_prompt,
                preset=self._preset,
                word_timestamps=self._word_timestamps,
                provider_name=PARAFORMER_PROVIDER_NAME,
            ),
            metadata={"provider_result_type": "skipped_tiny_bad_clip"},
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

    def _transcribe_clip_with_subdivide_fallback(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel: Callable[[], bool] | None = None,
        subdivision_window_seconds: float | None = None,
        subdivision_label: str = "",
    ) -> Transcript | None:
        clip_duration_seconds = end_seconds - start_seconds
        window_seconds = min(
            clip_duration_seconds,
            subdivision_window_seconds or self._clip_fallback_window_seconds,
        )
        if clip_duration_seconds <= self._clip_min_fallback_window_seconds + 1e-6:
            return None

        LOGGER.warning(
            "Falling back to subdivided Paraformer clip transcription: "
            "source=%s start=%.3f end=%.3f window=%.1fs",
            audio.path,
            start_seconds,
            end_seconds,
            window_seconds,
        )
        transcripts: list[Transcript] = []
        failed_parts = 0
        window_start = start_seconds
        part_index = 1
        while window_start < end_seconds - 1e-6:
            if should_cancel is not None and should_cancel():
                raise CancellationError("Transcription canceled.")
            window_end = min(end_seconds, window_start + window_seconds)
            try:
                part = self._transcribe_clip_resilient(
                    audio,
                    start_seconds=window_start,
                    end_seconds=window_end,
                    should_cancel=should_cancel,
                    subdivision_window_seconds=max(
                        self._clip_min_fallback_window_seconds,
                        window_seconds / 2.0,
                    ),
                    subdivision_label=f"{subdivision_label}-part{part_index}",
                    accurate_seek=True,
                    pad_silence_seconds=0.2,
                    file_suffix=f"{subdivision_label}-part{part_index}",
                )
                transcripts.append(self._offset_transcript(part, window_start - start_seconds))
            except TranscriptionError:
                failed_parts += 1
                LOGGER.warning(
                    "Subdivided clip part failed, continuing with remaining parts: "
                    "source=%s window=[%.3f, %.3f] failed=%d",
                    audio.path,
                    window_start,
                    window_end,
                    failed_parts,
                )
            window_start = window_end
            part_index += 1

        if not transcripts:
            return None
        return self._merge_clip_transcripts(audio, transcripts)

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
    def _configure_external_model_cache() -> None:
        cache_root = resolve_resource_paths().model_cache_dir
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

    @staticmethod
    def _probe_wave_duration_seconds(path: Path) -> float | None:
        try:
            with wave.open(str(path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
        except (EOFError, wave.Error, OSError):
            return None
        if frame_rate <= 0 or frame_count <= 0:
            return None
        return frame_count / float(frame_rate)

    @staticmethod
    def _should_retry_clip_transcription(exc: TranscriptionError) -> bool:
        message = str(exc).lower()
        return (
            "negative dimension" in message
            or "empty or unreadable clip" in message
        )

    @staticmethod
    def _offset_transcript(transcript: Transcript, offset_seconds: float) -> Transcript:
        if abs(offset_seconds) < 1e-9:
            return transcript
        return Transcript(
            source=transcript.source,
            segments=tuple(
                TranscriptSegment(
                    text=segment.text,
                    start_seconds=(
                        None if segment.start_seconds is None else segment.start_seconds + offset_seconds
                    ),
                    end_seconds=(
                        None if segment.end_seconds is None else segment.end_seconds + offset_seconds
                    ),
                    raw_words=tuple(
                        TranscriptWord(
                            text=word.text,
                            start_seconds=(
                                None if word.start_seconds is None else word.start_seconds + offset_seconds
                            ),
                            end_seconds=(
                                None if word.end_seconds is None else word.end_seconds + offset_seconds
                            ),
                            confidence=word.confidence,
                        )
                        for word in segment.raw_words
                    ),
                    words=tuple(
                        TranscriptWord(
                            text=word.text,
                            start_seconds=(
                                None if word.start_seconds is None else word.start_seconds + offset_seconds
                            ),
                            end_seconds=(
                                None if word.end_seconds is None else word.end_seconds + offset_seconds
                            ),
                            confidence=word.confidence,
                        )
                        for word in segment.words
                    ),
                )
                for segment in transcript.segments
            ),
            language=transcript.language,
            model_name=transcript.model_name,
            options=transcript.options,
            metadata=dict(transcript.metadata),
            task_id=transcript.task_id,
            document_id=transcript.document_id,
            resume_token=transcript.resume_token,
            checkpoint_id=transcript.checkpoint_id,
            cache_key=transcript.cache_key,
            created_at=transcript.created_at,
        )

    @staticmethod
    def _merge_clip_transcripts(audio: PreparedAudio, transcripts: list[Transcript]) -> Transcript:
        first = transcripts[0]
        return Transcript(
            source=audio.source,
            segments=tuple(segment for transcript in transcripts for segment in transcript.segments),
            language=first.language,
            model_name=first.model_name,
            options=first.options,
            metadata=dict(first.metadata),
            task_id=first.task_id,
            document_id=first.document_id,
            resume_token=first.resume_token,
            checkpoint_id=first.checkpoint_id,
            cache_key=first.cache_key,
            created_at=first.created_at,
        )

    @staticmethod
    def _resolve_device() -> str:
        """Determine the best device for FunASR inference in the current environment.

        Falls back to CPU when CUDA is unavailable or when torch detection fails
        (e.g., in a PyInstaller-packaged build where CUDA DLLs may not be bundled).
        """
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            return "cpu"
        except (ImportError, RuntimeError, OSError):
            return "cpu"


def _safe_timestamp(value: float) -> str:
    return f"{max(0.0, value):.3f}".replace(".", "p")
