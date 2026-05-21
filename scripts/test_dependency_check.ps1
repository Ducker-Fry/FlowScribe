# Test script for Check-BuildDependencies.ps1
# Run this to verify dependency checking works correctly

param(
    [string]$Python = "python",
    [string]$DotNet = "dotnet"
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DependencyChecker = Join-Path $ScriptDir "Check-BuildDependencies.ps1"

Write-Host "=== Testing Dependency Checker ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Test 1: Check Python only" -ForegroundColor Yellow
& $DependencyChecker -Python $Python -CheckPython
Write-Host ""

Write-Host "Test 2: Check .NET only" -ForegroundColor Yellow
& $DependencyChecker -DotNet $DotNet -CheckDotNet
Write-Host ""

Write-Host "Test 3: Check ffmpeg only" -ForegroundColor Yellow
& $DependencyChecker -CheckFfmpeg
Write-Host ""

Write-Host "Test 4: Check PyInstaller (with auto-install)" -ForegroundColor Yellow
& $DependencyChecker -Python $Python -CheckPyInstaller -AutoInstall
Write-Host ""

Write-Host "Test 5: Check PySide6 (with auto-install)" -ForegroundColor Yellow
& $DependencyChecker -Python $Python -CheckPySide6 -AutoInstall
Write-Host ""

Write-Host "Test 6: Check all CLI build dependencies" -ForegroundColor Yellow
& $DependencyChecker -Python $Python -CheckPython -CheckFfmpeg -CheckPyInstaller
Write-Host ""

Write-Host "Test 7: Check all GUI build dependencies" -ForegroundColor Yellow
& $DependencyChecker -Python $Python -DotNet $DotNet -CheckPython -CheckDotNet -CheckFfmpeg -CheckPyInstaller -CheckPySide6
Write-Host ""

Write-Host "=== All tests completed ===" -ForegroundColor Cyan
