# Desktop GUI

FlowScribe's desktop GUI starts in Phase 3 as a PySide6 shell around the existing
application service layer. The goal is to make daily transcription usable without
memorizing CLI commands while keeping the UI replaceable later.

## Current Milestone

Milestone 3.2 connects the GUI skeleton to local-file transcription:

- Open a desktop window.
- Choose local media files.
- Drag local media files into the window.
- Paste a URL.
- Choose an output directory.
- Set model, language, preset, output formats, network family, proxy, and cookies path.
- Collect and preview form state as a `TranscriptionJob`-compatible payload.
- Start a transcription job for local files.
- Display progress messages.
- Display output file paths.
- Display structured failure messages.

URL fields are already present in the form, but Phase 3.2's acceptance focus is
local-file transcription from the GUI.

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

The `Start Transcription` button now runs the collected job in a background Qt
thread, so the GUI should remain responsive while local transcription is running.

Milestone 3.3 will polish URL transcription from the GUI and add stronger
job-level controls.

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

This package currently validates that the GUI shell can be built. It does not
replace the CLI release package yet.
