from __future__ import annotations

import argparse
import json
import os
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flowscribe.app.models import DownloadOptions, SourceSpec, TranscriptionJob
from flowscribe.app.service import _build_pipeline, _settings_from_job
from flowscribe.core.models import MediaItem
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.media.audio_extractor import FfmpegAudioExtractor

PLACEHOLDER_PREFIXES = ("<provide-", "<placeholder", "TODO:", "todo:")
LOCAL_WHISPER_BENCHMARK_MODEL = "small"
NATIVE_ENGINE_BENCHMARK_MODEL = Path("models") / "ggml-small.en.bin"
NATIVE_ENGINE_BENCHMARK_THREADS = 8


@dataclass(frozen=True)
class BenchmarkSample:
    id: str
    source_kind: str
    media_kind: str
    duration_bucket: str
    value: str
    language: str | None
    enabled: bool
    notes: str = ""


@dataclass(frozen=True)
class BenchmarkRunResult:
    sample_id: str
    provider_name: str
    run_kind: str
    source_kind: str
    media_kind: str
    duration_bucket: str
    success: bool
    skipped: bool
    skip_reason: str | None
    error: str | None
    total_elapsed_seconds: float | None
    stages: dict[str, float]
    transcript_path: str | None
    native_chunked: dict[str, Any] | None = None
    progressive_summary: dict[str, Any] | None = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark FlowScribe transcription providers.")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("scripts") / "benchmark_matrix.example.json",
        help="Benchmark matrix JSON. Default: scripts/benchmark_matrix.example.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs") / "benchmarks",
        help="Directory for benchmark report and artifacts. Default: outputs/benchmarks",
    )
    parser.add_argument(
        "--providers",
        default="local-whisper,native-engine",
        help="Comma-separated provider names. Default: local-whisper,native-engine",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=NATIVE_ENGINE_BENCHMARK_MODEL,
        help="Native-engine ggml model path. Default: models/ggml-small.en.bin",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for decoding. Default: 5",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=NATIVE_ENGINE_BENCHMARK_THREADS,
        help=f"Native-engine decode threads. Default: {NATIVE_ENGINE_BENCHMARK_THREADS}",
    )
    parser.add_argument(
        "--sample-ids",
        default=None,
        help="Comma-separated sample IDs to run. Default: all samples in the matrix",
    )
    parser.add_argument(
        "--warm-runs",
        type=int,
        default=1,
        help="Additional warm runs per provider after the first cold run. Default: 1",
    )
    parser.add_argument(
        "--progressive",
        action="store_true",
        help="Enable native-engine chunked transcription for benchmark runs.",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=120.0,
        help="Native chunk size in seconds when --progressive is set. Default: 120",
    )
    parser.add_argument(
        "--chunk-overlap-seconds",
        type=float,
        default=5.0,
        help="Native chunk overlap in seconds when --progressive is set. Default: 5",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Native chunk parallelism cap. Use 0 for auto. Default: 0",
    )
    args = parser.parse_args(argv)

    matrix = load_samples(args.matrix)
    matrix = filter_samples(matrix, args.sample_ids)
    providers = tuple(item.strip() for item in args.providers.split(",") if item.strip())
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[BenchmarkRunResult] = []
    for sample in matrix:
        for provider_name in providers:
            print(f"Running sample={sample.id} provider={provider_name} run=cold", flush=True)
            result = run_sample(
                sample,
                provider_name=provider_name,
                run_kind="cold",
                output_root=args.output_dir,
                native_model=args.model,
                beam_size=args.beam_size,
                native_threads=args.threads,
                progressive_enabled=args.progressive,
                chunk_seconds=args.chunk_seconds,
                overlap_seconds=args.chunk_overlap_seconds,
                max_workers=args.max_workers,
            )
            print(format_run_summary(result), flush=True)
            results.append(result)
            for index in range(args.warm_runs):
                run_kind = f"warm-{index + 1}"
                print(f"Running sample={sample.id} provider={provider_name} run={run_kind}", flush=True)
                result = run_sample(
                    sample,
                    provider_name=provider_name,
                    run_kind=run_kind,
                    output_root=args.output_dir,
                    native_model=args.model,
                    beam_size=args.beam_size,
                    native_threads=args.threads,
                    progressive_enabled=args.progressive,
                    chunk_seconds=args.chunk_seconds,
                    overlap_seconds=args.chunk_overlap_seconds,
                    max_workers=args.max_workers,
                )
                print(format_run_summary(result), flush=True)
                results.append(
                    result
                )

    json_path = args.output_dir / "results.json"
    report_path = args.output_dir / "report.md"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "environment": environment_summary(),
        "config": benchmark_config(
            args.model,
            args.beam_size,
            args.threads,
            progressive_enabled=args.progressive,
            chunk_seconds=args.chunk_seconds,
            overlap_seconds=args.chunk_overlap_seconds,
            max_workers=args.max_workers,
        ),
        "matrix_path": str(args.matrix.resolve()),
        "results": [asdict(result) for result in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        render_report(payload["environment"], results, payload["config"]),
        encoding="utf-8",
    )

    print(f"Wrote benchmark JSON: {json_path}")
    print(f"Wrote benchmark report: {report_path}")
    return 0


