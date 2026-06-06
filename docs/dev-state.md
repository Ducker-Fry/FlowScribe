# FlowScribe Development State

Use this file as the compact handoff context when starting a new conversation.
For the shortest operational summary, start with `docs/developer-handoff.md`
and then return here for more detail.

## Project

- Name: FlowScribe
- Path: `E:\Draft\FlowScribe`
- Language: Python
- Current version: v0.3.3
- Next release: v1.0.0 (major release in preparation)
- Current branch: `dev`
- Main branch: `main`
- Current phase: Performance Optimization & UI Enhancement

## Product Goal

FlowScribe is a local-first audio/video transcription tool. It supports local
files, URL audio extraction, structured transcript outputs, keyword timestamp
location, and ships with a desktop GUI for non-technical users.

The long-term goal is an open-source, portfolio-quality project that can:

- Turn local media and public URL media into text.
- Produce machine-readable transcript JSON.
- Locate keywords and timestamps.
- Provide a GUI for daily use.
- Keep core logic decoupled from the frontend.

## Current Release

- Latest GitHub Release: use the newest tag published on GitHub Releases
- Release assets:
  - `FlowScribe-vX.Y.Z-windows-x64.zip`
  - `FlowScribeGUI-vX.Y.Z-windows-x64.zip`
- Next major release: `v1.0.0` (in preparation)

## Completed Capabilities

### CLI

- Local transcription: `flowscribe transcribe video.mp4 -o outputs`
- URL transcription: `flowscribe url "https://example.com/video" -o outputs`
- Source inspection: `flowscribe inspect <path-or-url>`
- Transcript search: `flowscribe search transcript.json "keyword"`
- Progressive transcription for long media with chunk cache and resume support
- Bookmarklet server: `flowscribe serve` for browser integration

### GUI

**Architecture**: QStackedWidget with toolbar navigation (v0.3.0 refactor)

- **NewMainWindow** (375 lines): Simplified from legacy 1198-line MainWindow
- **SingleTaskView**: Local files, URLs, system audio capture, "Open Transcript" button
- **LibraryView**: Transcript library with filtering, sorting, and actions
- **QueueView**: Batch queue with local files + URLs, bookmarklet server integration
- **SettingsDialog**: Standalone settings dialog
- **Modular utilities**: Focused modules for formatting, state, library, artifacts

Key features:
- Drag-and-drop local source handling
- URL input with validation
- System audio capture (WASAPI helper)
- Transcript JSON viewer with editing and re-export
- Keyword search with click-to-jump navigation
- Local media playback and seek
- Batch queue with auto-retry and drag-reorder
- Bookmarklet server for browser-based URL addition
- Title-based display for queue items (web page title instead of URL)
- Auto-indexing completed transcriptions to library
- Queue file watcher for external changes

### Outputs

Supported formats: `txt`, `md`, `json`, `srt`, `vtt`

### Timing And Search

- Segment-level timestamps
- Provider word timestamps
- Chinese natural-word alignment (jieba)
- Traditional→Simplified Chinese conversion (opencc)
- Keyword search with time filters, context length, limit, and JSON output

### Automation

- `pytest` test suite (44 test files)
- `ruff` linting
- GitHub Actions CI
- GitHub Actions Release workflow
- Windows x64 portable release packaging
- `ffmpeg.exe`, `ffprobe.exe`, and `WasapiCaptureHelper.exe` bundled in releases

## v1.0.0 Development Roadmap

FlowScribe is entering v1.0.0 after completing the GUI refactor (v0.3.0) that
simplified the interface from 1198 lines to 375 lines with modular architecture.

### v1.0.0 Focus Areas

**1. CLI Performance Optimization**

Goal: Make CLI the high-performance transcription engine for power users and automation.

Priority improvements:
- Optimize progressive transcription for long media (reduce overhead)
- Improve chunk merging accuracy and speed
- Enhance parallel processing efficiency
- Reduce memory footprint for large files
- Add performance profiling and benchmarking tools
- Optimize Chinese word alignment performance

**2. GUI UI Enhancement**

Goal: Polish the GUI for better user experience and visual appeal.

Priority improvements:
- Modern UI styling (color scheme, typography, spacing)
- Improved visual feedback for transcription progress
- Enhanced queue view with better status indicators
- Refined settings dialog layout and organization
- Better error message presentation
- Improved transcript viewer readability
- Add dark mode support (optional)

**3. Chinese Transcription Optimization**

Goal: Improve accuracy and performance for Chinese language transcription.

Priority improvements:
- Optimize jieba word segmentation performance
- Improve Traditional/Simplified Chinese conversion accuracy
- Enhance Chinese word timestamp alignment
- Better handling of mixed Chinese/English content
- Optimize Chinese text rendering in GUI
- Add Chinese-specific transcription presets

### v1.0.0 Success Criteria

- CLI performance: 20-30% speed improvement for long media
- GUI polish: Modern, consistent visual design across all views
- Chinese transcription: Improved accuracy and 15-25% speed boost
- Stability: All existing features working reliably
- Documentation: Updated for v1.0.0 features and improvements

### Post-v1.0.0 Considerations

- Cloud transcription provider integration (OpenAI Whisper API, Azure Speech)
- Multi-language UI support (i18n)
- Advanced editing features (segment splitting, merging)
- Export templates and customization
- Plugin system for extensibility

## User Workflow Preference

Use explicit work modes:

### Light Mode (default)

```text
Only change code.
Skip non-essential docs by default.
Do not commit unless asked.
Run only focused tests/checks.
```

### Standard Mode

```text
Change code.
Add or update focused tests.
Run relevant tests and lint.
Commit changes.
```

### Wrap-Up Mode

```text
Update docs.
Run full tests.
Build/package if needed.
Create release if requested.
Summarize stage results.
```

### Discussion Mode

```text
Only analyze and explain.
Do not read many files.
Do not modify code.
```

## Recommended Context Rebuild Order

When starting a new conversation, open:

1. `docs/developer-handoff.md`
2. `docs/dev-state.md` (this file)
3. `docs/roadmap.md`

For v1.0.0 development work:

4. **Performance optimization**: `src/flowscribe/core/progressive/`, `src/flowscribe/transcription/providers.py`
5. **GUI enhancement**: `src/flowscribe/gui/new_main_window.py`, `src/flowscribe/gui/views/`, `src/flowscribe/gui/dialogs/`
6. **Chinese optimization**: `src/flowscribe/nlp/`, `src/flowscribe/transcription/providers.py`

For packaging or release work:

7. `docs/packaging.md`
8. `docs/release-automation.md`
9. `.github/workflows/release.yml`

## Key Commands

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
git commit -m "Prepare v1.0.0"; git push; git tag v1.0.0; git push origin v1.0.0
```
