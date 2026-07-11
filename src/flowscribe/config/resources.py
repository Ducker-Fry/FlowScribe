"""Shared installation/resource configuration for packaged and source builds."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from flowscribe.utils.runtime_layout import resolve_runtime_layout

InstallScope = Literal["user", "machine"]

INSTALL_CONFIG_FILENAME = "install-config.json"


@dataclass(frozen=True)
class InstalledModelEntry:
    model_id: str
    provider_name: str
    display_name: str
    status: str = "installed"
    path: str | None = None
    imported: bool = False
    size_bytes: int | None = None


@dataclass(frozen=True)
class InstallConfig:
    install_scope: InstallScope
    models_dir: Path
    docs_dir: Path
    installed_components: tuple[str, ...] = ()
    installed_models: tuple[InstalledModelEntry, ...] = ()
    allow_implicit_model_download: bool = False


@dataclass(frozen=True)
class ResourcePaths:
    config_path: Path | None
    resource_root: Path
    models_dir: Path
    model_cache_dir: Path
    docs_dir: Path
    install_config: InstallConfig | None


def _portable_root() -> Path | None:
    layout = resolve_runtime_layout()
    if layout.frozen:
        return layout.app_root
    return None


def _source_project_root() -> Path:
    return resolve_runtime_layout().source_root


def _default_user_resource_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "FlowScribe"
    return Path.home() / ".flowscribe"


def _default_machine_resource_root() -> Path:
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        return Path(program_data) / "FlowScribe"
    return _default_user_resource_root()


def _config_search_paths() -> tuple[Path, ...]:
    env_dir = os.environ.get("FLOWSCRIBE_CONFIG_DIR")
    if env_dir:
        return (Path(env_dir).expanduser() / INSTALL_CONFIG_FILENAME,)
    return (
        _default_user_resource_root() / INSTALL_CONFIG_FILENAME,
        _default_machine_resource_root() / INSTALL_CONFIG_FILENAME,
    )


def load_install_config() -> tuple[Path | None, InstallConfig | None]:
    for candidate in _config_search_paths():
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        config = _install_config_from_payload(payload)
        if config is not None:
            return candidate, config
    return None, None


def save_install_config(config: InstallConfig, *, config_path: Path | None = None) -> Path:
    target = config_path
    if target is None:
        env_dir = os.environ.get("FLOWSCRIBE_CONFIG_DIR")
        if env_dir:
            target = Path(env_dir).expanduser() / INSTALL_CONFIG_FILENAME
        else:
            root = (
                _default_machine_resource_root()
                if config.install_scope == "machine"
                else _default_user_resource_root()
            )
            target = root / INSTALL_CONFIG_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "install_scope": config.install_scope,
        "models_dir": str(config.models_dir),
        "docs_dir": str(config.docs_dir),
        "installed_components": list(config.installed_components),
        "installed_models": [asdict(entry) for entry in config.installed_models],
        "allow_implicit_model_download": config.allow_implicit_model_download,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def resolve_resource_paths() -> ResourcePaths:
    config_path, install_config = load_install_config()
    if install_config is not None:
        models_dir = Path(os.environ.get("FLOWSCRIBE_MODELS_DIR") or install_config.models_dir).expanduser()
        docs_dir = Path(os.environ.get("FLOWSCRIBE_DOCS_DIR") or install_config.docs_dir).expanduser()
        model_cache_dir = Path(
            os.environ.get("FLOWSCRIBE_MODEL_CACHE_DIR") or models_dir.parent / "model-cache"
        ).expanduser()
        return ResourcePaths(
            config_path=config_path,
            resource_root=models_dir.parent,
            models_dir=models_dir,
            model_cache_dir=model_cache_dir,
            docs_dir=docs_dir,
            install_config=install_config,
        )

    portable_root = _portable_root()
    if portable_root is not None:
        models_dir = Path(os.environ.get("FLOWSCRIBE_MODELS_DIR") or portable_root / "models").expanduser()
        docs_dir = Path(os.environ.get("FLOWSCRIBE_DOCS_DIR") or portable_root / "docs").expanduser()
        model_cache_dir = Path(
            os.environ.get("FLOWSCRIBE_MODEL_CACHE_DIR") or portable_root / "model-cache"
        ).expanduser()
        return ResourcePaths(
            config_path=None,
            resource_root=portable_root,
            models_dir=models_dir,
            model_cache_dir=model_cache_dir,
            docs_dir=docs_dir,
            install_config=None,
        )

    project_root = _source_project_root()
    models_dir = Path(os.environ.get("FLOWSCRIBE_MODELS_DIR") or project_root / "models").expanduser()
    docs_dir = Path(os.environ.get("FLOWSCRIBE_DOCS_DIR") or project_root / "docs").expanduser()
    model_cache_dir = Path(
        os.environ.get("FLOWSCRIBE_MODEL_CACHE_DIR") or _default_user_resource_root() / "model-cache"
    ).expanduser()
    return ResourcePaths(
        config_path=None,
        resource_root=project_root,
        models_dir=models_dir,
        model_cache_dir=model_cache_dir,
        docs_dir=docs_dir,
        install_config=None,
    )


def allow_implicit_model_download() -> bool:
    env_value = os.environ.get("FLOWSCRIBE_DISABLE_IMPLICIT_MODEL_DOWNLOAD")
    if env_value is not None:
        return env_value.strip() not in {"1", "true", "TRUE", "yes", "YES"}
    _, config = load_install_config()
    if config is not None:
        return config.allow_implicit_model_download
    return True


def update_installed_models(entries: tuple[InstalledModelEntry, ...]) -> None:
    config_path, config = load_install_config()
    if config is None:
        return
    save_install_config(
        InstallConfig(
            install_scope=config.install_scope,
            models_dir=config.models_dir,
            docs_dir=config.docs_dir,
            installed_components=config.installed_components,
            installed_models=entries,
            allow_implicit_model_download=config.allow_implicit_model_download,
        ),
        config_path=config_path,
    )


def _install_config_from_payload(payload: object) -> InstallConfig | None:
    if not isinstance(payload, dict):
        return None
    install_scope = payload.get("install_scope")
    if install_scope not in {"user", "machine"}:
        install_scope = "user"
    models_dir = payload.get("models_dir")
    docs_dir = payload.get("docs_dir")
    if not isinstance(models_dir, str) or not models_dir.strip():
        return None
    if not isinstance(docs_dir, str) or not docs_dir.strip():
        return None
    installed_components = tuple(
        str(item)
        for item in payload.get("installed_components", ())
        if isinstance(item, str) and item.strip()
    )
    installed_models: list[InstalledModelEntry] = []
    for raw_item in payload.get("installed_models", ()) or ():
        if not isinstance(raw_item, dict):
            continue
        model_id = raw_item.get("model_id")
        provider_name = raw_item.get("provider_name")
        display_name = raw_item.get("display_name")
        if not all(isinstance(value, str) and value.strip() for value in (model_id, provider_name, display_name)):
            continue
        installed_models.append(
            InstalledModelEntry(
                model_id=model_id.strip(),
                provider_name=provider_name.strip(),
                display_name=display_name.strip(),
                status=str(raw_item.get("status") or "installed"),
                path=str(raw_item.get("path")) if raw_item.get("path") else None,
                imported=bool(raw_item.get("imported", False)),
                size_bytes=int(raw_item["size_bytes"]) if isinstance(raw_item.get("size_bytes"), int) else None,
            )
        )
    return InstallConfig(
        install_scope=install_scope,
        models_dir=Path(models_dir).expanduser(),
        docs_dir=Path(docs_dir).expanduser(),
        installed_components=installed_components,
        installed_models=tuple(installed_models),
        allow_implicit_model_download=bool(payload.get("allow_implicit_model_download", False)),
    )
