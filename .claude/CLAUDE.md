# CLAUDE.md

Project guidance for Claude Code (claude.ai/code) when working in this repository.

## Project Overview

FlowScribe is a local-first audio/video transcription toolkit for Windows. Provides a CLI (`flowscribe`) and PySide6 desktop GUI for transcribing local media and public URL audio, with transcript review, editing, search, and re-export.

**Stack**: Python 3.10+ CLI + PySide6 GUI + .NET 8 WASAPI helper (system audio capture)  
**Current release**: v0.3.3  
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

## Codegraph

Use the workspace-local codegraph before broad exploration or multi-file reads.

```powershell
python scripts/build_codegraph.py
python scripts/query_codegraph.py search TranscriptionService
python scripts/query_codegraph.py show flowscribe.app.service.TranscriptionService
python scripts/query_codegraph.py neighbors flowscribe.providers.transcribe.registry.ParaformerProvider
```

Generated artifacts:

- `.codex/codegraph/index.json`
- `.codex/codegraph/summary.md`

## Package Layout

```
src/flowscribe/
├── app/            Service layer — TranscriptionService, ProgressEvent, TranscriptionJob
├── cli/main.py     Argparse dispatch (transcribe/url/inspect/search/serve)
├── config/         Runtime settings, presets
├── core/           Domain models, pipeline orchestration, progressive chunking, ports, errors
│   └── progressive/  Modular progressive transcription (planner, merger, executor)
├── gui/            PySide6 — new_main_window.py, qt_app.py (entry), state.py
│   ├── dialogs/    Settings dialog, queue item settings dialog
│   ├── views/      SingleTaskView, LibraryView, QueueView (QStackedWidget architecture)
│   ├── utils/      Modular utility functions (formatting, state, library, artifacts)
│   ├── windows/    Legacy MainWindow mixins (deprecated, kept for reference)
│   ├── widgets/    Source list, custom UI components
│   └── workers/    QThread workers (transcription, queue runner, bookmarklet server)
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
docs/               Developer handoff, dev-state, packaging, release-automation, roadmap, ui-refactor docs
```

## Core Architecture

Layered pipeline: `InputSource → MediaPreparer → Transcriber → ArtifactWriter`

Key files by layer:
- **`core/`** — domain models, `LocalTranscriptionPipeline` orchestrator, progressive chunking, deduplication, `ports.py` (protocols), `errors.py` (error hierarchy)
- **`core/progressive/`** — modular progressive transcription: `planner.py` (chunk planning), `merger.py` (merge policy), `executor.py` (execution & cache)
- **`core/deduplication.py`** — `TranscriptDeduplicator` (post-processing duplicate removal at chunk boundaries)
- **`app/service.py`** — `TranscriptionService.run(job)` entry point, wires pipeline, emits progress
- **`gui/new_main_window.py`** — `NewMainWindow(QMainWindow)` (375 lines), simplified QStackedWidget architecture
- **`gui/views/`** — Standalone views: `SingleTaskView` (350 lines), `LibraryView` (230 lines), `QueueView` (450 lines)
- **`gui/dialogs/`** — `SettingsDialog` (240 lines), `QueueItemSettingsDialog`
- **`gui/utils/`** — modular utility functions: `formatting.py`, `state.py`, `library.py`, `artifacts.py`
- **`gui/qt_app.py`** — `run_gui()` entry point, `FlowScribeMainWindow` compat wrapper
- **`gui/workers/transcription_worker.py`** — `TranscriptionWorker` (QThread wrapper)
- **`gui/workers/queue_runner.py`** — `QueueRunner` (sequential batch processor)
- **`gui/workers/bookmarklet_server_worker.py`** — `BookmarkletServerWorker` (QThread wrapper for HTTP server)
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

Prefer `.codex/codegraph/summary.md` and `python scripts/query_codegraph.py ...` for current navigation.  
Legacy class table fallback → [CLAUDE_CLASSES.md](CLAUDE_CLASSES.md)

