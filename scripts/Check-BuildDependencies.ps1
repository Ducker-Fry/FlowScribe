# Check-BuildDependencies.ps1
# Shared dependency checking and installation module for FlowScribe build scripts

param(
    [string]$Python = "python",
    [string]$DotNet = "dotnet",
    [switch]$CheckPython,
    [switch]$CheckDotNet,
    [switch]$CheckFfmpeg,
    [switch]$CheckPyInstaller,
    [switch]$CheckPySide6,
    [switch]$CheckParaformer,
    [switch]$AutoInstall,
    [switch]$AutoAddToPath
)

$ErrorActionPreference = "Stop"

# Set console output encoding to UTF-8 to fix Chinese character display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Get-UserChoice {
    param(
        [string]$Prompt,
        [string]$Default = "Y"
    )

    $choice = Read-Host "$Prompt [Y/n]"
    if ([string]::IsNullOrWhiteSpace($choice)) {
        return $Default
    }
    return $choice.ToUpper()
}

function Get-UserPathChoice {
    param([string]$Prompt)

    Write-Host $Prompt
    Write-Host "  1. Add to User PATH (current user only)"
    Write-Host "  2. Add to System PATH (all users, requires admin)"
    Write-Host "  3. Add to current session only (temporary)"
    Write-Host "  4. Skip"

    $choice = Read-Host "Choose [1-4]"
    return $choice
}

function Add-ToPath {
    param(
        [string]$Directory,
        [string]$Scope = "User"
    )

    try {
        if ($Scope -eq "User") {
            $regPath = "HKCU:\Environment"
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        }
        elseif ($Scope -eq "System") {
            $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")

            $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            if (-not $isAdmin) {
                Write-Warning "Adding to System PATH requires administrator privileges"
                return $false
            }
        }
        elseif ($Scope -eq "Session") {
            $env:PATH = "$Directory;$env:PATH"
            Write-Success "Added to current session PATH: $Directory"
            Write-Info "Note: This change is temporary and will be lost when you close this terminal"
            return $true
        }
        else {
            Write-Error "Invalid scope: $Scope"
            return $false
        }

        if ($currentPath -split ";" | Where-Object { $_ -eq $Directory }) {
            Write-Info "Directory already in PATH: $Directory"
            return $true
        }

        $newPath = "$currentPath;$Directory"
        Set-ItemProperty -Path $regPath -Name "Path" -Value $newPath

        $env:PATH = "$Directory;$env:PATH"

        Write-Success "Added to $Scope PATH: $Directory"
        Write-Info "Note: You may need to restart your terminal for the change to take effect"
        return $true
    }
    catch {
        Write-Error "Failed to add to PATH: $($_.Exception.Message)"
        return $false
    }
}

function Find-PythonInstallation {
    param([string]$MinVersion = "3.10")

    $searchPaths = @(
        "C:\Python*",
        "$env:LOCALAPPDATA\Programs\Python\Python*",
        "C:\Program Files\Python*",
        "C:\Program Files (x86)\Python*"
    )

    $candidates = @()

    foreach ($pattern in $searchPaths) {
        Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $pythonExe = Join-Path $_.FullName "python.exe"
            if (Test-Path $pythonExe) {
                $candidates += @{
                    Path = $_.FullName
                    Exe = $pythonExe
                }
            }
        }
    }

    foreach ($candidate in $candidates) {
        try {
            $versionOutput = & $candidate.Exe --version 2>&1
            if ($versionOutput -match "Python (\d+\.\d+\.\d+)") {
                $version = $matches[1]
                $current = [version]$version
                $required = [version]$MinVersion

                if ($current -ge $required) {
                    return @{
                        Success = $true
                        Path = $candidate.Path
                        Exe = $candidate.Exe
                        Version = $version
                    }
                }
            }
        }
        catch {
            continue
        }
    }

    return @{ Success = $false; Message = "No suitable Python installation found" }
}

