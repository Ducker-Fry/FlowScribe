# WASAPI Helper Design

This document captures the recommended formal design for Windows system-audio
capture in FlowScribe after confirming that current mainstream Windows FFmpeg
builds do not provide a usable `wasapi` input device.

The goal is to replace the current `dshow`-based MVP path with a more stable
Windows-native loopback capture path while preserving the existing FlowScribe
transcription pipeline.

## Goal

Build a formal Windows system-audio capture architecture around a dedicated
WASAPI helper:

```text
Windows system playback
  -> WasapiCaptureHelper.exe
  -> WAV / PCM file
  -> existing local input path
  -> GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

Key outcomes:

- system-audio capture no longer depends on FFmpeg input-device support
- capture remains decoupled from transcription
- captured output is still a normal local WAV file
- GUI behavior stays simple and product-oriented

## Why This Exists

As of 2026-05-15, FlowScribe has confirmed that:

- official-style Windows FFmpeg builds in current use do not expose a working
  `wasapi` input device
- the current `dshow` MVP path is limited to environments with loopback-like
  devices such as `Stereo Mix`, `What U Hear`, or virtual loopback drivers
- continuing to chase a "WASAPI-capable FFmpeg distribution" is not a reliable
  product path

That means a formal product solution must move actual system-audio capture out
of FFmpeg and into a dedicated Windows-native helper.

## Recommended Technical Choice

### Primary Recommendation

Use **C# / .NET** to build a dedicated `WasapiCaptureHelper.exe`.

### Why C# / .NET

- Windows audio APIs are easier to access and maintain than raw Win32/COM code
- the `NAudio` ecosystem provides practical support for:
  - device enumeration
  - WASAPI loopback capture
  - WAV writing
- the helper can live as a standalone process instead of being embedded into
  the Python GUI process
- failure boundaries are cleaner than mixing low-level audio capture directly
  into the PySide6 application

### Why Not Prioritize Other Options

- **C++**: powerful but too expensive in implementation and maintenance cost for
  this phase
- **pure Python**: higher runtime/packaging risk for a system-level Windows
  capture feature
- **FFmpeg-only**: does not meet the desired WASAPI product path

## Architecture

Recommended structure:

```text
FlowScribe GUI
  -> CaptureController (Python)
  -> WasapiCaptureHelper.exe
  -> WAV file
  -> existing local source path
  -> GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

Principles:

- capture and transcription remain decoupled
- the helper has one narrow responsibility: reliable Windows system-playback
  capture
- FlowScribe treats the helper as a controlled runtime dependency
- the resulting WAV is fed into the existing local transcription path without a
  new pipeline

## Helper Responsibility Boundary

### The Helper Should Do

- enumerate Windows output devices
- choose or accept a target render device
- run WASAPI loopback capture
- write a WAV file
- emit structured status and error information

### The Helper Should Not Do

- transcription
- URL download
- transcript generation
- GUI logic
- recent-history handling
- FFmpeg media preparation

## Helper Process Interface

The preferred first implementation is:

```text
standalone helper process
  + CLI arguments
  + structured stdout/stderr
  + WAV output file
```

Do not start with DLL embedding or a complex IPC-first design.

### Recommended Commands

#### `version`

Returns helper version/runtime info.

#### `probe`

Checks whether loopback capture is supported on the current machine.

Example JSON:

```json
{
  "supported": true,
  "default_output_name": "Speakers (Realtek Audio)"
}
```

or:

```json
{
  "supported": false,
  "reason": "No active output device available for loopback capture."
}
```

#### `list-devices`

Lists output devices that can participate in loopback capture.

Example JSON:

```json
{
  "default_output_id": "device-1",
  "devices": [
    {
      "id": "device-1",
      "name": "Speakers (Realtek Audio)",
      "is_default": true
    },
    {
      "id": "device-2",
      "name": "Headphones (Bluetooth Headset)",
      "is_default": false
    }
  ]
}
```

#### `capture`

Starts loopback capture until told to stop.

Suggested arguments:

- `--output <path>`
- `--device default|<id>`
- optional `--sample-rate 16000`
- optional `--channels 1`

## GUI And Helper Interaction

### Python-Side Controller

Add a thin `CaptureController` layer in Python that:

- launches the helper
- tracks helper lifecycle
- handles stop/finalize behavior
- verifies capture output
- hands the WAV path back to the GUI

### GUI Responsibilities

The Qt layer should:

- render buttons and status text
- decide whether to keep or delete the capture file
- re-add the captured WAV as a local source
- pass the WAV through the normal transcription path

### Startup Flow

On GUI startup:

1. run `WasapiCaptureHelper.exe probe`
2. if supported:
   - enable `Start Capture`
   - show a ready message
3. if unsupported:
   - disable `Start Capture`
   - show a clear product-style explanation

### Capture Flow

#### Start

1. GUI chooses an output path
2. GUI starts:

   ```text
   WasapiCaptureHelper.exe capture --output ... --device default
   ```

3. `Start Capture` becomes disabled
4. `Stop Capture` becomes enabled
5. GUI status reflects active system-playback capture

#### Stop

1. GUI sends stop signal
2. helper finalizes the WAV
3. GUI verifies the artifact
4. GUI re-adds the WAV into the local-source list
5. GUI either keeps the file or schedules cleanup after transcription

## Stop Mechanism

Recommended first version:

- GUI holds the child-process handle
- helper listens on `stdin`
- GUI writes:

  ```text
  stop
  ```

- helper flushes/finalizes WAV and exits cleanly

Fallback termination is acceptable as a defensive backup, but it should not be
the primary control path.

## Structured Runtime Output

The helper should emit machine-readable status events. JSON lines are a good
fit.

Examples:

```json
{"event":"started","device":"Speakers (Realtek Audio)","output":"E:\\capture.wav"}
{"event":"stopping"}
{"event":"completed","output":"E:\\capture.wav","duration_seconds":8.3}
```

Error example:

```json
{"event":"error","message":"No active output device available for loopback capture."}
```

This keeps the GUI from having to parse human-oriented stderr text.

## Device Strategy

### Recommended MVP Strategy

Capture the **default playback device** first.

Benefits:

- simplest GUI behavior
- no extra settings UI needed in the first version
- matches the normal user mental model of "record what my computer is playing"

### Future Extension

Device selection can be added later after the default-device path is stable.

## Packaging And Release Integration

The helper must become a controlled release dependency just like bundled FFmpeg.

### Desired Release Layout

```text
dist/FlowScribeGUI/
  FlowScribeGUI.exe
  ffmpeg.exe
  ffprobe.exe
  WasapiCaptureHelper.exe
  ...
```

### Build Script Changes

#### `scripts/build_gui_exe.ps1`

Should:

- verify that the helper has been built
- copy `WasapiCaptureHelper.exe` into the GUI package directory

#### `scripts/build_exe.ps1`

Decision point:

- if capture stays GUI-only in this phase, CLI packaging may omit the helper
- if future CLI capture is planned, the helper can be copied there too

### Release Workflow Changes

Release automation should:

1. build the helper
2. copy the helper into the packaged GUI bundle
3. run smoke checks for helper presence and helper CLI compatibility

Suggested smoke checks:

- `WasapiCaptureHelper.exe version`
- `WasapiCaptureHelper.exe probe`
- packaged GUI self-test still succeeds

If CI cannot run real loopback capture on the runner, it should still validate
protocol-level behavior and executable presence.

## Version Pinning

### Helper Source

- keep helper source in the repository
- version it alongside FlowScribe releases

### Helper Dependencies

- fix target framework explicitly
- pin package versions such as `NAudio`

The goal is to avoid any "download a random helper binary" workflow.

## Licensing And Runtime Model

The helper should be released as part of FlowScribe's normal Windows package.

Things to verify and document:

- the helper's own project license alignment
- third-party dependency licenses such as `NAudio`
- whether the release uses:
  - framework-dependent deployment, or
  - self-contained deployment

### Recommended Direction

Long-term, prefer a **self-contained helper** for end-user simplicity.

Short-term during development, framework-dependent is acceptable if it speeds up
iteration.

## Migration Plan From Current `dshow` MVP

Do not replace everything at once. Use an incremental transition.

### Phase 1: Reclassify Existing Path

Treat the current implementation as:

```text
LegacyDshowCaptureRecorder
```

It becomes a compatibility path, not the long-term design center.

### Phase 2: Add WASAPI Helper Path

Introduce:

```text
WasapiHelperCaptureRecorder
```

This recorder communicates with the helper process and becomes the preferred
path.

### Phase 3: Change Default Priority

Move from:

```text
dshow first
```

to:

```text
wasapi helper first
legacy dshow fallback second
```

### Phase 4: Re-evaluate Fallback

Once the helper path is stable in packaged builds, decide whether to:

- keep `dshow` as a compatibility fallback
- or remove it from the normal end-user path entirely

Recommended long-term direction:

- keep `dshow` only as a compatibility path, if at all
- treat WASAPI helper as the formal product route

## Suggested Code Layout

Recommended future structure:

```text
src/flowscribe/media/system_audio_capture.py
  - capture facade
  - support/result models
  - abstract recorder interface

src/flowscribe/media/system_audio_capture_dshow.py
  - legacy dshow recorder

src/flowscribe/media/system_audio_capture_helper.py
  - helper process integration
  - JSON event parsing

tools/wasapi-capture-helper/
  - helper source project
  - helper build scripts
  - helper README and licensing notes
```

This keeps:

- Python media orchestration clean
- GUI integration thin
- native helper build concerns isolated

## Testing Strategy

### Python Tests

Cover:

- helper discovery
- `probe` parsing
- `list-devices` parsing
- capture start/stop process protocol
- GUI capture-state transitions
- keep/delete capture-file flow

### Helper Tests

Cover:

- default-output-device enumeration
- loopback capture startup
- stop/finalize behavior
- WAV correctness
- no-device failure paths

### Smoke Validation

At minimum:

- helper `version`
- helper `probe`
- packaged GUI recognizes helper availability correctly

Real system-playback capture verification can remain a manual validation step
until a practical automation strategy exists.

## Suggested Delivery Sequence

### Milestone 4.5A

- create helper project
- implement `version`
- implement `probe`
- implement `list-devices`

### Milestone 4.5B

- implement `capture --output ... --device default`
- implement stdin-based stop
- finalize WAV output reliably

### Milestone 4.5C

- integrate helper path into GUI
- feed captured WAV into local-source workflow
- wire keep/delete behavior

### Milestone 4.5D

- integrate helper build into packaging
- integrate helper presence into release workflow
- add helper smoke validation

### Milestone 4.5E

- demote current `dshow` path to compatibility mode
- decide later whether to keep or remove it from normal builds

## Final Recommendation

The recommended formal product direction is:

**Use a standalone C# / .NET `WasapiCaptureHelper.exe` with NAudio, invoked by
the Python GUI as a controlled subprocess.**

Reasons:

- practical implementation path
- cleaner Windows integration than raw C++ for this phase
- more reliable than continuing to stretch `dshow`
- easier to bundle into release artifacts than ad hoc system dependencies
- preserves the current FlowScribe architecture by reusing the normal local
  transcription pipeline

This gives FlowScribe a realistic path from:

```text
best-effort Windows capture MVP
```

to:

```text
formal Windows loopback capture product capability
```