## Key Workflows

```
CLI:        flowscribe transcribe → app/service.py → pipeline.process[_progressive]()
GUI:        Start click → SingleTaskView._start_transcription() → TranscriptionWorker → service.run(progress=...) → Qt signal
Queue:      Add items → QueueItem → QueueRunner.run() → dequeue → service.run() → mark completed
Bookmarklet: Browser click → POST /add-url → AddUrlHandler → BatchQueueStore.enqueue() → GUI auto-refresh
URL:        SourceSpec(url) → _run_url_source() → UrlAudioDownloader → pipeline → optional media preserve
Chunk flow: transcribe_clip() → FixedDurationChunkPlanner [30s+3s overlap] → Executor [serial/parallel, retry×1] → MergePolicy → ConsistencyChecker → Deduplicator → Cache.persist()
```

## GUI Architecture (v0.3.0+)

**New QStackedWidget Architecture**: Single main window with toolbar navigation between views.

```
NewMainWindow (QMainWindow)
├── Toolbar: Settings | Single Task | Library | Queue
└── QStackedWidget
    ├── [0] SingleTaskView — Source selection, transcription controls, Run Details, Workspace
    ├── [1] LibraryView — Transcript library with filters, sorting, and actions
    └── [2] QueueView — Batch queue with local file + URL support, bookmarklet server
```

**Key Features**:
- **Settings Dialog**: Standalone dialog (not embedded), saves space
- **Single Task View**: Local files, URLs, system audio capture in one view; "Open Transcript" button to load existing JSON files
- **Library View**: Full filtering (source, status, opened), sorting, actions
- **Queue View**: Supports both local files and URLs, bookmarklet server integration, displays titles instead of URLs
- **Transcription View Dialog**: Workspace with "Open Transcript" button to switch between different transcript files
- **Signal-based communication**: Loose coupling between views and main window
- **Auto-indexing**: Completed transcriptions automatically added to library
- **Queue file watcher**: Auto-refresh when queue changes externally

**Migration from v0.2.x**:
- Old `MainWindow` (1198 lines) → New `NewMainWindow` (375 lines)
- Embedded settings → `SettingsDialog` (240 lines)
- Views dialog tabs → Standalone views (SingleTaskView 350, LibraryView 230, QueueView 450 lines)
- Queue URL-only → Queue supports local files + URLs

## Batch Queue System

**Architecture**: Sequential processor with persistent JSON queue, auto-retry, and drag-reorder UI.

**Key components**:
- `QueueItem` — frozen dataclass with source (local or URL), settings snapshot, output strategy, status, retry count
- `BatchQueueStore` — JSON persistence at `{AppData}/FlowScribe/batch-queue.json`, full-rewrite on mutation
- `QueueRunner` — QObject on QThread, dequeues items one by one, calls `TranscriptionService.run()` per item
- `QueueView` — UI with local file + URL support, file import (.txt/.csv/.xlsx), drag-reorder list

**Features**:
- **Local file support**: Add local media files directly to queue (v0.3.0+)
- Multi-URL import from text/CSV/Excel with deduplication (blocks pending/running/completed, allows failed)
- Smart URL extraction from rich text clipboard (HTML href parsing)
- Batch output strategies: unified directory, per-source subdirs, template naming
- Auto-retry on failure (configurable max retries, default 2)
- Settings snapshot at enqueue time (output dir, formats, model, language, etc.)
- Queue persistence across GUI restarts
- **File watcher integration**: GUI auto-refreshes when queue file changes (e.g., from Bookmarklet server)
- **Bookmarklet server**: Integrated HTTP server for browser-based URL addition
- **Title-based display**: Queue items display web page title (from bookmarklet) instead of URL for better readability
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
- **Queue display**: `QueueItem.display_label` prioritizes `title` field over URL; `QueueView._format_item_display` uses `display_label` for consistent title-based display

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

