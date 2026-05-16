# Desktop GUI

FlowScribe's desktop GUI starts in Phase 3 as a PySide6 shell around the existing
application service layer. The goal is to make daily transcription usable without
memorizing CLI commands while keeping the UI replaceable later.

## Current Milestone

The GUI has now moved beyond the initial Phase 3 shell and supports a more
consolidated transcript workspace:

- Open a desktop window.
- Add local files and folders with explicit checkbox selection.
- Remember local source list and checked state across restarts.
- Paste a public URL.
- Choose an output directory.
- Optionally choose a custom output basename for generated transcript files.
- Set model, language, preset, output formats, network family, proxy, and cookies path.
- Collect and preview form state as a `TranscriptionJob`-compatible payload.
- Start a transcription job for checked local sources or a URL.
- Display progress messages, output file paths, and structured failures.
- Surface progressive long-run transcription updates while a job is still running.
- Open an existing transcript JSON file inside the GUI.
- Render segment text and timestamps in a transcript viewer.
- Search transcript keywords and jump to hits.
- Bind local media to a transcript and seek playback from segments or search hits.
- Edit transcript segments and save corrected JSON or copies.
- Re-export transcript artifacts from the current transcript workflow.
- Save and reapply export profiles.
- Review transcript artifacts inside `Views` without leaving transcript review.
- Reopen transcripts through a local transcript library.
- Filter and sort transcript library entries by source kind, missing state,
  opened state, and time-oriented sort modes.
- Review recent transcript work with labels that align more closely with the
  library.
- Persist non-sensitive view preferences such as visible base `Views` tabs and
  the active workspace tab.
- Cancel active jobs, open output directories, and keep lightweight recent-work
  shortcuts.
- Capture Windows system audio to WAV and route it back through the normal
  local-source transcription flow.

## Install GUI Dependencies

From a developer checkout:

```powershell
python -m pip install -e .[gui]
```

For development with tests and lint:

```powershell
python -m pip install -e .[dev,gui]
```

## Run The GUI

```powershell
flowscribe gui
```

or:

```powershell
flowscribe-gui
```

or:

```powershell
python -m flowscribe.gui
```

## Architecture Rule

The GUI must remain a thin frontend:

```text
GUI widgets
  -> GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

The Qt layer should not directly instantiate low-level media, URL, transcription,
or output classes. That keeps the project ready for a future frontend replacement
such as WebView, a web UI, or a more polished native interface.

## Current Boundary

The GUI is still a lightweight desktop shell. It now has a denser `Views`
workspace, but it still focuses on one active transcription/review workflow
rather than a full project database or batch queue.

The `Start Transcription` button runs the collected job in a background Qt
thread, so the GUI should remain responsive while transcription is running.

Media sync is intentionally transcript-bound. The GUI first tries to resolve the
original local media from the transcript metadata; if it cannot, the user binds
one local media file to that transcript explicitly.

The review surface is now more stateful and more consolidated:

- current playback position can advance transcript selection automatically
- search-hit jumps, segment clicks, and playback updates converge on the same
  segment-selection behavior
- the GUI shows whether media is unbound, auto-bound, or manually bound
- suspicious transcript/media mismatches are called out with a warning instead
  of staying silent
- transcript playback, segment review, editing, and artifact inspection now sit
  inside the same `Views` workspace
- transcript library reopening and cleanup can be done inside `Views` instead of
  a separate competing window

Preference persistence currently remains intentionally narrow:

- only non-sensitive values are saved
- cookie contents are not stored
- saved preferences are inspectable from the GUI
- custom output basenames can be saved and restored with the other non-sensitive
  GUI defaults

Task control also remains intentionally lightweight:

- one active GUI transcription job at a time
- cooperative cancellation rather than hard process termination
- no full multi-job queue yet

Progress feedback is now stronger for long runs:

- progressive transcription can report chunk-level completion instead of waiting
  for the whole media item to finish
- the GUI can show processed duration against total duration
- the GUI can show a rough speed multiplier and ETA during long runs
- transcript segments can appear in the workspace while transcription is still
  in progress

Recent-work support also remains intentionally lightweight:

- the GUI remembers a short recent list rather than building a project library
- recent jobs are for reopening context quickly, not for full queue management
- recent transcript/media bindings help restore review sessions without creating
  a persistent asset database
- recent transcript labels now reuse library metadata where possible so recent
  work and the library feel like related surfaces instead of separate systems

Transcript-library support is now stronger but still intentionally local:

- library entries can be filtered by source kind, missing state, and opened
  state
- library entries can be sorted by label, created time, updated time, or last
  opened time
- missing transcript cleanup is visible from both `Views` library actions and
  the `Recent Work` window
- media rebind and transcript reopen actions stay centered on the current
  workspace rather than opening a separate management flow

System-audio capture currently remains intentionally conservative:

- FlowScribe only enables capture when ffmpeg can see a loopback-like Windows
  input device such as `Stereo Mix`, `What U Hear`, `Wave Out`, or a virtual
  loopback device
- capture writes a normal WAV file and then reuses the existing local-source
  transcription path
- silent or empty recordings are treated as failures rather than successful
  captures
- machines that only expose microphone/headphone dshow endpoints are reported as
  unsupported instead of producing misleading blank audio

## Logging Modes

The GUI supports two runtime noise modes through `FLOWSCRIBE_GUI_LOG_MODE`:

- `dev`: keep development-oriented logging visible.
- `user`: quiet packaged mode for normal end users.

Source runs default to `dev`. Frozen packaged GUI builds default to `user`.
The packaged GUI also starts with a windowed entry point, so users do not see a
console window during normal launch.

## Build A GUI Executable

For a local smoke test of GUI packaging:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The output folder is:

```text
dist/FlowScribeGUI/
|-- FlowScribeGUI.exe
`-- _internal/
```

The packaged GUI build now defaults to quiet `user` logging by using a
PyInstaller runtime hook. This keeps routine `qt.multimedia` startup chatter out
of end-user sessions while still allowing source runs to use `dev` mode during
development.

For packaging smoke tests:

```powershell
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
```

Release automation can ship the GUI package alongside the CLI release package.
