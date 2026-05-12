# FlowScribe

[![CI](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml/badge.svg)](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Ducker-Fry/FlowScribe?display_name=tag)](https://github.com/Ducker-Fry/FlowScribe/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](docs/packaging.md)
[![Local First](https://img.shields.io/badge/local--first-transcription-green)](docs/ethics-and-boundaries.md)

FlowScribe is a local-first command-line transcription tool that turns local audio and video files into raw TXT and Markdown transcripts. It is designed as an extensible open-source project: the current CLI focuses on local files, while the architecture leaves room for URL input, system audio capture, desktop GUI, and optional external speech-to-text providers.

## Features

- Transcribe local audio and video files.
- Process a single file, multiple files, or a folder.
- Recursively scan folders.
- Prepare audio with `ffmpeg`.
- Transcribe locally with `faster-whisper`.
- Export raw transcripts as `.txt` and `.md`.
- Export structured `.json` and subtitle `.srt` files.
- Request word-level timing data for future text-to-video navigation.
- Support Chinese, English, and mixed-language workflows.
- Tune transcription with `--beam-size`, `--vad-filter`, `--initial-prompt`, and `--task`.
- Use `--preset zh` for Chinese-oriented defaults.
- Check user environments with `flowscribe doctor`.
- Build a portable Windows one-folder executable with PyInstaller.

## Current Scope

FlowScribe v0.1 focuses on:

- Input: local audio/video files and folders.
- Processing: normalize media into transcription-ready audio.
- Transcription: local speech recognition.
- Output: `.txt` and `.md` transcript files.

Out of scope for v0.1:

- Summary generation.
- Opinion extraction.
- Database-backed library management.
- Desktop GUI.
- DRM circumvention or protected media extraction.

## Requirements

Developer install from source:

- Python 3.10 or newer.
- `ffmpeg` and `ffprobe` available on `PATH`.
- Windows PowerShell or another terminal.

Portable Windows release:

- Download and unzip the release folder.
- `ffmpeg.exe` and `ffprobe.exe` are included in the release folder.
- Whisper models are not bundled; the first model run may download model files.

## Installation From Source

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Check the CLI:

```powershell
flowscribe --help
```

Check the local environment:

```powershell
flowscribe doctor
```

## Quick Start

Transcribe one local file:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs
```

Transcribe a folder:

```powershell
flowscribe transcribe "D:\media" -o outputs --recursive
```

Use the Chinese preset:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

Write timestamped Markdown, JSON, and SRT:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --timestamps --format txt,md,json,srt
```

Write JSON with word-level timing data:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --word-timestamps --format json
```

For Chinese transcripts, FlowScribe keeps provider timing units in `raw_words` and writes
natural Chinese words in `words` when alignment is possible. For example, provider tokens
such as `牛` and `奶` can be merged into one navigable word, `牛奶`.

Run environment diagnostics:

```powershell
flowscribe doctor -o outputs --model small
```

Use a larger model for better accuracy:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --model medium --preset zh
```

The legacy form `flowscribe "D:\media\lecture.mp4" -o outputs` is still supported for compatibility, but `flowscribe transcribe ...` is the recommended command style.

Useful information commands:

```powershell
flowscribe version
flowscribe formats
flowscribe models
```

Outputs:

```text
outputs/
|-- lecture.txt
|-- lecture.md
|-- lecture.json
`-- lecture.srt
```

## Portable Windows Build

Build a one-folder executable:

```powershell
.\scripts\build_exe.ps1
```

The release folder will be:

```text
dist/FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- supporting runtime files
```

Test the packaged executable:

```powershell
.\dist\FlowScribe\FlowScribe.exe doctor
```

See [Packaging](docs/packaging.md) for release details.

## Useful Options

```text
--model small       Local faster-whisper model name or path
--language zh       Optional language hint, such as zh or en
--preset zh         Chinese-oriented transcription preset
--beam-size 5       Decoding beam size; larger can improve accuracy
--vad-filter        Enable voice activity detection
--initial-prompt    Guide terminology and mixed-language behavior
--task transcribe   Keep source language; this is the default
--timestamps        Include segment timestamps in timestamp-aware outputs
--word-timestamps   Include provider word timing data in JSON output
--format txt,md     Comma-separated output formats: txt,md,json,srt
--overwrite         Replace existing transcript files
--keep-audio        Keep prepared WAV files for debugging
```

`tiny` is useful for quick smoke tests. For real Chinese or mixed-language transcription, start with `small`; use `medium` or larger models when accuracy matters more than speed.

## Documentation

- [User Guide](docs/user-guide.md)
- [Release Installation](docs/release-installation.md)
- [Development Guide](docs/development-guide.md)
- [Packaging](docs/packaging.md)
- [Release Automation](docs/release-automation.md)
- [Architecture](docs/architecture.md)
- [Project Process](docs/project-process.md)
- [Roadmap](docs/roadmap.md)
- [Test Plan](docs/test-plan.md)
- [Ethics and Boundaries](docs/ethics-and-boundaries.md)
- [v1 Module Diagram](docs/v1-local-pipeline.mmd)

## Repository Layout

```text
FlowScribe/
|-- docs/                  Project documentation
|-- examples/              Example commands and future fixtures
|-- scripts/               Developer helper scripts
|-- src/flowscribe/        Application source code
|   |-- cli/               Command-line interface
|   |-- config/            Runtime settings and presets
|   |-- core/              Domain models, ports, pipeline, runner
|   |-- input/             Local file discovery
|   |-- media/             ffprobe/ffmpeg integration
|   |-- output/            TXT and Markdown writers
|   `-- transcription/     Local faster-whisper provider
`-- tests/                 Automated tests
```

## Legal and Ethical Boundaries

FlowScribe is intended for personal learning, accessibility, research notes, and lawful information processing. It should not be used to bypass DRM, crack applications, or redistribute copyrighted transcripts without permission.

## License

FlowScribe is licensed under the MIT License. See [LICENSE](LICENSE).
