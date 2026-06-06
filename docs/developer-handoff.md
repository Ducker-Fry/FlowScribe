# FlowScribe Developer Handoff

This document defines the public framework surface that FlowScribe currently
commits to keep stable for downstream developers.

## Stability Policy

FlowScribe currently exposes four official public entry packages:

- `flowscribe.app`
- `flowscribe.tasks`
- `flowscribe.providers`
- `flowscribe.capabilities`

Code outside those package exports should be treated as internal implementation
detail unless a future document explicitly promotes it to public API.

For the current `v0` protocol phase, stability means:

- We may add new fields and new exported symbols.
- We avoid renaming or removing exported symbols from the four public packages.
- We keep protocol objects JSON-serializable and suitable for CLI, GUI, and
  service integration.
- We do not promise import stability for internal modules such as
  `flowscribe.pipeline.*`, `flowscribe.runtime.*`, `flowscribe.gui.*`, or
  private helpers inside `flowscribe.app.service`.

## Public API Contracts

### `flowscribe.app`

Purpose:

- Application-layer entry surface for CLI, GUI, API server, and external tools.
- Accepts user intent and invokes the lower layers without exposing provider or
  runtime details.

Stable exports:

- `TranscriptionService`
- `SourceSpec`
- `TaskSpec`
- `TranscriptionJob`
- `TranscriptionResult`
- `ProgressEvent`
- `ProgressCallback`
- `CancelRequest`
- `CancelAck`

What we promise:

- `TranscriptionService` remains the primary programmatic entry point for
  launching transcription work from application code.
- Public task/progress/cancel models exported here remain compatible with the
  task-layer protocol.
- App consumers do not need to import concrete providers, `ffmpeg`, `yt-dlp`,
  or model runtimes directly.

What remains internal:

- URL subtitle-first routing details
- Download fallback decisions
- Provider selection heuristics
- Runtime factory wiring
- Compatibility hooks kept only for existing tests and migration safety

Recommended usage:

```python
from flowscribe.app import SourceSpec, TranscriptionJob, TranscriptionService

service = TranscriptionService()
job = TranscriptionJob(
    sources=(SourceSpec(kind="url", value="https://www.youtube.com/watch?v=..."),),
    requested_capabilities=("subtitle", "transcribe"),
)
result = service.run(job)
```

### `flowscribe.tasks`

Purpose:

- Stable task protocol and task-adjacent queue/import helpers.
- Defines the data contracts that move across app, pipeline, capability, and
  provider boundaries.

Stable exports:

- `SourceSpec`
- `TaskSpec`
- `CapabilityResult`
- `TranscriptionJob`
- `TranscriptionResult`
- `ProgressEvent`
- `ProgressCallback`
- `ErrorInfo`
- `ErrorEvent`
- `CancelRequest`
- `CancelAck`
- `RuntimePreferences`
- `OutputContract`
- `DownloadOptions`
- `generate_cache_key`
- `BatchQueueStore`
- `QueueItem`
- `QueueItemSettings`
- `deduplicate_sources`
- `import_urls_from_file`

What we promise:

- These models remain the source of truth for task identity, progress,
  cancellation, output contracts, and capability results.
- `protocol_version="v0"` objects remain forward-compatible by additive fields.
- Task-layer models are safe to serialize to JSON for persistence, queueing, and
  inter-process handoff.

What remains internal:

- Concrete scheduler implementation
- Checkpoint storage format
- Cache layout on disk
- GUI queue persistence details

Recommended usage:

- Build new workflows around `TaskSpec` first.
- Treat `TranscriptionJob` as a compatibility entry model while older code is
  migrated.
- Use `CapabilityResult` rather than provider-specific return shapes in new
  orchestration code.

### `flowscribe.providers`

Purpose:

- Stable adapter-layer surface for plugging in transcription and subtitle
  backends.
- Lets downstream developers add or swap concrete engines without rewriting app
  and task code.

Stable exports:

- `TranscriptionProvider`
- `ProviderCapabilities`
- `ProviderTranscriptionSettings`
- `resolve_transcription_provider`
- `default_transcription_provider`
- `is_native_engine_provider_name`
- `LocalWhisperProvider`
- `LocalWhisperTranscriber`
- `NativeEngineProvider`
- `NativeEngineTranscriber`
- `ParaformerProvider`
- `ParaformerTranscriber`
- `PARAFORMER_MODEL_NAME`
- `YouTubeNativeSubtitleProvider`
- `YOUTUBE_SUBTITLE_PROVIDER_NAME`

