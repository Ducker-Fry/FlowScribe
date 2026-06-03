"""Shared runtime coordination helpers for queue and server flows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread

from flowscribe.gui.workers.bookmarklet_server_worker import BookmarkletServerWorker
from flowscribe.gui.workers.queue_runner import QueueRunner


def start_queue_runtime(owner, store, started, progress, completed, failed, canceled, finished):
    thread = QThread(owner)
    runner = QueueRunner(store)
    runner.moveToThread(thread)
    thread.started.connect(runner.run)
    runner.item_started.connect(started)
    runner.item_progress.connect(progress)
    runner.item_completed.connect(completed)
    runner.item_failed.connect(failed)
    runner.item_canceled.connect(canceled)
    runner.queue_finished.connect(finished)
    runner.queue_finished.connect(thread.quit)
    thread.finished.connect(runner.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, runner


def start_bookmarklet_server_runtime(
    owner,
    *,
    queue_store_path: Path,
    port: int,
    default_output_dir: Path,
    default_output_formats,
    default_model_name,
    default_language,
    started,
    stopped,
    error,
):
    thread = QThread(owner)
    worker = BookmarkletServerWorker(
        queue_store_path=queue_store_path,
        port=port,
        default_output_dir=default_output_dir,
        default_output_formats=default_output_formats,
        default_model_name=default_model_name,
        default_language=default_language,
    )
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.started.connect(started)
    worker.stopped.connect(stopped)
    worker.error.connect(error)
    worker.stopped.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
