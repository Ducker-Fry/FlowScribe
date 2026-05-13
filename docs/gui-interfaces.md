# GUI Interface Preparation

This document describes the stable application-facing interfaces that should be
used before building a desktop GUI. The goal is to keep future UI code away from
low-level media, URL, transcription, and output implementation details.

## Design Rule

The GUI should call the application layer:

```text
GUI
  -> TranscriptionJob
  -> TranscriptionService.run(...)
  -> ProgressEvent callbacks
  -> TranscriptionResult
```

It should not directly instantiate `FfmpegAudioExtractor`,
`LocalWhisperTranscriber`, `UrlAudioDownloader`, or output writers.

## Stable Models

The app-facing models live in:

```text
src/flowscribe/app/models.py
```

### `SourceSpec`

Represents one source selected by the user.

```python
SourceSpec(kind="local", value="D:/media/lecture.mp4")
SourceSpec(kind="url", value="https://example.com/video", keep_media=False)
SourceSpec(kind="capture", value="system")
```

Supported source kinds:

```text
local    implemented
url      implemented
capture  reserved, not implemented yet
```

### `TranscriptionJob`

Represents a complete transcription request.

Important fields:

```text
sources
output_dir
work_dir
model_name
language
preset
task
beam_size
vad_filter / no_vad_filter
initial_prompt
timestamps
word_timestamps
output_formats
overwrite
keep_audio
max_download_mb
max_duration_seconds
download_timeout_seconds
network_family
```

This object is the main boundary between UI state and backend execution.

### `ProgressEvent`

Structured progress callback event.

Stages:

```text
discover
download
prepare
transcribe
write
complete
error
```

The GUI can map these stages to progress bars, status labels, logs, or task cards.

### `ErrorInfo`

Structured error object for user-facing display.

```text
code
message
source
recoverable
```

The GUI should display `message`, use `source` to highlight the failed item, and
use `recoverable` to decide whether the batch can continue.

### `TranscriptionResult`

Final response object.

```text
outputs
errors
succeeded
failed
ok
started_at
finished_at
```

The GUI should use `outputs` to populate result lists and `errors` to show failed
items without losing successful work.

## Service

The app service lives in:

```text
src/flowscribe/app/service.py
```

Example:

```python
from pathlib import Path

from flowscribe.app.models import SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService


job = TranscriptionJob(
    sources=(SourceSpec(kind="local", value="D:/media/lecture.mp4"),),
    output_dir=Path("outputs"),
    model_name="small",
    language="zh",
    preset="zh",
    output_formats=("txt", "md", "json"),
)


def on_progress(event):
    print(event.stage, event.message)


result = TranscriptionService().run(job, progress=on_progress)
```

## JSON Schema

Transcript JSON remains the core intermediate format for GUI, search, and future
AI analysis layers.

Schema versions live in:

```text
src/flowscribe/app/schema.py
```

Current versions:

```text
TRANSCRIPT_JSON_SCHEMA_VERSION = 1.1
INSPECTION_JSON_SCHEMA_VERSION = 1.0
```

Rules:

- Add fields in a backward-compatible way whenever possible.
- Keep `schema_version`, `segments`, `text`, `start_seconds`, and `end_seconds`.
- Preserve `raw_words` for provider timing units.
- Preserve `words` for user-facing natural word timing.
- Do not make GUI code parse TXT, Markdown, SRT, or VTT as its primary data source.

## Source Abstraction

The GUI should treat every user input as a `SourceSpec`.

```text
local file/folder -> SourceSpec(kind="local")
public URL        -> SourceSpec(kind="url")
system capture    -> SourceSpec(kind="capture")
```

`capture` is intentionally reserved so the future GUI can add system-audio capture
without changing the job contract.

## CLI Integration

The CLI local and URL transcription paths now create `TranscriptionJob` objects
and execute them through `TranscriptionService`. This means the CLI and future GUI
share the same execution path for the most important transcription workflows.

The CLI still owns command parsing, terminal formatting, `doctor`, `inspect`,
`search`, and simple informational commands.

## Next GUI-Oriented Steps

Before building the first desktop window:

1. Add cancellation support to `ProgressCallback` or a job controller.
2. Add persistent job history only after the basic GUI workflow is stable.
3. Add GUI-safe validation before execution.
4. Keep all GUI state serializable into `TranscriptionJob`.
5. Decide whether `inspect` should also move into an app-facing service.
