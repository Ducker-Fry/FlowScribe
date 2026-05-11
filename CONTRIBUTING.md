# Contributing

Thanks for your interest in FlowScribe. The project is still early, so contributions are most useful when they keep the core workflow reliable and the architecture easy to extend.

## Project Direction

FlowScribe is a local-first media transcription tool. The current scope is:

- Local audio/video files.
- Local faster-whisper transcription.
- TXT and Markdown output.
- Windows portable release.

The project should not add features intended to bypass DRM, crack client applications, or redistribute protected transcripts without permission.

## Development Setup

```powershell
git clone https://github.com/Ducker-Fry/FlowScribe.git
cd FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Check the environment:

```powershell
flowscribe doctor
```

## Quality Checks

Before opening a pull request, run:

```powershell
python -m pytest
python -m ruff check src tests
```

For packaging-related changes, also run:

```powershell
.\scripts\build_exe.ps1
.\dist\FlowScribe\FlowScribe.exe doctor
```

## Contribution Workflow

1. Open an issue for larger changes before implementation.
2. Keep each pull request focused on one feature, fix, or documentation improvement.
3. Add tests for behavior changes.
4. Update README or docs for user-visible changes.
5. Keep CLI, core, media, transcription, and output responsibilities separated.

## Architecture Guidelines

- Keep the CLI thin.
- Put orchestration in `core`.
- Add new input methods as adapters under `src/flowscribe/input`.
- Add new transcription engines under `src/flowscribe/transcription`.
- Add new output formats under `src/flowscribe/output`.
- Avoid making GUI or future desktop code depend directly on low-level media/transcription implementations.

## Good First Contributions

- Documentation improvements.
- Better error messages.
- More unit tests.
- Additional output formats such as SRT or VTT.
- More robust packaging checks.

## Not Currently Accepted

- DRM bypassing.
- Client cracking.
- Bulk scraping of protected content.
- Features that require uploading user media by default.
- Large rewrites without prior discussion.
