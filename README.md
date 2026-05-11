# FlowScribe

FlowScribe is an extensible local-first media transcription toolkit. Its first goal is simple: turn local audio and video files into clean raw transcripts in TXT and Markdown formats. Over time, it is designed to grow into a broader input pipeline for URLs, system audio capture, desktop workflows, and optional external speech-to-text providers.

## Project Goals

- Convert local audio and video files into raw verbatim transcripts.
- Support Chinese, English, and mixed-language media.
- Start with a fast command-line workflow for validation and batch processing.
- Keep the core architecture extensible for future GUI, URL ingestion, system audio capture, and cloud transcription providers.
- Store results as ordinary files first, with database support reserved for later versions.

## Current Scope

Version 0 focuses on local files only:

- Input: local audio/video files and folders.
- Processing: normalize media into transcription-ready audio.
- Transcription: local speech recognition.
- Output: `.txt` and `.md` transcript files.

Out of scope for the first version:

- Summary generation.
- Opinion extraction.
- Database-backed library management.
- Desktop GUI.
- DRM circumvention or protected media extraction.

## Repository Layout

```text
FlowScribe/
├── docs/                  Project planning and architecture documents
├── examples/              Sample commands and placeholder fixtures
├── scripts/               Developer helper scripts
├── src/flowscribe/        Application source code
│   ├── cli/               Command-line interface
│   ├── config/            Configuration loading and defaults
│   ├── core/              Shared orchestration and domain models
│   ├── input/             Input source adapters
│   ├── media/             Media probing and audio preparation
│   ├── output/            Transcript writers
│   └── transcription/     Local and future provider-based transcribers
└── tests/                 Automated tests
```

## Development Status

This repository currently contains the initial project scaffold and planning documents. Implementation will proceed from a minimal local-file CLI pipeline.

## License

License to be decided before public release.
