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
python -m flowscribe serve  # Start Bookmarklet server

# Release (commit then tag)
git commit -m "Prepare v0.x.y"; git push; git tag v0.x.y; git push origin v0.x.y
```

## Package Layout

```
src/flowscribe/
├── app/            Service layer — TranscriptionService, ProgressEvent, TranscriptionJob
├── cli/main.py     Argparse dispatch (transcribe/url/inspect/search/serve)
├── config/         Runtime settings, presets
├── core/           Domain models, pipeline orchestration, progressive chunking, ports, errors
│   └── progressive/  Modular progressive transcription (planner, merger, executor)
├── gui/            PySide6 — main_window.py, qt_app.py (entry), state.py
│   ├── utils/      Modular utility functions (formatting, state, library, artifacts)
│   ├── windows/    MainWindow mixins (transcription, viewer, library, workspace, capture, settings, queue)
│   ├── widgets/    Queue tab, source list, custom UI components
│   └── workers/    QThread workers (transcription, queue runner)
├── input/          Local file discovery, URL download/inspection, URL security validation
├── library/        Transcript library (JSON-backed persistent index)
├── media/          ffmpeg extraction, WASAPI capture, audio cache
├── nlp/            Chinese word alignment (jieba), simplified conversion (opencc)
├── output/         Writers for txt/md/json/srt/vtt, path builder
├── queue/          Batch queue system (models, store, importers, runner)
├── search/         Full-text search over transcript JSON
├── server/         HTTP server for Bookmarklet integration (bookmarklet_server.py, handlers.py)
├── transcript/     Transcript editing, re-export from existing JSON
└── transcription/  Provider abstraction + LocalWhisperTranscriber (faster-whisper)
tests/              41 test files matching source modules
scripts/            build_exe.ps1, build_gui_exe.ps1, build_wasapi_helper.ps1
tools/              wasapi-capture-helper/ (.NET 8 C# WASAPI loopback capture)
docs/               Developer handoff, dev-state, packaging, release-automation, roadmap
```

## Core Architecture

Layered pipeline: `InputSource → MediaPreparer → Transcriber → ArtifactWriter`

Key files by layer:
- **`core/`** — domain models, `LocalTranscriptionPipeline` orchestrator, progressive chunking, deduplication, `ports.py` (protocols), `errors.py` (error hierarchy)
- **`core/progressive/`** — modular progressive transcription: `planner.py` (chunk planning), `merger.py` (merge policy), `executor.py` (execution & cache)
- **`core/deduplication.py`** — `TranscriptDeduplicator` (post-processing duplicate removal at chunk boundaries)
- **`app/service.py`** — `TranscriptionService.run(job)` entry point, wires pipeline, emits progress
- **`gui/main_window.py`** — `MainWindow(QMainWindow)` (1198 lines), core UI logic with mixin inheritance
- **`gui/windows/`** — MainWindow mixins: `transcription_controls.py`, `transcript_viewer_controls.py`, `library_controls.py`, `workspace_controls.py`, `capture_controls.py`, `settings_controls.py`, `queue_controls.py`
- **`gui/utils/`** — modular utility functions: `formatting.py`, `state.py`, `library.py`, `artifacts.py`
- **`gui/qt_app.py`** — `run_gui()` entry point, `FlowScribeMainWindow` compat wrapper
- **`gui/workers/transcription_worker.py`** — `TranscriptionWorker` (QThread wrapper)
- **`gui/workers/queue_runner.py`** — `QueueRunner` (sequential batch processor)
- **`gui/widgets/queue_tab_widget.py`** — Queue tab UI (URL paste, import, drag-reorder)
- **`gui/widgets/source_list_widget.py`** — `SourceListWidget` (drag-drop media list)
- **`queue/models.py`** — `QueueItem`, `QueueItemSettings`, `BatchOutputStrategy`
- **`queue/store.py`** — `BatchQueueStore` (JSON persistence at `{AppData}/FlowScribe/batch-queue.json`)
- **`queue/importers.py`** — URL parsing, .txt/.csv/.xlsx import, deduplication
- **`server/bookmarklet_server.py`** — `BookmarkletServer` (HTTP server for browser integration)
- **`server/handlers.py`** — `AddUrlHandler` (request processing, queue integration)
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
Bookmarklet: Browser click → POST /add-url → AddUrlHandler → BatchQueueStore.enqueue() → GUI auto-refresh
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
- **File watcher integration**: GUI auto-refreshes when queue file changes (e.g., from Bookmarklet server)
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

## Token Efficiency Guidelines

**Core Principle**: Minimize token consumption through targeted reads, precise operations, and user-driven verification.

**File Reading**:
- Use `Grep` to locate code patterns before reading files (e.g., `Grep pattern="class TranscriptionService" type="py"`)
- Use `Glob` to find files by pattern instead of reading directories (e.g., `Glob pattern="**/test_*.py"`)
- Read only the specific files needed for the task — avoid exploratory reads
- Use `offset` and `limit` parameters for large files (read relevant sections only)
- Never re-read a file just edited — trust the Edit/Write tool succeeded
- Check CLAUDE_CLASSES.md reference table before reading implementation files

**Testing Strategy**:
- Run **targeted tests only** — specify exact test file/function (e.g., `pytest tests/test_queue_store.py::test_enqueue`)
- Redirect output and show summary: `python -m pytest tests/test_file.py > test.log 2>&1; Get-Content test.log -Tail 10`
- Skip full test suite unless explicitly requested or in wrap-up mode
- User runs tests and shares relevant output — don't run tests proactively
- Avoid `--verbose` flag — use default output or `-q` for quieter output

**Command Execution**:
- Redirect verbose command output to files: `command > output.log 2>&1`
- Filter output with `Select-String`, `Get-Content -Tail`, or `grep` equivalents
- Show only errors, warnings, and summary lines from build/lint output
- User runs builds/lints themselves — provide commands, don't execute unless asked

**Code Changes**:
- Make focused edits — change only what's needed for the task
- Avoid refactoring unrelated code during bug fixes
- Skip adding comments unless the WHY is non-obvious
- Don't add defensive error handling for impossible scenarios
- Trust internal code contracts — validate only at system boundaries

**Verification**:
- Skip verification reads after edits unless the change is safety-critical (auth, data handling, infrastructure)
- For simple changes (typo fix, parameter rename), trust the edit succeeded
- For complex changes, verify with targeted grep/read, not full file re-read
- User will report if something broke — don't verify proactively

**Documentation**:
- Skip updating docs unless explicitly requested or in standard/wrap-up mode
- Don't create README/CHANGELOG entries for internal changes
- Update CLAUDE.md only for architectural changes or new patterns

**Communication**:
- One-sentence status updates at key moments only
- End-of-turn summary: 1-2 sentences max
- Skip narrating internal deliberation or tool choices
- Don't explain what the code does if the code is self-explanatory

**Anti-Patterns to Avoid**:
- ❌ Reading entire file to verify a small edit
- ❌ Running full test suite for a single-function change
- ❌ Reading multiple files to understand context before making a targeted fix
- ❌ Re-reading files already read in the same conversation
- ❌ Verbose command output without filtering
- ❌ Proactive verification of non-critical changes
- ❌ Adding comments explaining WHAT the code does
- ❌ Refactoring surrounding code during focused fixes

**Preferred Patterns**:
- ✅ Grep → targeted read → edit → done
- ✅ User provides error → direct fix → user verifies
- ✅ Glob to find files → read only relevant ones
- ✅ Redirect output → show summary only
- ✅ Trust edit succeeded → move to next task

## Code Organization Guidelines

**File Size Limits**: To maintain readability and avoid context overflow:
- **Maximum file size**: 500 lines per file (strict limit)
- **Target file size**: 200-300 lines per file (recommended)
- **When creating new files**: Always check line count before writing
- **When modifying files**: If a file exceeds 500 lines after changes, split it into focused modules

**Refactoring Strategy**:
- Use **Mixin pattern** for large classes (see `gui/main_window.py` → `gui/windows/*.py`)
- Use **module packages** for large modules (see `core/progressive.py` → `core/progressive/*.py`)
- Create **compatibility shims** to maintain backward compatibility (re-export from `__init__.py`)
- Group related functions into focused modules by responsibility

**Recent Refactoring** (2026-05):
- `gui/main_window.py`: 3269 lines → 1198 lines (7 mixins in `gui/windows/`)
- `core/progressive.py`: 973 lines → 40 lines (3 modules in `core/progressive/`)
- `gui/utils.py`: 929 lines → 154 lines (4 modules in `gui/utils/`)
- Removed: `media/system_audio_capture_legacy.py` (323 lines, unused)

**Writing New Code**:
- Start with focused, single-responsibility modules
- If a module grows beyond 300 lines, consider splitting before it reaches 500
- Use clear module names that describe their specific purpose
- Prefer multiple small files over one large file
