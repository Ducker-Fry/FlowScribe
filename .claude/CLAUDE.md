# CLAUDE.md

Project guidance for Claude Code (claude.ai/code) when working in this repository.

## Project Overview

FlowScribe is a local-first audio/video transcription toolkit for Windows. Provides a CLI (`flowscribe`) and PySide6 desktop GUI for transcribing local media and public URL audio, with transcript review, editing, search, and re-export.

**Stack**: Python 3.10+ CLI + PySide6 GUI + .NET 8 WASAPI helper (system audio capture)  
**Current release**: v0.2.7  
**License**: MIT

## Quick Commands

```powershell
# Run tests (redirect output to save tokens)
python -m pytest > test.log 2>&1; Get-Content test.log -Tail 5
python -m pytest -p no:cacheprovider --basetemp="$env:TEMP\pytest-fs" tests/test_file.py

# Lint
python -m ruff check src tests

# Build CLI package
.\scripts\build_exe.ps1 > build.log 2>&1; Get-Content build.log | Select-String "error|Done|Release"

# Build GUI package (run after CLI build, not in parallel)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python > gui_build.log 2>&1

# Smoke tests
.\dist\FlowScribe\FlowScribe.exe doctor
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test

# Run from source
python -m flowscribe --help
python -m flowscribe.gui

# Release (commit then tag)
git commit -m "Prepare v0.x.y"; git push; git tag v0.x.y; git push origin v0.x.y
```

## Package Layout

```
src/flowscribe/
├── app/            Service layer — TranscriptionService, ProgressEvent, TranscriptionJob
├── cli/main.py     Argparse dispatch (transcribe/url/inspect/search)
├── config/         Runtime settings, presets
├── core/           Domain models, pipeline orchestration, progressive chunking, ports, errors
├── gui/            PySide6 — main_window.py, qt_app.py (entry), state.py, utils.py
├── input/          Local file discovery, URL download/inspection
├── library/        Transcript library (JSON-backed persistent index)
├── media/          ffmpeg extraction, WASAPI capture, audio cache
├── nlp/            Chinese word alignment (jieba), simplified conversion (opencc)
├── output/         Writers for txt/md/json/srt/vtt, path builder
├── search/         Full-text search over transcript JSON
├── transcript/     Transcript editing, re-export from existing JSON
└── transcription/  Provider abstraction + LocalWhisperTranscriber (faster-whisper)
tests/              28 test files matching source modules
scripts/            build_exe.ps1, build_gui_exe.ps1, build_wasapi_helper.ps1
tools/              wasapi-capture-helper/ (.NET 8 C# WASAPI loopback capture)
docs/               Developer handoff, dev-state, packaging, release-automation, roadmap
```

## Core Architecture

Layered pipeline: `InputSource → MediaPreparer → Transcriber → ArtifactWriter`

Key files by layer:
- **`core/`** — domain models, `LocalTranscriptionPipeline` orchestrator, progressive chunking, `ports.py` (protocols), `errors.py` (error hierarchy)
- **`app/service.py`** — `TranscriptionService.run(job)` entry point, wires pipeline, emits progress
- **`gui/main_window.py`** — `MainWindow(QMainWindow)` (3322 lines), all UI logic
- **`gui/qt_app.py`** — `run_gui()` entry point, `FlowScribeMainWindow` compat wrapper
- **`gui/utils.py`** — 68 stateless pure functions for state payloads, formatting, rendering
- **`gui/workers/transcription_worker.py`** — `TranscriptionWorker` (QThread wrapper)
- **`gui/widgets/source_list_widget.py`** — `SourceListWidget` (drag-drop media list)
- **`cli/main.py`** — argparser dispatch to service
- **`input/url_downloader.py`** — `UrlAudioDownloader.download_audio()` (yt-dlp/ffmpeg)
- **`media/audio_extractor.py`** — `FfmpegAudioExtractor`, `PreparedAudioCache`
- **`transcription/providers.py`** — `LocalWhisperTranscriber` (faster-whisper wrapper)

Detailed class table → [CLAUDE_CLASSES.md](CLAUDE_CLASSES.md) (read on demand)

## Key Workflows

```
CLI:        flowscribe transcribe → app/service.py → pipeline.process[_progressive]()
GUI:        Start click → state.to_job() → _TranscriptionWorker → service.run(progress=...) → Qt signal
URL:        SourceSpec(url) → _run_url_source() → UrlAudioDownloader → pipeline → optional media preserve
Chunk flow: transcribe_clip() → FixedDurationChunkPlanner [30s+3s overlap] → Executor [serial/parallel, retry×1] → MergePolicy → ConsistencyChecker → Cache.persist()
```

## Key Dependencies

- `faster-whisper>=1.0` — local speech-to-text (CTranslate2 + Whisper)
- `PySide6>=6.7` — desktop GUI
- `yt-dlp>=2025.1` — URL media extraction
- `jieba>=0.42` — Chinese text segmentation
- `opencc-python-reimplemented>=0.1.7` — Traditional→Simplified Chinese
- External: `ffmpeg`/`ffprobe`, `WasapiCaptureHelper.exe` (.NET 8)

## Testing Patterns

- pytest with `testpaths = ["tests"]`; Ruff lint (line-length 100)
- Mock-based testing for service, URL downloader, progressive executor
- Run focused: `python -m pytest tests/test_file.py`

## Workflow Preferences

- **Light mode** (default): Code changes only. Skip docs. No commits unless asked. Focused tests/checks only.
- **Standard mode**: Code + tests + lint + commit.
- **Wrap-up mode**: Full test suite + build + docs + release if requested.
- User runs builds/tests themselves and shares relevant output only.
