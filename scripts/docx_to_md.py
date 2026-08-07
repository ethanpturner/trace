"""Convert the Word design documents under docs/ into Markdown.

The design corpus was authored in Word and committed as .docx, which GitHub cannot
render -- a link to one produces a download prompt rather than a page. This converts
them once, in a reproducible and reviewable way, rather than by hand.

Neither pandoc nor libreoffice is assumed to be present. The documents use real Word
heading styles, numbered/bulleted list paragraphs, and tables, and contain no bold
runs, no italics, and no hyperlinks, so a narrow converter covers them completely.

Usage:
    uv run python scripts/docx_to_md.py            # convert docs/ in place
    uv run python scripts/docx_to_md.py --check     # report what would change
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Final

W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

HEADING_PREFIX: Final[dict[str, str]] = {
    "Heading1": "#",
    "Heading2": "##",
    "Heading3": "###",
    "Heading4": "####",
    "Heading5": "#####",
    "Heading6": "######",
    "Title": "#",
}

REPO_ROOT: Final = Path(__file__).resolve().parents[1]

# Source .docx -> destination .md. Lower-cased and hyphenated so links need no
# percent-escaping. Threat_Model.md.docx is deliberately absent: it is a
# byte-identical copy of Agent_Design.md.docx (verified by hash) and its own title
# line reads "Trace - Agent Design". Converting it would publish a document that
# does not exist.
CONVERSIONS: Final[dict[str, str]] = {
    "docs/product/Vision.md.docx": "docs/product/vision.md",
    "docs/product/Design Principles.md.docx": "docs/product/design-principles.md",
    "docs/product/Roadmap.md.docx": "docs/product/roadmap.md",
    "docs/product/Future features.md.docx": "docs/product/future-features.md",
    "docs/architecture/Project_Scope.md.docx": "docs/architecture/project-scope.md",
    "docs/architecture/Current_Architecture.md.docx": "docs/architecture/current-architecture.md",
    "docs/architecture/Agent_Design.md.docx": "docs/architecture/agent-design.md",
    "docs/architecture/Data_Model.md.docx": "docs/architecture/data-model.md",
    "docs/architecture/Decision_Log.md.docx": "docs/architecture/decision-log.md",
    "docs/architecture/Evaluation_plan.md.docx": "docs/architecture/evaluation-plan.md",
}


def _is_on(run_properties: ET.Element | None, tag: str) -> bool:
    """Read a Word boolean run property, which may be absent, bare, or explicitly valued."""
    if run_properties is None:
        return False
    element = run_properties.find(f"{W}{tag}")
    if element is None:
        return False
    value = element.get(f"{W}val")
    return value is None or value in {"1", "true", "on"}


def _segments(node: ET.Element) -> list[tuple[str, bool, bool]]:
    """Flatten a paragraph or cell into (text, bold, italic) segments in document order."""
    out: list[tuple[str, bool, bool]] = []
    for run in node.iter(f"{W}r"):
        properties = run.find(f"{W}rPr")
        bold = _is_on(properties, "b")
        italic = _is_on(properties, "i")
        for child in run:
            if child.tag == f"{W}t":
                out.append((child.text or "", bold, italic))
            elif child.tag == f"{W}tab":
                out.append((" ", bold, italic))
            elif child.tag in (f"{W}br", f"{W}cr"):
                out.append(("\n", False, False))
    return out


def _render(segments: list[tuple[str, bool, bool]]) -> str:
    """Render segments to Markdown, merging adjacent runs that share formatting.

    Word splits a single visually-bold phrase across many runs. Emitting a marker
    per run would produce `**a****b**`, so runs are merged first. Markdown also
    requires the markers to hug the text, so surrounding whitespace is moved out.
    """
    merged: list[tuple[str, bool, bool]] = []
    for text, bold, italic in segments:
        if merged and merged[-1][1] == bold and merged[-1][2] == italic:
            merged[-1] = (merged[-1][0] + text, bold, italic)
        else:
            merged.append((text, bold, italic))

    parts: list[str] = []
    for text, bold, italic in merged:
        if not (bold or italic) or not text.strip():
            parts.append(text)
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        marker = "**" if bold else ""
        marker += "*" if italic else ""
        parts.append(f"{lead}{marker}{text.strip()}{marker}{trail}")

    joined = "".join(parts)
    joined = re.sub(r"[ \t]+", " ", joined)
    return "\n".join(line.strip() for line in joined.split("\n")).strip()


def _plain_text(node: ET.Element) -> str:
    """Render with all emphasis discarded, for headings and table cells."""
    return _render([(text, False, False) for text, _, _ in _segments(node)])


def _style_of(paragraph: ET.Element) -> str | None:
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    return None if style is None else style.get(f"{W}val")


def _numbering_of(paragraph: ET.Element) -> tuple[str, int] | None:
    """Return (numId, indent level) when the paragraph is a list item."""
    num_pr = paragraph.find(f"{W}pPr/{W}numPr")
    if num_pr is None:
        return None
    num_id = num_pr.find(f"{W}numId")
    if num_id is None:
        return None
    value = num_id.get(f"{W}val")
    if value is None:
        return None
    ilvl = num_pr.find(f"{W}ilvl")
    level_raw = None if ilvl is None else ilvl.get(f"{W}val")
    return value, int(level_raw) if level_raw is not None and level_raw.isdigit() else 0


def _ordered_list_ids(numbering_xml: bytes | None) -> set[tuple[str, int]]:
    """Identify which (numId, level) pairs render as numbered rather than bulleted.

    Word stores the marker format indirectly: a numId points at an abstractNumId,
    which holds a per-level numFmt. Anything other than "bullet" is ordered.
    """
    if numbering_xml is None:
        return set()
    root = ET.fromstring(numbering_xml)  # noqa: S314 - local, repo-controlled file

    formats: dict[str, dict[int, str]] = {}
    for abstract in root.findall(f"{W}abstractNum"):
        abstract_id = abstract.get(f"{W}abstractNumId")
        if abstract_id is None:
            continue
        levels: dict[int, str] = {}
        for lvl in abstract.findall(f"{W}lvl"):
            raw = lvl.get(f"{W}ilvl")
            fmt = lvl.find(f"{W}numFmt")
            if raw is not None and raw.isdigit() and fmt is not None:
                levels[int(raw)] = fmt.get(f"{W}val") or "bullet"
        formats[abstract_id] = levels

    ordered: set[tuple[str, int]] = set()
    for num in root.findall(f"{W}num"):
        num_id = num.get(f"{W}numId")
        abstract_ref = num.find(f"{W}abstractNumId")
        if num_id is None or abstract_ref is None:
            continue
        target = abstract_ref.get(f"{W}val")
        if target is None:
            continue
        for level, number_format in formats.get(target, {}).items():
            if number_format != "bullet":
                ordered.add((num_id, level))
    return ordered


def _table_to_markdown(table: ET.Element) -> list[str]:
    """Render a w:tbl as a Markdown table, treating the first row as the header."""
    rows: list[list[str]] = []
    for tr in table.findall(f"{W}tr"):
        cells = [
            _plain_text(tc).replace("|", "\\|").replace("\n", " ") for tc in tr.findall(f"{W}tc")
        ]
        if cells:
            rows.append(cells)
    if not rows:
        return []

    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header, *body = padded

    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * width) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return lines


def convert(docx_path: Path) -> str:
    """Convert one .docx into Markdown text."""
    with zipfile.ZipFile(docx_path) as archive:
        document = archive.read("word/document.xml")
        try:
            numbering = archive.read("word/numbering.xml")
        except KeyError:
            numbering = None

    ordered = _ordered_list_ids(numbering)
    body = ET.fromstring(document).find(f"{W}body")  # noqa: S314 - local, repo-controlled file
    if body is None:
        return ""

    lines: list[str] = []
    counters: dict[tuple[str, int], int] = {}
    in_list = False

    for node in body:
        if node.tag == f"{W}tbl":
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend(_table_to_markdown(node))
            lines.append("")
            in_list = False
            counters.clear()
            continue

        if node.tag != f"{W}p":
            continue

        style = _style_of(node)
        listing = _numbering_of(node)
        # Heading markup already conveys emphasis, so bold inside a heading is dropped
        # rather than rendered as `## **Text**`.
        text = _plain_text(node) if style in HEADING_PREFIX else _render(_segments(node))

        if not text:
            # A blank paragraph ends any run of list items but adds no output of
            # its own; spacing is normalised at the end.
            in_list = False
            counters.clear()
            continue

        if style in HEADING_PREFIX:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"{HEADING_PREFIX[style]} {text}")
            lines.append("")
            in_list = False
            counters.clear()
            continue

        if listing is not None:
            _, level = listing
            indent = "  " * level
            if listing in ordered:
                counters[listing] = counters.get(listing, 0) + 1
                marker = f"{counters[listing]}."
            else:
                marker = "-"
            if not in_list and lines and lines[-1] != "":
                lines.append("")
            lines.append(f"{indent}{marker} {text.replace(chr(10), ' ')}")
            in_list = True
            continue

        # A paragraph may carry explicit line breaks -- the document metadata blocks
        # use them. Emit each as its own paragraph; consecutive Markdown lines would
        # otherwise reflow into one, and a two-space hard break cannot survive the
        # trailing-whitespace pre-commit hook.
        for line in text.split("\n"):
            if not line:
                continue
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(line)
            lines.append("")
        in_list = False
        counters.clear()

    rendered = "\n".join(lines)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()
    return rendered + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change without writing files",
    )
    args = parser.parse_args()

    exit_code = 0
    for source, destination in CONVERSIONS.items():
        src = REPO_ROOT / source
        dst = REPO_ROOT / destination
        if not src.is_file():
            print(f"missing source: {source}", file=sys.stderr)
            exit_code = 1
            continue

        markdown = convert(src)
        current = dst.read_text(encoding="utf-8") if dst.is_file() else None

        if args.check:
            state = "unchanged" if current == markdown else "would write"
            print(f"{state:>12}  {destination}  ({len(markdown):,} chars)")
            if current != markdown:
                exit_code = 1
            continue

        dst.write_text(markdown, encoding="utf-8")
        print(f"{'wrote':>12}  {destination}  ({len(markdown):,} chars)")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
