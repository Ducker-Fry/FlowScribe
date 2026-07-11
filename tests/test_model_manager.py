from __future__ import annotations

import json
from pathlib import Path

import pytest

from flowscribe.config.resources import load_install_config
from flowscribe.model_manager import (
    PARAFORMER_MODEL_ID,
    InstalledModelEntry,
    _build_modelscope_progress_callback,
    _download_paraformer_package,
    _missing_paraformer_files,
    _upsert_installed_model,
    paraformer_component_paths,
    list_available_models,
    managed_models_present,
    model_download_guidance,
    runtime_model_reference,
    write_install_config,
)


def test_list_available_models_includes_recommended_small_and_paraformer() -> None:
    entries = list_available_models()
    ids = {entry.model_id for entry in entries}

    assert "small" in ids
    assert PARAFORMER_MODEL_ID in ids
    assert any(entry.model_id == "small" and entry.recommended for entry in entries)


def test_write_install_config_persists_scope_and_paths(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    models_dir = tmp_path / "managed-models"
    docs_dir = tmp_path / "managed-docs"
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(config_dir))

    config_path = write_install_config(
        install_scope="machine",
        models_dir=models_dir,
        docs_dir=docs_dir,
        component_names=("gui", "cli", "docs"),
        allow_implicit_model_download_value=False,
    )

    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["install_scope"] == "machine"
    assert payload["models_dir"] == str(models_dir.resolve())
    assert payload["docs_dir"] == str(docs_dir.resolve())
    assert payload["installed_components"] == ["gui", "cli", "docs"]
    assert payload["allow_implicit_model_download"] is False

    _, config = load_install_config()
    assert config is not None
    assert config.install_scope == "machine"
    assert config.models_dir == models_dir.resolve()
    assert config.docs_dir == docs_dir.resolve()


def test_runtime_model_reference_rejects_missing_packaged_model(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("FLOWSCRIBE_DISABLE_IMPLICIT_MODEL_DOWNLOAD", "1")

    write_install_config(
        install_scope="user",
        models_dir=tmp_path / "models",
        docs_dir=tmp_path / "docs",
        component_names=("gui",),
        allow_implicit_model_download_value=False,
    )

    try:
        runtime_model_reference("local-whisper", "small")
    except Exception as exc:
        assert "is not installed" in str(exc)
        assert "Model Center" in str(exc)
    else:
        raise AssertionError("Expected missing packaged model to raise an error.")


def test_managed_models_present_false_without_installed_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))
    write_install_config(
        install_scope="user",
        models_dir=tmp_path / "models",
        docs_dir=tmp_path / "docs",
        component_names=("gui",),
        allow_implicit_model_download_value=False,
    )

    assert managed_models_present() is False


