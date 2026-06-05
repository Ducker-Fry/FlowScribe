# Release Installation

This guide is for users who want to run FlowScribe without setting up Python or using the source tree.

## Download

Open the latest release page:

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

- `FlowScribe-vX.Y.Z-windows-x64.zip`: portable CLI package.
- `FlowScribeGUI-vX.Y.Z-windows-x64.zip`: portable GUI package.
- `FlowScribeSetup-online-x64.exe`: installer that downloads packaged app files during setup.
- `FlowScribeSetup-offline-x64.exe`: installer that bundles packaged app files locally.

## Install

Unzip the file to a folder you control, for example:

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

Do not move only `FlowScribe.exe` by itself. The surrounding files are required.

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

The packaged GUI launches in quiet `user` logging mode and does not open a
console window during normal use.

You should see checks for:

- Python runtime inside the package.
- Bundled `ffmpeg.exe`.
- Bundled `ffprobe.exe`.
- `faster-whisper`.
- Output directory write access.
- Model download access.

If you used the installer build, local help docs are copied into the managed
docs folder and the installed GUI points Help actions there. Installed builds
also default to **not** auto-downloading transcription models on first use, so
the first launch may ask you to open **Model Center** or the local model guide.

## Transcribe a File

Chinese-oriented transcription:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

Recommended command style:

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

Inside the GUI package you can:

- add local files and folders with checkbox selection
- paste a public URL
- capture Windows system playback through the bundled WASAPI helper
- open an existing transcript JSON or another generated transcript artifact
- browse a transcript library
- use a unified `Views` window to switch between run details, transcript review,
  and generated transcript artifacts
- edit transcript segment text
- save corrected transcript JSON by overwriting or writing a copy
- re-export transcript JSON into TXT, Markdown, JSON, SRT, or VTT
- save and apply named export profiles
- search transcript keywords
- bind local media to a transcript for playback sync directly inside the
  transcript review view

During capture, the GUI stays quiet in packaged mode but now reports whether the
capture file is actively growing or appears stalled. If capture starts but no
new audio data arrives, verify that Windows playback is active and that the
default output device is the one producing sound.

## Output

For an input file named:

```text
lecture.mp4
```

FlowScribe writes:

```text
outputs/
|-- lecture.txt
`-- lecture.md
```

## Model Downloads

Transcription models are not bundled in the portable packages.

- In source-tree or portable runs, selecting a new model may trigger a download.
- In installed app builds, first-use auto-download is disabled by default. Open
  **Model Center** or run `flowscribe model download ...` yourself.

Recommended model choices:

- `tiny`: quick smoke tests only.
- `small`: recommended starting point.
- `medium`: better accuracy, slower.
- `paraformer-zh`: Chinese-first model package for the `paraformer` provider.

Useful commands:

```powershell
flowscribe model list-available
flowscribe model list-installed
flowscribe model download small
flowscribe model download paraformer-zh
```

## Troubleshooting

If `doctor` passes but `outputs` is empty, that is normal. `doctor` only checks the environment. Run a transcription command to create TXT and Markdown files.

If a file reports `No audio stream found`, it likely contains video only. Some downloaded media stores video and audio separately.

If model access fails, check network access to Hugging Face, open Model Center,
or use a local model path where the selected provider supports it.

If the GUI reports that `WasapiCaptureHelper.exe` is missing, the GUI package is
incomplete. Re-extract the full `FlowScribeGUI` folder from the release ZIP and
do not move only `FlowScribeGUI.exe` by itself.

If the GUI says capture is running but no new audio data has arrived recently,
start actual system playback and confirm the expected Windows output device is
the current default playback device.
