from pathlib import Path

import pytest

from flowscribe.tasks.models import SourceSpec, TranscriptionJob
from flowscribe.app.service import _build_pipeline
from flowscribe.config.settings import AppSettings
from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber
from flowscribe.providers.transcribe.registry import (
    LocalWhisperProvider,
    NativeEngineProvider,
    ProviderTranscriptionSettings,
    default_transcription_provider,
    is_native_engine_provider_name,
    resolve_transcription_provider,
)


def test_default_provider_is_local_whisper_with_explicit_capabilities() -> None:
    provider = default_transcription_provider()

    assert isinstance(provider, LocalWhisperProvider)
    assert provider.capabilities.provider_name == "local-whisper"
    assert provider.capabilities.default_model_name == "small"
    assert provider.capabilities.supports_language_hint is True
    assert provider.capabilities.supports_word_timestamps is True
    assert provider.capabilities.supports_initial_prompt is True
    assert provider.capabilities.supports_vad_filter is True
    assert provider.capabilities.requires_credentials is False
    assert provider.capabilities.cost_tier == "free-local"
    assert provider.capabilities.latency_tier == "fast-local"
    assert "small" in provider.capabilities.supported_model_names


def test_local_whisper_provider_builds_default_transcriber() -> None:
    provider = LocalWhisperProvider()

    transcriber = provider.build_transcriber(
        ProviderTranscriptionSettings(
            model_name="tiny",
            language="en",
            task="transcribe",
            beam_size=3,
            vad_filter=True,
            initial_prompt="terms",
            preset=None,
            word_timestamps=True,
        )
    )

    assert isinstance(transcriber, LocalWhisperTranscriber)


def test_resolve_transcription_provider_supports_default_aliases() -> None:
    assert isinstance(resolve_transcription_provider(), LocalWhisperProvider)
    assert isinstance(resolve_transcription_provider("default"), LocalWhisperProvider)
    assert isinstance(resolve_transcription_provider("local"), LocalWhisperProvider)
    assert isinstance(resolve_transcription_provider("local-whisper"), LocalWhisperProvider)
    assert isinstance(resolve_transcription_provider("faster-whisper"), LocalWhisperProvider)

    with pytest.raises(ValueError, match="Unsupported transcription provider"):
        resolve_transcription_provider("remote-api")


def test_resolve_transcription_provider_supports_native_engine_aliases() -> None:
    assert isinstance(resolve_transcription_provider("native-engine"), NativeEngineProvider)
    assert isinstance(resolve_transcription_provider("native"), NativeEngineProvider)
    assert isinstance(resolve_transcription_provider("whisper.cpp"), NativeEngineProvider)
    assert is_native_engine_provider_name("native-engine") is True
    assert is_native_engine_provider_name("local-whisper") is False


def test_build_pipeline_uses_provider_factory(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeProvider:
        def build_transcriber(self, settings: ProviderTranscriptionSettings):
            captured["settings"] = settings
            return "fake-transcriber"

    monkeypatch.setattr(
        "flowscribe.app.service.resolve_transcription_provider",
        lambda provider_name=None: FakeProvider(),
    )

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(tmp_path / "sample.mp4")),),
        output_dir=tmp_path / "out",
        model_name="medium",
        language="zh",
        preset="zh",
        task="transcribe",
        beam_size=7,
        vad_filter=True,
        initial_prompt="preserve names",
        word_timestamps=True,
        output_formats=("txt", "json"),
        overwrite=True,
        provider_name="native-engine",
    )
    settings = AppSettings.from_options(
        output_dir=job.output_dir,
        work_dir=job.work_dir,
        model_name=job.model_name,
        language=job.language,
        preset=job.preset,
        task=job.task,
        beam_size=job.beam_size,
        vad_filter=job.vad_filter,
        no_vad_filter=job.no_vad_filter,
        initial_prompt=job.initial_prompt,
        word_timestamps=job.word_timestamps,
        recursive=False,
        overwrite=job.overwrite,
        keep_audio=job.keep_audio,
    )

    pipeline = _build_pipeline(job, settings)

    assert pipeline._transcriber == "fake-transcriber"
    assert captured["settings"].progressive_enabled is True
    assert captured["settings"].progressive_chunk_seconds == 30.0
    assert captured["settings"].progressive_chunk_overlap_seconds == 3.0
    assert captured["settings"].progressive_max_workers == 1
    assert captured["settings"].model_name == "medium"
    assert captured["settings"].language == "zh"
    assert captured["settings"].preset == "zh"
    assert captured["settings"].word_timestamps is True
