from pathlib import Path

from scripts.codegraph.indexer import build_index, summarize_index


def test_build_index_captures_modules_classes_functions_and_edges(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "demo"
    src_dir.mkdir(parents=True)
    module_path = src_dir / "sample.py"
    module_path.write_text(
        "\n".join(
            [
                '"""Demo module."""',
                "",
                "from demo.base import BaseThing",
                "",
                "class Sample(BaseThing):",
                '    """Example class."""',
                "",
                "    def run(self, value):",
                "        helper(value)",
                "",
                "def helper(value):",
                "    return str(value)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    index = build_index(tmp_path, include_roots=("src",))
    qualnames = {symbol["qualname"]: symbol for symbol in index["symbols"]}
    edges = index["edges"]

    assert "demo.sample" in qualnames
    assert "demo.sample.Sample" in qualnames
    assert "demo.sample.Sample.run" in qualnames
    assert "demo.sample.helper" in qualnames
    assert any(edge["kind"] == "inherits" and edge["target"] == "BaseThing" for edge in edges)
    assert any(edge["kind"] == "calls" and edge["target"] == "helper" for edge in edges)


def test_summarize_index_includes_stats_and_queries(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "one.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")

    index = build_index(tmp_path, include_roots=("src",))
    summary = summarize_index(index)

    assert "# FlowScribe Codegraph" in summary
    assert "Files indexed" in summary
    assert "Recommended Queries" in summary