def load_samples(path: Path) -> list[BenchmarkSample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkSample(**sample) for sample in payload["samples"]]


def benchmark_config(
    model: Path,
    beam_size: int,
    threads: int | None,
    *,
    progressive_enabled: bool = False,
    chunk_seconds: float = 120.0,
    overlap_seconds: float = 5.0,
    max_workers: int = 0,
) -> dict[str, Any]:
    return {
        "native_model": str(model),
        "beam_size": beam_size,
        "native_threads": threads,
        "chunked_enabled": progressive_enabled,
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "max_workers": max_workers,
    }


def filter_samples(samples: list[BenchmarkSample], sample_ids: str | None) -> list[BenchmarkSample]:
    if sample_ids is None:
        return samples
    requested = tuple(item.strip() for item in sample_ids.split(",") if item.strip())
    if not requested:
        return samples
    by_id = {sample.id: sample for sample in samples}
    missing = [sample_id for sample_id in requested if sample_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown benchmark sample ID(s): {', '.join(missing)}")
    return [by_id[sample_id] for sample_id in requested]


def format_run_summary(result: BenchmarkRunResult) -> str:
    status = "skipped" if result.skipped else ("ok" if result.success else "failed")
    total = "n/a" if result.total_elapsed_seconds is None else f"{result.total_elapsed_seconds:.3f}s"
    notes = result.skip_reason or result.error
    suffix = "" if not notes else f" notes={notes}"
    return (
        f"Finished sample={result.sample_id} provider={result.provider_name} "
        f"run={result.run_kind} status={status} total={total} "
        f"prepare={result.stages['prepare_audio']:.3f}s "
        f"transcribe={result.stages['transcribe']:.3f}s "
        f"write={result.stages['write_outputs']:.3f}s{suffix}"
    )


def run_sample(
    sample: BenchmarkSample,
    *,
    provider_name: str,
    run_kind: str,
    output_root: Path,
    native_model: Path = NATIVE_ENGINE_BENCHMARK_MODEL,
    beam_size: int = 5,
    native_threads: int | None = NATIVE_ENGINE_BENCHMARK_THREADS,
    progressive_enabled: bool = False,
    chunk_seconds: float = 120.0,
    overlap_seconds: float = 5.0,
    max_workers: int = 0,
) -> BenchmarkRunResult:
    skip_reason = validate_sample(sample)
    if skip_reason is not None:
        return BenchmarkRunResult(
            sample_id=sample.id,
            provider_name=provider_name,
            run_kind=run_kind,
            source_kind=sample.source_kind,
            media_kind=sample.media_kind,
            duration_bucket=sample.duration_bucket,
            success=False,
            skipped=True,
            skip_reason=skip_reason,
            error=None,
            total_elapsed_seconds=None,
            stages={"download": 0.0, "prepare_audio": 0.0, "transcribe": 0.0, "write_outputs": 0.0},
            transcript_path=None,
            native_chunked=None,
            progressive_summary=None,
        )

    sample_output_dir = output_root / sample.id / provider_name / run_kind
    sample_output_dir.mkdir(parents=True, exist_ok=True)
    stages = {"download": 0.0, "prepare_audio": 0.0, "transcribe": 0.0, "write_outputs": 0.0}
    started = time.perf_counter()
    transcript_path = None
    try:
        job = build_job(
            sample,
            provider_name=provider_name,
            output_dir=sample_output_dir,
            native_model=native_model,
            beam_size=beam_size,
            native_threads=native_threads,
            progressive_enabled=progressive_enabled,
            chunk_seconds=chunk_seconds,
            overlap_seconds=overlap_seconds,
            max_workers=max_workers,
        )
        measured = measure_stages(job)
        stages.update(measured["stages"])
        transcript_path = measured["transcript_path"]
        return BenchmarkRunResult(
            sample_id=sample.id,
            provider_name=provider_name,
            run_kind=run_kind,
            source_kind=sample.source_kind,
            media_kind=sample.media_kind,
            duration_bucket=sample.duration_bucket,
            success=True,
            skipped=False,
            skip_reason=None,
            error=None,
            total_elapsed_seconds=time.perf_counter() - started,
            stages=stages,
            transcript_path=transcript_path or None,
            native_chunked=measured.get("native_chunked"),
            progressive_summary=measured.get("progressive_summary"),
        )
    except Exception as exc:
        return BenchmarkRunResult(
            sample_id=sample.id,
            provider_name=provider_name,
            run_kind=run_kind,
            source_kind=sample.source_kind,
            media_kind=sample.media_kind,
            duration_bucket=sample.duration_bucket,
            success=False,
            skipped=False,
            skip_reason=None,
            error=str(exc),
            total_elapsed_seconds=time.perf_counter() - started,
            stages=stages,
            transcript_path=transcript_path,
            native_chunked=None,
            progressive_summary=None,
        )


def validate_sample(sample: BenchmarkSample) -> str | None:
    if not sample.enabled:
        return "disabled in matrix"
    value = sample.value.strip()
    if not value:
        return "empty sample value"
    if value.startswith(PLACEHOLDER_PREFIXES):
        return "placeholder sample value"
    if sample.source_kind == "local" and not Path(value).expanduser().exists():
        return f"local sample path does not exist: {value}"
    return None


def build_job(
    sample: BenchmarkSample,
    *,
    provider_name: str,
    output_dir: Path,
    native_model: Path = NATIVE_ENGINE_BENCHMARK_MODEL,
    beam_size: int = 5,
    native_threads: int | None = NATIVE_ENGINE_BENCHMARK_THREADS,
    progressive_enabled: bool = False,
    chunk_seconds: float = 120.0,
    overlap_seconds: float = 5.0,
    max_workers: int = 0,
) -> TranscriptionJob:
    source = build_source(sample)
    model_name = (
        LOCAL_WHISPER_BENCHMARK_MODEL
        if provider_name == "local-whisper"
        else str(native_model)
    )
    return TranscriptionJob(
        sources=(source,),
        output_dir=output_dir,
        work_dir=output_dir / ".work",
        provider_name=provider_name,
        model_name=model_name,
        language=sample.language,
        beam_size=beam_size,
        native_threads=native_threads if provider_name == "native-engine" else None,
        output_formats=("json",),
        progressive_enabled=bool(progressive_enabled),
        progressive_chunk_seconds=chunk_seconds,
        progressive_chunk_overlap_seconds=overlap_seconds,
        progressive_max_workers=max_workers,
    )


def build_source(sample: BenchmarkSample) -> SourceSpec:
    if sample.source_kind == "local":
        return SourceSpec(kind="local", value=sample.value)
    return SourceSpec(
        kind="url",
        value=sample.value,
        keep_media=False,
        download_options=DownloadOptions(quality="best"),
    )


def measure_stages(job: TranscriptionJob) -> dict[str, Any]:
    stages = {"download": 0.0, "prepare_audio": 0.0, "transcribe": 0.0, "write_outputs": 0.0}
    source = job.sources[0]
    if source.kind == "url":
        downloader = UrlAudioDownloader(
            download_dir=job.output_dir / ".download",
            max_bytes=job.max_download_mb * 1024 * 1024,
            max_duration_seconds=job.max_duration_seconds,
            timeout_seconds=job.download_timeout_seconds,
            network_family=job.network_family,
            cookies_path=job.cookies_path,
            proxy=job.proxy,
        )
        started = time.perf_counter()
        download = downloader.download_audio(source.value)
        stages["download"] = time.perf_counter() - started
        media_path = download.path
    else:
        media_path = Path(source.value)

    preparer = FfmpegAudioExtractor()
    started = time.perf_counter()
    prepared = preparer.prepare(MediaItem(path=media_path), job.work_dir or (job.output_dir / ".work"))
    stages["prepare_audio"] = time.perf_counter() - started

    try:
        settings = _settings_from_job(job, recursive=False)
        pipeline = _build_pipeline(job, settings)
        started = time.perf_counter()
        transcript = pipeline._transcriber.transcribe(prepared)
        stages["transcribe"] = time.perf_counter() - started
        started = time.perf_counter()
        artifacts = pipeline._artifact_writer.write_all(transcript, job.output_dir)
        stages["write_outputs"] = time.perf_counter() - started
        transcript_path = str(artifacts.json_path or artifacts.txt_path or "")
        native_chunked = None
        progressive_summary = None
        if transcript_path:
            progressive_summary = read_progressive_metadata(Path(transcript_path))
            if job.provider_name == "native-engine":
                native_chunked = read_native_chunked_metadata(Path(transcript_path))
        return {
            "stages": stages,
            "transcript_path": transcript_path or None,
            "native_chunked": native_chunked,
            "progressive_summary": progressive_summary,
        }
    finally:
        prepared.path.unlink(missing_ok=True)


def environment_summary() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "cwd": str(Path.cwd()),
    }


