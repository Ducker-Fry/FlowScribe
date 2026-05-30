"""Argument type validators for CLI parsing."""

from __future__ import annotations

import argparse


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("Value cannot be negative.")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("Value cannot be negative.")
    return parsed


def parse_time_value(value: str) -> float:
    parts = value.strip().split(":")
    if not parts or len(parts) > 3:
        raise argparse.ArgumentTypeError("Time must be SS, MM:SS, or HH:MM:SS.")

    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Time must contain only numbers and ':'.") from exc

    if any(number < 0 for number in numbers):
        raise argparse.ArgumentTypeError("Time cannot be negative.")
    if len(numbers) == 1:
        return numbers[0]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def parse_output_formats(value: str) -> tuple[str, ...]:
    supported = {"txt", "md", "json", "srt", "vtt"}
    formats = tuple(dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip()))
    if not formats:
        raise argparse.ArgumentTypeError("At least one output format is required.")

    unsupported = [output_format for output_format in formats if output_format not in supported]
    if unsupported:
        joined = ", ".join(unsupported)
        supported_joined = ",".join(sorted(supported))
        raise argparse.ArgumentTypeError(
            f"Unsupported output format(s): {joined}. Supported: {supported_joined}"
        )
    return formats
