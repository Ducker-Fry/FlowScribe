"""Legacy DirectShow system-audio capture compatibility helpers."""

from __future__ import annotations

import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from flowscribe.core.errors import MediaPreparationError
from flowscribe.media.tools import resolve_tool_path


@dataclass(frozen=True)
class LegacyCaptureStartInfo:
    """Metadata describing a started legacy capture session."""

    output_path: Path
    backend: str


@dataclass(frozen=True)
class LegacyCaptureDeviceInfo:
    """One ffmpeg-visible Windows audio capture device."""

    backend: str
    name: str
    alternative_name: str | None = None


@dataclass(frozen=True)
class LegacyCaptureAttemptInfo:
    """One attempted legacy capture backend/device and its error state."""

    backend: str
    target: str
    error: str


class LegacyDshowCaptureRecorder:
    """Compatibility recorder for old ffmpeg DirectShow loopback-style devices."""

    def __init__(self, *, ffmpeg_executable: str | None = None) -> None:
        self._ffmpeg_executable = ffmpeg_executable or resolve_tool_path("ffmpeg")
        self._process: subprocess.Popen[str] | None = None
        self._output_path: Path | None = None
        self._backend: str | None = None
        self._last_attempts: tuple[LegacyCaptureAttemptInfo, ...] = ()

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def last_attempts(self) -> tuple[LegacyCaptureAttemptInfo, ...]:
        return self._last_attempts

    def list_available_devices(self) -> tuple[LegacyCaptureDeviceInfo, ...]:
        return _list_dshow_audio_devices(self._ffmpeg_executable)

    def support_status(self) -> tuple[bool, str]:
        devices = self.list_available_devices()
        loopback_devices = [
            device.name for device in _sorted_capture_devices(devices) if _is_loopback_like_device(device)
        ]
        if loopback_devices:
            return True, f"Legacy DirectShow loopback capture available via: {', '.join(loopback_devices)}"
        return (
            False,
            "No supported legacy DirectShow loopback capture device was detected. "
            "FlowScribe's normal system-audio capture path uses the bundled WASAPI helper. "
            "The legacy path only works with loopback-capable devices such as Stereo Mix, "
            "What U Hear, Wave Out Mix, virtual-audio-capturer, or VB-CABLE. "
            f"Detected dshow audio devices: {', '.join(device.name for device in devices) or 'none'}",
        )

    def start(self, output_path: Path) -> LegacyCaptureStartInfo:
        if self.is_recording:
            raise MediaPreparationError("Legacy DirectShow capture is already running.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        attempts: list[LegacyCaptureAttemptInfo] = []
        for backend, target, command in _capture_commands(self._ffmpeg_executable, output_path):
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise MediaPreparationError(
                    "ffmpeg was not found. Install ffmpeg and add it to PATH."
                ) from exc
            except OSError as exc:
                attempts.append(LegacyCaptureAttemptInfo(backend=backend, target=target, error=str(exc)))
                continue

            time.sleep(0.35)
            if process.poll() is None:
                self._process = process
                self._output_path = output_path
                self._backend = f"{backend}: {target}"
                self._last_attempts = tuple(attempts)
                return LegacyCaptureStartInfo(output_path=output_path, backend=f"{backend}: {target}")

            stderr = ""
            if process.stderr is not None:
                stderr = process.stderr.read().strip()
            attempts.append(
                LegacyCaptureAttemptInfo(
                    backend=backend,
                    target=target,
                    error=stderr or f"{backend} exited immediately.",
                )
            )

        self._last_attempts = tuple(attempts)
        device_names = [device.name for device in self.list_available_devices()]
        device_hint = (
            "Detected dshow audio devices: " + ", ".join(device_names)
            if device_names
            else "No dshow audio devices were detected by ffmpeg."
        )
        attempt_summary = " | ".join(
            f"{attempt.backend} [{attempt.target}]: {attempt.error}" for attempt in attempts
        ) or "No compatible legacy DirectShow capture backend was available."
        raise MediaPreparationError(
            "Could not start legacy DirectShow system audio capture. "
            f"{device_hint} Attempts: {attempt_summary}"
        )

    def stop(self) -> Path:
        if not self.is_recording or self._process is None or self._output_path is None:
            raise MediaPreparationError("Legacy DirectShow capture is not running.")

        process = self._process
        output_path = self._output_path
        try:
            if process.stdin is not None:
                try:
                    process.stdin.write("q\n")
                    process.stdin.flush()
                except OSError:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        finally:
            self._process = None
            self._output_path = None
            self._backend = None

        stderr = ""
        if process.stderr is not None:
            stderr = process.stderr.read().strip()
        if process.returncode not in (0, None) and not output_path.exists():
            raise MediaPreparationError(
                "Legacy DirectShow capture failed to finalize. "
                f"ffmpeg reported: {stderr or f'exit code {process.returncode}'}"
            )
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise MediaPreparationError("Legacy DirectShow capture produced no usable audio file.")
        if is_probably_silent_wav(output_path):
            output_path.unlink(missing_ok=True)
            raise MediaPreparationError(
                "Legacy DirectShow capture produced a silent WAV file. "
                "This usually means ffmpeg captured the wrong audio input instead of system playback. "
                "Use the bundled WASAPI helper path for normal GUI capture, or enable a legacy loopback "
                "device such as Stereo Mix / virtual-audio-capturer / VB-CABLE."
            )
        return output_path

    def abort(self) -> None:
        process = self._process
        output_path = self._output_path
        self._process = None
        self._output_path = None
        self._backend = None
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


def _capture_commands(
    ffmpeg_executable: str,
    output_path: Path,
) -> tuple[tuple[str, str, list[str]], ...]:
    base = [
        ffmpeg_executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    wav_args = [
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    commands: list[tuple[str, str, list[str]]] = []
    seen_targets: set[str] = set()

    for device in _sorted_capture_devices(_list_dshow_audio_devices(ffmpeg_executable)):
        if not _is_loopback_like_device(device):
            continue
        target = device.alternative_name or device.name
        if target in seen_targets:
            continue
        seen_targets.add(target)
        commands.append(
            (
                "Legacy DirectShow audio device",
                device.name,
                base + ["-f", "dshow", "-i", f"audio={target}"] + wav_args,
            )
        )

    if "virtual-audio-capturer" not in seen_targets:
        commands.append(
            (
                "Legacy DirectShow virtual-audio-capturer",
                "virtual-audio-capturer",
                base + ["-f", "dshow", "-i", "audio=virtual-audio-capturer"] + wav_args,
            )
        )
    return tuple(commands)


def _list_dshow_audio_devices(ffmpeg_executable: str) -> tuple[LegacyCaptureDeviceInfo, ...]:
    command = [
        ffmpeg_executable,
        "-hide_banner",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaPreparationError("ffmpeg was not found. Install ffmpeg and add it to PATH.") from exc
    except OSError as exc:
        raise MediaPreparationError(f"Could not query legacy DirectShow audio devices: {exc}") from exc

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return _parse_dshow_audio_devices(output)


def _parse_dshow_audio_devices(output: str) -> tuple[LegacyCaptureDeviceInfo, ...]:
    devices: list[LegacyCaptureDeviceInfo] = []
    last_audio_index: int | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "(audio)" in line and '"' in line:
            name = _extract_quoted_value(line)
            if name:
                devices.append(LegacyCaptureDeviceInfo(backend="dshow", name=name))
                last_audio_index = len(devices) - 1
            continue
        if "Alternative name" in line and last_audio_index is not None and '"' in line:
            alternative_name = _extract_quoted_value(line)
            if alternative_name:
                current = devices[last_audio_index]
                devices[last_audio_index] = LegacyCaptureDeviceInfo(
                    backend=current.backend,
                    name=current.name,
                    alternative_name=alternative_name,
                )
    return tuple(devices)


def _extract_quoted_value(text: str) -> str | None:
    parts = text.split('"')
    if len(parts) < 3:
        return None
    return parts[1].strip() or None


def _sorted_capture_devices(
    devices: tuple[LegacyCaptureDeviceInfo, ...],
) -> tuple[LegacyCaptureDeviceInfo, ...]:
    return tuple(sorted(devices, key=_capture_device_priority, reverse=True))


def _capture_device_priority(device: LegacyCaptureDeviceInfo) -> int:
    name = device.name.casefold()
    score = 0
    preferred_terms = (
        ("stereo mix", 30),
        ("what u hear", 30),
        ("wave out", 25),
        ("virtual-audio-capturer", 25),
        ("cable output", 25),
        ("loopback", 25),
        ("mix", 10),
        ("立体声混音", 30),
    )
    discouraged_terms = (
        "microphone",
        "mic",
        "line in",
        "array",
        "input",
        "麦克风",
    )
    for term, weight in preferred_terms:
        if term in name:
            score += weight
    for term in discouraged_terms:
        if term in name:
            score -= 10
    return score


def _is_loopback_like_device(device: LegacyCaptureDeviceInfo) -> bool:
    return _capture_device_priority(device) > 0


def is_probably_silent_wav(path: Path, *, average_threshold: float = 8.0) -> bool:
    try:
        with wave.open(str(path), "rb") as wav_file:
            if wav_file.getnchannels() <= 0 or wav_file.getsampwidth() != 2:
                return False
            frame_count = wav_file.getnframes()
            if frame_count <= 0:
                return True
            frames = wav_file.readframes(frame_count)
    except (OSError, EOFError, wave.Error):
        return False

    if not frames:
        return True

    sample_count = len(frames) // 2
    if sample_count <= 0:
        return True

    total = 0
    for index in range(0, len(frames), 2):
        sample = int.from_bytes(frames[index:index + 2], byteorder="little", signed=True)
        total += abs(sample)
    average = total / sample_count
    return average < average_threshold
