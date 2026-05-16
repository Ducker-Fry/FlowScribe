# Phase 6 Task List

Phase 6 name: Workspace Consolidation, Onboarding, And Release Reliability

Target release line: `v0.2.6`

## Target Outcome

Phase 6 should make FlowScribe's desktop workspace feel tighter, easier to
understand, and less fragile to use or release. The goal is not to add an
entirely new product category, but to make the transcript workspace from Phase 5
faster to navigate and easier to support.

## Delivery Phases

1. Consolidate the desktop workspace layout.
2. Improve transcript library filtering and review speed.
3. Expand artifact viewing and comparison ergonomics.
4. Improve onboarding and diagnostics.
5. Harden release workflow behavior and observability.
6. Refresh docs and verification paths around the new workflow.

## Phase 6.1: Workspace Consolidation

Suggested files:

```text
src/flowscribe/gui/qt_app.py
tests/test_gui_qt_app.py
```

Tasks:

- Continue compacting the GUI around the unified `Views` window.
- Keep transcript playback sync, transcript navigation, and transcript editing
  in one coherent workflow surface.
- Add stable sizing and scroll behavior so controls and bottom actions remain
  reachable on smaller laptop displays.
- Persist non-sensitive view preferences only if they improve repeated use.
- Reduce duplicated or competing window surfaces where the same work can happen
  in one place.

Acceptance:

- Transcript review no longer feels split across unrelated parts of the GUI.
- Editing, playback, and output inspection are reachable without layout breakage
  on common desktop sizes.

## Phase 6.2: Transcript Library Review Ergonomics

Tasks:

- Add filtering by source kind, missing state, or recently opened state.
- Improve sort modes for created time, updated time, and last opened time.
- Add denser list presentation or secondary metadata views where useful.
- Make missing-entry cleanup and recovery more discoverable.
- Keep recent-work shortcuts aligned with the library experience.

Acceptance:

- Users can find the right transcript faster as the library grows.
- Missing or stale entries are easier to identify and clean up.

## Phase 6.3: Artifact Review And Comparison

Tasks:

- Improve presentation for `.txt`, `.md`, `.json`, `.srt`, and `.vtt` views.
- Add format-aware labels, actions, and switching behavior.
- Explore lightweight comparison workflows, such as fast switching between
  transcript JSON, corrected JSON, and subtitle artifacts.
- Keep artifact review integrated with transcript context rather than detached
  from the current workspace.

Acceptance:

- Generated artifacts are easier to inspect than raw text dumps.
- Users can move between transcript source and exported forms with less friction.

## Phase 6.4: Onboarding And Diagnostics

Tasks:

- Add first-run guidance for model downloads, helper requirements, and output
  expectations.
- Improve GUI explanations for common failure states such as missing models,
  unreadable state files, unsupported capture environments, and missing media.
- Expand desktop-visible diagnostics without making packaged logging noisy.
- Keep CLI diagnostics aligned with GUI support messaging where possible.

Acceptance:

- New desktop users have a clearer path from first launch to first successful
  transcript.
- Common environment failures are easier to diagnose without reading source code.

## Phase 6.5: Release Workflow Reliability

Tasks:

- Continue hardening release workflow reruns and existing-release updates.
- Improve workflow observability around release asset creation and update paths.
- Keep dual-artifact validation for CLI and GUI packages.
- Review current GitHub Actions assumptions that are sensitive to timing,
  existing tags, or repeated release attempts.
- Keep packaging docs aligned with the real release behavior.

Acceptance:

- Re-running a release is less fragile than the current create-only path.
- CLI and GUI artifact publication remains verifiable in Actions.

## Phase 6.6: Docs And Verification

Tasks:

- Update workflow docs for the consolidated desktop workspace.
- Update release and installation docs for onboarding and diagnostics changes.
- Keep `dev-state`, `roadmap`, and phase summary docs aligned with shipped
  behavior.
- Add or refresh focused tests for any new library filtering, artifact viewing,
  and release workflow logic.

Acceptance:

- Docs match the actual GUI and release workflow.
- New desktop behavior has focused regression coverage.

## Test Plan

Suggested new or expanded tests:

```text
tests/test_gui_qt_app.py
tests/test_transcript_library.py
tests/test_transcript_reexport.py
tests/test_release_workflow_docs.py
```

Coverage expectations:

- workspace layout and view-state behavior where practical
- transcript library filtering and ordering
- artifact view loading and switching
- onboarding and diagnostics messaging
- release workflow rerun or existing-release handling logic where practical

## Documentation Updates

Update these documents as Phase 6 lands:

- `README.md`
- `docs/gui.md`
- `docs/release-installation.md`
- `docs/packaging.md`
- `docs/release-automation.md`
- `docs/roadmap.md`
- `docs/dev-state.md`

## Immediate Execution Checklist

1. Revisit the `Views` workflow and tighten transcript review layout.
2. Add transcript library filters and stronger sort controls.
3. Improve generated artifact readability and switching behavior.
4. Add first-run guidance and stronger desktop diagnostics.
5. Harden release rerun behavior and release metadata update flow.
6. Update docs and focused tests as Phase 6 changes land.

## Recommended Order

Start with workspace consolidation and library review speed, because those shape
the day-to-day desktop workflow. Then improve artifact inspection and
onboarding, and keep release workflow hardening moving in parallel with feature
work so packaging regressions do not pile up at the end.
