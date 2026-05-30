from __future__ import annotations

from pathlib import Path

import scripts.benchmark_transcription as benchmark_transcription
from scripts.benchmark_transcription import (
    BenchmarkRunResult,
    BenchmarkSample,
    benchmark_config,
    build_job,
    filter_samples,
    format_run_summary,
    load_samples,
    render_report,
    run_sample,
    validate_sample,
)


def test_load_samples_reads_placeholder_matrix() -> None:
    samples = load_samples(Path("scripts") / "benchmark_matrix.example.json")

    assert len(samples) == 12
    assert samples[0].id == "local_audio_short"
    assert samples[-1].id == "url_video_long"


def test_validate_sample_skips_disabled_placeholder() -> None:
    samples = load_samples(Path("scripts") / "benchmark_matrix.example.json")

    reason = validate_sample(samples[3])

    assert reason == "disabled in matrix"


def test_build_job_uses_provider_specific_model_for_placeholder_matrix(tmp_path: Path) -> None:
    sample = load_samples(Path("scripts") / "benchmark_matrix.example.json")[0]
    enabled_sample = type(sample)(
        id=sample.id,
        source_kind=sample.source_kind,
        media_kind=sample.media_kind,
        duration_bucket=sample.duration_bucket,
        value=str(tmp_path / "audio.wav"),
        language=sample.language,
        enabled=True,
        notes=sample.notes,
    )
    (tmp_path / "audio.wav").write_bytes(b"audio")

    local_job = build_job(enabled_sample, provider_name="local-whisper", output_dir=tmp_path / "local")
    native_job = build_job(enabled_sample, provider_name="native-engine", output_dir=tmp_path / "native")

    assert local_job.model_name == "small"
    assert native_job.model_name.endswith("models\\ggml-small.en.bin")
    assert local_job.progressive_enabled is False
    assert native_job.progressive_enabled is False


