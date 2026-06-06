from pathlib import Path


def test_setup_env_uses_argument_array_for_local_editable_install() -> None:
    script = Path("scripts/setup_env.ps1").read_text(encoding="utf-8")

    assert '@("-e", ".[{0}]" -f ($extras -join ","))' in script
    assert '@("-e", ".")' in script
    assert "& $Python -m pip install @packageArgs" in script


def test_setup_env_runs_cli_doctor_subcommand() -> None:
    script = Path("scripts/setup_env.ps1").read_text(encoding="utf-8")

    assert "& $Python -m flowscribe doctor" in script
    assert "flowscribe.doctor" not in script


def test_setup_env_checks_doctor_exit_code_before_reporting_success() -> None:
    script = Path("scripts/setup_env.ps1").read_text(encoding="utf-8")

    assert 'if ($LASTEXITCODE -eq 0)' in script
    assert 'Write-Warn "doctor reported issues; review the output above before first use"' in script
