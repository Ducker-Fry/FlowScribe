# Demo script for PATH management features
# This script demonstrates the automatic search and PATH addition features

param(
    [switch]$DemoSearch,
    [switch]$DemoPathAdd,
    [switch]$ShowCurrentPath
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DependencyChecker = Join-Path $ScriptDir "Check-BuildDependencies.ps1"

function Write-Demo {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Magenta
    Write-Host ""
}

if ($ShowCurrentPath) {
    Write-Demo "Current PATH Environment"
    Write-Host "User PATH:" -ForegroundColor Cyan
    [Environment]::GetEnvironmentVariable("Path", "User") -split ";" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "System PATH:" -ForegroundColor Cyan
    [Environment]::GetEnvironmentVariable("Path", "Machine") -split ";" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "Current Session PATH:" -ForegroundColor Cyan
    $env:PATH -split ";" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
    exit 0
}

if ($DemoSearch) {
    Write-Demo "Demonstrating Automatic Dependency Search"

    Write-Host "This demo will search for installed dependencies not in PATH" -ForegroundColor Yellow
    Write-Host "Press Enter to continue..."
    Read-Host

    Write-Host ""
    Write-Host "Searching for Python installations..." -ForegroundColor Cyan
    & $DependencyChecker -CheckPython
    Write-Host ""

    Write-Host "Searching for .NET SDK installations..." -ForegroundColor Cyan
    & $DependencyChecker -CheckDotNet
    Write-Host ""

    Write-Host "Searching for ffmpeg installations..." -ForegroundColor Cyan
    & $DependencyChecker -CheckFfmpeg
    Write-Host ""

    Write-Demo "Search Demo Complete"
    Write-Host "The script searched common installation locations for each dependency."
    Write-Host "If found, it offered to add them to PATH."
}

if ($DemoPathAdd) {
    Write-Demo "Demonstrating PATH Addition Options"

    Write-Host "When a dependency is found but not in PATH, you get these options:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1. Add to User PATH (current user only)" -ForegroundColor Green
    Write-Host "     - Permanent change" -ForegroundColor Gray
    Write-Host "     - Only affects your user account" -ForegroundColor Gray
    Write-Host "     - No admin privileges required" -ForegroundColor Gray
    Write-Host "     - Requires terminal restart to take effect" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Add to System PATH (all users, requires admin)" -ForegroundColor Green
    Write-Host "     - Permanent change" -ForegroundColor Gray
    Write-Host "     - Affects all user accounts" -ForegroundColor Gray
    Write-Host "     - Requires administrator privileges" -ForegroundColor Gray
    Write-Host "     - Requires terminal restart to take effect" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  3. Add to current session only (temporary)" -ForegroundColor Green
    Write-Host "     - Temporary change" -ForegroundColor Gray
    Write-Host "     - Only affects current terminal session" -ForegroundColor Gray
    Write-Host "     - No admin privileges required" -ForegroundColor Gray
    Write-Host "     - Takes effect immediately" -ForegroundColor Gray
    Write-Host "     - Lost when terminal is closed" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  4. Skip" -ForegroundColor Green
    Write-Host "     - Don't add to PATH" -ForegroundColor Gray
    Write-Host "     - You can add it manually later" -ForegroundColor Gray
    Write-Host ""

    Write-Host "For automated builds, use -AutoAddToPath flag:" -ForegroundColor Yellow
    Write-Host "  .\scripts\Check-BuildDependencies.ps1 -CheckPython -AutoAddToPath" -ForegroundColor Cyan
    Write-Host "  This automatically adds to User PATH without prompting" -ForegroundColor Gray
    Write-Host ""
}

if (-not $DemoSearch -and -not $DemoPathAdd -and -not $ShowCurrentPath) {
    Write-Host "PATH Management Demo Script" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\scripts\demo_path_management.ps1 -DemoSearch       # Demo automatic search"
    Write-Host "  .\scripts\demo_path_management.ps1 -DemoPathAdd      # Explain PATH options"
    Write-Host "  .\scripts\demo_path_management.ps1 -ShowCurrentPath  # Show current PATH"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  # See what's in your PATH"
    Write-Host "  .\scripts\demo_path_management.ps1 -ShowCurrentPath"
    Write-Host ""
    Write-Host "  # Test automatic dependency search"
    Write-Host "  .\scripts\demo_path_management.ps1 -DemoSearch"
    Write-Host ""
    Write-Host "  # Learn about PATH addition options"
    Write-Host "  .\scripts\demo_path_management.ps1 -DemoPathAdd"
}
