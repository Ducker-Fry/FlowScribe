# Requirements

## Primary User Need

The user wants to read information from media instead of watching or listening to it in real time. FlowScribe should convert media into raw transcripts that can be skimmed, searched, archived, or passed to an AI assistant for higher-level analysis.

## v0.1 Functional Requirements

- Accept one local audio or video file.
- Accept a folder for batch processing.
- Detect supported media files.
- Prepare audio for transcription.
- Run local speech-to-text transcription.
- Support Chinese and English speech.
- Export raw transcript as TXT.
- Export raw transcript as Markdown.
- Continue batch processing when one item fails.
- Print useful progress and error information.

## v0.1 Non-Functional Requirements

- Command-line first.
- Local-first transcription.
- Clear module boundaries.
- Extensible for future input sources.
- Extensible for future transcription providers.
- No database requirement.
- No GUI requirement.

## Explicit Non-Goals for v0.1

- Summarization.
- Viewpoint extraction.
- AI note generation.
- URL ingestion.
- System audio capture.
- Desktop GUI.
- DRM bypassing.
- Public subtitle redistribution workflow.

## Future Requirements

- URL input.
- System audio capture.
- Windows desktop GUI.
- External transcription API integration.
- Transcript search and indexing.
- Optional subtitle export.
