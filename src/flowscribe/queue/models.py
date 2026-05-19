"""Data models for the batch queue system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from flowscribe.app.models import SourceSpec, TranscriptionJob

QueueItemStatus = Literal["pending", "running", "completed", "failed", "canceled"]
BatchOutputMode = Literal["unified", "per_source", "template"]


@dataclass(frozen=True)
class BatchOutputStrategy:
    mode: BatchOutputMode = "unified"
    base_dir: Path = field(default_factory=lambda: Path("outputs"))
    subdir_template: str = "{source_stem}"
    name_template: str = "{source_stem}"


@dataclass(frozen=True)
class QueueItemSettings:
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
    model_name: str = "small"
    language: str | None = None
    preset: str | None = None
    output_formats: tuple[str, ...] = ("txt", "md", "json")
    timestamps: bool = True
    word_timestamps: bool = False
    overwrite: bool = False
    network_family: str = "auto"
    proxy: str | None = None
    cookies_path: Path | None = None
    progressive_enabled: bool = True
    progressive_resume: bool = True
    progressive_chunk_seconds: float = 30.0
    progressive_max_workers: int = 1
    max_download_mb: int = 2048
    max_duration_seconds: float = 14400.0
    download_timeout_seconds: int = 30


@dataclass(frozen=True)
class QueueItem:
    item_id: str
    source: SourceSpec
    settings: QueueItemSettings
    output_strategy: BatchOutputStrategy = field(default_factory=BatchOutputStrategy)
    status: QueueItemStatus = "pending"
    priority: int = 0
    attempt_count: int = 0
    max_retries: int = 2
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    title: str | None = None

    @property
    def can_retry(self) -> bool:
        return self.status == "failed" and self.attempt_count <= self.max_retries

    @property
    def display_label(self) -> str:
        if self.title:
            return self.title
        if self.source.kind == "url":
            return self.source.value
        return Path(self.source.value).name

    def to_job(self) -> TranscriptionJob:
        effective_output_dir = _resolve_output_dir(
            self.source, self.settings, self.output_strategy
        )
        effective_name_base = _resolve_output_name(self.source, self.output_strategy)
        return TranscriptionJob(
            sources=(self.source,),
            output_dir=effective_output_dir,
            output_name_base=effective_name_base,
            model_name=self.settings.model_name,
            language=self.settings.language,
            preset=self.settings.preset,
            timestamps=self.settings.timestamps,
            word_timestamps=self.settings.word_timestamps,
            output_formats=self.settings.output_formats,
            overwrite=self.settings.overwrite,
            network_family=self.settings.network_family,
            proxy=self.settings.proxy,
            cookies_path=self.settings.cookies_path,
            progressive_enabled=self.settings.progressive_enabled,
            progressive_resume=self.settings.progressive_resume,
            progressive_chunk_seconds=self.settings.progressive_chunk_seconds,
            progressive_max_workers=self.settings.progressive_max_workers,
            max_download_mb=self.settings.max_download_mb,
            max_duration_seconds=self.settings.max_duration_seconds,
            download_timeout_seconds=self.settings.download_timeout_seconds,
        )


def generate_queue_item_id(source: SourceSpec) -> str:
    key = f"{source.kind}:{source.value}".encode("utf-8")
    return sha1(key).hexdigest()[:12]


def _resolve_output_dir(
    source: SourceSpec,
    settings: QueueItemSettings,
    strategy: BatchOutputStrategy,
) -> Path:
    if strategy.mode == "unified":
        return strategy.base_dir
    if strategy.mode == "per_source":
        stem = _source_stem(source)
        subdir = strategy.subdir_template.format(source_stem=stem)
        return strategy.base_dir / subdir
    return strategy.base_dir


def _resolve_output_name(source: SourceSpec, strategy: BatchOutputStrategy) -> str | None:
    if strategy.mode == "template":
        stem = _source_stem(source)
        return strategy.name_template.format(source_stem=stem)
    return None


def _source_stem(source: SourceSpec) -> str:
    if source.kind == "local":
        return Path(source.value).stem
    path = urlparse(source.value).path.rstrip("/")
    if path:
        return Path(path).stem or "download"
    return "download"
