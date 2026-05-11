# Development Guide

This guide explains how to work on FlowScribe as a developer.

## Setup

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

FlowScribe also requires `ffmpeg` and `ffprobe` on `PATH` for real media processing:

```powershell
ffmpeg -version
ffprobe -version
```

## Common Commands

Run tests:

```powershell
python -m pytest
```

Run lint checks:

```powershell
python -m ruff check src tests
```

The same checks run automatically on GitHub Actions for pushes and pull requests to `main`.

Show CLI help:

```powershell
flowscribe --help
```

Run environment diagnostics:

```powershell
flowscribe doctor -o outputs --model small
```

Run a quick transcription smoke test:

```powershell
flowscribe transcribe "D:\media\sample.wav" -o outputs --model tiny --overwrite
```

Run a Chinese-oriented transcription:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --model small --preset zh --overwrite
```

Run a timestamped multi-format transcription:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --timestamps --format txt,md,json,srt
```

Build a portable Windows executable:

```powershell
.\scripts\build_exe.ps1
```

See [Packaging](packaging.md) for release details.

Create a tagged release:

```powershell
git tag v0.1.1
git push origin v0.1.1
```

See [Release Automation](release-automation.md) for the GitHub Actions release workflow.

## Development Workflow

1. Update requirements or architecture notes when changing behavior.
2. Keep the CLI thin and put business behavior in core or adapters.
3. Add or update tests for the changed module.
4. Run `python -m pytest`.
5. Run `python -m ruff check src tests`.
6. Update README, user guide, or changelog when user-visible behavior changes.

## Adding an Input Source

Create a new module under `src/flowscribe/input`.

The adapter should discover user-provided sources and return core domain objects. Do not make transcription providers aware of where media came from.

Good candidates:

- URL input.
- System audio capture output.
- Browser or downloader handoff.

## Adding a Transcription Provider

Create a new module under `src/flowscribe/transcription`.

The provider should accept a prepared audio artifact and return a `Transcript`. It should record provider-specific settings through `TranscriptionOptions` or a future compatible metadata object.

Provider examples:

- Local faster-whisper.
- WhisperX.
- FunASR or SenseVoice for Chinese-focused recognition.
- External speech-to-text APIs.

## Adding an Output Format

Create a new writer under `src/flowscribe/output`.

The writer should depend only on `Transcript` and `Path`. This keeps output formats independent from input and transcription details.

Output examples:

- SRT.
- VTT.
- JSON.
- DOCX.

## Testing Strategy

Use unit tests for:

- File filtering.
- Settings and presets.
- Output rendering.
- Pipeline orchestration.
- Error handling.

Use manual media tests for:

- Chinese speech.
- English speech.
- Mixed-language speech.
- Long video files.
- Files without audio streams.
- Corrupted or unsupported files.

Do not commit personal media samples or generated transcript outputs.

## Git Hygiene

Ignored local artifacts include:

- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `outputs*/`
- `samples/`
- `media/`

Keep commits focused. A good commit should represent one coherent project step, such as a feature, documentation update, or test improvement.
