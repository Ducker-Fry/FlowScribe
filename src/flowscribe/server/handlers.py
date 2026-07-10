"""Request handlers for Bookmarklet server."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flowscribe.server.agent_api import AgentTaskStore, agent_task_store_path_for
from flowscribe.server.storage import UploadBlobStore
from flowscribe.tasks.models import SourceSpec
from flowscribe.input.url_security import validate_public_http_url
from flowscribe.tasks.queue_models import (
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
)
from flowscribe.tasks.queue_store import BatchQueueStore

logger = logging.getLogger(__name__)


def _get_app_data_dir() -> Path:
    """Get FlowScribe AppData directory (Windows-specific)."""
    if os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "FlowScribe"
    return Path.home() / ".flowscribe"



class AddUrlHandler:
    """Handler for adding URLs to the batch queue."""

    def __init__(
        self,
        queue_store_path: Path,
        default_output_dir: Path | None = None,
        default_output_formats: tuple[str, ...] = ("json",),
        default_model_name: str = "small",
        default_language: str | None = None,
        api_token: str | None = None,
        task_retention_hours: float | None = 24.0,
    ) -> None:
        self.queue_store_path = queue_store_path
        self.store = BatchQueueStore(queue_store_path)
        self.upload_store = UploadBlobStore(queue_store_path.with_name("remote-blobs"))
        self.task_retention_hours = _normalize_task_retention_hours(task_retention_hours)
        self.task_store = AgentTaskStore(
            agent_task_store_path_for(queue_store_path),
            blob_resolver=self.upload_store.resolve,
            blob_deleter=self.upload_store.delete,
            task_retention=_retention_timedelta_from_hours(self.task_retention_hours),
        )
        self.default_output_dir = default_output_dir or (Path.home() / "Documents" / "FlowScribe")
        self.default_output_formats = default_output_formats
        self.default_model_name = default_model_name
        self.default_language = default_language
        self.api_token = api_token

    def get_status(self) -> dict[str, Any]:
        """Get server and queue status."""
        items = self.store.load_items()
        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")

        return {
            "status": "running",
            "queue": {
                "total": len(items),
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed,
            },
        }

    def add_url(
        self,
        url: str,
        title: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Add a single URL to the queue."""
        if not url:
            return {"status": "error", "message": "URL is required"}

        # Validate URL
        try:
            validate_public_http_url(url)
        except Exception as e:
            logger.warning(f"Invalid URL rejected: {url} - {e}")
            return {"status": "error", "message": f"Invalid URL: {e}"}

        # Create queue item with default settings
        source = SourceSpec(kind="url", value=url)
        settings = self._create_default_settings()

        item = QueueItem(
            item_id=generate_queue_item_id(source),
            source=source,
            settings=settings,
            status="pending",
            created_at=datetime.now(),
            title=title if title else None,
        )

        # Check for duplicates and enqueue
        result = self.store.enqueue(item)
        if result is None:
            # Find existing item to report status
            items = self.store.load_items()
            for existing in items:
                if existing.source == source:
                    return {
                        "status": "duplicate",
                        "message": "URL already in queue",
                        "existing_status": existing.status,
                    }
            return {"status": "error", "message": "Failed to add URL"}

        # Calculate position in queue
        items = self.store.load_items()
        position = sum(1 for item in items if item.status in ("pending", "running"))

        logger.info(f"Added URL to queue: {url} (position: {position})")
        return {
            "status": "queued",
            "message": "URL added to queue",
            "position": position,
            "item_id": result.item_id,
        }

    def add_urls(self, urls: list[dict[str, Any]]) -> dict[str, Any]:
        """Add multiple URLs to the queue."""
        results = []
        for entry in urls:
            if isinstance(entry, str):
                url = entry
                title = None
            elif isinstance(entry, dict):
                url = entry.get("url", "")
                title = entry.get("title")
            else:
                results.append({"url": str(entry), "status": "error", "message": "Invalid format"})
                continue

            result = self.add_url(url, title)
            results.append({"url": url, **result})

        queued = sum(1 for r in results if r["status"] == "queued")
        duplicates = sum(1 for r in results if r["status"] == "duplicate")
        errors = sum(1 for r in results if r["status"] == "error")

        return {
            "status": "completed",
            "summary": {
                "total": len(urls),
                "queued": queued,
                "duplicates": duplicates,
                "errors": errors,
            },
            "results": results,
        }

    def cleanup_expired_remote_data(self) -> int:
        return self.task_store.prune_expired()

    def _create_default_settings(self) -> QueueItemSettings:
        """Create default queue item settings from server configuration."""
        return QueueItemSettings(
            output_dir=self.default_output_dir,
            output_formats=self.default_output_formats,
            model_name=self.default_model_name,
            language=self.default_language,
            preset=None,
            timestamps=True,
            word_timestamps=False,
            overwrite=False,
        )


def _normalize_task_retention_hours(value: float | None) -> float | None:
    if value is None:
        return None
    if value <= 0:
        return None
    return float(value)


def _retention_timedelta_from_hours(value: float | None) -> timedelta | None:
    if value is None:
        return None
    return timedelta(hours=value)
