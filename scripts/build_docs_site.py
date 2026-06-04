"""Build a minimal local HTML help site from Markdown docs."""

from __future__ import annotations

import html
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"
OUTPUT_ROOT = PROJECT_ROOT / "build" / "docs-site"

DOC_FILES = (
    ("index.html", "FlowScribe Help", ("user-guide.md", "gui-user-guide.md", "release-installation.md")),
    ("model-guide.html", "Model Guide", ("user-guide.md", "gui-user-guide.md", "vad-guide.md")),
)


def _markdown_to_html(title: str, sources: tuple[str, ...]) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'>",
        f"  <title>{html.escape(title)}</title>",
        "  <style>body{font-family:Segoe UI,Arial,sans-serif;max-width:980px;margin:0 auto;padding:24px;line-height:1.6;}pre{background:#f4f4f4;padding:12px;overflow:auto;}code{font-family:Consolas,monospace;}h1,h2,h3{margin-top:1.4em;}nav{margin-bottom:24px;padding:12px;background:#eef3f8;border-radius:8px;}section{margin-bottom:32px;}blockquote{border-left:4px solid #ccc;padding-left:12px;color:#555;}</style>",
        "</head>",
        "<body>",
        "<nav><a href='index.html'>Help Home</a> | <a href='model-guide.html'>Model Guide</a></nav>",
        f"<h1>{html.escape(title)}</h1>",
    ]
    for source_name in sources:
        source_path = DOCS_ROOT / source_name
        if not source_path.exists():
            continue
        parts.append(f"<section><h2>{html.escape(source_name)}</h2>")
        raw = source_path.read_text(encoding="utf-8")
        escaped = html.escape(raw)
        parts.append(f"<pre>{escaped}</pre>")
        parts.append("</section>")
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts) + "\n"


def build_docs_site(output_root: Path = OUTPUT_ROOT) -> tuple[Path, ...]:
    output_root.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for filename, title, sources in DOC_FILES:
        target = output_root / filename
        target.write_text(_markdown_to_html(title, sources), encoding="utf-8")
        generated.append(target)
    return tuple(generated)


if __name__ == "__main__":
    built = build_docs_site()
    for path in built:
        print(path)
