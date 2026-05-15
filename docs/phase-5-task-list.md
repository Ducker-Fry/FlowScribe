# Phase 5 Task List

Phase 5 name: Transcript Library, Editing Workflow, And Provider Readiness

Target release line: `v0.5.0`

Current implementation status: Phase 5.1 through Phase 5.8 are implemented in
the current working flow and are awaiting the next release wrap-up.

## Target Outcome

Phase 5 should make FlowScribe feel like a transcript workspace instead of only
a one-shot transcription launcher. Users should be able to find previous
transcripts, reopen them with media context, correct text, and re-export outputs
without running the transcription model again.

## Delivery Phases

1. Define transcript library models and storage.
2. Add library indexing and maintenance behavior.
3. Connect the library to the GUI.
4. Add transcript correction support.
5. Add re-export from corrected transcript JSON.
6. Add named export profiles.
7. Define the transcription provider boundary.
8. Polish capture feedback, release docs, and packaged smoke checks.

## Phase 5.1: Transcript Library Models And Storage

Suggested files:

```text
src/flowscribe/library/models.py
src/flowscribe/library/store.py
tests/test_transcript_library.py
```

Tasks:

- Create a small library package under `src/flowscribe/library`.
- Define a `TranscriptLibraryEntry` model.
- Define a `TranscriptLibraryStore` API.
- Track transcript JSON path, source media path, output directory, created time,
  updated time, display label, source kind, last-opened time, and missing-file
  status.
- Track media binding information in a durable shape.
- Track output records so generated `.txt`, `.md`, `.json`, `.srt`, and `.vtt`
  files can be discovered later.
- Use an existing project-friendly persistence style before introducing a larger
  database dependency.
- Add unit tests for create, update, read, missing-path detection, and corrupted
  store recovery.

Acceptance:

- A transcript entry can be created from a completed transcription result.
- A transcript entry can be loaded across app restarts.
- Missing transcript, media, and output paths are represented without crashing.

## Phase 5.2: Library Indexing And Maintenance

Tasks:

- Add completed transcription outputs to the library automatically.
- Add opened transcript JSON files to the library.
- Update last-opened metadata when a transcript is viewed.
- Update media binding metadata when the user binds or rebinds media.
- Add remove-from-library behavior that does not delete user files by default.
- Add cleanup behavior for entries whose files no longer exist.
- Keep recent history compatible during the transition.

Acceptance:

- New GUI transcription jobs appear in the library.
- Existing transcript JSON files can be imported or opened into the library.
- Removing a library entry does not delete transcript or media files unless a
  later explicit destructive option is added.

## Phase 5.3: GUI Library Window

Tasks:

- Add a transcript library window or panel.
- Show transcript label, source kind, created time, last-opened time, output
  directory, and missing-file status.
- Add actions to open a transcript, open its output directory, bind or rebind
  media, and remove the entry from the library.
- Reuse the existing transcript viewer and media binding behavior.
- Decide whether recent work becomes a filtered library view or remains a
  separate quick-access view backed by the same store.

Acceptance:

- A user can reopen a prior transcript from the GUI without browsing manually.
- Missing files are visible and recoverable through rebinding or removal.
- Existing recent-work behavior remains usable during migration.

## Phase 5.4: Transcript Correction Workflow

Suggested files:

```text
src/flowscribe/transcript/editing.py
tests/test_transcript_editing.py
```

Tasks:

- Add a safe editing model for transcript segment text.
- Preserve segment timestamps and ordering.
- Mark edited segments in corrected JSON metadata.
- Save corrected transcript JSON without overwriting the original unless the user
  chooses that path.
- Surface unsaved-change state in the GUI.
- Add tests for text edits, save behavior, timestamp preservation, and invalid
  transcript handling.

Acceptance:

- Segment text can be corrected from the desktop UI.
- Corrected transcript JSON preserves timing metadata.
- Users can avoid accidental data loss when closing or switching transcripts.

## Phase 5.5: Re-Export From Transcript JSON

Tasks:

- Add a service function that exports from transcript JSON without rerunning
  transcription.
- Support `.txt`, `.md`, `.json`, `.srt`, and `.vtt` outputs from corrected JSON.
- Add GUI actions to re-export the current transcript.
- Let the user choose output directory and output formats.
- Add tests that corrected text appears in regenerated outputs.

