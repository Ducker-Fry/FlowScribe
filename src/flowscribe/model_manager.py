"""Shared model registry and download management."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from flowscribe.config.resources import (
    InstallConfig,
    InstalledModelEntry,
    allow_implicit_model_download,
    resolve_resource_paths,
    save_install_config,
    update_installed_models,
)
from flowscribe.core.errors import InputError, TranscriptionError
from flowscribe.model_catalog import resolve_faster_whisper_repo

try:
    from huggingface_hub import snapshot_download as huggingface_snapshot_download
except ImportError:  # pragma: no cover - optional runtime dependency
    huggingface_snapshot_download = None

PARAFORMER_MODEL_ID = "paraformer-zh"
PARAFORMER_MODEL_SOURCE_ID = (
    "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
)
PARAFORMER_VAD_SOURCE_ID = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
PARAFORMER_PUNC_SOURCE_ID = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"


@dataclass(frozen=True)
class ModelCatalogEntry:
    model_id: str
    provider_name: str
    display_name: str
    description: str
    recommended: bool = False
    approx_size_mb: int | None = None
    downloadable: bool = True


@dataclass(frozen=True)
class InstalledModelRecord:
    model_id: str
    provider_name: str
    display_name: str
    status: str
    path: Path | None
    imported: bool = False
    recommended: bool = False
    description: str = ""
    approx_size_mb: int | None = None


MODEL_CATALOG: tuple[ModelCatalogEntry, ...] = (
    ModelCatalogEntry("tiny", "local-whisper", "tiny", "Fastest smoke-test model.", approx_size_mb=75),
    ModelCatalogEntry(
        "base",
        "local-whisper",
        "base",
        "Balanced starter model for small local jobs.",
        approx_size_mb=150,
    ),
    ModelCatalogEntry(
        "small",
        "local-whisper",
        "small",
        "Recommended default model for daily transcription.",
        recommended=True,
        approx_size_mb=500,
    ),
    ModelCatalogEntry("medium", "local-whisper", "medium", "Higher accuracy, slower runtime.", approx_size_mb=1500),
    ModelCatalogEntry(
        "large-v3-turbo",
        "local-whisper",
        "large-v3-turbo",
        "Highest speed among large models with strong accuracy.",
        approx_size_mb=1700,
    ),
    ModelCatalogEntry(
        "large-v3",
        "local-whisper",
        "large-v3",
        "Highest local accuracy, heaviest resource usage.",
        approx_size_mb=3000,
    ),
    ModelCatalogEntry(
        PARAFORMER_MODEL_ID,
        "paraformer",
        "paraformer-zh",
        "Chinese-first FunASR Paraformer package.",
        approx_size_mb=1400,
    ),
)


def list_available_models() -> tuple[ModelCatalogEntry, ...]:
    return MODEL_CATALOG


def list_installed_models() -> tuple[InstalledModelRecord, ...]:
    resources = resolve_resource_paths()
    config = resources.install_config
    entries_by_id = {entry.model_id: entry for entry in MODEL_CATALOG}
    installed: list[InstalledModelRecord] = []
    if config is not None:
        for entry in config.installed_models:
            catalog = entries_by_id.get(entry.model_id)
            record_path = Path(entry.path).expanduser() if entry.path else None
            installed.append(
                InstalledModelRecord(
                    model_id=entry.model_id,
                    provider_name=entry.provider_name,
                    display_name=entry.display_name,
                    status=entry.status,
                    path=record_path.resolve() if record_path is not None and record_path.exists() else record_path,
                    imported=entry.imported,
                    recommended=catalog.recommended if catalog is not None else False,
                    description=catalog.description if catalog is not None else "",
                    approx_size_mb=catalog.approx_size_mb if catalog is not None else entry.size_bytes,
                )
            )
    else:
        for catalog in MODEL_CATALOG:
            inferred_path = installed_model_path(catalog.model_id)
            if inferred_path is not None and inferred_path.exists():
                installed.append(
                    InstalledModelRecord(
                        model_id=catalog.model_id,
                        provider_name=catalog.provider_name,
                        display_name=catalog.display_name,
                        status="installed",
                        path=inferred_path.resolve(),
                        recommended=catalog.recommended,
                        description=catalog.description,
                        approx_size_mb=catalog.approx_size_mb,
                    )
                )
    return tuple(installed)


def installed_model_path(model_id: str) -> Path | None:
    resources = resolve_resource_paths()
    if model_id == PARAFORMER_MODEL_ID:
        target = resources.models_dir / PARAFORMER_MODEL_ID
        return target if target.exists() else None
    repo_id = resolve_faster_whisper_repo(model_id)
    if repo_id is not None:
        target = resources.models_dir / model_id
        return target if target.exists() else None
    for installed in list_installed_models():
        if installed.model_id == model_id and installed.path is not None:
            return installed.path
    return None


def is_model_installed(model_id: str) -> bool:
    target = installed_model_path(model_id)
    return target is not None and target.exists()


def model_download_guidance(model_id: str) -> str:
    if model_id == PARAFORMER_MODEL_ID:
        return "Download it from the Model Center or run `flowscribe model download paraformer-zh`."
    return f"Download it from the Model Center or run `flowscribe model download {model_id}`."


def runtime_model_reference(provider_name: str, model_name: str) -> str:
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return str(model_path.resolve())

    if provider_name == "local-whisper":
        installed = installed_model_path(model_name)
        if installed is not None:
            return str(installed.resolve())
        if allow_implicit_model_download():
            return model_name
        raise TranscriptionError(f"Model `{model_name}` is not installed. {model_download_guidance(model_name)}")

    if provider_name == "paraformer":
        installed = installed_model_path(PARAFORMER_MODEL_ID)
        if installed is not None:
            return model_name or PARAFORMER_MODEL_ID
        if allow_implicit_model_download():
            return model_name or PARAFORMER_MODEL_ID
        raise TranscriptionError(
            "Paraformer model package is not installed. "
            f"{model_download_guidance(PARAFORMER_MODEL_ID)}"
        )

    return model_name


def ensure_runtime_model_available(provider_name: str, model_name: str) -> None:
    runtime_model_reference(provider_name, model_name)


def download_model(
    model_id: str,
    *,
    progress: callable | None = None,
    models_dir: Path | None = None,
) -> InstalledModelRecord:
    catalog = next((entry for entry in MODEL_CATALOG if entry.model_id == model_id), None)
    if catalog is None:
        raise InputError(f"Unknown model id: {model_id}")

    target_root, cache_root = _resolve_download_paths(models_dir)
    resources = resolve_resource_paths()
    cache_root.mkdir(parents=True, exist_ok=True)

    if progress is not None:
        progress(f"Preparing model download: {catalog.display_name}")

    if catalog.provider_name == "local-whisper":
        if huggingface_snapshot_download is None:
            raise TranscriptionError("huggingface_hub is required to download local-whisper models.")
        repo_id = resolve_faster_whisper_repo(model_id)
        if repo_id is None:
            raise TranscriptionError(f"Could not resolve Hugging Face repo for model `{model_id}`.")
        target_dir = target_root / model_id
        if progress is not None:
            progress(f"Downloading {repo_id}...")
        huggingface_snapshot_download(
            repo_id=repo_id,
            local_dir=str(target_dir),
            cache_dir=str(cache_root / "huggingface"),
            local_dir_use_symlinks=False,
        )
        record_path = target_dir
    elif catalog.provider_name == "paraformer":
        if progress is not None:
            progress("Downloading Paraformer model package...")
        _download_paraformer_package(target_root, cache_root, progress=progress)
        record_path = target_root / PARAFORMER_MODEL_ID
    else:
        raise InputError(f"Model `{model_id}` cannot be downloaded automatically.")

    if progress is not None:
        progress(f"Installed model: {catalog.display_name}")
    return _upsert_installed_model(
        InstalledModelEntry(
            model_id=catalog.model_id,
            provider_name=catalog.provider_name,
            display_name=catalog.display_name,
            status="installed",
            path=str(record_path.resolve()),
            imported=False,
            size_bytes=_directory_size_bytes(record_path),
        ),
        catalog=catalog,
    )


def remove_model(model_id: str) -> bool:
    resources = resolve_resource_paths()
    removed = False
    target = installed_model_path(model_id)
    if target is not None and target.exists() and not _is_imported_native_entry(model_id):
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        removed = True
    config = resources.install_config
    if config is not None:
        remaining = tuple(entry for entry in config.installed_models if entry.model_id != model_id)
        if len(remaining) != len(config.installed_models):
            update_installed_models(remaining)
            removed = True
    return removed


def import_native_model(path: Path, *, display_name: str | None = None) -> InstalledModelRecord:
    candidate = path.expanduser().resolve()
    if not candidate.exists() or not candidate.is_file():
        raise InputError(f"Native model file does not exist: {candidate}")
    if candidate.suffix.lower() != ".bin":
        raise InputError("Native model imports must be whisper.cpp ggml .bin files.")
    model_id = f"native:{candidate.stem}"
    display = display_name or candidate.stem
    return _upsert_installed_model(
        InstalledModelEntry(
            model_id=model_id,
            provider_name="native-engine",
            display_name=display,
            status="imported",
            path=str(candidate),
            imported=True,
            size_bytes=candidate.stat().st_size,
        ),
        catalog=None,
    )


def local_docs_index_path() -> Path | None:
    docs_dir = resolve_resource_paths().docs_dir
    for candidate in (docs_dir / "index.html", docs_dir / "model-guide.html"):
        if candidate.exists():
            return candidate.resolve()
    return None


def local_model_guide_path() -> Path | None:
    docs_dir = resolve_resource_paths().docs_dir
    for candidate in (docs_dir / "model-guide.html", docs_dir / "index.html"):
        if candidate.exists():
            return candidate.resolve()
    return None


def _download_paraformer_package(target_root: Path, cache_root: Path, *, progress: callable | None = None) -> None:
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError as exc:
        raise TranscriptionError("modelscope is required to download Paraformer models.") from exc

    os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_root / "huggingface" / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root / "huggingface" / "transformers"))
    os.environ.setdefault("MODELSCOPE_CACHE", str(cache_root / "modelscope"))

    stages = (
        (PARAFORMER_MODEL_SOURCE_ID, target_root / PARAFORMER_MODEL_ID, "Downloading Paraformer ASR model..."),
        (PARAFORMER_VAD_SOURCE_ID, target_root / "fsmn-vad", "Downloading Paraformer VAD model..."),
        (PARAFORMER_PUNC_SOURCE_ID, target_root / "ct-punc", "Downloading Paraformer punctuation model..."),
    )
    for model_source_id, target_dir, message in stages:
        if progress is not None:
            progress(message)
        snapshot_download(
            model_id=model_source_id,
            local_dir=str(target_dir),
            cache_dir=str(cache_root / "modelscope"),
        )


def _upsert_installed_model(
    entry: InstalledModelEntry,
    *,
    catalog: ModelCatalogEntry | None,
) -> InstalledModelRecord:
    resources = resolve_resource_paths()
    config = resources.install_config
    existing_entries = ()
    if config is not None:
        filtered = [item for item in config.installed_models if item.model_id != entry.model_id]
        filtered.append(entry)
        update_installed_models(tuple(filtered))
        existing_entries = tuple(filtered)
    elif catalog is not None:
        existing_entries = (entry,)
    return InstalledModelRecord(
        model_id=entry.model_id,
        provider_name=entry.provider_name,
        display_name=entry.display_name,
        status=entry.status,
        path=Path(entry.path).expanduser().resolve() if entry.path else None,
        imported=entry.imported,
        recommended=catalog.recommended if catalog is not None else False,
        description=catalog.description if catalog is not None else "",
        approx_size_mb=catalog.approx_size_mb if catalog is not None else entry.size_bytes,
    )


def write_install_config(
    *,
    install_scope: str,
    models_dir: Path,
    docs_dir: Path,
    component_names: tuple[str, ...] = (),
    allow_implicit_model_download_value: bool = False,
) -> Path:
    normalized_components = tuple(
        component
        for component in component_names
        if component in {"gui", "cli", "docs"}
    )
    return save_install_config(
        InstallConfig(
            install_scope=install_scope,
            models_dir=models_dir.expanduser().resolve(),
            docs_dir=docs_dir.expanduser().resolve(),
            installed_components=normalized_components,
            installed_models=(),
            allow_implicit_model_download=allow_implicit_model_download_value,
        )
    )


def managed_models_present() -> bool:
    return any(
        record.provider_name in {"local-whisper", "paraformer"} and record.path is not None and record.path.exists()
        for record in list_installed_models()
    )


def _directory_size_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _is_imported_native_entry(model_id: str) -> bool:
    return model_id.startswith("native:")


def _resolve_download_paths(models_dir: Path | None) -> tuple[Path, Path]:
    resources = resolve_resource_paths()
    target_root = (models_dir or resources.models_dir).expanduser()
    if models_dir is None:
        cache_root = resources.model_cache_dir
    else:
        cache_root = target_root.parent / "model-cache"
    target_root.mkdir(parents=True, exist_ok=True)
    return target_root, cache_root.expanduser()
