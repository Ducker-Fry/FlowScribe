# Architecture

FlowScribe uses a small pipeline architecture with high cohesion and low coupling. The CLI wires concrete adapters together, while the core layer defines the domain models and interfaces that keep input, media processing, transcription, and output independent.

## Current v0.1 Pipeline

```text
CLI
  -> AppSettings
  -> LocalFileSource
  -> LocalTranscriptionPipeline
       -> FfmpegAudioExtractor
       -> LocalWhisperTranscriber
       -> TranscriptArtifactWriter
            -> TxtTranscriptWriter
            -> MarkdownTranscriptWriter
  -> JobResult
```

The user-facing behavior is:

```text
local file/folder
  -> discover supported media files
  -> detect audio stream with ffprobe
  -> extract 16 kHz mono WAV with ffmpeg
  -> transcribe with faster-whisper
  -> write TXT and Markdown transcripts
```

## Code Modules

### `src/flowscribe/cli`

- `main.py`: application entry point. It parses options, creates settings, wires adapters, and runs the job.
- `args.py`: command-line option definitions and `CliOptions`.

The CLI should remain thin. It should not contain transcription, media, or output formatting logic.

### `src/flowscribe/config`

- `settings.py`: runtime settings and preset resolution.

The Chinese preset is resolved here so provider-specific code does not need to know how CLI presets are interpreted.

### `src/flowscribe/core`

- `models.py`: domain objects such as `MediaItem`, `PreparedAudio`, `Transcript`, `TranscriptionOptions`, and `JobResult`.
- `ports.py`: protocol interfaces for input sources, media preparers, transcribers, and writers.
- `pipeline.py`: single-item transcription pipeline.
- `runner.py`: batch orchestration and recoverable item-level failures.
- `errors.py`: project-specific exceptions.

The core layer owns the application vocabulary. Concrete adapters should depend on core models and ports, not on each other.

### `src/flowscribe/input`

- `file_filter.py`: supported media extension detection.
- `local_source.py`: local file and folder discovery.

Future URL input and system audio capture should be added as new input adapters rather than changing the core pipeline.

### `src/flowscribe/media`

- `ffmpeg_probe.py`: audio stream detection through `ffprobe`.
- `audio_extractor.py`: transcription-ready WAV preparation through `ffmpeg`.

This layer hides media tooling details from the transcription layer.

### `src/flowscribe/transcription`

- `local_whisper.py`: local faster-whisper provider.

The provider accepts model, language, task, beam size, VAD, prompt, and preset metadata. Future providers such as WhisperX, FunASR, SenseVoice, or external APIs should implement the same transcriber role.

### `src/flowscribe/output`

- `paths.py`: safe output path generation.
- `txt_writer.py`: raw text output.
- `md_writer.py`: Markdown output with metadata.
- `artifact_writer.py`: writes all v0.1 artifacts for one transcript.

Output writers should not know how input was discovered or how transcription was performed.

## Dependency Direction

```text
CLI -> Config
CLI -> Core
CLI -> Concrete adapters
Concrete adapters -> Core models / ports
Concrete adapters -> External tools or libraries
```

The intended rule is:

- Core does not import CLI.
- Core does not import concrete adapters.
- Input, media, transcription, and output modules do not depend on each other directly unless they have a narrow local helper relationship.
- New capabilities should be added by introducing new adapters that satisfy existing core interfaces.

## Extension Points

### New Input Source

Add a new adapter under `src/flowscribe/input`.

Examples:

- URL input.
- Browser handoff.
- System audio recording.
- Application audio capture through user-controlled system audio.

The adapter should return `MediaItem` or a future source model without changing output writers or transcription providers.

### New Transcription Provider

Add a provider under `src/flowscribe/transcription`.

Examples:

- WhisperX provider.
- FunASR/SenseVoice provider for stronger Chinese recognition.
- OpenAI or other cloud speech-to-text API provider.

The provider should return `Transcript` and record relevant `TranscriptionOptions`.

### New Output Format

Add a writer under `src/flowscribe/output`.

Examples:

- SRT.
- VTT.
- JSON.
- DOCX.

The writer should consume `Transcript` only.

## Non-Goals

- Do not bypass DRM or protected media controls.
- Do not build summary or opinion extraction into the transcription core.
- Do not make future GUI code depend directly on low-level media or transcription implementations.
- Do not require a database for the first local-file CLI version.