Acceptance:

- Corrected transcript text can be exported to all supported formats.
- Re-export does not invoke media download, capture, or transcription.
- Existing one-shot job export behavior remains unchanged.

## Phase 5.6: Export Profiles

Tasks:

- Add named export profiles for format and timestamp preferences.
- Store profiles as non-sensitive settings.
- Allow a profile to be applied to a new transcription job.
- Allow a profile to be applied during re-export.
- Add default profiles only if they simplify real workflows.

Acceptance:

- Users can reuse common export settings.
- Profiles affect only export behavior and do not store secrets.
- Tests cover profile create, update, load, and apply behavior.

## Phase 5.7: Provider Readiness Boundary

Tasks:

- Review the current local faster-whisper integration.
- Define a provider-facing interface for transcription requests and results.
- Keep local faster-whisper as the default provider.
- Keep provider capability metadata explicit, including model names, language
  handling, word timestamp support, cost expectations, and latency expectations.
- Document what is intentionally not implemented yet for cloud or paid providers.
- Avoid credential storage in this phase unless a later task explicitly adds it.

Acceptance:

- The local transcription path still behaves the same to users.
- Provider-specific concerns are less coupled to GUI and job orchestration code.
- Future provider work has a documented integration point.

## Phase 5.8: Capture Feedback And Release Polish

Tasks:

- Add clearer capture-level or silence feedback where the current helper contract
  allows it.
- Improve messages for missing helper, unsupported device, and capture startup
  failures.
- Keep packaged GUI logging quiet by default.
- Keep CLI and GUI portable package smoke checks in the release workflow.
- Update release documentation to describe library, correction, and re-export
  behavior.

Acceptance:

- Capture failures are easier to diagnose from the GUI.
- Release packages remain dual-artifact Windows packages.
- GitHub Actions still validates both package families.

Implementation notes:

- GUI capture now surfaces `idle`, `active`, and `stalled` activity feedback
  based on whether the capture output file is still growing.
- GUI messaging now distinguishes missing `WasapiCaptureHelper.exe`,
  unsupported loopback environments, and startup/no-audio situations more
  clearly.
- Packaged GUI logging remains quiet by default while capture status remains
  user-visible inside the application.
- Release installation and packaging docs now describe transcript library,
  transcript editing, transcript JSON re-export, export profiles, and helper
  troubleshooting.
- Packaging docs now explicitly require CLI and GUI build entry points to run
  sequentially because both use the shared top-level `build/` workspace.

## Test Plan

Suggested new or expanded tests:

```text
tests/test_transcript_library.py
tests/test_transcript_editing.py
tests/test_transcript_reexport.py
tests/test_export_profiles.py
tests/test_provider_boundary.py
```

Coverage expectations:

- library persistence and recovery
- missing-file state
- recent-history migration or compatibility
- transcript text edits
- corrected JSON save behavior
- re-export output correctness
- export profile persistence
- provider interface behavior
- GUI-facing library and correction state transitions where practical

## Documentation Updates

Update these documents as Phase 5 lands:

- `README.md`
- `docs/gui.md`
- `docs/user_guide.md`
- `docs/release-installation.md`
- `docs/packaging.md`
- `docs/test-plan.md`
- `docs/architecture.md`
- `docs/dev-state.md`

## Execution Checklist

1. [done] Create `src/flowscribe/library` with models, store, and tests.
2. [done] Add library entry creation from completed transcription results.
3. [done] Add opened-transcript indexing.
4. [done] Connect media binding updates to the library store.
5. [done] Add a first GUI library view.
6. [done] Decide and document recent-history compatibility.
7. [done] Implement transcript segment text editing.
8. [done] Add corrected JSON save behavior.
9. [done] Implement re-export from transcript JSON.
10. [done] Add GUI re-export controls.
11. [done] Add named export profiles.
12. [done] Introduce the provider interface around local faster-whisper.
13. [done] Improve capture feedback and first-run diagnostics.
14. [done] Update docs, release notes, tests, and packaging smoke checks.

## Recommended Order

Build the library foundation first, connect the GUI second, then implement
editing and re-export. Export profiles and provider readiness should come after
the data model is stable. Capture feedback and release documentation should be
kept current throughout the phase rather than saved for the end.
