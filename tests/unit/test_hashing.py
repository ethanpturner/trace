"""Tests for content hashing, against DEC-019's format and its per-type inputs.

DEC-019's own stated risk is that a hash computed over the wrong input verifies against itself
forever and only fails when something else changes. Tests that recompute the hash the same way the
implementation does would reproduce that failure exactly, so the expected digests below are
**literal constants**, checked against values produced outside this module.

The rest is the format. `sha256:` and 64 lowercase hex, rejected rather than normalized when it is
anything else -- two spellings of one hash compare unequal as strings, and a value that is
sometimes normalized is worse than one that is always refused. Issue #44.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import DomainModel
from trace_ai.domain.hashing import (
    ContentHash,
    content_hash,
    hash_quoted_text,
    hash_source_bytes,
    is_content_hash,
    verify_hash,
)

# sha256 of b"" and of b"trace", as literals. Recomputing them with hashlib here would test the
# implementation against itself, which is the failure DEC-019 names.
EMPTY = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TRACE = "sha256:eafe895eb8119e6e5d06463590b2ef81b3651c157d5c8e18f1889186c7fd0ac0"


def test_a_known_digest_matches_a_literal() -> None:
    """The anchor. If this passes, the algorithm and the rendering are both what DEC-019 says."""
    assert content_hash(b"") == EMPTY
    assert content_hash(b"trace") == TRACE


def test_the_literal_anchors_agree_with_hashlib() -> None:
    """Cross-check the constants, so a typo in one cannot make the test above lenient."""
    assert f"sha256:{hashlib.sha256(b'').hexdigest()}" == EMPTY
    assert f"sha256:{hashlib.sha256(b'trace').hexdigest()}" == TRACE


def test_the_format_is_the_one_section_eight_shows() -> None:
    value = content_hash(b"trace")
    algorithm, _, digest = value.partition(":")
    assert algorithm == "sha256"
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(character in "0123456789abcdef" for character in digest)


def test_hashing_is_deterministic() -> None:
    assert content_hash(b"architecture-overview.md") == content_hash(b"architecture-overview.md")


def test_one_changed_byte_changes_the_hash() -> None:
    assert content_hash(b"webhook signature verified") != content_hash(
        b"webhook signature verifieD"
    )


def test_a_line_ending_difference_is_visible() -> None:
    """The reason source documents are hashed as bytes rather than as decoded text.

    A file re-saved with CRLF endings is a changed file. Normalizing first would hide exactly the
    change the hash exists to detect.
    """
    assert hash_source_bytes(b"line one\nline two") != hash_source_bytes(b"line one\r\nline two")


def test_an_encoding_difference_is_visible() -> None:
    """Same argument, one layer up: two encodings of one string are two files."""
    text = "café"
    assert hash_source_bytes(text.encode("utf-8")) != hash_source_bytes(text.encode("latin-1"))


def test_quoted_text_is_hashed_as_utf8() -> None:
    """DEC-019 fixes the encoding for evidence, so the value does not depend on the platform."""
    assert hash_quoted_text("café") == content_hash("café".encode())


def test_whitespace_in_quoted_text_is_significant() -> None:
    """DEC-015 makes `quoted_text` verbatim, so trailing whitespace is part of the excerpt."""
    assert hash_quoted_text("all traffic uses TLS") != hash_quoted_text("all traffic uses TLS ")


def test_hashing_the_same_file_twice_agrees(tmp_path: Path) -> None:
    document = tmp_path / "architecture-overview.md"
    document.write_bytes(b"# Architecture\n\nWebhook requests are validated.\n")

    first = hash_source_bytes(document.read_bytes())
    second = hash_source_bytes(document.read_bytes())
    assert first == second

    document.write_bytes(b"# Architecture\n\nWebhook requests are validated!\n")
    assert hash_source_bytes(document.read_bytes()) != first


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sha256:",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # no prefix
        "sha256:E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",  # uppercase
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85",  # 63 chars
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8555",  # 65
        "sha256:zzzz0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # not hex
        "sha1:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sha256:example",  # section 8's placeholder, which is not a hash
    ],
)
def test_a_malformed_hash_is_rejected(value: str) -> None:
    assert not is_content_hash(value)


def test_a_well_formed_hash_is_accepted() -> None:
    assert is_content_hash(EMPTY)
    assert is_content_hash(content_hash(b"anything"))


def test_uppercase_is_rejected_rather_than_normalized() -> None:
    """Stated on its own because normalizing is the tempting fix and the wrong one.

    A hash that is sometimes lowered and sometimes not compares unequal to itself across the two
    code paths, and the mismatch surfaces as 'the document changed'.
    """
    assert not is_content_hash(EMPTY.upper().replace("SHA256", "sha256"))


def test_verify_accepts_matching_content() -> None:
    data = b"# Architecture\n"
    assert verify_hash(content_hash(data), data)


def test_verify_rejects_changed_content() -> None:
    assert not verify_hash(content_hash(b"# Architecture\n"), b"# Architecture!\n")


def test_verify_refuses_a_malformed_expected_value() -> None:
    """A malformed expected value is a bug, not a mismatch, and must not read as 'content changed'."""
    with pytest.raises(ValueError, match="is not a content hash"):
        verify_hash("sha256:example", b"anything")


def test_the_annotated_type_accepts_a_real_hash() -> None:
    class Document(DomainModel):
        content_hash: ContentHash

    assert Document(content_hash=EMPTY).content_hash == EMPTY


def test_the_annotated_type_rejects_the_placeholder_from_section_eight() -> None:
    """`content_hash: sha256:example` is the format precedent in the document, not a valid value."""

    class Document(DomainModel):
        content_hash: ContentHash

    with pytest.raises(ValidationError, match="is not a content hash"):
        Document(content_hash="sha256:example")


def test_the_rejection_names_the_expected_shape() -> None:
    class Document(DomainModel):
        content_hash: ContentHash

    with pytest.raises(ValidationError) as caught:
        Document(content_hash="nonsense")
    assert "64 lowercase hexadecimal" in str(caught.value)


def test_only_the_two_in_scope_inputs_have_helpers() -> None:
    """Prompt and catalog hashing belong to loaders that do not exist yet.

    DEC-019 requires one utility to compute every hash, which this module is. It does not require
    every call site to be written before its caller -- a helper nothing can call is a guess at an
    interface. This test records the boundary so its absence reads as a decision.
    """
    import trace_ai.domain.hashing as module

    helpers = {name for name in module.__all__ if name.startswith("hash_")}
    assert helpers == {"hash_source_bytes", "hash_quoted_text"}
