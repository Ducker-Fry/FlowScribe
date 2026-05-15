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

Status: planned. See `docs/phase-5-summary-and-phase-6-plan.md` and
`docs/phase-6-task-list.md`.

## v1.0 Open Source Release

Goal: polish the project as a public portfolio-quality tool.

- Stable CLI and GUI workflows.
- Clean release artifacts.
- Complete user documentation.
- Demo media workflows.
- Maintainer documentation.
- Clear legal and ethical boundaries.
