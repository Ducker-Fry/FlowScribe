from pathlib import Path

from flowscribe.app.models import SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import MediaPreparationError
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


def test_transcription_service_keeps_processing_after_local_item_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bad_media = tmp_path / "bad.mp4"
    good_media = tmp_path / "good.mp4"
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "good.txt",))

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=bad_media), MediaItem(path=good_media)]

    class FakePipeline:
        def process(self, item: MediaItem) -> OutputArtifacts:
            if item.path == bad_media:
                raise MediaPreparationError("no audio")
            return artifact

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(tmp_path)),),
        output_dir=tmp_path / "out",
    )

    result = TranscriptionService().run(job)

    assert result.ok is False
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.outputs == (artifact,)
    assert result.errors[0].source == str(bad_media)


def test_transcription_service_emits_write_events_for_url_source(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "remote-audio.m4a"
    audio.write_bytes(b"audio")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.txt",))

    class FakeDownload:
        path = audio
        cleanup_dir = tmp_path / "download"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str):
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem) -> OutputArtifacts:
            assert item.path == audio
            return artifact

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/video"),),
        output_dir=tmp_path / "out",
    )
    events = []

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    assert result.outputs == (artifact,)
    assert "write" in [event.stage for event in events]


def test_transcription_service_passes_url_network_options_to_downloader(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "remote-audio.m4a"
    audio.write_bytes(b"audio")
    captured: dict = {}

    class FakeDownload:
        path = audio
        cleanup_dir = tmp_path / "download"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def download_audio(self, url: str):
            captured["url"] = url
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem) -> OutputArtifacts:
            return OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.txt",))

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    cookies = tmp_path / "cookies.txt"
    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/watch", keep_media=True),),
        output_dir=tmp_path / "out",
        network_family="ipv6",
        cookies_path=cookies,
        proxy="http://127.0.0.1:7890",
        max_download_mb=321,
        max_duration_seconds=45,
        download_timeout_seconds=12,
    )

    result = TranscriptionService().run(job)

    assert result.ok is True
    assert captured["url"] == "https://example.com/watch"
    assert captured["network_family"] == "ipv6"
    assert captured["cookies_path"] == cookies
    assert captured["proxy"] == "http://127.0.0.1:7890"
    assert captured["max_bytes"] == 321 * 1024 * 1024
    assert captured["max_duration_seconds"] == 45
    assert captured["timeout_seconds"] == 12
