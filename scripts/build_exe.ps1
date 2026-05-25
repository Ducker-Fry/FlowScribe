param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv-build",
    [string]$AppName = "FlowScribe",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

# Set console output encoding to UTF-8 to fix Chinese character display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvFullPath = Join-Path $ProjectRoot $VenvPath
$PythonExe = Join-Path $VenvFullPath "Scripts\python.exe"
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot $AppName
$ReleaseReadme = Join-Path $PackageDir "README-USER.txt"
$UserBase = Join-Path $ProjectRoot ".py-user-base"
$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Copy-Tool {
    param(
        [string]$Name,
        [string]$DestinationDir
    )

    $candidatePaths = New-Object System.Collections.Generic.List[string]

    if ($env:ChocolateyInstall) {
        $chocoLib = Join-Path $env:ChocolateyInstall "lib"
        if (Test-Path $chocoLib) {
            Get-ChildItem -Path $chocoLib -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue |
                ForEach-Object { $candidatePaths.Add($_.FullName) }
        }
    }

    $tool = Get-Command $Name -ErrorAction SilentlyContinue
    if ($tool) {
        $candidatePaths.Add($tool.Source)
    }

    foreach ($candidate in ($candidatePaths | Select-Object -Unique)) {
        if ($candidate -match "\\[Cc]hocolatey\\bin\\") {
            continue
        }

        $pushedLocation = $false
        try {
            Push-Location (Split-Path -Parent $candidate)
            $pushedLocation = $true
            & $candidate -version *> $null
            $exitCode = $LASTEXITCODE
            Pop-Location
            $pushedLocation = $false
            if ($exitCode -ne 0) { continue }

            Copy-Item -LiteralPath $candidate -Destination (Join-Path $DestinationDir "$Name.exe") -Force

            $toolDir = Split-Path -Parent $candidate
            Get-ChildItem -LiteralPath $toolDir -Filter "*.dll" -ErrorAction SilentlyContinue |
                Copy-Item -Destination $DestinationDir -Force

            Write-Host "Copied $Name from $candidate"
            return
        }
        catch {
            if ($pushedLocation) {
                Pop-Location
            }
            continue
        }
    }

    throw "$Name was not found or could not run. Install a working ffmpeg build before packaging."
}

Push-Location $ProjectRoot
try {
    Write-Step "Check build dependencies"
    & $DependencyChecker -Python $Python -CheckPython -CheckFfmpeg -CheckPyInstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

    Write-Step "Create or reuse packaging virtual environment"
    if (-not (Test-Path $PythonExe)) {
        & $Python -m venv $VenvFullPath
    }

    Write-Step "Install project dependencies and PyInstaller"
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install --upgrade setuptools
    & $PythonExe -m pip install --no-build-isolation -e ".[dev]"
    & $PythonExe -m pip install pyinstaller

    if (-not $SkipClean) {
        Write-Step "Clean previous build artifacts"
        if (Test-Path $DistRoot) {
            Remove-Item -LiteralPath $DistRoot -Recurse -Force
        }
        if (Test-Path $BuildRoot) {
            Remove-Item -LiteralPath $BuildRoot -Recurse -Force
        }
    }

    Write-Step "Build one-folder executable"
    & $PythonExe -m PyInstaller `
        --name $AppName `
        --onedir `
        --console `
        --clean `
        --noconfirm `
        --collect-all faster_whisper `
        --collect-all ctranslate2 `
        --collect-all tokenizers `
        --collect-all av `
        --collect-all onnxruntime `
        --hidden-import faster_whisper `
        --hidden-import ctranslate2 `
        --hidden-import tokenizers `
        --hidden-import av `
        --hidden-import onnxruntime `
        --copy-metadata faster-whisper `
        --copy-metadata ctranslate2 `
        --copy-metadata tokenizers `
        --copy-metadata av `
        --copy-metadata onnxruntime `
        "src\flowscribe\__main__.py"

    Write-Step "Copy ffmpeg and ffprobe into release folder"
    Copy-Tool -Name "ffmpeg" -DestinationDir $PackageDir
    Copy-Tool -Name "ffprobe" -DestinationDir $PackageDir

    Write-Step "Generate end-user README"
    @"
FlowScribe Windows Portable
===========================

This folder contains a portable FlowScribe CLI build for Windows.

Quick check:
  .\FlowScribe.exe doctor

Transcribe a local video:
  .\FlowScribe.exe "D:\media\lecture.mp4" -o outputs --model small --preset zh

Transcribe an English video:
  .\FlowScribe.exe "D:\media\english.mp4" -o outputs --model small --language en

Notes:
  - ffmpeg.exe and ffprobe.exe are included in this folder.
  - Whisper models are NOT bundled in the executable.
  - The first transcription with a model may download files from Hugging Face.
  - Use --model tiny only for quick smoke tests.
  - Use --model small or medium for real transcription.
  - Outputs are written to the folder passed with -o, defaulting to outputs.

Legal boundary:
  Use FlowScribe for personal learning, accessibility, research notes, and lawful media processing.
  Do not use it to bypass DRM, crack applications, or redistribute copyrighted transcripts without permission.
"@ | Set-Content -LiteralPath $ReleaseReadme -Encoding UTF8

    Write-Step "Done"
    Write-Host "Release folder: $PackageDir" -ForegroundColor Green
    Write-Host "Executable: $(Join-Path $PackageDir "$AppName.exe")" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next test:"
    Write-Host "  `"$PackageDir\$AppName.exe`" doctor"
}
finally {
    Pop-Location
}
