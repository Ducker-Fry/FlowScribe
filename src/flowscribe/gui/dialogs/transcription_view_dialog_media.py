from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QFileDialog

from flowscribe.gui.transcript_viewer import (
    transcript_search_hit_seek_seconds,
    transcript_segment_index_for_seconds,
    transcript_segment_seek_seconds,
)


class TranscriptionViewDialogMediaMixin:
    """Media binding and transcript sync helpers for the view dialog."""

    def _bind_media_to_transcript(self) -> None:
        if self._transcript_view is None:
            self.media_status_label.setText("Open a transcript JSON file before binding media.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            "",
            "Media files (*.mp4 *.mp3 *.wav *.m4a *.mkv *.avi *.flac *.ogg *.webm);;All files (*.*)",
        )
        if file_path:
            self._bind_media(Path(file_path))

    def _bind_media(self, media_path: Path) -> None:
        if not media_path.is_file():
            self.media_status_label.setText(f"Media file not found: {media_path}")
            self.media_binding_label.setText("Binding: Failed")
            return

        try:
            self._media_player.setSource(QUrl.fromLocalFile(str(media_path)))
            self.media_binding_label.setText(f"Binding: {media_path.name}")
            self.media_status_label.setText(
                "Media bound successfully. Duration will appear when ready."
            )
            self.play_media_button.setEnabled(True)
            self.media_position_slider.setEnabled(True)
        except Exception as exc:
            self.media_status_label.setText(f"Error binding media: {exc}")
            self.media_binding_label.setText("Binding: Error")

    def _toggle_media_playback(self) -> None:
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
            self.play_media_button.setText("Play")
        else:
            self._media_player.play()
            self.play_media_button.setText("Pause")

    def _seek_media_milliseconds(self, position: int) -> None:
        self._media_player.setPosition(position)

    def _on_media_position_changed(self, position: int) -> None:
        self.media_position_slider.blockSignals(True)
        self.media_position_slider.setValue(position)
        self.media_position_slider.blockSignals(False)
        self._sync_transcript_to_media_position(position)

    def _sync_transcript_to_media_position(self, position_milliseconds: int) -> None:
        if self._transcript_view is None:
            return

        row = transcript_segment_index_for_seconds(
            self._transcript_view,
            position_milliseconds / 1000.0,
        )
        if row is None or row == self._active_segment_row:
            return

        self._active_segment_row = row
        self.transcript_segments.blockSignals(True)
        try:
            self.transcript_segments.setCurrentRow(row)
            item = self.transcript_segments.item(row)
            if item is not None:
                self.transcript_segments.scrollToItem(
                    item,
                    self.transcript_segments.ScrollHint.PositionAtCenter,
                )
        finally:
            self.transcript_segments.blockSignals(False)

    def _on_media_duration_changed(self, duration: int) -> None:
        self.media_position_slider.setRange(0, duration)
        duration_seconds = duration / 1000.0
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        self.media_status_label.setText(f"Media ready. Duration: {minutes}:{seconds:02d}")

    def _on_media_playback_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_media_button.setText("Pause")
        else:
            self.play_media_button.setText("Play")

    def _seek_media_seconds(self, seconds: float, *, autoplay: bool) -> None:
        if not self._media_player.source().isValid():
            return

        self._media_player.setPosition(int(max(0.0, seconds) * 1000))
        if autoplay:
            self._media_player.play()

    def _seek_to_search_hit(self, row: int) -> None:
        if row < 0 or row >= len(self._search_hits):
            return
        self._seek_media_seconds(
            transcript_search_hit_seek_seconds(self._search_hits[row]),
            autoplay=True,
        )

    def _seek_to_segment(self, row: int) -> None:
        if self._transcript_view is None or row >= len(self._transcript_view.segments):
            return
        seek_seconds = transcript_segment_seek_seconds(self._transcript_view.segments[row])
        self._seek_media_seconds(seek_seconds, autoplay=True)

    def _empty_media_source(self) -> QUrl:
        return QUrl()
