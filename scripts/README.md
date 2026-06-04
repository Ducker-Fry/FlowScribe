# Scripts

## GUI Packaging

Build the PySide6 GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The GUI build also builds and copies the WASAPI capture helper into
`dist\FlowScribeGUI` so packaged system-audio capture can find
`WasapiCaptureHelper.exe` next to `FlowScribeGUI.exe`.

If optional Paraformer dependencies (`funasr`, `modelscope`) are importable,
the GUI package also bundles FunASR support. If they are missing, the GUI build
still succeeds and packages the rest of the desktop app.

## WASAPI Helper

Build only the Windows system-audio capture helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_wasapi_helper.ps1
```

The helper is published to:

```text
build\wasapi-helper\
```
