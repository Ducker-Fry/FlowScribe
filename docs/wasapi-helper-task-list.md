# WASAPI Helper Task List

This document turns the high-level WASAPI helper design into a concrete
implementation checklist for FlowScribe.

It is intentionally optimized for direct execution:

- where to create files
- what the first helper CLI should look like
- which Python classes to add first
- which build and release scripts must change

## Target Outcome

Deliver a formal Windows system-audio capture path based on a dedicated helper:

```text
FlowScribe GUI
  -> WasapiCaptureHelper.exe
  -> WAV file
  -> existing local transcription path
```

The existing `dshow` capture path should remain available temporarily as a
compatibility fallback while the helper path is integrated and stabilized.

## Delivery Phases

Recommended implementation sequence:

1. create the helper project scaffold - complete
2. implement the first helper CLI contract - complete
3. add Python-side helper process integration - complete
4. connect GUI capture flow to the helper - complete
5. package the helper into the GUI release - complete
6. release workflow integration - complete
7. move `dshow` capture behind a compatibility boundary - complete

---

## Phase 1: Create The Helper Project

### Goal

Create a dedicated Windows helper project that can be built independently from
the Python application.

### Directory Layout

Create this new project subtree:

```text
tools/wasapi-capture-helper/
  WasapiCaptureHelper.sln
  src/
    WasapiCaptureHelper/
      WasapiCaptureHelper.csproj
      Program.cs
      Commands/
        ProbeCommand.cs
        ListDevicesCommand.cs
        CaptureCommand.cs
        VersionCommand.cs
      Models/
        ProbeResult.cs
        DeviceInfo.cs
        CaptureStartEvent.cs
        CaptureCompleteEvent.cs
        ErrorEvent.cs
      Audio/
        WasapiLoopbackCaptureService.cs
        DeviceEnumerationService.cs
        WavCaptureWriter.cs
      Serialization/
        JsonConsole.cs
  README.md
  LICENSE-THIRD-PARTY.md
```

### Required Initial Files

#### `tools/wasapi-capture-helper/src/WasapiCaptureHelper/WasapiCaptureHelper.csproj`

Initial requirements:

- target Windows only
- use .NET SDK-style project
- pin package versions
- add the audio library dependency explicitly

Recommended first pass:

- `TargetFramework`: `net8.0-windows`
- `RuntimeIdentifier`: `win-x64`
- `PublishSingleFile`: `true` later if desired
- pin `NAudio` version explicitly

#### `tools/wasapi-capture-helper/README.md`

Document:

- project purpose
- how to build locally
- how FlowScribe calls it
- expected stdout JSON behavior

#### `tools/wasapi-capture-helper/LICENSE-THIRD-PARTY.md`

Track:

- helper dependency licenses
- `NAudio` version and license
- any publishing/runtime notes

### Acceptance Criteria

- Complete: helper project builds locally on Windows.
- Complete: repo now has a dedicated helper subtree.
- Complete: helper dependencies are version-pinned, not floating.

### Implementation Status

Completed in the current working flow:

- Added `tools/wasapi-capture-helper/WasapiCaptureHelper.sln`.
- Added SDK-style helper project targeting `net8.0-windows` and `win-x64`.
- Pinned `NAudio` to version `2.2.1`.
- Added the planned command, model, audio, and serialization source layout.
- Added helper README and third-party license notes.

---

## Phase 2: Define And Implement The First Helper CLI Contract

### Goal

Make the helper usable as a stable subprocess dependency before connecting it to
the GUI.

## Command Contract

The helper should support exactly these first commands:

### 1. `version`

Purpose:

- confirm the binary exists and runs
- support smoke validation

Example:

```powershell
WasapiCaptureHelper.exe version
```

Expected stdout JSON:

```json
{
  "command": "version",
  "name": "WasapiCaptureHelper",
  "version": "0.1.0",
  "runtime": ".NET 8",
  "platform": "win-x64"
}
```

### 2. `probe`

Purpose:

- check whether loopback capture is supported
- expose the current default render device

Example:

```powershell
WasapiCaptureHelper.exe probe
```

Expected stdout JSON:

```json
{
  "command": "probe",
  "supported": true,
  "default_output_device": {
    "id": "default-device-id",
    "name": "Speakers (Realtek Audio)",
    "is_default": true
  }
}
```

Unsupported example:

```json
{
  "command": "probe",
  "supported": false,
  "reason": "No active output device available for loopback capture."
}
```

### 3. `list-devices`

Purpose:

- enumerate output render devices
- prepare for future manual device selection

Example:

```powershell
WasapiCaptureHelper.exe list-devices
```

Expected stdout JSON:

```json
{
  "command": "list-devices",
  "default_output_id": "default-device-id",
  "devices": [
    {
      "id": "default-device-id",
      "name": "Speakers (Realtek Audio)",
      "is_default": true
    },
    {
      "id": "other-device-id",
      "name": "Headphones (Bluetooth Headset)",
      "is_default": false
    }
  ]
}
```

### 4. `capture`

Purpose:

- start WASAPI loopback capture
- write a WAV file
- keep running until told to stop

Example:

```powershell
WasapiCaptureHelper.exe capture --output E:\temp\capture.wav --device default
```

Initial arguments:

- `--output <absolute-path>`
- `--device default|<device-id>`
- optional `--sample-rate 16000`
- optional `--channels 1`

### Capture Runtime Event Contract

The helper should emit JSON lines on stdout.

Required events:

#### started

```json
{
  "event": "started",
  "device_id": "default-device-id",
  "device_name": "Speakers (Realtek Audio)",
  "output": "E:\\temp\\capture.wav"
}
```

#### stopping

```json
{
  "event": "stopping"
}
```

#### completed

```json
{
  "event": "completed",
  "output": "E:\\temp\\capture.wav",
  "duration_seconds": 8.2
}
```

#### error

```json
{
  "event": "error",
  "message": "No active output device available for loopback capture."
}
```

### Stop Mechanism

First implementation:

- helper listens on `stdin`
- GUI/Python writes:

  ```text
  stop
  ```

- helper finalizes WAV and exits `0`

### Exit Code Rules

- `0`: command succeeded
- `2`: unsupported environment or invalid device
- `3`: capture failed after startup
- `4`: invalid arguments

### Acceptance Criteria

- Complete: all four commands exist.
- Complete: output is machine-readable JSON.
- Complete: `capture` can start and stop through stdin.
- Complete: helper does not require the GUI to parse human-only stderr.

### Implementation Status

Completed in the current working flow:

- `version` emits helper name, helper version, runtime, and platform JSON.
- `probe` reports support status and default active render device details.
- `list-devices` emits active render devices plus the default output id.
- `capture` accepts `--output`, `--device`, `--sample-rate`, and `--channels`.
- `capture` emits `started`, `stopping`, `completed`, and `error` JSON events.
- `capture` finalizes WAV output after receiving `stop` on stdin.
- Exit code behavior follows the first contract:
  - `0`: success
  - `2`: unsupported environment or invalid device
  - `3`: capture failed after startup
  - `4`: invalid arguments

---

## Phase 3: Add Python-Side Helper Integration

### Goal

Create a clean Python boundary between the GUI and the native helper.

## New Python Files

Create:

```text
src/flowscribe/media/system_audio_capture_helper.py
src/flowscribe/media/system_audio_capture_models.py
```

Optional if you want stricter separation:

```text
src/flowscribe/media/system_audio_capture_legacy.py
```

for the current `dshow` MVP path.

## New Python Models

Suggested file:

`src/flowscribe/media/system_audio_capture_models.py`

Add:

- `CaptureSupportStatus`
- `CaptureDevice`
- `CaptureStartResult`
- `CaptureEvent`
- `CaptureCompletedResult`

Suggested shapes:

```python
@dataclass(frozen=True)
class CaptureDevice:
    id: str
    name: str
    is_default: bool


@dataclass(frozen=True)
class CaptureSupportStatus:
    supported: bool
    reason: str | None = None
    default_device: CaptureDevice | None = None


@dataclass(frozen=True)
class CaptureCompletedResult:
    output_path: Path
    duration_seconds: float | None = None
```

## New Python Helper Integration Class

Suggested file:

`src/flowscribe/media/system_audio_capture_helper.py`

Add:

### `WasapiHelperCaptureRecorder`

Responsibilities:

- locate `WasapiCaptureHelper.exe`
- run `version`
- run `probe`
- run `list-devices`
- start capture subprocess
- stream stdout JSON events
- send `stop\n` to stdin
- return final WAV path

Suggested methods:

- `helper_path() -> Path`
- `version() -> dict`
- `probe() -> CaptureSupportStatus`
- `list_devices() -> tuple[CaptureDevice, ...]`
- `start(output_path: Path, device: str = "default") -> CaptureStartResult`
- `stop() -> CaptureCompletedResult`
- `abort() -> None`

### `CaptureController`

Suggested role:

- facade used by the GUI
- prefer helper-based recorder first
- optionally keep legacy `dshow` recorder available for compatibility mode

Suggested methods:

- `support_status() -> CaptureSupportStatus`
- `is_recording() -> bool`
- `start_capture(output_path: Path) -> CaptureStartResult`
- `stop_capture() -> CaptureCompletedResult`
- `abort_capture() -> None`

### Acceptance Criteria

