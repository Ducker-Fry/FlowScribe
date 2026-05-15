from pathlib import Path

import pytest

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.system_audio_capture import FfmpegSystemAudioRecorder
from flowscribe.media.system_audio_capture_legacy import (
    LegacyCaptureDeviceInfo,
    LegacyDshowCaptureRecorder,
    _capture_commands,
    _is_loopback_like_device,
    _parse_dshow_audio_devices,
    _sorted_capture_devices,
    is_probably_silent_wav,
)


def test_capture_commands_include_windows_backends(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_legacy._list_dshow_audio_devices",
        lambda _ffmpeg: (),
    )
    commands = _capture_commands("ffmpeg", tmp_path / "capture.wav")

    assert commands[0][0] == "Legacy DirectShow virtual-audio-capturer"
    assert commands[0][1] == "virtual-audio-capturer"
    assert commands[0][2][:6] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f"]
    assert any("virtual-audio-capturer" in token for token in commands[0][2])


def test_system_audio_recorder_falls_back_to_second_backend(monkeypatch, tmp_path: Path) -> None:
    attempts: list[list[str]] = []

    class FakePipe:
        def __init__(self, text: str = "") -> None:
            self._text = text
            self.writes: list[str] = []

        def read(self) -> str:
            return self._text

        def write(self, value: str) -> None:
            self.writes.append(value)

        def flush(self) -> None:
            return

    class FakeProcess:
        def __init__(self, alive: bool, stderr_text: str = "") -> None:
            self._alive = alive
            self.stderr = FakePipe(stderr_text)
            self.stdin = FakePipe()
            self.returncode = None if alive else 1

        def poll(self):
            return None if self._alive else self.returncode

        def wait(self, timeout=None):
            self._alive = False
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self._alive = False
            self.returncode = -15

        def kill(self) -> None:
            self._alive = False
            self.returncode = -9

    processes = [
        FakeProcess(False, "wasapi failed"),
        FakeProcess(True),
    ]

    def fake_popen(command, **kwargs):
        attempts.append(command)
        return processes.pop(0)

    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_legacy._list_dshow_audio_devices",
        lambda _ffmpeg: (
            LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列"),
            LegacyCaptureDeviceInfo(backend="dshow", name="Stereo Mix"),
        ),
    )
    monkeypatch.setattr("flowscribe.media.system_audio_capture_legacy.subprocess.Popen", fake_popen)
    monkeypatch.setattr("flowscribe.media.system_audio_capture_legacy.time.sleep", lambda *_args, **_kwargs: None)

    recorder = LegacyDshowCaptureRecorder(ffmpeg_executable="ffmpeg")
    started = recorder.start(tmp_path / "capture.wav")

    assert started.backend == "Legacy DirectShow virtual-audio-capturer: virtual-audio-capturer"
    assert len(attempts) == 2


