from __future__ import annotations

import logging

from flowscribe.engine.pipe_client import FlowScribeEngineClient
from flowscribe.engine.protocol import MessageKind


class FakeEngineClient(FlowScribeEngineClient):
    def __init__(self, messages):
        super().__init__()
        self._messages = list(messages)

    def recv_message(self, *, quiet_timeout: bool = False):
        if not self._messages:
            return None
        return self._messages.pop(0)

    def send_message(self, kind: int, payload: dict) -> bool:
        self.sent = (kind, payload)
        return True


def test_recv_expected_buffers_async_messages() -> None:
    client = FakeEngineClient(
        [
            (MessageKind.JobEvent, {"job_id": "job-1", "status": "job_started"}),
            (MessageKind.JobEvent, {"job_id": "job-1", "status": "transcribing"}),
            (MessageKind.JobResult, {"job_id": "job-1", "segments": []}),
            (MessageKind.QueryJobResult, {"ok": True, "job_id": "job-1"}),
        ]
    )

    result = client._recv_expected(MessageKind.QueryJobResult)

    assert result == {"ok": True, "job_id": "job-1"}
    assert list(client._async_inbox) == [
        (MessageKind.JobEvent, {"job_id": "job-1", "status": "job_started"}),
        (MessageKind.JobEvent, {"job_id": "job-1", "status": "transcribing"}),
        (MessageKind.JobResult, {"job_id": "job-1", "segments": []}),
    ]


def test_recv_job_messages_consumes_cached_async_messages_first() -> None:
    client = FakeEngineClient(
        [
            (MessageKind.JobResult, {"job_id": "job-1", "segments": []}),
        ]
    )
    client._async_inbox.append(
        (MessageKind.JobEvent, {"job_id": "job-1", "status": "job_started"})
    )

    messages = client.recv_job_messages("job-1")

    assert messages == [
        (MessageKind.JobEvent, {"job_id": "job-1", "status": "job_started"}),
        (MessageKind.JobResult, {"job_id": "job-1", "segments": []}),
    ]


def test_recv_message_quiet_timeout_suppresses_expected_polling_logs(caplog) -> None:
    client = FlowScribeEngineClient(timeout=0.0)
    caplog.set_level(logging.ERROR, logger="flowscribe.engine.pipe_client")

    result = client.recv_message(quiet_timeout=True)

    assert result is None
    assert "Read timed out" not in caplog.text
    assert "Failed to read frame header" not in caplog.text


def test_submit_job_includes_threads_only_when_provided() -> None:
    client = FakeEngineClient([(MessageKind.SubmitJobResult, {"ok": True, "job_id": "job-1"})])

    client.submit_job(job_id="job-1", audio_path="audio.wav", threads=8)

    assert client.sent[0] == MessageKind.SubmitJobRequest
    assert client.sent[1]["threads"] == 8


def test_submit_job_omits_threads_by_default() -> None:
    client = FakeEngineClient([(MessageKind.SubmitJobResult, {"ok": True, "job_id": "job-1"})])

    client.submit_job(job_id="job-1", audio_path="audio.wav")

    assert "threads" not in client.sent[1]


def test_submit_job_default_progressive_includes_max_workers() -> None:
    client = FakeEngineClient([(MessageKind.SubmitJobResult, {"ok": True, "job_id": "job-1"})])

    client.submit_job(job_id="job-1", audio_path="audio.wav")

    assert client.sent[1]["progressive"]["max_workers"] == 1
