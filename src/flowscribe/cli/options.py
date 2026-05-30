"""Command-line option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ProgressiveMode = Literal["auto", "enabled", "disabled"]


@dataclass(frozen=True)
class CliOptions:
    command: str
    inputs: list[Path]
    output_dir: Path
    work_dir: Path | None
    provider_name: str | None
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    no_vad_filter: bool
    initial_prompt: str | None
    timestamps: bool
    word_timestamps: bool
    output_formats: tuple[str, ...]
    recursive: bool
    overwrite: bool
    keep_audio: bool
    progressive_mode: ProgressiveMode
    progressive_chunk_seconds: float
    progressive_chunk_overlap_seconds: float
    progressive_resume: bool
    progressive_max_workers: int


@dataclass(frozen=True)
class DoctorOptions:
    command: str
    output_dir: Path
    provider_name: str | None
    model_name: str
    hello_smoke: bool = False


@dataclass(frozen=True)
class SearchOptions:
    command: str
    transcript: Path
    query: str
    context_chars: int
    limit: int | None
    after_seconds: float | None
    before_seconds: float | None
    json_output: bool


@dataclass(frozen=True)
class InspectOptions:
    command: str
    source: str
    json_output: bool
    timeout_seconds: int
    network_family: str
    cookies: Path | None
    proxy: str | None


@dataclass(frozen=True)
class UrlOptions:
    command: str
    url: str
    output_dir: Path
    work_dir: Path | None
    provider_name: str
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    no_vad_filter: bool
    initial_prompt: str | None
    timestamps: bool
    word_timestamps: bool
    output_formats: tuple[str, ...]
    overwrite: bool
    keep_audio: bool
    keep_media: bool
    max_download_mb: int
    max_duration_seconds: float
    download_timeout_seconds: int
    network_family: str
    cookies: Path | None
    proxy: str | None
    progressive_mode: ProgressiveMode
    progressive_chunk_seconds: float
    progressive_chunk_overlap_seconds: float
    progressive_resume: bool
    progressive_max_workers: int
    download_quality: str = "best"
    download_format: str | None = None


@dataclass(frozen=True)
class ServeOptions:
    command: str
    host: str
    port: int
    queue_store_path: Path
    output_dir: Path
    output_formats: tuple[str, ...]
    model_name: str
    language: str | None


@dataclass(frozen=True)
class SimpleCommandOptions:
    command: str
