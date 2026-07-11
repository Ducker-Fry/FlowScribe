"""Transcription provider adapters and registry.

Keep this package init lazy so importing the registry does not eagerly import
optional provider implementations.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "LocalWhisperProvider",
    "LocalWhisperTranscriber",
    "NativeEngineProvider",
    "NativeEngineTranscriber",
    "PARAFORMER_MODEL_NAME",
    "ParaformerProvider",
    "ParaformerTranscriber",
    "ProviderCapabilities",
    "ProviderTranscriptionSettings",
    "TranscriptionProvider",
    "default_transcription_provider",
    "is_native_engine_provider_name",
    "resolve_transcription_provider",
]


def __getattr__(name: str) -> Any:
    if name == "LocalWhisperTranscriber":
        from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber

        return LocalWhisperTranscriber

    if name == "NativeEngineTranscriber":
        from flowscribe.providers.transcribe.native_engine import NativeEngineTranscriber

        return NativeEngineTranscriber

    if name in {"PARAFORMER_MODEL_NAME", "ParaformerProvider", "ParaformerTranscriber"}:
        from flowscribe.providers.transcribe.paraformer import (
            PARAFORMER_MODEL_NAME,
            ParaformerTranscriber,
        )
        from flowscribe.providers.transcribe.registry import ParaformerProvider

        values = {
            "PARAFORMER_MODEL_NAME": PARAFORMER_MODEL_NAME,
            "ParaformerProvider": ParaformerProvider,
            "ParaformerTranscriber": ParaformerTranscriber,
        }
        return values[name]

    if name in {
        "LocalWhisperProvider",
        "NativeEngineProvider",
        "ProviderCapabilities",
        "ProviderTranscriptionSettings",
        "TranscriptionProvider",
        "default_transcription_provider",
        "is_native_engine_provider_name",
        "resolve_transcription_provider",
    }:
        from flowscribe.providers.transcribe.registry import (
            LocalWhisperProvider,
            NativeEngineProvider,
            ProviderCapabilities,
            ProviderTranscriptionSettings,
            TranscriptionProvider,
            default_transcription_provider,
            is_native_engine_provider_name,
            resolve_transcription_provider,
        )

        values = {
            "LocalWhisperProvider": LocalWhisperProvider,
            "NativeEngineProvider": NativeEngineProvider,
            "ProviderCapabilities": ProviderCapabilities,
            "ProviderTranscriptionSettings": ProviderTranscriptionSettings,
            "TranscriptionProvider": TranscriptionProvider,
            "default_transcription_provider": default_transcription_provider,
            "is_native_engine_provider_name": is_native_engine_provider_name,
            "resolve_transcription_provider": resolve_transcription_provider,
        }
        return values[name]

    raise AttributeError(name)
