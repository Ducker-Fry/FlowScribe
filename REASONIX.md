# FlowScribe for Reasonix

## Project Summary

FlowScribe is a Windows-first, local-first transcription toolkit for audio and video.
It has:

- a Python 3.10+ CLI
- a PySide6 desktop GUI
- a native C++ transcription engine
- a .NET 8 WASAPI helper
- PowerShell packaging and release scripts

Primary user value:

- transcribe local files and public URLs
- review and edit transcripts in the GUI
- batch URL and local-file work through Queue
- export reusable text assets such as `txt`, `md`, `json`, `srt`, and `vtt`

## Default Model

Use `deepseek-v4-flash` by default for this repository.
Only suggest switching to a stronger model when the task is unusually cross-cutting, high-risk, or architecture-heavy.

## First Reading Order

Start with:

1. `docs/developer-handoff.md`
2. `docs/dev-state.md`
3. `docs/roadmap.md`

Then read only the modules needed for the task.

## Architectural Guardrails

- Treat `flowscribe.app`, `flowscribe.tasks`, `flowscribe.providers`, and `flowscribe.capabilities` as the stable public API surface.
- Keep core logic decoupled from CLI, GUI, and packaging layers.
- Preserve the layered pipeline shape: input -> media preparation -> transcription/provider -> artifact output.
- For GUI work, preserve the newer `QStackedWidget` architecture built around `NewMainWindow`, `SingleTaskView`, `LibraryView`, and `QueueView`.
- For queue work, preserve persistent JSON queue behavior, title-based URL display, and bookmarklet ingestion flow.
- For long-media work, preserve progressive transcription, chunk overlap handling, resume behavior, and post-pass deduplication.

## Working Style

- Make focused changes; do not refactor unrelated areas opportunistically.
- Prefer small, targeted reads instead of loading huge parts of the repo.
- Do not edit vendored third-party code under `native/flowscribe-engine/third_party/` unless the user explicitly asks.
- Do not touch `dist/`, `build/`, `out/`, generated logs, or release artifacts unless the task is packaging-related.
- Prefer updating tests alongside behavior changes.
- For bug fixes, add or adjust the narrowest regression test that proves the fix.
- For architecture or API changes, explain the tradeoff before making broad edits.

## Validation Preferences

- Prefer focused checks such as:
  - `python -m pytest tests/test_file.py`
  - `python -m ruff check src tests`
  - `python -m flowscribe --help`
- Avoid large noisy test runs by default.
- The user prefers to run heavyweight builds and full test suites themselves unless explicitly asked otherwise.

## High-Value Areas

- `src/flowscribe/core/`
- `src/flowscribe/app/`
- `src/flowscribe/transcription/`
- `src/flowscribe/gui/views/`
- `src/flowscribe/tasks/`
- `src/flowscribe/input/`
- `src/flowscribe/output/`
- `tests/`

## Task Routing Hints

- CLI or pipeline issues: read `src/flowscribe/app/`, `core/`, `transcription/`, `input/`, `output/`
- GUI issues: read `src/flowscribe/gui/new_main_window.py`, `gui/views/`, `gui/dialogs/`, `gui/workers/`
- Queue issues: read `src/flowscribe/tasks/`, queue-related GUI files, and bookmarklet/server integration
- Packaging or Windows runtime issues: read `scripts/`, `installer/`, `tools/wasapi-capture-helper/`, and packaging docs

## Common Risks

- Breaking public API contracts in the four stable packages
- Regressing Windows-specific behavior
- Mixing GUI concerns into core pipeline code
- Regressing long-audio chunk merge or deduplication behavior
- Running broad commands that generate excessive output or take a long time without user need
