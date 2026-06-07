param(
    [string]$Python = "python",
    [string]$Iscc = "iscc",
    [switch]$OfflineOnly,
    [switch]$OnlineOnly,
    [string]$OnlineVersion = "",
    [ValidateSet("gitee", "github")]
    [string]$ReleaseMirror = "gitee",
    [string]$OnlineBaseUrl = "",
    [string]$OnlineCliUrl = "",
    [string]$OnlineGuiUrl = "",
    [switch]$UseLocalTestFeed,
    [string]$LocalTestFeedBaseUrl = "",
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

function Get-ProjectVersion {
    $pyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
    $content = Get-Content $pyprojectPath -Raw
    $match = [regex]::Match($content, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "Could not determine version from $pyprojectPath"
    }
    return $match.Groups[1].Value
}

function Get-DefaultReleaseBaseUrl {
    param(
        [string]$VersionTag,
        [string]$Mirror
    )

    if ($Mirror -eq "github") {
        return "https://github.com/Ducker-Fry/FlowScribe/releases/download/$VersionTag"
    }

    return "https://gitee.com/Ducker-Fry/FlowScribe/releases/download/$VersionTag"
}

function Resolve-IsccPath {
    param([string]$Requested)

    if ($Requested) {
        return $Requested
    }

    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $commonCandidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $commonCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw 'ISCC.exe was not found. Pass -Iscc with the full path, for example "C:\Program Files (x86)\Inno Setup 6\ISCC.exe".'
}

function New-ReleaseZip {
    param(
        [string]$SourceDir,
        [string]$ZipPath
    )

    if (Test-Path $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    Compress-Archive -LiteralPath $SourceDir -DestinationPath $ZipPath -CompressionLevel Optimal
}

function Get-FileSha256Hex {
    param([string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
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

function Test-PackagedUrlToolExists {
    param([string]$PackageDir)

    return (Test-Path (Join-Path $PackageDir "FlowScribeURL.exe"))
}

function Ensure-ReleasePayloads {
    $cliDir = Join-Path $DistRoot "FlowScribe"
    $guiDir = Join-Path $DistRoot "FlowScribeGUI"

    if (
        -not (Test-Path $cliDir) -or
        -not (Test-PackagedCliInstallCommand) -or
        -not (Test-PackagedUrlToolExists -PackageDir $cliDir)
    ) {
        Write-Step "Build fresh CLI release payload"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $CliBuilder -Python $Python
        if ($LASTEXITCODE -ne 0) {
            throw "CLI packaging failed."
        }
    }

    if (-not (Test-Path $guiDir) -or -not (Test-PackagedUrlToolExists -PackageDir $guiDir)) {
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

function Get-OnlineAssetMetadata {
    $versionCore = if ($OnlineVersion) {
        if ($OnlineVersion.StartsWith("v")) { $OnlineVersion.Substring(1) } else { $OnlineVersion }
    } else {
        Get-ProjectVersion
    }
    $versionTag = if ($OnlineVersion) {
        if ($OnlineVersion.StartsWith("v")) { $OnlineVersion } else { "v$OnlineVersion" }
    } else {
        "v$versionCore"
    }

    $cliZipName = "FlowScribe-$versionCore-windows-x64.zip"
    $guiZipName = "FlowScribeGUI-$versionCore-windows-x64.zip"
    $cliZipPath = Join-Path $DistRoot $cliZipName
    $guiZipPath = Join-Path $DistRoot $guiZipName

    Write-Step "Create release ZIP payloads"
    New-ReleaseZip -SourceDir (Join-Path $DistRoot "FlowScribe") -ZipPath $cliZipPath
    New-ReleaseZip -SourceDir (Join-Path $DistRoot "FlowScribeGUI") -ZipPath $guiZipPath

    $resolvedBaseUrl = $OnlineBaseUrl.TrimEnd('/')
    if ($UseLocalTestFeed) {
        if (-not $LocalTestFeedBaseUrl) {
            throw "Local test feed was requested but -LocalTestFeedBaseUrl was not provided."
        }
        $resolvedBaseUrl = $LocalTestFeedBaseUrl.TrimEnd('/')
    } elseif (-not $OnlineCliUrl -and -not $OnlineGuiUrl) {
        if (-not $resolvedBaseUrl) {
            $resolvedBaseUrl = Get-DefaultReleaseBaseUrl -VersionTag $versionTag -Mirror $ReleaseMirror
        }
    }

    $cliUrl = if ($OnlineCliUrl) { $OnlineCliUrl } else { "$resolvedBaseUrl/$cliZipName" }
    $guiUrl = if ($OnlineGuiUrl) { $OnlineGuiUrl } else { "$resolvedBaseUrl/$guiZipName" }

    [pscustomobject]@{
        VersionTag = $versionTag
        VersionCore = $versionCore
        CliZipName = $cliZipName
        GuiZipName = $guiZipName
        CliZipPath = $cliZipPath
        GuiZipPath = $guiZipPath
        CliSha256 = Get-FileSha256Hex -Path $cliZipPath
        GuiSha256 = Get-FileSha256Hex -Path $guiZipPath
        CliUrl = $cliUrl
        GuiUrl = $guiUrl
        BaseUrl = $resolvedBaseUrl
    }
}

Write-Step "Ensure release payloads are current"
Ensure-ReleasePayloads

$Iscc = Resolve-IsccPath -Requested $Iscc

Write-Step "Build local docs site"
& $Python $DocsBuilder | Out-Host

Write-Step "Verify release folders exist"
$cliDir = Join-Path $DistRoot "FlowScribe"
$guiDir = Join-Path $DistRoot "FlowScribeGUI"
$onlineAssets = Get-OnlineAssetMetadata

Write-Step "Compile Windows installer scripts"
if (Test-Path $InstallerOutputRoot) {
    Get-ChildItem $InstallerOutputRoot -Filter "FlowScribeSetup-*.exe" -ErrorAction SilentlyContinue |
        Remove-Item -Force
}
if (-not $OfflineOnly) {
    & $Iscc `
        "/DOnlineVersion=$($onlineAssets.VersionTag)" `
        "/DOnlineCliZipName=$($onlineAssets.CliZipName)" `
        "/DOnlineGuiZipName=$($onlineAssets.GuiZipName)" `
        "/DOnlineCliUrl=$($onlineAssets.CliUrl)" `
        "/DOnlineGuiUrl=$($onlineAssets.GuiUrl)" `
        "/DOnlineCliSha256=$($onlineAssets.CliSha256)" `
        "/DOnlineGuiSha256=$($onlineAssets.GuiSha256)" `
        (Join-Path $InstallerRoot "FlowScribe-online.iss")
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
