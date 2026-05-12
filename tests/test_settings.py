from pathlib import Path

from flowscribe.config.settings import AppSettings, ZH_INITIAL_PROMPT


def test_zh_preset_applies_language_vad_and_prompt(tmp_path: Path) -> None:
    settings = AppSettings.from_options(
        output_dir=tmp_path / "out",
        work_dir=None,
        model_name="small",
        language=None,
        preset="zh",
        task="transcribe",
        beam_size=5,
        vad_filter=False,
        initial_prompt=None,
        word_timestamps=True,
        recursive=False,
        overwrite=False,
        keep_audio=False,
    )

    assert settings.language == "zh"
    assert settings.vad_filter is True
    assert settings.initial_prompt == ZH_INITIAL_PROMPT
    assert settings.word_timestamps is True


def test_explicit_prompt_and_language_override_zh_preset_defaults(tmp_path: Path) -> None:
    settings = AppSettings.from_options(
        output_dir=tmp_path / "out",
        work_dir=None,
        model_name="small",
        language="en",
        preset="zh",
        task="transcribe",
        beam_size=3,
        vad_filter=False,
        initial_prompt="custom terms",
        word_timestamps=False,
        recursive=False,
        overwrite=False,
        keep_audio=False,
    )

    assert settings.language == "en"
    assert settings.vad_filter is True
    assert settings.initial_prompt == "custom terms"
    assert settings.beam_size == 3
