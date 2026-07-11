param(
    [string]$Python = "python",
    [string]$DotNet = "dotnet",
    [string]$VenvPath = ".venv-build",
    [string]$ReleaseName = "FlowScribePortable",
    [switch]$SkipHelperBuild,
    [switch]$SkipClean,
    [switch]$ExpectCodeRefresh
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
$CodeDir = Join-Path $PortableRoot "code"
$StdlibDir = Join-Path $CoreDir "Lib"
$DllDir = Join-Path $CoreDir "DLLs"
$SitePackagesDir = Join-Path $CoreDir "site-packages"
$LauncherDistRoot = Join-Path $BuildRoot "portable-core-dist"
$LauncherWorkRoot = Join-Path $BuildRoot "portable-core-work"
$StageSitePackagesDir = Join-Path $BuildRoot "portable-core-site-packages"
$UserBase = Join-Path $ProjectRoot ".py-user-base"

function Get-ParaformerPackagingSupport {
    param([string]$PythonCmd)

    $checkScript = "import importlib.metadata as metadata; import importlib.util as util; required=(('funasr','funasr'),('modelscope','modelscope'),('torch','torch')); versions=[]; [versions.append(f'{package_name}={metadata.version(package_name)}') if util.find_spec(import_name) is not None else (_ for _ in ()).throw(ModuleNotFoundError(import_name)) for package_name, import_name in required]; import torch, torchaudio, funasr, modelscope; print('; '.join(versions))"

    $output = & $PythonCmd -c $checkScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        return @{
            Available = $true
            Message = ($output | Select-Object -Last 1).ToString().Trim()
        }
    }

    $message = ($output | Select-Object -Last 1)
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = "unknown reason"
    }

    return @{
        Available = $false
        Message = $message.ToString().Trim()
    }
}

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

    $stageSummary = Sync-DirectoryTree `
        -SourceDir $SourceDir `
        -DestinationDir $StageDir `
        -ProjectRoot $ProjectRoot `
        -ExcludeNamePatterns @("flowscribe*", "__editable__*", "*.pth")
    $destinationSummary = Sync-DirectoryTree `
        -SourceDir $StageDir `
        -DestinationDir $DestinationDir `
        -ProjectRoot $ProjectRoot

    return [ordered]@{
        Stage = $stageSummary
        Destination = $destinationSummary
    }
}

function Copy-PythonRuntime {
    param(
        [string]$RuntimeRoot,
        [string]$DestinationCoreDir
    )

    $runtimeFilesSummary = [ordered]@{
        FilesAdded = 0
        FilesUpdated = 0
        FilesUnchanged = 0
    }
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
            $fileSync = Sync-FileIfChanged -SourcePath $sourcePath -DestinationPath (Join-Path $DestinationCoreDir $fileName)
            switch ($fileSync.Status) {
                "added" { $runtimeFilesSummary.FilesAdded += 1 }
                "updated" { $runtimeFilesSummary.FilesUpdated += 1 }
                default { $runtimeFilesSummary.FilesUnchanged += 1 }
            }
        }
    }

    $dllSummary = $null
    $sourceDllDir = Join-Path $RuntimeRoot "DLLs"
    if (Test-Path $sourceDllDir) {
        $dllSummary = Sync-DirectoryTree `
            -SourceDir $sourceDllDir `
            -DestinationDir $DllDir `
            -ProjectRoot $ProjectRoot
    }

    $sourceLibDir = Join-Path $RuntimeRoot "Lib"
    if (-not (Test-Path $sourceLibDir)) {
        throw "Python standard library directory was not found: $sourceLibDir"
    }

    $stdlibSummary = Sync-DirectoryTree `
        -SourceDir $sourceLibDir `
        -DestinationDir $StdlibDir `
        -ProjectRoot $ProjectRoot `
        -ExcludeNames @("site-packages")

    return [ordered]@{
        RuntimeFiles = $runtimeFilesSummary
        Dlls = $dllSummary
        Stdlib = $stdlibSummary
    }
}

function Write-PortableRuntimeSummary {
    param([hashtable]$Summary)

    if ($null -eq $Summary) {
        return
    }

    Write-Host (
        "  Python runtime files: +{0} ~{1} ={2}" -f
        $Summary.RuntimeFiles.FilesAdded,
        $Summary.RuntimeFiles.FilesUpdated,
        $Summary.RuntimeFiles.FilesUnchanged
    ) -ForegroundColor DarkGray

    if ($null -ne $Summary.Dlls) {
        Write-SyncSummary -Label "DLLs" -Summary $Summary.Dlls
    }

    if ($null -ne $Summary.Stdlib) {
        Write-SyncSummary -Label "Lib" -Summary $Summary.Stdlib
    }
}

