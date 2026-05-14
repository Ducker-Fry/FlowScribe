# Release Automation

FlowScribe uses GitHub Actions to build and publish Windows release packages automatically.

## What the Release Workflow Does

When a version tag such as `v0.2.3` is pushed, `.github/workflows/release.yml` runs on GitHub-hosted Windows runners and performs the full release flow:

```text
push tag v0.2.3
-> install Python
-> install project dependencies
-> run pytest
-> run ruff
-> install ffmpeg
-> run CLI PyInstaller packaging script
-> run GUI PyInstaller packaging script
-> verify FlowScribe.exe doctor
-> verify FlowScribeGUI.exe --self-test
-> compress dist/FlowScribe
-> compress dist/FlowScribeGUI
-> create GitHub Release
-> upload FlowScribe-v0.2.3-windows-x64.zip
-> upload FlowScribeGUI-v0.2.3-windows-x64.zip
```

## Triggering a Release

Update code and documentation first, then commit and push `main`:

```powershell
git status
git add .
git commit -m "Prepare v0.2.3"
git push
```

Create and push a version tag:

```powershell
git tag v0.2.3
git push origin v0.2.3
```

GitHub Actions will build and publish the release.

## Manual Trigger

The workflow also supports manual runs through GitHub Actions with `workflow_dispatch`.

When running manually, provide a version string:

```text
v0.2.3
```

For normal releases, prefer tag-triggered releases because tags give the published artifact a stable source reference.

## Release Asset

The uploaded assets are:

```text
FlowScribe-v0.2.3-windows-x64.zip
FlowScribeGUI-v0.2.3-windows-x64.zip
```

The CLI ZIP contains the entire portable application folder:

```text
FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- _internal/
```

The GUI ZIP contains:

```text
FlowScribeGUI/
|-- FlowScribeGUI.exe
`-- _internal/
```

Do not distribute only `FlowScribe.exe` or `FlowScribeGUI.exe`. The runtime folders and bundled media tools are required.

## Permissions

The workflow uses:

```yaml
permissions:
  contents: write
```

This allows GitHub Actions to create a Release and upload assets using the repository's built-in `GITHUB_TOKEN`.

## Notes

- The workflow only runs automatically for tags matching `v*.*.*`.
- Whisper models are not bundled in the release zip.
- First use of a selected model may download model files from Hugging Face.
- The workflow verifies the packaged executable with `FlowScribe.exe doctor` before creating the release.
- The workflow verifies the packaged GUI entry point with `FlowScribeGUI.exe --self-test`.
- If GitHub has a temporary checkout or release API failure, rerun the workflow from the Actions page.
