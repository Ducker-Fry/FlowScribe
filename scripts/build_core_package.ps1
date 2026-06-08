param(
    [string]$Python = "python",
    [string]$DotNet = "dotnet",
    [string]$VenvPath = ".venv-build",
    [string]$ReleaseName = "FlowScribePortable",
    [switch]$SkipHelperBuild,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "packaging_common.ps1")

$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"
$HelperBuildScript = Join-Path $PSScriptRoot "build_wasapi_helper.ps1"
$HelperStageDir = Join-Path $ProjectRoot "build\wasapi-helper"
$HelperSourceRoot = Join-Path $ProjectRoot "tools\wasapi-capture-helper"
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PortableRoot = Join-Path $DistRoot $ReleaseName
$CoreDir = Join-Path $PortableRoot "core"
$StdlibDir = Join-Path $CoreDir "Lib"
$DllDir = Join-Path $CoreDir "DLLs"
$SitePackagesDir = Join-Path $CoreDir "site-packages"
$LauncherDistRoot = Join-Path $BuildRoot "portable-core-dist"
$LauncherWorkRoot = Join-Path $BuildRoot "portable-core-work"
$StageSitePackagesDir = Join-Path $BuildRoot "portable-core-site-packages"
$UserBase = Join-Path $ProjectRoot ".py-user-base"

function Test-DirectoryHasNewerFiles {
    param(
        [string]$Path,
        [datetime]$ReferenceTime
    )

    if (-not (Test-Path $Path)) {
        return $false
    }

    return [bool](Get-ChildItem -LiteralPath $Path -Recurse -File |
        Where-Object { $_.LastWriteTimeUtc -gt $ReferenceTime } |
        Select-Object -First 1)
}

function Test-WasapiHelperRebuildRequired {
    $helperExe = Join-Path $HelperStageDir "WasapiCaptureHelper.exe"
    if (-not (Test-Path $helperExe)) {
        return $true
    }

    $helperExeWriteTime = (Get-Item -LiteralPath $helperExe).LastWriteTimeUtc
    return (Test-DirectoryHasNewerFiles -Path $HelperSourceRoot -ReferenceTime $helperExeWriteTime)
}