What we promise:

- Public provider classes and resolver helpers remain the supported extension
  surface for backend adapters.
- Provider code may rely on task-layer protocol objects instead of app-layer
  internals.
- Subtitle providers and transcribe providers remain separate concepts even when
  the pipeline composes them into one user workflow.

What remains internal:

- Registry storage details
- Runtime process launching
- CLI presentation rules
- Pipeline routing decisions such as subtitle-first fallback logic

Recommended usage:

- Add new engines under provider-oriented modules and expose them through
  `flowscribe.providers`.
- Keep provider implementations focused on declaring support and executing work,
  not on routing tasks across multiple capabilities.

### `flowscribe.capabilities`

Purpose:

- Stable capability-layer surface between orchestration and concrete providers.
- Represents business capabilities such as subtitle extraction and transcription
  independent of specific engines.

Stable exports:

- `Capability`
- `CancelToken`
- `ProviderProtocol`
- `ProviderRequest`
- `ProviderResponse`
- `SubtitleCapability`
- `TranscribeCapability`

What we promise:

- Capability classes remain the supported place for business-level policies such
  as "subtitle first, then transcription fallback".
- Provider/runtime interactions continue to flow through capability-level
  request/response abstractions instead of leaking raw subprocess or SDK logic
  upward.
- `SubtitleCapability` and `TranscribeCapability` remain the first-class v0
  capabilities.

What remains internal:

- Exact pipeline step graph
- Scheduler strategy
- Runtime factory composition
- Service-level backward-compatibility shims

Recommended usage:

- If you need new end-user behavior, extend a capability before changing app
  service code.
- If you only need a new backend, implement or wire a provider without changing
  capability contracts.

## Internal Modules And Non-Guaranteed Imports

The following areas are intentionally not part of the official stable API yet:

- `flowscribe.pipeline.*`
- `flowscribe.runtime.*`
- `flowscribe.gui.*`
- `flowscribe.input.*`
- `flowscribe.core.*` except where re-exported through a public package
- private functions or underscored names anywhere in the tree

Why this boundary exists:

- The pipeline is still being actively refactored to make six-layer boundaries
  clearer.
- Runtime integration may change as local engines, cloud APIs, and native
  binaries evolve.
- GUI and service composition need freedom to move without breaking downstream
  plugin authors.

## How Others Should Build On Top Of FlowScribe

### Reuse the framework

- Import from `flowscribe.app` if you want a stable entry point.
- Import from `flowscribe.tasks` if you need durable models, queue data, or
  cache-safe protocol objects.
- Import from `flowscribe.capabilities` if you are extending workflow behavior.
- Import from `flowscribe.providers` if you are integrating a new backend.

### Add a new provider

Recommended path:

1. Implement provider logic against the provider/capability protocol.
2. Export the provider from `flowscribe.providers`.
3. Let capability or pipeline code decide when that provider should be used.

Avoid:

- Calling provider internals directly from CLI or GUI code.
- Embedding subtitle-first or download-fallback policy in the provider itself.

### Add a new capability

Recommended path:

1. Define the capability behavior around `TaskSpec`, `ProviderRequest`, and
   `CapabilityResult`.
2. Reuse existing providers where possible.
3. Return normalized `ProgressEvent`, `ErrorEvent`, and cancel semantics.

Avoid:

- Returning backend-specific raw result shapes to app code.
- Letting app/service become the place where multi-step business logic grows.

## Current Architectural Direction

The intended six layers are:

1. App Layer: CLI / GUI / API / meeting assistant / third-party tools
2. Task Layer: job / batch / queue / progress / cancel / resume / cache / export
3. Orchestration Layer: pipeline / router / scheduler / runtime manager / model
   manager
4. Capability Layer: subtitle / transcribe / summarize / translate / indexing
5. Adapter Layer: local whisper / native engine / paraformer / ffmpeg / cloud
6. Runtime Layer: SDKs / subprocesses / native binaries / API clients

Current public API work is meant to let external developers build on top of the
framework now, while the internal pipeline and runtime pieces continue to settle.

## Versioning Guidance For Downstream Developers

If you are building on FlowScribe today:

- Pin a minor version when depending on internal imports.
- Prefer the four public packages if you want fewer breakages during refactors.
- Expect internal modules to move as the six-layer architecture is extracted more
  cleanly.
- Watch release notes for any public API promotion or deprecation notices.
