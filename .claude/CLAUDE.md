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
│   ├── widgets/    Queue tab, source list, custom UI components
│   └── workers/    QThread workers (transcription, queue runner)
├── input/          Local file discovery, URL download/inspection, URL security validation
├── library/        Transcript library (JSON-backed persistent index)
├── media/          ffmpeg extraction, WASAPI capture, audio cache
├── nlp/            Chinese word alignment (jieba), simplified conversion (opencc)
├── output/         Writers for txt/md/json/srt/vtt, path builder
├── queue/          Batch queue system (models, store, importers, runner)
├── search/         Full-text search over transcript JSON
├── transcript/     Transcript editing, re-export from existing JSON
└── transcription/  Provider abstraction + LocalWhisperTranscriber (faster-whisper)
tests/              39 test files matching source modules
scripts/            build_exe.ps1, build_gui_exe.ps1, build_wasapi_helper.ps1
tools/              wasapi-capture-helper/ (.NET 8 C# WASAPI loopback capture)
docs/               Developer handoff, dev-state, packaging, release-automation, roadmap
```

## Core Architecture

Layered pipeline: `InputSource → MediaPreparer → Transcriber → ArtifactWriter`

Key files by layer:
- **`core/`** — domain models, `LocalTranscriptionPipeline` orchestrator, progressive chunking, deduplication, `ports.py` (protocols), `errors.py` (error hierarchy)
- **`core/deduplication.py`** — `TranscriptDeduplicator` (post-processing duplicate removal at chunk boundaries)
- **`app/service.py`** — `TranscriptionService.run(job)` entry point, wires pipeline, emits progress
- **`gui/main_window.py`** — `MainWindow(QMainWindow)` (3400+ lines), all UI logic, queue integration
- **`gui/qt_app.py`** — `run_gui()` entry point, `FlowScribeMainWindow` compat wrapper
- **`gui/utils.py`** — 68 stateless pure functions for state payloads, formatting, rendering
- **`gui/workers/transcription_worker.py`** — `TranscriptionWorker` (QThread wrapper)
- **`gui/workers/queue_runner.py`** — `QueueRunner` (sequential batch processor)
- **`gui/widgets/queue_tab_widget.py`** — Queue tab UI (URL paste, import, drag-reorder)
- **`gui/widgets/source_list_widget.py`** — `SourceListWidget` (drag-drop media list)
- **`queue/models.py`** — `QueueItem`, `QueueItemSettings`, `BatchOutputStrategy`
- **`queue/store.py`** — `BatchQueueStore` (JSON persistence at `{AppData}/FlowScribe/batch-queue.json`)
- **`queue/importers.py`** — URL parsing, .txt/.csv/.xlsx import, deduplication
- **`cli/main.py`** — argparser dispatch to service
- **`input/url_downloader.py`** — `UrlAudioDownloader.download_audio()` (yt-dlp/ffmpeg)
- **`input/url_security.py`** — `validate_public_http_url()` (blocks private IPs, allows Teredo IPv6)
- **`media/audio_extractor.py`** — `FfmpegAudioExtractor`, `PreparedAudioCache`
- **`transcription/providers.py`** — `LocalWhisperTranscriber` (faster-whisper wrapper)

Detailed class table → [CLAUDE_CLASSES.md](CLAUDE_CLASSES.md) (read on demand)

## Key Workflows

```
CLI:        flowscribe transcribe → app/service.py → pipeline.process[_progressive]()
GUI:        Start click → state.to_job() → _TranscriptionWorker → service.run(progress=...) → Qt signal
Queue:      Add URLs → QueueItem → QueueRunner.run() → dequeue → service.run() → mark completed
URL:        SourceSpec(url) → _run_url_source() → UrlAudioDownloader → pipeline → optional media preserve
Chunk flow: transcribe_clip() → FixedDurationChunkPlanner [30s+3s overlap] → Executor [serial/parallel, retry×1] → MergePolicy → ConsistencyChecker → Deduplicator → Cache.persist()
```

## Batch Queue System

**Architecture**: Sequential processor with persistent JSON queue, auto-retry, and drag-reorder UI.

**Key components**:
- `QueueItem` — frozen dataclass with source, settings snapshot, output strategy, status, retry count
- `BatchQueueStore` — JSON persistence at `{AppData}/FlowScribe/batch-queue.json`, full-rewrite on mutation
- `QueueRunner` — QObject on QThread, dequeues items one by one, calls `TranscriptionService.run()` per item
- `QueueTabWidget` — UI in Views dialog with URL paste, file import (.txt/.csv/.xlsx), drag-reorder list

**Features**:
- Multi-URL import from text/CSV/Excel with deduplication (blocks pending/running/completed, allows failed)
- Smart URL extraction from rich text clipboard (HTML href parsing)
- Batch output strategies: unified directory, per-source subdirs, template naming
- Auto-retry on failure (configurable max retries, default 2)
- Settings snapshot at enqueue time (output dir, formats, model, language, etc.)
- Queue persistence across GUI restarts
- Completion notification with sound (planned)

**Important notes**:
- Language "auto" → `None` for faster-whisper compatibility
- Preset "none" → `None` for faster-whisper compatibility
- Output formats read from `self.format_checks` dict in MainWindow
- Default to JSON if no formats selected
- IPv6 Teredo addresses (2001::/32) allowed in URL validation
- Progressive overlap tolerance: 3.0s (increased from 1.5s to handle long audio timestamp drift)
- Progressive timestamp auto-fix: enabled by default to correct Whisper timestamp anomalies in long audio
- CPU optimization: auto-detects CPU-only systems and enables int8 quantization for 15-25% speed boost
- **Transcript deduplication**: enabled by default, removes duplicate segments at chunk boundaries after transcription completes (not during chunk merging)

## Performance Metrics

**Realtime speed**: Processing speed relative to audio duration (e.g., 4.2x = process 1 min audio in 14 sec)
- Typical CPU performance: 3-5x with small model, beam_size=5
- Optimized CPU: 5-7x with int8 quantization, beam_size=1, VAD filter
- GPU acceleration: 10-20x with CUDA-enabled GPU

**Optimization options**:
- Lower beam_size (5→1): +30-40% speed, slight accuracy trade-off
- Smaller model (small→base): +100% speed, moderate accuracy trade-off
- VAD filter: +10-30% speed on audio with silence
- GPU: +200-400% speed (requires NVIDIA GPU with CUDA)

## Key Dependencies

- `faster-whisper>=1.0` — local speech-to-text (CTranslate2 + Whisper)
- `PySide6>=6.7` — desktop GUI
- `yt-dlp>=2025.1` — URL media extraction
- `jieba>=0.42` — Chinese text segmentation
- `opencc-python-reimplemented>=0.1.7` — Traditional→Simplified Chinese
- `openpyxl>=3.1` — Excel file import for batch queue (GUI optional dependency)
- External: `ffmpeg`/`ffprobe`, `WasapiCaptureHelper.exe` (.NET 8)

## Testing Patterns

- pytest with `testpaths = ["tests"]`; Ruff lint (line-length 100)
- Mock-based testing for service, URL downloader, progressive executor, queue system, deduplication
- 41 test files covering core, queue, GUI utilities, and integration scenarios
- Run focused: `python -m pytest tests/test_file.py`
- Queue tests: `tests/test_queue_models.py`, `tests/test_queue_store.py`, `tests/test_queue_importers.py`
- Deduplication tests: `tests/test_deduplication.py`, `tests/test_deduplication_integration.py`

## Workflow Preferences

- **Light mode** (default): Code changes only. Skip docs. No commits unless asked. Focused tests/checks only.
- **Standard mode**: Code + tests + lint + commit.
- **Wrap-up mode**: Full test suite + build + docs + release if requested.
- User runs builds/tests themselves and shares relevant output only.
