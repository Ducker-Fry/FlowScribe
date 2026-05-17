"""Completion notification for the batch queue."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


_BUNDLED_SOUND = Path(__file__).parent / "assets" / "queue-complete.wav"


class QueueNotificationPlayer:

    def __init__(self) -> None:
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

    def play_completion_sound(self) -> None:
        if not _BUNDLED_SOUND.is_file():
            return
        if self._player is None:
            self._audio_output = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(str(_BUNDLED_SOUND)))
        self._player.play()
