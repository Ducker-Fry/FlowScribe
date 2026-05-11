# Release Automation

FlowScribe uses GitHub Actions to build and publish Windows release packages automatically.

## What the Release Workflow Does

When a version tag such as `v0.1.1` is pushed, `.github/workflows/release.yml` runs on GitHub-hosted Windows runners and performs the full release flow:

```text
push tag v0.1.1
-> install Python
-> install project dependencies
-> run pytest
-> run ruff
-> install ffmpeg
-> run PyInstaller packaging script
-> verify FlowScribe.exe doctor
-> compress dist/FlowScribe
-> create GitHub Release
-> upload FlowScribe-v0.1.1-windows-x64.zip
```

## Triggering a Release

Update code and documentation first, then commit and push `main`:

```powershell
git status
git add .
git commit -m "Prepare v0.1.1"
git push
```

Create and push a version tag:

```powershell
git tag v0.1.1
git push origin v0.1.1
```

GitHub Actions will build and publish the release.

## Manual Trigger

The workflow also supports manual runs through GitHub Actions with `workflow_dispatch`.

When running manually, provide a version string:

```text
v0.1.1
```

For normal releases, prefer tag-triggered releases because tags give the published artifact a stable source reference.

## Release Asset

The uploaded asset is named:

```text
FlowScribe-v0.1.1-windows-x64.zip
```

The ZIP contains the entire portable application folder:

```text
FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- _internal/
```

Do not distribute only `FlowScribe.exe`. The `_internal` runtime folder and bundled media tools are required.

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
- If GitHub has a temporary checkout or release API failure, rerun the workflow from the Actions page.
