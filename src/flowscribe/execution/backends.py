"""Execution backend abstractions for CLI, GUI, and queue entry points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
import inspect
from pathlib import Path

from flowscribe.core.errors import DownloadError, FlowScribeError, TranscriptionError
from flowscribe.core.models import OutputArtifacts
from flowscribe.execution.remote_client import RemoteServerClient
from flowscribe.server.task_payloads import job_to_payload
from flowscribe.tasks.models import ErrorInfo, ProgressCallback, ProgressEvent, SourceSpec, TranscriptionJob, TranscriptionResult

ServiceFactory = Callable[[], object]


class ExecutionBackend:
    """Common interface for local and remote execution backends."""

    def run(
        self,
        job: TranscriptionJob,
        *,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError


class LocalExecutionBackend(ExecutionBackend):
    """Execute jobs locally through the stable app service."""

    def __init__(self, service_factory: ServiceFactory) -> None:
        self._service_factory = service_factory

    def run(
        self,
        job: TranscriptionJob,
        *,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        service = self._service_factory()
        kwargs = {"progress": progress}
        if should_cancel is not None and _callable_accepts_keyword(service.run, "should_cancel"):
            kwargs["should_cancel"] = should_cancel
        return service.run(job, **kwargs)


class RemoteExecutionBackend(ExecutionBackend):
    """Execute jobs through a remote FlowScribe server."""

    def __init__(
        self,
        client: RemoteServerClient,
        *,
        poll_seconds: float,
        download_artifacts: bool,
    ) -> None:
        self._client = client
        self._poll_seconds = max(0.1, poll_seconds)
        self._download_artifacts = download_artifacts

    def run(
        self,
        job: TranscriptionJob,
        *,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        progress = progress or (lambda event: None)
        should_cancel = should_cancel or (lambda: False)
        task_specs = job.to_task_specs()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []
        started_at = datetime.now()

        progress(
            ProgressEvent(
                stage="discover",
                message=f"Received {len(job.sources)} source(s).",
                total=len(job.sources),
                task_id=task_specs[0].task_id if task_specs else None,
            )
        )

        for index, (source, task_spec) in enumerate(zip(job.sources, task_specs, strict=False), start=1):
            sub_job = replace(
                job,
                sources=(source,),
                task_id=task_spec.task_id,
                resume_token=task_spec.resume_token,
                checkpoint_id=task_spec.checkpoint_id,
            )
            try:
                if should_cancel():
                    break
                output_artifacts = self._run_one_source(
                    sub_job=sub_job,
                    source=source,
                    task_spec=task_spec,
                    current=index,
                    total=len(job.sources),
                    progress=progress,
                    should_cancel=should_cancel,
                )
                if output_artifacts is not None:
                    outputs.append(output_artifacts)
            except FlowScribeError as exc:
                errors.append(
                    ErrorInfo(
                        code=type(exc).__name__,
                        message=str(exc),
                        source=source.value,
                        recoverable=True,
                    )
                )
            except OSError as exc:
                errors.append(
                    ErrorInfo(
                        code=DownloadError.__name__,
                        message=str(exc),
                        source=source.value,
                        recoverable=True,
                    )
                )

        finished_at = datetime.now()
        if not errors:
            progress(
                ProgressEvent(
                    stage="complete",
                    message=f"Done. Succeeded: {len(outputs)}. Failed: 0.",
                    total=len(job.sources),
                    task_id=task_specs[0].task_id if task_specs else None,
                )
            )
        return TranscriptionResult(
            job=job,
            task_specs=task_specs,
            outputs=tuple(outputs),
            errors=tuple(errors),
            canceled=should_cancel() and not outputs and not errors,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _run_one_source(
        self,
        *,
        sub_job: TranscriptionJob,
        source: SourceSpec,
        task_spec,
        current: int,
        total: int,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
    ) -> OutputArtifacts | None:
        source_payload = None
        cookies_payload = None
        if source.kind == "local":
            file_path = Path(source.value)
            progress(
                ProgressEvent(
                    stage="prepare",
                    message=f"Uploading local media: {file_path.name}",
                    source=str(file_path),
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                )
            )
            upload = self._client.upload_file(file_path)
            source_payload = {
                "kind": "remote_blob",
                "value": upload["blob_id"],
                "locator": str(file_path),
                "metadata": {
                    "filename": upload["filename"],
                    "size_bytes": upload["size_bytes"],
                },
            }
            progress(
                ProgressEvent(
                    stage="prepare",
                    message=f"Upload complete: {upload['filename']}",
                    source=str(file_path),
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                )
            )

        if sub_job.cookies_path is not None:
            cookies_path = Path(sub_job.cookies_path)
            progress(
                ProgressEvent(
                    stage="prepare",
                    message=f"Uploading cookies file: {cookies_path.name}",
                    source=str(cookies_path),
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                )
            )
            upload = self._client.upload_file(cookies_path)
            cookies_payload = {
                "kind": "remote_blob",
                "value": upload["blob_id"],
                "locator": str(cookies_path),
                "metadata": {
                    "filename": upload["filename"],
                    "size_bytes": upload["size_bytes"],
                },
            }
            progress(
                ProgressEvent(
                    stage="prepare",
                    message=f"Cookies upload complete: {upload['filename']}",
                    source=str(cookies_path),
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                )
            )

        payload = job_to_payload(
            sub_job,
            source_payload=source_payload,
            cookies_payload=cookies_payload,
        )
        progress(
            ProgressEvent(
                stage="discover",
                message="Submitting remote task.",
                source=source.value,
                current=current,
                total=total,
                task_id=task_spec.task_id,
            )
        )
        task_summary = self._client.submit_task(payload)
        remote_task_id = str(task_summary["task_id"])
        seen_events: set[tuple[object, ...]] = set()

        while True:
            if should_cancel():
                raise TranscriptionError("Remote task polling canceled before completion.")
            for event in self._client.get_task_events(remote_task_id):
                key = (
                    event.get("sequence"),
                    event.get("timestamp"),
                    event.get("event_type"),
                    event.get("stage"),
                    event.get("message"),
                )
                if key in seen_events:
                    continue
                seen_events.add(key)
                progress(_progress_event_from_payload(event))

            status = self._client.get_task_status(remote_task_id)
            if status["status"] in {"completed", "failed", "canceled"}:
                break
            self._client.sleep(self._poll_seconds)

        result_payload = None
        try:
            result_payload = self._client.get_task_result(remote_task_id)
        except FlowScribeError:
            result_payload = None

        if status["status"] == "canceled":
            raise TranscriptionError("Remote task was canceled.")
        if result_payload is None:
            if status["status"] == "failed" and status.get("error"):
                raise TranscriptionError(str(status["error"]))
            raise TranscriptionError("Remote task completed without a result payload.")

        parsed = _transcription_result_from_payload(result_payload, fallback_job=sub_job)
        if parsed.errors:
            raise TranscriptionError(parsed.errors[0].message)
        if not parsed.outputs:
            return None

        if not self._download_artifacts:
            return parsed.outputs[0]

        downloaded_paths = tuple(
            self._download_artifact(
                artifact,
                sub_job.output_dir,
                overwrite=sub_job.overwrite,
                progress=progress,
                task_id=task_spec.task_id,
                source=source.value,
                current=current,
                total=total,
            )
            for artifact in _artifacts_from_output_payload(result_payload["outputs"][0])
        )
        first_output = parsed.outputs[0]
        if source.kind == "local":
            source_kind = "local"
            source_value = source.value
            source_locator = source.resolved_locator
            original_filename = first_output.original_filename or Path(source.resolved_locator).name
        else:
            source_kind = first_output.source_kind or source.kind
            source_value = first_output.source_value or source.value
            source_locator = first_output.source_locator or source.resolved_locator
            original_filename = first_output.original_filename or _original_filename_from_source(
                source_kind,
                source_locator or source_value,
            )
        return OutputArtifacts(
            paths=downloaded_paths or first_output.paths,
            media_path=first_output.media_path,
            media_kind=first_output.media_kind,
            requested_media_kind=first_output.requested_media_kind,
            media_fallback=first_output.media_fallback,
            source_kind=source_kind,
            source_value=source_value,
            auto_bind_media=first_output.auto_bind_media,
            transcription_strategy=first_output.transcription_strategy,
            subtitle_source_kind=first_output.subtitle_source_kind,
            subtitle_language=first_output.subtitle_language,
            source_locator=source_locator,
            original_filename=original_filename,
        )

    def _download_artifact(
        self,
        artifact: dict,
        output_dir: Path,
        *,
        overwrite: bool,
        progress: ProgressCallback,
        task_id: str | None,
        source: str,
        current: int,
        total: int,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = _allocate_output_path(
            output_dir / str(artifact["filename"]),
            overwrite=overwrite,
        )
        progress(
            ProgressEvent(
                stage="write",
                message=f"Downloading artifact: {destination.name}",
                source=source,
                current=current,
                total=total,
                task_id=task_id,
            )
        )
        self._client.download_artifact(str(artifact["artifact_id"]), destination)
        return destination


def _allocate_output_path(path: Path, *, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _progress_event_from_payload(payload: dict) -> ProgressEvent:
    raw_metadata = payload.get("raw_metadata")
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}
    path_value = payload.get("path")
    return ProgressEvent(
        stage=str(payload.get("stage") or "transcribe"),
        message=str(payload.get("message") or ""),
        event_type=payload.get("event_type"),
        timestamp=payload.get("timestamp"),
        sequence=payload.get("sequence"),
        source=payload.get("source"),
        current=payload.get("current"),
        total=payload.get("total"),
        path=Path(path_value) if isinstance(path_value, str) and path_value else None,
        processed_duration_seconds=payload.get("processed_duration_seconds"),
        total_duration_seconds=payload.get("total_duration_seconds"),
        eta_seconds=payload.get("eta_seconds"),
        realtime_factor=payload.get("realtime_factor"),
        chunk_index=payload.get("chunk_index"),
        chunk_count=payload.get("chunk_count"),
        completed_chunks=payload.get("completed_chunks"),
        failed_chunks=payload.get("failed_chunks"),
        resumed=bool(payload.get("resumed", False)),
        task_id=payload.get("task_id"),
        capability=payload.get("capability"),
        percent=payload.get("percent"),
        raw_metadata=raw_metadata,
    )


def _transcription_result_from_payload(
    payload: dict,
    *,
    fallback_job: TranscriptionJob,
) -> TranscriptionResult:
    outputs: list[OutputArtifacts] = []
    for output in payload.get("outputs", []):
        paths = tuple(Path(value) for value in output.get("paths", []))
        media_path = output.get("media_path")
        outputs.append(
            OutputArtifacts(
                paths=paths,
                media_path=Path(media_path) if isinstance(media_path, str) and media_path else None,
                media_kind=output.get("media_kind"),
                requested_media_kind=output.get("requested_media_kind"),
                source_kind=output.get("source_kind"),
                source_value=output.get("source_value"),
                transcription_strategy=output.get("transcription_strategy"),
                subtitle_language=output.get("subtitle_language"),
                source_locator=output.get("source_locator"),
                original_filename=output.get("original_filename"),
            )
        )
    errors = tuple(
        ErrorInfo(
            code=str(error.get("code") or TranscriptionError.__name__),
            message=str(error.get("message") or "Unknown remote error."),
            source=error.get("source"),
            recoverable=bool(error.get("recoverable", True)),
        )
        for error in payload.get("errors", [])
        if isinstance(error, dict)
    )
    return TranscriptionResult(
        job=fallback_job,
        outputs=tuple(outputs),
        errors=errors,
        canceled=bool(payload.get("canceled", False)),
    )


def _artifacts_from_output_payload(output_payload: dict) -> tuple[dict, ...]:
    artifacts = output_payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        return ()
    return tuple(item for item in artifacts if isinstance(item, dict))


def _original_filename_from_source(source_kind: str | None, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if path.name:
        return path.name
    return value if source_kind == "url" else None


def _callable_accepts_keyword(func, name: str) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return name in signature.parameters
