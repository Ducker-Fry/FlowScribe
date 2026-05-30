from __future__ import annotations

from pathlib import Path

import pytest

from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.engine.protocol import MessageKind
import flowscribe.providers.transcribe.native_engine as native_engine
from flowscribe.providers.transcribe.native_engine import NativeEngineTranscriber


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if not self.terminated and not self.killed else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


class FakeClient:
    def __init__(self, messages=None) -> None:
        self.messages = list(messages or [])
        self.connected = False
        self.closed = False
        self.loaded = None
        self.submitted = None
        self.cancelled = None

    def connect(self, retry=3, delay=1.0) -> bool:
        self.connected = True
        return True

    def send_hello(self):
        return {"ok": True, "engine_version": "test", "protocol_version": 1}

    def load_model(self, model_path: str, model_name: str, use_gpu: bool = False):
        self.loaded = {
            "model_path": model_path,
            "model_name": model_name,
            "use_gpu": use_gpu,
        }
        return {"ok": True, "model_load_time_ms": 1}

    def submit_job(self, job_id: str, audio_path: str, **kwargs):
        self.submitted = {"job_id": job_id, "audio_path": audio_path, **kwargs}
        patched_messages = []
        for kind, payload in self.messages:
            if payload.get("job_id") in {None, "", "__job_id__"}:
                payload = {**payload, "job_id": job_id}
            patched_messages.append((kind, payload))
        self.messages = patched_messages
        return {"ok": True, "job_id": job_id}

    def recv_message(self, *, quiet_timeout: bool = False):
        if not self.messages:
            return None
        return self.messages.pop(0)

    def cancel_job(self, job_id: str):
        self.cancelled = job_id
        return {"ok": False, "job_id": job_id, "error": "running job cancellation is not supported yet"}

    def close(self) -> None:
        self.closed = True


def _prepared_audio(tmp_path: Path) -> PreparedAudio:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    return PreparedAudio(source=MediaItem(path=audio), path=audio, sample_rate=16000)


def _transcriber(tmp_path: Path, client: FakeClient, process: FakeProcess) -> NativeEngineTranscriber:
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"model")
    engine = tmp_path / "flowscribe-engine.exe"
    engine.write_bytes(b"exe")
    return NativeEngineTranscriber(
        model_name=str(model),
        language="en",
        beam_size=3,
        vad_filter=True,
        initial_prompt="terms",
        progressive_enabled=True,
        progressive_chunk_seconds=42.0,
        progressive_chunk_overlap_seconds=4.0,
        progressive_max_workers=0,
        threads=8,
        engine_exe=engine,
        client_factory=lambda: client,
        process_factory=lambda *args, **kwargs: process,
    )


def _model_and_engine(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"model")
    engine = tmp_path / "flowscribe-engine.exe"
    engine.write_bytes(b"exe")
    return model, engine


def test_native_transcriber_maps_result_and_uses_protocol_payload(tmp_path: Path) -> None:
    client = FakeClient(
        [
            (
                MessageKind.JobResult,
                {
                    "job_id": "__job_id__",
                    "segments": [],
                },
            )
        ]
    )
    process = FakeProcess()
    transcriber = _transcriber(tmp_path, client, process)

    client.messages = [
        (
            MessageKind.JobResult,
            {
                "job_id": "__job_id__",
                "segments": [
                    {
                        "id": 1,
                        "start": 0.5,
                        "end": 2.0,
                        "text": " hello world ",
                        "words": [{"word": "hello", "start": 0.5, "end": 1.0}],
                    }
                ],
                "chunked_enabled": True,
                "chunk_count": 2,
                "runtime_count": 2,
                "effective_parallel_chunks": 2,
                "chunk_threads": 8,
                "chunk_metrics": [
                    {
                        "index": 1,
                        "start": 0.0,
                        "end": 120.0,
                        "runtime_slot": 0,
                        "acquire_wait_seconds": 0.01,
                        "elapsed_seconds": 2.5,
                        "threads": 8,
                    }
                ],
            },
        )
    ]

    transcript = transcriber.transcribe(_prepared_audio(tmp_path))

    assert client.loaded is not None
    assert client.loaded["model_name"] == "ggml-base.en"
    assert client.submitted is not None
    assert set(client.submitted["progressive"]) == {
        "enabled",
        "chunk_seconds",
        "overlap_seconds",
        "max_workers",
    }
    assert client.submitted["progressive"]["chunk_seconds"] == 42.0
    assert client.submitted["progressive"]["max_workers"] == 0
    assert client.submitted["threads"] == 8
    assert transcript.options is not None
    assert transcript.options.provider_name == "native-engine"
    assert transcript.segments[0].text == "hello world"
    assert transcript.segments[0].start_seconds == 0.5
    assert transcript.segments[0].raw_words[0].text == "hello"
    assert transcript.metadata["chunk_threads"] == 8
    assert transcript.metadata["chunk_metrics"] == (
        {
            "index": 1,
            "start": 0.0,
            "end": 120.0,
            "runtime_slot": 0,
            "acquire_wait_seconds": 0.01,
            "elapsed_seconds": 2.5,
            "threads": 8,
        },
    )
    assert client.closed
    assert process.terminated


