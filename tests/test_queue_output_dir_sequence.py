from pathlib import Path

from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings, allocate_series_output_dir


def test_allocate_series_output_dir_starts_at_001(tmp_path: Path) -> None:
    allocated = allocate_series_output_dir(tmp_path)

    assert allocated == tmp_path / "001"
    assert allocated.exists()


def test_allocate_series_output_dir_increments_from_existing_numeric_dirs(tmp_path: Path) -> None:
    (tmp_path / "001").mkdir()
    (tmp_path / "002").mkdir()
    (tmp_path / "notes").mkdir()

    allocated = allocate_series_output_dir(tmp_path)

    assert allocated == tmp_path / "003"
    assert allocated.exists()


def test_queue_item_to_job_uses_numbered_series_output_dir(tmp_path: Path) -> None:
    settings = QueueItemSettings(output_dir=tmp_path)
    item = QueueItem(
        item_id="abc123",
        source=SourceSpec(kind="url", value="https://example.com/video"),
        settings=settings,
    )

    first_job = item.to_job()
    second_job = item.to_job()

    assert first_job.output_dir == tmp_path / "001"
    assert second_job.output_dir == tmp_path / "002"
