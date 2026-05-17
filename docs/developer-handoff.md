# Developer Handoff

Use this document as the fastest way to rebuild context in a new conversation.
It is intentionally shorter and more operational than the broader project docs.

## Project Snapshot

- Project: `FlowScribe`
- Workspace: `E:\Draft\FlowScribe`
- Stack: Python CLI + PySide6 desktop GUI + .NET WASAPI helper
- Current public release: `v0.2.6`
- Current implementation line: `v0.7` long-media progressive transcription

FlowScribe is a local-first transcription tool for local media, URL-derived
media, transcript review, transcript correction, re-export, and Windows desktop
use.

## What Is Stable Right Now

These areas are already productized enough to treat as established behavior:

- CLI local transcription, URL transcription, inspect, search, and doctor flows
- GUI local-file workflow, URL workflow, transcript review, transcript library,
  artifact review, transcript editing, re-export, and help/diagnostics
- Windows portable CLI and GUI packaging
- GitHub Actions CI and create-or-update release automation
- WASAPI helper-based Windows system-playback capture

## Main Recent Work

The most important recent implementation work is concentrated in three areas.

### 1. Long-Media Progressive Transcription

This is the current main engineering thread.

Implemented so far:

- fixed-duration chunk planning with overlap
- progressive state and chunk result models
- prepared-audio duration probing
- serial progressive execution
- per-run chunk cache and resume
- GUI-facing progressive progress events
- GUI transcript preview updates during active runs
- limited parallel worker groundwork
- CLI progressive flags and progressive progress logging

Important files:

- `src/flowscribe/core/progressive.py`
- `src/flowscribe/core/pipeline.py`
- `src/flowscribe/app/models.py`
- `src/flowscribe/app/service.py`
- `src/flowscribe/cli/args.py`
- `src/flowscribe/cli/main.py`
- `src/flowscribe/gui/qt_app.py`

Important tests:

- `tests/test_progressive_transcription.py`
- `tests/test_app_service.py`
- `tests/test_cli_main.py`
- `tests/test_gui_qt_app.py`

### 2. Progressive Accuracy Protection

Progressive transcription now includes conservative quality guards:

- default overlap tuning, with a more conservative Chinese path
- conservative chunk merge behavior
- progressive consistency validation before final transcript output
- protection against aggressive Chinese text de-duplication

Look at:

- `src/flowscribe/core/progressive.py`
- `src/flowscribe/core/pipeline.py`

### 3. URL Media Preservation And Auto-Bind

The GUI URL block now supports more than plain URL transcription.

Implemented so far:

- choose whether to save no media, audio media, or video media
- choose a custom media-save directory
- auto-bind saved URL media back to the transcript workspace
- persist those URL media settings in GUI state
- show fallback status when requested video preservation falls back to audio

Look at:

- `src/flowscribe/input/url_downloader.py`
- `src/flowscribe/app/service.py`
- `src/flowscribe/gui/state.py`
- `src/flowscribe/gui/qt_app.py`
- `src/flowscribe/core/models.py`

## Current Architecture Rules

These rules matter when continuing implementation.

### GUI Boundary

The GUI should stay on this path:

```text
GuiTranscriptionForm -> TranscriptionJob -> TranscriptionService
```

The GUI should not directly orchestrate low-level media prep, URL download, or
transcription provider behavior.

### Core Separation

- `src/flowscribe/core/` owns domain models, orchestration, progressive logic,
  and pipeline behavior
- `src/flowscribe/input/` owns local and URL source handling
- `src/flowscribe/transcription/` owns provider integration
- `src/flowscribe/output/` owns transcript artifact writing
- `src/flowscribe/gui/` owns desktop workflow presentation

### Progressive Strategy

Progressive mode is meant to be conservative first:

- keep short tasks simple
- preserve output compatibility with library, editing, and re-export
- prefer readable segment order over aggressive merge cleverness
- prefer slightly conservative Chinese boundaries over risky de-duplication

## Current CLI And GUI Behavior To Remember

### CLI Progressive Behavior

CLI now supports:

- `--progressive`
- `--no-progressive`
- `--chunk-seconds`
- `--chunk-overlap-seconds`
- `--resume`
- `--max-workers`

Auto behavior currently aims to stay simple:

- long single local files can auto-enable progressive mode
- long single URL jobs can auto-enable progressive mode
- recursive and multi-input batch flows stay on classic mode by default

### GUI URL Media Behavior

The GUI URL section now supports:

- no media preservation
- save audio copy
- save video copy
- custom save directory
- auto-bind saved media

If video preservation is requested but a usable local video copy is not
available, the service can fall back to saving audio instead and the GUI status
text should make that visible.

## Where To Start In A New Chat

If the next conversation is about current implementation work, open these first:

1. `docs/developer-handoff.md`
2. `docs/dev-state.md`
3. `docs/roadmap.md`
4. `docs/long-media-progressive-transcription-task-list.md`

If the next conversation is about packaging or release work, also open:

5. `docs/packaging.md`
6. `docs/release-automation.md`
7. `.github/workflows/release.yml`

If the next conversation is about GUI workflow work, also open:

8. `docs/gui.md`
9. `src/flowscribe/gui/qt_app.py`
10. `src/flowscribe/gui/state.py`

## High-Value Verification Commands

Use focused checks first unless the user explicitly asks for a full sweep.

Progressive and service work:

```powershell
python -m pytest tests\test_progressive_transcription.py tests\test_app_service.py tests\test_cli_main.py
python -m ruff check src\flowscribe\core src\flowscribe\app src\flowscribe\cli tests\test_progressive_transcription.py tests\test_app_service.py tests\test_cli_main.py
```

GUI and URL media work:

```powershell
python -m pytest tests\test_gui_state.py tests\test_gui_qt_app.py tests\test_url_input.py tests\test_app_service.py
python -m ruff check src\flowscribe\gui src\flowscribe\input\url_downloader.py src\flowscribe\app tests\test_gui_state.py tests\test_gui_qt_app.py tests\test_url_input.py tests\test_app_service.py
```

Packaging and release smoke checks:

```powershell
.\scripts\build_exe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
.\dist\FlowScribe\FlowScribe.exe doctor
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
.\dist\FlowScribeGUI\WasapiCaptureHelper.exe version
.\dist\FlowScribeGUI\WasapiCaptureHelper.exe probe
```

## Build And Release Commands

Build from source:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev,gui]
```

Build CLI package:

```powershell
.\scripts\build_exe.ps1
```

Build GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

Create and push a release tag:

```powershell
git add .
git commit -m "Prepare v0.x.y"
git push
git tag v0.x.y
git push origin v0.x.y
```

The GitHub release workflow is create-or-update and supports reruns with asset
overwrite. See `docs/release-automation.md`.

## Suggested Next-Step Areas

If work resumes on `v0.7`, these are the most natural continuation points:

- progressive long-media experience tuning with real long samples
- progressive ETA stability and worker policy tuning
- URL workflow ergonomics and media-preservation clarity
- batch workflow enhancements that build on progressive execution
- future provider work for Chinese accuracy once the current progressive path
  feels stable
