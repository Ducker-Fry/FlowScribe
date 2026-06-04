# FlowScribe Agent API Guide

FlowScribe now exposes a small agent-friendly surface for automation, RAG
pipelines, and workflow tools.

This guide focuses on:

- non-interactive CLI usage
- structured JSON / JSONL output
- single-task HTTP submission
- the `MediaDocument` JSON artifact

Use this document when integrating FlowScribe into an agent, queue worker, or
knowledge ingestion pipeline.

## Overview

FlowScribe exposes the same task model across CLI and HTTP:

- input: `SourceSpec`-style source description
- execution: one `TranscriptionJob`
- progress: ordered `ProgressEvent` objects
- result: one `TranscriptionResult`
- artifact: one canonical JSON `MediaDocument`

Current v1 scope:

- single task submit / status / events / result
- local file and public URL sources
- CLI JSON result output
- CLI JSONL event output
- HTTP SSE event output
- stable `task_id`, `resume_token`, `checkpoint_id`, `cache_key`

## CLI For Agents

### Structured result output

Use `--json` for a final machine-readable result object:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" `
  --format json `
  --json `
  --non-interactive `
  --task-id lecture-001
```

For URL media:

```powershell
flowscribe url "https://example.com/video" `
  --format json `
  --json `
  --non-interactive `
  --task-id remote-001
```

Result shape:

```json
{
  "ok": true,
  "canceled": false,
  "succeeded": 1,
  "failed": 0,
  "elapsed_seconds": 12.3,
  "tasks": [
    {
      "task_id": "lecture-001",
      "resume_token": null,
      "checkpoint_id": null,
      "cache_key": "v0_...",
      "source": {
        "kind": "local",
        "value": "D:\\media\\lecture.mp4",
        "locator": "D:\\media\\lecture.mp4"
      }
    }
  ],
  "outputs": [
    {
      "paths": ["outputs\\lecture.json"],
      "json_path": "outputs\\lecture.json",
      "media_path": null,
      "media_kind": null,
      "requested_media_kind": null,
      "source_kind": null,
      "source_value": null,
      "transcription_strategy": null,
      "subtitle_language": null
    }
  ],
  "errors": []
}
```

### Streaming progress events

Use `--events jsonl` for structured progress streaming on stdout:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" `
  --format json `
  --events jsonl `
  --non-interactive `
  --task-id lecture-001
```

Each line is one JSON object:

```json
{"event_type":"task.accepted","timestamp":"2026-06-04T10:00:00.000Z","sequence":1,"task_id":"lecture-001","stage":"discover","message":"Received 1 source(s).","source":null}
{"event_type":"task.started","timestamp":"2026-06-04T10:00:01.000Z","sequence":2,"task_id":"lecture-001","stage":"discover","message":"Discovered 1 media file(s).","source":"D:\\media\\lecture.mp4"}
{"event_type":"artifact.written","timestamp":"2026-06-04T10:00:12.000Z","sequence":8,"task_id":"lecture-001","stage":"write","message":"Wrote: outputs\\lecture.json","path":"outputs\\lecture.json"}
{"event_type":"task.completed","timestamp":"2026-06-04T10:00:12.100Z","sequence":9,"task_id":"lecture-001","stage":"complete","message":"Done. Succeeded: 1. Failed: 0."}
```

### Resume-aware flags

Agent workflows can explicitly set:

- `--task-id`
- `--resume-token`
- `--checkpoint-id`

Example:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" `
  --format json `
  --json `
  --non-interactive `
  --task-id lecture-001 `
  --resume-token lecture-001 `
  --checkpoint-id lecture-001 `
  --resume
```

## CLI Exit Codes

FlowScribe uses fixed automation-oriented exit codes:

- `0`: success
- `10`: partial success
- `20`: input error
- `30`: source/download/media access error
- `40`: environment/output dependency error
- `50`: runtime/transcription error
- `60`: resumable interruption
- `70`: canceled

## HTTP Task API

Start the local server:

```powershell
flowscribe serve
```

Current task endpoints:

- `POST /v1/tasks`
- `GET /v1/tasks/{task_id}`
- `GET /v1/tasks/{task_id}/events`
- `GET /v1/tasks/{task_id}/result`

### Submit a task

Local file example:

```http
POST /v1/tasks
Content-Type: application/json

{
  "task_id": "lecture-001",
  "source": {
    "kind": "local",
    "value": "D:\\media\\lecture.mp4"
  },
  "output": {
    "output_dir": "outputs",
    "formats": ["json"],
    "overwrite": false
  },
  "provider_name": "local-whisper",
  "model_name": "small",
  "language": "zh",
  "timestamps": true,
  "word_timestamps": true,
  "progressive": true,
  "progressive_resume": true,
  "resume_token": "lecture-001",
  "checkpoint_id": "lecture-001"
}
```

URL example:

```http
POST /v1/tasks
Content-Type: application/json

