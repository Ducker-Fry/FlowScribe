from __future__ import annotations

import queue
from pathlib import Path

import pytest

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.system_audio_capture_helper import (
    CaptureController,
    WasapiHelperCaptureRecorder,
    _parse_json_payload,
    _parse_probe_result,
)
from flowscribe.media.system_audio_capture_models import (
    CaptureDevice,
    CaptureSupportStatus,
)


def test_parse_probe_result_supported_device() -> None:
    status = _parse_probe_result(
        {
            "command": "probe",
            "supported": True,
            "default_output_device": {
                "id": "device-1",
                "name": "Speakers",
                "is_default": True,
            },
        }
    )

    assert status == CaptureSupportStatus(
        supported=True,
        default_device=CaptureDevice(id="device-1", name="Speakers", is_default=True),
    )


def test_parse_probe_result_unsupported_reason() -> None:
    status = _parse_probe_result(
        {
            "command": "probe",
            "supported": False,
            "reason": "No active output device available for loopback capture.",
        }
    )

    assert status.supported is False
    assert status.reason == "No active output device available for loopback capture."
    assert status.default_device is None


def test_parse_json_payload_rejects_invalid_output() -> None:
    with pytest.raises(MediaPreparationError, match="invalid JSON"):
        _parse_json_payload("not json")


def test_version_runs_helper_json_command(monkeypatch, tmp_path: Path) -> None:
    helper = tmp_path / "WasapiCaptureHelper.exe"
    helper.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = '{"command":"version","name":"WasapiCaptureHelper","version":"0.1.0"}\n'
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Completed()

    monkeypatch.setattr("flowscribe.media.system_audio_capture_helper.subprocess.run", fake_run)

    version = WasapiHelperCaptureRecorder(helper_executable=helper).version()

    assert version["command"] == "version"
    assert calls == [[str(helper), "version"]]


def test_probe_accepts_unsupported_exit_code(monkeypatch, tmp_path: Path) -> None:
    helper = tmp_path / "WasapiCaptureHelper.exe"
    helper.write_text("", encoding="utf-8")

    class Completed:
        returncode = 2
        stdout = (
            '{"command":"probe","supported":false,'
            '"reason":"No active output device available for loopback capture."}\n'
        )
        stderr = ""

    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_helper.subprocess.run",
        lambda *_args, **_kwargs: Completed(),
    )

    status = WasapiHelperCaptureRecorder(helper_executable=helper).probe()

    assert status.supported is False
    assert "No active output device" in (status.reason or "")


def test_list_devices_maps_helper_devices(monkeypatch, tmp_path: Path) -> None:
    helper = tmp_path / "WasapiCaptureHelper.exe"
    helper.write_text("", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = (
            '{"command":"list-devices","default_output_id":"device-1",'
            '"devices":[{"id":"device-1","name":"Speakers","is_default":true}]}\n'
        )
        stderr = ""

    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_helper.subprocess.run",
        lambda *_args, **_kwargs: Completed(),
    )

    devices = WasapiHelperCaptureRecorder(helper_executable=helper).list_devices()

    assert devices == (CaptureDevice(id="device-1", name="Speakers", is_default=True),)


def test_helper_path_reports_missing_configured_helper(tmp_path: Path) -> None:
    missing = tmp_path / "missing.exe"
    recorder = WasapiHelperCaptureRecorder(helper_executable=missing)

    with pytest.raises(MediaPreparationError, match="WASAPI helper was not found"):
        recorder.helper_path()


def test_start_and_stop_capture_through_helper_process(monkeypatch, tmp_path: Path) -> None:
    helper = tmp_path / "WasapiCaptureHelper.exe"
    helper.write_text("", encoding="utf-8")
    output_path = tmp_path / "capture.wav"

    class FakeStdout:
        def __init__(self) -> None:
            self.lines: queue.Queue[str | None] = queue.Queue()
            self.lines.put(
                '{"event":"started","device_id":"device-1",'
                '"device_name":"Speakers","output":"' + str(output_path).replace("\\", "\\\\") + '"}\n'
            )

        def __iter__(self):
            return self

        def __next__(self) -> str:
            line = self.lines.get(timeout=2)
            if line is None:
                raise StopIteration
            return line

    class FakeStdin:
        def __init__(self, process: "FakeProcess") -> None:
            self.process = process
            self.writes: list[str] = []

        def write(self, value: str) -> None:
            self.writes.append(value)
            if value == "stop\n":
                output_path.write_bytes(b"wav")
                self.process.stdout.lines.put('{"event":"stopping"}\n')
                self.process.stdout.lines.put(
                    '{"event":"completed","output":"'
                    + str(output_path).replace("\\", "\\\\")
                    + '","duration_seconds":1.25}\n'
                )
                self.process.stdout.lines.put(None)

        def flush(self) -> None:
            return

    class FakeStderr:
        def read(self) -> str:
            return ""

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = FakeStdout()
            self.stdin = FakeStdin(self)
            self.stderr = FakeStderr()
            self.returncode: int | None = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self.returncode = -15

        def kill(self) -> None:
            self.returncode = -9

    created_processes: list[FakeProcess] = []

    def fake_popen(command, **_kwargs):
        assert command[:5] == [str(helper), "capture", "--output", str(output_path.resolve()), "--device"]
        process = FakeProcess()
        created_processes.append(process)
        return process

    monkeypatch.setattr("flowscribe.media.system_audio_capture_helper.subprocess.Popen", fake_popen)

    recorder = WasapiHelperCaptureRecorder(helper_executable=helper)
    started = recorder.start(output_path)
    completed = recorder.stop()

    assert started.output_path == output_path.resolve()
    assert started.device == CaptureDevice(id="device-1", name="Speakers", is_default=True)
    assert completed.output_path == output_path
    assert completed.duration_seconds == 1.25
    assert created_processes[0].stdin.writes == ["stop\n"]


def test_capture_controller_delegates_to_recorder(tmp_path: Path) -> None:
    output_path = tmp_path / "capture.wav"

    class FakeRecorder:
        is_recording = False

        def probe(self):
            return CaptureSupportStatus(supported=True)

        def start(self, path: Path):
            assert path == output_path
            return "started"

        def stop(self):
            return "completed"

        def abort(self) -> None:
            self.aborted = True

    recorder = FakeRecorder()
    controller = CaptureController(recorder=recorder)  # type: ignore[arg-type]

    assert controller.support_status() == CaptureSupportStatus(supported=True)
    assert controller.is_recording() is False
    assert controller.start_capture(output_path) == "started"
    assert controller.stop_capture() == "completed"
    controller.abort_capture()
    assert recorder.aborted is True
