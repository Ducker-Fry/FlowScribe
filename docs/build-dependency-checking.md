# Build Scripts Dependency Checking

## Overview

All FlowScribe build scripts now include automatic dependency checking with:
- **Automatic detection** of missing or outdated dependencies
- **Intelligent search** for installed dependencies not in PATH
- **Interactive prompts** to add dependencies to PATH
- **Auto-install mode** for Python packages and PATH management

## Features

- **Automatic detection** of missing or outdated dependencies
- **Version checking** for Python, .NET SDK, and Python packages
- **Smart search** in common installation locations
- **PATH management** with three options:
  - User PATH (current user only)
  - System PATH (all users, requires admin)
  - Session PATH (temporary, current terminal only)
- **Interactive prompts** to install or upgrade dependencies
- **Auto-install mode** for CI/CD environments
- **Clear error messages** with installation instructions

## Dependencies by Build Type

### CLI Build (`build_exe.ps1`)
- Python 3.10+
- ffmpeg/ffprobe
- PyInstaller

### GUI Build (`build_gui_exe.ps1`)
- Python 3.10+
- .NET SDK 8.0+
- ffmpeg/ffprobe
- PyInstaller
- PySide6 6.7+

### WASAPI Helper Build (`build_wasapi_helper.ps1`)
- .NET SDK 8.0+

## Usage

### Normal Build (Interactive)

The build scripts will automatically check dependencies and prompt you to install missing ones:

```powershell
# CLI build
.\scripts\build_exe.ps1

# GUI build
.\scripts\build_gui_exe.ps1

# WASAPI helper build
.\scripts\build_wasapi_helper.ps1
```

When a dependency is missing or outdated, you'll see prompts like:

```
⚠ PyInstaller not found: Package not installed or import failed
Install PyInstaller now? [Y/n]
```

Press `Y` (or just Enter) to install, or `n` to skip.

### Manual Dependency Check

Test dependencies without building:

```powershell
# Check all CLI dependencies
.\scripts\Check-BuildDependencies.ps1 -CheckPython -CheckFfmpeg -CheckPyInstaller

# Check all GUI dependencies
.\scripts\Check-BuildDependencies.ps1 -CheckPython -CheckDotNet -CheckFfmpeg -CheckPyInstaller -CheckPySide6

# Check specific dependency
.\scripts\Check-BuildDependencies.ps1 -CheckPython
```

### Auto-Install Mode (CI/CD)

Skip interactive prompts and auto-install missing packages:

```powershell
.\scripts\Check-BuildDependencies.ps1 -CheckPyInstaller -CheckPySide6 -AutoInstall
```

## Dependency Checker Options

### Flags

- `-CheckPython` - Check Python version (requires 3.10+)
- `-CheckDotNet` - Check .NET SDK version (requires 8.0+)
- `-CheckFfmpeg` - Check ffmpeg/ffprobe availability
- `-CheckPyInstaller` - Check PyInstaller package
- `-CheckPySide6` - Check PySide6 package (requires 6.7+)
- `-AutoInstall` - Auto-install missing Python packages without prompting
- `-AutoAddToPath` - Auto-add found dependencies to User PATH without prompting

### Parameters

- `-Python <command>` - Python command to use (default: "python")
- `-DotNet <command>` - .NET command to use (default: "dotnet")

## Examples

### Example 1: First-time Setup

```powershell
# User runs GUI build for the first time
PS> .\scripts\build_gui_exe.ps1

==> Check build dependencies
Checking Python...
✓ Python 3.11.5 found
Checking .NET SDK...
✓ .NET SDK 8.0.100 found
Checking ffmpeg...
✓ ffmpeg 6.0 found
  ffmpeg: C:\ProgramData\chocolatey\bin\ffmpeg.exe
  ffprobe: C:\ProgramData\chocolatey\bin\ffprobe.exe
Checking PyInstaller...
⚠ PyInstaller not found: Package not installed or import failed
Install PyInstaller now? [Y/n] y
Installing PyInstaller...
✓ PyInstaller installed successfully
Checking PySide6...
⚠ PySide6 not found: Package not installed or import failed
Install PySide6 now? [Y/n] y
Installing PySide6...
✓ PySide6 installed successfully

✓ All dependency checks passed!

==> Create or reuse packaging virtual environment
...
```

### Example 2: Outdated Dependency

```powershell
PS> .\scripts\build_gui_exe.ps1

==> Check build dependencies
Checking Python...
✓ Python 3.11.5 found
Checking .NET SDK...
✓ .NET SDK 8.0.100 found
Checking ffmpeg...
✓ ffmpeg 6.0 found
Checking PyInstaller...
✓ PyInstaller 6.3.0 found
Checking PySide6...
⚠ PySide6 version too old: Version 6.5.0 is below minimum 6.7
Upgrade PySide6 now? [Y/n] y
Installing PySide6...
✓ PySide6 installed successfully

✓ All dependency checks passed!
...
```

### Example 3: Dependency Not in PATH

```powershell
PS> .\scripts\build_exe.ps1

==> Check build dependencies
Checking Python...
✗ Python check failed: Python command failed
Searching for Python installation...
✓ Found Python 3.11.5 at: C:\Users\YourName\AppData\Local\Programs\Python\Python311
Add Python to PATH?
  1. Add to User PATH (current user only)
  2. Add to System PATH (all users, requires admin)
  3. Add to current session only (temporary)
  4. Skip
Choose [1-4]: 1
✓ Added to User PATH: C:\Users\YourName\AppData\Local\Programs\Python\Python311
Note: You may need to restart your terminal for the change to take effect

Checking ffmpeg...
✗ ffmpeg check failed: ffmpeg or ffprobe not found in PATH
Searching for ffmpeg installation...
✓ Found ffmpeg 6.0 at: C:\ffmpeg\bin
Add ffmpeg to PATH?
  1. Add to User PATH (current user only)
  2. Add to System PATH (all users, requires admin)
  3. Add to current session only (temporary)
  4. Skip
Choose [1-4]: 3
✓ Added to current session PATH: C:\ffmpeg\bin
Note: This change is temporary and will be lost when you close this terminal

Checking PyInstaller...
✓ PyInstaller 6.3.0 found

✓ All dependency checks passed!
...
```

