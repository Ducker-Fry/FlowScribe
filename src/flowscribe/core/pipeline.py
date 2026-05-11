"""Pipeline orchestration for local media transcription."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.core.ports import ArtifactWriter, MediaPreparer, Transcriber


class LocalTranscriptionPipeline:
    def __init__(
        self,
        *,
        media_preparer: MediaPreparer,
        transcriber: Transcriber,
        artifact_writer: ArtifactWriter,
        work_dir: Path,
        output_dir: Path,
        keep_audio: bool = False,
    ) -> None:
        self._media_preparer = media_preparer
        self._transcriber = transcriber
        self._artifact_writer = artifact_writer
        self._work_dir = work_dir
        self._output_dir = output_dir
        self._keep_audio = keep_audio

    def process(self, item: MediaItem) -> OutputArtifacts:
        item_work_dir = self._work_dir / item.path.stem
        prepared_audio = self._media_preparer.prepare(item, item_work_dir)
        try:
            transcript = self._transcriber.transcribe(prepared_audio)
            return self._artifact_writer.write_all(transcript, self._output_dir)
        finally:
            if not self._keep_audio:
                prepared_audio.path.unlink(missing_ok=True)
