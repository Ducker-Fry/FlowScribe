import sys

from scripts import portable_core_bootstrap


def test_purge_bootstrap_stdlib_shadows_removes_logging_modules(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "logging", object())
    monkeypatch.setitem(sys.modules, "logging.config", object())
    monkeypatch.setitem(sys.modules, "urllib", object())
    monkeypatch.setitem(sys.modules, "urllib.parse", object())
    monkeypatch.setitem(sys.modules, "json", object())

    portable_core_bootstrap._purge_bootstrap_stdlib_shadows()

    assert "logging" not in sys.modules
    assert "logging.config" not in sys.modules
    assert "urllib" not in sys.modules
    assert "urllib.parse" not in sys.modules
    assert "json" in sys.modules
