import json
import logging
import time
from collections import deque
from typing import Any

from .protocol import (
    PIPE_NAME,
    PROTOCOL_VERSION,
    MessageKind,
    decode_header,
    encode_message,
)

try:
    import pywintypes
    import win32file
    import win32pipe
except ImportError:
    pywintypes = None  # type: ignore[assignment]
    win32file = None  # type: ignore[assignment]
    win32pipe = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class FlowScribeEngineClient:
    def __init__(self, timeout: float = 5.0, pipe_name: str = PIPE_NAME) -> None:
        self.pipe_handle: Any | None = None
        self.timeout = timeout
        self.pipe_name = pipe_name
        self._async_inbox: deque[tuple[int, dict[str, Any]]] = deque()

    def connect(self, retry: int = 3, delay: float = 1.0) -> bool:
        """Connect to the native engine named pipe with retries."""
        if pywintypes is None or win32file is None:
            logger.error("pywin32 is required to connect to the FlowScribe engine")
            return False

        for attempt in range(1, retry + 1):
            try:
                handle = win32file.CreateFile(
                    self.pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                self.pipe_handle = handle
                logger.info("Connected to FlowScribe engine")
                return True
            except pywintypes.error as exc:
                logger.warning("Connection attempt %s/%s failed: %s", attempt, retry, exc)
                if attempt < retry:
                    time.sleep(delay)

        logger.error("All connection attempts failed")
        return False

    def _read_exact(self, size: int, *, quiet_timeout: bool = False) -> bytes | None:
        """Read exactly size bytes from the pipe."""
        if self.pipe_handle is None or pywintypes is None or win32file is None:
            return None

        buffer = b""
        start = time.monotonic()
        while len(buffer) < size:
            if time.monotonic() - start > self.timeout:
                if not quiet_timeout:
                    logger.error("Read timed out after %.1fs", self.timeout)
                return None

            if win32pipe is not None:
                try:
                    _data, available, _message_left = win32pipe.PeekNamedPipe(
                        self.pipe_handle,
                        0,
                    )
                except pywintypes.error as exc:
                    logger.error("Peek failed: %s", exc)
                    return None

                if available == 0:
                    time.sleep(0.01)
                    continue

            try:
                result, data = win32file.ReadFile(self.pipe_handle, size - len(buffer))
            except pywintypes.error as exc:
                logger.error("Read failed: %s", exc)
                return None

            if result != 0 or not data:
                logger.error("Read returned no data, result=%s", result)
                return None

            buffer += data

        return buffer

    def send_message(self, kind: int, payload: dict[str, Any]) -> bool:
        """Send one framed protocol message."""
        if self.pipe_handle is None or pywintypes is None or win32file is None:
            logger.error("FlowScribe engine is not connected")
            return False

        try:
            message = encode_message(kind, payload)
            win32file.WriteFile(self.pipe_handle, message)
            logger.debug("Sent message: kind=%s, len=%s", kind, len(message))
            return True
        except pywintypes.error as exc:
            logger.error("Send failed: %s", exc)
            return False

    def recv_message(self, *, quiet_timeout: bool = False) -> tuple[int, dict[str, Any]] | None:
        """Receive one framed protocol message."""
        header = self._read_exact(8, quiet_timeout=quiet_timeout)
        if not header:
            if not quiet_timeout:
                logger.error("Failed to read frame header")
            return None

        payload_len, version, kind = decode_header(header)
        if version != PROTOCOL_VERSION:
            logger.error(
                "Protocol version mismatch: expected=%s, actual=%s",
                PROTOCOL_VERSION,
                version,
            )
            return None

        payload_bytes = self._read_exact(payload_len, quiet_timeout=quiet_timeout)
        if not payload_bytes:
            logger.error("Failed to read payload")
            return None

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.error("Failed to parse JSON payload: %s", exc)
            return None

        logger.debug("Received message: kind=%s, len=%s", kind, payload_len)
        return kind, payload

    @staticmethod
    def _is_async_kind(kind: int) -> bool:
        return kind in (
            MessageKind.JobEvent,
            MessageKind.JobResult,
            MessageKind.JobError,
        )

    def _recv_expected(self, expected_kind: int) -> dict[str, Any] | None:
        """Receive a specific response kind, buffering async job messages."""
        while True:
            response = self.recv_message()
            if response is None:
                return None

            kind, payload = response
            if kind == expected_kind:
                return payload

            if self._is_async_kind(kind):
                self._async_inbox.append((kind, payload))
                continue

            logger.error("Unexpected message kind: %s", kind)
            return None

    def send_hello(self) -> dict[str, Any] | None:
        """Send HelloRequest and wait for HelloResult."""
        if not self.send_message(MessageKind.HelloRequest, {"client_id": "FlowScribe-Python"}):
            return None

        payload = self._recv_expected(MessageKind.HelloResult)
        if payload is None:
            logger.error("No HelloResult received")
            return None
        return payload

    def load_model(self, model_path: str, model_name: str, use_gpu: bool = False):
        payload = {
            "model_path": model_path,
            "model_name": model_name,
            "use_gpu": use_gpu
        }
        if not self.send_message(MessageKind.LoadModelRequest, payload):
            return None
        
        payload = self._recv_expected(MessageKind.LoadModelResult)
        if payload is None:
            logger.error("No LoadModelResult received")
            return None
        return payload

    def submit_job(self, job_id: str, audio_path: str, **kwargs):
        payload = {
            "job_id": job_id,
            "audio_path": audio_path,
            "language": kwargs.get("language", "zh"),
            "task": kwargs.get("task", "transcribe"),
            "vad_filter": kwargs.get("vad_filter", False),
            "beam_size": kwargs.get("beam_size", 5),
            "initial_prompt": kwargs.get("initial_prompt", ""),
            "progressive": kwargs.get("progressive", {
                "enabled": True,
                "chunk_seconds": 60.0,
                "overlap_seconds": 5.0,
                "max_workers": 1,
            })
        }
        threads = kwargs.get("threads")
        if threads is not None:
            payload["threads"] = threads
        if not self.send_message(MessageKind.SubmitJobRequest, payload):
            return None
        payload = self._recv_expected(MessageKind.SubmitJobResult)
        if payload is None:
            logger.error("No SubmitJobResult received")
            return None
        return payload

    def cancel_job(self, job_id: str):
        if not self.send_message(MessageKind.CancelJobRequest, {"job_id": job_id}):
            return None

        payload = self._recv_expected(MessageKind.CancelJobResult)
        if payload is None:
            logger.error("No CancelJobResult received")
            return None
        return payload

    def query_job(self, job_id: str):
        if not self.send_message(MessageKind.QueryJobRequest, {"job_id": job_id}):
            return None

        payload = self._recv_expected(MessageKind.QueryJobResult)
        if payload is None:
            logger.error("No QueryJobResult received")
            return None
        return payload

    def recv_job_messages(
        self,
        job_id: str,
        timeout: float | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        messages: list[tuple[int, dict[str, Any]]] = []
        original_timeout = self.timeout
        if timeout is not None:
            self.timeout = timeout

        try:
            while True:
                if self._async_inbox:
                    response = self._async_inbox.popleft()
                else:
                    response = self.recv_message()
                if response is None:
                    return messages

                kind, payload = response
                if payload.get("job_id") == job_id:
                    messages.append((kind, payload))

                if kind in (MessageKind.JobResult, MessageKind.JobError):
                    return messages
        finally:
            if timeout is not None:
                self.timeout = original_timeout

    def close(self) -> None:
        if self.pipe_handle is not None and win32file is not None:
            win32file.CloseHandle(self.pipe_handle)
            self.pipe_handle = None
            logger.info("Connection closed")
