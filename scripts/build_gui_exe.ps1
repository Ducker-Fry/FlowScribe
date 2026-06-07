param(
    [string]$Python = "python",
    [string]$AppName = "FlowScribeGUI",
    [string]$DotNet = "dotnet",
    [switch]$IncludeBundledModels,
    [switch]$SkipHelperBuild,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

# Set console output encoding to UTF-8 to fix Chinese character display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot $AppName
$PyInstallerDistRoot = Join-Path $BuildRoot "pyinstaller-dist"
$PyInstallerWorkRoot = Join-Path $BuildRoot "pyinstaller-work"
$PyInstallerStageDir = Join-Path $PyInstallerDistRoot $AppName
$PyInstallerWorkDir = Join-Path $PyInstallerWorkRoot $AppName
$UrlBuilder = Join-Path $ProjectRoot "scripts\build_url_exe.ps1"
$UrlToolPackageDir = Join-Path $DistRoot "FlowScribeURL"
$RuntimeHook = Join-Path $ProjectRoot "scripts\pyinstaller_gui_runtime_hook.py"
$HelperBuildScript = Join-Path $ProjectRoot "scripts\build_wasapi_helper.ps1"
$HelperStageDir = Join-Path $ProjectRoot "build\wasapi-helper"
$UserBase = Join-Path $ProjectRoot ".py-user-base"
$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"
$ModelsSourceDir = Join-Path $ProjectRoot "models"
$HelperSourceRoot = Join-Path $ProjectRoot "tools\wasapi-capture-helper"

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

function Remove-ProjectItemIfExists {
    param([string]$Path)

    Assert-InProject -Path $Path
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Test-FileCopyRequired {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    if (-not (Test-Path $DestinationPath)) {
        return $true
    }

    $sourceItem = Get-Item -LiteralPath $SourcePath
    $destinationItem = Get-Item -LiteralPath $DestinationPath
    if ($sourceItem.Length -ne $destinationItem.Length) {
        return $true
    }

    return $sourceItem.LastWriteTimeUtc -ne $destinationItem.LastWriteTimeUtc
}

function Sync-FileIfChanged {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    if (-not (Test-Path $SourcePath)) {
        throw "Source file was not found: $SourcePath"
    }

    $destinationDir = Split-Path -Parent $DestinationPath
    if (-not [string]::IsNullOrWhiteSpace($destinationDir)) {
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }

    if (Test-FileCopyRequired -SourcePath $SourcePath -DestinationPath $DestinationPath) {
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
        return $true
    }

    return $false
}

function Sync-DirectoryContents {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    if (-not (Test-Path $SourceDir)) {
        throw "Source directory was not found: $SourceDir"
    }

    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $destinationPath = Join-Path $DestinationDir $item.Name
        if ($item.PSIsContainer) {
            Remove-ProjectItemIfExists -Path $destinationPath
            Copy-Item -LiteralPath $item.FullName -Destination $destinationPath -Recurse -Force
        } else {
            [void](Sync-FileIfChanged -SourcePath $item.FullName -DestinationPath $destinationPath)
        }
    }
}

function Sync-TopLevelFilesIfChanged {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    if (-not (Test-Path $SourceDir)) {
        throw "Source directory was not found: $SourceDir"
    }

    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -File) {
        [void](Sync-FileIfChanged -SourcePath $item.FullName -DestinationPath (Join-Path $DestinationDir $item.Name))
    }
}

function Test-PathMatchesAnyPattern {
    param(
        [string]$Name,
        [string[]]$Patterns
    )

    foreach ($pattern in $Patterns) {
        if ($Name -like $pattern) {
            return $true
        }
    }

    return $false
}

