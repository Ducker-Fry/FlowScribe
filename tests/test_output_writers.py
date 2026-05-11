from pathlib import Path

from flowscribe.core.models import MediaItem, Transcript, TranscriptSegment, TranscriptionOptions
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.txt_writer import TxtTranscriptWriter


def test_transcript_artifact_writer_writes_txt_and_markdown(tmp_path: Path) -> None:
    source = MediaItem(path=tmp_path / "lesson.mp4")
    transcript = Transcript(
        source=source,
        segments=(TranscriptSegment(text="Hello world."), TranscriptSegment(text="你好，世界。")),
        language="mixed",
        model_name="test-model",
        options=TranscriptionOptions(
            model_name="test-model",
            language="zh",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            initial_prompt="preserve source languages",
            preset="zh",
        ),
    )
    path_builder = OutputPathBuilder(overwrite=True)
    writer = TranscriptArtifactWriter(
        txt_writer=TxtTranscriptWriter(path_builder),
        md_writer=MarkdownTranscriptWriter(path_builder),
    )

    artifacts = writer.write_all(transcript, tmp_path)

    assert artifacts.txt_path.read_text(encoding="utf-8") == "Hello world.\n你好，世界。\n"
    markdown = artifacts.md_path.read_text(encoding="utf-8")
    assert "# lesson" in markdown
    assert "- Task: `transcribe`" in markdown
    assert "- VAD Filter: `True`" in markdown
    assert "- Preset: `zh`" in markdown
    assert "Hello world.\n你好，世界。" in markdown