def test_native_transcriber_emits_chunk_progress_events(tmp_path: Path) -> None:
    client = FakeClient(
        [
            (
                MessageKind.JobEvent,
                {
                    "job_id": "__job_id__",
                    "status": "chunks_planned",
                    "chunk_count": 3,
                    "total_seconds": 90.0,
                },
            ),
            (
                MessageKind.JobEvent,
                {
                    "job_id": "__job_id__",
                    "status": "chunk_completed",
                    "chunk_index": 1,
                    "chunk_count": 3,
                    "completed_chunks": 1,
                    "current_seconds": 30.0,
                    "total_seconds": 90.0,
                    "segments": [
                        {
                            "id": 1,
                            "start": 0.0,
                            "end": 2.0,
                            "text": " hello from chunk ",
                        }
                    ],
                },
            ),
            (MessageKind.JobResult, {"job_id": "__job_id__", "segments": []}),
        ]
    )
    transcriber = _transcriber(tmp_path, client, FakeProcess())
    events = []

    transcriber.transcribe(_prepared_audio(tmp_path), progress=events.append)

    assert "Loading native model: ggml-base.en.bin." in [event.message for event in events]
    chunk_events = [
        event
        for event in events
        if event.message.startswith("Progressive transcription ready")
        or event.message.startswith("Processed chunk")
    ]
    assert [event.message for event in chunk_events] == [
        "Progressive transcription ready for audio.wav: 01:30 across 3 chunk(s).",
        "Processed chunk 1/3 for audio.wav: 00:30 / 01:30.",
    ]
    assert chunk_events[0].stage == "prepare"
    assert chunk_events[0].chunk_count == 3
    assert chunk_events[1].stage == "transcribe"
    assert chunk_events[1].chunk_index == 1
    assert chunk_events[1].completed_chunks == 1
    assert chunk_events[1].processed_duration_seconds == 30.0
    assert chunk_events[1].total_duration_seconds == 90.0
    assert chunk_events[1].segments[0].text == "hello from chunk"
    assert chunk_events[1].segments[0].start_seconds == 0.0
    assert chunk_events[1].segments[0].end_seconds == 2.0


def test_native_transcriber_submits_absolute_audio_path(tmp_path: Path) -> None:
    client = FakeClient([(MessageKind.JobResult, {"job_id": "__job_id__", "segments": []})])
    transcriber = _transcriber(tmp_path, client, FakeProcess())
    relative_audio = Path("relative-benchmark-audio.wav")
    absolute_audio = relative_audio.resolve()
    absolute_audio.write_bytes(b"audio")

    try:
        transcriber.transcribe(PreparedAudio(source=MediaItem(path=relative_audio), path=relative_audio, sample_rate=16000))
    finally:
        absolute_audio.unlink(missing_ok=True)

    assert client.submitted is not None
    assert Path(client.submitted["audio_path"]).is_absolute()


