"""Execution backends for local and remote FlowScribe runs."""

from .backends import ExecutionBackend, LocalExecutionBackend, RemoteExecutionBackend
from .factory import build_execution_backend

__all__ = [
    "ExecutionBackend",
    "LocalExecutionBackend",
    "RemoteExecutionBackend",
    "build_execution_backend",
]
