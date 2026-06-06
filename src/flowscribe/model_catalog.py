"""Shared helpers for model identifier resolution."""

from __future__ import annotations


def resolve_faster_whisper_repo(model_name: str) -> str | None:
    known = {
        "tiny",
        "tiny.en",
        "base",
        "base.en",
        "small",
        "small.en",
        "medium",
        "medium.en",
        "large-v1",
        "large-v2",
        "large-v3",
        "large-v3-turbo",
    }
    if model_name in known:
        return f"Systran/faster-whisper-{model_name}"
    if "/" in model_name:
        return model_name
    return None