**CRITICAL: AI writes tests, user executes complex tests. AI MUST NOT run tests with large I/O or output.**

- pytest with `testpaths = ["tests"]`; Ruff lint (line-length 100)
- Mock-based testing for service, URL downloader, progressive executor, queue system, deduplication
- 44 test files covering core, queue, GUI utilities, dialogs, and integration scenarios
- Run focused: `python -m pytest tests/test_file.py`
- Queue tests: `tests/test_queue_models.py`, `tests/test_queue_store.py`, `tests/test_queue_importers.py`, `tests/test_queue_display_title.py`, `tests/test_bookmarklet_title_integration.py`
- Deduplication tests: `tests/test_deduplication.py`, `tests/test_deduplication_integration.py`
- Dialog tests: `tests/test_transcription_view_dialog.py`

## Workflow Preferences

- **Light mode** (default): Code changes only. Skip docs. No commits unless asked. Focused tests/checks only.
- **Standard mode**: Code + tests + lint + commit.
- **Wrap-up mode**: Full test suite + build + docs + release if requested.
- User runs builds/tests themselves and shares relevant output only.

## Conversation Types and Responsibilities

**CRITICAL: Each conversation should have a clear, single responsibility. Declare conversation type at the start.**

### Conversation Categories

**1. Configuration (Meta)**
- **Purpose**: Update CLAUDE.md, manage Memory, adjust workflows, configure hooks/permissions
- **Duration**: Short (complete and end)
- **Output**: Configuration files updated
- **When to use**: Setting up rules, changing preferences, adjusting automation
- **Why separate**: New conversations load updated configs; avoid polluting development context

**2. Feature Development**
- **Purpose**: Implement single new feature with tests
- **Duration**: Medium (dozens to hundreds of turns)
- **Output**: Feature code + tests + commit
- **Scope**: 1-3 modules
- **When to use**: Adding new functionality with clear requirements
- **Why separate**: Focused context on feature requirements and implementation details

**3. Bug Fix**
- **Purpose**: Diagnose and fix single bug with regression test
- **Duration**: Short (few to dozens of turns)
- **Output**: Bug fix + test + commit
- **Scope**: Usually 1-2 files
- **When to use**: Fixing specific reported issues
- **Why separate**: Quick, focused fixes; avoid mixing with feature work

**4. Refactoring**
- **Purpose**: Code structure adjustment, performance optimization, tech debt cleanup
- **Duration**: Medium to long (may use context compression)
- **Output**: Refactored code + verification tests
- **Scope**: May span multiple modules
- **When to use**: Improving code quality without changing behavior
- **Why separate**: Requires maintaining large context; keep separate from feature work

**5. Exploration**
- **Purpose**: Understand existing code, research solutions, evaluate feasibility
- **Duration**: Short (mostly reading and analysis)
- **Output**: Understanding docs, solution proposals
- **Scope**: May be broad
- **When to use**: Before starting implementation, investigating issues
- **Why separate**: Avoid exploratory reads consuming development tokens; use Explore agent

**6. Testing**
- **Purpose**: Write test suites, improve coverage, fix failing tests
- **Duration**: Short to medium
- **Output**: Test files + execution commands (user runs tests)
- **Scope**: Test files only
- **When to use**: Dedicated testing work, improving test coverage
- **Why separate**: AI writes tests, user executes; avoid test output polluting context

**7. Release**
- **Purpose**: Build executables, run full test suite, prepare release, tag and push
- **Duration**: Short (verification-focused)
- **Output**: Release package + git tag
- **Scope**: Build and release process
- **When to use**: Preparing version releases
- **Why separate**: Critical operation requiring focus; clear release checklist

### Core Principles

**Single Responsibility**:
- ✅ One conversation, one primary goal
- ❌ Don't refactor during feature development
- ❌ Don't add features during bug fixes

