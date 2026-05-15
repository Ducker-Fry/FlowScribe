"""Python integration for the Windows WASAPI capture helper."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.system_audio_capture_models import (
    CaptureActivityStatus,
    CaptureCompletedResult,
    CaptureDevice,
    CaptureEvent,
    CaptureStartResult,
    CaptureSupportStatus,
)

HELPER_EXE_NAME = "WasapiCaptureHelper.exe"


class WasapiHelperCaptureRecorder:
    """Control ``WasapiCaptureHelper.exe`` as a structured subprocess."""

    def __init__(
        self,
        *,
        helper_executable: str | Path | None = None,
        command_timeout_seconds: float = 10.0,
    ) -> None:
        self._configured_helper = Path(helper_executable) if helper_executable is not None else None
        self._command_timeout_seconds = command_timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._events: queue.Queue[CaptureEvent] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._active_output_path: Path | None = None
        self._last_observed_capture_size_bytes = 0
        self._last_capture_growth_at: datetime | None = None

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def helper_path(self) -> Path:
        """Resolve the helper for source runs and packaged GUI runs."""

        if self._configured_helper is not None:
            if self._configured_helper.exists():
                return self._configured_helper
            raise MediaPreparationError(f"WASAPI helper was not found: {self._configured_helper}")

        for candidate in _helper_candidates():
            if candidate.exists():
                return candidate

        raise MediaPreparationError(
            "WasapiCaptureHelper.exe was not found. Build the helper or use a packaged GUI bundle."
        )

    def version(self) -> dict[str, Any]:
        return _run_json_command(
            self.helper_path(),
            ["version"],
            timeout_seconds=self._command_timeout_seconds,
        )

    def probe(self) -> CaptureSupportStatus:
        payload = _run_json_command(
            self.helper_path(),
            ["probe"],
            timeout_seconds=self._command_timeout_seconds,
            accepted_returncodes={0, 2},
        )
        return _parse_probe_result(payload)

    def list_devices(self) -> tuple[CaptureDevice, ...]:
        payload = _run_json_command(
            self.helper_path(),
            ["list-devices"],
            timeout_seconds=self._command_timeout_seconds,
            accepted_returncodes={0, 2},
        )
        return tuple(_parse_device(device) for device in payload.get("devices", ()))

    def start(
        self,
        output_path: Path,
        *,
        device: str = "default",
        sample_rate: int | None = 16000,
        channels: int | None = 1,
    ) -> CaptureStartResult:
        if self.is_recording:
            raise MediaPreparationError("System audio capture is already running.")

        output_path = output_path.resolve()
        command = [
            str(self.helper_path()),
            "capture",
            "--output",
            str(output_path),
            "--device",
            device,
        ]
        if sample_rate is not None:
            command += ["--sample-rate", str(sample_rate)]
        if channels is not None:
            command += ["--channels", str(channels)]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._process = process
        self._active_output_path = output_path
        self._last_observed_capture_size_bytes = 0
        self._last_capture_growth_at = None
        self._events = queue.Queue()
        self._reader_thread = threading.Thread(
            target=self._read_stdout_events,
            args=(process,),
            name="WasapiCaptureHelperStdout",
            daemon=True,
        )
        self._reader_thread.start()

        try:
            event = self._wait_for_event({"started", "error"})
        except Exception:
            self.abort()
            raise

        if event.event == "error":
            self.abort()
            raise MediaPreparationError(str(event.payload.get("message") or "WASAPI capture failed."))

        return CaptureStartResult(
            output_path=output_path,
            device=_device_from_started_event(event),
            event=event,
        )

    def stop(self) -> CaptureCompletedResult:
        if not self.is_recording or self._process is None or self._active_output_path is None:
            raise MediaPreparationError("System audio capture is not running.")

        process = self._process
        output_path = self._active_output_path
        if process.stdin is not None:
            try:
                process.stdin.write("stop\n")
                process.stdin.flush()
            except OSError as exc:
                raise MediaPreparationError(f"Could not stop WASAPI capture helper: {exc}") from exc

        event = self._wait_for_event({"completed", "error"})
        self._finalize_process(process)
        self._clear_active_process()

        if event.event == "error":
            raise MediaPreparationError(str(event.payload.get("message") or "WASAPI capture failed."))

        completed_path = Path(str(event.payload.get("output") or output_path))
        if not completed_path.exists() or completed_path.stat().st_size <= 0:
            raise MediaPreparationError("WASAPI capture produced no usable audio file.")

        return CaptureCompletedResult(
            output_path=completed_path,
            duration_seconds=_optional_float(event.payload.get("duration_seconds")),
            event=event,
        )

    def abort(self) -> None:
        process = self._process
        output_path = self._active_output_path
        self._clear_active_process()
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if output_path is not None:
            output_path.unlink(missing_ok=True)

    def activity_status(self) -> CaptureActivityStatus:
        if not self.is_recording or self._active_output_path is None:
            return CaptureActivityStatus(
                state="idle",
                message="System capture is idle.",
            )

        try:
            bytes_captured = (
                self._active_output_path.stat().st_size
                if self._active_output_path.exists()
                else 0
            )
        except OSError:
            bytes_captured = 0

        now = datetime.now()
        recently_grew = False
        if bytes_captured > self._last_observed_capture_size_bytes:
            self._last_observed_capture_size_bytes = bytes_captured
            self._last_capture_growth_at = now
            recently_grew = True

        if recently_grew or (
            self._last_capture_growth_at is not None
            and now - self._last_capture_growth_at <= timedelta(seconds=2)
        ):
            return CaptureActivityStatus(
                state="active",
                bytes_captured=bytes_captured,
                recently_grew=recently_grew,
                message=(
                    f"Capture is receiving audio data. "
                    f"Current file size: {_format_capture_size(bytes_captured)}."
                ),
            )

        return CaptureActivityStatus(
            state="stalled",
            bytes_captured=bytes_captured,
            recently_grew=False,
            message=(
                "Capture is running, but no new audio data arrived recently. "
                "Check whether system playback is active and the default output device is correct."
            ),
        )

    def _read_stdout_events(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_name = str(payload.get("event") or "")
            if event_name:
                self._events.put(CaptureEvent(event=event_name, payload=payload))

    def _wait_for_event(self, accepted_events: set[str]) -> CaptureEvent:
        while True:
            try:
                event = self._events.get(timeout=self._command_timeout_seconds)
            except queue.Empty as exc:
                stderr = self._read_stderr()
                raise MediaPreparationError(
                    "Timed out waiting for WASAPI helper output."
                    + (f" stderr: {stderr}" if stderr else "")
                ) from exc
            if event.event in accepted_events:
                return event

    def _read_stderr(self) -> str:
        process = self._process
        if process is None or process.stderr is None or process.poll() is None:
            return ""
        return process.stderr.read().strip()

    def _finalize_process(self, process: subprocess.Popen[str]) -> None:
        try:
            process.wait(timeout=self._command_timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.terminate()
            raise MediaPreparationError("WASAPI helper did not exit after completing capture.") from exc
        if process.returncode not in (0, None):
            raise MediaPreparationError(f"WASAPI helper exited with code {process.returncode}.")

    def _clear_active_process(self) -> None:
        self._process = None
        self._active_output_path = None
        self._reader_thread = None
        self._last_observed_capture_size_bytes = 0
        self._last_capture_growth_at = None


class CaptureController:
    """Facade for GUI system-audio capture."""

    def __init__(self, recorder: WasapiHelperCaptureRecorder | None = None) -> None:
        self._recorder = recorder or WasapiHelperCaptureRecorder()

    def support_status(self) -> CaptureSupportStatus:
        return self._recorder.probe()

    def is_recording(self) -> bool:
        return self._recorder.is_recording

    def start_capture(self, output_path: Path) -> CaptureStartResult:
        return self._recorder.start(output_path)

    def stop_capture(self) -> CaptureCompletedResult:
        return self._recorder.stop()

    def abort_capture(self) -> None:
        self._recorder.abort()

    def activity_status(self) -> CaptureActivityStatus:
        return self._recorder.activity_status()


def _helper_candidates() -> tuple[Path, ...]:
    executable_dir = Path(sys.executable).resolve().parent
    source_root = Path(__file__).resolve().parents[3]
    bundle_dir = Path(getattr(sys, "_MEIPASS", executable_dir))
    return (
        executable_dir / HELPER_EXE_NAME,
        bundle_dir / HELPER_EXE_NAME,
        source_root / "build" / "wasapi-helper" / HELPER_EXE_NAME,
        source_root
        / "tools"
        / "wasapi-capture-helper"
        / "src"
        / "WasapiCaptureHelper"
        / "bin"
        / "x64"
        / "Release"
        / "net8.0-windows"
        / "win-x64"
        / HELPER_EXE_NAME,
    )


def _run_json_command(
    helper_path: Path,
    args: list[str],
    *,
    timeout_seconds: float,
    accepted_returncodes: set[int] | None = None,
) -> dict[str, Any]:
    accepted = accepted_returncodes or {0}
    try:
        completed = subprocess.run(
            [str(helper_path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaPreparationError(f"WASAPI helper was not found: {helper_path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaPreparationError("Timed out waiting for WASAPI helper.") from exc
    except OSError as exc:
        raise MediaPreparationError(f"Could not run WASAPI helper: {exc}") from exc

    payload = _parse_json_payload(completed.stdout)
    if completed.returncode not in accepted:
        message = payload.get("message") or completed.stderr.strip() or f"exit code {completed.returncode}"
        raise MediaPreparationError(f"WASAPI helper command failed: {message}")
    return payload


def _parse_json_payload(output: str) -> dict[str, Any]:
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MediaPreparationError("WASAPI helper emitted invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise MediaPreparationError("WASAPI helper emitted JSON that was not an object.")
        return payload
    raise MediaPreparationError("WASAPI helper emitted no JSON output.")


def _parse_probe_result(payload: dict[str, Any]) -> CaptureSupportStatus:
    return CaptureSupportStatus(
        supported=bool(payload.get("supported")),
        reason=_optional_str(payload.get("reason")),
        default_device=_parse_optional_device(payload.get("default_output_device")),
    )


def _parse_optional_device(value: Any) -> CaptureDevice | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MediaPreparationError("WASAPI helper returned an invalid device object.")
    return _parse_device(value)


def _parse_device(value: Any) -> CaptureDevice:
    if not isinstance(value, dict):
        raise MediaPreparationError("WASAPI helper returned an invalid device object.")
    return CaptureDevice(
        id=str(value.get("id") or ""),
        name=str(value.get("name") or ""),
        is_default=bool(value.get("is_default")),
    )


def _device_from_started_event(event: CaptureEvent) -> CaptureDevice | None:
    device_id = _optional_str(event.payload.get("device_id"))
    device_name = _optional_str(event.payload.get("device_name"))
    if device_id is None and device_name is None:
        return None
    return CaptureDevice(
        id=device_id or "default",
        name=device_name or "Default output device",
        is_default=True,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _format_capture_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"
