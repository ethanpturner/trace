"""Tests guarding the empirical basis of DEC-015.

DEC-015 decides two things about evidence locations, and both were settled by measuring the
demo corpus rather than by reasoning about documents in general. These tests pin the
measurements so the decision cannot quietly stop being true.

**Normalization is line-count preserving.** That rule is currently free because no input
document contains a CRLF line ending, trailing whitespace, front matter, or a tab -- there is
nothing for a line-preserving normalizer to refuse to do. A document that introduces one of
those makes the constraint cost something, which is the moment to re-read DEC-015 rather than
to work around it.

**Markdown is segmented at the shallowest heading level present in that document**, chosen per
document rather than fixed. The corpus is inconsistent about heading depth, so any fixed level
fails in both directions: segmenting on `#` gives a 734-line document one chunk, and segmenting
on `##` gives five of the seven documents none. These tests assert that the fixed rules fail, so
a future implementer who reaches for one finds out here instead of in an evidence reference.

They check the corpus, not the ingestion code, which does not exist yet. When it does, the
line-count assertion moves onto real normalized artifacts and this file keeps the precondition.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT

INPUT_DIR = PROJECT_ROOT / "demo" / "forgeflow" / "input"
STRUCTURED_INPUT = INPUT_DIR / "structured-system-input.yaml"

HEADING = re.compile(r"^(#{1,6}) ")


def markdown_files() -> list[Path]:
    return sorted(INPUT_DIR.glob("*.md"))


def all_input_files() -> list[Path]:
    return sorted(p for p in INPUT_DIR.iterdir() if p.is_file() and not p.name.startswith("."))


def heading_levels(text: str) -> list[int]:
    """Every ATX heading level in document order."""
    return [len(m.group(1)) for line in text.splitlines() if (m := HEADING.match(line))]


def segmenting_level(text: str) -> int | None:
    """The shallowest heading level that occurs more than once.

    Not simply the shallowest level present: a document whose only `#` is its title would
    segment into one chunk under that reading, which is the failure DEC-015 exists to avoid.
    A level that appears once does not partition anything.
    """
    levels = heading_levels(text)
    for level in sorted(set(levels)):
        if levels.count(level) > 1:
            return level
    return None


def chunk_count(text: str, level: int) -> int:
    """How many chunks segmenting at `level` would produce."""
    return sum(1 for found in heading_levels(text) if found == level)


# --- the precondition that makes line-preserving normalization free --------------------


@pytest.mark.parametrize("path", all_input_files(), ids=lambda p: p.name)
def test_input_file_has_no_crlf(path: Path) -> None:
    assert b"\r\n" not in path.read_bytes(), (
        f"{path.name} has CRLF line endings. Converting them is line-preserving, so DEC-015 "
        f"still holds -- but the corpus is no longer trivially clean, so re-read the decision."
    )


@pytest.mark.parametrize("path", all_input_files(), ids=lambda p: p.name)
def test_input_file_has_no_trailing_whitespace(path: Path) -> None:
    offenders = [
        i for i, line in enumerate(path.read_text().splitlines(), 1) if line != line.rstrip()
    ]
    assert not offenders, f"{path.name} has trailing whitespace on line(s) {offenders[:5]}"


@pytest.mark.parametrize("path", all_input_files(), ids=lambda p: p.name)
def test_input_file_has_no_front_matter(path: Path) -> None:
    """Front matter is the hazard DEC-015 actually forecloses.

    Stripping it would shift every line below it, so a line-preserving normalizer must leave it
    in place. A document that has some is the case worth re-reading the decision over.
    """
    first = path.read_text().splitlines()[:1]
    assert first != ["---"], (
        f"{path.name} starts with front matter. DEC-015 forbids stripping it, because doing so "
        f"would shift every line below and invalidate the line numbers on every evidence "
        f"reference into this document."
    )


@pytest.mark.parametrize("path", all_input_files(), ids=lambda p: p.name)
def test_input_file_is_nfc_normalized(path: Path) -> None:
    text = path.read_text()
    assert unicodedata.normalize("NFC", text) == text, (
        f"{path.name} is not NFC-normalized. NFC conversion is line-preserving so DEC-015 holds, "
        f"but quoted_text is stored verbatim from the original, so the stored evidence would "
        f"carry the un-normalized form."
    )


# --- the segmentation rule ------------------------------------------------------------


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: p.name)
def test_markdown_file_has_headings(path: Path) -> None:
    assert heading_levels(path.read_text()), (
        f"{path.name} has no headings. DEC-015 makes that one chunk with section_title unset, "
        f"which is defined behaviour but is worth noticing."
    )


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: p.name)
def test_segmenting_rule_yields_multiple_chunks(path: Path) -> None:
    """The rule DEC-015 chose produces sensible granularity on every document."""
    text = path.read_text()
    level = segmenting_level(text)
    assert level is not None, f"{path.name} has no heading level occurring more than once"
    count = chunk_count(text, level)
    assert count > 1, (
        f"{path.name} segments into {count} chunk(s) at h{level}. A single chunk for a whole "
        f"document defeats addressable evidence."
    )


def test_title_only_heading_level_is_not_chosen_as_the_segmenting_level() -> None:
    """The case that makes 'shallowest level present' the wrong rule.

    Two documents use `#` once as a title and `##` for every section. Segmenting at the
    shallowest level *present* would give each of them one chunk -- 734 lines in one case.
    """
    title_style = [p for p in markdown_files() if chunk_count(p.read_text(), 1) == 1]
    assert title_style, (
        "Expected at least one document using `#` once as a title. If none remains, the "
        "distinction between 'shallowest present' and 'shallowest repeated' no longer bites "
        "on this corpus and DEC-015's rule statement should be re-read."
    )
    for path in title_style:
        text = path.read_text()
        assert segmenting_level(text) != 1, f"{path.name} would collapse to a single chunk"
        assert chunk_count(text, segmenting_level(text) or 0) > 1


def test_a_fixed_heading_level_would_fail_the_corpus() -> None:
    """The finding that motivated the per-document rule, asserted so it cannot be forgotten.

    Segmenting always on `#` collapses a 734-line document to one chunk. Segmenting always on
    `##` gives most documents none. Neither fixed rule is usable here.
    """
    always_h1_broken = []
    always_h2_broken = []
    for path in markdown_files():
        text = path.read_text()
        if chunk_count(text, 1) <= 1:
            always_h1_broken.append(path.name)
        if chunk_count(text, 2) == 0:
            always_h2_broken.append(path.name)

    assert always_h1_broken, (
        "Expected a fixed h1 rule to collapse at least one document to a single chunk. "
        "If the corpus changed so that it no longer does, DEC-015's reasoning needs revisiting."
    )
    assert always_h2_broken, (
        "Expected a fixed h2 rule to produce zero chunks for at least one document. "
        "If the corpus changed so that it no longer does, DEC-015's reasoning needs revisiting."
    )


# --- structured input -----------------------------------------------------------------


def test_structured_input_top_level_keys_are_addressable() -> None:
    """DEC-015 addresses JSON and YAML by JSON Pointer, one node per top-level key.

    Every top-level key must therefore produce a distinct pointer.
    """
    loaded: Any = yaml.safe_load(STRUCTURED_INPUT.read_text())
    assert isinstance(loaded, dict)
    pointers = [f"/{key}" for key in loaded]
    assert len(pointers) == len(set(pointers))
    assert len(pointers) > 1


def test_structured_input_sequence_elements_are_addressable() -> None:
    """A top-level sequence's elements are separately addressable, per DEC-015.

    This is why a line range is not an address here: two elements can be textually identical,
    and `- name: web` means nothing without knowing it is `components[0]`.
    """
    loaded: Any = yaml.safe_load(STRUCTURED_INPUT.read_text())
    sequences = {k: v for k, v in loaded.items() if isinstance(v, list)}
    assert sequences, "expected at least one top-level sequence in the structured input"

    pointers = [f"/{key}/{i}" for key, items in sequences.items() for i in range(len(items))]
    assert len(pointers) == len(set(pointers))
