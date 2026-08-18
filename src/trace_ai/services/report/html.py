"""The rendered report as an HTML page: a derived view, not a second report (#527, DEC-108).

DEC-035 makes Markdown the report format, sixteen sections, one owner each, and this module
re-decides none of it: the input is the *rendered* Markdown deliverable, and the output is a
deterministic transform of it. There is no second template and no second section inventory to
drift — a section exists in the HTML because it exists in the render, with the same heading,
the same anchors, and the same text.

**Everything is escaped except the whitelisted structure.** The report body carries
source-derived text — finding descriptions, quoted evidence — and the transform treats every
line as untrusted: text nodes pass through `html.escape`, and only the constructs the renderer
itself emits become markup (headings, tables, fenced blocks, list lines, the exact
`<a id="..."></a>` anchor form, bold, single-star emphasis, and fragment-only links). A
`<script>` in a description renders as text. Ownership comments (`<!-- ... -->`) are dropped:
they are the template's notes to editors, not report content.

**Deterministic.** Two conversions of the same Markdown are byte-identical; the page carries no
clock, no environment value, and no path.
"""

from __future__ import annotations

import html
import re
from typing import Final

__all__ = ["render_report_html"]

_ANCHOR: Final = re.compile(r'^<a id="[a-z][a-z0-9-]*"></a>$')
_HEADING: Final = re.compile(r"^(#{1,4}) (.+)$")
_BOLD: Final = re.compile(r"\*\*(.+?)\*\*")
_EMPHASIS: Final = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_FRAGMENT_LINK: Final = re.compile(r"\[([^\]\n]+)\]\(#([a-z][a-z0-9-]*)\)")

_STYLE: Final = """
:root { --fg: #1f2328; --muted: #57606a; --line: #d0d7de; --bg: #ffffff; --head: #f6f8fa; }
body { background: var(--bg); color: var(--fg); margin: 0 auto; max-width: 60rem;
       padding: 2rem 1.5rem; font: 16px/1.6 system-ui, sans-serif; }
h1, h2, h3, h4 { line-height: 1.25; }
h2 { border-bottom: 1px solid var(--line); padding-bottom: .3rem; margin-top: 2.2rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .95em; }
th, td { border: 1px solid var(--line); padding: .4rem .6rem; text-align: left;
         vertical-align: top; }
th { background: var(--head); }
pre { background: var(--head); border: 1px solid var(--line); border-radius: 6px;
      padding: .8rem; overflow-x: auto; font-size: .9em; }
em { color: var(--muted); }
details.lineage { border: 1px solid var(--line); border-radius: 6px; margin: .6rem 0;
                  padding: .4rem .8rem; }
details.lineage summary { cursor: pointer; font-weight: 600; }
details.lineage h4 { margin: .8rem 0 .2rem; font-size: .95em; }
details.lineage ul { margin: .2rem 0 .6rem; }
"""


def _inline(text: str) -> str:
    """One text node: escaped first, then the renderer's own inline forms become markup."""
    escaped = html.escape(text, quote=False)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _EMPHASIS.sub(r"<em>\1</em>", escaped)
    return _FRAGMENT_LINK.sub(r'<a href="#\2">\1</a>', escaped)


def _table_row(line: str, *, header: bool) -> str:
    tag = "th" if header else "td"
    # Split on unescaped pipes; the renderer escapes literal pipes in cells as `\|`.
    cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
    rendered = "".join(
        f"<{tag}>{_inline(cell.replace(chr(92) + '|', '|'))}</{tag}>" for cell in cells
    )
    return f"<tr>{rendered}</tr>"


def render_report_html(markdown: str, *, title: str, appendix: str | None = None) -> str:
    """The report page, converted line by line from the rendered Markdown.

    `appendix` is an already-rendered HTML fragment appended after the converted body — the
    lineage appendix (`lineage_html.py`, #600) is the one caller. It is trusted markup by
    construction: its builder owns the escaping of every text node it embeds, exactly as this
    transform owns the escaping of the Markdown's. Passing source-derived text here raw would
    bypass the fence; nothing in the tree does, and the appendix builder's tests hold that.
    """
    body: list[str] = []
    paragraph: list[str] = []
    fence: list[str] | None = None
    listing = False
    table: list[str] | None = None

    def flush_paragraph() -> None:
        if paragraph:
            body.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal listing
        if listing:
            body.append("</ul>")
            listing = False

    def flush_table() -> None:
        nonlocal table
        if table is not None:
            rows = [_table_row(table[0], header=True)]
            rows += [_table_row(line, header=False) for line in table[2:]]
            body.append("<table>" + "".join(rows) + "</table>")
            table = None

    for line in markdown.splitlines():
        if fence is not None:
            if line.strip() == "```":
                body.append(f"<pre><code>{html.escape(chr(10).join(fence))}</code></pre>")
                fence = None
            else:
                fence.append(line)
            continue
        if line.strip() == "```":
            flush_paragraph()
            flush_list()
            flush_table()
            fence = []
            continue
        if line.startswith("|"):
            flush_paragraph()
            flush_list()
            table = [line] if table is None else [*table, line]
            continue
        flush_table()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        if _ANCHOR.match(stripped):
            flush_paragraph()
            flush_list()
            body.append(stripped)
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            body.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not listing:
                body.append("<ul>")
                listing = True
            body.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    flush_table()
    if fence is not None:
        body.append(f"<pre><code>{html.escape(chr(10).join(fence))}</code></pre>")

    content = "\n".join(body)
    if appendix:
        content += "\n" + appendix
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"{content}\n</body>\n</html>\n"
    )
