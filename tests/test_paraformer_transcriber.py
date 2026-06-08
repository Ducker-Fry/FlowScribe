import sys
import types
import builtins
from pathlib import Path

import pytest

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import MediaItem, PreparedAudio
import flowscribe.providers.transcribe.paraformer as paraformer
from flowscribe.providers.transcribe.paraformer import (
    ParaformerTranscriber,
    ensure_funasr_runtime_importable,
    validate_paraformer_runtime,
)


def test_paraformer_transcriber_maps_top_level_text(monkeypatch, tmp_path: Path) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=12.5)
    fake_models = _install_fake_funasr(monkeypatch, [{"text": "hello zh"}])
    _install_fake_paraformer_components(monkeypatch, tmp_path)

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
    _install_fake_paraformer_components(monkeypatch, tmp_path)

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
    _install_fake_paraformer_components(monkeypatch, tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    monkeypatch.setattr(
        ParaformerTranscriber,
        "_probe_wave_duration_seconds",
        staticmethod(lambda path: 5.5),
    )
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
    _install_fake_paraformer_components(monkeypatch, tmp_path)
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
    monkeypatch.setattr(
        ParaformerTranscriber,
        "_probe_wave_duration_seconds",
        staticmethod(lambda path: 5.5),
    )

    ParaformerTranscriber(language="zh").transcribe_clip(
        audio,
        start_seconds=10.0,
        end_seconds=15.5,
    )

    assert calls[0]["creationflags"] == 123


def test_paraformer_transcribe_clip_retries_negative_dimension_with_accurate_seek(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=30.0)
    _install_fake_paraformer_components(monkeypatch, tmp_path)
    commands = []
    attempts = {"count": 0}

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    def fake_probe(path: Path) -> float | None:
        return 60.2 if path.name.endswith("-retry.wav") else 60.0

    def fake_transcribe(self, clip_audio, *, should_cancel=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TranscriptionError(
                "Paraformer transcription failed for clip: Trying to create tensor "
                "with negative dimension -1: [-1, 516]"
            )
        return _transcript_for_audio(clip_audio, "retry succeeded")

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    monkeypatch.setattr(
        ParaformerTranscriber,
        "_probe_wave_duration_seconds",
        staticmethod(fake_probe),
    )
    monkeypatch.setattr(ParaformerTranscriber, "transcribe", fake_transcribe)

    transcript = ParaformerTranscriber(language="zh").transcribe_clip(
        audio,
        start_seconds=171.0,
        end_seconds=231.0,
    )

    assert transcript.text == "retry succeeded"
    assert attempts["count"] == 2
    assert commands[0][2:6] == ["-ss", "171.000", "-t", "60.000"]
    assert commands[1][2:4] == ["-i", str(audio.path)]
    assert "-af" in commands[1]
    assert "apad=pad_dur=0.200" in commands[1]
    assert commands[1][commands[1].index("-ss") + 1] == "171.000"
    assert commands[1][commands[1].index("-t") + 1] == "60.200"


def test_paraformer_extract_clip_rejects_empty_clip(monkeypatch, tmp_path: Path) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=30.0)
    _install_fake_paraformer_components(monkeypatch, tmp_path)

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    monkeypatch.setattr(
        ParaformerTranscriber,
        "_probe_wave_duration_seconds",
        staticmethod(lambda path: None),
    )

    with pytest.raises(TranscriptionError, match="empty or unreadable clip"):
        ParaformerTranscriber(language="zh")._extract_clip_audio(
            audio,
            start_seconds=10.0,
            end_seconds=15.0,
        )


def test_paraformer_transcribe_clip_subdivides_when_retry_still_hits_negative_dimension(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _redirect_model_dirs(monkeypatch, tmp_path)
    audio = _prepared_audio(tmp_path, duration_seconds=120.0)
    _install_fake_paraformer_components(monkeypatch, tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"clip")

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    def fake_probe(path: Path) -> float | None:
        return 12.2

    def fake_transcribe(self, clip_audio, *, should_cancel=None):
        clip_name = Path(clip_audio.path).name
        if "-part" not in clip_name:
            raise TranscriptionError(
                "Paraformer transcription failed for clip: Trying to create tensor "
                "with negative dimension -1: [-1, 516]"
            )
        return _transcript_for_audio(clip_audio, clip_name)

    monkeypatch.setattr("flowscribe.providers.transcribe.paraformer.subprocess.run", fake_run)
    monkeypatch.setattr(
        ParaformerTranscriber,
        "_probe_wave_duration_seconds",
        staticmethod(fake_probe),
    )
    monkeypatch.setattr(ParaformerTranscriber, "transcribe", fake_transcribe)

    transcript = ParaformerTranscriber(language="zh").transcribe_clip(
        audio,
        start_seconds=81.0,
        end_seconds=111.0,
    )

    assert len(transcript.segments) == 3
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[1].start_seconds == 12.0
    assert transcript.segments[2].start_seconds == 24.0
    assert any("-part1.wav" in str(command[-1]) for command in commands)
    assert any("-part2.wav" in str(command[-1]) for command in commands)
    assert any("-part3.wav" in str(command[-1]) for command in commands)


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


def test_validate_paraformer_runtime_reports_missing_dependency(monkeypatch) -> None:
    real_import = builtins.__import__

    def fail_import(name, *args, **kwargs):
        if name == "funasr":
            raise ImportError("missing funasr")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_import)

    with pytest.raises(TranscriptionError, match="pip install funasr modelscope"):
        validate_paraformer_runtime()


def test_validate_paraformer_runtime_reports_missing_automodel_export(monkeypatch) -> None:
    real_import = builtins.__import__

    def fail_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "funasr" and fromlist and "AutoModel" in fromlist:
            raise ImportError("cannot import name 'AutoModel'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_import)

    with pytest.raises(TranscriptionError, match="pip install funasr modelscope"):
        ensure_funasr_runtime_importable()


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


def _install_fake_paraformer_components(monkeypatch, tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    for name, files in {
        "paraformer-zh": ("configuration.json", "config.yaml", "model.pt", "tokens.json", "am.mvn"),
        "fsmn-vad": ("configuration.json", "config.yaml", "model.pt"),
        "ct-punc": ("configuration.json", "config.yaml", "model.pt"),
    }.items():
        target = model_root / name
        target.mkdir(parents=True, exist_ok=True)
        for file_name in files:
            (target / file_name).write_text("ok", encoding="utf-8")
    monkeypatch.setattr(
        paraformer,
        "paraformer_component_paths",
        lambda ensure_download=True: (
            (model_root / "paraformer-zh").resolve(),
            (model_root / "fsmn-vad").resolve(),
            (model_root / "ct-punc").resolve(),
        ),
    )


def _transcript_for_audio(audio: PreparedAudio, text: str):
    from flowscribe.core.models import Transcript, TranscriptSegment

    return Transcript(
        source=audio.source,
        segments=(
            TranscriptSegment(
                text=text,
                start_seconds=0.0,
                end_seconds=audio.duration_seconds,
            ),
        ),
        language="zh",
        model_name="paraformer-zh",
    )
