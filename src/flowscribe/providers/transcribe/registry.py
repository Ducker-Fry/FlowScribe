"""Transcription provider boundary and default provider selection."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Protocol

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.ports import Transcriber
from flowscribe.model_manager import runtime_model_reference
from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber
from flowscribe.providers.transcribe.native_engine import (
    NativeEngineTranscriber,
    resolve_engine_exe,
)

ProviderCostTier = Literal["free-local", "usage-based", "fixed-paid", "unknown"]
ProviderLatencyTier = Literal["fast-local", "medium-local", "network-bound", "unknown"]
PARAFORMER_MODEL_NAME = "paraformer-zh"


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
    progressive_enabled: bool = True
    progressive_resume_requested: bool = False
    progressive_chunk_seconds: float = 30.0
    progressive_chunk_overlap_seconds: float = 3.0
    progressive_max_workers: int = 1
    native_threads: int | None = None


class TranscriptionProvider(Protocol):
    """Construct transcribers and expose provider metadata."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return stable metadata about this provider."""

    def build_transcriber(self, settings: ProviderTranscriptionSettings) -> Transcriber:
        """Create a transcriber for one request."""

    def validate_runtime(self, settings: ProviderTranscriptionSettings) -> None:
        """Raise a FlowScribeError when this provider cannot run in the current environment."""


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

    def validate_runtime(self, settings: ProviderTranscriptionSettings) -> None:
        try:
            __import__("faster_whisper")
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. Run: python -m pip install faster-whisper"
            ) from exc
        runtime_model_reference("local-whisper", settings.model_name)


class NativeEngineProvider:
    """Native whisper.cpp engine provider."""

    _CAPABILITIES = ProviderCapabilities(
        provider_name="native-engine",
        display_name="Native whisper.cpp engine",
        default_model_name="models/ggml-base.en.bin",
        supported_model_names=(),
        supports_language_hint=True,
        supports_word_timestamps=True,
        supports_initial_prompt=True,
        supports_vad_filter=True,
        supports_presets=True,
        requires_credentials=False,
        cost_tier="free-local",
        latency_tier="fast-local",
        notes=(
            "Runs a local C++ whisper.cpp engine over the FlowScribe named-pipe protocol.",
            "The model setting must be a local ggml .bin file path.",
        ),
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._CAPABILITIES

    def build_transcriber(self, settings: ProviderTranscriptionSettings) -> Transcriber:
        return NativeEngineTranscriber(
            model_name=settings.model_name,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
            word_timestamps=settings.word_timestamps,
            progressive_enabled=settings.progressive_enabled,
            progressive_resume_requested=settings.progressive_resume_requested,
            progressive_chunk_seconds=settings.progressive_chunk_seconds,
            progressive_chunk_overlap_seconds=settings.progressive_chunk_overlap_seconds,
            progressive_max_workers=settings.progressive_max_workers,
            threads=settings.native_threads,
        )

    def validate_runtime(self, settings: ProviderTranscriptionSettings) -> None:
        resolve_engine_exe()
        model_path = Path(settings.model_name).expanduser()
        if not model_path.exists() or not model_path.is_file():
            raise TranscriptionError(
                "Native engine provider requires --model to be a local whisper.cpp ggml "
                f".bin file path. Got: {settings.model_name!r}"
            )
        if model_path.suffix.lower() != ".bin":
            raise TranscriptionError(
                "Native engine provider requires a whisper.cpp ggml .bin model file. "
                f"Got: {model_path}"
            )


class ParaformerProvider:
    """FunASR Paraformer provider for Chinese-first transcription."""

    _CAPABILITIES = ProviderCapabilities(
        provider_name="paraformer",
        display_name="Paraformer Chinese",
        default_model_name=PARAFORMER_MODEL_NAME,
        supported_model_names=(PARAFORMER_MODEL_NAME,),
        supports_language_hint=True,
        supports_word_timestamps=False,
        supports_initial_prompt=False,
        supports_vad_filter=True,
        supports_presets=True,
        requires_credentials=False,
        cost_tier="free-local",
        latency_tier="fast-local",
        notes=(
            "Runs locally through the optional FunASR SDK.",
            "Designed as the Chinese-first provider while keeping Whisper available.",
            "Install with: python -m pip install funasr modelscope",
        ),
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._CAPABILITIES

    def build_transcriber(self, settings: ProviderTranscriptionSettings) -> Transcriber:
        from flowscribe.providers.transcribe.stable_paraformer import StableParaformerTranscriber

        return StableParaformerTranscriber(
            model_name=settings.model_name or PARAFORMER_MODEL_NAME,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
            word_timestamps=settings.word_timestamps,
        )

    def validate_runtime(self, settings: ProviderTranscriptionSettings) -> None:
        from flowscribe.providers.transcribe.paraformer import validate_paraformer_runtime

        validate_paraformer_runtime(settings.model_name or PARAFORMER_MODEL_NAME)


def default_transcription_provider() -> TranscriptionProvider:
    """Return the current default provider for FlowScribe."""

    return LocalWhisperProvider()


def resolve_transcription_provider(provider_name: str | None = None) -> TranscriptionProvider:
    """Resolve a provider by name while keeping local whisper as the default."""

    normalized = (provider_name or "").strip().lower()
    if normalized in {"", "default", "local", "local-whisper", "faster-whisper"}:
        return default_transcription_provider()
    if normalized in {"native", "native-engine", "whisper.cpp", "whisper-cpp"}:
        return NativeEngineProvider()
    if normalized in {"paraformer", "funasr", "paraformer-zh"}:
        return ParaformerProvider()
    raise ValueError(f"Unsupported transcription provider: {provider_name}")


def is_native_engine_provider_name(provider_name: str | None) -> bool:
    """Return whether a provider name resolves to the native engine provider."""

    return (provider_name or "").strip().lower() in {
        "native",
        "native-engine",
        "whisper.cpp",
        "whisper-cpp",
    }


def supports_python_progressive_provider_name(provider_name: str | None) -> bool:
    """Return whether a provider supports the Python chunked progressive executor."""

    normalized = (provider_name or "").strip().lower()
    return normalized in {
        "",
        "default",
        "local",
        "local-whisper",
        "faster-whisper",
        "paraformer",
        "funasr",
        "paraformer-zh",
    }


def validate_transcription_provider_runtime(
    provider_name: str | None,
    settings: ProviderTranscriptionSettings,
) -> None:
    """Raise early when a provider is selected but its local runtime is not usable."""

    resolve_transcription_provider(provider_name).validate_runtime(settings)
