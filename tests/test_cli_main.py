from pathlib import Path
import io
from contextlib import redirect_stdout

from flowscribe.cli.args import parse_args
from flowscribe.cli.main import (
    _cli_progress_line,
    _job_from_transcribe_options,
    _job_from_url_options,
    main,
)
from flowscribe.tasks.models import ProgressEvent
from flowscribe.media.inspector import LocalMediaInspection
from flowscribe.input.url_inspector import UrlInspection


def test_parse_transcribe_args_supports_progressive_flags(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(
        [
            "transcribe",
            str(media),
            "--progressive",
            "--chunk-seconds",
            "40",
            "--chunk-overlap-seconds",
            "5",
            "--resume",
            "--max-workers",
            "2",
        ]
    )

    assert options.progressive_mode == "enabled"
    assert options.progressive_chunk_seconds == 40.0
    assert options.progressive_chunk_overlap_seconds == 5.0
    assert options.progressive_resume is True
    assert options.progressive_max_workers == 2


def test_parse_transcribe_args_supports_native_provider(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    model = tmp_path / "ggml-base.en.bin"
    media.write_bytes(b"media")
    model.write_bytes(b"model")

    options = parse_args(
        [
            "transcribe",
            str(media),
            "--provider",
            "native-engine",
            "--model",
            str(model),
        ]
    )
    job = _job_from_transcribe_options(options)

    assert options.provider_name == "native-engine"
    assert job.provider_name == "native-engine"
    assert job.model_name == str(model)


def test_parse_url_args_supports_native_provider(tmp_path: Path) -> None:
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"model")

    options = parse_args(
        [
            "url",
            "https://example.com/watch",
            "--provider",
            "native-engine",
            "--model",
            str(model),
            "--no-progressive",
        ]
    )
    job = _job_from_url_options(options)

    assert options.provider_name == "native-engine"
    assert job.provider_name == "native-engine"


def test_job_from_transcribe_options_auto_enables_progressive_for_long_single_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(["transcribe", str(media)])

    class FakeInspector:
        def __init__(self, *, timeout_seconds: int = 30) -> None:
            self.timeout_seconds = timeout_seconds

        def inspect(self, path: Path) -> LocalMediaInspection:
            return LocalMediaInspection(
                source=path,
                exists=True,
                duration_seconds=25 * 60,
                has_audio=True,
                has_video=True,
                audio_streams=1,
                video_streams=1,
                format_name="mp4",
                size_bytes=1024,
            )

    monkeypatch.setattr("flowscribe.cli.main.LocalMediaInspector", FakeInspector)

    job = _job_from_transcribe_options(options)

    assert job.progressive_enabled is True
    assert job.progressive_resume is False


def test_job_from_transcribe_options_keeps_classic_mode_for_multi_input_batch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    options = parse_args(["transcribe", str(first), str(second)])

    class FakeInspector:
        def __init__(self, *, timeout_seconds: int = 30) -> None:
            raise AssertionError("batch auto mode should not inspect media duration")

    monkeypatch.setattr("flowscribe.cli.main.LocalMediaInspector", FakeInspector)

    job = _job_from_transcribe_options(options)

    assert job.progressive_enabled is False


def test_job_from_url_options_auto_enables_progressive_for_long_media(monkeypatch) -> None:
    options = parse_args(["url", "https://example.com/watch"])

    class FakeUrlInspector:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def inspect(self, url: str) -> UrlInspection:
            return UrlInspection(
                source=url,
                kind="video-page-url",
                title="demo",
                duration_seconds=30 * 60,
                has_audio_only=True,
                has_combined_media=True,
                selected_strategy="download audio-only stream",
                selected_format=None,
                format_count=1,
            )

    monkeypatch.setattr("flowscribe.cli.main.UrlInspector", FakeUrlInspector)

    job = _job_from_url_options(options)

    assert job.progressive_enabled is True


def test_cli_progress_line_includes_chunk_metrics() -> None:
    event = ProgressEvent(
        stage="transcribe",
        message="Processed chunk 2/4 for sample.mp4.",
        processed_duration_seconds=60.0,
        total_duration_seconds=180.0,
        eta_seconds=30.0,
        realtime_factor=2.5,
        chunk_index=2,
        chunk_count=4,
        resumed=True,
    )

    line = _cli_progress_line(event)

    assert "Progress 00:01:00.000 / 00:03:00.000" in line
    assert "Chunk 2/4" in line
    assert "Speed 2.5x" in line
    assert "ETA 00:00:30.000" in line
    assert "resumed" in line


def test_models_command_mentions_native_engine(monkeypatch, tmp_path: Path) -> None:
    buffer = io.StringIO()
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    sample_model = model_dir / "ggml-base.en.bin"
    sample_model.write_bytes(b"model")
    monkeypatch.chdir(tmp_path)

    with redirect_stdout(buffer):
        exit_code = main(["models"])

    output = buffer.getvalue()
    assert exit_code == 0
    assert "native-engine requires a local whisper.cpp ggml .bin model path" in output
    assert "ggml-base.en.bin" in output