{
  "task_id": "remote-001",
  "source": {
    "kind": "url",
    "value": "https://example.com/video"
  },
  "output": {
    "output_dir": "outputs",
    "formats": ["json"]
  },
  "provider_name": "local-whisper",
  "model_name": "small"
}
```

Accepted response:

```json
{
  "task_id": "lecture-001",
  "status": "accepted",
  "created_at": "2026-06-04T10:00:00.000Z",
  "updated_at": null,
  "resume_token": "lecture-001",
  "checkpoint_id": "lecture-001",
  "cache_key": "v0_...",
  "document_path": null,
  "result_available": false
}
```

### Poll task status

```http
GET /v1/tasks/lecture-001
```

Response:

```json
{
  "task_id": "lecture-001",
  "status": "completed",
  "created_at": "2026-06-04T10:00:00.000Z",
  "updated_at": "2026-06-04T10:00:12.100Z",
  "resume_token": "lecture-001",
  "checkpoint_id": "lecture-001",
  "cache_key": "v0_...",
  "document_path": "outputs\\lecture.json",
  "result_available": true
}
```

Status values currently used:

- `accepted`
- `running`
- `completed`
- `failed`
- `canceled`

### Stream events with SSE

```http
GET /v1/tasks/lecture-001/events
Accept: text/event-stream
```

Response body:

```text
data: {"event_type":"task.accepted","timestamp":"2026-06-04T10:00:00.000Z","sequence":1,"task_id":"lecture-001","stage":"discover","message":"Received 1 source(s).","source":null}

data: {"event_type":"task.started","timestamp":"2026-06-04T10:00:01.000Z","sequence":2,"task_id":"lecture-001","stage":"discover","message":"Discovered 1 media file(s).","source":"D:\\media\\lecture.mp4"}
```

### Fetch final result

```http
GET /v1/tasks/lecture-001/result
```

This returns the same structured result shape as CLI `--json`.

## Progress Event Contract

The event envelope keeps existing `ProgressEvent` semantics and adds:

- `event_type`
- `timestamp`
- `sequence`
- `task_id`

Common `event_type` values:

- `task.accepted`
- `task.started`
- `progress`
- `artifact.written`
- `task.completed`
- `task.failed`
- `task.canceled`

Useful fields for automation:

- `stage`
- `message`
- `source`
- `path`
- `processed_duration_seconds`
- `total_duration_seconds`
- `eta_seconds`
- `realtime_factor`
- `chunk_index`
- `chunk_count`
- `completed_chunks`
- `failed_chunks`

## MediaDocument JSON

The canonical JSON artifact remains the normal `*.json` transcript file, but it
now includes agent/RAG-oriented fields while preserving legacy compatibility.

Top-level fields include:

- `schema_version`
- `document_id`
- `task_id`
- `source`
- `source_info`
- `provenance`
- `language`
- `provider`
- `model`
- `text`
- `segments`
- `chunks`
- `artifacts`
- `media_binding`
- `resume`
- `metadata`

### Compatibility

Legacy consumers can continue reading:

- `source`
- `text`
- `segments`
- `start_seconds`
- `end_seconds`
- `words`
- `raw_words`

Preferred fields for new consumers:

- `document_id`
- `task_id`
- `chunks`
- `artifacts`
- `provenance`
- `resume`

### `chunks` for RAG

Each chunk is a stable, traceable unit:

```json
{
  "chunk_id": "4cf5...",
  "index": 1,
  "text": "Hello world.",
  "start_seconds": 0.0,
  "end_seconds": 1.5,
  "segment_ids": ["seg-0001"],
  "segment_indexes": [1]
}
```

RAG guidance:

- use `chunk_id` as the primary external key
- store `document_id` alongside each embedding row
- keep `start_seconds` / `end_seconds` for playback and citation
- keep `segment_ids` for precise traceability back to source transcript units

## Recommended Integration Patterns

### Pattern 1: CLI worker

Best for:

- local batch jobs
- cron/scheduled tasks
- existing shell-based automation

Recommended contract:

1. call CLI with `--events jsonl --non-interactive`
2. capture stdout as event stream
3. if needed, call again with `--json` for final summary
4. ingest the produced `MediaDocument` JSON into downstream RAG/indexing steps

### Pattern 2: Local HTTP orchestrator

Best for:

- editor plugins
- desktop assistants
- agent runtimes that prefer HTTP over subprocesses

Recommended contract:

1. `POST /v1/tasks`
2. subscribe to `/events`
3. poll `/result` or `/status`
4. ingest `document_path`

## Current Limits

Current v1 limits:

- single-task API only
- JSON-backed local task registry
- task history persists across server restarts on the same machine
- tasks interrupted by server restart are recovered as failed
- batch submission is not yet a first-class API
- advanced semantic chunking is not yet configurable

If you need multi-machine or multi-process orchestration, use FlowScribe as a
local worker behind your own queue and persist higher-level workflow state in
your orchestration layer.
