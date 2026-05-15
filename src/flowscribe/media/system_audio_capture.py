"""Backward-compatible imports for legacy DirectShow system-audio capture.

Normal GUI capture now uses the WASAPI helper path in
``flowscribe.media.system_audio_capture_helper``. This module remains only so
older imports keep working while the legacy DirectShow path is phased down.
"""

from __future__ import annotations

from flowscribe.media.system_audio_capture_legacy import (
    LegacyCaptureAttemptInfo,
    LegacyCaptureDeviceInfo,
    LegacyCaptureStartInfo,
    LegacyDshowCaptureRecorder,
    _capture_commands,
    _is_loopback_like_device,
    _parse_dshow_audio_devices,
    _sorted_capture_devices,
    is_probably_silent_wav,
)

CaptureAttemptInfo = LegacyCaptureAttemptInfo
CaptureDeviceInfo = LegacyCaptureDeviceInfo
CaptureStartInfo = LegacyCaptureStartInfo
FfmpegSystemAudioRecorder = LegacyDshowCaptureRecorder

__all__ = [
    "CaptureAttemptInfo",
    "CaptureDeviceInfo",
    "CaptureStartInfo",
    "FfmpegSystemAudioRecorder",
    "LegacyCaptureAttemptInfo",
    "LegacyCaptureDeviceInfo",
    "LegacyCaptureStartInfo",
    "LegacyDshowCaptureRecorder",
    "_capture_commands",
    "_is_loopback_like_device",
    "_parse_dshow_audio_devices",
    "_sorted_capture_devices",
    "is_probably_silent_wav",
]
