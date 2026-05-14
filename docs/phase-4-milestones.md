# Phase 4 Milestones

Phase 4 name: **Capture, Workflow Persistence, And Desktop Productization**

Target version: **v0.4.0**

## Phase 4 Theme

Phase 4 should turn the current desktop GUI from a strong MVP into a steadier
daily-use application.

The phase focus is:

```text
desktop transcription MVP
  -> repeatable workflow
  -> better job control
  -> stronger transcript/media review
  -> system audio capture
  -> release-quality desktop delivery
```

## Milestone 4.1: GUI Preference Persistence

### Goal

Make the GUI remember non-sensitive user preferences so repeated use does not
start from a blank slate.

### Scope

- Persist default output directory.
- Persist default model.
- Persist default language.
- Persist default preset.
- Persist default output formats.
- Persist default timestamp-related options.
- Persist default network family.
- Optionally persist explicit proxy value or path if the user entered one.
- Consolidate GUI state storage into a clearer schema.
- Keep backward compatibility with existing saved local-source state where
  feasible.
- Add an explicit `Save Settings` action so preference persistence is
  user-controlled.
- Add a `View Settings` action so users can inspect saved and current
  preference values clearly.

### Acceptance Criteria

- Closing and reopening the GUI restores practical non-sensitive defaults.
- Invalid saved paths or outdated values do not crash the GUI.
- Users can still override restored defaults normally in the current session.
- Saved state remains readable and maintainable from an engineering standpoint.
- Users can explicitly save preferences from the GUI.
- Users can inspect saved and current preferences without mixing them into run
  progress output.

### Non-Goals

- Do not store cookie contents.
- Do not store hidden login/session data.
- Do not build a full settings page if simple persistence is enough for the
  milestone.

## Milestone 4.2: Job Control And Output Actions

### Goal

Give users direct control over running desktop tasks and quicker access to
generated outputs.

### Scope

- Add `Cancel Transcription` support for the current running job.
- Add `Open Output Folder` action in the GUI.
- Improve run-state messaging for:
  - pending
  - running
  - cancel requested
  - canceled
  - failed
  - completed
- Make post-run actions clearly available only when they are valid.

### Acceptance Criteria

- A running transcription job can be canceled from the GUI.
- Canceling does not freeze the GUI.
- Canceled jobs are not misreported as generic failures.
- Users can open the configured output directory directly from the GUI.
- Status text and controls reflect the real job state clearly.

### Non-Goals

- Do not build a full multi-job queue yet.
- Do not introduce distributed/background job execution outside the current GUI
  process.

## Milestone 4.3: Recent Work History

### Goal

Help users quickly resume recent work without manually rediscovering files,
transcripts, or output locations.

### Scope

- Track recently opened transcript JSON files.
- Track recently used output directories.
- Track recent transcription jobs at a lightweight level.
- Optionally remember recent bound media paths for transcript review flows.
- Expose recent items in a simple desktop-friendly way.

### Acceptance Criteria

- Users can reopen recent transcript work from the GUI.
- Users can quickly return to recent output locations.
- Recent state survives app restart.
- Missing or deleted files are handled gracefully.

### Non-Goals

- Do not build a database-backed transcript library.
- Do not add tagging, collections, or full-text indexing across a historical
  corpus.

## Milestone 4.4: Transcript-Media Review Enhancement

### Goal

Turn the current media sync MVP into a steadier review experience for reading,
searching, and listening at the same time.

### Scope

- Highlight the active transcript segment during playback.
- Keep the transcript view following the active segment when appropriate.
- Improve selection consistency between:
  - search results
  - current transcript segment
  - media playback position
- Show clearer media-binding state:
  - auto-bound
  - manually bound
  - unbound
- Add clearer mismatch warnings when transcript source and bound media appear
  inconsistent.

### Acceptance Criteria

- During playback, the active segment is visibly highlighted.
- The viewer can keep the current segment in view without chaotic scrolling.
- Clicking a search hit still seeks media and focuses the correct segment.
- Unbound or suspicious media states produce clear feedback instead of silent
  confusion.

### Non-Goals

- Do not implement full word-level click-to-seek editing yet.
- Do not build a professional NLE-style timeline or subtitle editor.

## Milestone 4.5: System Audio Capture MVP

### Goal

Let users capture audio being played locally, save it as a normal local artifact,
and run it through the existing transcription pipeline.

### Scope

- Start system audio capture from the GUI.
- Stop capture from the GUI.
- Save capture output to a local audio file, such as WAV.
- Treat the captured file as a normal local input artifact.
- Allow the user to transcribe the captured file through the existing service
  layer.
- Show clear errors when capture cannot start or no usable capture path exists.

### Acceptance Criteria

- Users can start and stop capture through the GUI.
- Stopping capture produces a local audio artifact.
- The captured artifact can be transcribed without a special second pipeline.
- Failure states are reported clearly in the GUI.

### Non-Goals

- Do not add advanced clipping, waveform editing, or timeline slicing.
- Do not add DRM bypass or protected-stream circumvention.
- Do not assume browser-session extraction is a substitute for user-controlled
  capture.

## Milestone 4.6: Release Hardening And Desktop Validation

### Goal

Keep CLI and GUI delivery stable as the desktop workflow grows more capable.

### Scope

- Preserve dual release packaging:
  - CLI portable package
  - GUI portable package
- Maintain smoke verification for both packaged entry points.
- Extend test coverage for:
  - GUI persistence
  - cancel flow
  - recent-work state
  - capture-related logic where feasible
- Continue improving end-user release notes and installation instructions.
- Keep GUI packaged logging behavior quiet and predictable for normal users.

### Acceptance Criteria

- CLI and GUI release packages continue to build in GitHub Actions.
- Release workflows verify both packaged entry points successfully.
- Desktop-specific regressions are covered by focused tests where practical.
- Release docs reflect actual shipped behavior and artifacts.

### Non-Goals

- Do not redesign the entire CI/CD pipeline without a concrete need.
- Do not try to solve every possible platform variation beyond the current
  Windows-focused release path.

## Recommended Implementation Order

Recommended execution order for the phase:

1. Milestone 4.1: GUI Preference Persistence
2. Milestone 4.2: Job Control And Output Actions
3. Milestone 4.3: Recent Work History
4. Milestone 4.4: Transcript-Media Review Enhancement
5. Milestone 4.5: System Audio Capture MVP
6. Milestone 4.6: Release Hardening And Desktop Validation

## Phase 4 Exit Criteria

Phase 4 can be considered complete when:

- the GUI remembers practical non-sensitive defaults
- users can cancel active jobs and open outputs directly
- users can return to recent work without manual rediscovery
- transcript/media review feels steadier during playback
- system audio capture produces transcribable local artifacts
- CLI and GUI release packaging remain reliable
