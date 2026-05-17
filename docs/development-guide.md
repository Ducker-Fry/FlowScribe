# Development Guide

This guide explains how to work on FlowScribe as a developer.

For the quickest current-project context, read
`docs/developer-handoff.md` before this guide.

## Setup

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev,gui]
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

Build the desktop GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

See [Packaging](packaging.md) for release details.

Create a tagged release:

```powershell
git tag v0.1.1
git push origin v0.1.1
```

See [Release Automation](release-automation.md) for the GitHub Actions release workflow.

## Fast Context Rebuild

If you are starting work in a fresh conversation, use this order:

1. `docs/developer-handoff.md`
2. `docs/dev-state.md`
3. `docs/roadmap.md`
4. `docs/long-media-progressive-transcription-task-list.md`

Then open the relevant code entry points for the task at hand.

## Current High-Signal Work Areas

### Progressive Long-Media Transcription

This is the current primary engineering line.

Look here first:

- `src/flowscribe/core/progressive.py`
- `src/flowscribe/core/pipeline.py`
- `src/flowscribe/app/service.py`
- `src/flowscribe/cli/main.py`
- `src/flowscribe/gui/qt_app.py`

Already landed:

- chunk planning
- chunk cache and resume
- GUI progress events, duration progress, and ETA plumbing
- limited worker concurrency groundwork
- CLI progressive options and auto-selection rules
- conservative Chinese-oriented overlap and merge protection

### URL Media Preservation

The GUI URL workflow now includes user-visible media preservation choices and
auto-binding behavior.

Look here:

- `src/flowscribe/input/url_downloader.py`
- `src/flowscribe/app/models.py`
- `src/flowscribe/app/service.py`
- `src/flowscribe/gui/state.py`
- `src/flowscribe/gui/qt_app.py`

Implemented behavior:

- save no media, saved audio, or saved video
- custom save directory
- auto-bind saved media to the transcript
- fallback messaging when requested video preservation resolves to audio only

## Development Workflow

1. Update requirements or architecture notes when changing behavior.
2. Keep the CLI thin and put business behavior in core or adapters.
3. Add or update tests for the changed module.
4. Run focused `pytest` checks first, then broader checks if risk grows.
5. Run focused `ruff` checks first, then broader checks if needed.
6. Update README, developer docs, and user-facing docs when behavior changes.
7. If packaging or release behavior changed, update `docs/packaging.md` and
   `docs/release-automation.md` in the same step.

## Focused Verification Commands

Progressive core and service work:

```powershell
python -m pytest tests\test_progressive_transcription.py tests\test_app_service.py tests\test_cli_main.py
python -m ruff check src\flowscribe\core src\flowscribe\app src\flowscribe\cli tests\test_progressive_transcription.py tests\test_app_service.py tests\test_cli_main.py
```

GUI and URL workflow work:

```powershell
python -m pytest tests\test_gui_state.py tests\test_gui_qt_app.py tests\test_url_input.py tests\test_app_service.py
python -m ruff check src\flowscribe\gui src\flowscribe\input\url_downloader.py src\flowscribe\app tests\test_gui_state.py tests\test_gui_qt_app.py tests\test_url_input.py tests\test_app_service.py
```

Packaging and release smoke validation:

```powershell
.\scripts\build_exe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
.\dist\FlowScribe\FlowScribe.exe doctor
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
.\dist\FlowScribeGUI\WasapiCaptureHelper.exe version
.\dist\FlowScribeGUI\WasapiCaptureHelper.exe probe
```

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
- Long URL-derived media.
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
