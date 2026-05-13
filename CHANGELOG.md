# Changelog

## Unreleased

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
