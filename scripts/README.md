# Scripts

## GUI Packaging

Build the PySide6 GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The GUI build also builds and copies the WASAPI capture helper into
`dist\FlowScribeGUI` so packaged system-audio capture can find
`WasapiCaptureHelper.exe` next to `FlowScribeGUI.exe`.

The GUI script now stages PyInstaller output under `build\pyinstaller-dist`
and syncs only the GUI application payload back into `dist\FlowScribeGUI`.
Stable sibling files such as `ffmpeg.exe`, `ffprobe.exe`,
`WasapiCaptureHelper.exe`, and `FlowScribeURL.exe` are reused when unchanged
instead of being deleted and recopied on every source edit.

When the selected Python build environment can fully import `funasr`,
`modelscope`, and `torch`, the GUI and CLI packaging scripts also bundle the
Paraformer runtime. If those optional runtime dependencies are incomplete, the
build now skips Paraformer bundling instead of failing the whole package build.

## URL Packaging

Build the standalone URL acquisition package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_url_exe.ps1 -Python python
```

The URL build outputs:

```text
dist\FlowScribeURL\
```

This package contains `FlowScribeURL.exe` plus bundled `ffmpeg.exe` and
`ffprobe.exe` for URL inspection and media download without starting the
transcription pipeline.

When the packaged CLI or GUI finds `FlowScribeURL.exe` in the same folder as
`FlowScribe.exe` or `FlowScribeGUI.exe`, URL inspection/download work is routed
through that sibling executable automatically.

## WASAPI Helper

Build only the Windows system-audio capture helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_wasapi_helper.ps1
```

The helper is published to:

```text
build\wasapi-helper\
```

## Local Docs Site

Build the local HTML help bundle used by the Windows installer and packaged help entry:

```powershell
python .\scripts\build_docs_site.py
```

The output is written to:

```text
build\docs-site\
```

## Windows Installers

Compile the Windows online and offline installers with Inno Setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_installers.ps1
```

This expects:

- `dist\FlowScribe\`
- `dist\FlowScribeGUI\`
- Inno Setup `iscc` on PATH
