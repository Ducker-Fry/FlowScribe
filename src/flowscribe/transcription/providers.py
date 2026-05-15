"""Transcription provider boundary and default provider selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from flowscribe.core.ports import Transcriber
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber

ProviderCostTier = Literal["free-local", "usage-based", "fixed-paid", "unknown"]
ProviderLatencyTier = Literal["fast-local", "medium-local", "network-bound", "unknown"]


@dataclass(frozen=True)
class ProviderCapabilities:
    """Explicit capability metadata for one transcription provider."""

    provider_name: str
    display_name: str
    default_model_name: str
    supported_model_names: tuple[str, ...]
    supports_language_hint: bool
    supports_word_timestamps: bool
    supports_initial_prompt: bool
    supports_vad_filter: bool
    supports_presets: bool
    requires_credentials: bool
    cost_tier: ProviderCostTier
    latency_tier: ProviderLatencyTier
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderTranscriptionSettings:
    """Provider-agnostic transcription request settings."""

    model_name: str
    language: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None
    preset: str | None
    word_timestamps: bool


class TranscriptionProvider(Protocol):
    """Construct transcribers and expose provider metadata."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return stable metadata about this provider."""

    def build_transcriber(self, settings: ProviderTranscriptionSettings) -> Transcriber:
        """Create a transcriber for one request."""


class LocalWhisperProvider:
    """Default local faster-whisper provider."""

    _CAPABILITIES = ProviderCapabilities(
        provider_name="local-whisper",
        display_name="Local faster-whisper",
        default_model_name="small",
        supported_model_names=(
            "tiny",
            "base",
            "small",
            "medium",
            "large-v3-turbo",
            "large-v3",
        ),
        supports_language_hint=True,
        supports_word_timestamps=True,
        supports_initial_prompt=True,
        supports_vad_filter=True,
        supports_presets=True,
        requires_credentials=False,
        cost_tier="free-local",
        latency_tier="fast-local",
        notes=(
            "Runs locally with faster-whisper and no remote API dependency.",
            "Latency depends on local hardware and selected model size.",
            "Chinese presets can align raw words into natural reading units.",
        ),
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._CAPABILITIES

    def build_transcriber(self, settings: ProviderTranscriptionSettings) -> Transcriber:
        return LocalWhisperTranscriber(
            model_name=settings.model_name,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
            word_timestamps=settings.word_timestamps,
        )


def default_transcription_provider() -> TranscriptionProvider:
    """Return the current default provider for FlowScribe."""

    return LocalWhisperProvider()


def resolve_transcription_provider(provider_name: str | None = None) -> TranscriptionProvider:
    """Resolve a provider by name while keeping local whisper as the default."""

    normalized = (provider_name or "").strip().lower()
    if normalized in {"", "default", "local", "local-whisper", "faster-whisper"}:
        return default_transcription_provider()
    raise ValueError(f"Unsupported transcription provider: {provider_name}")
