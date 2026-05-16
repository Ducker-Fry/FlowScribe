# Phase 7 Task List

Phase 7 name: Guided Recovery, Comparison, And Session Flow

Target release line: `v0.2.7`

## Target Outcome

Phase 7 should make FlowScribe faster to review, easier to recover, and easier
to reopen after time away. The goal is not a new product category. The goal is
to remove the next layer of friction from a desktop workflow that already has
the right core capabilities.

## Delivery Phases

1. Turn diagnostics into guided recovery actions.
2. Improve artifact comparison for corrected transcript verification.
3. Add stronger library search and session recovery.
4. Productize onboarding inside the GUI.
5. Tighten release and packaging closure.

## Phase 7.1: Guided Error Recovery

Suggested files:

```text
src/flowscribe/gui/qt_app.py
tests/test_gui_qt_app.py
```

Tasks:

- Add direct action buttons from help and diagnostics to the relevant GUI areas.
- Improve repair flows for missing media, stale library entries, and output
  directory issues.
- Make state-file recovery and fallback behavior clearer.
- Keep diagnostics useful without exposing unnecessary environment internals.

Acceptance:

- Users can act on common problems directly from the GUI instead of only reading
  about them.

## Phase 7.2: Structured Artifact Comparison

Tasks:

- Add stronger comparison between transcript JSON and corrected JSON.
- Add easier review paths across transcript JSON, subtitles, Markdown, and text
  exports.
- Surface edited segments more clearly during artifact review.
- Keep comparison inside the current transcript workspace.

Acceptance:

- Users can verify transcript edits and exported outputs faster than a
  quick-switch-only workflow allows today.

## Phase 7.3: Library Search And Session Recovery

Tasks:

- Add library text search.
- Improve reopen and restore flows for recent work.
- Explore restoring more of the last review context safely.
- Keep recent-work and library behavior aligned.

Acceptance:

- Users can find and restore older transcript work more quickly as the local
  library grows.

## Phase 7.4: Onboarding Productization

Tasks:

- Turn first-run guidance into clearer quick-start sections or checklist-style
  guidance.
- Show more concrete examples of where outputs go and what to do next.
- Keep help copy friendly to non-technical users.
- Continue aligning GUI support wording with shared CLI diagnostics.

Acceptance:

- New users can reach a first successful transcript with less ambiguity.

## Phase 7.5: Release And Packaging Closure

Tasks:

- Add more regression checks around release workflow expectations.
- Keep packaging and release docs aligned with the real workflow.
- Add or improve a maintainer-facing release runbook.
- Keep CLI and GUI artifact verification explicit in automation.

Acceptance:

- Release reruns stay reliable, and failures are easier to localize quickly.
