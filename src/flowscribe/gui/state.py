"""GUI-facing state that can be reused by different frontends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from flowscribe.app.models import SourceSpec, TranscriptionJob
from flowscribe.core.errors import DownloadError
from flowscribe.input.file_filter import is_supported_media
from flowscribe.input.url_security import validate_public_http_url
from flowscribe.output.paths import sanitize_output_base_name


SUPPORTED_GUI_FORMATS = ("txt", "md", "json", "srt", "vtt")


@dataclass(frozen=True)
class GuiTranscriptionForm:
    """Serializable form state collected by the desktop GUI."""

    local_paths: tuple[Path, ...] = ()
    url: str = ""
    output_dir: Path = Path("outputs")
    output_name_base: str = ""
    model_name: str = "small"
    language: str = ""
    preset: str = ""
    output_formats: tuple[str, ...] = ("txt", "md", "json")
    timestamps: bool = True
    word_timestamps: bool = False
    overwrite: bool = False
    keep_media: bool = False
    network_family: str = "auto"
    proxy: str = ""
    cookies_path: Path | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        has_local = bool(self.local_paths)
        has_url = bool(self.url.strip())

        if not has_local and not has_url:
            errors.append("Add at least one local file or paste a URL.")

        if has_url and not _is_http_url(self.url.strip()):
            errors.append("URL input must start with http:// or https://.")
        elif has_url:
            try:
                validate_public_http_url(
                    self.url.strip(),
                    network_family=self.network_family,
                )
            except DownloadError as exc:
                errors.append(str(exc))

        if not self.output_formats:
            errors.append("Select at least one output format.")

        if self.output_name_base.strip() and sanitize_output_base_name(self.output_name_base) is None:
            errors.append("Output name cannot be empty after trimming.")

        unsupported = [
            output_format
            for output_format in self.output_formats
            if output_format not in SUPPORTED_GUI_FORMATS
        ]
        if unsupported:
            errors.append(f"Unsupported output format(s): {', '.join(unsupported)}.")

        if self.network_family not in {"auto", "ipv4", "ipv6"}:
            errors.append("Network family must be auto, ipv4, or ipv6.")

        return errors

    def to_job(self) -> TranscriptionJob:
        errors = self.validate()
        if errors:
            raise ValueError(" ".join(errors))

        sources: list[SourceSpec] = [
            SourceSpec(kind="local", value=str(path), recursive=False) for path in self.local_paths
        ]
        if self.url.strip():
            sources.append(
                SourceSpec(kind="url", value=self.url.strip(), keep_media=self.keep_media)
            )

        language = self.language.strip() or None
        preset = self.preset.strip() or None
        proxy = self.proxy.strip() or None

        return TranscriptionJob(
            sources=tuple(sources),
            output_dir=self.output_dir,
            output_name_base=sanitize_output_base_name(self.output_name_base),
            model_name=self.model_name.strip() or "small",
            language=language,
            preset=preset,
            timestamps=self.timestamps,
            word_timestamps=self.word_timestamps,
            output_formats=self.output_formats,
            overwrite=self.overwrite,
            network_family=self.network_family,
            proxy=proxy,
            cookies_path=self.cookies_path,
        )

    def preview(self) -> dict:
        """Return plain data for display, debugging, and future frontend bridges."""

        job = self.to_job()
        return {
            "sources": [
                {
                    "kind": source.kind,
                    "value": source.value,
                    "keep_media": source.keep_media,
                }
                for source in job.sources
            ],
            "output_dir": str(job.output_dir),
            "output_name_base": job.output_name_base,
            "model_name": job.model_name,
            "language": job.language,
            "preset": job.preset,
            "timestamps": job.timestamps,
            "word_timestamps": job.word_timestamps,
            "output_formats": list(job.output_formats),
            "overwrite": job.overwrite,
            "network_family": job.network_family,
            "proxy": job.proxy,
            "cookies_path": str(job.cookies_path) if job.cookies_path else None,
        }


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_acceptable_local_source(path: Path) -> bool:
    """Return whether a local path matches what the CLI local source can accept."""

    return path.is_dir() or is_supported_media(path)
