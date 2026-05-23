from pathlib import Path
import threading

import pytest

from flowscribe.core.models import MediaItem, OutputArtifacts, PreparedAudio, Transcript, TranscriptSegment
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.progressive import (
    CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS,
    FixedDurationChunkPlanner,
    MediaDurationInfo,
    ProgressiveTranscriptConsistencyChecker,
    ProgressiveChunkCache,
    ProgressiveTranscriptionExecutor,
    tuned_chunk_overlap_seconds,
)
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.transcript.reexport import reexport_transcript_json


class FakeClipTranscriber:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def transcribe(self, audio: PreparedAudio, *, should_cancel=None) -> Transcript:  # pragma: no cover - compatibility only
        return Transcript(source=audio.source, segments=(TranscriptSegment(text="full"),))

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
        should_cancel=None,
    ) -> Transcript:
        self.calls.append((start_seconds, end_seconds))
        if start_seconds == 0.0:
            segments = (
                TranscriptSegment(text="first core", start_seconds=0.0, end_seconds=28.0),
                TranscriptSegment(text="boundary", start_seconds=28.0, end_seconds=30.0),
            )
        else:
            segments = (
                TranscriptSegment(text="boundary", start_seconds=27.0, end_seconds=30.0),
                TranscriptSegment(text="second core", start_seconds=30.0, end_seconds=55.0),
            )
        return Transcript(source=audio.source, segments=segments, language="en", model_name="tiny")

    def fork_for_worker(self):
        return FakeClipTranscriber()


class FakePreparer:
    def prepare(self, item: MediaItem, work_dir: Path) -> PreparedAudio:
        work_dir.mkdir(parents=True, exist_ok=True)
        audio = work_dir / "prepared.wav"
        audio.write_bytes(b"wav")
        return PreparedAudio(
            source=item,
            path=audio,
            sample_rate=16000,
            duration_seconds=55.0,
        )


class FakeArtifactWriter:
    def write_all(self, transcript: Transcript, output_dir: Path) -> OutputArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        txt = output_dir / "sample.txt"
        txt.write_text(transcript.text, encoding="utf-8")
        return OutputArtifacts(paths=(txt,))


def test_fixed_duration_chunk_planner_uses_overlap() -> None:
    duration_info = MediaDurationInfo(
        source=MediaItem(path=Path("sample.mp4")),
        prepared_audio_path=Path("sample.wav"),
        sample_rate=16000,
        duration_seconds=65.0,
    )

    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(duration_info)

    assert [(chunk.index, chunk.start_seconds, chunk.end_seconds) for chunk in plan.chunks] == [
        (1, 0.0, 30.0),
        (2, 27.0, 57.0),
        (3, 54.0, 65.0),
    ]


def test_progressive_executor_trims_leading_overlap_duplicates(tmp_path: Path) -> None:
    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=55.0,
    )
    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(
        MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=55.0,
        )
    )

    state = ProgressiveTranscriptionExecutor(transcriber=FakeClipTranscriber()).execute(audio, plan)

    assert [segment.text for segment in state.transcript.segments] == [
        "first core",
        "boundary",
        "second core",
    ]
    assert state.processed_duration_seconds == 55.0
    assert state.completed_chunks == 2


