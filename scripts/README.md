# Scripts

## GUI Packaging

Build the PySide6 GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The GUI build also builds and copies the WASAPI capture helper into
`dist\FlowScribeGUI` so packaged system-audio capture can find
`WasapiCaptureHelper.exe` next to `FlowScribeGUI.exe`.

The GUI package now always bundles the Paraformer runtime (`funasr`,
`modelscope`). Users only need to download Paraformer models from Model Center;
they should not need to install extra Python packages on the target machine.

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
