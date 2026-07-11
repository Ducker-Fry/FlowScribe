"""JSON-backed persistence for the batch queue."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from flowscribe.tasks.models import DownloadOptions, SourceSpec
from flowscribe.tasks.queue_models import (
    QueueItem,
    QueueItemSettings,
)

QUEUE_STORE_VERSION = 1


class BatchQueueStore:

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()

    def load_items(self) -> list[QueueItem]:
        if not self._path.is_file():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._recover_corrupt_file()
            return []
        except OSError:
            return []
        if not isinstance(payload, dict):
            return []
        items_data = payload.get("items", [])
        if not isinstance(items_data, list):
            return []
        result: list[QueueItem] = []
        for entry in items_data:
            item = _item_from_payload(entry)
            if item is not None:
                result.append(item)
        return result

    def save_items(self, items: list[QueueItem]) -> None:
        payload = {
            "version": QUEUE_STORE_VERSION,
            "items": [_item_to_payload(item) for item in items],
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def enqueue(self, item: QueueItem) -> QueueItem | None:
        items = self.load_items()
        if self._find_duplicate_in(items, item.source):
            return None
        items.append(item)
        self.save_items(items)
        return item

    def dequeue(self) -> QueueItem | None:
        items = self.load_items()
        for i, item in enumerate(items):
            if item.status == "pending":
                updated = replace(item, status="running", started_at=datetime.now())
                items[i] = updated
                self.save_items(items)
                return updated
        return None

    def update_item(self, item_id: str, **updates) -> QueueItem | None:
        items = self.load_items()
        for i, item in enumerate(items):
            if item.item_id == item_id:
                items[i] = replace(item, **updates)
                self.save_items(items)
                return items[i]
        return None

    def get_item(self, item_id: str) -> QueueItem | None:
        """Get a single item by ID.

        Returns:
            The queue item if found, None otherwise.
        """
        items = self.load_items()
        for item in items:
            if item.item_id == item_id:
                return item
        return None

    def remove_item(self, item_id: str) -> bool:
        items = self.load_items()
        before = len(items)
        items = [item for item in items if item.item_id != item_id]
        if len(items) < before:
            self.save_items(items)
            return True
        return False

    def remove_items(self, item_ids: list[str]) -> int:
        """Remove multiple items by ID.

        Returns:
            Number of items removed.
        """
        items = self.load_items()
        before = len(items)
        item_ids_set = set(item_ids)
        items = [item for item in items if item.item_id not in item_ids_set]
        removed = before - len(items)
        if removed > 0:
            self.save_items(items)
        return removed

    def remove_completed(self) -> int:
        items = self.load_items()
        before = len(items)
        items = [item for item in items if item.status != "completed"]
        removed = before - len(items)
        if removed:
            self.save_items(items)
        return removed

    def reorder(self, item_ids: list[str]) -> None:
        items = self.load_items()
        id_to_item = {item.item_id: item for item in items}
        reordered: list[QueueItem] = []
        for idx, item_id in enumerate(item_ids):
            if item_id in id_to_item:
                reordered.append(replace(id_to_item.pop(item_id), priority=idx))
        for item in id_to_item.values():
            reordered.append(replace(item, priority=len(reordered)))
        self.save_items(reordered)

    def find_duplicate(self, source: SourceSpec) -> QueueItem | None:
        return self._find_duplicate_in(self.load_items(), source)

    def pending_count(self) -> int:
        return sum(1 for item in self.load_items() if item.status == "pending")

    def _find_duplicate_in(
        self, items: list[QueueItem], source: SourceSpec
    ) -> QueueItem | None:
        key = f"{source.kind}:{source.value}"
        for item in items:
            if item.status in ("pending", "running"):
                if f"{item.source.kind}:{item.source.value}" == key:
                    return item
        return None

    def _recover_corrupt_file(self) -> None:
        if not self._path.is_file():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = self._path.with_suffix(f".corrupt-{timestamp}")
        try:
            self._path.rename(backup)
        except OSError:
            pass


def _item_to_payload(item: QueueItem) -> dict:
    download_opts = None
    if item.source.download_options:
        download_opts = {
            "quality": item.source.download_options.quality,
            "prefer_format": item.source.download_options.prefer_format,
        }

    return {
        "item_id": item.item_id,
        "source": {
            "kind": item.source.kind,
            "value": item.source.value,
            "recursive": item.source.recursive,
            "keep_media": item.source.keep_media,
            "url_media_kind": item.source.url_media_kind,
            "media_output_dir": str(item.source.media_output_dir)
            if item.source.media_output_dir
            else None,
            "auto_bind_media": item.source.auto_bind_media,
            "download_options": download_opts,
        },
        "settings": {
            "output_dir": str(item.settings.output_dir),
            "execution_mode": item.settings.execution_mode,
            "server_target": item.settings.server_target,
            "remote_token": item.settings.remote_token,
            "remote_poll_seconds": item.settings.remote_poll_seconds,
            "download_artifacts": item.settings.download_artifacts,
            "provider_name": item.settings.provider_name,
            "model_name": item.settings.model_name,
            "language": item.settings.language,
            "preset": item.settings.preset,
            "output_formats": list(item.settings.output_formats),
            "timestamps": item.settings.timestamps,
            "word_timestamps": item.settings.word_timestamps,
            "overwrite": item.settings.overwrite,
            "network_family": item.settings.network_family,
            "proxy": item.settings.proxy,
            "cookies_path": str(item.settings.cookies_path)
            if item.settings.cookies_path
            else None,
            "progressive_enabled": item.settings.progressive_enabled,
            "progressive_resume": item.settings.progressive_resume,
            "progressive_chunk_seconds": item.settings.progressive_chunk_seconds,
            "progressive_max_workers": item.settings.progressive_max_workers,
            "max_download_mb": item.settings.max_download_mb,
            "max_duration_seconds": item.settings.max_duration_seconds,
            "download_timeout_seconds": item.settings.download_timeout_seconds,
            "native_threads": item.settings.native_threads,
        },
        "status": item.status,
        "priority": item.priority,
        "attempt_count": item.attempt_count,
        "max_retries": item.max_retries,
        "error_message": item.error_message,
        "created_at": item.created_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "title": item.title,
        "transcript_path": str(item.transcript_path) if item.transcript_path else None,
        "run_detail": item.run_detail,
    }


def _item_from_payload(data: object) -> QueueItem | None:
    if not isinstance(data, dict):
        return None
    try:
        source_data = data["source"]
        settings_data = data.get("settings", {})

        download_opts = None
        if source_data.get("download_options"):
            opts_data = source_data["download_options"]
            download_opts = DownloadOptions(
                quality=opts_data.get("quality", "best"),
                prefer_format=opts_data.get("prefer_format"),
            )

        source = SourceSpec(
            kind=source_data["kind"],
            value=source_data["value"],
            recursive=source_data.get("recursive", False),
            keep_media=source_data.get("keep_media", False),
            url_media_kind=source_data.get("url_media_kind", "audio"),
            media_output_dir=Path(source_data["media_output_dir"])
            if source_data.get("media_output_dir")
            else None,
            auto_bind_media=source_data.get("auto_bind_media", False),
            download_options=download_opts,
        )

        settings = QueueItemSettings(
            output_dir=Path(settings_data.get("output_dir", "outputs")),
            execution_mode=settings_data.get("execution_mode", "local"),
            server_target=settings_data.get("server_target"),
            remote_token=settings_data.get("remote_token"),
            remote_poll_seconds=settings_data.get("remote_poll_seconds", 1.0),
            download_artifacts=settings_data.get("download_artifacts"),
            provider_name=settings_data.get("provider_name", "local-whisper"),
            model_name=settings_data.get("model_name", "small"),
            language=settings_data.get("language"),
            preset=settings_data.get("preset"),
            output_formats=tuple(settings_data.get("output_formats", ("txt", "md", "json"))),
            timestamps=settings_data.get("timestamps", True),
            word_timestamps=settings_data.get("word_timestamps", False),
            overwrite=settings_data.get("overwrite", False),
            network_family=settings_data.get("network_family", "auto"),
            proxy=settings_data.get("proxy"),
            cookies_path=Path(settings_data["cookies_path"])
            if settings_data.get("cookies_path")
            else None,
            progressive_enabled=settings_data.get("progressive_enabled", True),
            progressive_resume=settings_data.get("progressive_resume", True),
            progressive_chunk_seconds=settings_data.get("progressive_chunk_seconds", 30.0),
            progressive_max_workers=settings_data.get("progressive_max_workers", 1),
            max_download_mb=settings_data.get("max_download_mb", 2048),
            max_duration_seconds=settings_data.get("max_duration_seconds", 14400.0),
            download_timeout_seconds=settings_data.get("download_timeout_seconds", 30),
            native_threads=settings_data.get("native_threads"),
        )

        return QueueItem(
            item_id=data["item_id"],
            source=source,
            settings=settings,
            status=data.get("status", "pending"),
            priority=data.get("priority", 0),
            attempt_count=data.get("attempt_count", 0),
            max_retries=data.get("max_retries", 2),
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None,
            finished_at=datetime.fromisoformat(data["finished_at"])
            if data.get("finished_at")
            else None,
            title=data.get("title"),
            transcript_path=Path(data["transcript_path"]) if data.get("transcript_path") else None,
            run_detail=data.get("run_detail"),
        )
    except (KeyError, TypeError, ValueError):
        return None
