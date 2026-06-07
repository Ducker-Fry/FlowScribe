from pathlib import Path


def test_build_gui_script_requires_paraformer_dependencies() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert "-CheckPySide6" in script
    assert "-CheckParaformer" in script
    assert "-IncludeParaformer" not in script
    assert "GUI packaging requires funasr and modelscope" in script


def test_build_gui_script_always_bundles_paraformer_runtime() -> None:
    script = Path("scripts/build_gui_exe.ps1").read_text(encoding="utf-8")

    assert "Assert-ParaformerPackagingSupport" in script
    assert '--hidden-import", "funasr"' in script
    assert '--collect-all", "modelscope"' in script
