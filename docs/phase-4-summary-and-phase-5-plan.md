# Phase 4 Summary And Phase 5 Plan

Phase 4 name: Capture, Workflow Persistence, And Desktop Productization

Wrap-up release: `v0.2.4`

Completion date: 2026-05-15

## Phase 4 Goal

Phase 4 turned FlowScribe from a basic desktop transcription shell into a more
durable Windows desktop workflow:

```text
desktop transcription MVP
  -> persistent workflow
  -> job control
  -> recent work
  -> transcript/media review improvements
  -> system audio capture
  -> hardened CLI + GUI release delivery
```

The phase is complete from a product-milestone perspective. The main proof point
is the `v0.2.4` release, where both CLI and GUI portable packages are built and
validated in GitHub Actions.

## Completed Work

### GUI Preference Persistence

FlowScribe now persists non-sensitive desktop preferences that affect everyday
transcription work:

- output directory
- custom basename
- model selection
- language
- preset
- output formats
- timestamp options
- URL and network options

The implementation deliberately avoids storing cookies or secret-like values.
The GUI also exposes user-facing settings actions such as saving settings and
opening the settings location.

### Job Control And Output Actions

The GUI can cancel an active transcription job and report the canceled state
without pretending the job completed successfully. Output-directory actions are
reachable from the desktop workflow, which makes repeated local use less
dependent on manual file navigation.

### Recent Work History

Phase 4 added a recent-work layer for desktop continuity. It tracks recent
transcript JSON files, output directories, transcription tasks, and media binding
pairs. The dedicated recent-work UI handles missing paths gracefully instead of
failing the whole workflow.

### Transcript And Media Review

Transcript review is now tied more tightly to media playback. Segment selection,
search, playback, and media binding state are coordinated in the GUI. The binding
model distinguishes unbound, automatic, and manual media associations, and it can
surface mismatch warnings when the transcript and media look suspiciously out of
sync.

### System Audio Capture

Phase 4 started with a direct `dshow` MVP and then transitioned to a dedicated
WASAPI helper boundary:

```text
FlowScribe GUI
  -> CaptureController
  -> WasapiCaptureHelper.exe
  -> WAV file
  -> existing local transcription path
```

The helper is implemented as a C#/.NET executable with NAudio pinned through the
helper project. The first CLI contract includes:

- `version`
- `probe`
- `list-devices`
- `capture`

Helper output is machine-readable JSON on stdout. Capture can be stopped through
stdin, which gives the Python side a clean process-control contract. On the
Python side, `WasapiHelperCaptureRecorder` and `CaptureController` keep capture
logic separate from transcription. The older direct `dshow` path remains behind
`LegacyDshowCaptureRecorder` as a fallback rather than the primary path.

### Release Hardening

The `v0.2.4` release keeps the two Windows portable artifacts:

```text
FlowScribe-v0.2.4-windows-x64.zip
FlowScribeGUI-v0.2.4-windows-x64.zip
```

The GUI package now includes `WasapiCaptureHelper.exe` and its runtime
dependencies. GitHub Actions validates the CLI package, the GUI package, the GUI
self-test path, and the helper `version` and `probe` smoke checks. Release and
installation documentation now describe the helper-backed capture behavior and
the two package types.

## Engineering Outcomes

Desktop reliability improved because preferences, recent work, cancellation, and
output actions reduce repeated manual setup.

Architecture stayed contained. The main transcription flow still centers on:

```text
GuiTranscriptionForm
  -> TranscriptionJob
  -> TranscriptionService
```

Capture moved behind a process boundary, which keeps WASAPI, .NET, and NAudio
details out of the Python transcription core.

Release confidence improved because the release workflow validates both package
families and checks the helper binary after packaging.

Test coverage now protects GUI persistence, cancel flow, recent history, capture
controller behavior, helper integration, packaging smoke checks, and release
workflow expectations.

## Remaining Gaps

Phase 4 intentionally left several larger product areas for the next milestone:

- no transcript library beyond recent history
- no durable job database
- no transcript correction workflow
- no re-export workflow from corrected transcripts
- no named export profiles
- no provider abstraction beyond the local faster-whisper path
- no automatic capture level or silence feedback in the GUI
- no first-run onboarding or guided setup
- no broad platform release strategy beyond the current Windows path

## Phase 5 Plan

Phase 5 name: Transcript Library, Editing Workflow, And Provider Readiness

The next phase should convert FlowScribe from a job runner with useful history
into a transcript workspace:

```text
desktop transcription tool
  -> transcript workspace
  -> reusable history
  -> correction and export workflow
  -> provider abstraction readiness
  -> better first-run and release experience
```

### Core Features

1. Transcript Library

Build a durable local library index for completed transcripts, source media,
output directories, timestamps, labels, and missing-file status. Recent history
can either become a library view or remain as a small fast-access layer over the
same data.

2. Transcript Correction Workflow

Add first-class editing for transcript segment text while preserving timing
metadata. Corrected JSON should become the source for later export.

3. Export Profiles And Re-Export

Support named output profiles and allow users to regenerate text, Markdown,
subtitle, and JSON outputs from an existing transcript without rerunning
transcription.

4. Provider Readiness

Define a provider boundary for transcription backends while keeping local
faster-whisper as the default. The goal is not to add paid or cloud providers
immediately, but to prevent the local provider from becoming impossible to
separate later.

5. Capture And Release Polish

Improve capture feedback, unsupported-device messaging, first-run guidance, and
release documentation while preserving the quiet packaged-GUI behavior.

## Phase 5 Non-Goals

- no account system
- no cloud sync
- no large database unless the library shape clearly requires it
- no broad platform packaging expansion
- no paid provider integration before the provider boundary is stable
- no full professional subtitle editor or nonlinear media editor

## Success Criteria

Phase 5 is ready to close when:

- completed transcripts can be discovered and reopened from a durable library
- transcript text can be corrected and saved without losing timing metadata
- corrected transcripts can be re-exported without rerunning transcription
- export settings can be reused as named profiles
- provider-facing code has a clear interface around the local backend
- capture and first-run failure states are easier for desktop users to diagnose
- CLI and GUI release packages still build and pass smoke checks in GitHub
  Actions

Target release line: `v0.5.0`.
