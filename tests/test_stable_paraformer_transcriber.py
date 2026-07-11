import sys
import types
from pathlib import Path

from flowscribe.core.models import MediaItem, PreparedAudio
from flowscribe.providers.transcribe import stable_paraformer
from flowscribe.providers.transcribe.stable_paraformer import StableParaformerTranscriber


def test_stable_paraformer_clip_model_omits_nested_vad(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    model_dir = tmp_path / "paraformer-zh"
    punc_dir = tmp_path / "ct-punc"
    vad_dir = tmp_path / "fsmn-vad"

    class FakeAutoModel:
        def __init__(self, **kwargs) -> None:
            captured["kwargs"] = kwargs

    module = types.ModuleType("funasr")
    module.AutoModel = FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", module)
    monkeypatch.setattr(stable_paraformer, "_ASR_ONLY_MODEL_CACHE", {})
    monkeypatch.setattr(
        stable_paraformer,
        "paraformer_component_paths",
        lambda ensure_download=True: (model_dir, vad_dir, punc_dir),
    )
    monkeypatch.setattr(stable_paraformer, "runtime_model_reference", lambda *args: None)
    monkeypatch.setattr(
        StableParaformerTranscriber,
        "_configure_external_model_cache",
        staticmethod(lambda: None),
    )
    monkeypatch.setattr(StableParaformerTranscriber, "_resolve_device", staticmethod(lambda: "cpu"))

    StableParaformerTranscriber(language="zh")._load_clip_model()

    assert captured["kwargs"]["model"] == str(model_dir)
    assert captured["kwargs"]["punc_model"] == str(punc_dir)
    assert "vad_model" not in captured["kwargs"]


def test_stable_paraformer_clip_generate_uses_asr_only_kwargs(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    clip_path = tmp_path / "clip.wav"
    clip_path.write_bytes(b"clip")
    source = MediaItem(path=tmp_path / "sample.mp4")
    audio = PreparedAudio(
        source=source,
        path=tmp_path / "prepared.wav",
        sample_rate=16000,
        duration_seconds=30.0,
    )
    clip_audio = PreparedAudio(
        source=source,
        path=clip_path,
        sample_rate=16000,
        duration_seconds=30.2,
    )

    class FakeModel:
        def generate(self, **kwargs):
            captured["kwargs"] = kwargs
            return [{"text": "识别成功"}]

    monkeypatch.setattr(
        StableParaformerTranscriber,
        "_extract_clip_audio",
        lambda self, *args, **kwargs: clip_audio,
    )
    monkeypatch.setattr(StableParaformerTranscriber, "_load_clip_model", lambda self: FakeModel())

    transcript = StableParaformerTranscriber(language="zh").transcribe_clip(
        audio,
        start_seconds=0.0,
        end_seconds=30.0,
    )

    assert transcript.text == "识别成功"
    assert captured["kwargs"]["batch_size"] == 1
    assert captured["kwargs"]["disable_pbar"] is True
    assert "return_sentence" not in captured["kwargs"]
    assert "sentence_timestamp" not in captured["kwargs"]
    assert not clip_path.exists()