function Build-PortableLauncher {
    param(
        [string]$PythonExe,
        [string]$Name,
        [string]$ScriptPath,
        [switch]$Windowed
    )

    $args = @(
        "-m",
        "PyInstaller",
        "--name", $Name,
        "--onefile",
        "--noconfirm",
        "--distpath", $LauncherDistRoot,
        "--workpath", $LauncherWorkRoot
    )

    if ($Windowed) {
        $args += "--windowed"
        $iconPath = Join-Path $ProjectRoot "icons\flowscribe.ico"
        if (Test-Path $iconPath) {
            $args += @("--icon", $iconPath)
        }
    } else {
        $args += "--console"
    }

    if (-not $SkipClean) {
        $args += "--clean"
    }

    $args += $ScriptPath

    $exitCode = Invoke-LoggedNativeCommand `
        -FilePath $PythonExe `
        -ArgumentList $args `
        -WorkingDirectory $ProjectRoot
    $exePath = Join-Path $LauncherDistRoot "$Name.exe"
    if (-not (Test-Path $exePath)) {
        throw "Expected launcher executable was not created: $exePath"
    }
    if ($exitCode -ne 0) {
        Write-Host "  Warning: PyInstaller returned exit code $exitCode, but $exePath was created successfully. Continuing packaging." -ForegroundColor Yellow
    }
}

function Mirror-SitePackages {
    param(
        [string]$SourceDir,
        [string]$StageDir,
        [string]$DestinationDir
    )

    Remove-ProjectItemIfExists -Path $StageDir -ProjectRoot $ProjectRoot
    New-Item -ItemType Directory -Path $StageDir -Force | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        if (
            $item.Name -like "flowscribe*" -or
            $item.Name -like "__editable__*" -or
            $item.Name -like "*.pth"
        ) {
            continue
        }

        $stagePath = Join-Path $StageDir $item.Name
        if ($item.PSIsContainer) {
            Copy-Item -LiteralPath $item.FullName -Destination $stagePath -Recurse -Force
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $stagePath -Force
        }
    }

    Remove-ProjectItemIfExists -Path $DestinationDir -ProjectRoot $ProjectRoot
    Copy-Item -LiteralPath $StageDir -Destination $DestinationDir -Recurse -Force
}

function Copy-PythonRuntime {
    param(
        [string]$RuntimeRoot,
        [string]$DestinationCoreDir
    )

    $runtimeFiles = @(
        "python.exe",
        "pythonw.exe",
        "python3.dll",
        "python312.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll"
    )

    foreach ($fileName in $runtimeFiles) {
        $sourcePath = Join-Path $RuntimeRoot $fileName
        if (Test-Path $sourcePath) {
            [void](Sync-FileIfChanged -SourcePath $sourcePath -DestinationPath (Join-Path $DestinationCoreDir $fileName))
        }
    }

    $sourceDllDir = Join-Path $RuntimeRoot "DLLs"
    if (Test-Path $sourceDllDir) {
        Remove-ProjectItemIfExists -Path $DllDir -ProjectRoot $ProjectRoot
        Copy-Item -LiteralPath $sourceDllDir -Destination $DllDir -Recurse -Force
    }

    $sourceLibDir = Join-Path $RuntimeRoot "Lib"
    if (-not (Test-Path $sourceLibDir)) {
        throw "Python standard library directory was not found: $sourceLibDir"
    }

    Remove-ProjectItemIfExists -Path $StdlibDir -ProjectRoot $ProjectRoot
    New-Item -ItemType Directory -Path $StdlibDir -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $sourceLibDir -Force) {
        if ($item.Name -eq "site-packages") {
            continue
        }
        $destinationPath = Join-Path $StdlibDir $item.Name
        if ($item.PSIsContainer) {
            Copy-Item -LiteralPath $item.FullName -Destination $destinationPath -Recurse -Force
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $destinationPath -Force
        }
    }
}

function Write-RunScript {
    param(
        [string]$Path,
        [string]$ExecutableName
    )

    @"
@echo off
setlocal
"%~dp0core\$ExecutableName" %*
"@ | Set-Content -LiteralPath $Path -Encoding ASCII
}

Push-Location $ProjectRoot
try {
    Write-Step "Check build dependencies"
    & $DependencyChecker -Python $Python -DotNet $DotNet -CheckPython -CheckDotNet -CheckFfmpeg
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

    $PythonExe = Ensure-PackagingVenv -Python $Python -ProjectRoot $ProjectRoot -VenvPath $VenvPath -RequirePyInstaller
    $RuntimeRoot = Get-PythonRuntimeRoot -Python $Python
    $RuntimeSitePackagesDir = Get-PythonSitePackagesPath -Python $Python

    if (-not $SkipHelperBuild) {
        if (Test-WasapiHelperRebuildRequired) {
            Write-Step "Build WASAPI helper"
            & $HelperBuildScript -DotNet $DotNet
            if ($LASTEXITCODE -ne 0) {
                throw "WASAPI helper build failed."
            }
        } else {
            Write-Step "Reuse WASAPI helper staging output"
            Write-Host "  Reusing $HelperStageDir because helper sources did not change." -ForegroundColor Green
        }
    } elseif (-not (Test-Path (Join-Path $HelperStageDir "WasapiCaptureHelper.exe"))) {
        throw "WASAPI helper staging output is missing. Run scripts\build_wasapi_helper.ps1 first."
    }

    if (-not $SkipClean) {
        Write-Step "Clean portable launcher work directories"
        Remove-ProjectItemIfExists -Path $LauncherWorkRoot -ProjectRoot $ProjectRoot
        Remove-ProjectItemIfExists -Path $LauncherDistRoot -ProjectRoot $ProjectRoot
    }

    Write-Step "Build GUI core launcher"
    Build-PortableLauncher `
        -PythonExe $PythonExe `
        -Name "gui-core" `
        -ScriptPath "scripts\portable_gui_launcher.py" `
        -Windowed

    Write-Step "Build CLI core launcher"
    Build-PortableLauncher `
        -PythonExe $PythonExe `
        -Name "cli-core" `
        -ScriptPath "scripts\portable_cli_launcher.py"

    Write-Step "Build URL core launcher"
    Build-PortableLauncher `
        -PythonExe $PythonExe `
        -Name "FlowScribeURL" `
        -ScriptPath "scripts\portable_url_launcher.py"

    Write-Step "Mirror third-party runtime site-packages into core"
    Mirror-SitePackages `
        -SourceDir $RuntimeSitePackagesDir `
        -StageDir $StageSitePackagesDir `
        -DestinationDir $SitePackagesDir

    Write-Step "Copy Python runtime and standard library into core"
    Copy-PythonRuntime -RuntimeRoot $RuntimeRoot -DestinationCoreDir $CoreDir

    Write-Step "Sync portable core runtime"
    New-Item -ItemType Directory -Path $CoreDir -Force | Out-Null
    [void](Sync-FileIfChanged -SourcePath (Join-Path $LauncherDistRoot "gui-core.exe") -DestinationPath (Join-Path $CoreDir "gui-core.exe"))
    [void](Sync-FileIfChanged -SourcePath (Join-Path $LauncherDistRoot "cli-core.exe") -DestinationPath (Join-Path $CoreDir "cli-core.exe"))
    [void](Sync-FileIfChanged -SourcePath (Join-Path $LauncherDistRoot "FlowScribeURL.exe") -DestinationPath (Join-Path $CoreDir "FlowScribeURL.exe"))

    Write-Step "Copy ffmpeg and ffprobe into portable core"
    Copy-Tool -Name "ffmpeg" -DestinationDir $CoreDir
    Copy-Tool -Name "ffprobe" -DestinationDir $CoreDir

    Write-Step "Copy WASAPI helper into portable core"
    Copy-WasapiHelper -SourceDir $HelperStageDir -DestinationDir $CoreDir

    Write-Step "Write portable launch scripts"
    New-Item -ItemType Directory -Path $PortableRoot -Force | Out-Null
    Write-RunScript -Path (Join-Path $PortableRoot "run-gui.bat") -ExecutableName "gui-core.exe"
    Write-RunScript -Path (Join-Path $PortableRoot "run-cli.bat") -ExecutableName "cli-core.exe"

    Write-Step "Done"
    Write-Host "Portable release root: $PortableRoot" -ForegroundColor Green
    Write-Host "Portable core directory: $CoreDir" -ForegroundColor Green
}
finally {
    Pop-Location
}
