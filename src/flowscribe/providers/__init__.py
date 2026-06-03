"""Stable public provider-layer API for FlowScribe."""

from flowscribe.providers.subtitle import (
    YOUTUBE_SUBTITLE_PROVIDER_NAME,
    YouTubeNativeSubtitleProvider,
)
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
from flowscribe.providers.transcribe.paraformer import (
    PARAFORMER_MODEL_NAME,
    ParaformerTranscriber,
)
from flowscribe.providers.transcribe.registry import ParaformerProvider

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