- Complete: Python can run `probe` against the helper.
- Complete: Python can start/stop the helper and get a WAV path back.
- Complete: helper path resolution is stable for both source runs and packaged
  runs.

### Implementation Status

Completed in the current working flow:

- Added `src/flowscribe/media/system_audio_capture_models.py`.
- Added `src/flowscribe/media/system_audio_capture_helper.py`.
- Added `CaptureDevice`, `CaptureSupportStatus`, `CaptureEvent`,
  `CaptureStartResult`, and `CaptureCompletedResult`.
- Added `WasapiHelperCaptureRecorder` for helper discovery, one-shot helper
  commands, capture process ownership, stdout JSON event handling, stdin stop,
  and abort cleanup.
- Added `CaptureController` as the GUI-facing facade for Phase 4.
- Added focused tests in `tests/test_system_audio_capture_helper.py`.

---

## Phase 4: Connect The GUI

### Goal

Replace the current direct `dshow`-style capture logic in the GUI with the
helper-based controller.

## Files To Modify

### `src/flowscribe/gui/qt_app.py`

Primary changes:

1. replace direct recorder ownership with `CaptureController`
2. call `probe()` during startup
3. enable/disable `Start Capture` based on helper support
4. start capture through the helper
5. stop capture through the helper
6. keep existing behavior of:
   - adding captured WAV to local sources
   - optional auto-delete after the current transcription run
   - status messages in the GUI

### Suggested GUI State Changes

Add fields like:

- `_capture_controller`
- `_capture_supported`
- `_capture_default_device_name`
- `_active_capture_path`
- `_temporary_capture_paths`

### Suggested GUI Behavior

#### On startup

- call `probe()`
- if supported:
  - enable `Start Capture`
  - show `Ready to capture system playback.`
- if unsupported:
  - disable `Start Capture`
  - show clear explanation

#### On start

- create output path under capture temp directory
- start helper with `device=default`
- update buttons and status text

#### On stop

- send `stop`
- wait for completion
- validate WAV
- add WAV to local source list
- mark temporary if `Keep capture file` is unchecked

### Compatibility Plan

Do not immediately delete the current `dshow` MVP code.

Instead:

- move it behind a compatibility boundary
- keep helper path as the primary route
- optionally keep legacy fallback disabled by default

### Acceptance Criteria

- Complete: GUI startup reflects helper support status.
- Complete: capture button only enables when helper says the environment is
  supported.
- Complete: capture result still reuses the existing local transcription
  workflow.

### Implementation Status

Completed in the current working flow:

- `src/flowscribe/gui/qt_app.py` now imports and owns `CaptureController`.
- GUI support refresh now calls helper-backed `support_status()`.
- `Start Capture` is enabled only when the helper reports support and no
  transcription job is running.
- Capture start uses `start_capture()` and displays the selected/default output
  device name.
- Capture stop uses `stop_capture()` and adds the finalized WAV back into the
  local source list.
- Existing keep/delete captured-file behavior is preserved.
- Window close aborts the active helper-backed capture process if needed.

---

## Phase 5: Build And Packaging Integration

### Goal

Treat `WasapiCaptureHelper.exe` as a controlled runtime dependency in packaged
GUI builds.

## New Or Updated Build Assets

### New helper build script

Create:

```text
scripts/build_wasapi_helper.ps1
```

Responsibilities:

- restore helper project dependencies
- build or publish helper
- place output in a predictable staging directory

Suggested output location:

```text
build/wasapi-helper/
  WasapiCaptureHelper.exe
```

### Update `scripts/build_gui_exe.ps1`

Add steps:

1. verify helper exists or build it first
2. copy `WasapiCaptureHelper.exe` into:

```text
dist/FlowScribeGUI/
```

3. fail fast if helper is missing

### Optional update `scripts/build_exe.ps1`

Decide whether CLI package should include the helper:

- if GUI-only for now, leave CLI package unchanged
- if future CLI capture is planned, copy helper into CLI bundle too

### Acceptance Criteria

- Complete: local GUI packaging includes the helper.
- Complete: packaged GUI can find the helper without depending on PATH.

### Implementation Status

Completed in the current working flow:

- Added `scripts/build_wasapi_helper.ps1`.
- Helper publishing stages framework-dependent output in `build/wasapi-helper/`.
- Helper staging is smoke-tested with `WasapiCaptureHelper.exe version`.
- Updated `scripts/build_gui_exe.ps1` to build or verify helper staging before
  packaging.
- Updated GUI packaging to copy `WasapiCaptureHelper.exe`,
  `WasapiCaptureHelper.*`, and NAudio dependency DLLs into
  `dist/FlowScribeGUI/`.
- Packaged helper presence and `version` compatibility are verified during GUI
  packaging.