def test_pipeline_process_progressive_writes_merged_transcript(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    pipeline = LocalTranscriptionPipeline(
        media_preparer=FakePreparer(),
        transcriber=FakeClipTranscriber(),
        artifact_writer=FakeArtifactWriter(),
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        keep_audio=False,
    )

    artifacts, state = pipeline.process_progressive(
        item,
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    )

    assert artifacts.txt_path is not None
    assert artifacts.txt_path.read_text(encoding="utf-8") == "first core\nboundary\nsecond core"
    assert state.transcript.text == "first core\nboundary\nsecond core"
    assert not (tmp_path / "work" / "sample" / "prepared.wav").exists()


def test_progressive_cache_persists_plan_results_and_partial_transcript(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    audio = PreparedAudio(
        source=item,
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=55.0,
    )
    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(
        MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=55.0,
        )
    )
    cache = ProgressiveChunkCache(tmp_path / ".progressive")

    state = ProgressiveTranscriptionExecutor(transcriber=FakeClipTranscriber()).execute(
        audio,
        plan,
        cache_store=cache,
        resume=False,
    )

    assert (cache.cache_dir / "chunk-plan.json").exists()
    assert (cache.cache_dir / "state.json").exists()
    assert (cache.cache_dir / "partial-transcript.json").exists()
    assert (cache.cache_dir / "chunk-results" / "chunk-0001.json").exists()
    cached_results = cache.load_completed_results(plan)
    assert sorted(cached_results) == [1, 2]
    assert state.cache_dir == cache.cache_dir


def test_progressive_executor_resume_skips_completed_chunks(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    audio = PreparedAudio(
        source=item,
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=55.0,
    )
    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(
        MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=55.0,
        )
    )
    cache = ProgressiveChunkCache(tmp_path / ".progressive")
    first_transcriber = FakeClipTranscriber()
    ProgressiveTranscriptionExecutor(transcriber=first_transcriber).execute(
        audio,
        plan,
        cache_store=cache,
        resume=False,
    )

    resumed_transcriber = FakeClipTranscriber()
    resumed_state = ProgressiveTranscriptionExecutor(transcriber=resumed_transcriber).execute(
        audio,
        plan,
        cache_store=cache,
        resume=True,
    )

    assert resumed_transcriber.calls == []
    assert resumed_state.transcript.text == "first core\nboundary\nsecond core"


def test_pipeline_can_clear_progressive_cache(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    transcriber = FakeClipTranscriber()
    pipeline = LocalTranscriptionPipeline(
        media_preparer=FakePreparer(),
        transcriber=transcriber,
        artifact_writer=FakeArtifactWriter(),
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        keep_audio=False,
    )

    _, state = pipeline.process_progressive(item)
    assert state.cache_dir is not None
    assert state.cache_dir.exists()

    pipeline.clear_progressive_cache(item)

    assert not state.cache_dir.exists()


def test_progressive_executor_parallel_workers_keep_ordered_merge(tmp_path: Path) -> None:
    class SlowParallelTranscriber(FakeClipTranscriber):
        lock = threading.Lock()
        call_count = 0

        def transcribe_clip(
            self,
            audio: PreparedAudio,
            *,
            start_seconds: float,
            end_seconds: float,
            should_cancel=None,
        ) -> Transcript:
            with self.lock:
                type(self).call_count += 1
            return super().transcribe_clip(audio, start_seconds=start_seconds, end_seconds=end_seconds, should_cancel=should_cancel)

        def fork_for_worker(self):
            return SlowParallelTranscriber()

    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=55.0,
    )
    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(
        MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=55.0,
        )
    )

    state = ProgressiveTranscriptionExecutor(transcriber=SlowParallelTranscriber()).execute(
        audio,
        plan,
        max_workers=2,
    )

    assert [segment.text for segment in state.transcript.segments] == [
        "first core",
        "boundary",
        "second core",
    ]
    assert SlowParallelTranscriber.call_count >= 2


def test_tuned_chunk_overlap_seconds_uses_more_conservative_default_for_chinese() -> None:
    assert tuned_chunk_overlap_seconds(
        requested_overlap_seconds=3.0,
        language="zh",
        preset=None,
    ) == CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS
    assert tuned_chunk_overlap_seconds(
        requested_overlap_seconds=3.0,
        language=None,
        preset="zh",
    ) == CHINESE_PROGRESSIVE_CHUNK_OVERLAP_SECONDS
    assert tuned_chunk_overlap_seconds(
        requested_overlap_seconds=5.0,
        language="zh",
        preset=None,
    ) == 5.0


