# Phase 5 Summary And Phase 6 Plan

Phase 5 name: Transcript Library, Editing Workflow, And Provider Readiness

Wrap-up release: `v0.2.5`

Completion date: 2026-05-15

## Phase 5 Goal

Phase 5 turned FlowScribe from a transcription runner with useful desktop
history into a more complete transcript workspace:

```text
desktop transcription shell
  -> transcript workspace
  -> durable transcript history
  -> transcript correction and re-export
  -> reusable export setup
  -> provider boundary readiness
  -> more coherent desktop review flow
```

The phase is complete from a product-milestone perspective. The main proof
point is the `v0.2.5` release line, where the desktop GUI can now reopen,
correct, re-export, and review transcript artifacts as part of one reusable
workflow instead of only one-shot jobs.

## Completed Work

### Transcript Library

Phase 5 introduced a durable local transcript library under
`src/flowscribe/library/`.

The library now tracks:

- transcript JSON paths
- source media paths
- output directories
- created and updated timestamps
- display labels and source kinds
- last-opened timestamps
- missing-file state
- media binding metadata
- generated output artifacts such as `.txt`, `.md`, `.json`, `.srt`, and `.vtt`

The store uses a small JSON persistence layer rather than a database. It also
recovers from corrupt files and now tolerates unreadable or unwritable library
paths without crashing the GUI.

### Library Indexing And GUI Access

Completed transcription runs and opened transcript JSON files now flow into the
library automatically. Media binding and rebind actions update library metadata
as part of the same desktop workflow.

The GUI added a dedicated transcript library window where users can:

- reopen transcripts
- open output directories
- bind or rebind media
- remove items from the library without deleting user files
- clean missing transcript entries

Recent Work remains available as a lightweight companion view rather than being
removed.

### Transcript Correction Workflow

Transcript review is no longer read-only. The GUI now supports editing segment
text while preserving timing and ordering. Corrected transcript JSON records
correction metadata instead of flattening edits into an opaque file rewrite.

The workflow now includes:

- segment text editing
- unsaved-change prompts
- overwrite-or-save-copy decisions
- corrected JSON persistence

This means transcript correction is now part of the normal FlowScribe desktop
loop instead of a separate manual editing task.

### Re-Export And Export Profiles

FlowScribe can now regenerate transcript artifacts from existing transcript JSON
without rerunning download, capture, or model inference.

Supported re-export targets:

- `.txt`
- `.md`
- `.json`
- `.srt`
- `.vtt`

Named export profiles were also added so users can save and reuse combinations
of formats and timestamp settings across new jobs and re-export tasks.

### Provider Readiness

The local faster-whisper path now sits behind an explicit provider boundary.
Provider capability metadata documents model support, language handling, word
timestamp support, latency expectations, cost expectations, and whether
credentials are required.

Local whisper remains the default provider, and the phase intentionally stopped
before introducing cloud provider credentials or account concerns.

### Capture, Review, And Release Polish

The capture and desktop review workflow was tightened further during the phase:

- system capture now reports `idle`, `active`, or `stalled`
- helper-missing and unsupported-device messaging is clearer
- packaged GUI logging remains quiet by default
- release packaging still validates both CLI and GUI outputs

The GUI also gained a unified `Views` window for:

- run details
- transcript review
- generated transcript artifact viewing

Transcript media sync now lives inside the transcript-facing workflow instead of
requiring separate windows for transcript navigation and playback context.

## Engineering Outcomes

Phase 5 materially changed FlowScribe's product shape. The desktop app is now a
workspace for reopening and refining transcript results, not only a trigger for
new transcription jobs.

Data flow also improved. Transcript JSON is now treated as a durable working
asset instead of a terminal export artifact, which makes later editing,
re-export, and provider evolution cleaner.

Architecture stayed relatively disciplined:

```text
GUI shell
  -> form and job state
  -> transcription service
  -> transcript workspace helpers
  -> library storage
  -> provider boundary
```

This phase also improved release resilience. Packaging remains dual-artifact,
GUI state-path failures are less brittle, and release workflow handling around
existing releases has now been hardened.

## Remaining Gaps

Phase 5 solved a large functional slice, but several next-step product gaps are
still visible:

- the desktop workspace is feature-rich but not yet as compact or guided as it
  should be
- transcript library browsing still lacks richer filters, grouping, and faster
  scanning tools
- artifact viewing is useful but not yet optimized for comparison workflows
- first-run setup and onboarding are still thin
- release workflow observability and rerun ergonomics still need polishing
- there is still no broader queued-job, batch-review, or bulk-library workflow
- provider readiness exists, but no second provider has been integrated yet

## Phase 6 Plan

Phase 6 name: Workspace Consolidation, Onboarding, And Release Reliability

The next phase should make FlowScribe feel more coherent and easier to live in
day to day:

```text
feature-complete transcript workspace
  -> denser and more coherent desktop workflow
  -> faster library and artifact review
  -> better onboarding and diagnostics
  -> more repeatable release operations
```

### Core Features

1. Workspace Consolidation

Tighten the GUI so transcript review, artifact viewing, playback sync, and job
feedback feel like one intentional workspace instead of adjacent feature blocks.

2. Library Review Ergonomics

Add filtering, sorting, missing-state triage, and quicker reopen actions so the
library scales beyond a short recent-history replacement.

3. Artifact Review And Comparison

Improve artifact viewing for transcript outputs, including better readability,
format-specific presentation, and at least lightweight comparison or switch-fast
flows.

4. Onboarding And Diagnostics

Add clearer first-run guidance, helper troubleshooting, model download
explanations, and environment diagnostics for desktop users.

5. Release Workflow Reliability

Continue hardening GitHub Actions and release automation so rebuilds, reruns,
and release updates are less fragile and more observable.

## Phase 6 Non-Goals

- no account system
- no cloud sync
- no broad non-Windows packaging expansion
- no full collaborative editing model
- no advanced subtitle timeline editor
- no major database migration unless library scale clearly requires it

## Success Criteria

Phase 6 is ready to close when:

- the desktop review workspace feels compact enough for repeated daily use
- transcript library review is faster and more scalable than the current flat
  list
- generated artifact views are easier to inspect and switch between
- first-run desktop users can recover from common setup failures more easily
- release workflow reruns and updates are less error-prone and better documented

Target release line: `v0.6.0`.
