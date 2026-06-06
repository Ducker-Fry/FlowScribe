#!/usr/bin/env pwsh
<#
.SYNOPSIS
    FlowScribe environment setup — install via pip and resolve system dependencies.
.DESCRIPTION
    Installs flowscribe (with optional GUI extras) into a virtual environment,
    detects or installs ffmpeg/ffprobe, and optionally builds the WASAPI helper.
#>

param(
    [switch]$Gui,
    [switch]$Dev,
    [switch]$NoVenv,
    [switch]$SkipFfmpeg,
    [switch]$SkipWasapi,
    [string]$Python = "python",
    [string]$DotNet = "dotnet"
)

$ErrorActionPreference = "Stop"

function Write-Step { Write-Host "`n==> $($args[0])" -ForegroundColor Cyan }
function Write-Ok   { Write-Host "    $($args[0])" -ForegroundColor Green }
function Write-Warn { Write-Host "    $($args[0])" -ForegroundColor Yellow }

# ----- Python version check -----
Write-Step "Check Python version"
$pyVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or [version]$pyVersion -lt [version]"3.10") {
    Write-Host "ERROR: Python 3.10+ required, found $pyVersion" -ForegroundColor Red
    exit 1
}
Write-Ok "Python $pyVersion"

# ----- Determine extras -----
$extras = @()
if ($Gui) { $extras += "gui" }
if ($Dev) { $extras += "dev" }
$extrasSpec = if ($extras.Count -gt 0) { "[$($extras -join ',')]" } else { "" }

# ----- Create virtual environment -----
if (-not $NoVenv) {
    $venvDir = Join-Path (Get-Location) ".venv"
    if (-not (Test-Path $venvDir)) {
        Write-Step "Create virtual environment at $venvDir"
        & $Python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw "Failed to create venv" }
    }
    # Determine activate script path
    $activate = Join-Path $venvDir "Scripts\Activate.ps1"
    if (Test-Path $activate) {
        Write-Step "Activate virtual environment"
        . $activate
        $Python = (Get-Command python).Source
        Write-Ok "Using Python: $Python"
    } else {
        Write-Warn "Activate script not found at $activate — continuing with system Python"
    }
}

# ----- Install flowscribe -----
Write-Step "Install flowscribe$extrasSpec via pip"
& $Python -m pip install --upgrade pip
$packageArgs = if (Test-Path (Join-Path (Get-Location) "pyproject.toml")) {
    # Local source install (when running from repo checkout)
    if ($extras.Count -gt 0) {
        @("-e", ".[{0}]" -f ($extras -join ","))
    } else {
        @("-e", ".")
    }
} else {
    # PyPI install
    @("flowscribe$extrasSpec")
}
& $Python -m pip install @packageArgs
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ----- Verify CLI -----
Write-Step "Verify flowscribe CLI"
& $Python -m flowscribe --help *>&1 | Select-Object -First 5
if ($LASTEXITCODE -ne 0) { throw "CLI smoke test failed" }
Write-Ok "CLI works"

# ----- ffmpeg detection / install -----
if (-not $SkipFfmpeg) {
    Write-Step "Check ffmpeg and ffprobe"
    $ffmpegOk = $false
    $ffprobeOk = $false

    # Check PATH first
    $ffmpegPath = (Get-Command "ffmpeg" -ErrorAction SilentlyContinue).Source
    $ffprobePath = (Get-Command "ffprobe" -ErrorAction SilentlyContinue).Source
    if ($ffmpegPath) { $ffmpegOk = $true; Write-Ok "ffmpeg found at: $ffmpegPath" }
    if ($ffprobePath) { $ffprobeOk = $true; Write-Ok "ffprobe found at: $ffprobePath" }

    if (-not $ffmpegOk -or -not $ffprobeOk) {
        # Try installing via winget (Windows 11 / modern Windows 10)
        $winget = Get-Command "winget" -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Step "Install ffmpeg via winget (requires admin)"
            & winget install ffmpeg --accept-package-agreements --accept-source-agreements *>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "ffmpeg installed via winget — restart terminal or log out to update PATH"
                # Try to find the installed location
                $ffmpegPath = (Get-Command "ffmpeg" -ErrorAction SilentlyContinue).Source
                $ffprobePath = (Get-Command "ffprobe" -ErrorAction SilentlyContinue).Source
                if ($ffmpegPath) { $ffmpegOk = $true }
                if ($ffprobePath) { $ffprobeOk = $true }
            } else {
                Write-Warn "winget install failed — install ffmpeg manually from https://ffmpeg.org/download.html"
            }
        } else {
            Write-Warn "winget not available — install ffmpeg manually from https://ffmpeg.org/download.html"
        }
    }

    if ($ffmpegOk -and $ffprobeOk) {
        Write-Ok "ffmpeg/ffprobe ready"
    } else {
        Write-Warn "ffmpeg/ffprobe not fully available — transcription requires them"
    }
}

# ----- WASAPI helper (optional, GUI system-audio capture) -----
if (-not $SkipWasapi -and $Gui) {
    $helperDir = Join-Path (Get-Location) "tools\wasapi-capture-helper"
    if (Test-Path $helperDir) {
        $buildScript = Join-Path (Get-Location) "scripts\build_wasapi_helper.ps1"
        if (Test-Path $buildScript) {
            Write-Step "Build WASAPI capture helper (.NET 8 required)"
            try {
                & $buildScript -DotNet $DotNet
                if ($LASTEXITCODE -eq 0) {
                    Write-Ok "WASAPI helper built"
                    # Copy helper binaries alongside flowscribe-gui entry
                    $helperStage = Join-Path (Get-Location) "build\wasapi-helper"
                    $pythonLib = Split-Path (Split-Path $Python) -Parent
                    $sitePkgs = Join-Path $pythonLib "Lib\site-packages\flowscribe\media"
                    if (Test-Path $helperStage -and (Get-Command "flowscribe-gui" -ErrorAction SilentlyContinue)) {
                        Copy-Item "$helperStage\*" $sitePkgs -Force -ErrorAction SilentlyContinue
                        Write-Ok "WASAPI helper copied to flowscribe package"
                    }
                } else {
                    Write-Warn "WASAPI helper build failed — install .NET 8 SDK and retry"
                }
            } catch {
                Write-Warn "WASAPI helper build skipped: $_"
            }
        }
    }
}

# ----- Verify -----
Write-Step "Run flowscribe doctor"
try {
    & $Python -m flowscribe doctor *>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Environment looks good"
    } else {
        Write-Warn "doctor reported issues; review the output above before first use"
    }
} catch {
    Write-Warn "doctor check skipped (not critical)"
}

Write-Step "Done"
Write-Host @"

FlowScribe installed successfully!
  CLI:    flowscribe --help
  GUI:    flowscribe gui    (or flowscribe-gui)

Next steps:
  - Transcribe a file:   flowscribe transcribe D:\media\file.mp4 -o outputs
  - Inspect a URL:       flowscribe inspect https://example.com/video
  - Run diagnostics:     flowscribe doctor

For GUI extras:  pip install flowscribe[gui]
For development:  pip install flowscribe[dev]
"@ -ForegroundColor Green
