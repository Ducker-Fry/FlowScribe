# Project Process

FlowScribe will follow a lightweight enterprise-style process: enough structure to stay maintainable, without slowing down early validation.

## 1. Vision

Build an open-source, local-first tool that converts media into readable transcripts for learning, research, review, and downstream AI analysis.

## 2. Version Scope

Each version must have a small, testable goal.

### v0.1 MVP

- Accept local media files.
- Extract or normalize audio.
- Run local transcription.
- Export raw transcripts to TXT and Markdown.
- Support single-file and batch workflows.

### Later Versions

- URL ingestion.
- System audio capture.
- Desktop GUI.
- External transcription API providers.
- Searchable transcript library.

## 3. Development Workflow

1. Define the user scenario.
2. Write or update requirements.
3. Design the module boundary.
4. Implement a small vertical slice.
5. Test with real media samples.
6. Document commands and limitations.
7. Tag or record the version change.

## 4. Engineering Principles

- Prefer stable, boring architecture over clever shortcuts.
- Keep the command-line workflow usable before building GUI layers.
- Separate input acquisition, media processing, transcription, and output writing.
- Do not couple the application to a single transcription provider.
- Make failures visible and recoverable during batch processing.
- Keep first-party code responsible for orchestration, not for reimplementing mature media engines.

## 5. Quality Gates

Before a version is considered complete, it should pass:

- Single local video test.
- Single local audio test.
- Batch folder test.
- Chinese speech test.
- English speech test.
- Mixed-language test when available.
- Bad input test.
- Output format inspection for TXT and Markdown.

## 6. Open Source Readiness

Before public release, the project should include:

- README with clear installation and usage.
- License.
- Contribution guide.
- Example commands.
- Test plan.
- Architecture document.
- Changelog.
- Clear statement of legal and ethical boundaries.
