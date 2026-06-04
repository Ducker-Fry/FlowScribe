"""Integration tests for Bookmarklet server."""

from __future__ import annotations

import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from time import sleep

import pytest

from flowscribe.server import BookmarkletServer


@pytest.fixture
def server_thread(tmp_path: Path):
    """Start server in background thread."""
    queue_store = tmp_path / "queue.json"
    server = BookmarkletServer(queue_store, host="127.0.0.1", port=18765)

    thread = Thread(target=server.start, daemon=True)
    thread.start()
    sleep(0.5)  # Wait for server to start

    yield server

    server.stop()


def test_server_status_endpoint(server_thread: BookmarkletServer) -> None:
    """Test GET /status endpoint."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    conn.request("GET", "/status")
    response = conn.getresponse()

    assert response.status == 200
    data = json.loads(response.read().decode())
    assert data["status"] == "running"
    assert "queue" in data


def test_server_add_url_endpoint(server_thread: BookmarkletServer) -> None:
    """Test POST /add-url endpoint."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)

    payload = json.dumps({
        "url": "https://example.com/video",
        "title": "Test Video",
    })

    conn.request(
        "POST",
        "/add-url",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()

    assert response.status == 200
    data = json.loads(response.read().decode())
    assert data["status"] == "queued"
    assert data["position"] == 1


def test_server_add_url_invalid(server_thread: BookmarkletServer) -> None:
    """Test POST /add-url with invalid URL."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)

    payload = json.dumps({"url": "not-a-url"})

    conn.request(
        "POST",
        "/add-url",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()

    assert response.status == 400
    data = json.loads(response.read().decode())
    assert data["status"] == "error"


def test_server_bookmarklet_script(server_thread: BookmarkletServer) -> None:
    """Test GET /bookmarklet.js endpoint."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    conn.request("GET", "/bookmarklet.js")
    response = conn.getresponse()

    assert response.status == 200
    assert response.getheader("Content-Type") == "application/javascript; charset=utf-8"

    script = response.read().decode()
    assert "javascript:" in script
    assert "fetch" in script
    assert "127.0.0.1:8765" in script


def test_server_cors_headers(server_thread: BookmarkletServer) -> None:
    """Test CORS headers are present."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    conn.request("OPTIONS", "/add-url")
    response = conn.getresponse()

    assert response.status == 200
    assert response.getheader("Access-Control-Allow-Origin") == "*"
    assert "POST" in response.getheader("Access-Control-Allow-Methods", "")


def test_server_not_found(server_thread: BookmarkletServer) -> None:
    """Test 404 for unknown endpoints."""
    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    conn.request("GET", "/unknown")
    response = conn.getresponse()

    assert response.status == 404


def test_server_submit_agent_task_endpoint(monkeypatch, server_thread: BookmarkletServer) -> None:
    from flowscribe.tasks.models import TranscriptionResult

    def fake_run(self, job, progress=None, should_cancel=None):
        return TranscriptionResult(job=job, task_specs=job.to_task_specs())

    monkeypatch.setattr("flowscribe.server.agent_api.TranscriptionService.run", fake_run)

    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    payload = json.dumps(
        {
            "task_id": "task-1",
            "source": {"kind": "local", "value": "C:/media/sample.mp4"},
            "output": {"formats": ["json"], "output_dir": "outputs"},
        }
    )
    conn.request(
        "POST",
        "/v1/tasks",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()

    assert response.status == 202
    data = json.loads(response.read().decode())
    assert data["task_id"] == "task-1"


def test_server_task_events_endpoint(monkeypatch, server_thread: BookmarkletServer) -> None:
    from flowscribe.tasks.models import ProgressEvent, TranscriptionResult

    def fake_run(self, job, progress=None, should_cancel=None):
        progress(
            ProgressEvent(
                stage="discover",
                message="Received 1 source(s).",
                task_id="task-events",
                event_type="task.accepted",
                timestamp="2026-06-04T00:00:00.000Z",
                sequence=1,
            )
        )
        return TranscriptionResult(job=job, task_specs=job.to_task_specs())

    monkeypatch.setattr("flowscribe.server.agent_api.TranscriptionService.run", fake_run)

    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    payload = json.dumps(
        {
            "task_id": "task-events",
            "source": {"kind": "local", "value": "C:/media/sample.mp4"},
            "output": {"formats": ["json"], "output_dir": "outputs"},
        }
    )
    conn.request("POST", "/v1/tasks", body=payload, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    assert response.status == 202
    response.read()
    sleep(0.1)

    conn = HTTPConnection("127.0.0.1", 18765, timeout=5)
    conn.request("GET", "/v1/tasks/task-events/events")
    response = conn.getresponse()

    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream; charset=utf-8"
    body = response.read().decode()
    assert "task.accepted" in body
