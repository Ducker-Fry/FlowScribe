"""Helpers for building execution backends from CLI or queue settings."""

from __future__ import annotations

from collections.abc import Callable

from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import FlowScribeError
from flowscribe.execution.backends import LocalExecutionBackend, RemoteExecutionBackend
from flowscribe.execution.remote_client import RemoteServerClient
from flowscribe.execution.remote_config import resolve_remote_server


def build_execution_backend(
    *,
    execution_mode: str = "local",
    server_target: str | None = None,
    remote_token: str | None = None,
    remote_poll_seconds: float = 1.0,
    download_artifacts: bool | None = None,
    service_factory: Callable[[], object] | None = None,
):
    if execution_mode != "remote":
        return LocalExecutionBackend(service_factory or (lambda: TranscriptionService()))
    if not server_target:
        raise FlowScribeError("--execution remote requires --server with a profile name or base URL.")
    resolved = resolve_remote_server(
        server_target,
        token_override=remote_token,
        download_artifacts=download_artifacts,
    )
    if not resolved.enabled:
        raise FlowScribeError(f"Remote server profile is disabled: {resolved.name}")
    client = RemoteServerClient(
        resolved.base_url,
        token=resolved.token,
        verify_tls=resolved.verify_tls,
        timeout_seconds=resolved.timeout_seconds,
    )
    return RemoteExecutionBackend(
        client,
        poll_seconds=remote_poll_seconds,
        download_artifacts=resolved.download_artifacts_by_default,
    )
