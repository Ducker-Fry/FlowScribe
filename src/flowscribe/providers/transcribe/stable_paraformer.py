"""Safer Paraformer adapter for FlowScribe's progressive chunk workflow."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from threading import Lock
from typing import Any

from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import PreparedAudio, Transcript
from flowscribe.model_manager import paraformer_component_paths, runtime_model_reference
from flowscribe.providers.transcribe.paraformer import (
    PARAFORMER_MODEL_NAME,
    ParaformerTranscriber,
    ensure_funasr_runtime_importable,
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
            result = model.generate(**self._clip_generate_kwargs(clip_audio))
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
            ensure_funasr_runtime_importable()
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
                    cached_model = AutoModel(
                        model=str(model_path),
                        punc_model=str(punc_model_path),
                        disable_update=True,
                        device=device,
                    )
                    _ASR_ONLY_MODEL_CACHE[cache_key] = cached_model
                else:
                    LOGGER.info("Reusing ASR-only Paraformer clip model: device=%s", device)
            self._clip_model = cached_model
        return self._clip_model

    def _clip_generate_kwargs(self, audio: PreparedAudio) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "input": str(audio.path),
            "use_itn": True,
            "batch_size": 1,
            "disable_pbar": True,
        }
        if self._language:
            kwargs["language"] = self._language
        return kwargs