function Find-DotNetInstallation {
    param([string]$MinVersion = "8.0")

    $searchPaths = @(
        "C:\Program Files\dotnet",
        "C:\Program Files (x86)\dotnet"
    )

    foreach ($path in $searchPaths) {
        $dotnetExe = Join-Path $path "dotnet.exe"
        if (Test-Path $dotnetExe) {
            try {
                $versionOutput = & $dotnetExe --version 2>&1
                if ($versionOutput -match "(\d+\.\d+)") {
                    $version = $matches[1]
                    $current = [version]$version
                    $required = [version]$MinVersion

                    if ($current -ge $required) {
                        return @{
                            Success = $true
                            Path = $path
                            Exe = $dotnetExe
                            Version = $version
                        }
                    }
                }
            }
            catch {
                continue
            }
        }
    }

    return @{ Success = $false; Message = "No suitable .NET SDK installation found" }
}

function Find-FfmpegInstallation {
    $searchPaths = @(
        "C:\ffmpeg\bin",
        "C:\Program Files\ffmpeg\bin",
        "C:\Program Files (x86)\ffmpeg\bin",
        "$env:LOCALAPPDATA\ffmpeg\bin"
    )

    if ($env:ChocolateyInstall) {
        $chocoLib = Join-Path $env:ChocolateyInstall "lib"
        if (Test-Path $chocoLib) {
            Get-ChildItem -Path $chocoLib -Directory -Filter "ffmpeg*" -ErrorAction SilentlyContinue | ForEach-Object {
                $toolsPath = Join-Path $_.FullName "tools"
                if (Test-Path $toolsPath) {
                    $searchPaths += $toolsPath
                }
                $binPath = Join-Path $_.FullName "bin"
                if (Test-Path $binPath) {
                    $searchPaths += $binPath
                }
            }
        }
    }

    foreach ($path in $searchPaths) {
        $ffmpegExe = Join-Path $path "ffmpeg.exe"
        $ffprobeExe = Join-Path $path "ffprobe.exe"

        if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
            try {
                $versionOutput = & $ffmpegExe -version 2>&1 | Select-Object -First 1
                if ($versionOutput -match "ffmpeg version (\S+)") {
                    return @{
                        Success = $true
                        Path = $path
                        FfmpegExe = $ffmpegExe
                        FfprobeExe = $ffprobeExe
                        Version = $matches[1]
                    }
                }
            }
            catch {
                continue
            }
        }
    }

    return @{ Success = $false; Message = "No ffmpeg installation found" }
}

function Test-PythonVersion {
    param(
        [string]$PythonCmd,
        [string]$MinVersion = "3.10"
    )

    try {
        $versionOutput = & $PythonCmd --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return @{ Success = $false; Message = "Python command failed" }
        }

        if ($versionOutput -match "Python (\d+\.\d+\.\d+)") {
            $version = $matches[1]
            $current = [version]$version
            $required = [version]$MinVersion

            if ($current -ge $required) {
                return @{ Success = $true; Version = $version }
            }
            else {
                return @{ Success = $false; Version = $version; Message = "Version $version is below minimum $MinVersion" }
            }
        }
        else {
            return @{ Success = $false; Message = "Could not parse Python version" }
        }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}

function Test-DotNetVersion {
    param(
        [string]$DotNetCmd,
        [string]$MinVersion = "8.0"
    )

    try {
        $versionOutput = & $DotNetCmd --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return @{ Success = $false; Message = ".NET command failed" }
        }

        if ($versionOutput -match "(\d+\.\d+)") {
            $version = $matches[1]
            $current = [version]$version
            $required = [version]$MinVersion

            if ($current -ge $required) {
                return @{ Success = $true; Version = $version }
            }
            else {
                return @{ Success = $false; Version = $version; Message = "Version $version is below minimum $MinVersion" }
            }
        }
        else {
            return @{ Success = $false; Message = "Could not parse .NET version" }
        }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}

