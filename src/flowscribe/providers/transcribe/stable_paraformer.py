"""Safer Paraformer adapter for FlowScribe's progressive chunk workflow."""

from __future__ import annotations

import logging
import sys
import wave
from collections.abc import Callable
from time import perf_counter
from threading import Lock
from typing import Any

import numpy as np

from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import PreparedAudio, Transcript
from flowscribe.model_manager import paraformer_component_paths, runtime_model_reference
from flowscribe.providers.transcribe.paraformer import (
    PARAFORMER_MODEL_NAME,
    ParaformerTranscriber,
    ensure_funasr_runtime_importable,
)
from flowscribe.utils.subprocess_trace_scope import (
    trace_funasr_audio_loading_scope,
    trace_subprocess_scope,
)

LOGGER = logging.getLogger(__name__)
_ASR_ONLY_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}
_ASR_ONLY_MODEL_CACHE_LOCK = Lock()


class StableParaformerTranscriber(ParaformerTranscriber):
    """Use ASR-only Paraformer for already-windowed clips.

    FlowScribe's progressive executor has already split audio into small windows.
    Running FunASR's VAD pipeline again inside each window can create tiny
    internal VAD spans, which are the common trigger for FunASR's negative
    tensor-dimension failure. Clip transcription therefore bypasses the nested
    VAD model and lets the final pipeline guard decide whether an all-empty
    transcript is a real failure.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._clip_model = None

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Transcript:
        if should_cancel is not None and should_cancel():
            raise CancellationError("Transcription canceled.")

        clip_audio = self._extract_clip_audio(
            audio,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            accurate_seek=True,
            pad_silence_seconds=0.2,
            file_suffix="-asr",
        )
        try:
            model = self._load_clip_model()
            generate_label = (
                "paraformer-generate "
                f"chunk={start_seconds:.3f}-{end_seconds:.3f} clip={clip_audio.path.name}"
            )
            generate_kwargs = self._clip_generate_kwargs(clip_audio)
            generate_started_at = perf_counter()
            LOGGER.info("Paraformer clip generate starting: %s", generate_label)
            LOGGER.info(
                "Paraformer clip generate payload: input_type=%s input_shape=%s fs=%s",
                type(generate_kwargs.get("input")).__name__,
                getattr(generate_kwargs.get("input"), "shape", None),
                generate_kwargs.get("fs"),
            )
            with trace_subprocess_scope(generate_label, logger=LOGGER):
                with trace_funasr_audio_loading_scope(generate_label, logger=LOGGER):
                    result = model.generate(**generate_kwargs)
            LOGGER.info(
                "Paraformer clip generate finished: %s elapsed=%.3fs",
                generate_label,
                perf_counter() - generate_started_at,
            )
            if should_cancel is not None and should_cancel():
                raise CancellationError("Transcription canceled.")
            return self._build_transcript(clip_audio, result, should_cancel=should_cancel)
        except CancellationError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Paraformer clip transcription failed for {clip_audio.path}: {exc}"
            ) from exc
        finally:
            clip_audio.path.unlink(missing_ok=True)

    def _load_clip_model(self):
        if self._clip_model is None:
            self._configure_external_model_cache()
            import_started_at = perf_counter()
            LOGGER.info("Paraformer clip model import starting.")
            with trace_subprocess_scope("paraformer-import", logger=LOGGER):
                ensure_funasr_runtime_importable()
            LOGGER.info(
                "Paraformer clip model import finished: elapsed=%.3fs",
                perf_counter() - import_started_at,
            )
            from funasr import AutoModel

            runtime_model_reference("paraformer", self._model_name or PARAFORMER_MODEL_NAME)
            model_path, _vad_model_path, punc_model_path = paraformer_component_paths(
                ensure_download=True
            )
            device = self._resolve_device()
            cache_key = (str(model_path), str(punc_model_path), device)
            with _ASR_ONLY_MODEL_CACHE_LOCK:
                cached_model = _ASR_ONLY_MODEL_CACHE.get(cache_key)
                if cached_model is None:
                    LOGGER.info(
                        "Loading ASR-only Paraformer clip model: model=%s punc=%s device=%s "
                        "frozen=%s executable=%s",
                        model_path,
                        punc_model_path,
                        device,
                        bool(getattr(sys, "frozen", False)),
                        sys.executable,
                    )
                    model_started_at = perf_counter()
                    with trace_subprocess_scope("paraformer-automodel-init", logger=LOGGER):
                        cached_model = AutoModel(
                            model=str(model_path),
                            punc_model=str(punc_model_path),
                            disable_update=True,
                            device=device,
                        )
                    LOGGER.info(
                        "ASR-only Paraformer clip model initialized: elapsed=%.3fs",
                        perf_counter() - model_started_at,
                    )
                    _ASR_ONLY_MODEL_CACHE[cache_key] = cached_model
                else:
                    LOGGER.info("Reusing ASR-only Paraformer clip model: device=%s", device)
            self._clip_model = cached_model
        return self._clip_model

    def _clip_generate_kwargs(self, audio: PreparedAudio) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "input": self._load_clip_waveform(audio),
            "fs": audio.sample_rate,
            "use_itn": True,
            "batch_size": 1,
            "disable_pbar": True,
        }
        if self._language:
            kwargs["language"] = self._language
        return kwargs

    @staticmethod
    def _load_clip_waveform(audio: PreparedAudio) -> np.ndarray:
        try:
            with wave.open(str(audio.path), "rb") as wav_file:
                sample_width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                frame_count = wav_file.getnframes()
                frame_bytes = wav_file.readframes(frame_count)
        except (OSError, wave.Error) as exc:
            raise TranscriptionError(f"Failed to read Paraformer clip WAV {audio.path}: {exc}") from exc

        if sample_width != 2:
            raise TranscriptionError(
                f"Paraformer clip WAV must be 16-bit PCM, got sample width {sample_width} for {audio.path}"
            )

        waveform = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            waveform = waveform.reshape(-1, channels).mean(axis=1)
        return waveform