def test_build_job_applies_benchmark_model_beam_and_native_threads(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    sample = BenchmarkSample(
        id="configured",
        source_kind="local",
        media_kind="audio",
        duration_bucket="long",
        value=str(audio),
        language="en",
        enabled=True,
    )
    model = tmp_path / "ggml-small.en-q8_0.bin"

    native_job = build_job(
        sample,
        provider_name="native-engine",
        output_dir=tmp_path / "native",
        native_model=model,
        beam_size=1,
        native_threads=8,
        progressive_enabled=True,
        chunk_seconds=120.0,
        overlap_seconds=5.0,
        max_workers=0,
    )
    local_job = build_job(
        sample,
        provider_name="local-whisper",
        output_dir=tmp_path / "local",
        native_model=model,
        beam_size=1,
        native_threads=8,
    )

    assert native_job.model_name == str(model)
    assert native_job.beam_size == 1
    assert native_job.native_threads == 8
    assert native_job.progressive_enabled is True
    assert native_job.progressive_chunk_seconds == 120.0
    assert native_job.progressive_chunk_overlap_seconds == 5.0
    assert native_job.progressive_max_workers == 0
    assert local_job.model_name == "small"
    assert local_job.beam_size == 1
    assert local_job.native_threads is None


def test_benchmark_config_records_native_decode_settings(tmp_path: Path) -> None:
    model = tmp_path / "ggml-small.en-q5_1.bin"

    config = benchmark_config(
        model,
        beam_size=1,
        threads=6,
        progressive_enabled=True,
        chunk_seconds=120.0,
        overlap_seconds=5.0,
        max_workers=0,
    )

    assert config == {
        "native_model": str(model),
        "beam_size": 1,
        "native_threads": 6,
        "chunked_enabled": True,
        "chunk_seconds": 120.0,
        "overlap_seconds": 5.0,
        "max_workers": 0,
    }


def test_filter_samples_selects_requested_ids_in_order() -> None:
    samples = load_samples(Path("scripts") / "benchmark_matrix.example.json")

    selected = filter_samples(samples, "local_audio_long,local_audio_short")

    assert [sample.id for sample in selected] == ["local_audio_long", "local_audio_short"]


def test_filter_samples_rejects_unknown_id() -> None:
    samples = load_samples(Path("scripts") / "benchmark_matrix.example.json")

    try:
        filter_samples(samples, "missing_sample")
    except SystemExit as exc:
        assert "missing_sample" in str(exc)
    else:
        raise AssertionError("Expected SystemExit for an unknown sample ID")


def test_run_sample_uses_single_measured_execution(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    sample = BenchmarkSample(
        id="single_run",
        source_kind="local",
        media_kind="audio",
        duration_bucket="short",
        value=str(audio),
        language="en",
        enabled=True,
    )
    calls = 0

    def fake_measure_stages(job):
        nonlocal calls
        calls += 1
        return {
            "stages": {"download": 0.0, "prepare_audio": 0.1, "transcribe": 0.2, "write_outputs": 0.3},
            "transcript_path": str(job.output_dir / "audio.json"),
        }

    monkeypatch.setattr(benchmark_transcription, "measure_stages", fake_measure_stages)

    result = run_sample(sample, provider_name="native-engine", run_kind="cold", output_root=tmp_path / "out")

    assert result.success is True
    assert calls == 1
    assert result.total_elapsed_seconds is not None
    assert result.total_elapsed_seconds < 1.0


def test_render_report_marks_skipped_and_failed_runs() -> None:
    results = [
        BenchmarkRunResult(
            sample_id="local_audio_short",
            provider_name="local-whisper",
            run_kind="cold",
            source_kind="local",
            media_kind="audio",
            duration_bucket="short",
            success=False,
            skipped=True,
            skip_reason="placeholder sample value",
            error=None,
            total_elapsed_seconds=None,
            stages={"download": 0.0, "prepare_audio": 0.0, "transcribe": 0.0, "write_outputs": 0.0},
            transcript_path=None,
            native_chunked=None,
        ),
        BenchmarkRunResult(
            sample_id="local_audio_short",
            provider_name="native-engine",
            run_kind="cold",
            source_kind="local",
            media_kind="audio",
            duration_bucket="short",
            success=False,
            skipped=False,
            skip_reason=None,
            error="failed to connect",
            total_elapsed_seconds=1.234,
            stages={"download": 0.0, "prepare_audio": 0.111, "transcribe": 0.999, "write_outputs": 0.124},
            transcript_path=None,
            native_chunked={
                "chunk_count": 16,
                "runtime_count": 2,
                "effective_parallel_chunks": 2,
                "chunk_threads": 8,
            },
        ),
    ]

    report = render_report(
        {"platform": "Windows", "python_version": "3.12", "cpu_count": 8},
        results,
        {"native_model": "models/ggml-small.en-q8_0.bin", "beam_size": 1, "native_threads": 8},
    )

    assert "skipped" in report
    assert "failed to connect" in report
    assert "local_audio_short" in report
    assert "ggml-small.en-q8_0.bin" in report
    assert "Beam size: 1" in report
    assert "Native threads: 8" in report
    assert "16" in report
    assert "Threads" in report


def test_format_run_summary_includes_stage_timings() -> None:
    result = BenchmarkRunResult(
        sample_id="local_audio_short",
        provider_name="native-engine",
        run_kind="cold",
        source_kind="local",
        media_kind="audio",
        duration_bucket="short",
        success=True,
        skipped=False,
        skip_reason=None,
        error=None,
        total_elapsed_seconds=1.234,
        stages={"download": 0.0, "prepare_audio": 0.111, "transcribe": 0.999, "write_outputs": 0.124},
        transcript_path=None,
        native_chunked=None,
    )

    summary = format_run_summary(result)

    assert "status=ok" in summary
    assert "total=1.234s" in summary
    assert "transcribe=0.999s" in summary