def test_progressive_executor_clips_cross_boundary_chinese_segment_start(tmp_path: Path) -> None:
    class FakeChineseTranscriber(FakeClipTranscriber):
        def transcribe_clip(
            self,
            audio: PreparedAudio,
            *,
            start_seconds: float,
            end_seconds: float,
            should_cancel=None,
        ) -> Transcript:
            if start_seconds == 0.0:
                segments = (
                    TranscriptSegment(text="第一句。", start_seconds=0.0, end_seconds=28.0),
                    TranscriptSegment(text="第二句前半", start_seconds=28.0, end_seconds=30.0),
                )
            else:
                segments = (
                    TranscriptSegment(text="第二句前半后半。", start_seconds=29.0, end_seconds=32.0),
                    TranscriptSegment(text="第三句。", start_seconds=32.0, end_seconds=40.0),
                )
            return Transcript(source=audio.source, segments=segments, language="zh", model_name="tiny")

    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=40.0,
    )
    plan = FixedDurationChunkPlanner(
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    ).plan(
        MediaDurationInfo(
            source=audio.source,
            prepared_audio_path=audio.path,
            sample_rate=audio.sample_rate,
            duration_seconds=40.0,
        )
    )

    state = ProgressiveTranscriptionExecutor(transcriber=FakeChineseTranscriber()).execute(audio, plan)

    assert [segment.text for segment in state.transcript.segments] == [
        "第一句。",
        "第二句前半",
        "第二句前半后半。",
        "第三句。",
    ]
    assert state.transcript.segments[2].start_seconds == 30.0


def test_progressive_consistency_checker_rejects_large_segment_overlap(tmp_path: Path) -> None:
    transcript = Transcript(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        segments=(
            TranscriptSegment(text="one", start_seconds=0.0, end_seconds=5.0),
            TranscriptSegment(text="two", start_seconds=1.0, end_seconds=8.0),
        ),
    )

    # Strict mode should reject
    with pytest.raises(Exception, match="overlaps the previous segment too much"):
        ProgressiveTranscriptConsistencyChecker(auto_fix_timestamps=False).validate(transcript)

    # Auto-fix mode should fix the issue
    fixed = ProgressiveTranscriptConsistencyChecker(auto_fix_timestamps=True).validate(transcript)
    assert len(fixed.segments) == 2
    assert fixed.segments[1].start_seconds >= fixed.segments[0].end_seconds - 3.0


def test_progressive_consistency_checker_fixes_backward_timestamps(tmp_path: Path) -> None:
    """Test that auto-fix mode corrects segments that start before previous segment."""
    transcript = Transcript(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        segments=(
            TranscriptSegment(text="one", start_seconds=10.0, end_seconds=15.0),
            TranscriptSegment(text="two", start_seconds=8.0, end_seconds=18.0),
        ),
    )

    # Strict mode should reject
    with pytest.raises(Exception, match="starts before the previous segment"):
        ProgressiveTranscriptConsistencyChecker(auto_fix_timestamps=False).validate(transcript)

    # Auto-fix mode should fix by using previous segment's start as minimum
    fixed = ProgressiveTranscriptConsistencyChecker(auto_fix_timestamps=True).validate(transcript)
    assert len(fixed.segments) == 2
    assert fixed.segments[1].start_seconds == 10.0  # Fixed to previous segment's start
    assert fixed.segments[1].end_seconds == 18.0  # End unchanged


def test_pipeline_process_progressive_json_stays_reexportable(tmp_path: Path) -> None:
    item = MediaItem(path=tmp_path / "sample.mp4")
    pipeline = LocalTranscriptionPipeline(
        media_preparer=FakePreparer(),
        transcriber=FakeClipTranscriber(),
        artifact_writer=TranscriptArtifactWriter(
            formats=("txt", "json"),
            txt_writer=TxtTranscriptWriter(OutputPathBuilder(overwrite=True)),
            json_writer=JsonTranscriptWriter(OutputPathBuilder(overwrite=True)),
            md_writer=MarkdownTranscriptWriter(OutputPathBuilder(overwrite=True)),
        ),
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        keep_audio=False,
    )

    artifacts, state = pipeline.process_progressive(
        item,
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    )

    json_path = next(path for path in artifacts.paths if path.suffix == ".json")
    exported = reexport_transcript_json(
        json_path,
        output_dir=tmp_path / "exports",
        output_formats=("txt", "md", "json", "srt", "vtt"),
        overwrite=True,
        include_timestamps=True,
    )

    assert state.transcript.text == "first core\nboundary\nsecond core"
    assert {path.suffix for path in exported.paths} == {".txt", ".md", ".json", ".srt", ".vtt"}
