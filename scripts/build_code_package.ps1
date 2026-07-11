param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv-build",
    [string]$ReleaseName = "FlowScribePortable",
    [switch]$IncludeBundledModels
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "packaging_common.ps1")

$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"
$DocsBuilder = Join-Path $PSScriptRoot "build_docs_site.py"
$CodeBuilder = Join-Path $PSScriptRoot "build_code_package.py"
$PortableRoot = Join-Path (Join-Path $ProjectRoot "dist") $ReleaseName
$UserBase = Join-Path $ProjectRoot ".py-user-base"

Push-Location $ProjectRoot
try {
    Write-Step "Check build dependencies"
    & $DependencyChecker -Python $Python -CheckPython
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

    Write-Step "Build local docs site"
    & $Python $DocsBuilder
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build local docs site."
    }

    Write-Step "Build portable code payload"
    $args = @(
        $CodeBuilder,
        "--release-root",
        $PortableRoot
    )
    if ($IncludeBundledModels) {
        $args += "--include-bundled-models"
    }
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build portable code payload."
    }

    Write-Step "Done"
    Write-Host "Portable release root: $PortableRoot" -ForegroundColor Green
    Write-Host "Portable code directory: $(Join-Path $PortableRoot "code")" -ForegroundColor Green
}
finally {
    Pop-Location
}