function Test-FfmpegInstalled {
    try {
        $ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
        $ffprobeCmd = Get-Command ffprobe -ErrorAction SilentlyContinue

        if ($ffmpegCmd -and $ffprobeCmd) {
            $versionOutput = & ffmpeg -version 2>&1 | Select-Object -First 1
            if ($versionOutput -match "ffmpeg version (\S+)") {
                return @{ Success = $true; Version = $matches[1]; FfmpegPath = $ffmpegCmd.Source; FfprobePath = $ffprobeCmd.Source }
            }
        }

        return @{ Success = $false; Message = "ffmpeg or ffprobe not found in PATH" }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}

function Test-PythonPackage {
    param(
        [string]$PythonCmd,
        [string]$PackageName,
        [string]$ImportName = $PackageName,
        [string]$MinVersion = $null
    )

    try {
        $checkScript = "import importlib.metadata as metadata; import $ImportName; print(metadata.version('$PackageName'))"
        $versionOutput = & $PythonCmd -c $checkScript 2>&1

        if ($LASTEXITCODE -eq 0) {
            $version = $versionOutput.Trim()

            if ($MinVersion) {
                try {
                    $current = [version]$version
                    $required = [version]$MinVersion

                    if ($current -ge $required) {
                        return @{ Success = $true; Version = $version }
                    }
                    else {
                        return @{ Success = $false; Version = $version; Message = "Version $version is below minimum $MinVersion" }
                    }
                }
                catch {
                    return @{ Success = $true; Version = $version; Message = "Could not compare versions" }
                }
            }
            else {
                return @{ Success = $true; Version = $version }
            }
        }
        else {
            return @{ Success = $false; Message = "Package not installed or import failed" }
        }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}

function Install-PythonPackage {
    param(
        [string]$PythonCmd,
        [string]$PackageName,
        [switch]$Upgrade
    )

    try {
        Write-Info "Installing $PackageName..."

        if ($Upgrade) {
            $installOutput = & $PythonCmd -m pip install --upgrade $PackageName 2>&1
        }
        else {
            $installOutput = & $PythonCmd -m pip install $PackageName 2>&1
        }

        $installExitCode = $LASTEXITCODE
        foreach ($line in $installOutput) {
            Write-Host $line
        }

        if ($installExitCode -eq 0) {
            Write-Success "$PackageName installed successfully"
            return $true
        }
        else {
            Write-Error "Failed to install $PackageName"
            return $false
        }
    }
    catch {
        Write-Error "Exception during installation: $($_.Exception.Message)"
        return $false
    }
}

# Main dependency checks
$allChecksPassed = $true

if ($CheckPython) {
    Write-Info "Checking Python..."
    $pythonCheck = Test-PythonVersion -PythonCmd $Python -MinVersion "3.10"

    if ($pythonCheck.Success) {
        Write-Success "Python $($pythonCheck.Version) found"
    }
    else {
        Write-Error "Python check failed: $($pythonCheck.Message)"

        if ($pythonCheck.Version) {
            Write-Warning "Current version: $($pythonCheck.Version), Required: 3.10+"
            Write-Info "Please upgrade Python to version 3.10 or higher"
            Write-Info "Download from: https://www.python.org/downloads/"
            $allChecksPassed = $false
        }
        else {
            Write-Info "Searching for Python installation..."
            $foundPython = Find-PythonInstallation -MinVersion "3.10"

            if ($foundPython.Success) {
                Write-Success "Found Python $($foundPython.Version) at: $($foundPython.Path)"

                if ($AutoAddToPath) {
                    $added = Add-ToPath -Directory $foundPython.Path -Scope "User"
                    if (-not $added) {
                        $allChecksPassed = $false
                    }
                }
                else {
                    $pathChoice = Get-UserPathChoice -Prompt "Add Python to PATH?"

                    switch ($pathChoice) {
                        "1" {
                            $added = Add-ToPath -Directory $foundPython.Path -Scope "User"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        "2" {
                            $added = Add-ToPath -Directory $foundPython.Path -Scope "System"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        "3" {
                            $added = Add-ToPath -Directory $foundPython.Path -Scope "Session"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        default {
                            Write-Info "Skipped adding Python to PATH"
                            Write-Info "You can manually add it later: $($foundPython.Path)"
                            $allChecksPassed = $false
                        }
                    }
                }
            }
            else {
                Write-Info "Python not found in common installation locations"
                Write-Info "Please install Python 3.10+ from: https://www.python.org/downloads/"
                $allChecksPassed = $false
            }
        }
    }
}

if ($CheckDotNet) {
    Write-Info "Checking .NET SDK..."
    $dotnetCheck = Test-DotNetVersion -DotNetCmd $DotNet -MinVersion "8.0"

    if ($dotnetCheck.Success) {
        Write-Success ".NET SDK $($dotnetCheck.Version) found"
    }
    else {
        Write-Error ".NET SDK check failed: $($dotnetCheck.Message)"

        if ($dotnetCheck.Version) {
            Write-Warning "Current version: $($dotnetCheck.Version), Required: 8.0+"
            Write-Info "Please upgrade .NET SDK to version 8.0 or higher"
            Write-Info "Download from: https://dotnet.microsoft.com/download/dotnet/8.0"
            $allChecksPassed = $false
        }
        else {
            Write-Info "Searching for .NET SDK installation..."
            $foundDotNet = Find-DotNetInstallation -MinVersion "8.0"

            if ($foundDotNet.Success) {
                Write-Success "Found .NET SDK $($foundDotNet.Version) at: $($foundDotNet.Path)"

                if ($AutoAddToPath) {
                    $added = Add-ToPath -Directory $foundDotNet.Path -Scope "User"
                    if (-not $added) {
                        $allChecksPassed = $false
                    }
                }
                else {
                    $pathChoice = Get-UserPathChoice -Prompt "Add .NET SDK to PATH?"

                    switch ($pathChoice) {
                        "1" {
                            $added = Add-ToPath -Directory $foundDotNet.Path -Scope "User"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        "2" {
                            $added = Add-ToPath -Directory $foundDotNet.Path -Scope "System"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        "3" {
                            $added = Add-ToPath -Directory $foundDotNet.Path -Scope "Session"
                            if (-not $added) { $allChecksPassed = $false }
                        }
                        default {
                            Write-Info "Skipped adding .NET SDK to PATH"
                            Write-Info "You can manually add it later: $($foundDotNet.Path)"
                            $allChecksPassed = $false
                        }
                    }
                }
            }
            else {
                Write-Info ".NET SDK not found in common installation locations"
                Write-Info "Download from: https://dotnet.microsoft.com/download/dotnet/8.0"
                $allChecksPassed = $false
            }
        }
    }
}

if ($CheckFfmpeg) {
    Write-Info "Checking ffmpeg..."
    $ffmpegCheck = Test-FfmpegInstalled

    if ($ffmpegCheck.Success) {
        Write-Success "ffmpeg $($ffmpegCheck.Version) found"
        Write-Host "  ffmpeg: $($ffmpegCheck.FfmpegPath)" -ForegroundColor Gray
        Write-Host "  ffprobe: $($ffmpegCheck.FfprobePath)" -ForegroundColor Gray
    }
    else {
        Write-Error "ffmpeg check failed: $($ffmpegCheck.Message)"

        Write-Info "Searching for ffmpeg installation..."
        $foundFfmpeg = Find-FfmpegInstallation

        if ($foundFfmpeg.Success) {
            Write-Success "Found ffmpeg $($foundFfmpeg.Version) at: $($foundFfmpeg.Path)"

            if ($AutoAddToPath) {
                $added = Add-ToPath -Directory $foundFfmpeg.Path -Scope "User"
                if (-not $added) {
                    $allChecksPassed = $false
                }
            }
            else {
                $pathChoice = Get-UserPathChoice -Prompt "Add ffmpeg to PATH?"

                switch ($pathChoice) {
                    "1" {
                        $added = Add-ToPath -Directory $foundFfmpeg.Path -Scope "User"
                        if (-not $added) { $allChecksPassed = $false }
                    }
                    "2" {
                        $added = Add-ToPath -Directory $foundFfmpeg.Path -Scope "System"
                        if (-not $added) { $allChecksPassed = $false }
                    }
                    "3" {
                        $added = Add-ToPath -Directory $foundFfmpeg.Path -Scope "Session"
                        if (-not $added) { $allChecksPassed = $false }
                    }
                    default {
                        Write-Info "Skipped adding ffmpeg to PATH"
                        Write-Info "You can manually add it later: $($foundFfmpeg.Path)"
                        $allChecksPassed = $false
                    }
                }
            }
        }
        else {
            Write-Info "ffmpeg not found in common installation locations"
            Write-Info "Install ffmpeg using one of these methods:"
            Write-Info "  1. Chocolatey: choco install ffmpeg"
            Write-Info "  2. Scoop: scoop install ffmpeg"
            Write-Info "  3. Manual: Download from https://ffmpeg.org/download.html and add to PATH"
            $allChecksPassed = $false
        }
    }
}

if ($CheckPyInstaller) {
    Write-Info "Checking PyInstaller..."
    $pyinstallerCheck = Test-PythonPackage -PythonCmd $Python -PackageName "pyinstaller" -ImportName "PyInstaller"

    if ($pyinstallerCheck.Success) {
        Write-Success "PyInstaller $($pyinstallerCheck.Version) found"
    }
    else {
        Write-Warning "PyInstaller not found: $($pyinstallerCheck.Message)"

        if ($AutoInstall) {
            $install = Install-PythonPackage -PythonCmd $Python -PackageName "pyinstaller"
            if (-not $install) {
                $allChecksPassed = $false
            }
        }
        else {
            $choice = Get-UserChoice -Prompt "Install PyInstaller now?"
            if ($choice -eq "Y") {
                $install = Install-PythonPackage -PythonCmd $Python -PackageName "pyinstaller"
                if (-not $install) {
                    $allChecksPassed = $false
                }
            }
            else {
                Write-Info "Skipping PyInstaller installation"
                Write-Info "Install manually with: $Python -m pip install pyinstaller"
                $allChecksPassed = $false
            }
        }
    }
}

if ($CheckPySide6) {
    Write-Info "Checking PySide6..."
    $pyside6Check = Test-PythonPackage -PythonCmd $Python -PackageName "PySide6" -MinVersion "6.7"

    if ($pyside6Check.Success) {
        Write-Success "PySide6 $($pyside6Check.Version) found"
    }
    else {
        if ($pyside6Check.Version) {
            Write-Warning "PySide6 version too old: $($pyside6Check.Message)"

            if ($AutoInstall) {
                $install = Install-PythonPackage -PythonCmd $Python -PackageName "PySide6" -Upgrade
                if (-not $install) {
                    $allChecksPassed = $false
                }
            }
            else {
                $choice = Get-UserChoice -Prompt "Upgrade PySide6 now?"
                if ($choice -eq "Y") {
                    $install = Install-PythonPackage -PythonCmd $Python -PackageName "PySide6" -Upgrade
                    if (-not $install) {
                        $allChecksPassed = $false
                    }
                }
                else {
                    Write-Info "Skipping PySide6 upgrade"
                    Write-Info "Upgrade manually with: $Python -m pip install --upgrade PySide6"
                    $allChecksPassed = $false
                }
            }
        }
        else {
            Write-Warning "PySide6 not found: $($pyside6Check.Message)"

            if ($AutoInstall) {
                $install = Install-PythonPackage -PythonCmd $Python -PackageName "PySide6"
                if (-not $install) {
                    $allChecksPassed = $false
                }
            }
            else {
                $choice = Get-UserChoice -Prompt "Install PySide6 now?"
                if ($choice -eq "Y") {
                    $install = Install-PythonPackage -PythonCmd $Python -PackageName "PySide6"
                    if (-not $install) {
                        $allChecksPassed = $false
                    }
                }
                else {
                    Write-Info "Skipping PySide6 installation"
                    Write-Info "Install manually with: $Python -m pip install PySide6"
                    $allChecksPassed = $false
                }
            }
        }
    }
}

if ($CheckParaformer) {
    Write-Info "Checking Paraformer dependencies..."
    $paraformerPackages = @(
        @{ PackageName = "funasr"; ImportName = "funasr" },
        @{ PackageName = "modelscope"; ImportName = "modelscope" }
    )

    foreach ($package in $paraformerPackages) {
        $check = Test-PythonPackage `
            -PythonCmd $Python `
            -PackageName $package.PackageName `
            -ImportName $package.ImportName

        if ($check.Success) {
            Write-Success "$($package.PackageName) $($check.Version) found"
            continue
        }

        Write-Warning "$($package.PackageName) not found: $($check.Message)"
        if ($AutoInstall) {
            $install = Install-PythonPackage -PythonCmd $Python -PackageName $package.PackageName
            if (-not $install) {
                $allChecksPassed = $false
            }
            continue
        }

        $choice = Get-UserChoice -Prompt "Install $($package.PackageName) now?"
        if ($choice -eq "Y") {
            $install = Install-PythonPackage -PythonCmd $Python -PackageName $package.PackageName
            if (-not $install) {
                $allChecksPassed = $false
            }
        }
        else {
            Write-Info "Skipping $($package.PackageName) installation"
            Write-Info "Install manually with: $Python -m pip install $($package.PackageName)"
            $allChecksPassed = $false
        }
    }
}

if (-not $allChecksPassed) {
    Write-Host ""
    Write-Error "Some dependency checks failed. Please resolve the issues above before building."
    exit 1
}

Write-Host ""
Write-Success "All dependency checks passed!"
exit 0
