# Server Configuration

`flowscribe serve` starts an HTTP server for two kinds of clients:

- human/browser tools such as the bookmarklet queue
- agent / automation clients using `/v1/tasks`

It can run on the same Windows workstation as the GUI, or on a separate remote
host that receives jobs from CLI or GUI clients over HTTP.

## Basic Usage

Start the server with defaults:

```powershell
flowscribe serve
```

Default behavior:

- host: `127.0.0.1`
- port: `8765`
- output directory: `~/Documents/FlowScribe`
- output formats: `json`
- model: `small`
- language: auto-detect
- queue store: `batch-queue.json`
- agent task store: `agent-tasks.json` in the same directory as the queue store

For an end-to-end remote deployment walkthrough, see
[remote-server-guide.md](remote-server-guide.md) and
[remote-server-guide-en.md](remote-server-guide-en.md).

## Common Configuration

### Output directory

```powershell
flowscribe serve -o E:\Transcripts
```

### Output formats

Single format:

```powershell
flowscribe serve --format json
```

Multiple formats:

```powershell
flowscribe serve --format txt,md,json,srt
```

### Model

```powershell
flowscribe serve -m medium
```

### Language

Chinese:

```powershell
flowscribe serve -l zh
```

English:

```powershell
flowscribe serve -l en
```

Auto-detect:

```powershell
flowscribe serve
```

### Combined example

```powershell
flowscribe serve `
  -o E:\Transcripts `
  --format txt,md,json,srt `
  -m medium `
  -l zh `
  --port 9000
```

## Startup Output

On startup, FlowScribe prints:

- listening address
- queue store path
- agent task store path
- default output settings
- bookmarklet endpoints
- agent task endpoints
- task persistence behavior

Example:

```text
======================================================================
FlowScribe Server
======================================================================
Listening on: http://127.0.0.1:8765
Queue store:  C:\Users\...\AppData\Local\FlowScribe\batch-queue.json
Task store:   C:\Users\...\AppData\Local\FlowScribe\agent-tasks.json

Default Settings:
  Output dir:  E:\Videos\Transcripts
  Formats:     txt, srt
  Model:       small
  Language:    zh

Bookmarklet Endpoints:
  POST http://127.0.0.1:8765/add-url     - Add single URL to queue
  POST http://127.0.0.1:8765/add-urls    - Add multiple URLs to queue
  GET  http://127.0.0.1:8765/status      - Get queue status

Agent Task API:
  POST http://127.0.0.1:8765/v1/tasks                - Submit single task
  GET  http://127.0.0.1:8765/v1/tasks/{task_id}      - Get task status
  GET  http://127.0.0.1:8765/v1/tasks/{task_id}/events - Stream task events
  GET  http://127.0.0.1:8765/v1/tasks/{task_id}/result - Get final result

Task Persistence:
  Agent task history is stored in agent-tasks.json next to the queue store.
  Completed, failed, and canceled tasks remain queryable after server restart.
  Accepted or running tasks interrupted by restart are recovered as failed.

Status reports will be shown every 30 seconds
Press Ctrl+C to stop
======================================================================
```

## Endpoints

### Bookmarklet / queue endpoints

- `POST /add-url`
- `POST /add-urls`
- `GET /status`
- `GET /bookmarklet.js`

These are intended for:

- browser bookmarklets
- manual queue workflows
- lightweight URL collection

### Agent task endpoints

- `POST /v1/tasks`
- `GET /v1/tasks/{task_id}`
- `GET /v1/tasks/{task_id}/events`
- `GET /v1/tasks/{task_id}/result`

These are intended for:

- AI agents
- local orchestrators
- workflow engines
- RAG ingestion pipelines

For request/response shapes, see [Agent API Guide](agent-api.md).

## Operational Notes For Remote Hosts

FlowScribe now keeps the HTTP control plane responsive during long-running jobs:

- request handling uses a threaded HTTP server so `status`, `events`, and
  `result` requests can still be served while another task is transcribing
- heavy remote transcription is still limited to one active task by default, so
  small hosts do not accept multiple memory-heavy jobs at once
- when the active-task limit is reached, `POST /v1/tasks` returns HTTP `429`

This default is especially helpful on low-memory servers where one model load
or URL download can otherwise starve the whole machine.

## Artifact Staging For Remote Clients

When a client submits a remote job and requests artifact download, the server
stores result files in a server-managed staging directory first, then exposes
them through `/v1/artifacts/{artifact_id}` for client download.

That behavior avoids leaking a client-local path such as `E:\Temp` into a
Linux server filesystem and keeps remote outputs under server-controlled
directories.

## Sizing Guidance

Suggested starting points:

- `tiny` for very small Linux hosts or smoke tests
- `small` for everyday remote use when the host has enough RAM and patience for
  longer runs
- keep one active remote task at a time on 2 GB machines
- if you need login-required URL access, store a valid Netscape-format
  `cookies.txt` on the server and reference it from the remote server profile

The broader reason for this sizing model is client/server role separation:

- let the client machine stay responsive for normal work
- match the remote model size to the actual server hardware
- allow very small servers to participate with `tiny` first, instead of forcing
  every node to run a larger default model

## Task Persistence And Recovery

FlowScribe persists `/v1/tasks` state to a local JSON file:

- queue file: `batch-queue.json`
- agent task file: `agent-tasks.json`

By default, both live under the same application data directory. If you pass a
custom `--queue-store`, FlowScribe places `agent-tasks.json` next to that file.

Persistence behavior:

- completed tasks remain queryable after restart
- failed tasks remain queryable after restart
- canceled tasks remain queryable after restart
- accepted or running tasks that were interrupted by restart are recovered as
  `failed`

This makes `/v1/tasks` suitable for local workstation workflows and restart-safe
inspection, while still keeping the implementation lightweight.

## Validation Tips

Check the queue endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/status | Select-Object -ExpandProperty Content
```

Submit a simple local task:

```powershell
$body = @{
  task_id = "demo-001"
  source = @{
    kind = "local"
    value = "D:\media\lecture.mp4"
  }
  output = @{
    output_dir = "outputs"
    formats = @("json")
  }
} | ConvertTo-Json -Depth 5

Invoke-WebRequest `
  -Uri http://127.0.0.1:8765/v1/tasks `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

## Configuration Precedence

Priority order:

1. command-line flags
2. built-in defaults

These defaults apply to tasks submitted through the local server when the
request does not override them.

## Notes

1. The output directory is created automatically if needed.
2. Supported output formats remain `txt`, `md`, `json`, `srt`, and `vtt`.
3. The model may be downloaded on first use, depending on provider/runtime.
4. Language codes use ISO 639-1 style values such as `zh`, `en`, `ja`, `ko`.
5. The queue/bookmarklet APIs and `/v1/tasks` serve different workflows and can
   coexist on the same local server.