- CLI packaging remains unchanged because capture is GUI-only in this phase.

---

## Phase 6: Release Workflow Integration

### Goal

Make helper packaging part of normal Windows release generation.

## Files To Modify

### `.github/workflows/release.yml`

Add or update steps:

1. build the helper
2. build the GUI package
3. verify helper exists inside `dist/FlowScribeGUI`
4. run helper smoke checks:
   - `WasapiCaptureHelper.exe version`
   - `WasapiCaptureHelper.exe probe`

If the GitHub runner cannot perform real loopback capture, it should still
verify:

- the helper runs
- the helper emits valid JSON
- the helper is bundled into the final archive

### Optional `.github/workflows/ci.yml`

Add lighter validation for:

- Python-side helper protocol parsing
- packaging assumptions that do not require real audio capture

### Acceptance Criteria

- Complete: release workflow builds helper + GUI package together.
- Complete: release artifact contains `WasapiCaptureHelper.exe`.
- Complete: helper smoke checks pass in release automation.

### Implementation Status

Completed in the current working flow:

- `.github/workflows/release.yml` now sets up .NET 8 for helper publishing.
- The release GUI build uses `scripts/build_gui_exe.ps1`, which builds and
  bundles the helper.
- Release automation verifies `dist/FlowScribeGUI/WasapiCaptureHelper.exe`
  exists before archives are created.
- Release automation runs packaged helper smoke checks:
  - `WasapiCaptureHelper.exe version`
  - `WasapiCaptureHelper.exe probe`
- The release notes now mention GUI system-playback capture through the bundled
  helper.

---

## Phase 7: Controlled Transition Away From Direct `dshow` MVP

### Goal

Demote the current `dshow` capture path from "main implementation" to
"compatibility fallback".

## Steps

1. move current `dshow` logic behind a dedicated recorder or legacy wrapper
2. stop treating `dshow` loopback heuristics as the product default
3. make helper-first capture the normal GUI behavior
4. decide later whether legacy `dshow` should:
   - stay as a hidden compatibility path, or
   - be removed entirely

### Recommended Product Stance

In normal packaged GUI use:

- helper-based WASAPI path is the intended route
- legacy `dshow` should not silently replace it for end users

### Acceptance Criteria

- Complete: helper path is primary.
- Complete: `dshow` no longer defines the capture UX.
- Complete: code ownership is clearer between formal and legacy paths.

### Implementation Status

Completed in the current working flow:

- Added `src/flowscribe/media/system_audio_capture_legacy.py`.
- Moved the previous ffmpeg/DirectShow recorder behind
  `LegacyDshowCaptureRecorder`.
- Left `src/flowscribe/media/system_audio_capture.py` as a compatibility import
  module for older callers.
- Updated legacy tests to target `system_audio_capture_legacy` directly.
- Added a compatibility assertion that the old `FfmpegSystemAudioRecorder`
  import still resolves to the legacy recorder.
- Confirmed the GUI imports `CaptureController`, not the legacy DirectShow
  recorder.

---

## Test Plan

## Python Tests To Add

Suggested files:

```text
tests/test_system_audio_capture_helper.py
tests/test_capture_controller.py
```

Cover:

- helper `probe` parsing
- helper `list-devices` parsing
- helper `capture` JSON event parsing
- stop command behavior
- helper missing/broken executable cases
- GUI capture-state transitions where practical

## Helper Tests

Within the helper project, add tests for:

- device enumeration
- default-device detection
- loopback startup
- WAV finalization
- no-output-device failures

## Packaging Smoke Checks

Must be able to validate:

- helper runs `version`
- helper runs `probe`
- packaged GUI can locate helper binary

---

## Immediate Execution Checklist

If starting implementation right now, do this in order:

1. create `tools/wasapi-capture-helper/` - complete
2. add `WasapiCaptureHelper.csproj` - complete
3. implement `version` - complete
4. implement `probe` - complete
5. implement `list-devices` - complete
6. implement `capture` with stdin stop - complete
7. add `system_audio_capture_helper.py` - complete
8. add `CaptureController` - complete
9. wire GUI to helper support detection - complete
10. wire GUI start/stop capture flow - complete
11. create `scripts/build_wasapi_helper.ps1` - complete
12. update `scripts/build_gui_exe.ps1` - complete
13. update `release.yml` - complete
14. move current `dshow` path behind a compatibility label - complete

---

## Final Recommendation

Use this task order as the actual implementation path:

- **helper first**
- **Python integration second**
- **GUI hookup third**
- **packaging/release fourth**
- **legacy `dshow` cleanup last**

That sequence gets a real WASAPI-based product path into the project without
breaking the existing local transcription architecture.
