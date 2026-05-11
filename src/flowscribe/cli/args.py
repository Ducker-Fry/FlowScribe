"""Command-line argument parsing."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CliOptions:
    command: str
    inputs: list[Path]
    output_dir: Path
    work_dir: Path | None
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None
    recursive: bool
    overwrite: bool
    keep_audio: bool


@dataclass(frozen=True)
class DoctorOptions:
    command: str
    output_dir: Path
    model_name: str


def parse_args(argv: list[str] | None = None) -> CliOptions | DoctorOptions:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "doctor":
        return parse_doctor_args(argv[1:])
    return parse_transcribe_args(argv)


def parse_transcribe_args(argv: list[str] | None = None) -> CliOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe",
        description="Turn local audio/video files into raw TXT and Markdown transcripts.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Local media file(s) or folder(s) to transcribe.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for transcript outputs. Default: outputs",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for temporary prepared audio. Default: <output-dir>/.flowscribe-work",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Local faster-whisper model name or path. Default: small",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Optional language code, such as zh or en. Omit for auto-detection.",
    )
    parser.add_argument(
        "--preset",
        choices=["zh"],
        default=None,
        help="Apply a transcription preset. zh enables Chinese-oriented defaults.",
    )
    parser.add_argument(
        "--task",
        choices=["transcribe", "translate"],
        default="transcribe",
        help="Whisper task. Default: transcribe. Use translate only when explicitly needed.",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for decoding. Higher can improve accuracy but may be slower. Default: 5",
    )
    parser.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable voice activity detection to reduce silence/noise segments.",
    )
    parser.add_argument(
        "--initial-prompt",
        default=None,
        help="Optional prompt to guide transcription terminology and language behavior.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan input folders.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript files instead of creating numbered copies.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep prepared WAV files in the work directory for debugging or reuse.",
    )
    namespace = parser.parse_args(argv)
    return CliOptions(
        command="transcribe",
        inputs=namespace.inputs,
        output_dir=namespace.output_dir,
        work_dir=namespace.work_dir,
        model_name=namespace.model_name,
        language=namespace.language,
        preset=namespace.preset,
        task=namespace.task,
        beam_size=namespace.beam_size,
        vad_filter=namespace.vad_filter,
        initial_prompt=namespace.initial_prompt,
        recursive=namespace.recursive,
        overwrite=namespace.overwrite,
        keep_audio=namespace.keep_audio,
    )


def parse_doctor_args(argv: list[str] | None = None) -> DoctorOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe doctor",
        description="Check whether the local FlowScribe environment is ready.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory to test for transcript output writes. Default: outputs",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Local faster-whisper model name or path to check. Default: small",
    )
    namespace = parser.parse_args(argv)
    return DoctorOptions(
        command="doctor",
        output_dir=namespace.output_dir,
        model_name=namespace.model_name,
    )
