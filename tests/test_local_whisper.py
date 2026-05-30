from pathlib import Path
from types import SimpleNamespace

from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber


ME = "\u6211"
LIKE = "\u559c\u6b22"
MILK = "\u725b\u5976"
MILK_FIRST = "\u725b"
MILK_SECOND = "\u5976"


class FakeWhisperModel:
    def __init__(self) -> None:
        self.kwargs = None

    def transcribe(self, path: str, **kwargs):
        self.kwargs = kwargs
        segments = [
            SimpleNamespace(
                text=" Hello world. ",
                start=0.25,
                end=1.5,
                words=[
                    SimpleNamespace(word=" Hello", start=0.25, end=0.7, probability=0.92),
                    SimpleNamespace(word="world", start=0.72, end=1.2, probability=0.87),
                ],
            )
        ]
        return segments, SimpleNamespace(language="en")


class FakeChineseWhisperModel:
    def __init__(self) -> None:
        self.kwargs = None

    def transcribe(self, path: str, **kwargs):
        self.kwargs = kwargs
        segments = [
            SimpleNamespace(
                text=f" {ME}{LIKE}{MILK} ",
                start=0.0,
                end=1.0,
                words=[
                    SimpleNamespace(word=ME, start=0.0, end=0.1, probability=0.90),
                    SimpleNamespace(word=LIKE, start=0.1, end=0.4, probability=0.95),
                    SimpleNamespace(word=MILK_FIRST, start=0.4, end=0.6, probability=0.80),
                    SimpleNamespace(word=MILK_SECOND, start=0.6, end=0.8, probability=0.88),
                ],
            )
        ]
        return segments, SimpleNamespace(language="zh")


def test_local_whisper_maps_word_timestamps(monkeypatch, tmp_path: Path) -> None:
    model = FakeWhisperModel()
    transcriber = LocalWhisperTranscriber(
        model_name="tiny",
        language="en",
        word_timestamps=True,
    )
    monkeypatch.setattr(transcriber, "_load_model", lambda: model)
    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "video.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
    )

    transcript = transcriber.transcribe(audio)

    assert model.kwargs["word_timestamps"] is True
    assert transcript.options is not None
    assert transcript.options.word_timestamps is True
    assert transcript.segments[0].words[0].text == "Hello"
    assert transcript.segments[0].words[0].start_seconds == 0.25
    assert transcript.segments[0].words[0].end_seconds == 0.7
    assert transcript.segments[0].words[0].confidence == 0.92


def test_local_whisper_omits_words_when_disabled(monkeypatch, tmp_path: Path) -> None:
    model = FakeWhisperModel()
    transcriber = LocalWhisperTranscriber(model_name="tiny", word_timestamps=False)
    monkeypatch.setattr(transcriber, "_load_model", lambda: model)
    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "video.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
    )

    transcript = transcriber.transcribe(audio)

    assert model.kwargs["word_timestamps"] is False
    assert transcript.segments[0].words == ()


def test_local_whisper_aligns_chinese_raw_words(monkeypatch, tmp_path: Path) -> None:
    model = FakeChineseWhisperModel()
    transcriber = LocalWhisperTranscriber(model_name="tiny", word_timestamps=True)
    monkeypatch.setattr(transcriber, "_load_model", lambda: model)
    monkeypatch.setattr(
        "flowscribe.providers.transcribe.local_whisper.align_chinese_words",
        lambda text, raw_words: (
            raw_words[0],
            raw_words[1],
            type(raw_words[0])(
                MILK,
                raw_words[2].start_seconds,
                raw_words[3].end_seconds,
                0.84,
            ),
        ),
    )
    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "video.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
    )

    transcript = transcriber.transcribe(audio)
    segment = transcript.segments[0]

    assert [word.text for word in segment.raw_words] == [ME, LIKE, MILK_FIRST, MILK_SECOND]
    assert [word.text for word in segment.words] == [ME, LIKE, MILK]
    assert segment.words[2].start_seconds == 0.4
    assert segment.words[2].end_seconds == 0.8


def test_local_whisper_transcribe_clip_passes_clip_timestamps(monkeypatch, tmp_path: Path) -> None:
    model = FakeWhisperModel()
    transcriber = LocalWhisperTranscriber(model_name="tiny", language="en")
    monkeypatch.setattr(transcriber, "_load_model", lambda: model)
    audio = PreparedAudio(
        source=MediaItem(path=tmp_path / "video.mp4"),
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
    )

    transcript = transcriber.transcribe_clip(audio, start_seconds=12.0, end_seconds=24.5)

    assert model.kwargs["clip_timestamps"] == [12.0, 24.5]
    assert transcript.segments[0].text == "Hello world."
