# FlowScribe Development State

Use this file as the compact handoff context when starting a new conversation.

## Project

- Name: FlowScribe
- Path: `E:\Draft\FlowScribe`
- Language: Python
- Current phase: Phase 7, Guided Recovery, Comparison, And Session Flow

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

- Latest successful GitHub Release: `v0.2.6`
- Release assets:
  - `FlowScribe-v0.2.6-windows-x64.zip`
  - `FlowScribeGUI-v0.2.6-windows-x64.zip`
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
- Optional custom output basename control for generated artifacts.
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
- Consolidated `Views` workspace for run details, transcript review, artifact
  inspection, and transcript library access.
- Transcript segment editing, corrected-save flow, and transcript re-export.
- Local transcript library with missing-state tracking and output discovery.
- Library filtering by source kind, missing state, and opened state.
- Library sorting by last opened, updated, created, and label order.
- Recent transcript labels aligned more closely with library metadata.
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
Skip non-essential docs by default.
Do not commit unless asked.
Run only focused tests/checks.
```

## Phase 6 Outcome

Phase 6 is complete from a product-milestone perspective and wrapped in
`v0.2.6`.

Implemented in the phase:

- Phase 6.1 workspace consolidation:
  - `Views` is now the main review workspace instead of a loose collection of
    separate windows.
  - Transcript playback, search, segment review, editing, and artifact
    inspection are grouped into one denser workspace layout.
  - Transcript library actions can run inside `Views`.
  - Base `Views` tab visibility and current-tab preferences are persisted as
    non-sensitive GUI state.
- Phase 6.2 transcript library review ergonomics:
  - Transcript library entries can be filtered by source kind, missing state,
    and opened state.
  - Transcript library entries can be sorted by created time, updated time,
    last opened time, or label, with ascending or descending direction.
  - Library summary text surfaces how many results are shown and how many are
    missing.
  - Recent transcript display is closer to library display so reopening work
    feels more consistent.
- Phase 6.3 artifact review and comparison ergonomics:
  - Artifact viewing is more format-aware across `.json`, `.txt`, `.md`,
    `.srt`, and `.vtt`.
  - Workspace artifact switching is faster for transcript JSON, corrected JSON,
    subtitles, Markdown, and text exports.
  - Transcript JSON is presented in a more readable summary-oriented form for
    non-technical review.
- Phase 6.4 onboarding and diagnostics:
  - The GUI now includes a `Help` entry point for first-run guidance and common
    diagnostics.
  - Help and diagnostics now use more user-facing language and avoid exposing
    unnecessary absolute environment paths.
  - Desktop-visible diagnostics are clearer about output folder readiness,
    capture prerequisites, and common next steps.
- Phase 6.5 release workflow reliability:
  - Release automation now checks out and verifies the requested tag ref.
  - Release publication follows a create-or-update path instead of assuming
    create-only behavior.
  - Asset upload supports overwrite on rerun, and workflow logs are clearer
    about create, update, and upload phases.
- Phase 6.6 docs and verification:
  - GUI, packaging, release, roadmap, and phase planning docs were refreshed.
  - Focused regression checks were expanded around GUI behavior and release
    workflow expectations.

Phase 6 summary and Phase 7 planning are tracked in:

- `docs/phase-6-summary-and-phase-7-plan.md`
- `docs/phase-7-task-list.md`

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

## Current Phase Progress

Phase 4 is complete and shipped in `v0.2.4`.

Phase 5 is complete from a product-milestone perspective and wrapped in
`v0.2.5`.

Phase 5 progress:

- Milestone 5.1 is implemented in the current working flow.
- A local transcript library now lives under `src/flowscribe/library/`.
- Transcript library entries persist transcript path, media path, output
  directory, created/updated timestamps, display label, source kind, last-opened
  timestamp, missing-file state, media binding metadata, and generated output
  records.
- The library store uses a project-friendly JSON persistence model with
  corrupted-store recovery instead of introducing a database dependency.
- Milestone 5.2 is implemented in the current working flow.
- Completed transcription runs are now indexed into the transcript library.
- Opening transcript JSON files updates or creates library entries and refreshes
  `last_opened_at`.
- Media bind and rebind actions now update transcript library metadata.
- Library cleanup and remove-from-library behavior are available without
  deleting user files by default.
- Existing recent-work behavior remains available as a lightweight compatibility
  layer.
- Milestone 5.3 is implemented in the current working flow.
- The GUI now exposes a dedicated `Transcript Library` window.
- Users can reopen transcripts, open output folders, bind or rebind media,
  remove entries, and clean missing items from the library view.
- Recent Work remains as a separate quick-access surface instead of being folded
  away.
- Milestone 5.4 is implemented in the current working flow.
- The transcript viewer now supports segment text editing in the GUI.
- Edited transcript JSON preserves timing and ordering while recording
  correction metadata.
- Users are prompted before overwriting the original transcript and warned about
  unsaved edits when switching or closing.
- Milestone 5.5 is implemented in the current working flow.
- Transcript JSON can now be re-exported to `.txt`, `.md`, `.json`, `.srt`, and
  `.vtt` without rerunning transcription.
- The GUI exposes a re-export action for the current transcript and reuses
  output configuration from the desktop form.
- Milestone 5.6 is implemented in the current working flow.
- Named export profiles now persist output-format and timestamp preferences as
  non-sensitive GUI settings.
- The same profiles can be applied to both new transcription jobs and transcript
  JSON re-export.
- Milestone 5.7 is implemented in the current working flow.
- The local faster-whisper path now sits behind an explicit provider boundary in
  `src/flowscribe/transcription/providers.py`.
- Provider capability metadata now describes model support, language behavior,
  word timestamps, cost expectations, latency expectations, and credential
  requirements.
- Local whisper remains the default provider and no credential management was
  introduced in this phase.
- Milestone 5.8 is implemented in the current working flow.
- System capture now reports `idle`, `active`, or `stalled` feedback based on
  whether the captured WAV file is still growing.
- GUI messaging for missing helper binaries, unsupported devices, and startup
  failures is clearer and remains visible without enabling noisy packaged logs.
- The GUI now exposes a unified `Views` window for run details, transcript
  review, and generated transcript artifacts such as `.txt`, `.md`, `.json`,
  `.srt`, and `.vtt`.
- Transcript review now keeps media sync inside the same transcript-facing view
  instead of splitting segment navigation and playback across separate windows.
- Release installation and packaging documentation now describe transcript
  library, correction, re-export, export profiles, helper troubleshooting, and
  capture activity feedback.
- CLI and GUI package smoke checks remain intact, and packaging docs now note
  that CLI and GUI build scripts should run sequentially because they share the
  top-level `build/` workspace.
- The release workflow now needs to tolerate reruns and existing release tags as
  part of normal maintenance rather than assuming create-only release paths.

Phase 6 planning is tracked in:

- `docs/phase-5-summary-and-phase-6-plan.md`
- `docs/phase-6-task-list.md`

Phase 4 completion details:

- Milestone 4.1 is implemented in the current working flow.
- Non-sensitive GUI preferences can now be saved and restored.
- The GUI exposes explicit `Save Settings` and `View Settings` actions.
- Settings inspection now opens in a dedicated window instead of mixing with run
  details.
- Milestone 4.2 is implemented in the current working flow.
- The GUI now exposes `Cancel Transcription` and `Open Output Folder`.
- Cancellation uses a cooperative canceled-state flow instead of reporting a
  generic failure.
- Right-side action buttons have been rearranged into a more compact multi-row
  layout so they stay visible without horizontal scrolling.
- Milestone 4.3 is implemented in the current working flow.
- The GUI now remembers recent transcript JSON files, recent output
  directories, recent transcription tasks, and recent transcript/media binding
  pairs.
- Recent work opens in a dedicated desktop window so users can reopen prior
  transcript review state quickly after restart.
- Missing recent files and folders are handled gracefully and removed from the
  remembered list when selected.
- Milestone 4.4 is implemented in the current working flow.
- Playback now keeps transcript segment selection aligned with current media
  position.
- Search-hit navigation, segment activation, and playback progress now share a
  more consistent transcript-selection path.
- Media binding state is now shown explicitly as unbound, auto-bound, or
  manually bound.
- Transcript/media mismatch warnings are now surfaced in the GUI instead of
  remaining implicit.
- The GUI can now persist and reuse a custom output basename so generated
  transcript artifacts do not have to follow the source stem.
- Milestone 4.5 is implemented as a Windows-focused MVP in the current working
  flow.
- The GUI now exposes `Start Capture` and `Stop Capture` for system-audio
  recording, writing captured audio to WAV and feeding it back into the normal
  local-source transcription path.
- Capture can keep the WAV file or delete it automatically after the current
  transcription run.
- The current capture implementation now refuses fake-success silent recordings
  and only enables capture when ffmpeg can see a loopback-like Windows device
  such as `Stereo Mix`, `What U Hear`, `Wave Out`, or `virtual-audio-capturer`.
- On machines without a loopback-capable input path, the GUI now reports that
  limitation clearly instead of leaving behind misleading silent WAV files.
- WASAPI helper Phase 1 is implemented.
- A dedicated C#/.NET helper project now lives under
  `tools/wasapi-capture-helper/`.
- The helper targets `net8.0-windows` and `win-x64`, with `NAudio` pinned to
  version `2.2.1`.
- WASAPI helper Phase 2 is implemented.
- `WasapiCaptureHelper.exe` now supports `version`, `probe`, `list-devices`,
  and `capture`.
- Helper command output is machine-readable JSON.
- `capture` writes WAV output through NAudio WASAPI loopback capture and stops
  cleanly when stdin receives `stop`.
- WASAPI helper Phase 3 is implemented.
- Python now has a helper integration boundary in
  `src/flowscribe/media/system_audio_capture_helper.py`.
- Python capture models now live in
  `src/flowscribe/media/system_audio_capture_models.py`.
- `WasapiHelperCaptureRecorder` can locate the helper in source and packaged
  layouts, run `version`, `probe`, and `list-devices`, start capture, send
  `stop`, and return the finalized WAV path.
- `CaptureController` is available as the GUI-facing facade for the next GUI
  hookup phase.
- WASAPI helper Phase 4 is implemented.
- The PySide6 GUI now owns `CaptureController` instead of directly owning the
  legacy ffmpeg/dshow recorder.
- GUI startup probes helper support and enables `Start Capture` only when the
  helper reports a supported default output device.
- GUI start/stop capture now runs through the helper-backed controller while
  preserving the existing captured-WAV local-source workflow and keep/delete
  behavior.
- WASAPI helper Phase 5 is implemented.
- `scripts/build_wasapi_helper.ps1` publishes the helper into
  `build/wasapi-helper/`.
- `scripts/build_gui_exe.ps1` now builds or verifies the helper, copies the
  helper executable plus framework-dependent runtime files into
  `dist/FlowScribeGUI/`, and smoke-tests the packaged helper with `version`.
- WASAPI helper Phase 6 is implemented.
- `.github/workflows/release.yml` now sets up .NET 8 before packaging, relies
  on the GUI build to bundle the helper, verifies `WasapiCaptureHelper.exe`
  exists inside `dist/FlowScribeGUI/`, and runs packaged helper `version` and
  `probe` smoke checks before creating release archives.
- WASAPI helper Phase 7 is implemented.
- The previous ffmpeg/DirectShow capture implementation now lives in
  `src/flowscribe/media/system_audio_capture_legacy.py` as
  `LegacyDshowCaptureRecorder`.
- `src/flowscribe/media/system_audio_capture.py` is now a compatibility import
  module for older callers only.
- Normal GUI capture remains helper-first through `CaptureController`; dshow no
  longer defines the GUI capture UX.
- Milestone 4.6 is implemented in the current working flow.
- The `v0.2.4` GitHub Release successfully builds and publishes both CLI and
  GUI Windows x64 portable packages.
- Release automation verifies the CLI package, GUI package, and bundled
  `WasapiCaptureHelper.exe` smoke checks.
- Release and installation documentation now tracks the `v0.2.4` artifact names
  and packaged GUI helper contents.
- Phase 4 is complete from a product-milestone perspective and wrapped in
  `v0.2.4`.
- Phase 5 planning is tracked in
  `docs/phase-4-summary-and-phase-5-plan.md` and
  `docs/phase-5-task-list.md`.
- Current helper validation:

  ```powershell
  dotnet build .\tools\wasapi-capture-helper\WasapiCaptureHelper.sln -c Release
  .\tools\wasapi-capture-helper\src\WasapiCaptureHelper\bin\x64\Release\net8.0-windows\win-x64\WasapiCaptureHelper.exe version
  .\tools\wasapi-capture-helper\src\WasapiCaptureHelper\bin\x64\Release\net8.0-windows\win-x64\WasapiCaptureHelper.exe probe
  .\tools\wasapi-capture-helper\src\WasapiCaptureHelper\bin\x64\Release\net8.0-windows\win-x64\WasapiCaptureHelper.exe list-devices
  python -m pytest tests\test_system_audio_capture.py tests\test_system_audio_capture_helper.py
  python -m ruff check src\flowscribe\media\system_audio_capture_helper.py src\flowscribe\media\system_audio_capture_models.py tests\test_system_audio_capture_helper.py
  python -m pytest tests\test_gui_qt_app.py tests\test_gui_state.py tests\test_system_audio_capture_helper.py
  python -m compileall src\flowscribe\gui src\flowscribe\media
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_wasapi_helper.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python -SkipHelperBuild
  .\dist\FlowScribeGUI\WasapiCaptureHelper.exe version
  .\dist\FlowScribeGUI\WasapiCaptureHelper.exe probe
  .\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
  python -m pytest tests\test_system_audio_capture.py tests\test_system_audio_capture_helper.py tests\test_gui_qt_app.py
  python -m ruff check src\flowscribe\media\system_audio_capture.py src\flowscribe\media\system_audio_capture_legacy.py tests\test_system_audio_capture.py
  ```
