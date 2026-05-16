# Release Installation

This guide is for users who want to run FlowScribe without setting up Python or using the source tree.

## Download

Open the latest release page:

```text
https://github.com/Ducker-Fry/FlowScribe/releases
```

Download the Windows zip package:

```text
FlowScribe-v0.2.6-windows-x64.zip
FlowScribeGUI-v0.2.6-windows-x64.zip
```

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

## Transcribe a File

Chinese-oriented transcription:

```powershell
.\FlowScribe\FlowScribe.exe "D:\media\lecture.mp4" -o outputs --model small --preset zh
```

Recommended command style:

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --model small --preset zh
```

English transcription:

```powershell
.\FlowScribe\FlowScribe.exe "D:\media\english.mp4" -o outputs --model small --language en
```

Quick smoke test:

```powershell
.\FlowScribe\FlowScribe.exe "D:\media\short.wav" -o outputs --model tiny --overwrite
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

Whisper models are not bundled in the zip package. The first run with a selected model may download model files from Hugging Face.

Recommended model choices:

- `tiny`: quick smoke tests only.
- `small`: recommended starting point.
- `medium`: better accuracy, slower.

## Troubleshooting

If `doctor` passes but `outputs` is empty, that is normal. `doctor` only checks the environment. Run a transcription command to create TXT and Markdown files.

If a file reports `No audio stream found`, it likely contains video only. Some downloaded media stores video and audio separately.

If model access fails, check network access to Hugging Face or use a local model path.

If the GUI reports that `WasapiCaptureHelper.exe` is missing, the GUI package is
incomplete. Re-extract the full `FlowScribeGUI` folder from the release ZIP and
do not move only `FlowScribeGUI.exe` by itself.

If the GUI says capture is running but no new audio data has arrived recently,
start actual system playback and confirm the expected Windows output device is
the current default playback device.
