param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv-build",
    [string]$AppName = "FlowScribeURL",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvFullPath = Join-Path $ProjectRoot $VenvPath
$PythonExe = Join-Path $VenvFullPath "Scripts\python.exe"
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot $AppName
$SingleExePath = Join-Path $DistRoot "$AppName.exe"
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
        Write-Step "Clean previous URL build artifacts"
        if (Test-Path $PackageDir) {
            Remove-Item -LiteralPath $PackageDir -Recurse -Force
        }
        if (Test-Path $SingleExePath) {
            Remove-Item -LiteralPath $SingleExePath -Force
        }
        $UrlBuildDir = Join-Path $BuildRoot $AppName
        if (Test-Path $UrlBuildDir) {
            Remove-Item -LiteralPath $UrlBuildDir -Recurse -Force
        }
    }

    Write-Step "Build standalone URL executable"
    & $PythonExe -m PyInstaller --clean --noconfirm ".\FlowScribeURL.spec"

    if (-not (Test-Path $SingleExePath)) {
        throw "PyInstaller did not create $SingleExePath"
    }

    New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
    Copy-Item -LiteralPath $SingleExePath -Destination (Join-Path $PackageDir "$AppName.exe") -Force

    Write-Step "Copy ffmpeg and ffprobe into release folder"
    Copy-Tool -Name "ffmpeg" -DestinationDir $PackageDir
    Copy-Tool -Name "ffprobe" -DestinationDir $PackageDir

    Write-Step "Generate end-user README"
    @"
FlowScribeURL Windows Portable
==============================

This folder contains the standalone FlowScribe URL acquisition tool.

Quick checks:
  .\FlowScribeURL.exe version
  .\FlowScribeURL.exe inspect https://example.com/video

Download remote audio:
  .\FlowScribeURL.exe download https://example.com/video -o outputs\url-downloads

Notes:
  - ffmpeg.exe and ffprobe.exe are included in this folder.
  - This tool does not run transcription.
  - Use it to inspect URL strategy or download media for later processing.
"@ | Set-Content -LiteralPath $ReleaseReadme -Encoding UTF8

    Write-Step "Done"
    Write-Host "Release folder: $PackageDir" -ForegroundColor Green
    Write-Host "Executable: $(Join-Path $PackageDir "$AppName.exe")" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next test:"
    Write-Host "  `"$PackageDir\$AppName.exe`" version"
}
finally {
    Pop-Location
}
