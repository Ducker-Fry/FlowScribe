param(
    [string]$Python = "python",
    [string]$Iscc = "iscc",
    [switch]$OfflineOnly,
    [switch]$OnlineOnly,
    [string]$SignTool = "",
    [string]$CertificateSha1 = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$InstallerRoot = Join-Path $ProjectRoot "installer"
$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$DocsBuilder = Join-Path $ProjectRoot "scripts\build_docs_site.py"
$CliBuilder = Join-Path $ProjectRoot "scripts\build_exe.ps1"
$GuiBuilder = Join-Path $ProjectRoot "scripts\build_gui_exe.ps1"
$InstallerOutputRoot = Join-Path $InstallerRoot "build\installer"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-SignIfConfigured {
    param([string]$Path)

    if (-not $SignTool -or -not $CertificateSha1) {
        return
    }
    if (-not (Test-Path $Path)) {
        throw "Cannot sign missing file: $Path"
    }

    Write-Host "Signing $Path" -ForegroundColor Yellow
    & $SignTool sign /sha1 $CertificateSha1 /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool failed for $Path"
    }
}

function Test-PackagedCliInstallCommand {
    $cliExe = Join-Path $DistRoot "FlowScribe\FlowScribe.exe"
    if (-not (Test-Path $cliExe)) {
        return $false
    }

    $probeModels = Join-Path $env:TEMP "flowscribe-installer-probe-models"
    $probeDocs = Join-Path $env:TEMP "flowscribe-installer-probe-docs"
    $arguments = @(
        "install",
        "--json",
        "write-config",
        "--scope", "user",
        "--models-dir", $probeModels,
        "--docs-dir", $probeDocs,
        "--component", "cli"
    )

    $stdoutPath = Join-Path $env:TEMP "flowscribe-installer-probe-stdout.txt"
    $stderrPath = Join-Path $env:TEMP "flowscribe-installer-probe-stderr.txt"
    try {
        if (Test-Path $stdoutPath) {
            Remove-Item -LiteralPath $stdoutPath -Force
        }
        if (Test-Path $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force
        }

        $process = Start-Process `
            -FilePath $cliExe `
            -ArgumentList $arguments `
            -PassThru `
            -Wait `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath
        return ($process.ExitCode -eq 0)
    }
    finally {
        if (Test-Path $stdoutPath) {
            Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Ensure-ReleasePayloads {
    $cliDir = Join-Path $DistRoot "FlowScribe"
    $guiDir = Join-Path $DistRoot "FlowScribeGUI"

    if (-not (Test-Path $cliDir) -or -not (Test-PackagedCliInstallCommand)) {
        Write-Step "Build fresh CLI release payload"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $CliBuilder -Python $Python
        if ($LASTEXITCODE -ne 0) {
            throw "CLI packaging failed."
        }
    }

    if (-not (Test-Path $guiDir)) {
        Write-Step "Build fresh GUI release payload"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $GuiBuilder -Python $Python
        if ($LASTEXITCODE -ne 0) {
            throw "GUI packaging failed."
        }
    }

    if (-not (Test-PackagedCliInstallCommand)) {
        throw "Packaged CLI does not support installer commands after rebuild."
    }
}

Write-Step "Ensure release payloads are current"
Ensure-ReleasePayloads

Write-Step "Build local docs site"
& $Python $DocsBuilder | Out-Host

Write-Step "Verify release folders exist"
$cliDir = Join-Path $DistRoot "FlowScribe"
$guiDir = Join-Path $DistRoot "FlowScribeGUI"

Write-Step "Compile Windows installer scripts"
if (Test-Path $InstallerOutputRoot) {
    Get-ChildItem $InstallerOutputRoot -Filter "FlowScribeSetup-*.exe" -ErrorAction SilentlyContinue |
        Remove-Item -Force
}
if (-not $OfflineOnly) {
    & $Iscc (Join-Path $InstallerRoot "FlowScribe-online.iss")
}
if (-not $OnlineOnly) {
    & $Iscc (Join-Path $InstallerRoot "FlowScribe-offline.iss")
}

Write-Step "Optional code signing"
Invoke-SignIfConfigured -Path (Join-Path $cliDir "FlowScribe.exe")
Invoke-SignIfConfigured -Path (Join-Path $guiDir "FlowScribeGUI.exe")
$helperExe = Join-Path $guiDir "WasapiCaptureHelper.exe"
if (Test-Path $helperExe) {
    Invoke-SignIfConfigured -Path $helperExe
}
$offlineInstaller = Join-Path $BuildRoot "installer\FlowScribeSetup-offline-x64.exe"
$onlineInstaller = Join-Path $BuildRoot "installer\FlowScribeSetup-online-x64.exe"
if (Test-Path $offlineInstaller) {
    Invoke-SignIfConfigured -Path $offlineInstaller
}
if (Test-Path $onlineInstaller) {
    Invoke-SignIfConfigured -Path $onlineInstaller
}
