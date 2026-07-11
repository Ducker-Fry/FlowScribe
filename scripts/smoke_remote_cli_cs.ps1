param(
    [string]$RootDir = ".",
    [string]$PythonExe = "python",
    [string]$Host = "127.0.0.1",
    [int]$Port = 18769,
    [string]$ApiToken = "secret",
    [string]$ServerProfile = "local-test",
    [string]$SampleMedia = "samples\english_test.wav",
    [string]$Url = "https://www.bilibili.com/video/BV1PC4y1G7T5/?spm_id_from=333.337.search-card.all.click&vd_source=6dc67897b1c1ee5b41ec9718c3060026"
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

function Invoke-FlowScribeJson {
    param([string[]]$Arguments)
    $raw = & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "FlowScribe command failed with exit code $LASTEXITCODE: $($Arguments -join ' ')"
    }
    return $raw | ConvertFrom-Json
}

function Wait-RemoteServerReady {
    param(
        [string]$BaseUrl,
        [string]$Token,
        [System.Diagnostics.Process]$ServerProcess
    )

    $headers = @{ Authorization = "Bearer $Token" }
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        if ($ServerProcess.HasExited) {
            throw "FlowScribe server exited early with code $($ServerProcess.ExitCode)."
        }
        try {
            $info = Invoke-RestMethod -Uri "$BaseUrl/v1/server" -Headers $headers -TimeoutSec 3
            if ($info.capabilities.remote_blob -and $info.capabilities.artifacts) {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Timed out waiting for remote server readiness: $BaseUrl"
}

$workspace = (Resolve-Path $RootDir).Path
$sampleMediaPath = (Resolve-Path (Join-Path $workspace $SampleMedia)).Path
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runRoot = Join-Path $workspace ".smoke\remote-cli-cs\$runId"
$configDir = Join-Path $runRoot "config"
$serverOutputDir = Join-Path $runRoot "server-out"
$clientOutputDir = Join-Path $runRoot "client-out"
$clientUrlOutputDir = Join-Path $runRoot "client-out-url"
$logsDir = Join-Path $runRoot "logs"
$queueStorePath = Join-Path $runRoot "batch-queue.json"
$serverStdoutLog = Join-Path $logsDir "server.stdout.log"
$serverStderrLog = Join-Path $logsDir "server.stderr.log"
$baseUrl = "http://$Host:$Port"
$serverProcess = $null
$originalConfigDir = $env:FLOWSCRIBE_CONFIG_DIR

New-Item -ItemType Directory -Force -Path $configDir, $serverOutputDir, $clientOutputDir, $clientUrlOutputDir, $logsDir | Out-Null

try {
    $env:FLOWSCRIBE_CONFIG_DIR = $configDir

    Write-Step "Start remote FlowScribe server"
    $serverArgs = @(
        "-m", "flowscribe",
        "serve",
        "--host", $Host,
        "--port", "$Port",
        "--api-token", $ApiToken,
        "--queue-store", $queueStorePath,
        "-o", $serverOutputDir,
        "--format", "json"
    )
    $serverProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $serverArgs `
        -WorkingDirectory $workspace `
        -RedirectStandardOutput $serverStdoutLog `
        -RedirectStandardError $serverStderrLog `
        -WindowStyle Hidden `
        -PassThru

    Wait-RemoteServerReady -BaseUrl $baseUrl -Token $ApiToken -ServerProcess $serverProcess

    Write-Step "Register isolated remote server profile"
    & $PythonExe -m flowscribe remote add-server $ServerProfile --url $baseUrl --token $ApiToken
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add remote profile: $ServerProfile"
    }

    Write-Step "Run local-file upload remote transcription"
    $transcribePayload = Invoke-FlowScribeJson -Arguments @(
        "-m", "flowscribe",
        "transcribe", $sampleMediaPath,
        "--execution", "remote",
        "--server", $ServerProfile,
        "-o", $clientOutputDir,
        "--format", "json",
        "--json",
        "--non-interactive"
    )

    if (-not $transcribePayload.ok) {
        throw "Remote local-file transcription returned ok=false."
    }
    if ($transcribePayload.outputs.Count -lt 1) {
        throw "Remote local-file transcription returned no outputs."
    }
    $localOutput = $transcribePayload.outputs[0]
    Assert-PathExists -PathValue $localOutput.json_path
    if ($localOutput.source_kind -ne "local") {
        throw "Expected local source_kind, got: $($localOutput.source_kind)"
    }
    if ($localOutput.source_value -ne $sampleMediaPath) {
        throw "Expected source_value to be original client path."
    }
    if ($localOutput.source_locator -ne $sampleMediaPath) {
        throw "Expected source_locator to be original client path."
    }
    if ($localOutput.original_filename -ne [System.IO.Path]::GetFileName($sampleMediaPath)) {
        throw "Expected original_filename to match uploaded file name."
    }

    Write-Step "Run URL remote transcription"
    $urlPayload = Invoke-FlowScribeJson -Arguments @(
        "-m", "flowscribe",
        "url", $Url,
        "--execution", "remote",
        "--server", $ServerProfile,
        "-o", $clientUrlOutputDir,
        "--format", "json",
        "--json",
        "--non-interactive"
    )

    if (-not $urlPayload.ok) {
        throw "Remote URL transcription returned ok=false."
    }
    if ($urlPayload.outputs.Count -lt 1) {
        throw "Remote URL transcription returned no outputs."
    }
    $urlOutput = $urlPayload.outputs[0]
    Assert-PathExists -PathValue $urlOutput.json_path
    if ($urlOutput.source_kind -ne "url") {
        throw "Expected url source_kind, got: $($urlOutput.source_kind)"
    }
    if ($urlOutput.source_value -ne $Url) {
        throw "Expected source_value to remain the original URL."
    }
    if ([string]::IsNullOrWhiteSpace($urlOutput.transcription_strategy)) {
        throw "Expected transcription_strategy to be populated for URL remote result."
    }

    Write-Step "Remote CLI CS smoke test passed"
    Write-Host "Run root: $runRoot" -ForegroundColor Green
    Write-Host "Server log: $serverStdoutLog" -ForegroundColor Green
}
finally {
    if ($serverProcess -ne $null -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
    if ($ServerProfile) {
        & $PythonExe -m flowscribe remote remove-server $ServerProfile | Out-Null
    }
    if ($null -eq $originalConfigDir) {
        Remove-Item Env:FLOWSCRIBE_CONFIG_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:FLOWSCRIBE_CONFIG_DIR = $originalConfigDir
    }
}
