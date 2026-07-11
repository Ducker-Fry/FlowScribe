"""Build a minimal local HTML help site from Markdown docs.

Converts Markdown to proper HTML (not raw markdown in <pre> tags)
so the docs render correctly in a browser.
"""

from __future__ import annotations

import html as html_mod
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"
OUTPUT_ROOT = PROJECT_ROOT / "build" / "docs-site"
ASSETS_ROOT = DOCS_ROOT / "assets"
HTML_OUTPUT_ENCODING = "utf-8-sig"

DOC_FILES = (
    ("index.html", "FlowScribe Help", ("user-guide.md", "gui-user-guide.md", "release-installation.md")),
    (
        "index-en.html",
        "FlowScribe Help (EN)",
        ("user-guide-en.md", "gui-user-guide-en.md", "release-installation-en.md"),
    ),
    ("model-guide.html", "Model Guide", ("user-guide.md", "gui-user-guide.md", "vad-guide.md")),
    (
        "model-guide-en.html",
        "Model Guide (EN)",
        ("user-guide-en.md", "gui-user-guide-en.md", "vad-guide-en.md"),
    ),
)

_CSS = """\
body{font-family:Segoe UI,Arial,sans-serif;max-width:980px;margin:0 auto;padding:24px;line-height:1.6;}
pre{background:#f4f4f4;padding:12px;overflow:auto;border-radius:4px;}
code{font-family:Consolas,monospace;background:#f0f0f0;padding:1px 4px;border-radius:3px;}
pre code{background:transparent;padding:0;}
h1,h2,h3{margin-top:1.4em;}
nav{margin-bottom:24px;padding:12px;background:#eef3f8;border-radius:8px;}
section{margin-bottom:32px;}
blockquote{border-left:4px solid #ccc;padding-left:12px;color:#555;margin:1em 0;}
table{border-collapse:collapse;width:100%;margin:1em 0;}
th,td{border:1px solid #ddd;padding:8px;text-align:left;}
th{background:#f4f4f4;}
img{max-width:100%;height:auto;}
hr{border:none;border-top:2px solid #eee;margin:1.5em 0;}
ul,ol{padding-left:1.5em;}
p{margin:0.5em 0;}
"""


def _escape(s: str) -> str:
    """HTML-escape a plain-text string."""
    return html_mod.escape(s, quote=True)


