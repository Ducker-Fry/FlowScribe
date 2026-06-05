param(
    [string]$Python = "python",
    [string]$AppName = "FlowScribeGUI",
    [string]$DotNet = "dotnet",
    [switch]$IncludeBundledModels,
    [switch]$IncludeParaformer,
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
$RuntimeHook = Join-Path $ProjectRoot "scripts\pyinstaller_gui_runtime_hook.py"
$HelperBuildScript = Join-Path $ProjectRoot "scripts\build_wasapi_helper.ps1"
$HelperStageDir = Join-Path $ProjectRoot "build\wasapi-helper"
$UserBase = Join-Path $ProjectRoot ".py-user-base"
$DependencyChecker = Join-Path $PSScriptRoot "Check-BuildDependencies.ps1"
$ModelsSourceDir = Join-Path $ProjectRoot "models"

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

            Copy-Item -LiteralPath $candidate -Destination (Join-Path $DestinationDir "$Name.exe") -Force

            $toolDir = Split-Path -Parent $candidate
            Get-ChildItem -LiteralPath $toolDir -Filter "*.dll" -ErrorAction SilentlyContinue |
                Copy-Item -Destination $DestinationDir -Force

            Write-Host "Copied $Name from $candidate"
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

function Test-OptionalParaformerPackaging {
    param([string]$PythonCmd)

    & $PythonCmd -c "import funasr, modelscope; print('funasr', getattr(funasr, '__version__', 'unknown')); print('modelscope', getattr(modelscope, '__version__', 'unknown'))"
    return ($LASTEXITCODE -eq 0)
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
    & $DependencyChecker -Python $Python -DotNet $DotNet -CheckPython -CheckDotNet -CheckFfmpeg -CheckPyInstaller -CheckPySide6
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed. Please resolve the issues above."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUSERBASE = $UserBase

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

        # Check and close running FlowScribeGUI processes
        $runningProcesses = Get-Process | Where-Object { $_.ProcessName -like "*FlowScribe*" }
        if ($runningProcesses) {
            Write-Host "  Found running FlowScribeGUI processes. Attempting to close..." -ForegroundColor Yellow
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
                } catch {
                    Write-Host "    Warning: Could not close process: $_" -ForegroundColor Yellow
                }
            }
            # Wait a bit for file handles to be released
            Start-Sleep -Seconds 1
        }

        Assert-InProject -Path $PackageDir
        if (Test-Path $PackageDir) {
            try {
                Remove-Item -LiteralPath $PackageDir -Recurse -Force -ErrorAction Stop
            } catch {
                Write-Host "  Error: Cannot delete $PackageDir" -ForegroundColor Red
                Write-Host "  The directory may still be in use by another process." -ForegroundColor Red
                Write-Host "  Please close all FlowScribeGUI windows and try again." -ForegroundColor Red
                throw $_
            }
        }

        $guiBuildDir = Join-Path $BuildRoot $AppName
        Assert-InProject -Path $guiBuildDir
        if (Test-Path $guiBuildDir) {
            Remove-Item -LiteralPath $guiBuildDir -Recurse -Force
        }
    }

    Write-Step "Build GUI one-folder executable"

    $includeParaformer = $false
    if ($IncludeParaformer) {
        Write-Step "Check optional Paraformer packaging support"
        $includeParaformer = Test-OptionalParaformerPackaging -PythonCmd $Python
        if ($includeParaformer) {
            Write-Host "  Paraformer dependencies are available; bundling optional FunASR support." -ForegroundColor Green
        } else {
            throw "Paraformer packaging was requested, but funasr/modelscope are not importable in the selected Python environment."
        }
    } else {
        Write-Step "Skip optional Paraformer packaging"
        Write-Host "  Building GUI without bundled FunASR/modelscope payloads. Pass -IncludeParaformer to opt in." -ForegroundColor Yellow
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
        "--clean",
        "--noconfirm",
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

    if ($includeParaformer) {
        $PyInstallerArgs += @(
            "--hidden-import", "funasr",
            "--hidden-import", "modelscope",
            "--collect-all", "funasr",
            "--collect-all", "modelscope"
        )
    }

    if ($IconArg.Count -gt 0) {
        $PyInstallerArgs += $IconArg
    }

    $PyInstallerArgs += "src\flowscribe\gui\__main__.py"

    $exePath = Join-Path $PackageDir "$AppName.exe"
    $pyInstallerExitCode = Invoke-LoggedNativeCommand `
        -FilePath $Python `
        -ArgumentList $PyInstallerArgs `
        -WorkingDirectory $ProjectRoot
    if (-not (Test-Path $exePath)) {
        throw "PyInstaller failed for GUI packaging and no executable was created: $exePath"
    }
    if ($pyInstallerExitCode -ne 0) {
        Write-Host "  Warning: PyInstaller returned exit code $pyInstallerExitCode, but the GUI executable was created successfully. Continuing packaging." -ForegroundColor Yellow
    }

    Write-Step "Copy WASAPI helper into GUI release folder"
    Copy-WasapiHelper -SourceDir $HelperStageDir -DestinationDir $PackageDir

    Write-Step "Copy ffmpeg and ffprobe into GUI release folder"
    Copy-Tool -Name "ffmpeg" -DestinationDir $PackageDir
    Copy-Tool -Name "ffprobe" -DestinationDir $PackageDir

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
