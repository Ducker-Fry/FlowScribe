"""Agent-friendly HTTP task storage and payload helpers."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from flowscribe.app.service import TranscriptionService
from flowscribe.cli.payloads import result_payload
from flowscribe.server.task_payloads import job_to_payload, task_job_from_payload
from flowscribe.tasks.models import ProgressEvent, TranscriptionJob

AgentTaskStatus = Literal["accepted", "running", "completed", "failed", "canceled"]
AGENT_TASK_STORE_VERSION = 1


@dataclass(frozen=True)
class AgentTaskRecord:
    task_id: str
    status: AgentTaskStatus
    created_at: str
    updated_at: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    job_payload: dict[str, Any] = field(default_factory=dict)
    task_spec: dict[str, Any] = field(default_factory=dict)
    events: tuple[dict[str, Any], ...] = ()
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentTaskStore:
    """JSON-backed task registry for agent-facing HTTP APIs."""

    def __init__(self, path: Path, *, blob_resolver=None) -> None:
        self._path = path.expanduser().resolve()
        self._lock = threading.Lock()
        self._tasks: dict[str, AgentTaskRecord] = {}
        self._blob_resolver = blob_resolver
        self._load()
        self._recover_incomplete_tasks()

    def submit(self, job: TranscriptionJob) -> dict[str, Any]:
        spec = job.to_task_specs()[0]
        task_id = spec.task_id
        record = AgentTaskRecord(
            task_id=task_id,
            status="accepted",
            created_at=_utc_now(),
            source={
                "kind": spec.source.kind,
                "value": spec.source.value,
                "locator": spec.source.resolved_locator,
            },
            job_payload=job_to_payload(job),
            task_spec={
                "task_id": spec.task_id,
                "resume_token": spec.resume_token,
                "checkpoint_id": spec.checkpoint_id,
                "cache_key": spec.cache_key,
            },
        )
        with self._lock:
            self._tasks[task_id] = record
            self._save()

        thread = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
        thread.start()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return _task_summary(record)

    def get_events(self, task_id: str) -> list[dict[str, Any]] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return list(record.events)

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.result is None:
                return None
            return record.result

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._lock:
            for record in self._tasks.values():
                if not isinstance(record.result, dict):
                    continue
                for output in record.result.get("outputs", []):
                    if not isinstance(output, dict):
                        continue
                    for artifact in output.get("artifacts", []):
                        if isinstance(artifact, dict) and artifact.get("artifact_id") == artifact_id:
                            return artifact
        return None

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks[task_id]
            job = task_job_from_payload(record.job_payload, blob_resolver=self._blob_resolver)
            self._tasks[task_id] = AgentTaskRecord(
                **{
                    **asdict(record),
                    "status": "running",
                    "updated_at": _utc_now(),
                }
            )
            self._save()

        def progress(event: ProgressEvent) -> None:
            payload = _event_dict(event)
            with self._lock:
                current = self._tasks[task_id]
                self._tasks[task_id] = AgentTaskRecord(
                    **{
                        **asdict(current),
                        "events": tuple([*current.events, payload]),
                        "updated_at": _utc_now(),
                    }
                )
                self._save()

        try:
            result = TranscriptionService().run(job, progress=progress)
            status: AgentTaskStatus = "canceled" if result.canceled else ("failed" if result.errors else "completed")
            payload = result_payload(result)
            _attach_artifact_manifests(task_id, payload)
            with self._lock:
                current = self._tasks[task_id]
                self._tasks[task_id] = AgentTaskRecord(
                    **{
                        **asdict(current),
                        "status": status,
                        "updated_at": _utc_now(),
                        "result": payload,
                    }
                )
                self._save()
        except Exception as exc:  # pragma: no cover - defensive server path
            with self._lock:
                current = self._tasks[task_id]
                self._tasks[task_id] = AgentTaskRecord(
                    **{
                        **asdict(current),
                        "status": "failed",
                        "updated_at": _utc_now(),
                        "error": str(exc),
                    }
                )
                self._save()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        items = payload.get("tasks", [])
        if not isinstance(items, list):
            return
        for item in items:
            record = _record_from_payload(item)
            if record is not None:
                self._tasks[record.task_id] = record

    def _save(self) -> None:
        payload = {
            "version": AGENT_TASK_STORE_VERSION,
            "tasks": [_record_to_payload(record) for record in self._tasks.values()],
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def _recover_incomplete_tasks(self) -> None:
        changed = False
        for task_id, record in list(self._tasks.items()):
            if record.status not in {"accepted", "running"}:
                continue
            self._tasks[task_id] = AgentTaskRecord(
                **{
                    **asdict(record),
                    "status": "failed",
                    "updated_at": _utc_now(),
                    "error": "Task interrupted by server restart before completion.",
                }
            )
            changed = True
        if changed:
            self._save()

def _task_summary(record: AgentTaskRecord) -> dict[str, Any]:
    result = record.result
    document_path = None
    if isinstance(result, dict):
        for output in result.get("outputs", []):
            if isinstance(output, dict) and output.get("json_path"):
                document_path = output["json_path"]
                break
    return {
        "task_id": record.task_id,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "resume_token": record.task_spec.get("resume_token"),
        "checkpoint_id": record.task_spec.get("checkpoint_id"),
        "cache_key": record.task_spec.get("cache_key"),
        "document_path": document_path,
        "result_available": record.result is not None,
        "error": record.error,
    }


def _record_to_payload(record: AgentTaskRecord) -> dict[str, Any]:
    return asdict(record)


def _record_from_payload(data: object) -> AgentTaskRecord | None:
    if not isinstance(data, dict):
        return None
    try:
        return AgentTaskRecord(
            task_id=str(data["task_id"]),
            status=data["status"],
            created_at=str(data["created_at"]),
            updated_at=data.get("updated_at"),
            source=data.get("source", {}),
            job_payload=data.get("job_payload", {}),
            task_spec=data.get("task_spec", {}),
            events=tuple(data.get("events", ())),
            result=data.get("result"),
            error=data.get("error"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _event_dict(event: ProgressEvent) -> dict[str, Any]:
    payload = asdict(event)
    if event.path is not None:
        payload["path"] = str(event.path)
    return payload


def sse_bytes(events: list[dict[str, Any]]) -> bytes:
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
    return "".join(lines).encode("utf-8")


def agent_task_store_path_for(queue_store_path: Path) -> Path:
    queue_store_path = queue_store_path.expanduser().resolve()
    return queue_store_path.with_name("agent-tasks.json")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _attach_artifact_manifests(task_id: str, payload: dict[str, Any]) -> None:
    outputs = payload.get("outputs", [])
    if not isinstance(outputs, list):
        return
    for output_index, output in enumerate(outputs):
        if not isinstance(output, dict):
            continue
        paths = output.get("paths", [])
        if not isinstance(paths, list):
            continue
        artifacts: list[dict[str, Any]] = []
        for path_index, raw_path in enumerate(paths):
            if not isinstance(raw_path, str):
                continue
            file_path = Path(raw_path)
            artifact_id = f"{task_id}-{output_index}-{path_index}"
            artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "filename": file_path.name,
                    "format": file_path.suffix.removeprefix(".").lower(),
                    "download_path": f"/v1/artifacts/{artifact_id}",
                    "size_bytes": file_path.stat().st_size if file_path.exists() else None,
                    "path": str(file_path),
                }
            )
        output["artifacts"] = artifacts
