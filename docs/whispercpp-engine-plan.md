# Whisper.cpp Engine Plan

## Goal

Build a local persistent transcription engine for FlowScribe that keeps the
speech model loaded across multiple CLI transcription tasks, reduces repeated
startup cost, and creates a clean path for later throughput tuning on long
Chinese media.

This plan intentionally targets the current product shape:

- Windows-first
- local-first
- CLI integration first
- `whisper.cpp` as the native inference backend
- Windows Named Pipe as the local IPC mechanism

The Python application remains the orchestration layer for source discovery,
URL download, FFmpeg-based audio preparation, output writing, and most user
facing workflow logic. The native engine owns model lifetime, job execution,
chunk scheduling, cancellation, and progress streaming.

## Why This Exists

Current FlowScribe performance work is constrained by more than one factor:

- repeated model initialization across runs
- conservative progressive execution
- Python-side orchestration around a non-persistent provider instance
- Chinese workflow needs that benefit from stronger throughput-oriented tuning

Moving to a native persistent engine is not a blanket "rewrite Python in C++"
exercise. The point is to move the performance-critical runtime boundary to a
long-lived native process while preserving the existing Python product surface.

## Scope

### In Scope

- persistent local engine process
- `whisper.cpp` inference backend
- model preload and reuse
- CLI-first provider integration
- Named Pipe request and event transport
- whole-file transcription in `v0`
- chunked progressive scheduling in `v1`
- cancellation at least on chunk boundaries
- job and chunk level progress events
- engine-side chunk cache groundwork

### Out Of Scope For Initial Work

- GUI integration
- URL download inside the engine
- FFmpeg replacement
- transcript library changes
- transcript editing changes
- distributed or remote service deployment
- replacing all Python-side pipeline logic

## Target Architecture

```text
FlowScribe CLI
  -> Python provider adapter
  -> EngineProcessManager
  -> Windows Named Pipe
  -> flowscribe-engine.exe
  -> whisper.cpp runtime
  -> transcript JSON
  -> existing FlowScribe artifact writers
```

Python remains responsible for:

- parsing CLI options
- source discovery
- URL handling
- cookies and proxy handling
- FFmpeg audio extraction to WAV
- output artifact writing
- existing transcript post-processing integration

The native engine is responsible for:

- loading and holding models in memory
- receiving prepared audio jobs
- scheduling work
- managing worker threads
- reporting progress
- returning transcript payloads
- handling cancellation

## Repository Layout

Recommended layout:

```text
native/
  flowscribe-engine/
    CMakeLists.txt
    README.md
    third_party/
      whisper.cpp/
    include/flowscribe/engine/
      protocol/
        message.h
        codec.h
      ipc/
        named_pipe_server.h
        named_pipe_connection.h
      core/
        engine_service.h
        model_manager.h
        job_manager.h
        scheduler.h
        worker_pool.h
        event_bus.h
      transcription/
        whisper_runtime.h
        chunk_planner.h
        transcript_assembler.h
      cache/
        cache_store.h
      util/
        stopwatch.h
        hashing.h
        paths.h
    src/
      main.cpp
      protocol/
        codec.cpp
      ipc/
        named_pipe_server.cpp
        named_pipe_connection.cpp
      core/
        engine_service.cpp
        model_manager.cpp
        job_manager.cpp
        scheduler.cpp
        worker_pool.cpp
        event_bus.cpp
      transcription/
        whisper_runtime.cpp
        chunk_planner.cpp
        transcript_assembler.cpp
      cache/
        cache_store.cpp
    tests/
      protocol_tests.cpp
      planner_tests.cpp
      assembler_tests.cpp
      cache_tests.cpp

src/flowscribe/
  engine/
    __init__.py
    protocol.py
    models.py
    pipe_client.py
    process_manager.py
    client.py
    transcriber.py
```

## IPC Choice

The selected IPC transport is Windows Named Pipe.

Reasoning:

- local-only by design
- better fit than HTTP or gRPC for a desktop-local workflow
- lower surface area than a network API
- can evolve into a packaged product dependency cleanly

The pipe should be duplex and framed. Do not rely on line-based parsing.

Recommended pipe name pattern:

```text
\\.\pipe\flowscribe-engine-v1
```

For parallel CLI runs later, allow a unique suffix:

```text
\\.\pipe\flowscribe-engine-v1-<pid>-<nonce>
```

## Protocol Shape

Use framed binary messages with a JSON body.

Suggested frame:

- 4 bytes payload length
- 2 bytes protocol version
- 2 bytes message kind
- payload bytes

The first version should support these commands:

- `hello`
- `load_model`
- `submit_job`
- `cancel_job`
- `shutdown`

And these event or result messages:

- `hello_result`
- `load_model_result`
- `submit_job_result`
- `job_event`
- `job_result`
- `job_error`

## Core Engine Data Model

Suggested native request structures:

```text
EngineOptions
ProgressiveOptions
JobRequest
ChunkTask
ChunkResult
JobState
```

Key fields:

- model name
- language
- beam size
- VAD toggle
- word timestamps toggle
- prompt text
- chunk duration
- overlap duration
- max workers
- resume toggle
- prepared WAV path
- audio duration metadata

The engine should consume prepared WAV input, not raw media files. This keeps
FFmpeg and source complexity on the Python side.

## C++ Component Plan

### `ipc::NamedPipeServer`

Responsibilities:

- create and own the server pipe
- accept client connection
- create per-connection objects

### `ipc::NamedPipeConnection`

Responsibilities:

- blocking framed read
- framed write
- shutdown and cleanup

### `core::EngineService`

Responsibilities:

