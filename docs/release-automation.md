# Release Automation

FlowScribe uses GitHub Actions to build and publish Windows release packages automatically.

## What the Release Workflow Does

When a version tag such as `v0.2.6` is pushed, `.github/workflows/release.yml` runs on GitHub-hosted Windows runners and performs the full release flow:

```text
push tag v0.2.6
-> check out the tagged release ref
-> verify the workflow is building the expected tag contents
-> install Python
-> install .NET
-> install project dependencies
-> run pytest
-> run ruff
-> install ffmpeg
-> run CLI PyInstaller packaging script
-> build and bundle WasapiCaptureHelper.exe
-> run GUI PyInstaller packaging script
-> verify FlowScribe.exe doctor
-> verify WasapiCaptureHelper.exe version
-> verify WasapiCaptureHelper.exe probe
-> verify FlowScribeGUI.exe --self-test
-> compress dist/FlowScribe
-> compress dist/FlowScribeGUI
-> inspect existing GitHub Release state
-> create or update GitHub Release metadata
-> upload or overwrite FlowScribe-v0.2.6-windows-x64.zip
-> upload or overwrite FlowScribeGUI-v0.2.6-windows-x64.zip
-> summarize final release URL and asset list
```

## Triggering a Release

Update code and documentation first, then commit and push `main`:

```powershell
git status
git add .
git commit -m "Prepare v0.2.6"
git push
```

Create and push a version tag:

```powershell
git tag v0.2.6
git push origin v0.2.6
```

GitHub Actions will build and publish the release.

## Manual Trigger

The workflow also supports manual runs through GitHub Actions with `workflow_dispatch`.

When running manually, provide a version string:

```text
v0.2.6
```

For normal releases, prefer tag-triggered releases because tags give the published artifact a stable source reference.
Manual runs should point at an existing release tag. The workflow now checks out the
requested tag ref and verifies that `HEAD` matches that tag before it builds.

## Release Asset

The uploaded assets are:

```text
FlowScribe-v0.2.6-windows-x64.zip
FlowScribeGUI-v0.2.6-windows-x64.zip
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
|-- WasapiCaptureHelper.exe
|-- NAudio*.dll
`-- _internal/
```

Do not distribute only `FlowScribe.exe` or `FlowScribeGUI.exe`. The runtime folders and bundled media tools are required.

## Permissions

The workflow uses:

```yaml
permissions:
  contents: write
```

This allows GitHub Actions to create a Release, update an existing Release, and upload assets using the repository's built-in `GITHUB_TOKEN`.

## Rerun Behavior

The release workflow now uses a create-or-update path instead of assuming every
run is the first run for that tag.

- If the GitHub Release does not exist yet, the workflow creates the release
  record and then uploads assets.
- If the GitHub Release already exists, the workflow updates the release title
  and notes, then uploads assets with overwrite enabled.
- Asset uploads use `gh release upload --clobber`, so reruns can replace the CLI
  and GUI ZIPs without failing on existing asset names.
- The workflow logs whether it is creating or updating the release, and it prints
  the final release URL plus the asset names that GitHub sees after upload.

## Notes

- The workflow only runs automatically for tags matching `v*.*.*`.
- Whisper models are not bundled in the release zip.
- First use of a selected model may download model files from Hugging Face.
- The workflow verifies the packaged executable with `FlowScribe.exe doctor` before creating the release.
- The workflow verifies the packaged WASAPI helper with `WasapiCaptureHelper.exe version` and `WasapiCaptureHelper.exe probe`.
- The workflow verifies the packaged GUI entry point with `FlowScribeGUI.exe --self-test`.
- If GitHub has a temporary checkout or release API failure, rerun the workflow from the Actions page. The rerun path should now update the existing release instead of failing on duplicate creation.
