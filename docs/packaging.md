# Packaging

This document explains how to build Windows portable releases for FlowScribe.

## Packaging Strategy

FlowScribe is packaged as PyInstaller one-folder applications:

```text
dist/
|-- FlowScribe/
|   |-- FlowScribe.exe
|   |-- ffmpeg.exe
|   |-- ffprobe.exe
|   |-- README-USER.txt
|   `-- supporting runtime files
`-- FlowScribeGUI/
    |-- FlowScribeGUI.exe
    |-- WasapiCaptureHelper.exe
    |-- NAudio*.dll
    `-- supporting runtime files
```

One-folder is preferred before one-file because it is easier to debug, starts faster, and is more predictable for heavy dependencies such as `faster-whisper`, `ctranslate2`, `onnxruntime`, `tokenizers`, and `av`.

Whisper models are not bundled in the executable. The first run with a selected model may download model files to the user's Hugging Face cache. This keeps the release package smaller and lets users choose `tiny`, `small`, `medium`, or a local model path.

## Prerequisites

Before building:

- Use Windows.
- Install Python 3.10 or newer.
- Ensure `ffmpeg.exe` and `ffprobe.exe` are available on `PATH`.
- Clone the FlowScribe repository.

Verify:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

## Build Commands

From the repository root:

```powershell
cd E:\Draft\FlowScribe
.\scripts\build_exe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The CLI script will:

1. Create or reuse `.venv-build`.
2. Install FlowScribe dependencies.
3. Install PyInstaller.
4. Clean previous `dist/` and `build/` folders unless `-SkipClean` is used.
5. Build a one-folder executable.
6. Copy `ffmpeg.exe` and `ffprobe.exe` into the release folder.
7. Generate `README-USER.txt` for end users.

The GUI script will:

1. Reuse the active Python environment.
2. Build or verify the WASAPI capture helper staging output.
3. Clean previous GUI build artifacts unless `-SkipClean` is used.
4. Build a one-folder GUI executable with PyInstaller.
5. Copy `WasapiCaptureHelper.exe` and NAudio dependency files into the GUI release folder.
6. Smoke-test the packaged helper with `WasapiCaptureHelper.exe version`.
7. Apply a runtime hook that defaults packaged GUI builds to `FLOWSCRIBE_GUI_LOG_MODE=user`.
8. Launch the GUI with `--windowed`, so end-user runs do not open a console window.

Optional parameters:

```powershell
.\scripts\build_exe.ps1 -VenvPath ".venv-build"
.\scripts\build_exe.ps1 -SkipClean
```

## Build Output

The CLI artifact is:

```text
dist/FlowScribe/FlowScribe.exe
```

The whole `dist/FlowScribe/` folder is the portable application. Do not distribute only the `.exe`; the surrounding runtime files are required.

The GUI artifact is:

```text
dist/FlowScribeGUI/FlowScribeGUI.exe
```

The whole `dist/FlowScribeGUI/` folder is required for GUI distribution.

## Testing the EXEs

Run environment diagnostics:

```powershell
.\dist\FlowScribe\FlowScribe.exe doctor
```

Test with a small local audio or video file:

```powershell
.\dist\FlowScribe\FlowScribe.exe "D:\media\sample.mp4" -o outputs --model tiny --overwrite
```

Test Chinese-oriented transcription:

```powershell
.\dist\FlowScribe\FlowScribe.exe "D:\media\lecture.mp4" -o outputs --model small --preset zh --overwrite
```

Expected output:

```text
outputs/
|-- sample.txt
`-- sample.md
```

Test the GUI package entry point:

```powershell
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
```

For a visual smoke test, start the GUI normally:

```powershell
.\dist\FlowScribeGUI\FlowScribeGUI.exe
```

## GitHub Release Contents

For a GitHub Release, upload:

```text
FlowScribe-v0.2.4-windows-x64.zip
FlowScribeGUI-v0.2.4-windows-x64.zip
```

The CLI ZIP should contain the entire `dist/FlowScribe/` folder, including:

- `FlowScribe.exe`
- `ffmpeg.exe`
- `ffprobe.exe`
- `README-USER.txt`
- all PyInstaller runtime files

The GUI ZIP should contain the entire `dist/FlowScribeGUI/` folder, including:

- `FlowScribeGUI.exe`
- `WasapiCaptureHelper.exe`
- NAudio dependency DLLs
- all PyInstaller runtime files

Release notes should include:

- Supported platform: Windows x64.
- First run may download Whisper model files.
- Models are not bundled.
- The GUI package launches without a console window and defaults to quiet `user` logging mode.
- The GUI package includes `WasapiCaptureHelper.exe` for Windows system-playback capture.
- Recommended model: `small`.
- Quick test command: `FlowScribe.exe doctor`.
- GUI smoke test command: `FlowScribeGUI.exe --self-test`.
- Legal and ethical use boundary.

## Why Not One-File Yet?

PyInstaller one-file packages extract themselves to a temporary folder on each run. For large AI/audio dependencies this can make startup slower and harder to debug. One-file also tends to trigger more antivirus suspicion for unsigned open-source tools.

One-file packaging can be explored later after the one-folder release is stable.
