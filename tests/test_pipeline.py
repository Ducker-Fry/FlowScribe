from pathlib import Path

from flowscribe.core.models import MediaItem, OutputArtifacts, PreparedAudio, Transcript, TranscriptSegment
from flowscribe.core.pipeline import LocalTranscriptionPipeline


class FakePreparer:
    def prepare(self, item: MediaItem, work_dir: Path) -> PreparedAudio:
        work_dir.mkdir(parents=True)
        audio = work_dir / "prepared.wav"
        audio.write_text("audio", encoding="utf-8")
        return PreparedAudio(source=item, path=audio, sample_rate=16000)


class FakeTranscriber:
    def transcribe(self, audio: PreparedAudio) -> Transcript:
        return Transcript(source=audio.source, segments=(TranscriptSegment(text="transcribed"),))


class FakeArtifactWriter:
    def write_all(self, transcript: Transcript, output_dir: Path) -> OutputArtifacts:
        output_dir.mkdir(parents=True)
        txt = output_dir / "sample.txt"
        md = output_dir / "sample.md"
        txt.write_text(transcript.text, encoding="utf-8")
        md.write_text(transcript.text, encoding="utf-8")
        return OutputArtifacts(paths=(txt, md))


def test_pipeline_processes_item_and_removes_prepared_audio(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    pipeline = LocalTranscriptionPipeline(
        media_preparer=FakePreparer(),
        transcriber=FakeTranscriber(),
        artifact_writer=FakeArtifactWriter(),
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        keep_audio=False,
    )

    artifacts = pipeline.process(item)

    assert artifacts.txt_path is not None
    assert artifacts.txt_path.read_text(encoding="utf-8") == "transcribed"
    assert not (tmp_path / "work" / "sample" / "prepared.wav").exists()


def test_pipeline_applies_transcript_normalizer(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")

    def normalize(transcript: Transcript) -> Transcript:
        return Transcript(
            source=transcript.source,
            segments=(TranscriptSegment(text="normalized"),),
            language=transcript.language,
            model_name=transcript.model_name,
            options=transcript.options,
            created_at=transcript.created_at,
        )

    pipeline = LocalTranscriptionPipeline(
        media_preparer=FakePreparer(),
        transcriber=FakeTranscriber(),
        artifact_writer=FakeArtifactWriter(),
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        keep_audio=False,
        transcript_normalizer=normalize,
    )

    artifacts = pipeline.process(item)

    assert artifacts.txt_path is not None
    assert artifacts.txt_path.read_text(encoding="utf-8") == "normalized"
