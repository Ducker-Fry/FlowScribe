from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import OutputArtifacts
from flowscribe.gui.workers.queue_runner import QueueRunner
from flowscribe.tasks.models import SourceSpec, TranscriptionResult
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings, generate_queue_item_id
from flowscribe.tasks.queue_store import BatchQueueStore


def test_queue_store_persists_remote_execution_settings(tmp_path: Path) -> None:
    store = BatchQueueStore(tmp_path / "queue.json")
    source = SourceSpec(kind="local", value=str(tmp_path / "sample.wav"))
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(
            execution_mode="remote",
            server_target="local-test",
            remote_token="secret",
            remote_poll_seconds=2.0,
            download_artifacts=True,
        ),
    )

    store.enqueue(item)
    loaded = store.load_items()[0]

    assert loaded.settings.execution_mode == "remote"
    assert loaded.settings.server_target == "local-test"
    assert loaded.settings.remote_token == "secret"
    assert loaded.settings.remote_poll_seconds == 2.0
    assert loaded.settings.download_artifacts is True


def test_queue_runner_uses_injected_execution_backend(tmp_path: Path) -> None:
    store = BatchQueueStore(tmp_path / "queue.json")
    source_path = tmp_path / "sample.wav"
    source_path.write_bytes(b"audio")
    source = SourceSpec(kind="local", value=str(source_path))
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(output_dir=tmp_path / "outputs"),
    )
    store.enqueue(item)

    created_for: list[str] = []

    class FakeBackend:
        def run(self, job, *, progress=None, should_cancel=None):
            created_for.append(job.sources[0].value)
            output_dir = job.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / "queued.json"
            json_path.write_text("{}", encoding="utf-8")
            return TranscriptionResult(
                job=job,
                task_specs=job.to_task_specs(),
                outputs=(OutputArtifacts(paths=(json_path,), source_kind="local", source_value=job.sources[0].value),),
            )

    runner = QueueRunner(store, execution_backend_factory=lambda queue_item: FakeBackend())
    completed = runner._process_item(store.dequeue())

    assert completed is True
    assert created_for == [str(source_path)]
    updated = store.load_items()[0]
    assert updated.status == "completed"
    assert updated.transcript_path is not None
