"""Transcription provider adapters and registry."""

from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber
from flowscribe.providers.transcribe.native_engine import NativeEngineTranscriber
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

__all__ = [
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
]
