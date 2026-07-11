"""Bootstrap external FlowScribe code from a layered portable runtime."""

from __future__ import annotations

import importlib
import os
import sys

APP_ROOT_ENV = "FLOWSCRIBE_APP_ROOT"
CORE_DIR_ENV = "FLOWSCRIBE_CORE_DIR"
CODE_DIR_ENV = "FLOWSCRIBE_CODE_DIR"


def run_target(target: str, argv: list[str] | None = None) -> int:
    app_root, core_dir, code_dir = _resolve_layout()
    os.environ.setdefault(APP_ROOT_ENV, str(app_root))
    os.environ.setdefault(CORE_DIR_ENV, str(core_dir))
    os.environ.setdefault(CODE_DIR_ENV, str(code_dir))
    _install_import_paths(core_dir=core_dir, code_dir=code_dir)
    _purge_bootstrap_stdlib_shadows()
    _enable_site_package_shims()

    module_name, function_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    entrypoint = getattr(module, function_name)
    args = list(sys.argv[1:] if argv is None else argv)
    result = entrypoint(args)
    return 0 if result is None else int(result)


def _resolve_layout() -> tuple[str, str, str]:
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    app_root = (
        os.path.dirname(executable_dir)
        if os.path.basename(executable_dir).lower() == "core"
        else executable_dir
    )
    core_dir = os.path.join(app_root, "core")
    code_dir = os.path.join(app_root, "code")
    return app_root, core_dir, code_dir


def _install_import_paths(*, core_dir: str, code_dir: str) -> None:
    stdlib_dir = os.path.join(core_dir, "Lib")
    dll_dir = os.path.join(core_dir, "DLLs")
    site_packages = os.path.join(core_dir, "site-packages")

    preferred_paths = [
        path
        for path in (stdlib_dir, site_packages, code_dir, dll_dir)
        if os.path.exists(path)
    ]

    for dll_path in (core_dir, dll_dir):
        if os.path.exists(dll_path) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_path)

    sys.path[:] = preferred_paths


def _purge_bootstrap_stdlib_shadows() -> None:
    shadowed_packages = ("urllib", "http", "html", "xml", "email", "logging")
    for module_name in tuple(sys.modules):
        if any(
            module_name == package_name or module_name.startswith(f"{package_name}.")
            for package_name in shadowed_packages
        ):
            sys.modules.pop(module_name, None)


def _enable_site_package_shims() -> None:
    """Re-enable setuptools/distutils shims after replacing sys.path.

    The layered portable runtime bypasses normal site startup, so Python 3.12
    no longer sees setuptools' distutils compatibility shim automatically.
    FunASR model auto-registration still imports distutils-era modules, so we
    import setuptools eagerly to restore the shim before business code loads.
    """

    try:
        import setuptools  # noqa: F401
    except Exception:
        return
