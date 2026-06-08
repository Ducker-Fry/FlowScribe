Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-InProject {
    param(
        [string]$Path,
        [string]$ProjectRoot
    )

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($ProjectRoot)
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside project: $resolved"
    }
}

function Remove-ProjectItemIfExists {
    param(
        [string]$Path,
        [string]$ProjectRoot
    )

    Assert-InProject -Path $Path -ProjectRoot $ProjectRoot
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
        [string]$DestinationDir,
        [string]$ProjectRoot,
        [string[]]$ExcludeNames = @()
    )

    if (-not (Test-Path $SourceDir)) {
        throw "Source directory was not found: $SourceDir"
    }

    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        if ($ExcludeNames -contains $item.Name) {
            continue
        }

        $destinationPath = Join-Path $DestinationDir $item.Name
        if ($item.PSIsContainer) {
            Remove-ProjectItemIfExists -Path $destinationPath -ProjectRoot $ProjectRoot
            Copy-Item -LiteralPath $item.FullName -Destination $destinationPath -Recurse -Force
        } else {
            [void](Sync-FileIfChanged -SourcePath $item.FullName -DestinationPath $destinationPath)
        }
    }
}

function Invoke-LoggedNativeCommand {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    $stdoutPath = Join-Path $env:TEMP "flowscribe-build-stdout.log"
    $stderrPath = Join-Path $env:TEMP "flowscribe-build-stderr.log"

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

        while (-not $process.HasExited) {
            Start-Sleep -Milliseconds 300
            $process.Refresh()
        }

        $process.WaitForExit()
        $exitCode = [int]$process.ExitCode
        if (Test-Path $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath | Out-Host
        }
        if (Test-Path $stderrPath) {
            Get-Content -LiteralPath $stderrPath | Out-Host
        }
        return $exitCode
    }
    finally {
        foreach ($logPath in @($stdoutPath, $stderrPath)) {
            if (Test-Path $logPath) {
                Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Ensure-PackagingVenv {
    param(
        [string]$Python,
        [string]$ProjectRoot,
        [string]$VenvPath,
        [switch]$RequirePyInstaller
    )

    $venvRoot = Join-Path $ProjectRoot $VenvPath
    $pythonExe = Join-Path $venvRoot "Scripts\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Step "Create packaging virtual environment"
        & $Python -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create packaging virtual environment."
        }
    }

    if ($RequirePyInstaller) {
        Write-Step "Verify packaging virtual environment"
        & $pythonExe -c "import PyInstaller"
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller is not available in packaging virtual environment: $pythonExe"
        }
    }

    return $pythonExe
}

function Get-PythonSitePackagesPath {
    param([string]$Python)

    $path = & $Python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($path)) {
        throw "Could not resolve site-packages path for Python command: $Python"
    }

    return $path.Trim()
}

function Get-PythonRuntimeRoot {
    param([string]$Python)

    $path = & $Python -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($path)) {
        throw "Could not resolve Python runtime root for Python command: $Python"
    }

    return $path.Trim()
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

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -File) {
        [void](Sync-FileIfChanged -SourcePath $item.FullName -DestinationPath (Join-Path $DestinationDir $item.Name))
    }
}
