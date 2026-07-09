"""Remote server profile persistence for CLI and future GUI use."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from flowscribe.config.resources import load_install_config

REMOTE_SERVER_CONFIG_VERSION = 1
REMOTE_SERVER_CONFIG_FILENAME = "remote-servers.json"


@dataclass(frozen=True)
class RemoteServerProfile:
    name: str
    base_url: str
    token: str | None = None
    enabled: bool = True
    verify_tls: bool = True
    timeout_seconds: float = 30.0
    download_artifacts_by_default: bool = True


def remote_server_config_path() -> Path:
    env_dir = os.environ.get("FLOWSCRIBE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).expanduser() / REMOTE_SERVER_CONFIG_FILENAME
    config_path, _ = load_install_config()
    if config_path is not None:
        return config_path.with_name(REMOTE_SERVER_CONFIG_FILENAME)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "FlowScribe" / REMOTE_SERVER_CONFIG_FILENAME
    return Path.home() / ".flowscribe" / REMOTE_SERVER_CONFIG_FILENAME


def load_remote_server_profiles() -> tuple[RemoteServerProfile, ...]:
    path = remote_server_config_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    servers = payload.get("servers", [])
    if not isinstance(servers, list):
        return ()
    result: list[RemoteServerProfile] = []
    for item in servers:
        profile = _profile_from_payload(item)
        if profile is not None:
            result.append(profile)
    return tuple(result)


def save_remote_server_profiles(profiles: tuple[RemoteServerProfile, ...]) -> Path:
    path = remote_server_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": REMOTE_SERVER_CONFIG_VERSION,
        "servers": [asdict(profile) for profile in profiles],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def upsert_remote_server_profile(profile: RemoteServerProfile) -> tuple[RemoteServerProfile, ...]:
    profiles = [existing for existing in load_remote_server_profiles() if existing.name != profile.name]
    profiles.append(profile)
    profiles.sort(key=lambda item: item.name.lower())
    save_remote_server_profiles(tuple(profiles))
    return tuple(profiles)


def remove_remote_server_profile(name: str) -> bool:
    profiles = list(load_remote_server_profiles())
    filtered = [profile for profile in profiles if profile.name != name]
    if len(filtered) == len(profiles):
        return False
    save_remote_server_profiles(tuple(filtered))
    return True


def get_remote_server_profile(name: str) -> RemoteServerProfile | None:
    for profile in load_remote_server_profiles():
        if profile.name == name:
            return profile
    return None


def resolve_remote_server(
    target: str,
    *,
    token_override: str | None = None,
    poll_seconds: float | None = None,
    download_artifacts: bool | None = None,
) -> RemoteServerProfile:
    if _looks_like_url(target):
        profile = RemoteServerProfile(name=target, base_url=target)
    else:
        profile = get_remote_server_profile(target)
        if profile is None:
            raise ValueError(f"Unknown remote server profile: {target}")
    return RemoteServerProfile(
        name=profile.name,
        base_url=profile.base_url,
        token=token_override if token_override is not None else profile.token,
        enabled=profile.enabled,
        verify_tls=profile.verify_tls,
        timeout_seconds=profile.timeout_seconds if poll_seconds is None else profile.timeout_seconds,
        download_artifacts_by_default=(
            profile.download_artifacts_by_default if download_artifacts is None else download_artifacts
        ),
    )


def _profile_from_payload(payload: object) -> RemoteServerProfile | None:
    if not isinstance(payload, dict):
        return None
    name = payload.get("name")
    base_url = payload.get("base_url")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(base_url, str) or not base_url.strip():
        return None
    return RemoteServerProfile(
        name=name.strip(),
        base_url=base_url.strip(),
        token=payload.get("token"),
        enabled=bool(payload.get("enabled", True)),
        verify_tls=bool(payload.get("verify_tls", True)),
        timeout_seconds=float(payload.get("timeout_seconds", 30.0)),
        download_artifacts_by_default=bool(payload.get("download_artifacts_by_default", True)),
    )


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
