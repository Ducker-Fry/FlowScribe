"""Shared progressive execution policy for long-audio routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal

from flowscribe.pipeline.progressive import tuned_chunk_overlap_seconds

if TYPE_CHECKING:
    from flowscribe.tasks.models import TranscriptionJob

ProgressiveMode = Literal["classic", "python-progressive", "native-engine-progressive"]
ProgressiveBackend = Literal["classic", "python", "native-engine"]


@dataclass(frozen=True)
class ProgressiveExecutionPolicy:
    mode: ProgressiveMode
    progressive_requested: bool
    progressive_enabled: bool
    auto_enabled: bool
    backend: ProgressiveBackend
    resume_requested: bool
    resume_supported: bool
    resume_effective: bool
    cache_supported: bool
    chunk_seconds: float
    overlap_seconds: float
    max_workers: int
    notes: tuple[str, ...]


def resolve_cli_progressive_policy(
    *,
    provider_name: str | None,
    progressive_mode: str,
    progressive_resume: bool,
    chunk_seconds: float,
    overlap_seconds: float,
    max_workers: int,
    language: str | None,
    preset: str | None,
    source_kind: Literal["local", "url"],
    source_count: int = 1,
    recursive: bool = False,
    duration_seconds: float | None = None,
    auto_threshold_seconds: float,
) -> ProgressiveExecutionPolicy:
    explicit_enabled = progressive_mode == "enabled"
    explicit_disabled = progressive_mode == "disabled"
    auto_enabled = False
    progressive_enabled = False
    notes: list[str] = []

    if explicit_enabled:
        progressive_enabled = True
    elif explicit_disabled:
        progressive_enabled = False
    elif source_kind == "local" and (recursive or source_count != 1):
        progressive_enabled = False
    elif duration_seconds is not None and duration_seconds >= auto_threshold_seconds:
        progressive_enabled = True
        auto_enabled = True
        label = "local media" if source_kind == "local" else "URL media"
        notes.append(
            "Auto-enabled progressive transcription for long "
            f"{label} ({_format_duration(duration_seconds)} >= "
            f"{_format_duration(auto_threshold_seconds)})."
        )

    return _build_policy(
        provider_name=provider_name,
        progressive_requested=explicit_enabled,
        progressive_enabled=progressive_enabled,
        auto_enabled=auto_enabled,
        progressive_resume=progressive_resume,
        chunk_seconds=chunk_seconds,
        overlap_seconds=overlap_seconds,
        max_workers=max_workers,
        language=language,
        preset=preset,
        notes=tuple(notes),
    )


def resolve_runtime_progressive_policy(
    job: TranscriptionJob,
    *,
    notes: tuple[str, ...] = (),
) -> ProgressiveExecutionPolicy:
    return _build_policy(
        provider_name=job.provider_name,
        progressive_requested=bool(job.progressive_enabled and not job.progressive_auto_enabled),
        progressive_enabled=job.progressive_enabled,
        auto_enabled=job.progressive_auto_enabled,
        progressive_resume=job.progressive_resume,
        chunk_seconds=job.progressive_chunk_seconds,
        overlap_seconds=job.progressive_chunk_overlap_seconds,
        max_workers=job.progressive_max_workers,
        language=job.language,
        preset=job.preset,
        notes=notes,
    )


def job_with_progressive_policy(
    job: TranscriptionJob,
    policy: ProgressiveExecutionPolicy,
) -> TranscriptionJob:
    from flowscribe.tasks.models import TranscriptionJob

    return TranscriptionJob(
        sources=job.sources,
        task_id=job.task_id,
        output_dir=job.output_dir,
        output_name_base=job.output_name_base,
        work_dir=job.work_dir,
        provider_name=job.provider_name,
        model_name=job.model_name,
        language=job.language,
        preset=job.preset,
        task=job.task,
        beam_size=job.beam_size,
        vad_filter=job.vad_filter,
        no_vad_filter=job.no_vad_filter,
        initial_prompt=job.initial_prompt,
        timestamps=job.timestamps,
        word_timestamps=job.word_timestamps,
        output_formats=job.output_formats,
        overwrite=job.overwrite,
        keep_audio=job.keep_audio,
        max_download_mb=job.max_download_mb,
        max_duration_seconds=job.max_duration_seconds,
        download_timeout_seconds=job.download_timeout_seconds,
        network_family=job.network_family,
        cookies_path=job.cookies_path,
        proxy=job.proxy,
        progressive_enabled=policy.progressive_enabled,
        progressive_auto_enabled=policy.auto_enabled,
        progressive_resume=policy.resume_effective,
        progressive_chunk_seconds=policy.chunk_seconds,
        progressive_chunk_overlap_seconds=policy.overlap_seconds,
        progressive_max_workers=policy.max_workers,
        native_threads=job.native_threads,
        requested_capabilities=job.requested_capabilities,
        runtime_preferences=job.runtime_preferences,
        resume_token=job.resume_token,
        checkpoint_id=job.checkpoint_id,
        protocol_version=job.protocol_version,
        created_at=job.created_at,
    )


def build_progressive_metadata(
    policy: ProgressiveExecutionPolicy,
    *,
    cache_dir_present: bool,
    chunk_count: int | None,
    completed_chunks: int | None,
    failed_chunks: int | None,
    effective_parallel_chunks: int | None,
    resume_used: bool,
) -> dict[str, object]:
    if policy.backend == "classic":
        raise ValueError("Classic mode does not expose progressive metadata.")
    return {
        "backend": policy.backend,
        "mode": policy.mode,
        "resume_requested": policy.resume_requested,
        "resume_supported": policy.resume_supported,
        "resume_used": resume_used,
        "cache_supported": policy.cache_supported,
        "cache_dir_present": cache_dir_present,
        "chunk_count": chunk_count,
        "completed_chunks": completed_chunks,
        "failed_chunks": failed_chunks,
        "effective_parallel_chunks": effective_parallel_chunks,
        "chunk_seconds": policy.chunk_seconds,
        "overlap_seconds": policy.overlap_seconds,
    }


def progressive_failure_note(policy: ProgressiveExecutionPolicy) -> str:
    if policy.mode == "python-progressive":
        return "Progressive run failed; resume remains available on the python backend."
    if policy.mode == "native-engine-progressive":
        return "Progressive run failed; resume is unavailable on native-engine in this phase."
    return "Classic mode does not support progressive resume."


def progressive_completion_note(
    policy: ProgressiveExecutionPolicy,
    *,
    source_name: str,
    completed_chunks: int | None,
    chunk_count: int | None,
    resume_used: bool,
) -> str:
    backend = "python" if policy.backend == "python" else "native-engine"
    if completed_chunks is not None and chunk_count is not None:
        return (
            f"Progressive transcription complete for {source_name} via {backend}: "
            f"{completed_chunks}/{chunk_count} chunk(s), "
            f"{'resume used' if resume_used else 'resume not used'}."
        )
    return (
        f"Progressive transcription complete for {source_name} via {backend}: "
        f"{'resume used' if resume_used else 'resume not used'}."
    )


def _build_policy(
    *,
    provider_name: str | None,
    progressive_requested: bool,
    progressive_enabled: bool,
    auto_enabled: bool,
    progressive_resume: bool,
    chunk_seconds: float,
    overlap_seconds: float,
    max_workers: int,
    language: str | None,
    preset: str | None,
    notes: tuple[str, ...],
) -> ProgressiveExecutionPolicy:
    effective_notes = list(notes)
    if not progressive_enabled:
        return ProgressiveExecutionPolicy(
            mode="classic",
            progressive_requested=progressive_requested,
            progressive_enabled=False,
            auto_enabled=auto_enabled,
            backend="classic",
            resume_requested=progressive_resume,
            resume_supported=False,
            resume_effective=False,
            cache_supported=False,
            chunk_seconds=chunk_seconds,
            overlap_seconds=overlap_seconds,
            max_workers=max_workers,
            notes=tuple(effective_notes),
        )

    if _is_native_engine_provider_name(provider_name):
        if progressive_resume:
            effective_notes.append("Resume unsupported on native-engine; continuing without resume.")
        return ProgressiveExecutionPolicy(
            mode="native-engine-progressive",
            progressive_requested=progressive_requested,
            progressive_enabled=True,
            auto_enabled=auto_enabled,
            backend="native-engine",
            resume_requested=progressive_resume,
            resume_supported=False,
            resume_effective=False,
            cache_supported=False,
            chunk_seconds=chunk_seconds,
            overlap_seconds=overlap_seconds,
            max_workers=max_workers,
            notes=tuple(effective_notes),
        )

    if _supports_python_progressive_provider_name(provider_name):
        return ProgressiveExecutionPolicy(
            mode="python-progressive",
            progressive_requested=progressive_requested,
            progressive_enabled=True,
            auto_enabled=auto_enabled,
            backend="python",
            resume_requested=progressive_resume,
            resume_supported=True,
            resume_effective=progressive_resume,
            cache_supported=True,
            chunk_seconds=chunk_seconds,
            overlap_seconds=tuned_chunk_overlap_seconds(
                requested_overlap_seconds=overlap_seconds,
                language=language,
                preset=preset,
            ),
            max_workers=max_workers,
            notes=tuple(effective_notes),
        )

    return ProgressiveExecutionPolicy(
        mode="classic",
        progressive_requested=progressive_requested,
        progressive_enabled=False,
        auto_enabled=auto_enabled,
        backend="classic",
        resume_requested=progressive_resume,
        resume_supported=False,
        resume_effective=False,
        cache_supported=False,
        chunk_seconds=chunk_seconds,
        overlap_seconds=overlap_seconds,
        max_workers=max_workers,
        notes=tuple(effective_notes),
    )


def _format_duration(value: float) -> str:
    total_seconds = max(0, int(round(value)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _is_native_engine_provider_name(provider_name: str | None) -> bool:
    return (provider_name or "").strip().lower() in {
        "native",
        "native-engine",
        "whisper.cpp",
        "whisper-cpp",
    }


def _supports_python_progressive_provider_name(provider_name: str | None) -> bool:
    return (provider_name or "").strip().lower() in {
        "",
        "default",
        "local",
        "local-whisper",
        "faster-whisper",
        "paraformer",
        "funasr",
        "paraformer-zh",
    }