def test_native_transcriber_uses_unique_pipe_for_owned_engine(tmp_path: Path) -> None:
    model, engine = _model_and_engine(tmp_path)
    process = FakeProcess()
    client = FakeClient([(MessageKind.JobResult, {"job_id": "__job_id__", "segments": []})])
    started = {}
    created = {}

    def client_factory():
        created["client"] = True
        return client

    def process_factory(*args, **kwargs):
        started.update(kwargs)
        return process

    transcriber = NativeEngineTranscriber(
        model_name=str(model),
        engine_exe=engine,
        client_factory=client_factory,
        process_factory=process_factory,
    )

    transcriber.transcribe(_prepared_audio(tmp_path))

    assert created["client"] is True
    assert started["env"]["FLOWSCRIBE_ENGINE_PIPE_NAME"].startswith(
        r"\\.\pipe\flowscribe-engine-v1-"
    )
    assert started["env"]["FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT"] == "1"


def test_native_transcriber_preserves_explicit_runtime_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT", "2")
    model, engine = _model_and_engine(tmp_path)
    process = FakeProcess()
    client = FakeClient([(MessageKind.JobResult, {"job_id": "__job_id__", "segments": []})])
    started = {}

    transcriber = NativeEngineTranscriber(
        model_name=str(model),
        engine_exe=engine,
        client_factory=lambda: client,
        process_factory=lambda *args, **kwargs: started.update(kwargs) or process,
    )

    transcriber.transcribe(_prepared_audio(tmp_path))

    assert started["env"]["FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT"] == "2"


def test_native_transcriber_rejects_non_file_model_name(tmp_path: Path) -> None:
    transcriber = NativeEngineTranscriber(
        model_name="small",
        engine_exe=tmp_path / "flowscribe-engine.exe",
        client_factory=lambda: FakeClient(),
        process_factory=lambda *args, **kwargs: FakeProcess(),
    )

    with pytest.raises(TranscriptionError, match="requires --model"):
        transcriber.transcribe(_prepared_audio(tmp_path))


def test_native_transcriber_converts_job_error(tmp_path: Path) -> None:
    client = FakeClient(
        [
            (
                MessageKind.JobError,
                {"job_id": "native-error", "code": "job_failed", "message": "bad audio"},
            )
        ]
    )

    original_submit = client.submit_job

    def submit_job(job_id: str, audio_path: str, **kwargs):
        result = original_submit(job_id, audio_path, **kwargs)
        client.messages[0] = (
            MessageKind.JobError,
            {"job_id": job_id, "code": "job_failed", "message": "bad audio"},
        )
        return result

    client.submit_job = submit_job
    transcriber = _transcriber(tmp_path, client, FakeProcess())

    with pytest.raises(TranscriptionError, match="job_failed"):
        transcriber.transcribe(_prepared_audio(tmp_path))


def test_native_transcriber_cancels_running_job(tmp_path: Path) -> None:
    client = FakeClient([])
    transcriber = _transcriber(tmp_path, client, FakeProcess())
    calls = 0

    def should_cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    with pytest.raises(CancellationError):
        transcriber.transcribe(_prepared_audio(tmp_path), should_cancel=should_cancel)

    assert client.cancelled is not None


def test_native_transcriber_reports_engine_exit_before_result(tmp_path: Path) -> None:
    client = FakeClient([])
    process = FakeProcess()

    def exited_poll():
        return 1

    process.poll = exited_poll
    transcriber = _transcriber(tmp_path, client, process)

    with pytest.raises(TranscriptionError, match="exited before job completed"):
        transcriber.transcribe(_prepared_audio(tmp_path))


def test_resolve_engine_exe_prefers_release_over_debug(monkeypatch, tmp_path: Path) -> None:
    release = tmp_path / "native" / "flowscribe-engine" / "build" / "Release" / "flowscribe-engine.exe"
    debug = tmp_path / "native" / "flowscribe-engine" / "build" / "Debug" / "flowscribe-engine.exe"
    release.parent.mkdir(parents=True)
    debug.parent.mkdir(parents=True)
    release.write_bytes(b"release")
    debug.write_bytes(b"debug")
    module_file = tmp_path / "src" / "flowscribe" / "transcription" / "native_engine.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(native_engine, "__file__", str(module_file))
    monkeypatch.delenv("FLOWSCRIBE_ENGINE_EXE", raising=False)

    assert native_engine.resolve_engine_exe() == release.resolve()
