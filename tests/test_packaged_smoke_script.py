from pathlib import Path


def test_packaged_smoke_script_checks_cli_gui_and_transcription() -> None:
    script = Path("scripts/smoke_packaged_build.ps1").read_text(encoding="utf-8")

    assert "& $cliExe doctor --skip-model-access" in script
    assert "& $guiExe --self-test" in script
    assert "& $cliExe transcribe $smokeAudio -o $smokeOutput --model $Model --overwrite" in script
    assert 'Assert-PathExists -PathValue $txtOutput' in script
    assert 'Assert-PathExists -PathValue $mdOutput' in script


def test_local_whisper_configures_huggingface_runtime_noise_controls() -> None:
    source = Path("src/flowscribe/providers/transcribe/local_whisper.py").read_text(
        encoding="utf-8"
    )

    assert 'os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")' in source
    assert 'os.environ.setdefault("HF_HUB_DISABLE_XET", "1")' in source
