import sys
import types
from pathlib import Path

import pytest

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import MediaItem, PreparedAudio
import flowscribe.providers.transcribe.paraformer as paraformer
from flowscribe.providers.transcribe.paraformer import ParaformerTranscriber


def test_paraformer_transcriber_maps_top_level_text(monkeypatch, tmp_path: Path) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=12.5)
    fake_models = _install_fake_funasr(monkeypatch, [{"text": "hello zh"}])
    fake_downloads = _install_fake_modelscope(monkeypatch)

    transcript = ParaformerTranscriber(language="zh").transcribe(audio)

    assert transcript.text == "hello zh"
    assert transcript.language == "zh"
    assert transcript.model_name == "paraformer-zh"
    assert transcript.options is not None
    assert transcript.options.provider_name == "paraformer"
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 12.5
    assert Path(fake_models[0].kwargs["model"]).parts[-2:] == ("models", "paraformer-zh")
    assert Path(fake_models[0].kwargs["vad_model"]).parts[-2:] == ("models", "fsmn-vad")
    assert Path(fake_models[0].kwargs["punc_model"]).parts[-2:] == ("models", "ct-punc")
    assert fake_models[0].kwargs["disable_update"] is True
    assert [Path(item["local_dir"]).parts[-2:] for item in fake_downloads] == [
        ("models", "paraformer-zh"),
        ("models", "fsmn-vad"),
        ("models", "ct-punc"),
    ]


def test_paraformer_transcriber_maps_sentence_info(monkeypatch, tmp_path: Path) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path)
    _install_fake_funasr(
        monkeypatch,
        [
            {
                "text": "ignored when sentence_info exists",
                "sentence_info": [
                    {"text": "sentence one", "start": 0, "end": 1500},
                    {"text": "sentence two", "start": 1500, "end": 3200},
                ],
            }
        ],
    )
    _install_fake_modelscope(monkeypatch)

    transcript = ParaformerTranscriber(language="zh").transcribe(audio)

    assert [segment.text for segment in transcript.segments] == ["sentence one", "sentence two"]
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 1.5
    assert transcript.segments[1].start_seconds == 1.5
    assert transcript.segments[1].end_seconds == 3.2


def test_paraformer_transcribe_clip_slices_audio_and_maps_local_timestamps(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=30.0)
    fake_models = _install_fake_funasr(monkeypatch, [{"text": "clip text"}])
    _install_fake_modelscope(monkeypatch)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    transcriber = ParaformerTranscriber(language="zh")

    transcript = transcriber.transcribe_clip(audio, start_seconds=10.0, end_seconds=15.5)

    assert transcript.text == "clip text"
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 5.5
    assert fake_models[0].generate_kwargs["input"].endswith(".wav")
    assert commands[0][commands[0].index("-ss") + 1] == "10.000"
    assert commands[0][commands[0].index("-t") + 1] == "5.500"
    assert not Path(fake_models[0].generate_kwargs["input"]).exists()


def test_paraformer_clip_uses_hidden_subprocess_kwargs(monkeypatch, tmp_path: Path) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=30.0)
    _install_fake_funasr(monkeypatch, [{"text": "clip text"}])
    _install_fake_modelscope(monkeypatch)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(kwargs)
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    monkeypatch.setattr(
        "flowscribe.providers.transcribe.paraformer.hidden_subprocess_kwargs",
        lambda: {"creationflags": 123},
    )

    ParaformerTranscriber(language="zh").transcribe_clip(
        audio,
        start_seconds=10.0,
        end_seconds=15.5,
    )

    assert calls[0]["creationflags"] == 123


def test_default_models_root_uses_executable_dir_for_frozen_build(monkeypatch) -> None:
    monkeypatch.setattr(paraformer.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paraformer.sys, "executable", r"E:\Software\FlowScribeGUI\FlowScribeGUI.exe")

    assert paraformer._default_models_root() == Path(r"E:\Software\FlowScribeGUI\models")


def test_default_external_model_cache_root_prefers_local_appdata(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\TestUser\AppData\Local")

    assert paraformer._default_external_model_cache_root() == Path(
        r"C:\Users\TestUser\AppData\Local\FlowScribe\model-cache"
    )


def test_default_external_model_cache_root_falls_back_to_home(monkeypatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(paraformer.Path, "home", staticmethod(lambda: Path(r"C:\Users\TestUser")))

    assert paraformer._default_external_model_cache_root() == Path(
        r"C:\Users\TestUser\.flowscribe\model-cache"
    )


def test_paraformer_transcriber_reports_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    audio = _prepared_audio(tmp_path)

    def fail_load_model(self):
        raise ImportError("missing funasr")

    monkeypatch.setattr(ParaformerTranscriber, "_load_model", fail_load_model)

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


def _redirect_model_dirs(monkeypatch, tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    monkeypatch.setenv("FLOWSCRIBE_DISABLE_IMPLICIT_MODEL_DOWNLOAD", "0")
    monkeypatch.delenv("FLOWSCRIBE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(paraformer, "MODELS_ROOT", model_root)
    monkeypatch.setattr(paraformer, "PARAFORMER_MODEL_DIR", model_root / "paraformer-zh")
    monkeypatch.setattr(paraformer, "PARAFORMER_VAD_MODEL_DIR", model_root / "fsmn-vad")
    monkeypatch.setattr(paraformer, "PARAFORMER_PUNC_MODEL_DIR", model_root / "ct-punc")


def _install_fake_funasr(monkeypatch, result):
    models = []

    class FakeAutoModel:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            models.append(self)

        def generate(self, **kwargs):
            self.generate_kwargs = kwargs
            return result

    module = types.ModuleType("funasr")
    module.AutoModel = FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", module)
    return models


def _install_fake_modelscope(monkeypatch):
    downloads = []

    def fake_snapshot_download(**kwargs):
        downloads.append(kwargs)
        local_dir = Path(kwargs["local_dir"])
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "configuration.json").write_text("{}", encoding="utf-8")
        return str(local_dir)

    modelscope_module = types.ModuleType("modelscope")
    hub_module = types.ModuleType("modelscope.hub")
    snapshot_module = types.ModuleType("modelscope.hub.snapshot_download")
    snapshot_module.snapshot_download = fake_snapshot_download
    monkeypatch.setitem(sys.modules, "modelscope", modelscope_module)
    monkeypatch.setitem(sys.modules, "modelscope.hub", hub_module)
    monkeypatch.setitem(sys.modules, "modelscope.hub.snapshot_download", snapshot_module)
    return downloads