**Context Efficiency**:
- ✅ Related work in same conversation
- ✅ Unrelated work in new conversation
- ❌ Don't let exploration consume development tokens

**Rule Consistency**:
- ✅ Start new conversation after config changes
- ✅ Start new conversation if AI violates rules
- ✅ Periodically start fresh to reload rules

**Traceability**:
- ✅ Clear output at conversation end
- ✅ Conversation title describes goal
- ✅ Can trace decisions through conversation history

### When to Start New Conversation

**Always start new**:
- Updated CLAUDE.md or Memory
- Beginning independent task
- Previous task completed and verified
- AI behavior anomalies detected

**Consider starting new**:
- Conversation context compressed
- Work type changes (development → refactoring)
- Feature too large (split into multiple conversations)
- Need to explore before implementing

**Can continue**:
- Small related changes
- Bug fix discovered during feature work (if minor)
- Test fixes for code just written


## Token Efficiency Guidelines

**Core Principle**: Minimize token consumption through targeted reads, precise operations, and user-driven verification.

**File Reading**:
- Use `Grep` to locate code patterns before reading files (e.g., `Grep pattern="class TranscriptionService" type="py"`)
- Use `Glob` to find files by pattern instead of reading directories (e.g., `Glob pattern="**/test_*.py"`)
- Use the local codegraph summary/query tools before broad exploration or when you need a symbol map
- Read only the specific files needed for the task — avoid exploratory reads
- Use `offset` and `limit` parameters for large files (read relevant sections only)
- Never re-read a file just edited — trust the Edit/Write tool succeeded
- Check `.codex/codegraph/summary.md` or run `python scripts/query_codegraph.py ...` before opening many files

**Testing Strategy**:
- **AI writes test files, user executes complex tests** — AI creates/modifies test files, provides execution commands, user runs and shares results
- **AI only runs simple, low-token tests** — quick unit tests with minimal output (e.g., single test function, small test files)
- **Complex tests → provide implementation plan** — for integration tests, full test suites, or tests with large I/O, provide detailed test plan and commands for user execution
- Run **targeted tests only** when AI executes — specify exact test file/function (e.g., `pytest tests/test_queue_store.py::test_enqueue`)
- Redirect output and show summary: `python -m pytest tests/test_file.py > test.log 2>&1; Get-Content test.log -Tail 10`
- Skip full test suite unless explicitly requested or in wrap-up mode
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
- ❌ Running complex tests with large I/O or output (user executes these)
- ❌ Reading test output files that exceed 100 lines
- ❌ Reading multiple files to understand context before making a targeted fix
- ❌ Re-reading files already read in the same conversation
- ❌ Verbose command output without filtering
- ❌ Proactive verification of non-critical changes
- ❌ Adding comments explaining WHAT the code does
- ❌ Refactoring surrounding code during focused fixes

**Preferred Patterns**:
- ✅ Grep → targeted read → edit → done
- ✅ User provides error → direct fix → user verifies
- ✅ Write test file → provide execution command → user runs and shares results
- ✅ Simple test (< 5 functions, minimal I/O) → AI runs directly
- ✅ Complex test → provide detailed test plan and commands for user
- ✅ Glob to find files → read only relevant ones
- ✅ Redirect output → show summary only
- ✅ Trust edit succeeded → move to next task

## Code Organization Guidelines

**CRITICAL: Maximum 500 lines per file. MUST split files that exceed this limit.**

**File Size Limits**: To maintain readability and avoid context overflow:
- **Maximum file size**: 500 lines per file (STRICT LIMIT - NO EXCEPTIONS)
- **Target file size**: 200-300 lines per file (recommended)
- **When creating new files**: MUST check line count before writing
- **When modifying files**: If a file exceeds 500 lines after changes, MUST split it into focused modules
- **Before any Write operation**: Count lines in new content, refuse to write if > 500 lines

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
