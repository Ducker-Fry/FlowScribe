"""Shared models for system-audio capture integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaptureDevice:
    """One output device that can participate in system-audio capture."""

    id: str
    name: str
    is_default: bool


@dataclass(frozen=True)
class CaptureSupportStatus:
    """Current helper support status for system-audio capture."""

    supported: bool
    reason: str | None = None
    default_device: CaptureDevice | None = None


@dataclass(frozen=True)
class CaptureEvent:
    """One structured event emitted by the capture helper."""

    event: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CaptureStartResult:
    """Metadata returned after a capture session has started."""

    output_path: Path
    device: CaptureDevice | None = None
    event: CaptureEvent | None = None


@dataclass(frozen=True)
class CaptureCompletedResult:
    """Metadata returned after a capture session has finalized."""

    output_path: Path
    duration_seconds: float | None = None
    event: CaptureEvent | None = None
