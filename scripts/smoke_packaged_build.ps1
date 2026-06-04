param(
    [string]$CliDir = "dist\\FlowScribe",
    [string]$GuiDir = "dist\\FlowScribeGUI",
    [string]$Model = "tiny"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-PathExists {
    param([string]$PathValue)
    if (-not (Test-Path $PathValue)) {
        throw "Required path was not found: $PathValue"
    }
}

$cliExe = Join-Path $CliDir "FlowScribe.exe"
$guiExe = Join-Path $GuiDir "FlowScribeGUI.exe"
$ffmpegExe = Join-Path $CliDir "ffmpeg.exe"
$smokeAudio = Join-Path $CliDir "smoke-tone.wav"
$smokeOutput = Join-Path $CliDir "smoke-output"

Assert-PathExists -PathValue $cliExe
Assert-PathExists -PathValue $ffmpegExe

if (-not (Test-Path $guiExe)) {
    throw "Required GUI package was not found: $guiExe. Build it first with scripts\\build_gui_exe.ps1."
}

Write-Step "Run packaged CLI doctor"
& $cliExe doctor --skip-model-access
if ($LASTEXITCODE -ne 0) {
    throw "Packaged CLI doctor failed with exit code $LASTEXITCODE"
}

Write-Step "Run packaged GUI self-test"
& $guiExe --self-test
if ($LASTEXITCODE -ne 0) {
    throw "Packaged GUI self-test failed with exit code $LASTEXITCODE"
}

Write-Step "Generate 1-second smoke audio"
& $ffmpegExe -f lavfi -i "sine=frequency=880:duration=1" -ar 16000 -ac 1 -y $smokeAudio
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg smoke audio generation failed with exit code $LASTEXITCODE"
}

Write-Step "Run packaged CLI transcription smoke test"
& $cliExe transcribe $smokeAudio -o $smokeOutput --model $Model --overwrite
if ($LASTEXITCODE -ne 0) {
    throw "Packaged transcription smoke test failed with exit code $LASTEXITCODE"
}

$txtOutput = Join-Path $smokeOutput "smoke-tone.txt"
$mdOutput = Join-Path $smokeOutput "smoke-tone.md"
Assert-PathExists -PathValue $txtOutput
Assert-PathExists -PathValue $mdOutput

Write-Step "Smoke test passed"
Write-Host "CLI doctor, GUI self-test, and packaged transcription smoke test all succeeded." -ForegroundColor Green
