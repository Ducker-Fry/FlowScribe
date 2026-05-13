# Changelog

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
