"""Storage helpers for remote-direct uploads and downloadable artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import uuid


@dataclass(frozen=True)
class UploadedBlob:
    blob_id: str
    filename: str
    path: Path
    size_bytes: int


class UploadBlobStore:
    """Persist uploaded files under a server-managed blob directory."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir.expanduser().resolve()

    def save(self, *, filename: str, source_stream, content_length: int) -> UploadedBlob:
        blob_id = uuid.uuid4().hex
        suffix = Path(filename).suffix
        target_dir = self._root_dir / blob_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"upload{suffix}"
        remaining = max(0, content_length)
        written = 0
        with target_path.open("wb") as handle:
            while remaining > 0:
                chunk = source_stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                remaining -= len(chunk)
        return UploadedBlob(
            blob_id=blob_id,
            filename=filename,
            path=target_path,
            size_bytes=written,
        )

    def resolve(self, blob_id: str) -> Path | None:
        blob_dir = self._root_dir / blob_id
        if not blob_dir.is_dir():
            return None
        for child in blob_dir.iterdir():
            if child.is_file():
                return child
        return None

    def delete(self, blob_id: str) -> bool:
        blob_dir = self._root_dir / blob_id
        if not blob_dir.exists():
            return False
        shutil.rmtree(blob_dir, ignore_errors=False)
        return True