def test_system_audio_recorder_stop_finalizes_wav(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "capture.wav"

    class FakePipe:
        def __init__(self) -> None:
            self.writes: list[str] = []

        def write(self, value: str) -> None:
            self.writes.append(value)

        def flush(self) -> None:
            return

        def read(self) -> str:
            return ""

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakePipe()
            self.stderr = FakePipe()
            self.returncode = None
            self._alive = True

        def poll(self):
            return None if self._alive else self.returncode

        def wait(self, timeout=None):
            output_path.write_bytes(b"wav")
            self._alive = False
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self._alive = False
            self.returncode = -15

        def kill(self) -> None:
            self._alive = False
            self.returncode = -9

    process = FakeProcess()
    recorder = LegacyDshowCaptureRecorder(ffmpeg_executable="ffmpeg")
    monkeypatch.setattr(recorder, "_process", process)
    monkeypatch.setattr(recorder, "_output_path", output_path)
    monkeypatch.setattr(recorder, "_backend", "WASAPI default output")

    finalized = recorder.stop()

    assert finalized == output_path
    assert process.stdin.writes == ["q\n"]


def test_system_audio_recorder_raises_when_backend_never_starts(monkeypatch, tmp_path: Path) -> None:
    class FakePipe:
        def __init__(self, text: str) -> None:
            self._text = text

        def read(self) -> str:
            return self._text

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = None
            self.stderr = FakePipe("device unavailable")
            self.returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_legacy._list_dshow_audio_devices",
        lambda _ffmpeg: (),
    )
    monkeypatch.setattr(
        "flowscribe.media.system_audio_capture_legacy.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )
    monkeypatch.setattr("flowscribe.media.system_audio_capture_legacy.time.sleep", lambda *_args, **_kwargs: None)

    recorder = LegacyDshowCaptureRecorder(ffmpeg_executable="ffmpeg")

    with pytest.raises(MediaPreparationError, match="Could not start legacy DirectShow"):
        recorder.start(tmp_path / "capture.wav")


def test_parse_dshow_audio_devices_reads_display_and_alternative_names() -> None:
    output = """
[dshow @ 000] "麦克风阵列" (audio)
[dshow @ 000]   Alternative name "@device_cm_microphone"
[dshow @ 000] "耳机 (soundcore Q20i)" (audio)
[dshow @ 000]   Alternative name "@device_cm_headphone"
""".strip()

    devices = _parse_dshow_audio_devices(output)

    assert devices == (
        LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列", alternative_name="@device_cm_microphone"),
        LegacyCaptureDeviceInfo(backend="dshow", name="耳机 (soundcore Q20i)", alternative_name="@device_cm_headphone"),
    )


def test_sorted_capture_devices_prefers_output_like_devices() -> None:
    devices = (
        LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列"),
        LegacyCaptureDeviceInfo(backend="dshow", name="耳机 (soundcore Q20i)"),
        LegacyCaptureDeviceInfo(backend="dshow", name="Stereo Mix"),
    )

    sorted_devices = _sorted_capture_devices(devices)

    assert [device.name for device in sorted_devices] == [
        "Stereo Mix",
        "耳机 (soundcore Q20i)",
        "麦克风阵列",
    ]


def test_loopback_like_device_detection_is_strict() -> None:
    assert _is_loopback_like_device(LegacyCaptureDeviceInfo(backend="dshow", name="Stereo Mix")) is True
    assert _is_loopback_like_device(LegacyCaptureDeviceInfo(backend="dshow", name="virtual-audio-capturer")) is True
    assert _is_loopback_like_device(LegacyCaptureDeviceInfo(backend="dshow", name="耳机 (soundcore Q20i)")) is False
    assert _is_loopback_like_device(LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列")) is False


def test_is_probably_silent_wav_detects_empty_capture(tmp_path: Path) -> None:
    path = tmp_path / "silent.wav"
    import wave

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)

    assert is_probably_silent_wav(path) is True


def test_support_status_requires_loopback_like_device(monkeypatch) -> None:
    recorder = LegacyDshowCaptureRecorder(ffmpeg_executable="ffmpeg")
    monkeypatch.setattr(
        recorder,
        "list_available_devices",
        lambda: (
            LegacyCaptureDeviceInfo(backend="dshow", name="Stereo Mix"),
            LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列"),
        ),
    )

    supported, message = recorder.support_status()

    assert supported is True
    assert "Stereo Mix" in message


def test_support_status_reports_missing_loopback_devices(monkeypatch) -> None:
    recorder = LegacyDshowCaptureRecorder(ffmpeg_executable="ffmpeg")
    monkeypatch.setattr(
        recorder,
        "list_available_devices",
        lambda: (
            LegacyCaptureDeviceInfo(backend="dshow", name="耳机 (soundcore Q20i)"),
            LegacyCaptureDeviceInfo(backend="dshow", name="麦克风阵列"),
        ),
    )

    supported, message = recorder.support_status()

    assert supported is False
    assert "No supported legacy DirectShow loopback capture device" in message


def test_legacy_recorder_remains_available_from_compatibility_module() -> None:
    assert FfmpegSystemAudioRecorder is LegacyDshowCaptureRecorder
