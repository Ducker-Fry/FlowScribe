"""Completion notification for the batch queue."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from flowscribe.utils.runtime_layout import resolve_runtime_layout

def _bundled_sound() -> Path:
    layout = resolve_runtime_layout()
    candidates = (
        layout.code_dir / "flowscribe" / "gui" / "assets" / "queue-complete.wav",
        layout.app_root / "flowscribe" / "gui" / "assets" / "queue-complete.wav",
        Path(__file__).parent / "assets" / "queue-complete.wav",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(__file__).parent / "assets" / "queue-complete.wav"


class QueueNotificationPlayer:

    def __init__(self) -> None:
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

    def play_completion_sound(self) -> None:
        bundled_sound = _bundled_sound()
        if not bundled_sound.is_file():
            return
        if self._player is None:
            self._audio_output = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(str(bundled_sound)))
        self._player.play()
