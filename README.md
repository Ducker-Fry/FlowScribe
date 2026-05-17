# FlowScribe

[![CI](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml/badge.svg)](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Ducker-Fry/FlowScribe?display_name=tag)](https://github.com/Ducker-Fry/FlowScribe/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](docs/packaging.md)
[![Local First](https://img.shields.io/badge/local--first-transcription-green)](docs/ethics-and-boundaries.md)

FlowScribe is a local-first transcription toolkit that turns local media and public URL audio into readable transcripts. It ships with a command-line interface for batch-oriented workflows and a PySide6 desktop GUI for interactive transcript viewing, search, and local media sync.

## Features

- Transcribe local audio and video files.
- Transcribe public URLs with audio-first downloading/extraction.
- Process a single file, multiple files, or a folder.
- Recursively scan folders.
- Prepare audio with `ffmpeg`.
- Transcribe locally with `faster-whisper`.
- Export raw transcripts as `.txt` and `.md`.
- Export structured `.json` and subtitle `.srt` files.
- Open transcript JSON in the desktop GUI and read timestamped segments.
- Search transcript keywords in the GUI and jump to matching context.
- Bind local media to a transcript and seek playback from segments or search hits.
- Request word-level timing data for future text-to-video navigation.
- Support Chinese, English, and mixed-language workflows.
- Tune transcription with `--beam-size`, `--vad-filter`, `--initial-prompt`, and `--task`.
- Use `--preset zh` for Chinese-oriented defaults.
- Check user environments with `flowscribe doctor`.
- Build a portable Windows one-folder executable with PyInstaller.
- Build a portable Windows GUI executable with quiet packaged startup defaults.
- Use a consolidated `Views` workspace, transcript library, and help surface in the GUI.
- Start long-media progressive transcription so transcript segments can appear before the full run finishes.
- Save URL-derived media in the GUI, choose where it goes, and auto-bind it
  back to the transcript workspace.

## Current Scope

FlowScribe v0.2 focuses on:

- Input: local audio/video files, folders, and public audio-first URLs.
- Processing: normalize media into transcription-ready audio.
- Transcription: local speech recognition with CLI and desktop GUI entry points.
- Output: `.txt`, `.md`, `.json`, `.srt`, and `.vtt` transcript files.
- Interactive transcript review: desktop viewing, keyword search, and local media sync.

Out of scope for the current release line:

- Summary generation.
- Opinion extraction.
- Database-backed library management.
- DRM circumvention or protected media extraction.
- Default high-resolution video downloading from URL pages.

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

Run the desktop GUI from source:

```powershell
flowscribe gui
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

Transcribe a public URL with audio-first handling:

```powershell
flowscribe url "https://example.com/video-or-audio" -o outputs
```

URL input defaults to audio-first behavior. FlowScribe downloads or extracts audio for
transcription and does not intentionally keep high-resolution video files. Use
`--keep-media` only when you want to keep the downloaded/extracted intermediate media.

Try the real CCTV demo:

```powershell
flowscribe url "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml" -o outputs\demo-cctv --format txt,md,json --model small --language zh --preset zh --overwrite
```

Example terminal output:

```text
Downloading/extracting remote audio...
Remote audio ready: ...\remote-audio.m4a
Wrote: ...\outputs\demo-cctv\remote-audio.txt
Wrote: ...\outputs\demo-cctv\remote-audio.md
Wrote: ...\outputs\demo-cctv\remote-audio.json
Done. Succeeded: 1. Failed: 0.
```

Example transcript excerpt:

```text
更多新闻资讯,来看一组简讯。
11号,两高联合发布《办理非法占用耕地案件司法》解释,强化对耕地的全链条保护。
2023年以来,全国检察机关共办理非法占用耕地公益诉讼案件1.7万余件...
```

Demo screenshots:

![FlowScribe URL transcription demo](docs/assets/demo-terminal.png)

![FlowScribe transcript output demo](docs/assets/demo-transcript.png)

See [Demo](docs/demo.md) for the full walkthrough.

Use the Chinese preset:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

Write timestamped Markdown, JSON, SRT, and VTT:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --timestamps --format txt,md,json,srt,vtt
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

Inspect a local file or URL before transcription:

```powershell
flowscribe inspect "D:\media\lecture.mp4"
flowscribe inspect "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml"
```

For URL pages, `inspect` shows whether FlowScribe can use an audio-only stream or
needs to stream the lowest combined media and extract audio.
If your DNS or proxy returns an unusual blocked IPv6 address for a public site, try
`--network-family ipv4`.
For login-required pages that you are allowed to access, pass an explicit
Netscape cookie file with `--cookies path\to\cookies.txt`.
For local proxies such as Clash, pass `--proxy http://127.0.0.1:7890`.

Search a transcript JSON and locate a keyword:

```powershell
flowscribe search outputs\lecture.json "机器学习"
```

Limit and filter search results:

```powershell
flowscribe search outputs\lecture.json "机器学习" --limit 10 --after 00:10:00 --before 00:30:00 --context-chars 50
```

Write machine-readable search results:

```powershell
flowscribe search outputs\lecture.json "机器学习" --json
```

When word timestamps are available, search results use word-level timing. Otherwise,
FlowScribe falls back to the matched segment's timestamp range.

Outputs:

```text
outputs/
|-- lecture.txt
|-- lecture.md
|-- lecture.json
|-- lecture.srt
`-- lecture.vtt
```

## Desktop GUI

Run the GUI from source:

```powershell
flowscribe gui
```

or:

```powershell
python -m flowscribe.gui
```

The GUI currently supports:

- Local file and folder selection with remembered checkbox state.
- Public URL transcription with proxy, cookies, and network-family options.
- Opening existing transcript JSON files.
- Transcript search with clickable hit lists.
- Transcript-bound local media playback and seek-on-click.
- A consolidated `Views` workspace for transcript review, artifacts, and library access.
- Transcript segment editing, re-export, and quick artifact switching.
- A help and diagnostics surface for first-run guidance and common recovery paths.
- Progressive long-run transcription plumbing with chunk planning, resume-ready cache, and GUI-facing progress events.
- URL media preservation choices, custom save directories, and auto-bind
  behavior for saved URL media.

See [Desktop GUI](docs/gui.md) for the current workflow and packaging notes.

## Portable Windows Build

Build the CLI one-folder executable:

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

Build the desktop GUI package:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

The GUI output folder will be:

```text
dist/FlowScribeGUI/
|-- FlowScribeGUI.exe
|-- WasapiCaptureHelper.exe
|-- NAudio*.dll
`-- _internal/
```

Packaged GUI builds default to quiet `user` logging mode and use a windowed launch path, so normal end-user runs do not open a console window. The bundled WASAPI helper supports Windows system-playback capture from the GUI.

See [Packaging](docs/packaging.md) and [Desktop GUI](docs/gui.md) for release details.

## Useful Options

```text
--model small       Local faster-whisper model name or path
--language zh       Optional language hint, such as zh or en
--preset zh         Chinese-oriented transcription preset
--beam-size 5       Decoding beam size; larger can improve accuracy
--vad-filter        Enable voice activity detection
--no-vad-filter     Disable voice activity detection explicitly
--initial-prompt    Guide terminology and mixed-language behavior
--task transcribe   Keep source language; this is the default
--timestamps        Include segment timestamps in timestamp-aware outputs
--word-timestamps   Include provider word timing data in JSON output
--format txt,md     Comma-separated output formats: txt,md,json,srt,vtt
--overwrite         Replace existing transcript files
--keep-audio        Keep prepared WAV files for debugging
--keep-media        URL input only: keep downloaded/extracted media
```

URL safety options:

```text
--max-download-mb 2048     Limit downloaded audio/intermediate media size
--max-duration 04:00:00    Limit remote media duration
--download-timeout 30      Limit network/download operations
--network-family auto      Choose auto, ipv4, or ipv6 URL networking
--cookies cookies.txt      Explicit cookies file for login-required media
--proxy http://127.0.0.1:7890  Explicit proxy for URL media access
```

`tiny` is useful for quick smoke tests. For real Chinese or mixed-language transcription, start with `small`; use `medium` or larger models when accuracy matters more than speed.
If the beginning of a video is missing or inaccurate, retry with `--no-vad-filter`; VAD can over-filter news intros, music beds, or low-volume openings.

## Documentation

- [User Guide](docs/user-guide.md)
- [Demo](docs/demo.md)
- [Inspect Command](docs/inspect.md)
- [Cookies For URL Media](docs/cookies.md)
- [Proxy Configuration](docs/proxy.md)
- [VAD Guide](docs/vad-guide.md)
- [Desktop GUI](docs/gui.md)
- [GUI Interfaces](docs/gui-interfaces.md)
- [Release Installation](docs/release-installation.md)
- [Development Guide](docs/development-guide.md)
- [Developer Handoff](docs/developer-handoff.md)
- [Packaging](docs/packaging.md)
- [Release Automation](docs/release-automation.md)
- [Long Media Progressive Transcription Task List](docs/long-media-progressive-transcription-task-list.md)
- [Phase 6 Summary And Phase 7 Plan](docs/phase-6-summary-and-phase-7-plan.md)
- [Phase 7 Task List](docs/phase-7-task-list.md)
- [Phase 2 Summary And Phase 3 Plan](docs/phase-2-summary-and-phase-3-plan.md)
- [Architecture](docs/architecture.md)
- [JSON Format](docs/json-format.md)
- [Project Process](docs/project-process.md)
- [Roadmap](docs/roadmap.md)
- [Test Plan](docs/test-plan.md)
- [Ethics and Boundaries](docs/ethics-and-boundaries.md)
- [v1 Module Diagram](docs/v1-local-pipeline.mmd)

## Repository Layout

```text
FlowScribe/
|-- docs/                  Project documentation
|-- examples/              Runnable example commands
|-- scripts/               Developer helper scripts
|-- src/flowscribe/        Application source code
|   |-- cli/               Command-line interface
|   |-- config/            Runtime settings and presets
|   |-- core/              Domain models, ports, pipeline, runner
|   |-- input/             Local file discovery and URL source handling
|   |-- media/             ffprobe/ffmpeg integration
|   |-- output/            TXT and Markdown writers
|   `-- transcription/     Local faster-whisper provider
`-- tests/                 Automated tests
```

## Legal and Ethical Boundaries

FlowScribe is intended for personal learning, accessibility, research notes, and lawful information processing. It should not be used to bypass DRM, crack applications, or redistribute copyrighted transcripts without permission.

## License

FlowScribe is licensed under the MIT License. See [LICENSE](LICENSE).
