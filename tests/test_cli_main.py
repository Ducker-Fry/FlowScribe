from pathlib import Path
import io
import json
from contextlib import redirect_stdout, redirect_stderr

from flowscribe.cli.args import parse_args
from flowscribe.cli.main import (
    _cli_progress_line,
    _is_address_in_use_error,
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


def test_parse_transcribe_args_supports_paraformer_provider(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(
        [
            "transcribe",
            str(media),
            "--provider",
            "paraformer",
            "--model",
            "paraformer-zh",
        ]
    )
    job = _job_from_transcribe_options(options)

    assert options.provider_name == "paraformer"
    assert job.provider_name == "paraformer"
    assert job.model_name == "paraformer-zh"


def test_zh_preset_auto_selects_paraformer_when_provider_omitted(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(["transcribe", str(media), "--preset", "zh"])
    job = _job_from_transcribe_options(options)

    assert options.provider_name is None
    assert job.provider_name == "paraformer"
    assert job.model_name == "paraformer-zh"


def test_explicit_local_whisper_keeps_zh_preset_on_whisper(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(
        ["transcribe", str(media), "--provider", "local-whisper", "--preset", "zh"]
    )
    job = _job_from_transcribe_options(options)

    assert job.provider_name == "local-whisper"
    assert job.model_name == "small"


def test_explicit_paraformer_defaults_to_paraformer_model(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(["transcribe", str(media), "--provider", "paraformer"])
    job = _job_from_transcribe_options(options)

    assert job.provider_name == "paraformer"
    assert job.model_name == "paraformer-zh"


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
    assert job.requested_capabilities == ("subtitle", "transcribe")


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


def test_cli_progress_line_shows_subtitle_messages() -> None:
    event = ProgressEvent(
        stage="write",
        message="Using native YouTube subtitles.",
        capability="subtitle",
    )

    line = _cli_progress_line(event)

    assert line == "Using native YouTube subtitles."


def test_run_url_prints_strategy_summary(monkeypatch, tmp_path: Path) -> None:
    from flowscribe.cli.main import run_url
    from flowscribe.core.models import OutputArtifacts
    from flowscribe.tasks.models import TranscriptionResult

    options = parse_args(["url", "https://www.youtube.com/watch?v=abc123", "-o", str(tmp_path)])

    class FakeService:
        def run(self, job, progress=None):
            return TranscriptionResult(
                job=job,
                outputs=(
                    OutputArtifacts(
                        paths=(tmp_path / "demo.txt",),
                        source_kind="url",
                        source_value=options.url,
                        transcription_strategy="automatic-subtitles",
                        subtitle_language="en",
                    ),
                ),
            )

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.cli.main.TranscriptionService", lambda: FakeService())

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_url(options)

    assert exit_code == 0
    assert "Strategy: used automatic YouTube captions (en)." in stdout.getvalue()


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
    assert "paraformer-zh" in output
    assert "ggml-base.en.bin" in output


def test_parse_transcribe_args_supports_agent_flags(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(
        [
            "transcribe",
            str(media),
            "--json",
            "--events",
            "jsonl",
            "--non-interactive",
            "--task-id",
            "task-1",
            "--resume-token",
            "resume-1",
            "--checkpoint-id",
            "checkpoint-1",
        ]
    )

    assert options.json_output is True
    assert options.event_stream == "jsonl"
    assert options.non_interactive is True
    assert options.task_id == "task-1"
    assert options.resume_token == "resume-1"
    assert options.checkpoint_id == "checkpoint-1"


def test_run_transcribe_json_output(monkeypatch, tmp_path: Path) -> None:
    from flowscribe.cli.main import run_transcribe
    from flowscribe.core.models import OutputArtifacts
    from flowscribe.tasks.models import TranscriptionResult

    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    json_path = tmp_path / "sample.json"
    json_path.write_text("{}", encoding="utf-8")
    options = parse_args(["transcribe", str(media), "--json", "--non-interactive", "--task-id", "task-1"])
    job = _job_from_transcribe_options(options)
    task_specs = job.to_task_specs()

    class FakeService:
        def run(self, job, progress=None):
            return TranscriptionResult(
                job=job,
                task_specs=task_specs,
                outputs=(OutputArtifacts(paths=(json_path,)),),
            )

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.cli.main.TranscriptionService", lambda: FakeService())

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_transcribe(options)

    assert exit_code == 0
    payload = __import__("json").loads(stdout.getvalue())
    assert payload["tasks"][0]["task_id"] == "task-1"
    assert payload["outputs"][0]["json_path"] == str(json_path)


def test_run_transcribe_jsonl_events(monkeypatch, tmp_path: Path) -> None:
    from flowscribe.cli.main import run_transcribe
    from flowscribe.tasks.models import TranscriptionResult

    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    options = parse_args(["transcribe", str(media), "--events", "jsonl", "--non-interactive"])

    class FakeService:
        def run(self, job, progress=None):
            progress(
                ProgressEvent(
                    stage="discover",
                    message="Received 1 source(s).",
                    task_id="task-1",
                    event_type="task.accepted",
                    timestamp="2026-06-04T00:00:00.000Z",
                    sequence=1,
                )
            )
            return TranscriptionResult(job=job, task_specs=job.to_task_specs())

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.cli.main.TranscriptionService", lambda: FakeService())

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_transcribe(options)

    assert exit_code == 0
    line = stdout.getvalue().strip()
    assert '"event_type": "task.accepted"' in line
    assert '"task_id": "task-1"' in line


def test_is_address_in_use_error_matches_windows_errno() -> None:
    exc = OSError(10048, "Only one usage of each socket address")
    exc.winerror = 10048

    assert _is_address_in_use_error(exc) is True


def test_run_serve_reports_port_conflict_for_windows_socket_error(monkeypatch, tmp_path: Path) -> None:
    from flowscribe.cli.main import run_serve

    options = parse_args(["serve", "--port", "8765", "-o", str(tmp_path / "outputs")])

    class FakeServer:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def start(self) -> None:
            exc = OSError(10048, "Only one usage of each socket address")
            exc.winerror = 10048
            raise exc

    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("flowscribe.cli.main.BookmarkletServer", FakeServer, raising=False)
    monkeypatch.setattr(
        "flowscribe.server.BookmarkletServer",
        FakeServer,
        raising=False,
    )

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_serve(options)

    assert exit_code == 1
    assert "Port 8765 is already in use" in stderr.getvalue()


def test_run_install_write_config_json(monkeypatch, tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    docs_dir = tmp_path / "docs"
    stdout = io.StringIO()
    stderr = io.StringIO()

    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "install",
                "--json",
                "write-config",
                "--scope",
                "user",
                "--models-dir",
                str(models_dir),
                "--docs-dir",
                str(docs_dir),
                "--component",
                "gui",
                "--component",
                "docs",
            ]
        )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["install_scope"] == "user"
    assert payload["installed_components"] == ["gui", "docs"]
    config_path = Path(payload["config_path"])
    assert config_path.exists()
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_payload["allow_implicit_model_download"] is False
    assert config_payload["models_dir"] == str(models_dir.resolve())
    assert config_payload["docs_dir"] == str(docs_dir.resolve())


def test_run_model_list_available_json(monkeypatch) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(["model", "--json", "list-available"])

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert any(entry["model_id"] == "small" for entry in payload)
    assert any(entry["model_id"] == "paraformer-zh" for entry in payload)
