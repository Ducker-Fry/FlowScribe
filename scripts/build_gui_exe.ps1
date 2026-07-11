param(
    [string]$Python = "python",
    [string]$AppName = "FlowScribeGUI",
    [string]$DotNet = "dotnet",
    [switch]$IncludeBundledModels,
    [switch]$SkipBundledModels,
    [switch]$SkipHelperBuild,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$CoreBuilder = Join-Path $PSScriptRoot "build_core_package.ps1"
$CodeBuilder = Join-Path $PSScriptRoot "build_code_package.ps1"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PortableRoot = Join-Path $ProjectRoot "dist\FlowScribePortable"

if ($AppName -ne "FlowScribeGUI") {
    Write-Host "Ignoring legacy -AppName parameter value '$AppName'. The unified portable package now builds dist\\FlowScribePortable." -ForegroundColor Yellow
}

& $CoreBuilder -Python $Python -DotNet $DotNet -SkipHelperBuild:$SkipHelperBuild -SkipClean:$SkipClean
if ($LASTEXITCODE -ne 0) {
    throw "Portable core build failed."
}

$codeArgs = @{
    Python = $Python
}
if (-not $SkipBundledModels) {
    $codeArgs["IncludeBundledModels"] = $true
}
& $CodeBuilder @codeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Portable code build failed."
}

Write-Host ""
Write-Host "Unified portable package is ready at: $PortableRoot" -ForegroundColor Green
Write-Host "Launch GUI with: $(Join-Path $PortableRoot "run-gui.bat")" -ForegroundColor Green
