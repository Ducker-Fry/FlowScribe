from __future__ import annotations

from flowscribe.app.progressive_policy import (
    resolve_cli_progressive_policy,
    resolve_runtime_progressive_policy,
)
from flowscribe.tasks.models import SourceSpec, TranscriptionJob


def test_cli_policy_auto_enables_long_single_local_run() -> None:
    policy = resolve_cli_progressive_policy(
        provider_name="local-whisper",
        progressive_mode="auto",
        progressive_resume=False,
        chunk_seconds=30.0,
        overlap_seconds=3.0,
        max_workers=1,
        language=None,
        preset=None,
        source_kind="local",
        source_count=1,
        recursive=False,
        duration_seconds=20 * 60,
        auto_threshold_seconds=20 * 60,
    )

    assert policy.mode == "python-progressive"
    assert policy.progressive_enabled is True
    assert policy.auto_enabled is True
    assert policy.notes == (
        "Auto-enabled progressive transcription for long local media (20:00 >= 20:00).",
    )


def test_cli_policy_keeps_recursive_batch_runs_classic_by_default() -> None:
    policy = resolve_cli_progressive_policy(
        provider_name="local-whisper",
        progressive_mode="auto",
        progressive_resume=True,
        chunk_seconds=30.0,
        overlap_seconds=3.0,
        max_workers=1,
        language=None,
        preset=None,
        source_kind="local",
        source_count=2,
        recursive=True,
        duration_seconds=60 * 60,
        auto_threshold_seconds=20 * 60,
    )

    assert policy.mode == "classic"
    assert policy.progressive_enabled is False
    assert policy.auto_enabled is False


def test_cli_policy_explicit_progressive_overrides_classic_default() -> None:
    policy = resolve_cli_progressive_policy(
        provider_name="native-engine",
        progressive_mode="enabled",
        progressive_resume=True,
        chunk_seconds=90.0,
        overlap_seconds=5.0,
        max_workers=2,
        language="en",
        preset=None,
        source_kind="local",
        source_count=3,
        recursive=True,
        duration_seconds=None,
        auto_threshold_seconds=20 * 60,
    )

    assert policy.mode == "native-engine-progressive"
    assert policy.progressive_enabled is True
    assert policy.resume_supported is False
    assert policy.resume_effective is False
    assert "Resume unsupported on native-engine; continuing without resume." in policy.notes


def test_runtime_policy_resolves_classic_python_and_native_modes() -> None:
    classic_job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value="a.mp4"),),
        progressive_enabled=False,
    )
    python_job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value="a.mp4"),),
        provider_name="paraformer",
        progressive_enabled=True,
        progressive_resume=True,
    )
    native_job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value="a.mp4"),),
        provider_name="native-engine",
        model_name="model.bin",
        progressive_enabled=True,
        progressive_resume=True,
    )

    assert resolve_runtime_progressive_policy(classic_job).mode == "classic"
    assert resolve_runtime_progressive_policy(python_job).mode == "python-progressive"
    native_policy = resolve_runtime_progressive_policy(native_job)
    assert native_policy.mode == "native-engine-progressive"
    assert native_policy.resume_requested is True
    assert native_policy.resume_supported is False
    assert native_policy.resume_effective is False