### Example 4: Auto-Add to PATH Mode

```powershell
PS> .\scripts\Check-BuildDependencies.ps1 -CheckPython -CheckFfmpeg -AutoAddToPath

Checking Python...
✗ Python check failed: Python command failed
Searching for Python installation...
✓ Found Python 3.11.5 at: C:\Users\YourName\AppData\Local\Programs\Python\Python311
✓ Added to User PATH: C:\Users\YourName\AppData\Local\Programs\Python\Python311
Note: You may need to restart your terminal for the change to take effect

Checking ffmpeg...
✗ ffmpeg check failed: ffmpeg or ffprobe not found in PATH
Searching for ffmpeg installation...
✓ Found ffmpeg 6.0 at: C:\ffmpeg\bin
✓ Added to User PATH: C:\ffmpeg\bin
Note: You may need to restart your terminal for the change to take effect

✓ All dependency checks passed!
```

### Example 5: Dependency Not Found Anywhere

```powershell
PS> .\scripts\build_exe.ps1

==> Check build dependencies
Checking Python...
✓ Python 3.11.5 found
Checking ffmpeg...
✗ ffmpeg check failed: ffmpeg or ffprobe not found in PATH
Searching for ffmpeg installation...
ffmpeg not found in common installation locations
Install ffmpeg using one of these methods:
  1. Chocolatey: choco install ffmpeg
  2. Scoop: scoop install ffmpeg
  3. Manual: Download from https://ffmpeg.org/download.html and add to PATH

✗ Some dependency checks failed. Please resolve the issues above before building.
```

## Testing

Run the test script to verify all dependency checks:

```powershell
.\scripts\test_dependency_check.ps1
```

This will test each dependency check individually and show the results.

## Troubleshooting

### Python not found

**If Python is installed but not in PATH:**

The script will automatically search common installation locations and offer to add it to PATH.

**If you want to specify a custom Python:**

```powershell
.\scripts\build_exe.ps1 -Python "C:\Python311\python.exe"
```

**If Python is not installed:**

Download and install Python 3.10+ from: https://www.python.org/downloads/

Make sure to check "Add Python to PATH" during installation.

### .NET SDK not found

**If .NET SDK is installed but not in PATH:**

The script will automatically search common installation locations and offer to add it to PATH.

**If .NET SDK is not installed:**

Download and install .NET SDK 8.0+ from:
https://dotnet.microsoft.com/download/dotnet/8.0

### ffmpeg not found

**If ffmpeg is installed but not in PATH:**

The script will automatically search common installation locations (including Chocolatey) and offer to add it to PATH.

**If ffmpeg is not installed:**

Install ffmpeg using one of these methods:

**Chocolatey** (recommended):
```powershell
choco install ffmpeg
```

**Scoop**:
```powershell
scoop install ffmpeg
```

**Manual**:
1. Download from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. The script will find it automatically, or you can manually add `C:\ffmpeg\bin` to PATH

### PATH Changes Not Taking Effect

**For User/System PATH changes:**

You need to restart your terminal (or IDE) for the changes to take effect. The script adds the directory to the current session automatically, but permanent changes require a restart.

**For Session PATH changes:**

These are temporary and only work in the current terminal. They will be lost when you close the terminal.

**To verify PATH changes:**

```powershell
# Check if a command is now available
Get-Command python
Get-Command ffmpeg

# View current PATH
$env:PATH -split ";"
```

### Package installation fails

If pip installation fails, try upgrading pip first:

```powershell
python -m pip install --upgrade pip
```

Then retry the build script.

## CI/CD Integration

For automated builds, use auto-install and auto-add-to-path modes:

```powershell
# Install all dependencies without prompts
.\scripts\Check-BuildDependencies.ps1 `
    -CheckPython `
    -CheckDotNet `
    -CheckFfmpeg `
    -CheckPyInstaller `
    -CheckPySide6 `
    -AutoInstall `
    -AutoAddToPath

# Then run builds
.\scripts\build_exe.ps1
.\scripts\build_gui_exe.ps1
```

**Note:** `-AutoAddToPath` adds dependencies to User PATH. For CI/CD environments, you may want to use Session PATH instead by setting dependencies in the environment before running the script.

## Notes

- **System dependencies** (Python, .NET, ffmpeg) are searched in common installation locations if not in PATH
- **Python packages** (PyInstaller, PySide6) can be auto-installed via pip
- **PATH management** offers three scopes:
  - **User PATH**: Permanent, current user only, no admin required
  - **System PATH**: Permanent, all users, requires admin privileges
  - **Session PATH**: Temporary, current terminal only, lost on close
- **Version checks** use semantic versioning comparison
- **The dependency checker** exits with code 1 if any check fails
- **Build scripts** will stop if dependency checks fail
- **Search locations** include:
  - Python: `C:\Python*`, `%LOCALAPPDATA%\Programs\Python\*`, `C:\Program Files\Python*`
  - .NET SDK: `C:\Program Files\dotnet`, `C:\Program Files (x86)\dotnet`
  - ffmpeg: `C:\ffmpeg\bin`, `C:\Program Files\ffmpeg\bin`, Chocolatey lib folders
