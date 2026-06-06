"""Stable task and protocol models used across FlowScribe layers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Literal

from flowscribe.core.models import OutputArtifacts, TranscriptSegment

SourceKind = Literal["local", "url", "capture"]
ExtendedSourceKind = Literal["local", "url", "capture", "transcript"]
UrlMediaKind = Literal["audio", "video"]
DownloadQuality = Literal["best", "high", "medium", "low"]
ProgressStage = Literal[
    "discover",
    "download",
    "prepare",
    "transcribe",
    "write",
    "complete",
    "error",
    "canceled",
    "resume",
]
CapabilityName = Literal["subtitle", "transcribe", "summarize", "translate"]
CapabilityStatus = Literal["success", "failed", "unsupported", "cancelled"]
ErrorType = Literal["media", "model", "runtime", "network", "user"]
CancelStatus = Literal["pending", "cancelled", "failed"]
RuntimeDevice = Literal["cpu", "gpu", "auto"]


@dataclass(frozen=True)
class DownloadOptions:
    """Options for remote media download."""

    quality: DownloadQuality = "best"
    prefer_format: str | None = None


@dataclass(frozen=True)
class SourceSpec:
    """One user-provided source to process."""

    kind: SourceKind
    value: str
    recursive: bool = False
    keep_media: bool = False
    url_media_kind: UrlMediaKind = "audio"
    media_output_dir: Path | None = None
    auto_bind_media: bool = False
    download_options: DownloadOptions | None = None
    protocol_version: str = "v0"
    locator: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    hints: Mapping[str, object] = field(default_factory=dict)
    security_context: Mapping[str, object] = field(default_factory=dict)
    raw_metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def extended_kind(self) -> ExtendedSourceKind:
        return self.kind

    @property
    def resolved_locator(self) -> str:
        return self.locator or self.value


@dataclass(frozen=True)
class OutputContract:
    """Stable output requirements for one task."""

    formats: tuple[str, ...] = ("txt", "md")
    output_dir: Path = Path("outputs")
    output_name_base: str | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class RuntimePreferences:
    """Task-level runtime constraints that providers translate downstream."""

    max_cpu_threads: int | None = None
    max_memory_mb: int | None = None
    device: RuntimeDevice | None = None
    priority: int = 0


@dataclass(frozen=True)
class TaskSpec:
    """v0 cross-layer task protocol."""

    task_id: str
    source: SourceSpec
    requested_capabilities: tuple[CapabilityName, ...] = ("transcribe",)
    output_contract: OutputContract = field(default_factory=OutputContract)
    runtime_preferences: RuntimePreferences = field(default_factory=RuntimePreferences)
    resume_token: str | None = None
    checkpoint_id: str | None = None
    cache_key: str = ""
    protocol_version: str = "v0"
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ErrorEvent:
    """Standardized cross-layer error payload."""

    task_id: str
    capability: str
    error_type: ErrorType
    user_message: str
    internal_message: str
    retryable: bool
    code: str | None = None


@dataclass(frozen=True)
class CapabilityResult:
    """Standardized capability outcome."""

    task_id: str
    capability: str
    supported: bool
    status: CapabilityStatus
    artifacts: tuple[OutputArtifacts, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    metrics: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error: ErrorEvent | None = None
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CancelRequest:
    """Standardized cancellation request."""

    task_id: str
    force: bool = False


@dataclass(frozen=True)
class CancelAck:
    """Standardized cancellation acknowledgement."""

    task_id: str
    status: CancelStatus
    checkpoint: str | None = None


@dataclass(frozen=True)
class TranscriptionJob:
    """Stable request object for a transcription run."""

    sources: tuple[SourceSpec, ...]
    task_id: str | None = None
    output_dir: Path = Path("outputs")
    output_name_base: str | None = None
    work_dir: Path | None = None
    provider_name: str = "local-whisper"
    model_name: str = "small"
    language: str | None = None
    preset: str | None = None
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = False
    no_vad_filter: bool = False
    initial_prompt: str | None = None
    timestamps: bool = False
    word_timestamps: bool = False
    output_formats: tuple[str, ...] = ("txt", "md")
    overwrite: bool = False
    keep_audio: bool = False
    max_download_mb: int = 2048
    max_duration_seconds: float = 4 * 60 * 60
    download_timeout_seconds: int = 30
    network_family: str = "auto"
    cookies_path: Path | None = None
    proxy: str | None = None
    progressive_enabled: bool = True
    progressive_resume: bool = True
    progressive_chunk_seconds: float = 30.0
    progressive_chunk_overlap_seconds: float = 3.0
    progressive_max_workers: int = 1
    native_threads: int | None = None
    requested_capabilities: tuple[CapabilityName, ...] = ("transcribe",)
    runtime_preferences: RuntimePreferences = field(default_factory=RuntimePreferences)
    resume_token: str | None = None
    checkpoint_id: str | None = None
    protocol_version: str = "v0"
    created_at: datetime = field(default_factory=datetime.now)

    def to_task_specs(self) -> tuple[TaskSpec, ...]:
        """Normalize one app-facing job into task-layer specs."""

        specs: list[TaskSpec] = []
        for index, source in enumerate(self.sources, start=1):
            raw_metadata = {
                "language": self.language,
                "task": self.task,
                "beam_size": self.beam_size,
                "vad_filter": self.vad_filter,
                "initial_prompt": self.initial_prompt,
                "preset": self.preset,
                "word_timestamps": self.word_timestamps,
                "provider_name": self.provider_name,
                "model_name": self.model_name,
                "timestamps": self.timestamps,
                "network_family": self.network_family,
                "cookies_path": str(self.cookies_path) if self.cookies_path is not None else None,
                "proxy": self.proxy,
                "output_name_base": self.output_name_base,
            }
            output_contract = OutputContract(
                formats=self.output_formats,
                output_dir=self.output_dir,
                output_name_base=self.output_name_base,
                overwrite=self.overwrite,
            )
            task_id = self._task_id_for_source(
                source=source,
                index=index,
                output_contract=output_contract,
                raw_metadata=raw_metadata,
            )
            resume_token = self._resume_token_for_task(task_id)
            checkpoint_id = self._checkpoint_id_for_task(task_id)
            specs.append(
                TaskSpec(
                    task_id=task_id,
                    source=source,
                    requested_capabilities=self.requested_capabilities,
                    output_contract=output_contract,
                    runtime_preferences=self.runtime_preferences,
                    resume_token=resume_token,
                    checkpoint_id=checkpoint_id,
                    cache_key=generate_cache_key(
                        source=source,
                        requested_capabilities=self.requested_capabilities,
                        output_contract=output_contract,
                        runtime_preferences=self.runtime_preferences,
                    ),
                    raw_metadata=raw_metadata,
                )
            )
        return tuple(specs)

    def _task_id_for_source(
        self,
        *,
        source: SourceSpec,
        index: int,
        output_contract: OutputContract,
        raw_metadata: Mapping[str, object],
    ) -> str:
        if self.task_id is not None:
            if len(self.sources) == 1:
                return self.task_id
            return f"{self.task_id}-{index}"
        return _stable_task_id_for_source(
            source=source,
            index=index,
            requested_capabilities=self.requested_capabilities,
            output_contract=output_contract,
            runtime_preferences=self.runtime_preferences,
            raw_metadata=raw_metadata,
            protocol_version=self.protocol_version,
        )

    def _resume_token_for_task(self, task_id: str) -> str | None:
        if self.resume_token is not None:
            if len(self.sources) == 1:
                return self.resume_token
            return f"{self.resume_token}-{task_id}"
        return task_id if self.progressive_resume else None

    def _checkpoint_id_for_task(self, task_id: str) -> str | None:
        if self.checkpoint_id is not None:
            if len(self.sources) == 1:
                return self.checkpoint_id
            return f"{self.checkpoint_id}-{task_id}"
        return task_id if self.progressive_resume else None


@dataclass(frozen=True)
class ProgressEvent:
    """Structured progress event for UI and automation."""

    stage: ProgressStage
    message: str
    event_type: str | None = None
    timestamp: str | None = None
    sequence: int | None = None
    source: str | None = None
    current: int | None = None
    total: int | None = None
    path: Path | None = None
    processed_duration_seconds: float | None = None
    total_duration_seconds: float | None = None
    eta_seconds: float | None = None
    realtime_factor: float | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    completed_chunks: int | None = None
    failed_chunks: int | None = None
    segments: tuple[TranscriptSegment, ...] = ()
    resumed: bool = False
    task_id: str | None = None
    capability: str | None = None
    percent: float | None = None
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ErrorInfo:
    """Structured error information that can be displayed in a GUI."""

    code: str
    message: str
    source: str | None = None
    recoverable: bool = True


@dataclass(frozen=True)
class TranscriptionResult:
    """Stable response object returned by application services."""

    job: TranscriptionJob
    task_specs: tuple[TaskSpec, ...] = ()
    outputs: tuple[OutputArtifacts, ...] = ()
    errors: tuple[ErrorInfo, ...] = ()
    canceled: bool = False
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    @property
    def succeeded(self) -> int:
        return len(self.outputs)

    @property
    def failed(self) -> int:
        return len(self.errors)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.canceled

    @property
    def elapsed_seconds(self) -> float | None:
        """Total elapsed time in seconds, or None if not finished."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


