"""Command-line argument parsing (compatibility shim)."""

from __future__ import annotations

import sys

from .options import (
    CliOptions,
    DoctorOptions,
    InstallCommandOptions,
    InspectOptions,
    ModelCommandOptions,
    ProgressiveMode,
    RemoteCommandOptions,
    SearchOptions,
    ServeOptions,
    SimpleCommandOptions,
    UrlOptions,
)
from .parsers import (
    add_progressive_options,
    add_transcription_options,
    parse_doctor_args,
    parse_install_args,
    parse_inspect_args,
    parse_model_args,
    parse_remote_args,
    parse_search_args,
    parse_serve_args,
    parse_simple_command_args,
    parse_transcribe_args,
    parse_url_args,
)
from .validators import (
    non_negative_float,
    non_negative_int,
    parse_output_formats,
    parse_time_value,
    positive_float,
    positive_int,
)

__all__ = [
    "CliOptions",
    "DoctorOptions",
    "InstallCommandOptions",
    "InspectOptions",
    "ModelCommandOptions",
    "ProgressiveMode",
    "RemoteCommandOptions",
    "SearchOptions",
    "ServeOptions",
    "SimpleCommandOptions",
    "UrlOptions",
    "add_progressive_options",
    "add_transcription_options",
    "non_negative_float",
    "non_negative_int",
    "parse_args",
    "parse_doctor_args",
    "parse_install_args",
    "parse_inspect_args",
    "parse_model_args",
    "parse_remote_args",
    "parse_output_formats",
    "parse_search_args",
    "parse_serve_args",
    "parse_simple_command_args",
    "parse_time_value",
    "parse_transcribe_args",
    "parse_url_args",
    "positive_float",
    "positive_int",
]


def parse_args(
    argv: list[str] | None = None,
) -> CliOptions | DoctorOptions | SearchOptions | InspectOptions | UrlOptions | ServeOptions | SimpleCommandOptions | ModelCommandOptions | InstallCommandOptions | RemoteCommandOptions:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return parse_transcribe_args(argv)

    command = argv[0]
    if command == "transcribe":
        return parse_transcribe_args(argv[1:], prog="flowscribe transcribe")
    if command == "doctor":
        return parse_doctor_args(argv[1:])
    if command == "search":
        return parse_search_args(argv[1:])
    if command == "inspect":
        return parse_inspect_args(argv[1:])
    if command == "url":
        return parse_url_args(argv[1:])
    if command == "serve":
        return parse_serve_args(argv[1:])
    if command == "model":
        return parse_model_args(argv[1:])
    if command == "install":
        return parse_install_args(argv[1:])
    if command == "remote":
        return parse_remote_args(argv[1:])
    if command in {"version", "formats", "models", "capture", "gui"}:
        return parse_simple_command_args(command, argv[1:])
    return parse_transcribe_args(argv)
