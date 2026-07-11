# Packaging

This document explains how to build the current Windows portable release for FlowScribe.

## Packaging Strategy

FlowScribe now ships as one shared portable release root:

```text
dist\
`-- FlowScribePortable\
    |-- core\
    |   |-- gui-core.exe
    |   |-- cli-core.exe
    |   |-- FlowScribeURL.exe
    |   |-- python.exe / pythonw.exe
    |   |-- Lib\
    |   |-- DLLs\
    |   |-- site-packages\
    |   |-- ffmpeg.exe
    |   |-- ffprobe.exe
    |   |-- WasapiCaptureHelper.exe
    |   `-- other stable runtime files
    |-- code\
    |   |-- flowscribe\...*.pyc
    |   |-- flowscribe\gui\themes\*.qss
    |   |-- flowscribe\gui\assets\*.wav
    |   `-- icons\
    |-- docs\
    |-- run-gui.bat
    `-- run-cli.bat
```

The split is intentional:

- `core/` contains the runtime environment and third-party dependencies.
- `code/` contains only FlowScribe business code and self-owned resources.
- `docs/` stays at the portable app root.

This makes business-code updates incremental. If you only change FlowScribe source code or app-owned resources, you can rebuild and redistribute `code/` without rebuilding `core/`.

## What Goes Where

`core/` contains:

- thin PyInstaller launchers: `gui-core.exe`, `cli-core.exe`, `FlowScribeURL.exe`
- Python runtime, standard library, DLLs, and PyInstaller runtime
- third-party `site-packages`
- Qt / PySide6 runtime
- ffmpeg and ffprobe
- `WasapiCaptureHelper.exe` and its companion files
- other stable native runtime files

`code/` contains:

- compiled `src/flowscribe` package as `.pyc`
- FlowScribe-owned GUI themes and audio assets
- FlowScribe application icons

`code/` must not contain:

- third-party Python packages
- Python runtime files
- ffmpeg, ffprobe, Qt runtime, or helper executables

`core/` must not contain:

- the FlowScribe business package
- editable-install back references such as `__editable__*`
- project `.pth` files

## Prerequisites

Before building:

- Use Windows.
- Install Python 3.12 or newer.
- Ensure `ffmpeg.exe` and `ffprobe.exe` are available on `PATH`.
- Ensure `.NET SDK` is available if you want to rebuild the WASAPI helper.
- Clone the FlowScribe repository.

Verify:

```powershell
python --version
ffmpeg -version
ffprobe -version
dotnet --version
```

## Canonical Build Commands

From the repository root:

```powershell
cd E:\Draft\FlowScribe
```

Build or update only the shared runtime layer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_core_package.ps1 -Python python
```

Build or update only the FlowScribe business-code layer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_code_package.ps1 -Python python
```

Compatibility entrypoints still exist and now call the shared builders:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -Python python
```

All of the commands above now target:

```text
dist\FlowScribePortable\
```

## When To Rebuild `core`

Rebuild `core/` when you change:

- packaging launchers or packaging scripts
- Python runtime assumptions
- third-party dependencies
- PyInstaller behavior
- Qt / PySide6 runtime needs
- ffmpeg / ffprobe delivery
- WASAPI helper delivery
- URL helper delivery

Typical command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_core_package.ps1 -Python python
```

If business code also changed, rebuild `code/` afterwards.

## When To Rebuild `code`

Rebuild `code/` when you change:

- `src\flowscribe\...` business logic
- CLI or GUI application code
- FlowScribe-owned themes, icons, or bundled audio assets
- docs site content that should ship in `dist\FlowScribePortable\docs`

Typical command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_code_package.ps1 -Python python
```

This rebuilds:

- `dist\FlowScribePortable\code`
- `dist\FlowScribePortable\docs`

It does not need to rebuild `core/`.

## Incremental Update Workflow

For the common business-code-only case:

1. Edit FlowScribe code under `src\flowscribe`.
2. Run `build_code_package.ps1`.
3. Replace `code\` in an existing portable deployment.
4. Replace `docs\` too if help content changed.

For dependency or runtime changes:

1. Run `build_core_package.ps1`.
2. Run `build_code_package.ps1` if business code also changed.
3. Replace `core\` in the target deployment.

## Build Output And Launch

The portable application is the whole folder:

```text
dist\FlowScribePortable\
```

Do not distribute only the EXEs. The relative layout between `core/`, `code/`, and the root launch scripts is required.

Start the packaged application with:

```powershell
.\dist\FlowScribePortable\run-cli.bat --help
.\dist\FlowScribePortable\run-gui.bat
```

The root launch scripts are the canonical entrypoints. They should stay next to `core/` and `code/`.

## Validation Checklist

### Core Validation

After `build_core_package.ps1`, verify:

- `core\gui-core.exe` exists
- `core\cli-core.exe` exists
- `core\FlowScribeURL.exe` exists
- `core\site-packages` contains third-party runtime packages
- `core\site-packages` does not contain `flowscribe*`
- `core\site-packages` does not contain `__editable__*`
- `core\site-packages` does not contain project `.pth` files

### Code Validation

After `build_code_package.ps1`, verify:

- `code\flowscribe\` contains `.pyc` files
- `code\flowscribe\gui\themes\` contains `.qss` files
- `code\flowscribe\gui\assets\` contains required `.wav` files
- `code\icons\` contains FlowScribe icons
- no third-party package directories appear under `code\`

### Smoke Tests

CLI help:

```powershell
.\dist\FlowScribePortable\run-cli.bat --help
```

CLI doctor without network dependency:

```powershell
.\dist\FlowScribePortable\run-cli.bat doctor --skip-model-access
```

GUI self-test:

```powershell
cmd /c "set FLOWSCRIBE_GUI_AUTOCLOSE_MS=500&& .\dist\FlowScribePortable\run-gui.bat --self-test"
```

### Incremental Verification

To confirm that a business-only update does not rebuild `core/`:

1. Record timestamps of `core\gui-core.exe`, `core\cli-core.exe`, and `core\FlowScribeURL.exe`.
2. Change a FlowScribe business module.
3. Run `build_code_package.ps1`.
4. Confirm the `core\*.exe` timestamps are unchanged.
5. Re-run the CLI and GUI smoke tests.

## Optional Parameters

Examples:

```powershell
.\scripts\build_core_package.ps1 -Python python -SkipClean
.\scripts\build_core_package.ps1 -Python python -SkipHelperBuild
.\scripts\build_code_package.ps1 -Python python
.\scripts\build_code_package.ps1 -Python python -IncludeBundledModels
```

Notes:

- `-SkipClean` keeps the PyInstaller launcher work area for faster rebuilds.
- `-SkipHelperBuild` reuses an existing `build\wasapi-helper\` output.
- `-IncludeBundledModels` copies the local `models\` directory into the portable root.

## Paraformer Packaging

Paraformer packaging support remains best-effort:

- if the build environment can package the Paraformer runtime, it is included in `core/`
- if optional Paraformer packaging dependencies are incomplete, the build continues without blocking the release

This keeps packaging resilient while preserving optional Chinese-first runtime support when available.

## Release Distribution

For a release ZIP, package the entire folder:

```text
FlowScribePortable-vX.Y.Z-windows-x64.zip
```

Include the whole `dist\FlowScribePortable\` tree. Do not split `core/` from `code/` unless you are intentionally shipping an incremental business-code update to an existing compatible portable base.
