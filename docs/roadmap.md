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

Status: completed incrementally and wrapped up in `v0.2.3`.

## v0.4 Capture, Workflow Persistence, And Desktop Productization

Goal: make the desktop workflow repeatable, controllable, and capture-capable
for daily use.

- System audio capture prototype.
- Save captured audio as a normal input artifact.
- Transcribe captured audio through the existing pipeline.
- Persistent non-sensitive GUI defaults.
- Cancel-job support and open-output-directory actions.
- Lightweight recent-job or recent-transcript history.
- Stronger transcript/media synchronization feedback during playback.

Status: completed incrementally and wrapped up in `v0.2.4`.

## v0.5 Transcript Library And Provider Readiness

Goal: make repeated use more convenient and prepare a transcript workspace with
a cleaner provider boundary.

- Local transcript library.
- Transcript correction and re-export workflow.
- Reusable export profiles.
- Provider-facing transcription interface around the local backend.
- Provider capability and cost or latency documentation.

Status: completed incrementally and wrapped up in `v0.2.5`. See
`docs/phase-5-summary-and-phase-6-plan.md` and `docs/phase-6-task-list.md`.

## v0.6 Workspace Consolidation, Onboarding, And Release Reliability

Goal: make the transcript workspace denser, easier to learn, and less fragile
to operate or release.

- Consolidated transcript review and artifact viewing workflows.
- Faster transcript library review with better filtering and sorting.
- Better artifact inspection ergonomics.
- Stronger onboarding and user-facing diagnostics.
- More repeatable and idempotent release operations.

Status: completed incrementally and wrapped up in `v0.2.6`. See
`docs/phase-6-summary-and-phase-7-plan.md` and `docs/phase-7-task-list.md`.

## v0.7 Long Media Progressive Transcription

Goal: make long local media and URL-derived media feel more alive and more
recoverable by showing transcript progress before the full run completes.

- Chunk-based progressive transcription for long runs.
- Chunk cache and resume support.
- GUI-visible duration progress, speed, and ETA.
- Limited parallel scheduling groundwork for later throughput gains.
- CLI progressive mode and compatibility rules.
- Conservative overlap, merge, and consistency protection for progressive
  output.
- Compatibility with the current transcript library, editing, and re-export
  flow.

Status: in progress. Foundation, cache, resume support, GUI-facing progress
events, CLI progressive controls, compatibility rules, and limited parallel
groundwork have landed. Remaining work is now more about tuning, real long-run
validation, and experience refinement than first-time scaffolding. See
`docs/long-media-progressive-transcription-task-list.md`.

## v0.8 URL Workflow And Throughput Ergonomics

Goal: make URL-driven transcription and long-run handling more practical for
repeated daily use.

- GUI URL media preservation choices, including saved audio or saved video
  handling
- custom URL media save paths
- automatic transcript-to-media binding for preserved URL media
- clearer fallback status when requested video preservation becomes audio-only
- better long-run tuning informed by real media samples
- follow-on batch and throughput improvements that build on progressive
  execution

Status: partially underway in the current working tree, but not yet wrapped as a
release milestone.

## v0.9 Native Persistent Whisper.cpp Engine

Goal: reduce repeated transcription startup cost and create a native local
runtime path for more aggressive long-media throughput tuning.

- Native `whisper.cpp` engine process for Windows.
- Model persistence across multiple CLI jobs.
- Python provider adapter instead of a whole-pipeline rewrite.
- Local IPC over Windows Named Pipe.
- CLI-first integration before GUI adoption.
- `v0` whole-file transcription path.
- `v1` chunked scheduling, progress events, cancellation, and cache groundwork.
- Chinese throughput-oriented tuning path built on the native runtime boundary.

Status: planned. Design and implementation order are tracked in
`docs/whispercpp-engine-plan.md`.

## v1.0 Open Source Release

Goal: polish the project as a public portfolio-quality tool.

- Stable CLI and GUI workflows.
- Stable native-engine-backed workflow for performance-sensitive local use.
- Clean release artifacts.
- Complete user documentation.
- Demo media workflows.
- Maintainer documentation.
- Clear legal and ethical boundaries.