- top-level command handler
- command routing
- dependency wiring
- request validation

Holds:

- `ModelManager`
- `JobManager`
- `Scheduler`
- `EventBus`

### `core::ModelManager`

Responsibilities:

- lazy or explicit model load
- runtime reuse keyed by model configuration
- preload support

Important note:

Do not assume one mutable `whisper.cpp` runtime context is safely shared across
multiple worker threads. For `v0`, use a single runtime. For `v1`, prefer one
runtime instance per worker or another concurrency model proven safe by
benchmark and runtime validation.

### `core::JobManager`

Responsibilities:

- create job records
- track lifecycle
- hold cancel flags
- expose lookup by `job_id`

### `core::WorkerPool`

Responsibilities:

- own worker threads
- receive tasks from the scheduler
- execute chunk transcription

The first version can use:

- `std::thread`
- `std::mutex`
- `std::condition_variable`
- `std::deque`

No lock-free queue is required initially.

### `core::Scheduler`

Responsibilities:

- expand a job into chunk tasks
- enqueue tasks
- receive worker results
- forward events
- hand results to the assembler

### `transcription::ChunkPlanner`

Responsibilities:

- compute chunk boundaries
- apply overlap
- mirror current FlowScribe chunk semantics where practical

### `transcription::TranscriptAssembler`

Responsibilities:

- offset chunk-local timestamps into global time
- assemble transcript in source order
- support simple overlap trimming first

For `v0`, whole-file transcription is acceptable. For `v1`, this becomes a
required component.

### `transcription::WhisperRuntime`

Responsibilities:

- wrap `whisper.cpp`
- model initialization
- whole-file transcription
- clip-range transcription
- transcript serialization into engine JSON shape

### `cache::CacheStore`

Responsibilities:

- cache key generation
- chunk result persistence
- partial transcript persistence
- resume metadata

Cache can be postponed in `v0` and implemented in `v1`.

## Python Integration Plan

Python should integrate the engine through a new provider, not by replacing the
whole pipeline.

### New Python Modules

`src/flowscribe/engine/protocol.py`

- Python message codec
- protocol constants

`src/flowscribe/engine/models.py`

- request and response dataclasses

`src/flowscribe/engine/pipe_client.py`

- connect to Named Pipe
- send framed messages
- receive framed messages

`src/flowscribe/engine/process_manager.py`

- launch `flowscribe-engine.exe`
- wait for pipe readiness
- run `hello`
- shutdown engine

`src/flowscribe/engine/client.py`

- high-level methods:
  - `hello()`
  - `load_model()`
  - `submit_job()`
  - `cancel_job()`
  - `wait_for_result()`

`src/flowscribe/engine/transcriber.py`

- implement current `Transcriber` protocol
- map engine transcript JSON back into `Transcript`

### Provider Strategy

Add a new provider branch under:

- `src/flowscribe/transcription/providers.py`

Suggested provider name:

- `whispercpp-engine`

This keeps `LocalTranscriptionPipeline` and `TranscriptionService` largely
stable while allowing CLI selection of the new engine-backed path.

## Milestones

### `v0` Persistent Single-Worker CLI Prototype

Target:

- engine process starts
- Named Pipe command path works
- one model loads and stays alive
- one WAV file transcribes successfully
- Python CLI receives transcript and writes artifacts

Included work:

- `hello`
- `load_model`
- `submit_job`
- `job_result`
- Python process manager
- Python pipe client
- Python engine-backed transcriber
- provider registration

Excluded work:

- chunked progressive scheduling
- worker pool parallelism
- engine-side resume cache
- GUI integration

Success criteria:

- multiple files in one CLI run reuse one loaded model
- transcript output is stable enough for development use
- engine crashes return actionable Python-side errors

### `v1` Progressive Worker-Pool CLI Engine

Target:

- chunked long-audio execution
- worker pool scheduling
- chunk-level progress events
- chunk-boundary cancellation
- basic chunk cache and resume metadata

Included work:

- chunk planner
- scheduler
- worker pool
- transcript assembler
- `job_event`
- `cancel_job`
- basic cache store
- Python progress event mapping

Success criteria:

- long audio runs can report ETA and chunk progress
- same CLI session can process multiple files without repeated model load
- benchmark data shows reduced startup overhead and better long-run throughput

## Development Order

Recommended implementation order:

1. create native engine project skeleton
2. wire `whisper.cpp` build
3. implement framed codec
4. implement Named Pipe server and one duplex connection
5. implement `hello`
6. implement `load_model`
7. implement whole-file `submit_job`
8. build Python process manager and pipe client
9. implement Python engine-backed transcriber
10. register provider and run from CLI
11. add chunk planner
12. add worker pool
13. add scheduler and progress events
14. add cancellation
15. add cache and resume support

## Immediate Work Queue

The next concrete development tasks are:

1. scaffold `native/flowscribe-engine`
2. vendor or submodule `whisper.cpp`
3. define protocol message schema in both C++ and Python
4. implement engine startup and `hello`
5. implement model preload for one model
6. implement whole-file WAV transcription
7. add Python CLI path for `--provider whispercpp-engine`

## Risks And Watch Items

- `whisper.cpp` threading semantics must be validated before sharing runtime
  state across workers.
- first speed gains may come more from model persistence than raw inference
  acceleration.
- transcript output will not necessarily match `faster-whisper` behavior one to
  one.
- the engine should not absorb too many Python responsibilities too early.

## Recommended Follow-Up Docs

After implementation starts, add:

- `docs/whispercpp-engine-protocol.md`
- `docs/whispercpp-engine-benchmarks.md`
- `docs/whispercpp-engine-packaging.md`

