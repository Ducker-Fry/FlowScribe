"""Resolve FlowScribe runtime directories across source, legacy, and layered builds."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

APP_ROOT_ENV = "FLOWSCRIBE_APP_ROOT"
CORE_DIR_ENV = "FLOWSCRIBE_CORE_DIR"
CODE_DIR_ENV = "FLOWSCRIBE_CODE_DIR"


@dataclass(frozen=True)
class RuntimeLayout:
    app_root: Path
    core_dir: Path
    code_dir: Path
    source_root: Path
    frozen: bool
    layered: bool


def env_path(name: str) -> Path | None:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return None
    return Path(raw_value).expanduser().resolve()


@lru_cache(maxsize=16)
def _resolve_runtime_layout_cached(
    frozen: bool,
    executable: str,
    app_root_override: str | None,
    core_dir_override: str | None,
    code_dir_override: str | None,
) -> RuntimeLayout:
    source_root = Path(__file__).resolve().parents[3]
    executable_dir = Path(executable).resolve().parent if frozen else source_root

    def _path_override(raw_value: str | None) -> Path | None:
        if raw_value is None or not raw_value.strip():
            return None
        return Path(raw_value).expanduser().resolve()

    app_root = _path_override(app_root_override) or _infer_app_root(
        frozen=frozen,
        executable_dir=executable_dir,
        source_root=source_root,
    )
    core_dir = _path_override(core_dir_override) or _infer_core_dir(
        frozen=frozen,
        executable_dir=executable_dir,
        app_root=app_root,
        source_root=source_root,
    )
    code_dir = _path_override(code_dir_override) or _infer_code_dir(
        frozen=frozen,
        app_root=app_root,
        source_root=source_root,
    )
    layered = (
        _path_override(code_dir_override) is not None
        or _path_override(core_dir_override) is not None
        or (frozen and core_dir != app_root)
    )
    return RuntimeLayout(
        app_root=app_root,
        core_dir=core_dir,
        code_dir=code_dir,
        source_root=source_root,
        frozen=frozen,
        layered=layered,
    )


def resolve_runtime_layout() -> RuntimeLayout:
    return _resolve_runtime_layout_cached(
        bool(getattr(sys, "frozen", False)),
        str(sys.executable),
        os.environ.get(APP_ROOT_ENV),
        os.environ.get(CORE_DIR_ENV),
        os.environ.get(CODE_DIR_ENV),
    )


def code_package_root() -> Path:
    return resolve_runtime_layout().code_dir / "flowscribe"


def _infer_app_root(*, frozen: bool, executable_dir: Path, source_root: Path) -> Path:
    if not frozen:
        return source_root
    if executable_dir.name.lower() == "core":
        return executable_dir.parent
    return executable_dir


def _infer_core_dir(
    *,
    frozen: bool,
    executable_dir: Path,
    app_root: Path,
    source_root: Path,
) -> Path:
    if not frozen:
        return source_root
    layered_candidate = app_root / "core"
    if layered_candidate.exists():
        return layered_candidate.resolve()
    return executable_dir


def _infer_code_dir(*, frozen: bool, app_root: Path, source_root: Path) -> Path:
    if not frozen:
        return source_root / "src"
    layered_candidate = app_root / "code"
    if layered_candidate.exists():
        return layered_candidate.resolve()
    return app_root
