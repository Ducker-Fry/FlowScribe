param(
    [string]$CliDir = "dist\\FlowScribe",
    [string]$GuiDir = "dist\\FlowScribeGUI",
    [string]$PortableRoot = "dist\\FlowScribePortable",
    [string]$Model = "tiny",
    [string]$ParaformerSample = "samples\\chinese_test.wav",
    [switch]$SkipParaformer
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
$portableCoreDir = Join-Path $PortableRoot "core"
$portableCliExe = Join-Path $portableCoreDir "cli-core.exe"
$portableGuiExe = Join-Path $portableCoreDir "gui-core.exe"
$portableModelsDir = Join-Path $PortableRoot "models"
$paraformerOutput = Join-Path $PortableRoot "paraformer-smoke-output"

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

if (-not $SkipParaformer) {
    Write-Step "Run packaged Paraformer smoke test"
    Assert-PathExists -PathValue $portableCliExe
    Assert-PathExists -PathValue $portableGuiExe
    Assert-PathExists -PathValue $ParaformerSample
    Assert-PathExists -PathValue (Join-Path $portableModelsDir "paraformer-zh\\tokens.json")
    Assert-PathExists -PathValue (Join-Path $portableModelsDir "paraformer-zh\\am.mvn")
    Assert-PathExists -PathValue (Join-Path $portableModelsDir "ct-punc\\tokens.json")
    Assert-PathExists -PathValue (Join-Path $portableModelsDir "ct-punc\\jieba.c.dict")
    Assert-PathExists -PathValue (Join-Path $portableModelsDir "ct-punc\\jieba_usr_dict")

    & $portableGuiExe --self-test
    if ($LASTEXITCODE -ne 0) {
        throw "Portable GUI self-test failed with exit code $LASTEXITCODE"
    }

    & $portableCliExe transcribe $ParaformerSample -o $paraformerOutput --provider paraformer --model paraformer-zh --overwrite
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged Paraformer smoke test failed with exit code $LASTEXITCODE"
    }

    $paraformerTxtOutput = Join-Path $paraformerOutput "chinese_test.txt"
    Assert-PathExists -PathValue $paraformerTxtOutput
}

Write-Step "Smoke test passed"
Write-Host "CLI doctor, GUI self-test, packaged transcription smoke test, and Paraformer smoke test all succeeded." -ForegroundColor Green
