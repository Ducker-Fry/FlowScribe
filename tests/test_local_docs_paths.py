from pathlib import Path

from flowscribe import model_manager


def test_local_docs_index_prefers_chinese_then_english(monkeypatch, tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    class _Resources:
        def __init__(self, docs_dir: Path) -> None:
            self.docs_dir = docs_dir

    monkeypatch.setattr(model_manager, "resolve_resource_paths", lambda: _Resources(docs_dir))

    (docs_dir / "index-en.html").write_text("en", encoding="utf-8")
    assert model_manager.local_docs_index_path() == (docs_dir / "index-en.html").resolve()

    (docs_dir / "index.html").write_text("zh", encoding="utf-8")
    assert model_manager.local_docs_index_path() == (docs_dir / "index.html").resolve()


def test_local_model_guide_prefers_chinese_then_english(monkeypatch, tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    class _Resources:
        def __init__(self, docs_dir: Path) -> None:
            self.docs_dir = docs_dir

    monkeypatch.setattr(model_manager, "resolve_resource_paths", lambda: _Resources(docs_dir))

    (docs_dir / "model-guide-en.html").write_text("en", encoding="utf-8")
    assert model_manager.local_model_guide_path() == (docs_dir / "model-guide-en.html").resolve()

    (docs_dir / "model-guide.html").write_text("zh", encoding="utf-8")
    assert model_manager.local_model_guide_path() == (docs_dir / "model-guide.html").resolve()
