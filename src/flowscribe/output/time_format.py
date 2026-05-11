"""Timestamp formatting helpers."""

from __future__ import annotations


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "--:--:--"

    total_milliseconds = max(0, int(round(seconds * 1000)))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    second = total_seconds % 60
    total_minutes = total_seconds // 60
    minute = total_minutes % 60
    hour = total_minutes // 60
    return f"{hour:02d}:{minute:02d}:{second:02d}.{milliseconds:03d}"


def format_srt_timestamp(seconds: float | None) -> str:
    return format_timestamp(seconds).replace(".", ",")
