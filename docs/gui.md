# Desktop GUI

FlowScribe's desktop GUI starts in Phase 3 as a PySide6 shell around the existing
application service layer. The goal is to make daily transcription usable without
memorizing CLI commands while keeping the UI replaceable later.

## Current Milestone

Milestone 3.1 implements the GUI skeleton:

- Open a desktop window.
- Choose local media files.
- Paste a URL.
- Choose an output directory.
- Set model, language, preset, output formats, network family, proxy, and cookies path.
- Collect and preview form state as a `TranscriptionJob`-compatible payload.

It intentionally does not start transcription yet. Execution will be connected in
Milestone 3.2.

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

The `Start Transcription` button is disabled in Milestone 3.1. The working button
is `Collect State`, which validates the form and shows the collected job preview.

Milestone 3.2 will connect the GUI to background transcription execution and
progress events.

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
