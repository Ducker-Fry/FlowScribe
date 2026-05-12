from pathlib import Path
from types import SimpleNamespace

from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


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
