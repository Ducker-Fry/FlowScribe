# Contributing

FlowScribe is currently in early project setup. Contributions should preserve the core design goals: local-first operation, clear module boundaries, and extensibility.

## Development Guidelines

- Keep changes small and focused.
- Add or update documentation when behavior changes.
- Prefer explicit interfaces between modules.
- Avoid coupling CLI, GUI, media processing, and transcription provider code.
- Do not add functionality intended to bypass DRM or protected media controls.

## Local Development

The detailed setup command will be finalized after the first implementation slice. The intended workflow is:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
pytest
```
