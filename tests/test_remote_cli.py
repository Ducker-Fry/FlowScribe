from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from threading import Thread
from time import sleep

from flowscribe.cli.args import parse_args
from flowscribe.cli.main import main
from flowscribe.core.models import OutputArtifacts
from flowscribe.execution.backends import RemoteExecutionBackend
from flowscribe.server import BookmarkletServer
from flowscribe.tasks.models import SourceSpec, TranscriptionJob, TranscriptionResult


def test_parse_transcribe_args_supports_remote_execution(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")

    options = parse_args(
        [
            "transcribe",
            str(media),
            "--execution",
            "remote",
            "--server",
            "demo",
            "--remote-token",
            "secret",
            "--remote-poll-seconds",
            "2.5",
            "--no-download-artifacts",
        ]
    )

    assert options.execution_mode == "remote"
    assert options.server_target == "demo"
    assert options.remote_token == "secret"
    assert options.remote_poll_seconds == 2.5
    assert options.download_artifacts is False


def test_parse_url_args_supports_remote_execution() -> None:
    options = parse_args(
        [
            "url",
            "https://example.com/watch",
            "--execution",
            "remote",
            "--server",
            "http://127.0.0.1:8765",
            "--download-artifacts",
        ]
    )

    assert options.execution_mode == "remote"
    assert options.server_target == "http://127.0.0.1:8765"
    assert options.download_artifacts is True


def test_remote_server_profile_management_round_trip(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(config_dir))

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "remote",
                "--json",
                "add-server",
                "demo",
                "--url",
                "http://127.0.0.1:8765",
                "--token",
                "secret",
            ]
        )

    assert exit_code == 0
    saved = json.loads(stdout.getvalue())
    assert saved["profile"]["name"] == "demo"

    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        exit_code = main(["remote", "--json", "list-servers"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload[0]["name"] == "demo"

    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        exit_code = main(["remote", "--json", "remove-server", "demo"])
    assert exit_code == 0
    assert json.loads(stdout.getvalue())["ok"] is True


def test_remote_url_cli_downloads_artifact(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "client-outputs"
    server_output_dir = tmp_path / "server-outputs"
    queue_store = tmp_path / "queue.json"
    server = BookmarkletServer(queue_store, host="127.0.0.1", port=18768)

    class FakeService:
        def run(self, job, progress=None, should_cancel=None):
            server_output_dir.mkdir(parents=True, exist_ok=True)
            json_path = server_output_dir / "remote-url.json"
            json_path.write_text('{"ok": true}', encoding="utf-8")
            if progress is not None:
                from flowscribe.tasks.models import ProgressEvent

                progress(
                    ProgressEvent(
                        stage="transcribe",
                        message="Remote URL transcription complete.",
                        task_id=job.to_task_specs()[0].task_id,
                    )
                )
            return TranscriptionResult(
                job=job,
                task_specs=job.to_task_specs(),
                outputs=(
                    OutputArtifacts(
                        paths=(json_path,),
                        source_kind="url",
                        source_value=job.sources[0].value,
                        transcription_strategy="audio-transcription",
                    ),
                ),
            )

    monkeypatch.setattr("flowscribe.server.agent_api.TranscriptionService", lambda: FakeService())

    thread = Thread(target=server.start, daemon=True)
    thread.start()
    sleep(0.5)
    try:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "url",
                    "https://example.com/watch",
                    "--execution",
                    "remote",
                    "--server",
                    "http://127.0.0.1:18768",
                    "--json",
                    "--non-interactive",
                    "-o",
                    str(output_dir),
                ]
            )
        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        json_path = Path(payload["outputs"][0]["json_path"])
        assert json_path.is_file()
        assert json_path.parent == output_dir
        assert json_path != server_output_dir / "remote-url.json"
    finally:
        server.stop()


def test_remote_transcribe_backend_uploads_local_media(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"sample-media")
    output_dir = tmp_path / "client-outputs"
    server_output_dir = tmp_path / "server-outputs"
    server_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = server_output_dir / "remote-local.json"
    json_path.write_text('{"uploaded": true}', encoding="utf-8")
    uploaded_path = tmp_path / "remote-blobs" / "upload.mp4"
    uploaded_path.parent.mkdir(parents=True, exist_ok=True)

    class FakeClient:
        def __init__(self):
            self.uploaded = False

        def upload_file(self, path: Path):
            uploaded_path.write_bytes(path.read_bytes())
            self.uploaded = True
            return {"blob_id": "blob-1", "filename": path.name, "size_bytes": path.stat().st_size}

        def submit_task(self, payload: dict):
            assert payload["source"]["kind"] == "remote_blob"
            assert payload["source"]["locator"] == str(media)
            return {"task_id": "remote-local-task", "status": "accepted"}

        def get_task_events(self, task_id: str):
            return []

        def get_task_status(self, task_id: str):
            return {"task_id": task_id, "status": "completed"}

        def get_task_result(self, task_id: str):
            return {
                "ok": True,
                "canceled": False,
                "succeeded": 1,
                "failed": 0,
                "elapsed_seconds": 1.0,
                "tasks": [],
                "outputs": [
                    {
                        "paths": [str(json_path)],
                        "json_path": str(json_path),
                        "media_path": None,
                        "media_kind": None,
                        "requested_media_kind": None,
                        "source_kind": "local",
                        "source_value": str(uploaded_path),
                        "source_locator": str(media),
                        "original_filename": media.name,
                        "transcription_strategy": None,
                        "subtitle_language": None,
                        "artifacts": [
                            {
                                "artifact_id": "artifact-1",
                                "filename": "remote-local.json",
                                "format": "json",
                                "download_path": "/v1/artifacts/artifact-1",
                                "size_bytes": json_path.stat().st_size,
                                "path": str(json_path),
                            }
                        ],
                    }
                ],
                "errors": [],
            }

        def download_artifact(self, artifact_id: str, destination: Path):
            destination.write_bytes(json_path.read_bytes())
            return destination

        def sleep(self, seconds: float):
            return None

    backend = RemoteExecutionBackend(FakeClient(), poll_seconds=0.1, download_artifacts=True)
    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(media)),),
        output_dir=output_dir,
        output_formats=("json",),
    )

    result = backend.run(job)

    assert result.ok is True
    assert result.outputs[0].json_path is not None
    assert result.outputs[0].json_path.is_file()
    assert result.outputs[0].json_path.parent == output_dir
    assert result.outputs[0].source_kind == "local"
    assert result.outputs[0].source_value == str(media)
    assert result.outputs[0].source_locator == str(media)
    assert result.outputs[0].original_filename == "sample.mp4"


def test_remote_transcribe_cli_json_includes_local_source_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"sample-media")
    output_dir = tmp_path / "client-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "sample.json"
    json_path.write_text("{}", encoding="utf-8")

    class FakeBackend:
        def run(self, job, progress=None, should_cancel=None):
            return TranscriptionResult(
                job=job,
                task_specs=job.to_task_specs(),
                outputs=(
                    OutputArtifacts(
                        paths=(json_path,),
                        source_kind="local",
                        source_value=str(media),
                        source_locator=str(media),
                        original_filename=media.name,
                    ),
                ),
            )

    monkeypatch.setattr("flowscribe.cli.main._build_execution_backend", lambda options: FakeBackend())

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "transcribe",
                str(media),
                "--execution",
                "remote",
                "--server",
                "local-test",
                "--json",
                "--non-interactive",
                "-o",
                str(output_dir),
            ]
        )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["outputs"][0]["source_kind"] == "local"
    assert payload["outputs"][0]["source_value"] == str(media)
    assert payload["outputs"][0]["source_locator"] == str(media)
    assert payload["outputs"][0]["original_filename"] == "sample.mp4"
    assert payload["outputs"][0]["json_path"] == str(json_path)
