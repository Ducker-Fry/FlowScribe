from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from flowscribe.tasks.models import (
    CancelRequest,
    CapabilityResult,
    ErrorEvent,
    OutputContract,
    ProgressEvent,
    RuntimePreferences,
    SourceSpec,
    TaskSpec,
    TranscriptionJob,
)


def test_protocol_models_are_frozen_and_default_to_v0() -> None:
    source = SourceSpec(kind="url", value="https://example.com/video")
    task = TaskSpec(task_id="task-1", source=source)

    assert source.protocol_version == "v0"
    assert task.protocol_version == "v0"

    with pytest.raises(FrozenInstanceError):
        source.value = "changed"


def test_transcription_job_to_task_specs_builds_cache_and_runtime_preferences(tmp_path: Path) -> None:
    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(tmp_path / "media.mp4")),),
        output_dir=tmp_path / "out",
        output_formats=("txt", "json"),
        requested_capabilities=("subtitle", "transcribe"),
        runtime_preferences=RuntimePreferences(max_cpu_threads=4, device="cpu"),
    )

    spec = job.to_task_specs()[0]

    assert spec.requested_capabilities == ("subtitle", "transcribe")
    assert spec.output_contract == OutputContract(
        formats=("txt", "json"),
        output_dir=tmp_path / "out",
        output_name_base=None,
        overwrite=False,
    )
    assert spec.runtime_preferences.max_cpu_threads == 4
    assert spec.cache_key.startswith("v0_")


def test_protocol_payloads_are_json_friendly() -> None:
    error = ErrorEvent(
        task_id="task-1",
        capability="subtitle",
        error_type="network",
        user_message="Cannot fetch subtitles.",
        internal_message="HTTP 403",
        retryable=True,
        code="forbidden",
    )
    result = CapabilityResult(
        task_id="task-1",
        capability="subtitle",
        supported=False,
        status="unsupported",
        error=error,
    )
    progress = ProgressEvent(
        stage="prepare",
        message="Checking subtitles",
        task_id="task-1",
        capability="subtitle",
        percent=0.0,
    )
    cancel = CancelRequest(task_id="task-1")

    assert result.error is error
    assert progress.capability == "subtitle"
    assert cancel.force is False
