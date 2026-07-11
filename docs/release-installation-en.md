[中文](release-installation.md) | English

# Release Installation

This guide is for users who want to run FlowScribe without setting up Python or working from the source tree.

## Download

Open the latest Gitee release page if GitHub is slow or blocked:

```text
https://gitee.com/Ducker-Fry/FlowScribe/releases
```

GitHub remains available as a mirror:

```text
https://github.com/Ducker-Fry/FlowScribe/releases
```

Download the package you need:

```text
FlowScribe-vX.Y.Z-windows-x64.zip
FlowScribeGUI-vX.Y.Z-windows-x64.zip
FlowScribeSetup-online-x64.exe
FlowScribeSetup-offline-x64.exe
```

- `FlowScribe-vX.Y.Z-windows-x64.zip`: portable CLI package
- `FlowScribeGUI-vX.Y.Z-windows-x64.zip`: portable GUI package
- `FlowScribeSetup-online-x64.exe`: installer that downloads packaged app files during setup from the configured release mirror
- `FlowScribeSetup-offline-x64.exe`: installer that includes packaged app files locally

## Install

Extract the package into a folder you control, for example:

```text
D:\Tools\FlowScribe
```

After extracting the CLI package, the folder should contain:

```text
FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- _internal/
```

Do not move only `FlowScribe.exe` by itself.

After extracting the GUI package, the folder should contain:

```text
FlowScribeGUI/
|-- FlowScribeGUI.exe
|-- WasapiCaptureHelper.exe
|-- NAudio*.dll
`-- _internal/
```

Do not move only `FlowScribeGUI.exe` by itself.

## First Check

Open PowerShell in the extracted folder and run:

```powershell
.\FlowScribe\FlowScribe.exe doctor
```

For the GUI package, start:

```powershell
.\FlowScribeGUI\FlowScribeGUI.exe
```

The packaged GUI launches in quiet user logging mode and does not open a console during normal use.

You should see checks for:

- bundled runtime components
- bundled `ffmpeg.exe`
- bundled `ffprobe.exe`
- `faster-whisper`
- output directory write access
- model download access

Installed builds copy local help docs into the managed docs folder. `Help` and `Open Model Guide` point there. Installed builds also default to not auto-downloading transcription models on first use, so the first launch may ask you to open `Model Center` or the local model guide.

## Transcribe A File

Chinese-oriented transcription:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

Recommended general command style:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --model small --preset zh
```

English transcription:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\english.mp4" -o outputs --model small --language en
```

Quick smoke test:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\short.wav" -o outputs --model tiny --overwrite
```

## Use The Desktop GUI

The current GUI is centered on:

- `Single Task` for one local file or one URL
- `Queue` for batch local files and URLs
- `Library` for historical transcripts
- `Open View` for logs, transcript search, segment editing, and re-export

You can currently:

- add local files and folders with checkbox selection
- paste a public URL
- open existing transcript JSON
- browse a transcript library
- search transcript keywords
- edit transcript segment text
- save corrected transcript JSON by overwriting or writing a copy
- re-export transcript JSON into TXT, Markdown, JSON, SRT, or VTT
- bind local media to a transcript for playback sync

The GUI also includes a `System Audio Capture` entry, but that path is still being refined and should not be treated as the most stable primary workflow yet.

## Output

For an input file named:

```text
lecture.mp4
```

FlowScribe can write:

```text
outputs/
|-- lecture.txt
|-- lecture.md
|-- lecture.json
|-- lecture.srt
`-- lecture.vtt
```

## Model Downloads

Transcription models are not bundled inside the portable packages.

- source-tree and portable runs may download models when needed
- installed builds disable first-use auto-download by default

Recommended model choices:

- `tiny`: smoke tests only
- `small`: recommended starting point
- `medium`: better accuracy, slower
- `paraformer-zh`: Chinese-first package for the `paraformer` provider

Useful commands:

```powershell
flowscribe model list-available
flowscribe model list-installed
flowscribe model download small
flowscribe model download paraformer-zh
```

## Troubleshooting

If `doctor` passes but `outputs` is empty, that is normal. `doctor` checks the environment only.

If a file reports `No audio stream found`, inspect it first. Some media contains video only or stores audio separately.

If model access fails, check network access, open `Model Center`, or use a local model path where supported.

If the GUI reports that `WasapiCaptureHelper.exe` is missing, the GUI package is incomplete. Re-extract the full `FlowScribeGUI` folder and do not move only `FlowScribeGUI.exe`.

If system audio capture appears to start but no audio data arrives, start actual system playback and confirm that the expected Windows output device is the current default playback device.
