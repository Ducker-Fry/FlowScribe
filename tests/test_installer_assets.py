from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_installer_scripts_exist() -> None:
    assert (PROJECT_ROOT / "installer" / "FlowScribe-common.iss").exists()
    assert (PROJECT_ROOT / "installer" / "FlowScribe-offline.iss").exists()
    assert (PROJECT_ROOT / "installer" / "FlowScribe-online.iss").exists()


def test_common_installer_mentions_install_config_and_model_downloads() -> None:
    content = (PROJECT_ROOT / "installer" / "FlowScribe-common.iss").read_text(encoding="utf-8")

    assert "install write-config" in content
    assert "model download small" in content
    assert "model download tiny" in content
    assert "Use FlowScribe to open transcript" in content
    assert "FlowScribe could not write install-config.json" in content


def test_build_installers_script_mentions_docs_and_signing() -> None:
    content = (PROJECT_ROOT / "scripts" / "build_installers.ps1").read_text(encoding="utf-8")

    assert "build_docs_site.py" in content
    assert "Invoke-SignIfConfigured" in content
    assert "FlowScribeSetup-offline-x64.exe" in content
