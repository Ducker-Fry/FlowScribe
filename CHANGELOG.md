# Changelog

## 0.1.0 - 2026-05-11

- Implemented the first local-file transcription CLI.
- Added local file and folder discovery for supported media formats.
- Added ffprobe-based audio stream detection and ffmpeg-based WAV preparation.
- Added faster-whisper local transcription provider.
- Added TXT and Markdown transcript outputs.
- Added transcription quality options: `--beam-size`, `--vad-filter`, `--initial-prompt`, and `--task`.
- Added Chinese-oriented preset: `--preset zh`.
- Added bilingual user guide, development guide, architecture document, requirements, roadmap, and test plan.
- Added unit tests for file filtering, output writing, pipeline orchestration, and settings presets.
- Adopted the MIT License.
