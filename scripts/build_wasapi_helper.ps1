param(
    [string]$DotNet = "dotnet",
    [string]$Configuration = "Release",
    [string]$RuntimeIdentifier = "win-x64",
    [string]$OutputDir = "",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$HelperProject = Join-Path $ProjectRoot "tools\wasapi-capture-helper\src\WasapiCaptureHelper\WasapiCaptureHelper.csproj"
$DefaultOutputDir = Join-Path $ProjectRoot "build\wasapi-helper"
$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = $DefaultOutputDir
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-InProject {
    param([string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($ProjectRoot)
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean path outside project: $resolved"
    }
}

Push-Location $ProjectRoot
try {
    Write-Step "Check build dependencies"
    & $DependencyChecker -DotNet $DotNet -CheckDotNet
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    if (-not (Test-Path $HelperProject)) {
        throw "WASAPI helper project was not found: $HelperProject"
    }

    if (-not $SkipClean) {
        Write-Step "Clean previous WASAPI helper staging output"
        Assert-InProject -Path $OutputDir
        if (Test-Path $OutputDir) {
            Remove-Item -LiteralPath $OutputDir -Recurse -Force
        }
    }

    Write-Step "Publish WASAPI helper"
    & $DotNet publish $HelperProject `
        -c $Configuration `
        -r $RuntimeIdentifier `
        --self-contained false `
        -o $OutputDir
    if ($LASTEXITCODE -ne 0) {
        throw "dotnet publish failed for WASAPI helper."
    }

    $helperExe = Join-Path $OutputDir "WasapiCaptureHelper.exe"
    if (-not (Test-Path $helperExe)) {
        throw "Expected WASAPI helper executable was not created: $helperExe"
    }

    Write-Step "Smoke test WASAPI helper"
    & $helperExe version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "WASAPI helper version smoke test failed."
    }

    Write-Step "Done"
    Write-Host "WASAPI helper staging folder: $OutputDir" -ForegroundColor Green
    Write-Host "WASAPI helper executable: $helperExe" -ForegroundColor Green
}
finally {
    Pop-Location
}
