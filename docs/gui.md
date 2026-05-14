# Desktop GUI

FlowScribe's desktop GUI starts in Phase 3 as a PySide6 shell around the existing
application service layer. The goal is to make daily transcription usable without
memorizing CLI commands while keeping the UI replaceable later.

## Current Milestone

The current Phase 3 GUI build now covers the first interactive transcript
workflow end to end:

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
- Open an existing transcript JSON file inside the GUI.
- Render segment text and timestamps in a transcript viewer.
- Search transcript keywords and jump to hits.
- Bind local media to a transcript and seek playback from segments or search hits.

Phase 4 has now started with the first persistence-oriented desktop refinement:

- Persist non-sensitive GUI preferences such as output directory, model,
  language, preset, formats, timestamp flags, network family, and explicit
  proxy value.
- Keep local source list state compatible with older saved payloads.
- Provide `Save Settings` and `View Settings` actions so persistence is visible
  and user-controlled instead of hidden.
- Add direct desktop actions for canceling a running transcription and opening
  the output directory.
- Keep settings inspection separate from run details by showing preferences in a
  dedicated window.
- Let users override transcript artifact basenames from the GUI so output files
  can follow a task/session name instead of the source stem.
- Add a dedicated `Recent Work` window that can reopen recent transcript JSON
  files, recent output directories, recent lightweight jobs, and recent
  transcript/media bindings.
- Keep recent-work state across GUI restarts and remove missing entries
  gracefully when users try to reopen them.
- Strengthen transcript/media review so playback, transcript selection, and
  search-hit navigation stay more consistent during review.
- Show clearer transcript-media binding state and mismatch feedback inside the
  GUI.
- Add a Windows-focused system-audio capture MVP that records to WAV, returns
  the result as a normal local source, and can auto-delete temporary captures
  after transcription.

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

The GUI is still a lightweight desktop shell. It focuses on one active
transcription/review surface rather than a full project library or batch queue.

The `Start Transcription` button runs the collected job in a background Qt
thread, so the GUI should remain responsive while transcription is running.

Media sync is intentionally transcript-bound. The GUI first tries to resolve the
original local media from the transcript metadata; if it cannot, the user binds
one local media file to that transcript explicitly.

The review surface is now more stateful:

- current playback position can advance transcript selection automatically
- search-hit jumps, segment clicks, and playback updates converge on the same
  segment-selection behavior
- the GUI shows whether media is unbound, auto-bound, or manually bound
- suspicious transcript/media mismatches are called out with a warning instead
  of staying silent

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

Recent-work support also remains intentionally lightweight:

- the GUI remembers a short recent list rather than building a project library
- recent jobs are for reopening context quickly, not for full queue management
- recent transcript/media bindings help restore review sessions without creating
  a persistent asset database

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
