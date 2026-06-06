"""Minimal v0 capability and provider protocols."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from flowscribe.core.models import OutputArtifacts
from flowscribe.tasks.models import CapabilityResult, ProgressEvent, TaskSpec


class CancelToken(Protocol):
    """Cross-layer cancel token."""

    def __call__(self) -> bool:
        """Return whether cancellation has been requested."""


@dataclass(frozen=True)
class ProviderRequest:
    """Normalized request from capability layer to providers/runtime."""

    task: TaskSpec
    capability: str
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized provider response."""

    supported: bool
    artifacts: tuple[OutputArtifacts, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    raw_metadata: Mapping[str, object] = field(default_factory=dict)


class ProviderProtocol(Protocol):
    """Stable provider/runtime protocol for capability-layer routing."""

    def capabilities(self) -> tuple[str, ...]:
        """Return provider-supported capability names."""

    def prepare(self, request: ProviderRequest) -> ProviderRequest:
        """Optionally normalize or enrich a request before execution."""

    def execute(
        self,
        request: ProviderRequest,
        progress_cb: Callable[[ProgressEvent], None] | None,
        cancel_token: CancelToken | None,
    ) -> ProviderResponse:
        """Execute a capability request."""

    def close(self) -> None:
        """Release provider/runtime resources."""


class Capability(Protocol):
    """Stable capability-layer protocol."""

    name: str

    def run(
        self,
        task: TaskSpec,
        *,
        progress_cb: Callable[[ProgressEvent], None] | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CapabilityResult:
        """Execute one capability for one task."""
