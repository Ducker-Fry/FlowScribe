from pathlib import Path

from flowscribe.app.models import SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.core.models import MediaItem, OutputArtifacts


def test_transcription_service_returns_structured_error_for_capture_source(tmp_path: Path) -> None:
    job = TranscriptionJob(
        sources=(SourceSpec(kind="capture", value="system"),),
        output_dir=tmp_path / "out",
    )
    events = []

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is False
    assert result.succeeded == 0
    assert result.failed == 1
    assert result.errors[0].code == "FlowScribeError"
    assert result.errors[0].source == "system"
    assert events[-1].stage == "complete"


def test_transcription_service_runs_local_source_with_progress(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "sample.txt",))

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    class FakePipeline:
        def process(self, item: MediaItem) -> OutputArtifacts:
            assert item.path == media
            return artifact

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
    )
    events = []

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    assert result.succeeded == 1
    assert result.outputs == (artifact,)
    assert [event.stage for event in events] == ["discover", "discover", "transcribe", "write", "complete"]
