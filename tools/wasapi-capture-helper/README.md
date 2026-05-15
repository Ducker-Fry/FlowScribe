# WasapiCaptureHelper

WasapiCaptureHelper is FlowScribe's Windows-native system-playback capture helper.
It is designed to run as a standalone subprocess owned by the Python GUI, write a
normal WAV file, and hand that file back to the existing local transcription
pipeline.

The helper exists because mainstream Windows FFmpeg builds do not provide a
reliable WASAPI input path. FlowScribe uses this helper for the formal Windows
loopback capture path instead of depending on DirectShow loopback-style devices.

## Build Locally

From the repository root:

```powershell
dotnet build .\tools\wasapi-capture-helper\WasapiCaptureHelper.sln -c Release
```

The project targets `net8.0-windows` and `win-x64`.

## FlowScribe Integration

The GUI will call the helper as a controlled subprocess:

```text
FlowScribe GUI -> WasapiCaptureHelper.exe -> WAV file -> local transcription
```

The helper does not perform transcription, URL downloading, transcript writing,
or GUI work. Its responsibility is limited to Windows output-device discovery,
WASAPI loopback capture, WAV writing, and structured runtime status output.

## JSON Stdout Contract

Commands write machine-readable JSON to stdout. The Python side should not parse
human-oriented status text.

Command surface:

```powershell
WasapiCaptureHelper.exe version
WasapiCaptureHelper.exe probe
WasapiCaptureHelper.exe list-devices
WasapiCaptureHelper.exe capture --output E:\temp\capture.wav --device default
```

### `version`

Returns helper version and runtime information.

### `probe`

Returns whether a default active Windows render device is available for WASAPI
loopback capture.

### `list-devices`

Returns active Windows render devices and the current default output device id.

### `capture`

Starts WASAPI loopback capture and writes a WAV file.

Arguments:

- `--output <absolute-path>` is required.
- `--device default|<device-id>` defaults to `default`.
- `--sample-rate <hz>` is optional.
- `--channels 1|2` is optional.

The helper listens on stdin and stops cleanly when it receives:

```text
stop
```

The `capture` command emits JSON lines for runtime events:

```json
{"event":"started","device_id":"...","device_name":"Speakers","output":"E:\\temp\\capture.wav"}
{"event":"stopping"}
{"event":"completed","output":"E:\\temp\\capture.wav","duration_seconds":8.2}
```

Errors are emitted as JSON:

```json
{"event":"error","message":"No active output device available for loopback capture."}
```

Exit codes:

- `0`: command succeeded.
- `2`: unsupported environment or invalid device.
- `3`: capture failed after startup.
- `4`: invalid arguments.
