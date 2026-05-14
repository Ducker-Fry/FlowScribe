# Phase 3 Summary And Phase 4 Plan

Phase 3 name: **Desktop GUI And Interactive Transcript Workflow**

Phase 3 wrap-up release: **v0.2.3**

Completion date: **2026-05-14**

## Phase 3 Goal

Phase 2 proved that FlowScribe could handle local files, public URLs, structured
transcript JSON, search, and Windows release automation through a CLI-first
workflow.

Phase 3 moved the project much closer to daily desktop use. The main goal was:

```text
CLI transcription engine
  -> desktop GUI
  -> interactive transcript reading
  -> keyword navigation
  -> local media sync
  -> GUI release packaging
```

The practical success condition was simple: a non-technical user should be able
to start the application, choose a source, run a transcription, open transcript
JSON, search it, and jump through local media without using terminal commands.

## Completed Work

### Desktop GUI Foundation

FlowScribe now ships with a PySide6 desktop GUI layered on top of the existing
application service path:

```text
GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

This kept the GUI thin while reusing the same core execution model as the CLI.
The result is a frontend that can evolve without forking business logic.

Implemented GUI foundations:

- Local file and folder selection.
- Drag-and-drop local source support.
- URL input field.
- Output directory selection.
- Model, language, preset, format, proxy, cookies, and network-family controls.
- `Collect State` preview.
- Background transcription worker thread.
- In-window progress and failure reporting.

### URL Workflow In The GUI

Phase 3 connected the GUI URL path to the same safety model already used by the
CLI:

- Public `http/https` validation.
- Shared URL safety checks.
- Explicit `proxy`, `cookies`, and `network-family` passthrough.
- Clear GUI-side validation errors before a job starts.

This matters because it avoids the common GUI failure mode where the desktop
form and CLI drift into inconsistent behavior.

### Transcript Viewer

The GUI can now open and render existing transcript JSON files directly:

- Load transcript JSON from disk.
- Auto-load generated JSON output after a successful transcription.
- Render segment text.
- Render timestamps.
- Show transcript summaries inside the GUI.

This turns FlowScribe from a pure conversion tool into a usable transcript
reading surface.

### Search UI

Transcript search is now available inside the GUI:

- Enter a keyword.
- Show all hits as a list.
- Display match context.
- Jump from a hit to the matching transcript segment.

This brought a Phase 2 CLI capability into the desktop workflow and made
transcript navigation practical for real use.

### Local Media Sync MVP

Phase 3 added the first transcript-to-media synchronization loop:

- Load local media for playback.
- Jump playback from transcript segments.
- Jump playback from search hits.
- Bind one local media file to one transcript when auto-resolution is not
  possible.

This is intentionally transcript-bound rather than "open any media and hope for
the best." The GUI first tries to resolve the original media path from
transcript metadata, and if it cannot, it asks the user to bind one local file
explicitly.

### Source Selection Refinement

The local source list evolved from an implicit batch queue into an explicit
selection model:

- Local files and folders remain in a visible source list.
- Participation is controlled by checkboxes instead of list highlight state.
- `Select All` is available.
- Checked state is remembered across restarts.

This was an important usability fix. It made the desktop UI behave more like a
real work surface and less like a hidden batch collector.

### GUI Packaging And Runtime Hardening

Phase 3 also completed the first serious GUI packaging path:

- `scripts/build_gui_exe.ps1` builds a GUI one-folder package.
- The GUI release launches with PyInstaller `--windowed`.
- Packaged GUI runs default to `FLOWSCRIBE_GUI_LOG_MODE=user`.
- A `--self-test` entry point was added for packaged smoke checks.
- GitHub Release automation now publishes both:
  - `FlowScribe-v0.2.3-windows-x64.zip`
  - `FlowScribeGUI-v0.2.3-windows-x64.zip`

The release hardening work exposed two real CI issues:

- the GUI release runner was missing `PyInstaller`
- GUI self-test verification could not rely on `$LASTEXITCODE` for a windowed
  executable

Both issues were fixed, and the final `v0.2.3` release now completes
successfully in GitHub Actions.

## Engineering Outcomes

Phase 3 materially improved FlowScribe in several ways.

### Usability

FlowScribe is no longer limited to command-line users. The project now supports
desktop transcription, transcript reading, search, and local media navigation
inside one GUI surface.

### Consistency

The GUI reuses the same validation and service-layer execution path as the CLI.
This reduced duplication and kept URL handling, source handling, and output
behavior aligned across interfaces.

### Product Shape

Transcript JSON is now demonstrably useful as an interaction format, not only a
machine-readable export. That validates the earlier architectural decision to
make JSON a first-class intermediate artifact.

### Release Quality

Phase 3 improved the project's release discipline:

- CLI and GUI are both packaged for Windows.
- GUI builds have a quiet end-user startup mode.
- Release automation verifies both packaged entry points.

### Portfolio Value

By the end of Phase 3, FlowScribe demonstrates:

- CLI design
- desktop GUI design
- media processing
- transcript data modeling
- search and navigation UX
- packaging and release automation
- test coverage across service, GUI, and release behaviors

## Remaining Gaps After Phase 3

Phase 3 delivered the first usable desktop workflow, but some important product
gaps remain:

- no system audio capture yet
- no GUI cancel-job workflow yet
- no GUI job history or transcript library
- no persistent non-sensitive settings beyond local source state
- no automatic active-segment follow during playback
- no output-directory shortcuts or post-run file management tools
- no provider abstraction beyond the current local pipeline

These gaps point naturally to the next phase.

## Phase 4 Name

**Phase 4: Capture, Workflow Persistence, And Desktop Productization**

## Phase 4 Goal

Phase 4 should turn the current GUI from a strong MVP into a steadier desktop
application for repeated use.

The product direction:

```text
desktop transcription MVP
  -> system/browser audio capture
  -> persistent desktop workflow
  -> better job control
  -> better result management
  -> stronger media/transcript review loop
