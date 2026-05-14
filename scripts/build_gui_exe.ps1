param(
    [string]$Python = "python",
    [string]$AppName = "FlowScribeGUI",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot $AppName
$RuntimeHook = Join-Path $ProjectRoot "scripts\pyinstaller_gui_runtime_hook.py"
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

Push-Location $ProjectRoot
try {
    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

    Write-Step "Check GUI dependencies"
    & $Python -c "import PySide6; print('PySide6', PySide6.__version__)"
    & $Python -s -m PyInstaller --version

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

    Write-Step "Done"
    Write-Host "GUI release folder: $PackageDir" -ForegroundColor Green
    Write-Host "GUI executable: $exePath" -ForegroundColor Green
}
finally {
    Pop-Location
}
