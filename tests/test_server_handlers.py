"""Tests for Bookmarklet server handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowscribe.server.handlers import AddUrlHandler


@pytest.fixture
def temp_queue_store(tmp_path: Path) -> Path:
    """Create a temporary queue store path."""
    return tmp_path / "test-queue.json"


@pytest.fixture
def handler(temp_queue_store: Path) -> AddUrlHandler:
    """Create an AddUrlHandler with temporary store."""
    return AddUrlHandler(temp_queue_store)


def test_get_status_empty_queue(handler: AddUrlHandler) -> None:
    """Test status endpoint with empty queue."""
    result = handler.get_status()
    assert result["status"] == "running"
    assert result["queue"]["total"] == 0
    assert result["queue"]["pending"] == 0


def test_get_status_with_items(handler: AddUrlHandler, temp_queue_store: Path) -> None:
    """Test status endpoint with queue items."""
    # Add some items
    handler.add_url("https://example.com/video1")
    handler.add_url("https://example.com/video2")

    result = handler.get_status()
    assert result["status"] == "running"
    assert result["queue"]["total"] == 2
    assert result["queue"]["pending"] == 2


def test_add_url_success(handler: AddUrlHandler) -> None:
    """Test adding a valid URL."""
    result = handler.add_url("https://example.com/video", title="Test Video")

    assert result["status"] == "queued"
    assert result["position"] == 1
    assert "item_id" in result


def test_add_url_empty(handler: AddUrlHandler) -> None:
    """Test adding empty URL."""
    result = handler.add_url("")

    assert result["status"] == "error"
    assert "required" in result["message"].lower()


def test_add_url_invalid(handler: AddUrlHandler) -> None:
    """Test adding invalid URL."""
    result = handler.add_url("not-a-url")

    assert result["status"] == "error"
    assert "invalid" in result["message"].lower()


def test_add_url_private_ip(handler: AddUrlHandler) -> None:
    """Test adding private IP URL."""
    result = handler.add_url("http://192.168.1.1/video")

    assert result["status"] == "error"
    assert "invalid" in result["message"].lower()


def test_add_url_duplicate(handler: AddUrlHandler) -> None:
    """Test adding duplicate URL."""
    url = "https://example.com/video"

    # Add first time
    result1 = handler.add_url(url)
    assert result1["status"] == "queued"

    # Add second time
    result2 = handler.add_url(url)
    assert result2["status"] == "duplicate"
    assert result2["existing_status"] == "pending"


def test_add_url_with_metadata(handler: AddUrlHandler) -> None:
    """Test adding URL with title and timestamp."""
    result = handler.add_url(
        "https://example.com/video",
        title="Test Video",
        timestamp="2026-05-18T10:00:00Z",
    )

    assert result["status"] == "queued"

    # Verify item was stored
    items = handler.store.load_items()
    assert len(items) == 1


def test_add_urls_batch(handler: AddUrlHandler) -> None:
    """Test adding multiple URLs."""
    urls = [
        "https://example.com/video1",
        "https://example.com/video2",
        {"url": "https://example.com/video3", "title": "Video 3"},
    ]

    result = handler.add_urls(urls)

    assert result["status"] == "completed"
    assert result["summary"]["total"] == 3
    assert result["summary"]["queued"] == 3
    assert result["summary"]["duplicates"] == 0
    assert result["summary"]["errors"] == 0


def test_add_urls_with_duplicates(handler: AddUrlHandler) -> None:
    """Test batch add with duplicates."""
    # Add one URL first
    handler.add_url("https://example.com/video1")

    # Try to add batch including duplicate
    urls = [
        "https://example.com/video1",  # Duplicate
        "https://example.com/video2",  # New
    ]

    result = handler.add_urls(urls)

    assert result["status"] == "completed"
    assert result["summary"]["total"] == 2
    assert result["summary"]["queued"] == 1
    assert result["summary"]["duplicates"] == 1


def test_add_urls_with_errors(handler: AddUrlHandler) -> None:
    """Test batch add with invalid URLs."""
    urls = [
        "https://example.com/video1",  # Valid
        "not-a-url",  # Invalid
        "http://192.168.1.1/video",  # Private IP
    ]

    result = handler.add_urls(urls)

    assert result["status"] == "completed"
    assert result["summary"]["total"] == 3
    assert result["summary"]["queued"] == 1
    assert result["summary"]["errors"] == 2


def test_default_settings(handler: AddUrlHandler) -> None:
    """Test default queue item settings."""
    settings = handler._create_default_settings()

    assert settings.output_formats == ("json",)
    assert settings.model_name == "small"
    assert settings.language is None
    assert settings.preset is None
    assert settings.timestamps is True
    assert settings.word_timestamps is False
    assert settings.output_dir == handler.default_output_dir


def test_agent_task_store_uses_persistent_path(temp_queue_store: Path) -> None:
    handler = AddUrlHandler(temp_queue_store)

    expected = temp_queue_store.with_name("agent-tasks.json")

    assert handler.task_store._path == expected.resolve()


def test_handler_disables_task_retention_when_requested(temp_queue_store: Path) -> None:
    handler = AddUrlHandler(temp_queue_store, task_retention_hours=0)

    assert handler.task_retention_hours is None
    assert handler.task_store._task_retention is None
