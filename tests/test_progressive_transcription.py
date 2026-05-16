from pathlib import Path
import threading

from flowscribe.core.models import MediaItem, OutputArtifacts, PreparedAudio, Transcript, TranscriptSegment
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.progressive import (
    FixedDurationChunkPlanner,
    MediaDurationInfo,
    ProgressiveChunkCache,
    ProgressiveTranscriptionExecutor,
)


class FakeClipTranscriber:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def transcribe(self, audio: PreparedAudio) -> Transcript:  # pragma: no cover - compatibility only
        return Transcript(source=audio.source, segments=(TranscriptSegment(text="full"),))

    def transcribe_clip(
        self,
        audio: PreparedAudio,
        *,
        start_seconds: float,
        end_seconds: float,
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
        ) -> Transcript:
            with self.lock:
                type(self).call_count += 1
            return super().transcribe_clip(audio, start_seconds=start_seconds, end_seconds=end_seconds)

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