def test_runtime_model_reference_uses_recorded_custom_model_path(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    custom_models_dir = tmp_path / "custom-models"
    custom_models_dir.mkdir(parents=True)
    installed_path = custom_models_dir / "small"
    installed_path.mkdir()
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("FLOWSCRIBE_DISABLE_IMPLICIT_MODEL_DOWNLOAD", "1")

    write_install_config(
        install_scope="user",
        models_dir=tmp_path / "default-models",
        docs_dir=tmp_path / "docs",
        component_names=("gui",),
        allow_implicit_model_download_value=False,
    )
    _upsert_installed_model(
        InstalledModelEntry(
            model_id="small",
            provider_name="local-whisper",
            display_name="small",
            status="installed",
            path=str(installed_path),
            imported=False,
        ),
        catalog=next(entry for entry in list_available_models() if entry.model_id == "small"),
    )

    assert runtime_model_reference("local-whisper", "small") == str(installed_path.resolve())


def test_paraformer_component_paths_prefers_recorded_custom_root(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    custom_root = tmp_path / "custom-models"
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("FLOWSCRIBE_DISABLE_IMPLICIT_MODEL_DOWNLOAD", "1")

    write_install_config(
        install_scope="user",
        models_dir=tmp_path / "default-models",
        docs_dir=tmp_path / "docs",
        component_names=("gui",),
        allow_implicit_model_download_value=False,
    )

    for name, files in {
        "paraformer-zh": ("configuration.json", "model.pt", "tokens.json", "am.mvn"),
        "fsmn-vad": ("configuration.json", "model.pt"),
        "ct-punc": ("configuration.json", "model.pt"),
    }.items():
        target = custom_root / name
        target.mkdir(parents=True, exist_ok=True)
        for file_name in files:
            (target / file_name).write_text("ok", encoding="utf-8")

    _upsert_installed_model(
        InstalledModelEntry(
            model_id="paraformer-zh",
            provider_name="paraformer",
            display_name="paraformer-zh",
            status="installed",
            path=str((custom_root / "paraformer-zh").resolve()),
            imported=False,
        ),
        catalog=next(entry for entry in list_available_models() if entry.model_id == "paraformer-zh"),
    )

    model_path, vad_path, punc_path = paraformer_component_paths(ensure_download=False)

    assert model_path == (custom_root / "paraformer-zh").resolve()
    assert vad_path == (custom_root / "fsmn-vad").resolve()
    assert punc_path == (custom_root / "ct-punc").resolve()


def test_model_download_guidance_mentions_cli_command() -> None:
    assert "flowscribe model download small" in model_download_guidance("small")
    assert "paraformer-zh" in model_download_guidance(PARAFORMER_MODEL_ID)


def test_missing_paraformer_files_accepts_either_config_name(tmp_path: Path) -> None:
    target = tmp_path / "paraformer-zh"
    target.mkdir()
    (target / "config.yaml").write_text("ok", encoding="utf-8")
    (target / "model.pt").write_text("ok", encoding="utf-8")
    (target / "tokens.json").write_text("ok", encoding="utf-8")
    (target / "am.mvn").write_text("ok", encoding="utf-8")

    assert _missing_paraformer_files(target) == ()


def test_download_paraformer_package_retries_and_rejects_incomplete_download(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict] = []

    class FakeFileDownloadError(Exception):
        pass

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        local_dir = Path(kwargs["local_dir"])
        local_dir.mkdir(parents=True, exist_ok=True)
        if len(calls) == 1:
            raise FakeFileDownloadError("batch failed")
        (local_dir / "configuration.json").write_text("{}", encoding="utf-8")
        return str(local_dir)

    import sys
    import types

    modelscope_module = types.ModuleType("modelscope")
    hub_module = types.ModuleType("modelscope.hub")
    errors_module = types.ModuleType("modelscope.hub.errors")
    errors_module.FileDownloadError = FakeFileDownloadError
    snapshot_module = types.ModuleType("modelscope.hub.snapshot_download")
    snapshot_module.snapshot_download = fake_snapshot_download
    monkeypatch.setitem(sys.modules, "modelscope", modelscope_module)
    monkeypatch.setitem(sys.modules, "modelscope.hub", hub_module)
    monkeypatch.setitem(sys.modules, "modelscope.hub.errors", errors_module)
    monkeypatch.setitem(sys.modules, "modelscope.hub.snapshot_download", snapshot_module)

    with pytest.raises(Exception, match="incomplete after download"):
        _download_paraformer_package(tmp_path / "models", tmp_path / "cache", progress=lambda _: None)

    assert len(calls) >= 2
    assert calls[0]["allow_patterns"]
    assert calls[1]["max_workers"] == 1


def test_build_modelscope_progress_callback_returns_callback_class() -> None:
    messages: list[str] = []

    callback_cls = _build_modelscope_progress_callback("paraformer", messages.append)
    callback = callback_cls("model.pt", 100)
    callback.update(50)
    callback.end()

    assert messages
    assert any("model.pt" in message for message in messages)