def _inline(md: str) -> str:
    """Convert inline Markdown to HTML with proper HTML escaping.

    Steps:
      1. Save inline code spans (`` `code` ``) so their content isn't double-escaped.
      2. HTML-escape the remaining text.
      3. Restore code spans as <code> tags.
      4. Convert bold, italic, links, images.
    """
    # --- step 1: protect inline code spans ---
    codes: list[str] = []
    def _capture_code(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00CODE{codes.index(m.group(1))}\x00"
    # handle backtick code spans
    md = re.sub(r"`([^`]+)`", _capture_code, md)

    # --- step 2: HTML-escape everything ---
    md = _escape(md)

    # --- step 3: restore code spans ---
    for i, snippet in enumerate(codes):
        md = md.replace(f"\x00CODE{i}\x00", f"<code>{_escape(snippet)}</code>")

    # --- step 4: inline markup on escaped text ---
    # bold
    md = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", md)
    # italic (*word*)
    md = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", md)
    # italic (_word_)
    md = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", md)
    # image ![alt](url)
    md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', md)
    # link [text](url)
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', md)

    return md


def _md_to_html(md_text: str) -> str:
    """Convert full Markdown document to HTML."""
    lines = md_text.split("\n")
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    in_list = False       # True when inside <ul> or <ol>
    list_type: str | None = None  # "ul" | "ol" | None
    i = 0

    def _close_list() -> None:
        nonlocal in_list, list_type
        if in_list and list_type:
            out.append(f"</{list_type}>")
        in_list = False
        list_type = None

    def _start_list(t: str) -> None:
        _close_list()
        nonlocal in_list, list_type
        in_list = True
        list_type = t
        out.append(f"<{t}>")

    while i < len(lines):
        line = lines[i]

        # ---------- code blocks (fenced) ----------
        if line.startswith("```"):
            if in_code:
                body = "\n".join(code_buf)
                lang_attr = f' class="language-{_escape(code_lang)}"' if code_lang else ""
                out.append(f"<pre><code{lang_attr}>{_escape(body)}</code></pre>")
                code_buf.clear()
                in_code = False
                code_lang = ""
            else:
                in_code = True
                code_lang = line[3:].strip()
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # ---------- blank line ----------
        if line.strip() == "":
            _close_list()
            out.append("")  # preserve blank line as separator
            i += 1
            continue

        # ---------- horizontal rule ----------
        if re.match(r"^[-*_]{3,}\s*$", line):
            _close_list()
            out.append("<hr>")
            i += 1
            continue

        # ---------- headings ----------
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            _close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # ---------- blockquote ----------
        if line.startswith("> "):
            _close_list()
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            i += 1
            continue

        # ---------- unordered list ----------
        m = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if m:
            if not in_list or list_type != "ul":
                _start_list("ul")
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # ---------- ordered list ----------
        m = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if m:
            if not in_list or list_type != "ol":
                _start_list("ol")
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # ---------- table ----------
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            _close_list()
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # check next line for separator row (header indicator)
            # Separator rows contain only | - : and whitespace, e.g. |---|---|
            _sep = re.compile(r"^\|[\s:\-|]+\|$")
            if (
                i + 1 < len(lines)
                and _sep.match(lines[i + 1].strip())
            ):
                # header row
                out.append("<table>")
                out.append("<thead><tr>")
                for c in cells:
                    out.append(f"<th>{_inline(c)}</th>")
                out.append("</tr></thead><tbody>")
                i += 2  # skip separator
                while i < len(lines):
                    row = lines[i].strip()
                    if not (row.startswith("|") and row.endswith("|")):
                        break
                    row_cells = [c.strip() for c in row.strip("|").split("|")]
                    out.append("<tr>")
                    for c in row_cells:
                        out.append(f"<td>{_inline(c)}</td>")
                    out.append("</tr>")
                    i += 1
                out.append("</tbody></table>")
                continue
            else:
                # standalone pipe row (no header)
                out.append("<table><tr>")
                for c in cells:
                    out.append(f"<td>{_inline(c)}</td>")
                out.append("</tr></table>")
                i += 1
                continue

        # ---------- regular paragraph ----------
        _close_list()
        out.append(f"<p>{_inline(line)}</p>")
        i += 1

    _close_list()
    return "\n".join(out)


def _build_page(title: str, sources: tuple[str, ...]) -> str:
    is_english = title.endswith("(EN)")
    nav = (
        "<nav>"
        "<a href='index.html'>Help Home</a> | "
        "<a href='index-en.html'>Help Home (EN)</a> | "
        "<a href='model-guide.html'>Model Guide</a> | "
        "<a href='model-guide-en.html'>Model Guide (EN)</a>"
        "</nav>"
    )
    parts = [
        "<!DOCTYPE html>",
        f"<html lang='{'en' if is_english else 'zh-CN'}'>",
        "<head>",
        "  <meta charset='utf-8'>",
        f"  <title>{_escape(title)}</title>",
        f"  <style>{_CSS}</style>",
        "</head>",
        "<body>",
        nav,
        f"<h1>{_escape(title)}</h1>",
    ]
    for name in sources:
        path = DOCS_ROOT / name
        if not path.exists():
            continue
        parts.append(f"<section><h2>{_escape(name)}</h2>")
        parts.append(_md_to_html(path.read_text(encoding="utf-8")))
        parts.append("</section>")
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts) + "\n"


def build_docs_site(output_root: Path = OUTPUT_ROOT) -> tuple[Path, ...]:
    output_root.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for filename, title, sources in DOC_FILES:
        target = output_root / filename
        # Write a UTF-8 BOM so Windows text readers do not mis-detect Chinese HTML as ANSI/ACP.
        target.write_text(_build_page(title, sources), encoding=HTML_OUTPUT_ENCODING)
        generated.append(target)
    if ASSETS_ROOT.exists():
        target_assets_root = output_root / "assets"
        if target_assets_root.exists():
            for item in target_assets_root.iterdir():
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            target_assets_root.mkdir(parents=True, exist_ok=True)
        for source_path in ASSETS_ROOT.iterdir():
            target_path = target_assets_root / source_path.name
            if source_path.is_dir():
                import shutil
                shutil.copytree(source_path, target_path, dirs_exist_ok=True)
            else:
                target_path.write_bytes(source_path.read_bytes())
    return tuple(generated)


if __name__ == "__main__":
    built = build_docs_site()
    for path in built:
        print(path)
