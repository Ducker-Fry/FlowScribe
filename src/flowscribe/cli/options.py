"""Command-line option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ProgressiveMode = Literal["auto", "enabled", "disabled"]
ExecutionMode = Literal["local", "remote"]


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
    execution_mode: ExecutionMode = "local"
    server_target: str | None = None
    remote_token: str | None = None
    remote_poll_seconds: float = 1.0
    download_artifacts: bool | None = None
    submit_only: bool = False
    json_output: bool = False
    event_stream: str | None = None
    non_interactive: bool = False
    task_id: str | None = None
    resume_token: str | None = None
    checkpoint_id: str | None = None


@dataclass(frozen=True)
class DoctorOptions:
    command: str
    output_dir: Path
    provider_name: str | None
    model_name: str
    hello_smoke: bool = False
    skip_model_access: bool = False


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
    execution_mode: ExecutionMode = "local"
    server_target: str | None = None
    remote_token: str | None = None
    remote_poll_seconds: float = 1.0
    download_artifacts: bool | None = None
    submit_only: bool = False
    download_quality: str = "best"
    download_format: str | None = None
    json_output: bool = False
    event_stream: str | None = None
    non_interactive: bool = False
    task_id: str | None = None
    resume_token: str | None = None
    checkpoint_id: str | None = None


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
    api_token: str | None = None


@dataclass(frozen=True)
class SimpleCommandOptions:
    command: str


@dataclass(frozen=True)
class ModelCommandOptions:
    command: str
    subcommand: str
    model_id: str | None = None
    path: Path | None = None
    models_dir: Path | None = None
    json_output: bool = False


@dataclass(frozen=True)
class InstallCommandOptions:
    command: str
    subcommand: str
    install_scope: str | None = None
    models_dir: Path | None = None
    docs_dir: Path | None = None
    component_names: tuple[str, ...] = ()
    allow_implicit_model_download: bool = False
    json_output: bool = False


@dataclass(frozen=True)
class RemoteCommandOptions:
    command: str
    subcommand: str
    name: str | None = None
    base_url: str | None = None
    token: str | None = None
    server_target: str | None = None
    task_id: str | None = None
    output_dir: Path | None = None
    enabled: bool = True
    verify_tls: bool = True
    timeout_seconds: float = 30.0
    download_artifacts_by_default: bool = True
    download_artifacts: bool | None = None
    json_output: bool = False