function Write-CoreLauncherSyncSummary {
    param(
        [string]$LauncherDistRootPath,
        [string]$CoreDirectory
    )

    $launcherSummary = [ordered]@{
        FilesAdded = 0
        FilesUpdated = 0
        FilesUnchanged = 0
    }

    foreach ($fileName in @("gui-core.exe", "cli-core.exe", "FlowScribeURL.exe")) {
        $fileSync = Sync-FileIfChanged `
            -SourcePath (Join-Path $LauncherDistRootPath $fileName) `
            -DestinationPath (Join-Path $CoreDirectory $fileName)
        switch ($fileSync.Status) {
            "added" { $launcherSummary.FilesAdded += 1 }
            "updated" { $launcherSummary.FilesUpdated += 1 }
            default { $launcherSummary.FilesUnchanged += 1 }
        }
    }

    Write-Host (
        "  Core launchers: +{0} ~{1} ={2}" -f
        $launcherSummary.FilesAdded,
        $launcherSummary.FilesUpdated,
        $launcherSummary.FilesUnchanged
    ) -ForegroundColor DarkGray
}

function Get-LatestWriteTimeUtc {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    $latest = Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if ($null -eq $latest) {
        return $null
    }
    return $latest.LastWriteTimeUtc
}

function Write-CodePayloadStatusWarning {
    param(
        [string]$SourceRoot,
        [string]$PortableCodeDir
    )

    if ($ExpectCodeRefresh) {
        return
    }

    if (-not (Test-Path $PortableCodeDir)) {
        Write-Host "  Warning: portable code payload is missing: $PortableCodeDir" -ForegroundColor Yellow
        Write-Host "  Rebuild it with scripts\\build_code_package.ps1 or scripts\\build_gui_exe.ps1." -ForegroundColor Yellow
        return
    }

    $sourceLatest = Get-LatestWriteTimeUtc -Path $SourceRoot
    $codeLatest = Get-LatestWriteTimeUtc -Path $PortableCodeDir
    if ($null -eq $sourceLatest -or $null -eq $codeLatest) {
        return
    }

    if ($sourceLatest -gt $codeLatest) {
        Write-Host "  Warning: portable code payload looks older than src\\flowscribe." -ForegroundColor Yellow
        Write-Host "  gui-core.exe loads code from dist\\FlowScribePortable\\code, not from src directly." -ForegroundColor Yellow
        Write-Host "  Rebuild code with scripts\\build_code_package.ps1 or scripts\\build_gui_exe.ps1." -ForegroundColor Yellow
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

    Write-Step "Check Paraformer packaging runtime"
    $paraformerSupport = Get-ParaformerPackagingSupport -PythonCmd $Python
    if ($paraformerSupport.Available) {
        Write-Host "  Paraformer runtime import check passed ($($paraformerSupport.Message))." -ForegroundColor Green
    } else {
        Write-Host "  Warning: Paraformer runtime is incomplete in packaging Python: $($paraformerSupport.Message)" -ForegroundColor Yellow
        Write-Host "  Packaging will continue, but packaged Paraformer runs may fail until funasr, modelscope, torch, and transitive audio/runtime dependencies are importable together." -ForegroundColor Yellow
    }

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
    $sitePackagesSummary = Mirror-SitePackages `
        -SourceDir $RuntimeSitePackagesDir `
        -StageDir $StageSitePackagesDir `
        -DestinationDir $SitePackagesDir
    Write-SyncSummary -Label "site-packages stage" -Summary $sitePackagesSummary.Stage
    Write-SyncSummary -Label "site-packages core" -Summary $sitePackagesSummary.Destination

    Write-Step "Copy Python runtime and standard library into core"
    $pythonRuntimeSummary = Copy-PythonRuntime -RuntimeRoot $RuntimeRoot -DestinationCoreDir $CoreDir
    Write-PortableRuntimeSummary -Summary $pythonRuntimeSummary

    Write-Step "Sync portable core runtime"
    New-Item -ItemType Directory -Path $CoreDir -Force | Out-Null
    Write-CoreLauncherSyncSummary -LauncherDistRootPath $LauncherDistRoot -CoreDirectory $CoreDir

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
    Write-CodePayloadStatusWarning -SourceRoot (Join-Path $ProjectRoot "src\\flowscribe") -PortableCodeDir $CodeDir
    Write-Host "Portable release root: $PortableRoot" -ForegroundColor Green
    Write-Host "Portable core directory: $CoreDir" -ForegroundColor Green
}
finally {
    Pop-Location
}
