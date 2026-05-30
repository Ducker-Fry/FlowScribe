# Whisper.cpp Engine Benchmarks

This document describes the placeholder benchmark workflow for comparing:

- `local-whisper`
- `native-engine`

The first version uses a matrix file with disabled placeholder samples. Replace those values with
real local media paths and public URLs before drawing performance conclusions.

## Files

- Benchmark script: `scripts/benchmark_transcription.py`
- Sample matrix template: `scripts/benchmark_matrix.example.json`
- Output directory default: `outputs/benchmarks`

## What Is Measured

Each run records:

- `total_elapsed_seconds`
- `download`
- `prepare_audio`
- `transcribe`
- `write_outputs`

This separates network variability from provider-side transcription differences.

## Run

```powershell
cd E:\Draft\FlowScribe
$env:PYTHONPATH="E:\Draft\FlowScribe\src"
python scripts\benchmark_transcription.py --matrix scripts\benchmark_matrix.example.json
```

Optional:

```powershell
python scripts\benchmark_transcription.py --warm-runs 2 --output-dir outputs\benchmarks-demo
```

## Prepare Real Samples

For local media:

- replace `value` with a real local path
- set `enabled` to `true`

For URL media:

- replace `value` with a stable public URL
- set `enabled` to `true`

Leave any unavailable sample disabled. The script will mark it as skipped in both JSON and Markdown outputs.

## Read Outputs

`results.json`

- raw benchmark records
- suitable for later charting or re-analysis

`report.md`

- human-readable table
- includes cold and warm runs
- shows skipped samples and failure reasons

## Notes

- URL runs still use Python for download and audio preparation.
- Native engine gains should mainly appear in the `transcribe` stage and warm-run totals.
- Placeholder samples are expected to be skipped until real media is provided.
