from pathlib import Path


def test_build_gui_script_does_not_require_paraformer_for_base_gui_build() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert "-CheckPySide6" in script
    assert "-CheckParaformer" not in script
    assert "-IncludeParaformer" in script
    assert "Building GUI without bundled FunASR/modelscope payloads" in script


def test_build_gui_script_bundles_paraformer_only_when_available() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert "Test-OptionalParaformerPackaging" in script
    assert "Paraformer packaging was requested" in script
    assert '--hidden-import", "funasr"' in script
    assert '--collect-all", "modelscope"' in script
