"""Subtitle capability for subtitle-first routing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from flowscribe.capabilities.protocol import CancelToken
from flowscribe.core.errors import (
    CancellationError,
    DownloadError,
    SubtitleUnavailableError,
    TranscriptionError,
)
from flowscribe.core.models import OutputArtifacts
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder, sanitize_output_base_name
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter
from flowscribe.providers.subtitle import YouTubeNativeSubtitleProvider
from flowscribe.tasks.models import CapabilityResult, ErrorEvent, ProgressEvent, TaskSpec


class SubtitleCapability:
    """Extract native subtitles before falling back to speech transcription."""

    name = "subtitle"

    def run(
        self,
        task: TaskSpec,
        *,
        progress_cb: Callable[[ProgressEvent], None] | None = None,
        cancel_token: CancelToken | None = None,
    ) -> CapabilityResult:
        provider = YouTubeNativeSubtitleProvider()
        if progress_cb is not None:
            progress_cb(
                ProgressEvent(
                    task_id=task.task_id,
                    capability=self.name,
                    stage="prepare",
                    percent=0.0,
                    message="Checking for native subtitles...",
                    source=task.source.value,
                )
            )
        if task.source.kind != "url" or not provider.supports(task.source.value):
            return CapabilityResult(
                task_id=task.task_id,
                capability=self.name,
                supported=False,
                status="unsupported",
                payload={"reason": "subtitle-provider-unsupported-source"},
            )

        if cancel_token is not None and cancel_token():
            raise CancellationError("Subtitle extraction canceled.")

        try:
            fetch_result = provider.fetch(
                task.source.value,
                language=_optional_str(task.raw_metadata.get("language")),
                cookies_path=_optional_path(task.raw_metadata.get("cookies_path")),
                proxy=_optional_str(task.raw_metadata.get("proxy")),
                task=_optional_str(task.raw_metadata.get("task")) or "transcribe",
                initial_prompt=_optional_str(task.raw_metadata.get("initial_prompt")),
                preset=_optional_str(task.raw_metadata.get("preset")),
                word_timestamps=bool(task.raw_metadata.get("word_timestamps", False)),
                source_name=_resolved_output_name(task),
            )
            if cancel_token is not None and cancel_token():
                raise CancellationError("Subtitle extraction canceled.")

            path_builder = OutputPathBuilder(
                overwrite=task.output_contract.overwrite,
                base_name=_resolved_output_name(task),
            )
            writer = TranscriptArtifactWriter(
                formats=task.output_contract.formats,
                txt_writer=TxtTranscriptWriter(path_builder),
                md_writer=MarkdownTranscriptWriter(
                    path_builder,
                    include_timestamps=bool(task.raw_metadata.get("timestamps", False)),
                ),
                json_writer=JsonTranscriptWriter(path_builder),
                srt_writer=SrtTranscriptWriter(path_builder),
                vtt_writer=VttTranscriptWriter(path_builder),
            )
            written = writer.write_all(fetch_result.transcript, task.output_contract.output_dir)
            artifacts = OutputArtifacts(
                paths=written.paths,
                source_kind="url",
                source_value=task.source.value,
                auto_bind_media=task.source.auto_bind_media,
                transcription_strategy=(
                    "native-subtitles"
                    if fetch_result.source_kind == "subtitles"
                    else "automatic-subtitles"
                ),
                subtitle_source_kind=fetch_result.source_kind,
                subtitle_language=fetch_result.language,
            )
        except CancellationError:
            raise
        except SubtitleUnavailableError as exc:
            return CapabilityResult(
                task_id=task.task_id,
                capability=self.name,
                supported=False,
                status="unsupported",
                payload={"reason": "no-usable-native-subtitles"},
                warnings=(str(exc),),
            )
        except DownloadError as exc:
            return CapabilityResult(
                task_id=task.task_id,
                capability=self.name,
                supported=True,
                status="failed",
                error=ErrorEvent(
                    task_id=task.task_id,
                    capability=self.name,
                    error_type="network",
                    user_message=str(exc),
                    internal_message=str(exc),
                    retryable=True,
                    code=exc.__class__.__name__,
                ),
            )
        except TranscriptionError as exc:
            return CapabilityResult(
                task_id=task.task_id,
                capability=self.name,
                supported=True,
                status="failed",
                error=ErrorEvent(
                    task_id=task.task_id,
                    capability=self.name,
                    error_type="runtime",
                    user_message=str(exc),
                    internal_message=str(exc),
                    retryable=False,
                    code=exc.__class__.__name__,
                ),
            )

        if progress_cb is not None:
            progress_cb(
                ProgressEvent(
                    task_id=task.task_id,
                    capability=self.name,
                    stage="write",
                    percent=100.0,
                    message=(
                        "Using native YouTube subtitles."
                        if fetch_result.source_kind == "subtitles"
                        else "Using automatic YouTube captions."
                    ),
                    source=task.source.value,
                    raw_metadata={
                        "subtitle_format": fetch_result.subtitle_format,
                        "subtitle_language": fetch_result.language,
                        "subtitle_source_kind": fetch_result.source_kind,
                    },
                )
            )
        return CapabilityResult(
            task_id=task.task_id,
            capability=self.name,
            supported=True,
            status="success",
            artifacts=(artifacts,),
            payload={
                "language": fetch_result.language,
                "subtitle_format": fetch_result.subtitle_format,
                "subtitle_source_kind": fetch_result.source_kind,
                "title": fetch_result.title,
            },
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_path(value: object) -> Path | None:
    text = _optional_str(value)
    if text is None:
        return None
    return Path(text)


def _resolved_output_name(task: TaskSpec) -> str | None:
    explicit = sanitize_output_base_name(task.output_contract.output_name_base)
    if explicit is not None:
        return explicit
    title = sanitize_output_base_name(_optional_str(task.raw_metadata.get("title")))
    if title is not None:
        return title
    return None
