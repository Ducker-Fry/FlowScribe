from pathlib import Path


def test_build_gui_script_builds_unified_portable_package() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert '$CoreBuilder = Join-Path $PSScriptRoot "build_core_package.ps1"' in script
    assert '$CodeBuilder = Join-Path $PSScriptRoot "build_code_package.ps1"' in script
    assert "& $CoreBuilder -Python $Python -DotNet $DotNet" in script
    assert "& $CodeBuilder @codeArgs" in script
    assert 'dist\\FlowScribePortable' in script


def test_build_gui_script_bundles_models_by_default() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert "[switch]$SkipBundledModels" in script
    assert '$codeArgs = @{' in script
    assert "Python = $Python" in script
    assert 'if (-not $SkipBundledModels)' in script
    assert '$codeArgs["IncludeBundledModels"] = $true' in script
    assert '$codeArgs += "-IncludeBundledModels"' not in script


def test_build_exe_script_bundles_models_by_default() -> None:
    script = Path("scripts/build_exe.ps1").read_text(encoding="utf-8")

    assert "[switch]$SkipBundledModels" in script
    assert '$codeArgs = @{' in script
    assert "Python = $Python" in script
    assert "VenvPath = $VenvPath" in script
    assert 'if (-not $SkipBundledModels)' in script
    assert '$codeArgs["IncludeBundledModels"] = $true' in script
    assert '$codeArgs += "-IncludeBundledModels"' not in script
