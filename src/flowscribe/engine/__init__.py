"""FlowScribe C++ Engine IPC Client"""

from .pipe_client import FlowScribeEngineClient
from .protocol import MessageKind, encode_message, decode_header

__all__ = [
    "FlowScribeEngineClient",
    "MessageKind",
    "encode_message",
    "decode_header",
]
