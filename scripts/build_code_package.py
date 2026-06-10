"""Compile FlowScribe business code into a sourceless portable code payload."""

from __future__ import annotations

import argparse
import py_compile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE_ROOT = PROJECT_ROOT / "src" / "flowscribe"
DEFAULT_RELEASE_ROOT = PROJECT_ROOT / "dist" / "FlowScribePortable"

RESOURCE_SUFFIXES = {".qss", ".wav"}
IGNORED_DIRECTORIES = {"__pycache__", "outputs"}
IGNORED_FILE_SUFFIXES = {".pyc", ".json", ".txt", ".md", ".m4a"}
REQUIRED_BUNDLED_MODEL_FILES = {
    "paraformer-zh": (
        "configuration.json",
        "config.yaml",
        "model.pt",
        "tokens.json",
        "am.mvn",
    ),
    "fsmn-vad": (
        "configuration.json",
        "config.yaml",
        "model.pt",
    ),
    "ct-punc": (
        "configuration.json",
        "config.yaml",
        "model.pt",
        "tokens.json",
        "jieba.c.dict",
        "jieba_usr_dict",
    ),
}


def build_code_payload(*, release_root: Path, include_bundled_models: bool) -> None:
    code_root = release_root / "code"
    docs_root = release_root / "docs"
    models_root = release_root / "models"

    if code_root.exists():
        shutil.rmtree(code_root)
    code_root.mkdir(parents=True, exist_ok=True)

    compile_package_tree(
        source_root=SOURCE_PACKAGE_ROOT,
        destination_root=code_root / "flowscribe",
    )
    copy_icons(destination_root=code_root / "icons")

    docs_site_root = PROJECT_ROOT / "build" / "docs-site"
    if docs_root.exists():
        shutil.rmtree(docs_root)
    if docs_site_root.exists():
        shutil.copytree(docs_site_root, docs_root)
    else:
        docs_root.mkdir(parents=True, exist_ok=True)

    if include_bundled_models:
        source_models_root = PROJECT_ROOT / "models"
        if source_models_root.exists():
            if models_root.exists():
                shutil.rmtree(models_root)
            shutil.copytree(source_models_root, models_root)
            validate_bundled_models(models_root)


def validate_bundled_models(models_root: Path) -> None:
    missing_paths = []
    for model_name, required_files in REQUIRED_BUNDLED_MODEL_FILES.items():
        model_root = models_root / model_name
        for relative_file in required_files:
            required_path = model_root / relative_file
            if not required_path.is_file():
                missing_paths.append(required_path.relative_to(models_root))

    if missing_paths:
        formatted = ", ".join(str(path) for path in missing_paths)
        raise RuntimeError(f"Bundled Paraformer model resources are incomplete: {formatted}")


def compile_package_tree(*, source_root: Path, destination_root: Path) -> None:
    for source_path in sorted(source_root.rglob("*")):
        relative_path = source_path.relative_to(source_root)
        if _is_ignored(source_path, relative_path):
            continue
        if source_path.is_dir():
            (destination_root / relative_path).mkdir(parents=True, exist_ok=True)
            continue
        if source_path.suffix == ".py":
            compiled_path = destination_root / relative_path.with_suffix(".pyc")
            compiled_path.parent.mkdir(parents=True, exist_ok=True)
            py_compile.compile(
                str(source_path),
                cfile=str(compiled_path),
                doraise=True,
            )
            continue
        if source_path.suffix in RESOURCE_SUFFIXES:
            destination_path = destination_root / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)


def copy_icons(*, destination_root: Path) -> None:
    source_root = PROJECT_ROOT / "icons"
    if not source_root.exists():
        return
    if destination_root.exists():
        shutil.rmtree(destination_root)
    shutil.copytree(source_root, destination_root)


def _is_ignored(source_path: Path, relative_path: Path) -> bool:
    if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
        return True
    if source_path.is_file() and source_path.suffix in IGNORED_FILE_SUFFIXES:
        return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-root",
        type=Path,
        default=DEFAULT_RELEASE_ROOT,
        help="Portable release root. Default: dist/FlowScribePortable",
    )
    parser.add_argument(
        "--include-bundled-models",
        action="store_true",
        help="Copy the local models directory into the portable release root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_code_payload(
        release_root=args.release_root.expanduser().resolve(),
        include_bundled_models=args.include_bundled_models,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
