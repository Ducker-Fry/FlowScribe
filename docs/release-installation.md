# Release Installation

This guide is for users who want to run FlowScribe without setting up Python or using the source tree.

## Download

Open the latest release page:

```text
https://github.com/Ducker-Fry/FlowScribe/releases
```

Download the Windows zip package:

```text
FlowScribe-v0.1.0-windows-x64.zip
```

## Install

Unzip the file to a folder you control, for example:

```text
D:\Tools\FlowScribe
```

After extraction, the folder should contain:

```text
FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- _internal/
```

Do not move only `FlowScribe.exe` by itself. The surrounding files are required.

## First Check

Open PowerShell in the extracted folder and run:

```powershell
.\FlowScribe\FlowScribe.exe doctor
```

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
