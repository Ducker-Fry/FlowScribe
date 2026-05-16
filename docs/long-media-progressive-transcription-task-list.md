# Long Media Progressive Transcription Task List

Goal: move FlowScribe from a "finish everything, then show everything" model to
a progressive transcription pipeline that can surface early transcript content,
show meaningful progress for long media, recover from interruption, and leave a
clean path toward limited parallel execution later.

## Target Outcome

When users process long local media or URL-derived media, they should be able
to:

- see the first transcript segments early instead of waiting for the whole run
- watch progress advance against total media duration
- get a rough but useful estimate of remaining time
- recover from interruption at the chunk level
- keep compatibility with later library, editing, and re-export workflows

## Current Non-Goals

This task line does not require:

- true network-streaming transcription from remote media
- aggressive multi-worker execution by default
- complex NLP-style boundary merging
- large-model post-processing

## Delivery Stages

1. Progressive transcription foundation
2. Chunk cache and recovery
3. GUI progressive display and ETA
4. Limited parallel execution groundwork

## Stage A: Progressive Transcription Foundation

### A.1 Progressive transcription data model

Tasks:

- Add internal models for progressive transcription state.
- Define at least:
  - `MediaDurationInfo`
  - `TranscriptionChunkPlan`
  - `TranscriptionChunk`
  - `ChunkTranscriptionResult`
  - `ProgressiveTranscriptionState`
- Include fields for:
  - chunk index
  - start and end time
  - overlap duration
  - status such as `pending`, `running`, `done`, `failed`, `skipped`
  - processed duration
  - segment count
  - started and finished timestamps
  - failure details

Acceptance:

- Progressive transcription state is no longer spread across temporary values.
- Later GUI, cache, recovery, and scheduling work can reuse one shared model.

### A.2 Media duration probing

Tasks:

- Add a shared way to detect total duration for local media and URL-derived
  media.
- Provide a fallback path for media that does not expose duration cleanly.
- Normalize duration precision and units for downstream progress tracking.

Acceptance:

- Most transcription tasks know total duration before chunk processing starts.
- Missing duration degrades gracefully instead of blocking the workflow.

### A.3 Fixed-duration chunk planner

Tasks:

- Implement chunk planning based on fixed duration.
- Support configuration for:
  - `chunk_duration_seconds`
  - `chunk_overlap_seconds`
- Ensure planning covers the entire media duration and handles a shorter final
  chunk correctly.

Suggested defaults:

- `chunk_duration_seconds`: 30 or 60
- `chunk_overlap_seconds`: 2 to 5

Acceptance:

- Valid media duration inputs always produce a stable chunk execution plan.

### A.4 Serial chunk transcription executor

Tasks:

- Execute transcription chunk by chunk in sequence.
- Emit a chunk result immediately after each chunk finishes.
- Record for each chunk:
  - elapsed runtime
  - segment count
  - success or failure state
- Keep the first implementation serial so behavior stays easier to validate.

Acceptance:

- The backend can produce useful partial results before the full media is done.
- Progressive execution works even before the GUI is fully updated.

### A.5 Chunk result merge strategy v1

Tasks:

- Implement a minimal stable merge strategy for chunk outputs.
- Use conservative overlap trimming.
- Ensure:
  - final transcript order is time-based
  - overlapping chunk output does not create obvious duplicate runs
  - segment identifiers can be rebuilt consistently

Acceptance:

- Adjacent chunk outputs merge into one transcript without major repetition.
- Chinese content is handled conservatively instead of being over-merged.

## Stage B: Chunk Cache And Recovery

### B.1 Chunk cache directory structure

Tasks:

- Define a dedicated cache layout for each progressive transcription run.
- Store:
  - job metadata
  - chunk plan
  - per-chunk result files
  - partial merged transcript state
  - execution snapshot or status summary
- Keep cache separate from normal output artifacts.

Acceptance:

- Each long-running task has its own readable cache structure.

### B.2 Per-chunk intermediate persistence

Tasks:

- Save chunk results immediately after successful completion.
- Persist:
  - chunk metadata
  - raw segment output
  - normalized segment output
  - runtime metrics
  - failure details when relevant

Acceptance:

- Completed chunks survive interruption without requiring a full rerun.

### B.3 Recovery strategy v1

Tasks:

- Detect resumable progressive cache state at startup.
- Support at least:
  - resume unfinished chunks
  - discard cache and restart cleanly
- Reload:
  - chunk plan
  - finished chunk results
  - processed duration
  - already-produced transcript segments

Acceptance:

- Interrupted tasks can resume from chunk-level progress.
- Resume behavior preserves already-generated transcript content.

### B.4 Cache cleanup policy

Tasks:

- Define when cache is automatically removed.
- Define when cache is kept for recovery or debugging.
- Add cleanup entry points for:
  - completed runs
  - failed runs
  - manual user cleanup

Acceptance:

- Cache does not grow without bounds.
- Recovery data is not deleted prematurely.

## Stage C: GUI Progressive Display And ETA

### C.1 Progressive GUI event channel

Tasks:

- Add worker-to-GUI progressive event types.
- Include at least:
  - job started
  - duration known
  - chunk started
  - chunk completed
  - segments appended
  - progress updated
  - ETA updated
  - job finished
  - job failed
  - job resumed

Acceptance:

- The GUI no longer depends only on one final transcription payload.

### C.2 Streaming transcript list display

Tasks:

- Append transcript segments progressively in the GUI.
- Avoid full-list redraw on every update.
- Handle:
  - a user reading older content without forced jump-to-bottom behavior
  - an optional "follow latest result" mode
  - lightweight new-content indicators

Acceptance:

- Users can read progressively generated transcript content comfortably.

### C.3 Total-duration-based progress bar

Tasks:

- Drive progress from `processed_duration / total_duration`.
- Distinguish workflow phases such as:
  - media preparation
  - transcription
  - export
- Display:
  - processed duration
  - total duration
  - current chunk
  - completed chunk count

Acceptance:

- Long-running tasks show understandable progress instead of an opaque spinner.

### C.4 ETA estimation v1

Tasks:

- Estimate remaining time using recent chunk throughput.
- Show:
  - approximate realtime factor
  - rough remaining time
- Avoid unstable ETA output too early in the run.

Acceptance:

- Users get a coarse but useful sense of how long the current run may take.

### C.5 Long-task status summary

Tasks:

- Add a compact long-task summary showing:
  - total duration
  - processed duration
  - chunk counts
  - current chunk
  - total generated segments
  - elapsed time
  - estimated remaining time
- Keep failure, pause, and resume states explicit.

Acceptance:

- Long progressive runs feel observable instead of opaque.

## Stage D: Limited Parallel Execution Groundwork

### D.1 Pipeline-style scheduler structure

Tasks:

- Refactor execution into clearer stages:
  - chunk planning
  - chunk readiness
  - chunk transcription
  - chunk merge
  - GUI event emission
- Leave room for future parallel scheduling without rewriting the full flow.

Acceptance:

- Future parallel execution can build on a staged pipeline instead of a monolith.

### D.2 Preprocessing and transcription decoupling

Tasks:

- Separate chunk preparation from chunk transcription execution.
- Allow later chunks to be prepared while an earlier chunk is still being
  transcribed.

Acceptance:

- The system has a clearer pipeline even before multiple workers are enabled.

### D.3 Limited worker concurrency v1

Tasks:

- Support small worker counts such as 2 workers.
- Keep concurrency configurable and conservative.
- Ensure:
  - chunk results may finish out of order
  - merged transcript still respects time order
  - GUI-visible transcript order remains stable

Acceptance:

- Concurrency can improve throughput without corrupting result order.

### D.4 Device-aware concurrency policy

Tasks:

- Tune concurrency differently for CPU and GPU paths.
- Avoid:
  - memory spikes
  - GPU contention that reduces throughput
  - UI responsiveness regressions

Acceptance:

- Concurrency is constrained by real device behavior instead of a fixed guess.

## Accuracy Protection Tasks

### Overlap tuning

Tasks:

- Evaluate overlap size across common media lengths and speech patterns.
- Pay special attention to Chinese transcript boundaries.

Acceptance:

- Default overlap is conservative enough to reduce boundary damage.

### Chinese merge safety

Tasks:

- Avoid aggressive text-level duplicate suppression in early versions.
- Prefer preserving ASR output over clever but risky text rewrites.

Acceptance:

- Chinese chunk boundaries remain readable without introducing avoidable merge
  errors.

### Progressive result consistency checks

Tasks:

- Validate:
  - monotonic time ordering
  - acceptable overlap handling
  - export compatibility
  - transcript JSON compatibility with later editing and re-export steps

Acceptance:

- Progressive output remains compatible with the current transcript workflow.

## CLI And Workflow Tasks

### CLI progressive mode

Tasks:

- Add progressive mode options such as:
  - `--progressive`
  - `--chunk-seconds`
  - `--chunk-overlap-seconds`
  - `--resume`
  - `--max-workers`
- Surface progressive status in CLI output.

Acceptance:

- Progressive execution can be exercised without the GUI.

### Compatibility rules

Tasks:

- Define when normal transcription remains the default.
- Define when progressive mode is recommended or auto-suggested.
- Consider long-duration thresholds for GUI or CLI recommendations.

Acceptance:

- Short tasks do not pay unnecessary complexity cost.

## Test Plan

### Unit tests

- chunk plan generation
- overlap boundary logic
- merge ordering
- ETA estimation
- recovery state parsing
- chunk cache read and write behavior

### Integration tests

- long-media serial progressive transcription
- interruption and resume
- GUI progressive segment append behavior
- final transcript export from progressive runs
- CLI progressive mode

### Regression checks

- existing non-progressive transcription remains stable
- transcript library indexing still works
- re-export remains compatible

## Documentation Tasks

### User-facing docs

- explain what progressive transcription is
- explain when it helps
- describe what long-task progress and ETA mean
- explain recovery and resume behavior

### Developer docs

- progressive pipeline architecture
- chunk cache structure
- merge strategy notes
- concurrency limitations and extension points

## Recommended Implementation Order

1. media duration probing
2. chunk planner
3. serial chunk transcription executor
4. chunk merge strategy v1
5. GUI progressive events
6. total-duration progress bar
7. ETA estimation v1
8. chunk cache persistence
9. recovery mode
10. preprocessing and transcription decoupling
11. limited worker concurrency
12. documentation and end-to-end regression verification

## Phase Exit Criteria

This task line is ready to close when:

- users can see early transcript segments during long runs
- CLI and GUI both show meaningful progress against total duration
- users get a rough remaining-time estimate
- interrupted tasks can resume from chunk-level state
- final transcript output still works with library, editing, and re-export flows
- the execution model leaves a clean path for future limited parallelism
