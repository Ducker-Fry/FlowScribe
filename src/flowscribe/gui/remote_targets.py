"""Helpers for resolving and validating GUI remote execution targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from flowscribe.execution.remote_config import (
    get_remote_server_profile,
    get_remote_server_profile_for_url,
)


@dataclass(frozen=True)
class RemoteTargetInspection:
    target: str | None
    valid: bool
    resolved_url: str | None
    message: str
    error: str | None = None
    profile_name: str | None = None


def inspect_remote_target(target: str | None) -> RemoteTargetInspection:
    raw = (target or "").strip()
    if not raw:
        return RemoteTargetInspection(
            target=None,
            valid=False,
            resolved_url=None,
            message="Choose a saved profile or enter a full URL like http://127.0.0.1:18769.",
            error="Remote execution requires a server profile or a full http(s)://host:port URL.",
        )

    profile = get_remote_server_profile(raw)
    if profile is not None:
        if not profile.enabled:
            return RemoteTargetInspection(
                target=raw,
                valid=False,
                resolved_url=profile.base_url,
                message=f"Profile '{profile.name}' is disabled.",
                error=f"Remote server profile '{profile.name}' is disabled.",
                profile_name=profile.name,
            )
        return RemoteTargetInspection(
            target=raw,
            valid=True,
            resolved_url=profile.base_url.rstrip("/"),
            message=f"Resolved profile '{profile.name}' to {profile.base_url.rstrip('/')}",
            profile_name=profile.name,
        )

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return RemoteTargetInspection(
            target=raw,
            valid=False,
            resolved_url=None,
            message="Enter a full URL like http://127.0.0.1:18769, or choose a saved server profile.",
            error="Remote server must be a saved profile or a full http(s)://host:port URL.",
        )
    if parsed.port is None:
        return RemoteTargetInspection(
            target=raw,
            valid=False,
            resolved_url=None,
            message="URL must include an explicit port, for example http://127.0.0.1:18769.",
            error="Remote server URL must include an explicit port.",
        )

    resolved = raw.rstrip("/")
    matched_profile = get_remote_server_profile_for_url(resolved)
    if matched_profile is not None:
        return RemoteTargetInspection(
            target=raw,
            valid=True,
            resolved_url=resolved,
            message=f"Matched saved profile: {matched_profile.name} -> {resolved}",
            profile_name=matched_profile.name,
        )
    return RemoteTargetInspection(
        target=raw,
        valid=True,
        resolved_url=resolved,
        message=f"Direct URL: {resolved}",
    )


def validate_remote_execution_settings(settings: Mapping[str, object]) -> str | None:
    if settings.get("execution_mode", "local") != "remote":
        return None
    inspection = inspect_remote_target(_as_text(settings.get("server_target")))
    return inspection.error


def _as_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
