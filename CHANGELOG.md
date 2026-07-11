# Changelog

## Unreleased

## 0.3.7 - 2026-07-11

- Added remote execution support across CLI and GUI so local clients can submit work to another FlowScribe server and download finished artifacts back to the workstation.
- Added persisted remote server profiles with base URL, bearer token, timeout, artifact-download preference, and optional server-side cookies path for login-required URL media.
- Hardened the remote server path for small hosts by switching the control plane to `ThreadingHTTPServer`, rejecting excess heavy remote tasks with HTTP `429`, and isolating downloaded-artifact staging on the server.
- Improved remote URL media acquisition by ignoring temporary `yt-dlp` partial files when selecting the final downloaded audio artifact.

## 0.2.5 - 2026-05-15

- Added a unified GUI `Views` window for switching between run details,
  transcript review, and generated transcript artifacts.
- Added direct artifact viewing for `.json`, `.txt`, `.md`, `.srt`, and `.vtt`
  outputs from the desktop GUI.
- Moved transcript media sync into the transcript-facing view so segment
  navigation, playback sync, search, and editing stay in one workflow surface.
- Made the transcript library store tolerate unreadable or unwritable state-file
  paths instead of failing GUI startup.

## 0.2.4 - 2026-05-15

- Added a dedicated C#/.NET `WasapiCaptureHelper.exe` for Windows system-playback capture.
- Added helper commands for `version`, `probe`, `list-devices`, and stdin-controlled WAV capture.
- Added Python-side WASAPI helper integration and GUI capture controller support.
- Connected GUI system-audio capture to the helper-first path while preserving captured-WAV transcription workflow.
- Added helper build and GUI packaging integration so `WasapiCaptureHelper.exe` and NAudio dependencies ship with the GUI package.
- Added release workflow smoke checks for the packaged WASAPI helper.
- Moved the old ffmpeg/DirectShow capture implementation behind a legacy compatibility boundary.

- Added the Phase 3.1 PySide6 desktop GUI skeleton for collecting transcription form state.
- Connected the desktop GUI to background local-file transcription with progress and output display.

## 0.2.2 - 2026-05-13

- Fixed Windows release packaging to skip Chocolatey shim executables and copy the real ffmpeg/ffprobe binaries.

## 0.2.1 - 2026-05-13

- Fixed Windows release packaging so bundled ffmpeg/ffprobe companion DLLs are copied when needed.

## 0.2.0 - 2026-05-13

- Added URL transcription through `flowscribe url` with audio-first download/extraction.
- Added `flowscribe inspect` for local files and public URL media.
- Added `flowscribe search` for keyword search and timestamp location in transcript JSON.
- Added JSON, SRT, and VTT output support for downstream GUI, browser, and AI workflows.
- Added provider word timestamps plus Chinese natural-word alignment with `raw_words` and `words`.
- Added a stable `TranscriptionService` interface for future GUI integration.
- Added URL safety controls for file size, duration, timeouts, SSRF protection, temporary media cleanup, and `--keep-media`.
- Added `--network-family` for IPv4/IPv6 troubleshooting.
- Added explicit `--cookies` support for `flowscribe url` and `flowscribe inspect`.
- Added explicit `--proxy` support for URL inspection and transcription.
- Documented safe cookie-file usage and ignored common cookie paths to reduce accidental commits.

## 0.1.0 - 2026-05-11

- Implemented the first local-file transcription CLI.
- Added explicit CLI subcommands: `transcribe`, `version`, `formats`, and `models`.
- Added placeholders for future `url` and `capture` commands.
- Added segment-level timestamp output with `--timestamps`.
- Added selectable output formats with `--format txt,md,json,srt`.
- Added JSON and SRT transcript writers.
- Added `TranscriptWord` and segment word placeholders for future word-level timing.
- Added local file and folder discovery for supported media formats.
- Added ffprobe-based audio stream detection and ffmpeg-based WAV preparation.
- Added faster-whisper local transcription provider.
- Added `flowscribe doctor` environment diagnostics for Python, ffmpeg, ffprobe, faster-whisper, output writes, and model access.
- Added PyInstaller one-folder packaging script and packaging documentation.
- Added GitHub Actions CI for automated tests and lint checks.
- Added GitHub Actions release automation for tagged Windows builds.
- Added TXT and Markdown transcript outputs.
- Added transcription quality options: `--beam-size`, `--vad-filter`, `--initial-prompt`, and `--task`.
- Added Chinese-oriented preset: `--preset zh`.
- Added bilingual user guide, development guide, architecture document, requirements, roadmap, and test plan.
- Added unit tests for file filtering, output writing, pipeline orchestration, and settings presets.
- Adopted the MIT License.
