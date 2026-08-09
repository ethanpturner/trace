"""Normalization, which is defined by what it may not do.

DEC-015 makes normalization **line-count preserving by construction**: line *n* of the normalized
artifact is line *n* of the original, always. That single property is what makes evidence locations
unambiguous — every location field addresses the original document, and because line counts cannot
change, addressing the original and addressing the normalized artifact are the same address.

Permitted: convert line endings to LF, strip trailing whitespace within a line, normalize Unicode
to NFC.

Forbidden: remove blank lines, collapse consecutive blank lines, unwrap or rewrap paragraphs, strip
front matter. Every one of those changes a line count, and each is a thing a reasonable person
would call tidying. The list exists because the property is easy to break by improving something.

The transformations are also all idempotent, so normalizing an already-normalized artifact returns
it unchanged. That is worth having rather than assuming: it means a document re-ingested after a
crash produces byte-identical output, and `content_hash` comparisons across runs mean something.
"""

from __future__ import annotations

import unicodedata

__all__ = ["line_count", "normalize"]


def normalize(text: str) -> str:
    """Apply DEC-015's permitted transformations, and nothing else.

    Order matters only in that line splitting comes first: `str.splitlines` recognizes more line
    terminators than `\\n` and `\\r\\n` -- form feed, next line, line separator -- and treating any
    of them as content rather than as a break would change what "line *n*" means.
    """
    lines = text.splitlines()
    stripped = [unicodedata.normalize("NFC", line).rstrip() for line in lines]
    joined = "\n".join(stripped)

    # A trailing newline is a line terminator, not a blank line, and `splitlines` drops it. Putting
    # it back keeps the byte-level shape of an ordinary text file without adding a line.
    return joined + "\n" if text.endswith(("\n", "\r")) else joined


def line_count(text: str) -> int:
    """Lines as `normalize` counts them, so a caller comparing two documents uses one definition."""
    return len(text.splitlines())
