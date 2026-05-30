import sys
import types
from pathlib import Path

import pytest

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.providers.transcribe.paraformer import ParaformerTranscriber


def test_paraformer_transcriber_maps_top_level_text(monkeypatch, tmp_path: Path) -> None:
    audio = _prepared_audio(tmp_path, duration_seconds=12.5)
    _install_fake_funasr(monkeypatch, [{"text": "今天我们测试中文转写。"}])

    transcript = ParaformerTranscriber(language="zh").transcribe(audio)

    assert transcript.text == "今天我们测试中文转写。"
    assert transcript.language == "zh"
    assert transcript.model_name == "paraformer-zh"
    assert transcript.options is not None
    assert transcript.options.provider_name == "paraformer"
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 12.5


def test_paraformer_transcriber_maps_sentence_info(monkeypatch, tmp_path: Path) -> None:
    audio = _prepared_audio(tmp_path)
    _install_fake_funasr(
        monkeypatch,
        [
            {
                "text": "ignored when sentence_info exists",
                "sentence_info": [
                    {"text": "第一句。", "start": 0, "end": 1500},
                    {"text": "第二句。", "start": 1500, "end": 3200},
                ],
            }
        ],
    )

    transcript = ParaformerTranscriber(language="zh").transcribe(audio)

    assert [segment.text for segment in transcript.segments] == ["第一句。", "第二句。"]
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 1.5
    assert transcript.segments[1].start_seconds == 1.5
    assert transcript.segments[1].end_seconds == 3.2


def test_paraformer_transcriber_reports_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    audio = _prepared_audio(tmp_path)
    monkeypatch.delitem(sys.modules, "funasr", raising=False)

    with pytest.raises(TranscriptionError, match="pip install funasr modelscope"):
        ParaformerTranscriber().transcribe(audio)


def _prepared_audio(tmp_path: Path, *, duration_seconds: float | None = None) -> PreparedAudio:
    path = tmp_path / "sample.wav"
    path.write_bytes(b"audio")
    return PreparedAudio(
        source=MediaItem(path=tmp_path / "sample.mp4"),
        path=path,
        sample_rate=16000,
        duration_seconds=duration_seconds,
    )


def _install_fake_funasr(monkeypatch, result) -> None:
    class FakeAutoModel:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def generate(self, **kwargs):
            self.generate_kwargs = kwargs
            return result

    module = types.ModuleType("funasr")
    module.AutoModel = FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", module)
