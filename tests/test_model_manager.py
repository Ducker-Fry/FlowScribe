from __future__ import annotations

import json
from pathlib import Path

from flowscribe.config.resources import load_install_config
from flowscribe.model_manager import (
    PARAFORMER_MODEL_ID,
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


def test_model_download_guidance_mentions_cli_command() -> None:
    assert "flowscribe model download small" in model_download_guidance("small")
    assert "paraformer-zh" in model_download_guidance(PARAFORMER_MODEL_ID)
