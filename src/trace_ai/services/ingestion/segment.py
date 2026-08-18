"""Dividing a document into addressable units, per DEC-015.

Two rules, one per family of formats.

**Markdown and plain text segment at the shallowest heading level that occurs more than once.**
The qualifier is the whole rule. "Shallowest level present" is the intuitive statement and it fails
on the demo corpus: `architecture-overview.md` and `product-overview.md` each use `#` once as a
title and `##` for every section, so the shallowest level *present* is `#`, which turns a 734-line
document into one chunk — exactly the failure segmentation exists to prevent. A heading level that
appears once partitions nothing. Meanwhile five of the seven demo documents use `#` for every
section, so a fixed level fails in the other direction.

**JSON and YAML are addressed by JSON Pointer** (RFC 6901), with an addressable node being each
top-level mapping key and each element of a top-level sequence. Line numbers are populated so a
reviewer can find the passage, but the pointer is the address: two sequence elements can be
textually identical, so a line range does not identify one.

Every segment's `text` and line numbers come from **the original document**, never the normalized
artifact. Normalization is line-count preserving, so the two addressings agree — but taking the
text from the original is what makes `quoted_text` verbatim, which DEC-015 requires and evidence
verification depends on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import yaml

from trace_ai.domain.source_document import MediaType

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Segment", "segment"]

# An ATX heading: one to six hashes, whitespace, then text. A line of hashes alone is not a
# heading, which is why the title group requires a non-space character.
_HEADING: Final = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*$")

# A fenced block. Headings inside one are code, not structure -- the demo corpus contains no
# fences, which is exactly why this is easy to get wrong and worth handling before it appears.
_FENCE: Final = re.compile(r"^\s{0,3}(?:```|~~~)")

_PROSE: Final = frozenset({MediaType.MARKDOWN, MediaType.PLAIN_TEXT})


@dataclass(frozen=True, slots=True)
class Segment:
    """One addressable unit of a document, taken verbatim from the original.

    Line numbers are 1-based and inclusive, matching how a reviewer counts lines in an editor.
    For a PDF they address the extraction (DEC-123), and `page_number` carries the page the
    unit came from; both stay unset for every other format.
    """

    text: str
    start_line: int
    end_line: int
    section_title: str | None = None
    json_pointer: str | None = None
    page_number: int | None = None


def segment(text: str, media_type: MediaType) -> list[Segment]:
    """Divide a document into addressable units.

    Whitespace-only units are dropped rather than emitted. `EvidenceReference` requires non-empty
    `quoted_text`, so an empty segment could not become one -- and a citation of blank space is
    precisely what the DEC-009 separation exists to prevent.
    """
    lines = text.splitlines()
    if not lines:
        return []
    found = _prose(lines) if media_type in _PROSE else _structural(text, lines)
    return [unit for unit in found if unit.text.strip()]


def _headings(lines: Sequence[str]) -> list[tuple[int, int, str]]:
    """Every ATX heading outside a fenced block, as (line index, level, title)."""
    found: list[tuple[int, int, str]] = []
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if match := _HEADING.match(line):
            found.append((index, len(match.group(1)), match.group(2)))
    return found


def segmenting_level(lines: Sequence[str]) -> int | None:
    """The shallowest heading level that occurs more than once, or `None` if there is none.

    Exposed rather than private because it is the rule people will want to check against a real
    document, and reading it out of a chunk count is guesswork.
    """
    counts: dict[int, int] = {}
    for _, level, _ in _headings(lines):
        counts[level] = counts.get(level, 0) + 1
    repeated = [level for level, count in sorted(counts.items()) if count > 1]
    return repeated[0] if repeated else None


def _prose(lines: Sequence[str]) -> list[Segment]:
    level = segmenting_level(lines)
    if level is None:
        # DEC-015: a document with no repeated heading level is one chunk with no section title.
        return [Segment(text="\n".join(lines), start_line=1, end_line=len(lines))]

    boundaries = [(index, title) for index, found, title in _headings(lines) if found == level]
    starts = [index for index, _ in boundaries]

    segments: list[Segment] = []
    # Content before the first boundary belongs to no heading -- typically a title and an
    # introduction. It is emitted with no section title rather than dropped, because dropping it
    # would make part of the document uncitable.
    if starts[0] > 0:
        segments.append(
            Segment(text="\n".join(lines[: starts[0]]), start_line=1, end_line=starts[0])
        )

    for position, (index, title) in enumerate(boundaries):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        segments.append(
            Segment(
                text="\n".join(lines[index:end]),
                start_line=index + 1,
                end_line=end,
                section_title=title,
            )
        )
    return segments


def _escape(token: str) -> str:
    """RFC 6901 escaping: `~` becomes `~0` and `/` becomes `~1`, in that order."""
    return token.replace("~", "~0").replace("/", "~1")


def _structural(text: str, lines: Sequence[str]) -> list[Segment]:
    """Address a JSON or YAML document by JSON Pointer, with lines from the parser's marks.

    Composition uses PyYAML's `SafeLoader`, which builds a node graph without constructing Python
    objects -- the same reason the loader parses with `safe_load`. JSON is composed with the same
    parser: it is a subset of YAML in every respect this needs, and the loader has already
    validated the document with `json.loads`, so composition here is only for positions.

    If composition fails -- a tab-indented JSON file is the realistic case, since YAML forbids tabs
    for indentation -- the document is addressed as one segment rather than not at all. That is a
    worse address and a better outcome than an uncitable document.
    """
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return [Segment(text="\n".join(lines), start_line=1, end_line=len(lines))]

    if isinstance(node, yaml.MappingNode):
        pairs = [(_escape(str(key.value)), str(key.value), key, value) for key, value in node.value]
    elif isinstance(node, yaml.SequenceNode):
        pairs = [(str(index), f"[{index}]", child, child) for index, child in enumerate(node.value)]
    else:
        # A bare scalar. The loader refuses these, so reaching here means a caller bypassed it.
        return [Segment(text="\n".join(lines), start_line=1, end_line=len(lines))]

    segments: list[Segment] = []
    for token, title, anchor, value in pairs:
        start = anchor.start_mark.line + 1
        # An end mark can point at the first line of whatever follows, so clamp it back to the
        # last line the node actually occupies.
        end = min(max(value.end_mark.line, start), len(lines))
        segments.append(
            Segment(
                text="\n".join(lines[start - 1 : end]),
                start_line=start,
                end_line=end,
                section_title=title,
                json_pointer=f"/{token}",
            )
        )
    return segments
