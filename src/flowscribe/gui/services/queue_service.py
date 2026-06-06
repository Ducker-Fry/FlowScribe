"""Shared queue operations for GUI windows."""

from __future__ import annotations

from pathlib import Path

from flowscribe.tasks.models import DownloadOptions, SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings, generate_queue_item_id


def build_url_queue_items(
    urls: list[str],
    *,
    settings: QueueItemSettings,
    download_options: dict[str, object],
) -> list[QueueItem]:
    download_opts = DownloadOptions(
        quality=download_options["quality"],
        prefer_format=download_options["prefer_format"],
    )
    items: list[QueueItem] = []
    for url in urls:
        source = SourceSpec(
            kind="url",
            value=url,
            keep_media=bool(download_options["preserve_media"]),
            url_media_kind=str(download_options["media_kind"]),
            download_options=download_opts,
            auto_bind_media=True,
        )
        items.append(
            QueueItem(
                item_id=generate_queue_item_id(source),
                source=source,
                settings=settings,
            )
        )
    return items


def build_local_queue_items(paths: list[Path], *, settings: QueueItemSettings) -> list[QueueItem]:
    items: list[QueueItem] = []
    for path in paths:
        source = SourceSpec(kind="local", value=str(path))
        items.append(
            QueueItem(
                item_id=generate_queue_item_id(source),
                source=source,
                settings=settings,
            )
        )
    return items
