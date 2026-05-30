"""Native whisper.cpp engine transcription provider."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flowscribe.tasks.models import ProgressEvent
from flowscribe.core.errors import CancellationError, TranscriptionError
from flowscribe.core.models import (
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)
from flowscribe.engine.pipe_client import FlowScribeEngineClient
from flowscribe.engine.protocol import MessageKind

NATIVE_ENGINE_PROVIDER_NAME = "native-engine"


class NativeEngineTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        language: str | None = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = False,
        initial_prompt: str | None = None,
        preset: str | None = None,
        word_timestamps: bool = False,
        progressive_enabled: bool = True,
        progressive_chunk_seconds: float = 30.0,
        progressive_chunk_overlap_seconds: float = 3.0,
        progressive_max_workers: int = 1,
        use_gpu: bool = False,
        threads: int | None = None,
        engine_exe: Path | None = None,
        client_factory: Callable[[], FlowScribeEngineClient] | None = None,
        process_factory: Callable[..., subprocess.Popen] | None = None,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._task = task
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._initial_prompt = initial_prompt
        self._preset = preset
        self._word_timestamps = word_timestamps
        self._progressive_enabled = progressive_enabled
        self._progressive_chunk_seconds = progressive_chunk_seconds
        self._progressive_chunk_overlap_seconds = progressive_chunk_overlap_seconds
        self._progressive_max_workers = progressive_max_workers
        self._use_gpu = use_gpu
        self._threads = threads
        self._engine_exe = engine_exe
        self._client_factory = client_factory
        self._process_factory = process_factory or subprocess.Popen

    def transcribe(
        self,
        audio: PreparedAudio,
        *,
        should_cancel: Callable[[], bool] | None = None,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> Transcript:
        should_cancel = should_cancel or (lambda: False)
        model_path = self._resolve_model_path()
        engine_exe = self._engine_exe or resolve_engine_exe()
        pipe_name = _unique_pipe_name()
        process = self._start_engine(engine_exe, pipe_name=pipe_name)
        client = (
            self._client_factory()
            if self._client_factory is not None
            else FlowScribeEngineClient(timeout=120.0, pipe_name=pipe_name)
        )
        job_id = f"native-{uuid.uuid4().hex}"

        try:
            self._emit_progress(progress, "Starting native engine.")
            self._connect(client)
            self._emit_progress(progress, "Connected to native engine.")
            self._require_ok("HelloResult", client.send_hello())
            self._emit_progress(progress, f"Loading native model: {model_path.name}.")
            self._require_ok(
                "LoadModelResult",
                client.load_model(
                    model_path=str(model_path),
                    model_name=model_path.stem,
                    use_gpu=self._use_gpu,
                ),
            )
            self._emit_progress(progress, "Native model loaded.")
            submit = self._require_ok(
                "SubmitJobResult",
                client.submit_job(
                    job_id=job_id,
                    audio_path=str(audio.path.resolve()),
                    language=self._language or "",
                    task=self._task,
                    vad_filter=self._vad_filter,
                    beam_size=self._beam_size,
                    threads=self._threads,
                    initial_prompt=self._initial_prompt or "",
                    progressive={
                        "enabled": self._progressive_enabled,
                        "chunk_seconds": self._progressive_chunk_seconds,
                        "overlap_seconds": self._progressive_chunk_overlap_seconds,
                        "max_workers": self._progressive_max_workers,
                    },
                ),
            )
            self._emit_progress(progress, "Native transcription job submitted.")
            if submit.get("job_id") not in {None, "", job_id}:
                raise TranscriptionError(
                    f"Native engine returned unexpected job_id: {submit.get('job_id')}"
                )

            result = self._wait_for_result(
                client,
                job_id,
                audio=audio,
                process=process,
                should_cancel=should_cancel,
                progress=progress,
            )
            return self._build_transcript(audio, result, model_path=model_path)
        finally:
            client.close()
            self._stop_engine(process)

    def _resolve_model_path(self) -> Path:
        path = Path(self._model_name).expanduser()
        if not path.exists() or not path.is_file():
            raise TranscriptionError(
                "Native engine provider requires --model to be a local whisper.cpp ggml "
                f".bin file path. Got: {self._model_name!r}"
            )
        if path.suffix.lower() != ".bin":
            raise TranscriptionError(
                "Native engine provider requires a whisper.cpp ggml .bin model file. "
                f"Got: {path}"
            )
        return path.resolve()

    def _start_engine(self, engine_exe: Path, *, pipe_name: str):
        env = os.environ.copy()
        env["FLOWSCRIBE_ENGINE_PIPE_NAME"] = pipe_name
        env.setdefault("FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT", "1")
        try:
            return self._process_factory(
                [str(engine_exe)],
                cwd=str(engine_exe.parent),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise TranscriptionError(f"Failed to start native engine {engine_exe}: {exc}") from exc

    @staticmethod
    def _connect(client: FlowScribeEngineClient) -> None:
        if not client.connect(retry=40, delay=0.05):
            raise TranscriptionError("Failed to connect to native engine named pipe.")

    @staticmethod
    def _require_ok(label: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        if payload is None:
            raise TranscriptionError(f"Native engine did not return {label}.")
        if not payload.get("ok", False):
            error = payload.get("error") or payload.get("message") or "unknown error"
            raise TranscriptionError(f"Native engine {label} failed: {error}")
        return payload

    def _wait_for_result(
        self,
        client: FlowScribeEngineClient,
        job_id: str,
        *,
        audio: PreparedAudio,
        process,
        should_cancel: Callable[[], bool],
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> dict[str, Any]:
        original_timeout = getattr(client, "timeout", None)
        if original_timeout is not None:
            client.timeout = 1.0
        try:
            while True:
                if should_cancel():
                    self._cancel_job(client, job_id)
                    raise CancellationError("Transcription canceled.")
                poll = getattr(process, "poll", None)
                if callable(poll) and poll() is not None:
                    raise TranscriptionError(
                        f"Native engine exited before job completed: exit_code={poll()}"
                    )

                response = client.recv_message(quiet_timeout=True)
                if response is None:
                    continue

                kind, payload = response
                if payload.get("job_id") != job_id:
                    continue
                if kind == MessageKind.JobResult:
                    return payload
                if kind == MessageKind.JobError:
                    code = payload.get("code") or "job_error"
                    message = payload.get("message") or "unknown error"
                    raise TranscriptionError(f"Native engine job failed ({code}): {message}")
                if kind == MessageKind.JobEvent and progress is not None:
                    progress(self._progress_event_from_native(payload, source_name=audio.source.path.name))
        finally:
            if original_timeout is not None:
                client.timeout = original_timeout

    @staticmethod
    def _cancel_job(client: FlowScribeEngineClient, job_id: str) -> None:
        try:
            client.cancel_job(job_id)
        except Exception:
            pass

    @staticmethod
    def _emit_progress(
        progress: Callable[[ProgressEvent], None] | None,
        message: str,
        *,
        stage: str = "prepare",
    ) -> None:
        if progress is None:
            return
        progress(ProgressEvent(stage=stage, message=message))

    def _build_transcript(
        self,
        audio: PreparedAudio,
        payload: dict[str, Any],
        *,
        model_path: Path,
    ) -> Transcript:
        segments = tuple(self._build_segment(segment) for segment in payload.get("segments", []))
        options = TranscriptionOptions(
            model_name=str(model_path),
            language=self._language,
            task=self._task,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            initial_prompt=self._initial_prompt,
            preset=self._preset,
            word_timestamps=self._word_timestamps,
            provider_name=NATIVE_ENGINE_PROVIDER_NAME,
        )
        return Transcript(
            source=audio.source,
            segments=segments,
            language=self._language,
            model_name=str(model_path),
            options=options,
            metadata={
                "chunked_enabled": bool(payload.get("chunked_enabled", False)),
                "chunk_count": int(payload.get("chunk_count", 0) or 0),
                "runtime_count": int(payload.get("runtime_count", 0) or 0),
                "effective_parallel_chunks": int(
                    payload.get("effective_parallel_chunks", 0) or 0
                ),
                "chunk_threads": int(payload.get("chunk_threads", 0) or 0),
                "chunk_seconds": float(payload.get("chunk_seconds", 0.0) or 0.0),
                "overlap_seconds": float(payload.get("overlap_seconds", 0.0) or 0.0),
                "chunk_metrics": tuple(payload.get("chunk_metrics", ()) or ()),
            },
        )

    def _progress_event_from_native(
        self,
        payload: dict[str, Any],
        *,
        source_name: str | None = None,
    ) -> ProgressEvent:
        status = str(payload.get("status") or "transcribing")
        progress_value = _optional_float_or_none(payload.get("progress"))
        chunk_index = _optional_int(payload.get("chunk_index"))
        chunk_count = _optional_int(payload.get("chunk_count"))
        completed_chunks = _optional_int(payload.get("completed_chunks"))
        current_seconds = _optional_float_or_none(payload.get("current_seconds"))
        total_seconds = _optional_float_or_none(payload.get("total_seconds"))
        runtime_slot = _optional_int(payload.get("runtime_slot"))
        segments = tuple(
            self._build_segment(segment)
            for segment in payload.get("segments", []) or []
            if isinstance(segment, dict)
        )

        if status == "chunks_planned" and chunk_count:
            if source_name and total_seconds:
                message = (
                    f"Progressive transcription ready for {source_name}: "
                    f"{_format_duration_label(total_seconds)} across {chunk_count} chunk(s)."
                )
            else:
                message = f"Native engine planned {chunk_count} chunk(s)."
            stage = "prepare"
        elif status == "chunk_started" and chunk_index and chunk_count:
            slot = f" on runtime {runtime_slot}" if runtime_slot is not None and runtime_slot >= 0 else ""
            message = f"Native engine started chunk {chunk_index}/{chunk_count}{slot}."
            stage = "transcribe"
        elif status == "chunk_completed" and chunk_index and chunk_count:
            if source_name and current_seconds and total_seconds:
                message = (
                    f"Processed chunk {chunk_index}/{chunk_count} for {source_name}: "
                    f"{_format_duration_label(current_seconds)} / "
                    f"{_format_duration_label(total_seconds)}."
                )
            else:
                message = f"Processed chunk {chunk_index}/{chunk_count}."
            stage = "transcribe"
        elif status == "job_completed":
            message = "Native engine transcription completed."
            stage = "transcribe"
        elif status == "job_failed":
            message = "Native engine transcription failed."
            stage = "error"
        else:
            progress_text = (
                f" ({progress_value * 100:.0f}%)"
                if progress_value is not None and progress_value <= 1.0
                else ""
            )
            message = f"Native engine status: {status}{progress_text}."
            stage = "transcribe"

        return ProgressEvent(
            stage=stage,
            message=message,
            processed_duration_seconds=current_seconds,
            total_duration_seconds=total_seconds,
            chunk_index=chunk_index,
            chunk_count=chunk_count,
            completed_chunks=completed_chunks,
            segments=segments,
        )

    def _build_segment(self, payload: dict[str, Any]) -> TranscriptSegment:
        raw_words = tuple(self._build_word(word) for word in payload.get("words", []))
        return TranscriptSegment(
            text=str(payload.get("text", "")).strip(),
            start_seconds=self._optional_float(payload.get("start")),
            end_seconds=self._optional_float(payload.get("end")),
            raw_words=raw_words,
            words=raw_words,
        )

    @staticmethod
    def _build_word(payload: dict[str, Any]) -> TranscriptWord:
        return TranscriptWord(
            text=str(payload.get("word", "")).strip(),
            start_seconds=NativeEngineTranscriber._optional_float(payload.get("start")),
            end_seconds=NativeEngineTranscriber._optional_float(payload.get("end")),
        )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _stop_engine(process) -> None:
        if process is None:
            return
        poll = getattr(process, "poll", None)
        if callable(poll) and poll() is not None:
            return
        terminate = getattr(process, "terminate", None)
        wait = getattr(process, "wait", None)
        kill = getattr(process, "kill", None)
        if callable(terminate):
            terminate()
        if callable(wait):
            try:
                wait(timeout=5)
                return
            except Exception:
                pass
        if callable(kill):
            kill()


def resolve_engine_exe() -> Path:
    env_path = os.environ.get("FLOWSCRIBE_ENGINE_EXE")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists() and path.is_file():
            return path.resolve()
        raise TranscriptionError(f"FLOWSCRIBE_ENGINE_EXE does not point to a file: {env_path}")

    root = Path(__file__).resolve().parents[3]
    candidates = (
        root / "native" / "flowscribe-engine" / "build" / "Release" / _engine_exe_name(),
        root
        / "native"
        / "flowscribe-engine"
        / "build"
        / "RelWithDebInfo"
        / _engine_exe_name(),
        root / "native" / "flowscribe-engine" / "build" / "Debug" / _engine_exe_name(),
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    from_path = shutil.which(_engine_exe_name())
    if from_path:
        return Path(from_path).resolve()

    raise TranscriptionError(
        "Could not find flowscribe-engine executable. Build native/flowscribe-engine "
        "or set FLOWSCRIBE_ENGINE_EXE."
    )


def _engine_exe_name() -> str:
    return "flowscribe-engine.exe" if sys.platform == "win32" else "flowscribe-engine"


def _unique_pipe_name() -> str:
    return rf"\\.\pipe\flowscribe-engine-v1-{os.getpid()}-{uuid.uuid4().hex}"


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _optional_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _format_duration_label(value: float) -> str:
    total_seconds = max(0, int(round(value)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
