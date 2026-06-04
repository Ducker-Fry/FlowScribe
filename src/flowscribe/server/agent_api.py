"""Minimal agent-friendly HTTP task API."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flowscribe.app.service import TranscriptionService
from flowscribe.cli.main import _result_payload
from flowscribe.tasks.models import ProgressEvent, SourceSpec, TranscriptionJob


class AgentTaskStore:
    """In-memory task registry for agent-facing HTTP APIs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}

    def submit(self, job: TranscriptionJob) -> dict[str, Any]:
        spec = job.to_task_specs()[0]
        task_id = spec.task_id
        record = {
            "task_id": task_id,
            "status": "accepted",
            "created_at": _utc_now(),
            "updated_at": None,
            "job": job,
            "task_spec": spec,
            "events": [],
            "result": None,
            "error": None,
        }
        with self._lock:
            self._tasks[task_id] = record

        thread = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
        thread.start()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return {
                "task_id": record["task_id"],
                "status": record["status"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "resume_token": record["task_spec"].resume_token,
                "checkpoint_id": record["task_spec"].checkpoint_id,
                "cache_key": record["task_spec"].cache_key,
                "document_path": self._document_path(record["result"]),
                "result_available": record["result"] is not None,
            }

    def get_events(self, task_id: str) -> list[dict[str, Any]] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return list(record["events"])

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record["result"] is None:
                return None
            return _result_payload(record["result"])

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks[task_id]
            job = record["job"]
            record["status"] = "running"
            record["updated_at"] = _utc_now()

        def progress(event: ProgressEvent) -> None:
            payload = _event_dict(event)
            with self._lock:
                current = self._tasks[task_id]
                current["events"].append(payload)
                current["updated_at"] = _utc_now()

        try:
            result = TranscriptionService().run(job, progress=progress)
            with self._lock:
                current = self._tasks[task_id]
                current["result"] = result
                current["status"] = "canceled" if result.canceled else ("failed" if result.errors else "completed")
                current["updated_at"] = _utc_now()
        except Exception as exc:  # pragma: no cover - defensive server path
            with self._lock:
                current = self._tasks[task_id]
                current["status"] = "failed"
                current["error"] = str(exc)
                current["updated_at"] = _utc_now()

    @staticmethod
    def _document_path(result) -> str | None:
        if result is None:
            return None
        for output in result.outputs:
            if output.json_path is not None:
                return str(output.json_path)
        return None


def task_job_from_payload(payload: dict[str, Any]) -> TranscriptionJob:
    source_payload = payload.get("source")
    if not isinstance(source_payload, dict):
        raise ValueError("source must be an object")
    source_kind = str(source_payload.get("kind") or "").strip()
    source_value = str(source_payload.get("value") or "").strip()
    if source_kind not in {"local", "url"}:
        raise ValueError("source.kind must be local or url")
    if not source_value:
        raise ValueError("source.value is required")
    output_payload = payload.get("output", {})
    if not isinstance(output_payload, dict):
        raise ValueError("output must be an object")
    output_dir = Path(output_payload.get("output_dir") or "outputs")
    output_formats = tuple(output_payload.get("formats") or ("json",))
    if not output_formats:
        output_formats = ("json",)
    source = SourceSpec(kind=source_kind, value=source_value)
    return TranscriptionJob(
        sources=(source,),
        task_id=payload.get("task_id"),
        output_dir=output_dir,
        output_formats=output_formats,
        provider_name=payload.get("provider_name") or "local-whisper",
        model_name=payload.get("model_name") or "small",
        language=payload.get("language"),
        preset=payload.get("preset"),
        timestamps=bool(payload.get("timestamps", True)),
        word_timestamps=bool(payload.get("word_timestamps", False)),
        overwrite=bool(output_payload.get("overwrite", False)),
        progressive_enabled=bool(payload.get("progressive", False)),
        progressive_resume=bool(payload.get("progressive_resume", False)),
        resume_token=payload.get("resume_token"),
        checkpoint_id=payload.get("checkpoint_id"),
        requested_capabilities=("subtitle", "transcribe") if source_kind == "url" else ("transcribe",),
    )


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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
