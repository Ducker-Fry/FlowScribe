# Roadmap

## v0.1 Local File CLI

Goal: prove the core pipeline works for local media.

- Project scaffold.
- Local file input.
- Audio preparation.
- Local transcription provider.
- TXT and Markdown output.
- Basic batch processing.
- README usage instructions.

Status: completed.

## v0.2 URL Transcription, Search, And Release Automation

Goal: turn FlowScribe from a local-file CLI into a URL-capable transcript
processing tool with structured outputs and automated releases.

- URL input through `flowscribe url`.
- Local and URL source inspection through `flowscribe inspect`.
- TXT, Markdown, JSON, SRT, and VTT outputs.
- Word timing data and Chinese natural-word alignment.
- Keyword search and timestamp location through `flowscribe search`.
- URL safety limits, cookies, proxy, and IPv4/IPv6 controls.
- Stable `TranscriptionService` interface for CLI and future GUI.
- GitHub Actions release automation for Windows portable builds.

Status: completed in `v0.2.2`.

## v0.3 Desktop GUI And Interactive Transcript Workflow

Goal: make FlowScribe usable by non-technical users and introduce transcript
navigation.

- Desktop GUI shell.
- Drag-and-drop local files.
- Paste URL field.
- Job list and progress.
- User-friendly errors.
- Transcript JSON viewer.
- Keyword search UI.
- Segment-level media seek.
- GUI packaging in Windows releases.

## v0.4 System Audio Capture

Goal: support media played in browsers or Windows applications through user-controlled audio recording.

- System audio capture prototype.
- Save captured audio as an input artifact.
- Transcribe captured audio through the existing pipeline.

## v0.5 Transcript Library And External Providers

Goal: make repeated use more convenient and prepare optional higher-accuracy
provider integrations.

- Local transcript library.
- Job history.
- Saved user preferences.
- Optional external speech-to-text provider interface.
- Provider selection and cost/latency documentation.

## v1.0 Open Source Release

Goal: polish the project as a public portfolio-quality tool.

- Stable CLI and GUI workflows.
- Clean release artifacts.
- Complete user documentation.
- Demo media workflows.
- Maintainer documentation.
- Clear legal and ethical boundaries.