function Remove-NonPreservedPackageItems {
    param(
        [string]$PackagePath,
        [string[]]$PreservePatterns
    )

    if (-not (Test-Path $PackagePath)) {
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $PackagePath -Force) {
        if (Test-PathMatchesAnyPattern -Name $item.Name -Patterns $PreservePatterns) {
            continue
        }

        Remove-ProjectItemIfExists -Path $item.FullName
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

function Copy-Tool {
    param(
        [string]$Name,
        [string]$DestinationDir
    )

    $candidatePaths = New-Object System.Collections.Generic.List[string]

    if ($env:ChocolateyInstall) {
        $chocoLib = Join-Path $env:ChocolateyInstall "lib"
        if (Test-Path $chocoLib) {
            Get-ChildItem -Path $chocoLib -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue |
                ForEach-Object { $candidatePaths.Add($_.FullName) }
        }
    }

    $tool = Get-Command $Name -ErrorAction SilentlyContinue
    if ($tool) {
        $candidatePaths.Add($tool.Source)
    }

    foreach ($candidate in ($candidatePaths | Select-Object -Unique)) {
        if ($candidate -match "\\[Cc]hocolatey\\bin\\") {
            continue
        }

        $pushedLocation = $false
        try {
            Push-Location (Split-Path -Parent $candidate)
            $pushedLocation = $true
            & $candidate -version *> $null
            $exitCode = $LASTEXITCODE
            Pop-Location
            $pushedLocation = $false
            if ($exitCode -ne 0) { continue }

            [void](Sync-FileIfChanged -SourcePath $candidate -DestinationPath (Join-Path $DestinationDir "$Name.exe"))

            $toolDir = Split-Path -Parent $candidate
            Get-ChildItem -LiteralPath $toolDir -Filter "*.dll" -ErrorAction SilentlyContinue |
                ForEach-Object {
                    [void](Sync-FileIfChanged -SourcePath $_.FullName -DestinationPath (Join-Path $DestinationDir $_.Name))
                }

            Write-Host "Synced $Name from $candidate"
            return
        }
        catch {
            if ($pushedLocation) {
                Pop-Location
            }
            continue
        }
    }

    throw "$Name was not found or could not run. Install a working ffmpeg build before packaging."
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

    Sync-TopLevelFilesIfChanged -SourceDir $SourceDir -DestinationDir $DestinationDir

    $packagedHelper = Join-Path $DestinationDir "WasapiCaptureHelper.exe"
    if (-not (Test-Path $packagedHelper)) {
        throw "WASAPI helper was not copied into GUI package: $packagedHelper"
    }

    & $packagedHelper version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged WASAPI helper version smoke test failed."
    }
}

function Stop-RunningFlowScribeProcesses {
    $runningProcesses = Get-Process | Where-Object { $_.ProcessName -like "*FlowScribe*" }
    if (-not $runningProcesses) {
        return
    }

    Write-Host "  Found running FlowScribe processes. Attempting to close..." -ForegroundColor Yellow
    foreach ($proc in $runningProcesses) {
        Write-Host "    Closing process: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
        try {
            $proc.CloseMainWindow() | Out-Null
            Start-Sleep -Milliseconds 500
            if (-not $proc.HasExited) {
                Write-Host "    Process did not exit gracefully, forcing termination..." -ForegroundColor Yellow
                $proc.Kill()
            }
            Write-Host "    Process closed successfully" -ForegroundColor Green
        }
        catch {
            Write-Host "    Warning: Could not close process: $_" -ForegroundColor Yellow
        }
    }

    Start-Sleep -Seconds 1
}

function Assert-PackagedParaformerRuntime {
    param([string]$DestinationDir)

    $funasrDir = Join-Path $DestinationDir "_internal\funasr"
    $modelscopeDir = Join-Path $DestinationDir "_internal\modelscope"
    if (-not (Test-Path $funasrDir)) {
        throw "Packaged GUI is missing FunASR runtime directory: $funasrDir"
    }
    if (-not (Test-Path $modelscopeDir)) {
        throw "Packaged GUI is missing ModelScope runtime directory: $modelscopeDir"
    }
}

function Ensure-UrlToolSibling {
    if (-not (Test-Path (Join-Path $UrlToolPackageDir "FlowScribeURL.exe"))) {
        Write-Step "Build standalone URL tool"
        & $UrlBuilder -Python $Python -SkipClean
        if ($LASTEXITCODE -ne 0) {
            throw "Standalone URL tool packaging failed."
        }
    }

    $sourceExe = Join-Path $UrlToolPackageDir "FlowScribeURL.exe"
    [void](Sync-FileIfChanged -SourcePath $sourceExe -DestinationPath (Join-Path $PackageDir "FlowScribeURL.exe"))
    Write-Host "Synced FlowScribeURL.exe into $PackageDir"
}

function Get-ParaformerPackagingSupport {
    param([string]$PythonCmd)

    $checkScript = @'
import importlib.metadata as metadata
import importlib.util as util

required = {
    "funasr": "funasr",
    "modelscope": "modelscope",
    "torch": "torch",
}

versions = {}
for package_name, module_name in required.items():
    try:
        versions[package_name] = metadata.version(package_name)
    except metadata.PackageNotFoundError:
        print(f"missing package metadata: {package_name}")
        raise SystemExit(1)

    if util.find_spec(module_name) is None:
        print(f"missing import spec: {module_name}")
        raise SystemExit(1)

try:
    import torch  # noqa: F401
    import funasr
    import modelscope
except Exception as exc:
    print(f"runtime import failed: {exc.__class__.__name__}: {exc}")
    raise SystemExit(1)

print(
    "funasr={0}; modelscope={1}; torch={2}".format(
        versions["funasr"],
        versions["modelscope"],
        versions["torch"],
    )
)
'@

    $output = $checkScript | & $PythonCmd - 2>&1
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

function Write-AppendedLogLines {
    param(
        [string]$Path,
        [ref]$LineCount
    )

    if (-not (Test-Path $Path)) {
        return
    }

    $lines = Get-Content -LiteralPath $Path
    for ($i = $LineCount.Value; $i -lt $lines.Count; $i++) {
        Write-Host $lines[$i]
    }
    $LineCount.Value = $lines.Count
}

function Invoke-LoggedNativeCommand {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    $stdoutPath = Join-Path $env:TEMP "flowscribe-native-stdout.log"
    $stderrPath = Join-Path $env:TEMP "flowscribe-native-stderr.log"

    foreach ($logPath in @($stdoutPath, $stderrPath)) {
        if (Test-Path $logPath) {
            Remove-Item -LiteralPath $logPath -Force
        }
    }

    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $ArgumentList `
            -WorkingDirectory $WorkingDirectory `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $stdoutLineCount = 0
        $stderrLineCount = 0
        while (-not $process.HasExited) {
            Write-AppendedLogLines -Path $stdoutPath -LineCount ([ref]$stdoutLineCount)
            Write-AppendedLogLines -Path $stderrPath -LineCount ([ref]$stderrLineCount)
            Start-Sleep -Milliseconds 500
            $process.Refresh()
        }

        $process.WaitForExit()
        Write-AppendedLogLines -Path $stdoutPath -LineCount ([ref]$stdoutLineCount)
        Write-AppendedLogLines -Path $stderrPath -LineCount ([ref]$stderrLineCount)
        return $process.ExitCode
    }
    finally {
        foreach ($logPath in @($stdoutPath, $stderrPath)) {
            if (Test-Path $logPath) {
                Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Push-Location $ProjectRoot
try {
    Write-Step "Check build dependencies"
    & $DependencyChecker -Python $Python -DotNet $DotNet -CheckPython -CheckDotNet -CheckFfmpeg -CheckPyInstaller -CheckPySide6 -CheckParaformer
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

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
    }
    elseif (-not (Test-Path (Join-Path $HelperStageDir "WasapiCaptureHelper.exe"))) {
        throw "WASAPI helper staging output is missing. Run scripts\build_wasapi_helper.ps1 first."
    }

    if (-not $SkipClean) {
        Write-Step "Clean previous GUI build artifacts"
        Remove-ProjectItemIfExists -Path $PyInstallerWorkDir
    }

    Remove-ProjectItemIfExists -Path $PyInstallerStageDir

    Write-Step "Build GUI one-folder executable"
    Write-Step "Check optional Paraformer packaging support"
    $paraformerSupport = Get-ParaformerPackagingSupport -PythonCmd $Python
    if ($paraformerSupport.Available) {
        Write-Host "  Paraformer runtime will be bundled ($($paraformerSupport.Message))." -ForegroundColor Green
    } else {
        Write-Host "  Skipping Paraformer runtime bundling: $($paraformerSupport.Message)" -ForegroundColor Yellow
    }

    # Check if icon file exists
    $IconPath = Join-Path $ProjectRoot "icons\flowscribe.ico"
    if (-not (Test-Path $IconPath)) {
        Write-Host "  Warning: Icon file not found at $IconPath" -ForegroundColor Yellow
        Write-Host "  Run 'python scripts/convert_icon.py' to create it" -ForegroundColor Yellow
        $IconArg = @()
    } else {
        Write-Host "  Using icon: $IconPath" -ForegroundColor Green
        $IconArg = @("--icon", $IconPath)
    }

    $PyInstallerArgs = @(
        "-s",
        "-m",
        "PyInstaller",
        "--name", $AppName,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--distpath", $PyInstallerDistRoot,
        "--workpath", $PyInstallerWorkRoot,
        "--runtime-hook", $RuntimeHook,
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtMultimedia",
        "--hidden-import", "PySide6.QtMultimediaWidgets",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtSvg",
        "--add-data", "icons;icons",
        "--add-data", "src\flowscribe\gui\themes;flowscribe\gui\themes",
        "--add-data", "src\flowscribe\gui\assets;flowscribe\gui\assets"
    )

    if ($paraformerSupport.Available) {
        $PyInstallerArgs += @(
            "--hidden-import", "funasr",
            "--hidden-import", "modelscope",
            "--collect-all", "funasr",
            "--collect-all", "modelscope"
        )
    }

    if (-not $SkipClean) {
        $PyInstallerArgs += "--clean"
    }

    if ($IconArg.Count -gt 0) {
        $PyInstallerArgs += $IconArg
    }

    $PyInstallerArgs += "src\flowscribe\gui\__main__.py"

    New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
    $exePath = Join-Path $PackageDir "$AppName.exe"
    $pyInstallerExitCode = Invoke-LoggedNativeCommand `
        -FilePath $Python `
        -ArgumentList $PyInstallerArgs `
        -WorkingDirectory $ProjectRoot
    $stagedExePath = Join-Path $PyInstallerStageDir "$AppName.exe"
    if (-not (Test-Path $stagedExePath)) {
        throw "PyInstaller failed for GUI packaging and no staged executable was created: $stagedExePath"
    }
    if ($pyInstallerExitCode -ne 0) {
        Write-Host "  Warning: PyInstaller returned exit code $pyInstallerExitCode, but the GUI executable was created successfully. Continuing packaging." -ForegroundColor Yellow
    }

    Write-Step "Sync staged GUI payload into release folder"
    Stop-RunningFlowScribeProcesses
    try {
        Remove-NonPreservedPackageItems -PackagePath $PackageDir -PreservePatterns @(
            "ffmpeg.exe",
            "ffprobe.exe",
            "FlowScribeURL.exe",
            "WasapiCaptureHelper.exe",
            "WasapiCaptureHelper.dll",
            "WasapiCaptureHelper.deps.json",
            "WasapiCaptureHelper.runtimeconfig.json",
            "WasapiCaptureHelper.pdb",
            "NAudio*.dll"
        )
        Sync-DirectoryContents -SourceDir $PyInstallerStageDir -DestinationDir $PackageDir
    } catch {
        Write-Host "  Error: Cannot update $PackageDir" -ForegroundColor Red
        Write-Host "  Please close all FlowScribeGUI windows and try again." -ForegroundColor Red
        throw $_
    }

    if ($paraformerSupport.Available) {
        Write-Step "Verify packaged Paraformer runtime"
        Assert-PackagedParaformerRuntime -DestinationDir $PackageDir
    } else {
        Write-Step "Skip Paraformer runtime verification"
        Write-Host "  GUI package was built without bundled Paraformer runtime." -ForegroundColor Yellow
    }

    Write-Step "Copy WASAPI helper into GUI release folder"
    Copy-WasapiHelper -SourceDir $HelperStageDir -DestinationDir $PackageDir

    Write-Step "Copy ffmpeg and ffprobe into GUI release folder"
    Copy-Tool -Name "ffmpeg" -DestinationDir $PackageDir
    Copy-Tool -Name "ffprobe" -DestinationDir $PackageDir

    Write-Step "Copy standalone URL tool next to GUI executable"
    Ensure-UrlToolSibling

    if ($IncludeBundledModels) {
        if (-not (Test-Path $ModelsSourceDir)) {
            throw "Bundled model packaging was requested but the models directory was not found: $ModelsSourceDir"
        }

        $releaseModelsDir = Join-Path $PackageDir "models"
        if (Test-Path $releaseModelsDir) {
            Remove-Item -LiteralPath $releaseModelsDir -Recurse -Force
        }

        Write-Step "Copy model assets into GUI release folder"
        Copy-Item -LiteralPath $ModelsSourceDir -Destination $releaseModelsDir -Recurse -Force
        Write-Host "Copied model assets to $releaseModelsDir"
    } else {
        $releaseModelsDir = Join-Path $PackageDir "models"
        Remove-ProjectItemIfExists -Path $releaseModelsDir
        Write-Step "Skip bundled model assets"
        Write-Host "  Building zero-model GUI package. Users will download models from Model Center or via the installer." -ForegroundColor Yellow
    }

    Write-Step "Done"
    Write-Host "GUI release folder: $PackageDir" -ForegroundColor Green
    Write-Host "GUI executable: $exePath" -ForegroundColor Green
}
finally {
    Pop-Location
}