def read_native_chunked_metadata(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".json" or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "chunked_enabled": payload.get("chunked_enabled"),
        "chunk_count": payload.get("chunk_count"),
        "runtime_count": payload.get("runtime_count"),
        "effective_parallel_chunks": payload.get("effective_parallel_chunks"),
        "chunk_threads": payload.get("chunk_threads"),
        "chunk_seconds": payload.get("chunk_seconds"),
        "overlap_seconds": payload.get("overlap_seconds"),
        "chunk_metrics": payload.get("chunk_metrics"),
    }


def read_progressive_metadata(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".json" or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        progressive = metadata.get("progressive")
        if isinstance(progressive, dict):
            return {
                "progressive_backend": progressive.get("backend"),
                "progressive_mode": progressive.get("mode"),
                "resume_requested": progressive.get("resume_requested"),
                "resume_supported": progressive.get("resume_supported"),
                "resume_used": progressive.get("resume_used"),
                "cache_supported": progressive.get("cache_supported"),
                "chunk_count": progressive.get("chunk_count"),
                "effective_parallel_chunks": progressive.get("effective_parallel_chunks"),
                "chunk_seconds": progressive.get("chunk_seconds"),
                "overlap_seconds": progressive.get("overlap_seconds"),
            }
    native_chunked = read_native_chunked_metadata(path)
    if native_chunked is None:
        return None
    return {
        "progressive_backend": "native-engine" if native_chunked.get("chunked_enabled") else None,
        "progressive_mode": "native-engine-progressive" if native_chunked.get("chunked_enabled") else None,
        "resume_requested": False,
        "resume_supported": False,
        "resume_used": False,
        "cache_supported": False,
        "chunk_count": native_chunked.get("chunk_count"),
        "effective_parallel_chunks": native_chunked.get("effective_parallel_chunks"),
        "chunk_seconds": native_chunked.get("chunk_seconds"),
        "overlap_seconds": native_chunked.get("overlap_seconds"),
    }


def render_report(
    environment: dict[str, Any],
    results: list[BenchmarkRunResult],
    config: dict[str, Any] | None = None,
) -> str:
    config = config or {}
    lines = [
        "# FlowScribe Benchmark Report",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Platform: {environment['platform']}",
        f"- Python: {environment['python_version']}",
        f"- CPU count: {environment['cpu_count']}",
        f"- Native model: {config.get('native_model', str(NATIVE_ENGINE_BENCHMARK_MODEL))}",
        f"- Beam size: {config.get('beam_size', 5)}",
        f"- Native threads: {config.get('native_threads') or 'auto'}",
        f"- Chunked enabled: {config.get('chunked_enabled', False)}",
        f"- Chunk seconds: {config.get('chunk_seconds', 120.0)}",
        f"- Overlap seconds: {config.get('overlap_seconds', 5.0)}",
        f"- Max workers: {config.get('max_workers', 0)}",
        "",
        "## Results",
        "",
        "| Sample | Provider | Run | Status | Total (s) | Download | Prepare | Transcribe | Write | Chunks | Runtimes | Parallel | Threads | Notes |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        status = "skipped" if result.skipped else ("ok" if result.success else "failed")
        notes = result.skip_reason or result.error or ""
        total = "" if result.total_elapsed_seconds is None else f"{result.total_elapsed_seconds:.3f}"
        chunked = result.progressive_summary or result.native_chunked or {}
        if result.progressive_summary:
            backend = result.progressive_summary.get("progressive_backend")
            mode = result.progressive_summary.get("progressive_mode")
            if backend and mode:
                notes = f"{notes}; {backend}/{mode}" if notes else f"{backend}/{mode}"
        lines.append(
            "| {sample} | {provider} | {run} | {status} | {total} | {download:.3f} | {prepare:.3f} | {transcribe:.3f} | {write:.3f} | {chunks} | {runtimes} | {parallel} | {threads} | {notes} |".format(
                sample=result.sample_id,
                provider=result.provider_name,
                run=result.run_kind,
                status=status,
                total=total,
                download=result.stages["download"],
                prepare=result.stages["prepare_audio"],
                transcribe=result.stages["transcribe"],
                write=result.stages["write_outputs"],
                chunks=chunked.get("chunk_count", ""),
                runtimes=(result.native_chunked or {}).get("runtime_count", ""),
                parallel=chunked.get("effective_parallel_chunks", ""),
                threads=(result.native_chunked or {}).get("chunk_threads", ""),
                notes=notes.replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- URL runs include separate download and prepare stages so network variability does not hide provider differences.",
            "- Placeholder or disabled samples are skipped until real local paths and URLs are provided.",
            "- Warm runs represent repeated executions in the same benchmark session.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
