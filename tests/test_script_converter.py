from pathlib import Path

from flowscribe.core.models import MediaItem
from flowscribe.core.models import Transcript, TranscriptSegment, TranscriptWord
from flowscribe.nlp.script_converter import simplify_chinese_transcript


def test_simplify_chinese_transcript_converts_segments_and_words() -> None:
    transcript = Transcript(
        source=MediaItem(path=Path("sample.mp4")),
        language="zh",
        segments=(
            TranscriptSegment(
                text="這裡講到機器學習",
                raw_words=(TranscriptWord(text="這裡"),),
                words=(TranscriptWord(text="機器學習", start_seconds=1.0, end_seconds=2.0),),
            ),
        ),
    )

    converted = simplify_chinese_transcript(transcript)
    segment = converted.segments[0]

    assert segment.text == "这里讲到机器学习"
    assert segment.raw_words[0].text == "这里"
    assert segment.words[0].text == "机器学习"
    assert segment.words[0].start_seconds == 1.0
    assert segment.words[0].end_seconds == 2.0
