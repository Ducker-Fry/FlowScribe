from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from flowscribe.engine.pipe_client import FlowScribeEngineClient, pywintypes, win32file


ROOT = Path(__file__).resolve().parents[1]
ENGINE_EXE = ROOT / "native" / "flowscribe-engine" / "build" / "Debug" / "flowscribe-engine.exe"


def _can_run_engine_ipc() -> bool:
    return sys.platform == "win32" and pywintypes is not None and win32file is not None and ENGINE_EXE.exists()


pytestmark = pytest.mark.skipif(
    not _can_run_engine_ipc(),
    reason="native engine IPC smoke requires Windows, pywin32, and built flowscribe-engine.exe",
)


class EngineHarness:
    def __init__(self, mock_delay_ms: int = 0) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.model_path = self.root / "mock-model.bin"
        self.audio_path = self.root / "mock-audio.wav"
        self.model_path.write_bytes(b"mock")
        self.audio_path.write_bytes(b"mock")
        self.client = FlowScribeEngineClient(timeout=2.0)
        env = os.environ.copy()
        if mock_delay_ms > 0:
            env["FLOWSCRIBE_ENGINE_MOCK_JOB_DELAY_MS"] = str(mock_delay_ms)
        self.proc = subprocess.Popen(
            [str(ENGINE_EXE)],
            cwd=str(ENGINE_EXE.parent),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def __enter__(self) -> "EngineHarness":
        assert self.client.connect(retry=20, delay=0.05)
        assert self.client.send_hello()["ok"]
        load = self.client.load_model(str(self.model_path), "__mock__", use_gpu=False)
        assert load and load["ok"]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.client.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.temp_dir.cleanup()


def _submit(client: FlowScribeEngineClient, job_id: str, audio_path: Path) -> dict:
    result = client.submit_job(job_id=job_id, audio_path=str(audio_path), language="zh")
    assert result is not None
    assert result["ok"]
    return result


def _wait_status(client: FlowScribeEngineClient, job_id: str, status: str) -> dict:
    deadline = time.monotonic() + 2.0
    last = {}
    while time.monotonic() < deadline:
        last = client.query_job(job_id) or {}
        if last.get("job", {}).get("status") == status:
            return last
        time.sleep(0.02)
    return last


def test_submit_events_result_and_completed_query() -> None:
    with EngineHarness() as engine:
        _submit(engine.client, "job-basic", engine.audio_path)

        messages = engine.client.recv_job_messages("job-basic", timeout=2.0)

        kinds = [kind for kind, _payload in messages]
        statuses = [payload.get("status") for kind, payload in messages if kind == 0x0030]
        assert kinds[-1] == 0x0031
        assert "job_started" in statuses
        assert "job_completed" in statuses

        query = engine.client.query_job("job-basic")
        assert query is not None
        assert query["job"]["status"] == "completed"
        assert query["job"]["result"]["job_id"] == "job-basic"


def test_query_during_running_does_not_wait_for_completion() -> None:
    with EngineHarness(mock_delay_ms=400) as engine:
        _submit(engine.client, "job-query", engine.audio_path)

        query = _wait_status(engine.client, "job-query", "running")

        assert query["job"]["status"] == "running"
        assert query["job"]["finished_at"] == 0
        assert engine.client.recv_job_messages("job-query", timeout=2.0)[-1][0] == 0x0031


def test_queued_cancel_prevents_worker_result() -> None:
    with EngineHarness(mock_delay_ms=400) as engine:
        _submit(engine.client, "job-blocker", engine.audio_path)
        _submit(engine.client, "job-cancel-queued", engine.audio_path)

        cancel = engine.client.cancel_job("job-cancel-queued")
        assert cancel is not None
        assert cancel["ok"]

        assert engine.client.recv_job_messages("job-blocker", timeout=2.0)[-1][0] == 0x0031
        query = engine.client.query_job("job-cancel-queued")
        assert query is not None
        assert query["job"]["status"] == "canceled"
        assert engine.client.recv_job_messages("job-cancel-queued", timeout=0.2) == []


def test_running_and_completed_cancel_errors() -> None:
    with EngineHarness(mock_delay_ms=400) as engine:
        _submit(engine.client, "job-running", engine.audio_path)
        running = _wait_status(engine.client, "job-running", "running")
        assert running["job"]["status"] == "running"

        cancel = engine.client.cancel_job("job-running")
        assert cancel is not None
        assert not cancel["ok"]
        assert "running job cancellation is not supported yet" in cancel["error"]

        assert engine.client.recv_job_messages("job-running", timeout=2.0)[-1][0] == 0x0031
        completed_cancel = engine.client.cancel_job("job-running")
        assert completed_cancel is not None
        assert not completed_cancel["ok"]
        assert "job already finished" in completed_cancel["error"]
