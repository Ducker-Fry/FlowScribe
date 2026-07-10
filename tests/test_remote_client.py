from __future__ import annotations

import pytest

from flowscribe.execution.remote_client import (
    POLL_RETRY_ATTEMPTS,
    RemoteServerClient,
    _TransientRemoteError,
)


class _RetryingJsonClient(RemoteServerClient):
    def __init__(self, failures_before_success: int) -> None:
        super().__init__("http://example.com")
        object.__setattr__(self, "calls", 0)
        object.__setattr__(self, "delays", [])
        object.__setattr__(self, "failures_before_success", failures_before_success)

    def _request_json(self, url: str, *, method: str = "GET", data=None, headers=None):
        object.__setattr__(self, "calls", self.calls + 1)
        if self.calls <= self.failures_before_success:
            raise _TransientRemoteError("Bad Gateway")
        return {"task_id": "task-1", "status": "running"}

    def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


class _RetryingTextClient(RemoteServerClient):
    def __init__(self, failures_before_success: int) -> None:
        super().__init__("http://example.com")
        object.__setattr__(self, "calls", 0)
        object.__setattr__(self, "delays", [])
        object.__setattr__(self, "failures_before_success", failures_before_success)

    def _request_text(self, url: str, *, method: str = "GET", data=None, headers=None):
        object.__setattr__(self, "calls", self.calls + 1)
        if self.calls <= self.failures_before_success:
            raise _TransientRemoteError("Timed out while contacting remote server http://example.com.")
        return 'data: {"task_id":"task-1","stage":"transcribe","message":"Chunk done"}\n'

    def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


def test_get_task_status_retries_transient_gateway_failures() -> None:
    client = _RetryingJsonClient(failures_before_success=2)

    status = client.get_task_status("task-1")

    assert status["status"] == "running"
    assert client.calls == 3
    assert client.delays == [1.0, 2.0]


def test_get_task_events_retries_transient_timeouts() -> None:
    client = _RetryingTextClient(failures_before_success=1)

    events = client.get_task_events("task-1")

    assert len(events) == 1
    assert events[0]["message"] == "Chunk done"
    assert client.calls == 2
    assert client.delays == [1.0]


def test_get_task_result_raises_after_retry_budget_exhausted() -> None:
    client = _RetryingJsonClient(failures_before_success=POLL_RETRY_ATTEMPTS + 1)

    with pytest.raises(_TransientRemoteError, match="Bad Gateway"):
        client.get_task_result("task-1")

    assert client.calls == POLL_RETRY_ATTEMPTS + 1
    assert len(client.delays) == POLL_RETRY_ATTEMPTS
