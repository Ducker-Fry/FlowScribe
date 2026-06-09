from pathlib import Path


def test_build_core_package_uses_incremental_site_packages_sync() -> None:
    script = Path("scripts/build_core_package.ps1").read_text(encoding="utf-8")

    assert "function Mirror-SitePackages" in script
    assert "Sync-DirectoryTree `" in script
    assert "Write-SyncSummary -Label \"site-packages stage\"" in script
    assert "Write-SyncSummary -Label \"site-packages core\"" in script
    assert '-ExcludeNamePatterns @("flowscribe*", "__editable__*", "*.pth")' in script
    assert "Remove-ProjectItemIfExists -Path $DestinationDir -ProjectRoot $ProjectRoot" not in script


def test_build_core_package_uses_incremental_runtime_sync_for_dlls_and_stdlib() -> None:
    script = Path("scripts/build_core_package.ps1").read_text(encoding="utf-8")

    assert "function Write-PortableRuntimeSummary" in script
    assert "function Write-CoreLauncherSyncSummary" in script
    assert "Python runtime files:" in script
    assert "Core launchers:" in script
    assert '-DestinationDir $DllDir `' in script
    assert '-DestinationDir $StdlibDir `' in script
    assert "Write-SyncSummary -Label \"DLLs\"" in script
    assert "Write-SyncSummary -Label \"Lib\"" in script
    assert '-ExcludeNames @("site-packages")' in script
    assert "Remove-ProjectItemIfExists -Path $DllDir -ProjectRoot $ProjectRoot" not in script
    assert "Remove-ProjectItemIfExists -Path $StdlibDir -ProjectRoot $ProjectRoot" not in script


def test_packaging_common_defines_recursive_incremental_directory_sync() -> None:
    script = Path("scripts/packaging_common.ps1").read_text(encoding="utf-8")

    assert "function Sync-DirectoryTree" in script
    assert "function Get-RelativePathCompat" in script
    assert "function New-SyncSummary" in script
    assert "function Write-SyncSummary" in script
    assert "function Test-SyncPathExcluded" in script
    assert "MakeRelativeUri" in script
    assert "FilesAdded" in script
    assert "FilesRemoved" in script
    assert "Remove-ProjectItemIfExists -Path $item.FullName -ProjectRoot $ProjectRoot" in script
