# FlowScribe Development State

Use this file as the compact handoff context when starting a new conversation.

## Project

- Name: FlowScribe
- Path: `E:\Draft\FlowScribe`
- Language: Python
- Current phase: Phase 4, Capture, Workflow Persistence, And Desktop Productization

## Product Goal

FlowScribe is a local-first audio/video transcription tool. It supports local
files, URL audio extraction, structured transcript outputs, keyword timestamp
location, and now ships with a usable desktop GUI for non-technical users.

The long-term goal is an open-source, portfolio-quality project that can:

- Turn local media and public URL media into text.
- Produce machine-readable transcript JSON.
- Locate keywords and timestamps.
- Provide a GUI for daily use.
- Keep core logic decoupled from the frontend.

## Current Release

- Latest successful GitHub Release: `v0.2.3`
- Release assets:
  - `FlowScribe-v0.2.3-windows-x64.zip`
  - `FlowScribeGUI-v0.2.3-windows-x64.zip`
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
- Drag-and-drop local source handling.
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
- Transcript JSON viewer.
- Transcript keyword search UI.
- Transcript-bound local media playback and seek.
- Checkbox-based remembered local source selection.
- Quiet packaged GUI logging defaults.
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

Packaged GUI behavior:

- PyInstaller `--windowed` launch path, so release builds do not open a console window.
- Runtime hook defaults packaged GUI runs to `FLOWSCRIBE_GUI_LOG_MODE=user`.
- GUI smoke test entry point:

  ```powershell
  .\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
  ```

## Phase 3 Outcome

Phase 3 is now complete from a product-milestone perspective. It delivered the
first usable desktop workflow:

- Milestone 3.2: local-source drag/drop now accepts the same local files and
  folders supported by the CLI.
- Milestone 3.3: GUI URL transcription now validates public http(s) URLs and
  passes `proxy`, `cookies`, and `network-family` through to the shared URL
  service path.
- Milestone 3.4: transcript JSON viewer added to the GUI, including opening an
  existing `.json` transcript and auto-loading JSON output from a completed run.
- Milestone 3.5: search UI added to the GUI, including keyword search, hit
  list display, and click-to-jump transcript navigation.
- Milestone 3.6: local media sync MVP added, including transcript-bound media
  binding, local playback, and seek-on-segment / seek-on-search-hit behavior.
- Source list selection has been refined from implicit batch inputs to explicit
  checkbox-based local source selection with remembered checked state.

Phase 3 summary:

- Added shared local-source acceptance checks for GUI drag/drop and file lists.
- Reused URL safety validation inside GUI form validation.
- Added transcript JSON loading, segment rendering, and timestamp formatting
  helpers for the GUI.
- Added GUI transcript viewer support for opening existing JSON and auto-loading
  generated JSON output after transcription.
- Added GUI keyword search UI with hit list display and click-to-scroll
  transcript navigation.
- Added transcript-bound local media playback with explicit media binding when
  the original transcript source cannot be auto-resolved.
- Changed the local source list to visible checkbox selection, so only checked
  local items participate in preview/transcription.
- Added remembered local-source checked state across GUI restarts.
- Added GUI runtime log mode control with `dev` and `user` behavior, plus quiet packaged defaults.
- Added a packaged GUI `--self-test` entry point for smoke validation and release automation.
- Added focused tests for GUI state, URL option passthrough, transcript viewer,
  transcript search integration, GUI local-source state payload handling, and
  GUI logging/entry-point behavior.

Reference document:

```text
docs/phase-3-summary-and-phase-4-plan.md
```

Validated with:

```powershell
python -m pytest
python -m ruff check src tests
python -m compileall src\flowscribe\gui
.\dist\FlowScribe\FlowScribe.exe doctor
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
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

Phase 4 starting points:

- Non-sensitive GUI settings persistence.
- GUI cancel task support.
- GUI open output directory button.
- Recent job / recent transcript history.
- System audio capture prototype.
- Stronger transcript/media synchronization feedback during playback.

Current Phase 4 progress:

- Milestone 4.1 is in progress.
- Non-sensitive GUI preferences can now be saved and restored.
- The GUI exposes explicit `Save Settings` and `View Settings` actions.
- Settings inspection now opens in a dedicated window instead of mixing with run
  details.