ProgressCallback = Callable[[ProgressEvent], None]


def generate_cache_key(
    *,
    source: SourceSpec,
    requested_capabilities: tuple[CapabilityName, ...],
    output_contract: OutputContract,
    runtime_preferences: RuntimePreferences,
    protocol_version: str = "v0",
) -> str:
    """Create a stable task-layer cache key from immutable task inputs."""

    source_hash = hashlib.md5(source.resolved_locator.encode("utf-8")).hexdigest()[:16]
    cap_str = "_".join(sorted(requested_capabilities))
    param_hash = hashlib.md5(
        json.dumps(
            {
                "device": runtime_preferences.device,
                "max_cpu_threads": runtime_preferences.max_cpu_threads,
                "formats": output_contract.formats,
                "overwrite": output_contract.overwrite,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:8]
    return f"{protocol_version}_{source_hash}_{cap_str}_{param_hash}"


def _stable_task_id_for_source(
    *,
    source: SourceSpec,
    index: int,
    requested_capabilities: tuple[CapabilityName, ...],
    output_contract: OutputContract,
    runtime_preferences: RuntimePreferences,
    raw_metadata: Mapping[str, object],
    protocol_version: str = "v0",
) -> str:
    seed = {
        "index": index,
        "kind": source.kind,
        "locator": source.resolved_locator,
        "requested_capabilities": requested_capabilities,
        "output_formats": output_contract.formats,
        "provider_name": raw_metadata.get("provider_name"),
        "model_name": raw_metadata.get("model_name"),
        "language": raw_metadata.get("language"),
        "task": raw_metadata.get("task"),
        "device": runtime_preferences.device,
        "protocol_version": protocol_version,
    }
    digest = hashlib.md5(
        json.dumps(seed, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest
