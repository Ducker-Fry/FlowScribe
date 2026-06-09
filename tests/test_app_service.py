from pathlib import Path

from flowscribe.tasks.models import SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import MediaPreparationError, TranscriptionError
from flowscribe.core.models import (
    ChunkTranscriptionResult,
    MediaDurationInfo,
    MediaItem,
    OutputArtifacts,
    ProgressiveTranscriptionState,
    ProgressiveTranscriptionUpdate,
    Transcript,
    TranscriptSegment,
    TranscriptionChunk,
    TranscriptionChunkPlan,
)
from flowscribe.tasks.models import CapabilityResult


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
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
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
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
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
        saved_media_path = None
        saved_media_kind = "audio"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
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
    assert result.outputs[0].paths == artifact.paths
    assert result.outputs[0].source_kind == "url"
    assert result.outputs[0].source_value == "https://example.com/video"
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
        saved_media_path = None
        saved_media_kind = "audio"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            captured["url"] = url
            captured["saved_media_kind"] = saved_media_kind
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
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
    assert captured["saved_media_kind"] == "audio"
    assert captured["network_family"] == "ipv6"
    assert captured["cookies_path"] == cookies
    assert captured["proxy"] == "http://127.0.0.1:7890"
    assert captured["max_bytes"] == 321 * 1024 * 1024
    assert captured["max_duration_seconds"] == 45
    assert captured["timeout_seconds"] == 12


def test_transcription_service_preserves_url_media_in_custom_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "remote-audio.m4a"
    audio.write_bytes(b"audio")
    saved_video = tmp_path / "remote-media.mp4"
    saved_video.write_bytes(b"video")
    cleanup_dir = tmp_path / "download"
    cleanup_dir.mkdir()
    moved_audio = cleanup_dir / audio.name
    moved_audio.write_bytes(b"audio")
    moved_video = cleanup_dir / saved_video.name
    moved_video.write_bytes(b"video")

    class FakeDownload:
        def __init__(self) -> None:
            self.path = moved_audio
            self.cleanup_dir = cleanup_dir
            self.saved_media_path = moved_video
            self.saved_media_kind = "video"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            assert saved_media_kind == "video"
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            return OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.json",))

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    media_dir = tmp_path / "saved-media"
    job = TranscriptionJob(
        sources=(
            SourceSpec(
                kind="url",
                value="https://example.com/watch",
                keep_media=True,
                url_media_kind="video",
                media_output_dir=media_dir,
                auto_bind_media=True,
            ),
        ),
        output_dir=tmp_path / "out",
    )

    result = TranscriptionService().run(job)

    assert result.ok is True
    preserved = result.outputs[0].media_path
    assert preserved is not None
    assert preserved.is_file()
    assert preserved.parent.parent == media_dir.resolve()
    assert preserved.name == "remote-media.mp4"
    assert result.outputs[0].auto_bind_media is True
    assert result.outputs[0].media_kind == "video"
    assert result.outputs[0].requested_media_kind == "video"
    assert result.outputs[0].media_fallback is False
    assert not cleanup_dir.exists()


def test_transcription_service_marks_url_media_fallback_when_video_copy_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cleanup_dir = tmp_path / "download"
    cleanup_dir.mkdir()
    moved_audio = cleanup_dir / "remote-audio.m4a"
    moved_audio.write_bytes(b"audio")

    class FakeDownload:
        def __init__(self) -> None:
            self.path = moved_audio
            self.cleanup_dir = cleanup_dir
            self.saved_media_path = moved_audio
            self.saved_media_kind = "audio"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            assert saved_media_kind == "video"
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            return OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.json",))

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(
            SourceSpec(
                kind="url",
                value="https://example.com/watch",
                keep_media=True,
                url_media_kind="video",
                media_output_dir=tmp_path / "saved-media",
            ),
        ),
        output_dir=tmp_path / "out",
    )

    result = TranscriptionService().run(job)

    assert result.ok is True
    assert result.outputs[0].media_kind == "audio"
    assert result.outputs[0].requested_media_kind == "video"
    assert result.outputs[0].media_fallback is True


def test_transcription_service_returns_canceled_result_when_cancel_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            return artifact

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
    )
    events = []
    cancel_flag = {"requested": False}

    def progress(event) -> None:
        events.append(event)
        if event.stage == "discover" and event.source == str(media):
            cancel_flag["requested"] = True

    result = TranscriptionService().run(
        job,
        progress=progress,
        should_cancel=lambda: cancel_flag["requested"],
    )

    assert result.canceled is True
    assert result.failed == 0
    assert result.succeeded == 0
    assert events[-1].stage == "canceled"


def test_transcription_service_emits_progressive_chunk_updates(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "sample.txt",))

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    class FakeProgressivePipeline:
        def process_progressive(
            self,
            item: MediaItem,
            *,
            chunk_duration_seconds: float,
            chunk_overlap_seconds: float,
            resume: bool,
            keep_progressive_cache: bool,
            max_workers: int,
            plan_callback,
            update_callback,
            should_cancel=None,
        ):
            duration_info = MediaDurationInfo(
                source=item,
                prepared_audio_path=tmp_path / "prepared.wav",
                sample_rate=16000,
                duration_seconds=120.0,
            )
            chunk_plan = TranscriptionChunkPlan(
                duration_info=duration_info,
                chunks=(
                    TranscriptionChunk(
                        index=1,
                        start_seconds=0.0,
                        end_seconds=30.0,
                        overlap_seconds=3.0,
                    ),
                    TranscriptionChunk(
                        index=2,
                        start_seconds=27.0,
                        end_seconds=60.0,
                        overlap_seconds=3.0,
                    ),
                ),
                chunk_duration_seconds=30.0,
                chunk_overlap_seconds=3.0,
            )
            plan_callback(duration_info, chunk_plan)
            partial_transcript = Transcript(
                source=item,
                segments=(TranscriptSegment(text="hello", start_seconds=0.0, end_seconds=5.0),),
            )
            partial_state = ProgressiveTranscriptionState(
                source=item,
                duration_info=duration_info,
                chunk_plan=chunk_plan,
                chunk_results=(
                    ChunkTranscriptionResult(
                        chunk=chunk_plan.chunks[0],
                        status="done",
                        transcript=partial_transcript,
                    ),
                ),
                transcript=partial_transcript,
                processed_duration_seconds=30.0,
            )
            update_callback(
                ProgressiveTranscriptionUpdate(
                    state=partial_state,
                    chunk_result=partial_state.chunk_results[0],
                    appended_segments=partial_transcript.segments,
                    resumed=False,
                )
            )
            return artifact, partial_state

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr(
        "flowscribe.app.service._build_pipeline",
        lambda job, settings: FakeProgressivePipeline(),
    )

    events = []
    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
        progressive_enabled=True,
    )

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    prepare_event = next(event for event in events if event.stage == "prepare")
    transcribe_event = next(
        event
        for event in events
        if event.stage == "transcribe" and event.processed_duration_seconds is not None
    )
    assert prepare_event.total_duration_seconds == 120.0
    assert prepare_event.chunk_count == 2
    assert transcribe_event.processed_duration_seconds == 30.0
    assert transcribe_event.total_duration_seconds == 120.0
    assert transcribe_event.chunk_index == 1
    assert transcribe_event.chunk_count == 2
    assert transcribe_event.segments[0].text == "hello"


def test_transcription_service_does_not_use_python_progressive_for_native_provider(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"model")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "sample.txt",))
    captured = {"classic": False}

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            captured["classic"] = True
            return artifact

        def process_progressive(self, *args, **kwargs):
            raise AssertionError("native provider should not use Python progressive executor")

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
        provider_name="native-engine",
        model_name=str(model),
        progressive_enabled=True,
    )

    result = TranscriptionService().run(job)

    assert result.ok is True
    assert captured["classic"] is True


def test_transcription_service_uses_python_progressive_for_paraformer_provider(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "sample.txt",))
    captured = {"progressive": False}

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            raise AssertionError("paraformer provider should use Python progressive executor")

        def process_progressive(
            self,
            item: MediaItem,
            *,
            chunk_duration_seconds: float,
            chunk_overlap_seconds: float,
            resume: bool,
            keep_progressive_cache: bool,
            max_workers: int,
            plan_callback,
            update_callback,
            should_cancel=None,
        ):
            captured["progressive"] = True
            duration_info = MediaDurationInfo(
                source=item,
                prepared_audio_path=tmp_path / "prepared.wav",
                sample_rate=16000,
                duration_seconds=60.0,
            )
            chunk_plan = TranscriptionChunkPlan(
                duration_info=duration_info,
                chunks=(
                    TranscriptionChunk(
                        index=1,
                        start_seconds=0.0,
                        end_seconds=30.0,
                        overlap_seconds=3.0,
                    ),
                ),
                chunk_duration_seconds=30.0,
                chunk_overlap_seconds=3.0,
            )
            plan_callback(duration_info, chunk_plan)
            transcript = Transcript(
                source=item,
                segments=(TranscriptSegment(text="hello", start_seconds=0.0, end_seconds=5.0),),
            )
            state = ProgressiveTranscriptionState(
                source=item,
                duration_info=duration_info,
                chunk_plan=chunk_plan,
                chunk_results=(
                    ChunkTranscriptionResult(
                        chunk=chunk_plan.chunks[0],
                        status="done",
                        transcript=transcript,
                    ),
                ),
                transcript=transcript,
                processed_duration_seconds=30.0,
            )
            update_callback(
                ProgressiveTranscriptionUpdate(
                    state=state,
                    chunk_result=state.chunk_results[0],
                    appended_segments=transcript.segments,
                    resumed=False,
                )
            )
            return artifact, state

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
        provider_name="paraformer",
        progressive_enabled=True,
    )

    events = []
    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    assert captured["progressive"] is True
    assert any(
        event.stage == "transcribe" and event.chunk_index == 1
        for event in events
    )


def test_transcription_service_uses_more_conservative_default_overlap_for_chinese(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    captured: dict[str, float] = {}

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    class FakeProgressivePipeline:
        def process_progressive(
            self,
            item: MediaItem,
            *,
            chunk_duration_seconds: float,
            chunk_overlap_seconds: float,
            resume: bool,
            keep_progressive_cache: bool,
            max_workers: int,
            plan_callback,
            update_callback,
            should_cancel=None,
        ):
            captured["chunk_overlap_seconds"] = chunk_overlap_seconds
            return OutputArtifacts(paths=(tmp_path / "out" / "sample.txt",)), ProgressiveTranscriptionState(
                source=item,
                duration_info=MediaDurationInfo(
                    source=item,
                    prepared_audio_path=tmp_path / "prepared.wav",
                    sample_rate=16000,
                    duration_seconds=30.0,
                ),
                chunk_plan=TranscriptionChunkPlan(
                    duration_info=MediaDurationInfo(
                        source=item,
                        prepared_audio_path=tmp_path / "prepared.wav",
                        sample_rate=16000,
                        duration_seconds=30.0,
                    ),
                    chunks=(),
                    chunk_duration_seconds=30.0,
                    chunk_overlap_seconds=chunk_overlap_seconds,
                ),
                chunk_results=(),
                transcript=Transcript(source=item, segments=()),
                processed_duration_seconds=0.0,
            )

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakeProgressivePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
        language="zh",
        progressive_chunk_overlap_seconds=3.0,
    )

    TranscriptionService().run(job)

    assert captured["chunk_overlap_seconds"] == 4.0


def test_transcription_service_fails_local_source_before_pipeline_when_provider_runtime_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    captured = {"pipeline_built": False}

    class FakeLocalFileSource:
        def __init__(self, inputs, recursive: bool) -> None:
            self.inputs = inputs
            self.recursive = recursive

        def discover(self):
            return [MediaItem(path=media)]

    def fail_validate(job, settings) -> None:
        raise TranscriptionError("FunASR is not installed. Run: python -m pip install funasr modelscope")

    def fake_build_pipeline(job, settings):
        captured["pipeline_built"] = True
        raise AssertionError("pipeline should not be built when provider validation fails")

    monkeypatch.setattr("flowscribe.app.service.LocalFileSource", FakeLocalFileSource)
    monkeypatch.setattr("flowscribe.app.service._validate_provider_runtime", fail_validate)
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", fake_build_pipeline)

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=tmp_path / "out",
        provider_name="paraformer",
    )

    result = TranscriptionService().run(job)

    assert result.ok is False
    assert result.failed == 1
    assert "FunASR is not installed" in result.errors[0].message
    assert captured["pipeline_built"] is False


def test_transcription_service_validates_provider_runtime_only_after_url_subtitle_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "remote-subtitle.json",))
    captured = {"validated": False}

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            raise AssertionError("audio downloader should not run when subtitles succeed")

    def fake_run_subtitle_capability(self, task_spec, progress, should_cancel, *, current: int, total: int):
        return CapabilityResult(
            task_id=task_spec.task_id,
            capability="subtitle",
            supported=True,
            status="success",
            artifacts=(artifact,),
        )

    def fail_validate(job, settings) -> None:
        captured["validated"] = True
        raise AssertionError("provider runtime should not be validated when subtitles already succeeded")

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr(
        "flowscribe.app.service.TranscriptionService._run_subtitle_capability",
        fake_run_subtitle_capability,
    )
    monkeypatch.setattr("flowscribe.app.service._validate_provider_runtime", fail_validate)

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/video"),),
        output_dir=tmp_path / "out",
        provider_name="paraformer",
        requested_capabilities=("subtitle", "transcribe"),
    )

    result = TranscriptionService().run(job)

    assert result.ok is True
    assert result.outputs == (artifact,)
    assert captured["validated"] is False


def test_transcription_service_fails_url_source_before_download_when_provider_runtime_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured = {"validated": False, "downloaded": False}

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            captured["downloaded"] = True

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            raise AssertionError("download should not start when provider validation fails")

    def fake_run_subtitle_capability(self, task_spec, progress, should_cancel, *, current: int, total: int):
        return CapabilityResult(
            task_id=task_spec.task_id,
            capability="subtitle",
            supported=False,
            status="unsupported",
        )

    def fail_validate(job, settings) -> None:
        captured["validated"] = True
        raise TranscriptionError("FunASR is not installed. Run: python -m pip install funasr modelscope")

    monkeypatch.setattr("flowscribe.app.service.UrlAudioDownloader", FakeDownloader)
    monkeypatch.setattr(
        "flowscribe.app.service.TranscriptionService._run_subtitle_capability",
        fake_run_subtitle_capability,
    )
    monkeypatch.setattr("flowscribe.app.service._validate_provider_runtime", fail_validate)

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/video"),),
        output_dir=tmp_path / "out",
        provider_name="paraformer",
        requested_capabilities=("subtitle", "transcribe"),
    )

    result = TranscriptionService().run(job)

    assert result.ok is False
    assert result.failed == 1
    assert "FunASR is not installed" in result.errors[0].message
    assert captured["validated"] is True
    assert captured["downloaded"] is False


def test_transcription_service_emits_download_progress_after_url_subtitle_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "remote-audio.m4a"
    audio.write_bytes(b"audio")
    artifact = OutputArtifacts(paths=(tmp_path / "out" / "remote-audio.txt",))
    captured: dict[str, object] = {}

    class FakeDownload:
        path = audio
        cleanup_dir = tmp_path / "download"
        saved_media_path = None
        saved_media_kind = "audio"

    class FakeDownloader:
        def __init__(self, **kwargs) -> None:
            captured["progress_callback"] = kwargs.get("progress_callback")
            captured["should_cancel"] = kwargs.get("should_cancel")

        def download_audio(self, url: str, *, saved_media_kind: str = "audio", download_options=None):
            progress_callback = captured["progress_callback"]
            assert callable(progress_callback)
            progress_callback("Inspecting remote media metadata...")
            progress_callback("Downloading remote audio with yt-dlp...")
            return FakeDownload()

    class FakePipeline:
        def process(self, item: MediaItem, *, should_cancel=None) -> OutputArtifacts:
            return artifact

    def fake_run_subtitle_capability(self, task_spec, progress, should_cancel, *, current: int, total: int):
        return CapabilityResult(
            task_id=task_spec.task_id,
            capability="subtitle",
            supported=False,
            status="unsupported",
        )

    monkeypatch.setattr("flowscribe.app.service.select_url_downloader_cls", lambda default_cls: FakeDownloader)
    monkeypatch.setattr(
        "flowscribe.app.service.TranscriptionService._run_subtitle_capability",
        fake_run_subtitle_capability,
    )
    monkeypatch.setattr("flowscribe.app.service._build_pipeline", lambda job, settings: FakePipeline())

    job = TranscriptionJob(
        sources=(SourceSpec(kind="url", value="https://example.com/video"),),
        output_dir=tmp_path / "out",
        requested_capabilities=("subtitle", "transcribe"),
    )
    events = []

    result = TranscriptionService().run(job, progress=events.append)

    assert result.ok is True
    messages = [event.message for event in events if event.stage in {"prepare", "download"}]
    assert "No usable native subtitles found. Falling back to audio transcription." in messages
    assert "Inspecting remote media metadata..." in messages
    assert "Downloading remote audio with yt-dlp..." in messages
