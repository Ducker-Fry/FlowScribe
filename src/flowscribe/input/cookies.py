"""Explicit cookie-file handling for URL media access."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import DownloadError


def resolve_cookies_path(cookies_path: Path | None) -> str | None:
    """Return a validated cookie-file path for yt-dlp, or None."""

    if cookies_path is None:
        return None

    resolved = cookies_path.expanduser().resolve()
    if not resolved.exists():
        raise DownloadError(f"Cookies file does not exist: {resolved}")
    if not resolved.is_file():
        raise DownloadError(f"Cookies path must be a file: {resolved}")
    return str(resolved)
