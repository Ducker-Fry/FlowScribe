"""Stable public provider-layer API for FlowScribe.

Keep this module lazy so importing one provider registry path does not
eagerly import every optional provider implementation.
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
    "YOUTUBE_SUBTITLE_PROVIDER_NAME",
    "YouTubeNativeSubtitleProvider",
    "default_transcription_provider",
    "is_native_engine_provider_name",
    "resolve_transcription_provider",
]


def __getattr__(name: str) -> Any:
    if name in {"YOUTUBE_SUBTITLE_PROVIDER_NAME", "YouTubeNativeSubtitleProvider"}:
        from flowscribe.providers.subtitle import (
            YOUTUBE_SUBTITLE_PROVIDER_NAME,
            YouTubeNativeSubtitleProvider,
        )

        values = {
            "YOUTUBE_SUBTITLE_PROVIDER_NAME": YOUTUBE_SUBTITLE_PROVIDER_NAME,
            "YouTubeNativeSubtitleProvider": YouTubeNativeSubtitleProvider,
        }
        return values[name]

    if name in {
        "LocalWhisperProvider",
        "LocalWhisperTranscriber",
        "NativeEngineProvider",
        "NativeEngineTranscriber",
        "ProviderCapabilities",
        "ProviderTranscriptionSettings",
        "TranscriptionProvider",
        "default_transcription_provider",
        "is_native_engine_provider_name",
        "resolve_transcription_provider",
    }:
        from flowscribe.providers.transcribe import (
            LocalWhisperProvider,
            LocalWhisperTranscriber,
            NativeEngineProvider,
            NativeEngineTranscriber,
            ProviderCapabilities,
            ProviderTranscriptionSettings,
            TranscriptionProvider,
            default_transcription_provider,
            is_native_engine_provider_name,
            resolve_transcription_provider,
        )

        values = {
            "LocalWhisperProvider": LocalWhisperProvider,
            "LocalWhisperTranscriber": LocalWhisperTranscriber,
            "NativeEngineProvider": NativeEngineProvider,
            "NativeEngineTranscriber": NativeEngineTranscriber,
            "ProviderCapabilities": ProviderCapabilities,
            "ProviderTranscriptionSettings": ProviderTranscriptionSettings,
            "TranscriptionProvider": TranscriptionProvider,
            "default_transcription_provider": default_transcription_provider,
            "is_native_engine_provider_name": is_native_engine_provider_name,
            "resolve_transcription_provider": resolve_transcription_provider,
        }
        return values[name]

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

    raise AttributeError(name)