```

Phase 4 is less about proving a new surface exists and more about making that
surface dependable for real repeated workflows.

## Phase 4 Core Features

### 1. System Audio Capture

Add a user-controlled capture path for audio that is being played locally:

- capture browser or application audio to a local file
- save the captured file as a normal FlowScribe input artifact
- run the captured result through the existing transcription pipeline

This expands FlowScribe beyond static files and public URLs while staying within
the same local-first architecture.

### 2. Persistent Desktop Workflow

Add non-sensitive GUI preference persistence:

- default output directory
- default model
- default language or preset
- default output formats
- default network family
- default proxy path or value when explicitly desired

This should remain transparent and editable. Cookies contents should not be
stored.

### 3. Job Control And Result Management

Improve the desktop task loop:

- cancel current transcription job
- open output directory from the GUI
- show clearer per-run status
- keep a lightweight recent-job or recent-transcript history

This is the smallest step that makes the application feel persistent without
jumping all the way to a database-backed library.

### 4. Better Transcript-Media Review

Strengthen the media sync experience:

- follow the active segment during playback
- highlight the current segment more clearly
- improve mismatch handling when transcript and chosen media look inconsistent
- keep search, segment focus, and playback state more tightly aligned

This will turn the current sync MVP into a more trustworthy review workflow.

### 5. Release And Verification Hardening

Continue improving release quality:

- keep CLI and GUI packaging healthy in CI
- retain smoke verification for both packaged artifacts
- add targeted tests for new desktop persistence and capture logic
- document GUI-first release usage more clearly

## Phase 4 Technical Tasks

Recommended implementation order:

1. Add GUI settings persistence for non-sensitive defaults.
2. Add open-output-directory and cancel-job support.
3. Add recent-transcript or recent-job state.
4. Build a system audio capture prototype as a saved local artifact.
5. Route capture output through existing transcription jobs.
6. Improve transcript/media synchronization states and highlighting.
7. Extend packaging and release verification as needed for new capture/runtime
   dependencies.

## Phase 4 Non-Goals

Avoid over-expanding Phase 4:

- do not add multi-user accounts
- do not add cloud sync
- do not add DRM bypass or protected-media circumvention
- do not jump straight to a large database-backed media library
- do not add broad AI summarization or chat features inside FlowScribe yet

The focus should remain:

```text
make the desktop workflow repeatable, controllable, and capture-capable
```

## Phase 4 Success Criteria

Phase 4 can be considered complete when:

- a user can capture local/system audio into a normal FlowScribe input artifact
- the GUI remembers practical non-sensitive defaults
- a user can cancel a running GUI job
- a user can reopen recent work without manually rediscovering files
- transcript/media review feels steadier during playback
- CLI and GUI release packaging remain reliable

## Recommended Version Target

Phase 4 should target:

```text
v0.4.0
```

Reason: system audio capture and persistent desktop workflow features are
user-facing additions that extend FlowScribe beyond the first GUI MVP.
