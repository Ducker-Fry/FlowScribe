# Architecture

FlowScribe is designed around a pipeline architecture with high cohesion and low coupling. Each module owns one responsibility and communicates through stable domain objects instead of direct implementation dependencies.

## Architectural Goals

- Extensible input sources.
- Swappable transcription engines.
- Independent output writers.
- Batch-friendly execution.
- Clear boundaries for future GUI and API layers.
- Local-first behavior by default.

## Pipeline Overview

```text
Input Source
    -> Media Preparation
    -> Transcription
    -> Transcript Assembly
    -> Output Writing
```

## Module Responsibilities

### CLI Layer

The CLI parses user commands, loads configuration, and starts jobs. It should not contain business logic.

### Core Layer

The core layer coordinates jobs and defines shared domain models such as media items, transcript segments, job results, and errors.

### Input Layer

The input layer discovers media sources. In v0.1 this means local files and folders. Future adapters may support URLs and system audio recordings.

### Media Layer

The media layer validates files, probes metadata, and prepares audio for transcription. It hides media tooling details from the rest of the application.

### Transcription Layer

The transcription layer converts prepared audio into transcript segments. It should expose a provider interface so local models and external APIs can coexist later.

### Output Layer

The output layer writes transcripts to TXT, Markdown, and future formats. It should not know how media was acquired or transcribed.

### Config Layer

The config layer manages defaults, model choices, output paths, and future provider settings.

## Extension Points

### New Input Source

Add a new adapter under `input/` that returns the same media item model used by local files.

Examples:

- URL input.
- Browser download handoff.
- System audio capture.
- Application audio recording.

### New Transcription Provider

Add a provider under `transcription/` that implements the shared transcriber interface.

Examples:

- Local faster-whisper provider.
- OpenAI API provider.
- Other cloud speech-to-text provider.

### New Output Format

Add a writer under `output/` that accepts transcript data and writes a new artifact.

Examples:

- SRT.
- VTT.
- JSON.
- DOCX.

## Dependency Direction

Dependencies should point inward:

```text
CLI -> Core -> Input / Media / Transcription / Output
```

Implementation modules should depend on shared interfaces and data models, not on each other directly.

## Non-Goals

- Do not bypass DRM or protected media controls.
- Do not build summary or opinion extraction into the transcription core.
- Do not make GUI code depend directly on low-level media or transcription implementations.
- Do not require a database for the first version.
