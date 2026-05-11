"""Run a transcription job over one input source."""

from __future__ import annotations

from collections.abc import Callable

from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import JobFailure, JobResult
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.ports import InputSource

ProgressCallback = Callable[[str], None]


class JobRunner:
    def __init__(
        self,
        *,
        input_source: InputSource,
        pipeline: LocalTranscriptionPipeline,
        progress: ProgressCallback | None = None,
    ) -> None:
        self._input_source = input_source
        self._pipeline = pipeline
        self._progress = progress or (lambda message: None)

    def run(self) -> JobResult:
        items = self._input_source.discover()
        outputs = []
        failures = []

        self._progress(f"Discovered {len(items)} media file(s).")
        for index, item in enumerate(items, start=1):
            self._progress(f"[{index}/{len(items)}] Processing {item.path}")
            try:
                artifacts = self._pipeline.process(item)
            except FlowScribeError as exc:
                failures.append(JobFailure(source=item.path, message=str(exc)))
                self._progress(f"Failed: {item.path} - {exc}")
                continue
            outputs.append(artifacts)
            for path in artifacts.paths:
                self._progress(f"Wrote: {path}")

        return JobResult(outputs=tuple(outputs), failures=tuple(failures))
