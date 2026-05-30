from __future__ import annotations

import argparse
import logging
import tempfile
import time
from typing import Any

from flowscribe.engine.pipe_client import FlowScribeEngineClient


def _print_result(label: str, payload: dict[str, Any] | None) -> bool:
    if payload is None:
        print(f"{label}: failed")
        return False

    print(f"{label}: {payload}")
    return True


def _print_transcript(payload: dict[str, Any]) -> None:
    segments = payload.get("segments", [])
    transcript = " ".join(
        str(segment.get("text", "")).strip()
        for segment in segments
        if str(segment.get("text", "")).strip()
    )
    if transcript:
        print(f"Transcript: {transcript}")


def _require_result(label: str, payload: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    ok = _print_result(label, payload)
    return ok, payload or {}


def _submit_job(client: FlowScribeEngineClient, job_id: str, audio_path: str) -> tuple[bool, dict[str, Any]]:
    return _require_result(
        "SubmitJobResult",
        client.submit_job(
            job_id=job_id,
            audio_path=audio_path,
            language="zh",
        ),
    )


def _recv_until_terminal(
    client: FlowScribeEngineClient,
    job_id: str,
    timeout: float,
) -> tuple[bool, list[tuple[int, dict[str, Any]]]]:
    messages = client.recv_job_messages(job_id, timeout=timeout)
    for kind, payload in messages:
        print(f"AsyncMessage kind={kind}: {payload}")
        if kind == 0x0031:
            _print_transcript(payload)

    terminal = any(kind in (0x0031, 0x0032) for kind, _payload in messages)
    return terminal, messages


def _run_basic_submit(
    client: FlowScribeEngineClient,
    audio_path: str,
    *,
    query_after_result: bool,
    job_timeout: float,
) -> bool:
    ok, submit = _submit_job(client, "job-123", audio_path)
    if not ok or not submit.get("ok"):
        return False

    terminal, _messages = _recv_until_terminal(client, "job-123", timeout=job_timeout)
    ok = terminal and ok
    if query_after_result:
        query_ok, query = _require_result("QueryJobResult", client.query_job("job-123"))
        ok = query_ok and query.get("job", {}).get("status") == "completed" and ok
    return ok


def _run_query_during_run(
    client: FlowScribeEngineClient,
    audio_path: str,
    job_timeout: float,
) -> bool:
    ok, submit = _submit_job(client, "job-query", audio_path)
    if not ok or not submit.get("ok"):
        return False

    deadline = time.monotonic() + 2.0
    query: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        query = client.query_job("job-query")
        status = (query or {}).get("job", {}).get("status")
        if status in {"queued", "running", "completed"}:
            break
        time.sleep(0.02)

    query_ok = _print_result("QueryJobResult", query)
    terminal, _messages = _recv_until_terminal(client, "job-query", timeout=job_timeout)
    status = (query or {}).get("job", {}).get("status")
    return query_ok and status in {"queued", "running", "completed"} and terminal


def _run_queued_cancel(
    client: FlowScribeEngineClient,
    audio_path: str,
    job_timeout: float,
) -> bool:
    ok1, first = _submit_job(client, "job-blocker", audio_path)
    ok2, second = _submit_job(client, "job-cancel-queued", audio_path)
    if not (ok1 and first.get("ok") and ok2 and second.get("ok")):
        return False

    cancel_ok, cancel = _require_result(
        "CancelJobResult",
        client.cancel_job("job-cancel-queued"),
    )
    terminal, _messages = _recv_until_terminal(client, "job-blocker", timeout=job_timeout)
    query_ok, query = _require_result("QueryJobResult", client.query_job("job-cancel-queued"))
    status = query.get("job", {}).get("status")
    canceled_messages = client.recv_job_messages("job-cancel-queued", timeout=0.2)
    return (
        cancel_ok
        and cancel.get("ok")
        and terminal
        and query_ok
        and status == "canceled"
        and not canceled_messages
    )


def _run_running_cancel(
    client: FlowScribeEngineClient,
    audio_path: str,
    job_timeout: float,
) -> bool:
    ok, submit = _submit_job(client, "job-running-cancel", audio_path)
    if not ok or not submit.get("ok"):
        return False

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        query = client.query_job("job-running-cancel")
        if (query or {}).get("job", {}).get("status") == "running":
            break
        time.sleep(0.02)

    cancel_ok, cancel = _require_result(
        "CancelJobResult",
        client.cancel_job("job-running-cancel"),
    )
    terminal, _messages = _recv_until_terminal(client, "job-running-cancel", timeout=job_timeout)
    return (
        cancel_ok
        and not cancel.get("ok")
        and "running job cancellation is not supported yet" in cancel.get("error", "")
        and terminal
    )


def _run_completed_cancel(
    client: FlowScribeEngineClient,
    audio_path: str,
    job_timeout: float,
) -> bool:
    ok = _run_basic_submit(
        client,
        audio_path,
        query_after_result=False,
        job_timeout=job_timeout,
    )
    if not ok:
        return False

    cancel_ok, cancel = _require_result("CancelJobResult", client.cancel_job("job-123"))
    return cancel_ok and not cancel.get("ok") and "job already finished" in cancel.get("error", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test the FlowScribe native engine IPC.")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also send LoadModel and SubmitJob requests. Native support may not exist yet.",
    )
    parser.add_argument("--model-path", default=r"D:\models\ggml-small.bin")
    parser.add_argument("--model-name", default="small")
    parser.add_argument("--audio-path", default=r"D:\audio\test.wav")
    parser.add_argument(
        "--mock-files",
        action="store_true",
        help="Create temporary placeholder model/audio files for IPC-only testing.",
    )
    parser.add_argument(
        "--query-after-result",
        action="store_true",
        help="Query final job status after receiving JobResult or JobError.",
    )
    parser.add_argument(
        "--job-timeout",
        type=float,
        default=60.0,
        help="Seconds to wait for JobResult or JobError in extended scenarios.",
    )
    parser.add_argument(
        "--scenario",
        choices=[
            "basic-submit",
            "query-during-run",
            "queued-cancel",
            "running-cancel",
            "completed-cancel",
        ],
        default="basic-submit",
        help="Extended smoke scenario to run.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.mock_files:
        temp_dir = tempfile.TemporaryDirectory()
        model_path = f"{temp_dir.name}\\mock-model.bin"
        audio_path = f"{temp_dir.name}\\mock-audio.wav"
        open(model_path, "wb").close()
        open(audio_path, "wb").close()
        args.model_path = model_path
        args.audio_path = audio_path
        args.model_name = "__mock__"

    client = FlowScribeEngineClient()
    if not client.connect():
        print("Connection failed")
        if temp_dir is not None:
            temp_dir.cleanup()
        return 1

    try:
        ok = _print_result("HelloResult", client.send_hello())

        if args.extended:
            ok = (
                _print_result(
                    "LoadModelResult",
                    client.load_model(
                        model_path=args.model_path,
                        model_name=args.model_name,
                        use_gpu=False,
                    ),
                )
                and ok
            )
            if args.scenario == "basic-submit":
                ok = _run_basic_submit(
                    client,
                    args.audio_path,
                    query_after_result=args.query_after_result,
                    job_timeout=args.job_timeout,
                ) and ok
            elif args.scenario == "query-during-run":
                ok = _run_query_during_run(client, args.audio_path, args.job_timeout) and ok
            elif args.scenario == "queued-cancel":
                ok = _run_queued_cancel(client, args.audio_path, args.job_timeout) and ok
            elif args.scenario == "running-cancel":
                ok = _run_running_cancel(client, args.audio_path, args.job_timeout) and ok
            elif args.scenario == "completed-cancel":
                ok = _run_completed_cancel(client, args.audio_path, args.job_timeout) and ok

        return 0 if ok else 1
    finally:
        client.close()
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
