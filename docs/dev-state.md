# FlowScribe Development State

Use this file as the compact handoff context when starting a new conversation.

## Project

- Name: FlowScribe
- Path: `E:\Draft\FlowScribe`
- Language: Python
- Current phase: Phase 3, Desktop GUI And Interactive Transcript Workflow

## Product Goal

FlowScribe is a local-first audio/video transcription tool. It supports local
files, URL audio extraction, structured transcript outputs, keyword timestamp
location, and is moving toward a desktop GUI suitable for non-technical users.

The long-term goal is an open-source, portfolio-quality project that can:

- Turn local media and public URL media into text.
- Produce machine-readable transcript JSON.
- Locate keywords and timestamps.
- Provide a GUI for daily use.
- Keep core logic decoupled from the frontend.

## Current Release

- Latest successful GitHub Release: `v0.2.2`
- Release asset: `FlowScribe-v0.2.2-windows-x64.zip`
- Current branch: `main`

## Completed Capabilities

### CLI

- Local transcription:

  ```powershell
  flowscribe transcribe video.mp4 -o outputs
  ```

- URL transcription:

  ```powershell
  flowscribe url "https://example.com/video" -o outputs
  ```

- Source inspection:

  ```powershell
  flowscribe inspect "D:\media\video.mp4"
  flowscribe inspect "https://example.com/video"
  ```

- Transcript search:

  ```powershell
  flowscribe search transcript.json "keyword"
  ```

### Outputs

Supported output formats:

```text
txt
md
json
srt
vtt
```

### Timing And Search

- Segment-level timestamps.
- Provider word timestamps.
- Chinese natural-word alignment.
- `raw_words` plus `words` in JSON.
- Keyword search with time filters, context length, limit, and JSON output.

### URL Options

URL handling supports:

```text
--cookies
--proxy
--network-family
--keep-media
--max-download-mb
--max-duration
--download-timeout
```

### Automation

- `pytest` test suite.
- `ruff` linting.
- GitHub Actions CI.
- GitHub Actions Release workflow.
- Windows x64 portable release packaging.
- `ffmpeg.exe` and `ffprobe.exe` bundled in release packages.

## GUI Status

PySide6 has been selected for the first GUI implementation because it integrates
quickly with the existing Python service layer.

The GUI is intentionally designed as a replaceable shell. A future frontend
could be WebView, a web UI, or another more polished UI without rewriting core
transcription logic.

### GUI Architecture Rule

The GUI should call core logic through:

```text
GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

The GUI should not directly instantiate low-level media, URL, transcription, or
output classes.

### GUI Implemented So Far

- PySide6 GUI skeleton.
- Local file selection.
- URL input field.
- Output directory field.
- Model, language, preset, output format controls.
- Proxy, cookies, and network family controls.
- `Collect State` button to preview job state.
- `Start Transcription` button connected to `TranscriptionService`.
- Background Qt worker thread so the GUI does not freeze.
- Progress messages displayed in the GUI.
- Output file paths displayed in the GUI.
- Failure messages displayed in the GUI.
- GUI executable smoke build:

  ```text
  dist/FlowScribeGUI/FlowScribeGUI.exe
  ```

### GUI Packaging

Script added:

```text
scripts/build_gui_exe.ps1
```

It can build a GUI one-folder executable:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

## Current GUI Milestones

Recent GUI milestones completed in the working tree:

- Milestone 3.2: local-source drag/drop now accepts the same local files and
  folders supported by the CLI.
- Milestone 3.3: GUI URL transcription now validates public http(s) URLs and
  passes `proxy`, `cookies`, and `network-family` through to the shared URL
  service path.
- Milestone 3.4: transcript JSON viewer added to the GUI, including opening an
  existing `.json` transcript and auto-loading JSON output from a completed run.
- Milestone 3.5: search UI added to the GUI, including keyword search, hit
  list display, and click-to-jump transcript navigation.

Current uncommitted files:

```text
docs/dev-state.md
src/flowscribe/gui/qt_app.py
src/flowscribe/gui/state.py
src/flowscribe/gui/transcript_viewer.py
tests/test_app_service.py
tests/test_gui_state.py
tests/test_transcript_viewer.py
```

Change summary:

- Added shared local-source acceptance checks for GUI drag/drop and file lists.
- Reused URL safety validation inside GUI form validation.
- Added transcript JSON loading, segment rendering, and timestamp formatting
  helpers for the GUI.
- Added GUI transcript viewer support for opening existing JSON and auto-loading
  generated JSON output after transcription.
- Added GUI keyword search UI with hit list display and click-to-scroll
  transcript navigation.
- Added focused tests for GUI state, URL option passthrough, transcript viewer,
  and transcript search integration.

Validated with:

```powershell
python -m pytest tests\test_gui_state.py tests\test_app_service.py tests\test_url_input.py tests\test_transcript_viewer.py tests\test_transcript_search.py
python -m ruff check src\flowscribe\gui tests\test_gui_state.py tests\test_app_service.py tests\test_url_input.py tests\test_transcript_viewer.py tests\test_transcript_search.py
python -m compileall src\flowscribe\gui
```

## User Workflow Preference

Use explicit work modes:

### Light Mode

```text
Only change code.
Do not update docs.
Do not commit.
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

Default preference: use Light Mode or Standard Mode unless the user explicitly
asks for Wrap-Up Mode.

## Likely Next Tasks

Possible next Milestone 3 tasks:

- Finish and optionally commit the current drag/drop local source change.
- GUI URL transcription.
- GUI job status improvements.
- GUI cancel task support.
- GUI open output directory button.
- Segment-level media seek from transcript.
