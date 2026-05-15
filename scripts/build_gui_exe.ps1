param(
    [string]$Python = "python",
    [string]$AppName = "FlowScribeGUI",
    [string]$DotNet = "dotnet",
    [switch]$SkipHelperBuild,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot $AppName
$RuntimeHook = Join-Path $ProjectRoot "scripts\pyinstaller_gui_runtime_hook.py"
$HelperBuildScript = Join-Path $ProjectRoot "scripts\build_wasapi_helper.ps1"
$HelperStageDir = Join-Path $ProjectRoot "build\wasapi-helper"
$UserBase = Join-Path $ProjectRoot ".py-user-base"

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

function Copy-WasapiHelper {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    $helperExe = Join-Path $SourceDir "WasapiCaptureHelper.exe"
    if (-not (Test-Path $helperExe)) {
        throw "WASAPI helper was not found in staging output: $helperExe"
    }

    Get-ChildItem -LiteralPath $SourceDir -File |
        Copy-Item -Destination $DestinationDir -Force

    $packagedHelper = Join-Path $DestinationDir "WasapiCaptureHelper.exe"
    if (-not (Test-Path $packagedHelper)) {
        throw "WASAPI helper was not copied into GUI package: $packagedHelper"
    }

    & $packagedHelper version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged WASAPI helper version smoke test failed."
    }
}

Push-Location $ProjectRoot
try {
    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

    Write-Step "Check GUI dependencies"
    & $Python -c "import PySide6; print('PySide6', PySide6.__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "PySide6 is not installed in the selected Python environment."
    }
    & $Python -s -m PyInstaller --version
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed in the selected Python environment."
    }

    if (-not $SkipHelperBuild) {
        Write-Step "Build WASAPI helper"
        & $HelperBuildScript -DotNet $DotNet
        if ($LASTEXITCODE -ne 0) {
            throw "WASAPI helper build failed."
        }
    }
    elseif (-not (Test-Path (Join-Path $HelperStageDir "WasapiCaptureHelper.exe"))) {
        throw "WASAPI helper staging output is missing. Run scripts\build_wasapi_helper.ps1 first."
    }

    if (-not $SkipClean) {
        Write-Step "Clean previous GUI build artifacts"
        Assert-InProject -Path $PackageDir
        if (Test-Path $PackageDir) {
            Remove-Item -LiteralPath $PackageDir -Recurse -Force
        }

        $guiBuildDir = Join-Path $BuildRoot $AppName
        Assert-InProject -Path $guiBuildDir
        if (Test-Path $guiBuildDir) {
            Remove-Item -LiteralPath $guiBuildDir -Recurse -Force
        }
    }

    Write-Step "Build GUI one-folder executable"
    & $Python -s -m PyInstaller `
        --name $AppName `
        --onedir `
        --windowed `
        --clean `
        --noconfirm `
        --runtime-hook $RuntimeHook `
        --hidden-import PySide6.QtCore `
        --hidden-import PySide6.QtGui `
        --hidden-import PySide6.QtMultimedia `
        --hidden-import PySide6.QtMultimediaWidgets `
        --hidden-import PySide6.QtWidgets `
        "src\flowscribe\gui\__main__.py"

    $exePath = Join-Path $PackageDir "$AppName.exe"
    if (-not (Test-Path $exePath)) {
        throw "Expected GUI executable was not created: $exePath"
    }

    Write-Step "Copy WASAPI helper into GUI release folder"
    Copy-WasapiHelper -SourceDir $HelperStageDir -DestinationDir $PackageDir

    Write-Step "Done"
    Write-Host "GUI release folder: $PackageDir" -ForegroundColor Green
    Write-Host "GUI executable: $exePath" -ForegroundColor Green
}
finally {
    Pop-Location
}
