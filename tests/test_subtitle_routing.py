from pathlib import Path

from flowscribe.app.service import TranscriptionService
from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.tasks.models import CapabilityResult, ErrorEvent, SourceSpec, TranscriptionJob


def test_url_subtitle_capability_falls_back_to_transcription(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "remote-audio.m4a"
    audio.write_bytes(b"audio")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.txt",))

    class FakeDownload:
        path = audio
        cleanup_dir = tmp_path / "download"
        saved_media_path = None
        saved_media_kind = "audio"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            return artifact

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/video"),),
        output_dir=tmp_path / "out",
        requested_capabilities=("subtitle", "transcribe"),
    )
    events = []

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    assert result.outputs[0].paths == artifact.paths
    assert any(event.capability == "subtitle" for event in events)
    assert any(event.capability == "transcribe" for event in events)


def test_transcription_service_exposes_cancel_protocol(tmp_path: Path) -> None:
    service = TranscriptionService()
    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(tmp_path / "sample.mp4")),),
        output_dir=tmp_path / "out",
    )
    task = job.to_task_specs()[0]

    request = service.build_cancel_request(task)
    ack = service.acknowledge_cancel(request, checkpoint=task.checkpoint_id)

    assert request.task_id == task.task_id
    assert ack.status == "cancelled"
    assert ack.checkpoint == task.checkpoint_id


def test_url_subtitle_failure_does_not_fallback_to_transcription(monkeypatch, tmp_path: Path) -> None:
    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            raise AssertionError("audio downloader should not run when subtitle extraction fails")

    def fake_run_subtitle_capability(self, task_spec, progress, should_cancel, *, current: int, total: int):
        return CapabilityResult(
            task_id=task_spec.task_id,
            capability="subtitle",
            supported=True,
            status="failed",
            error=ErrorEvent(
                task_id=task_spec.task_id,
                capability="subtitle",
                error_type="runtime",
                user_message="Subtitle payload is malformed.",
                internal_message="parse error",
                retryable=False,
                code="TranscriptionError",
            ),
        )

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr(
        "flowscribe.app.service.TranscriptionService._run_subtitle_capability",
        fake_run_subtitle_capability,
    )

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://www.youtube.com/watch?v=abc123"),),
        output_dir=tmp_path / "out",
        requested_capabilities=("subtitle", "transcribe"),
    )

    result = TranscriptionService().run(job)

    assert result.ok is False
    assert result.failed == 1
    assert "Subtitle payload is malformed." in result.errors[0].message
