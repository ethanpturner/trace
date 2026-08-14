"""Tests for the artifact store, weighted toward the boundary it enforces.

Most of this file is about paths that must not be written. `SourceDocument.filename` is the
original name of a file supplied for review, so it is caller-supplied data reaching a path
expression, and `current-architecture.md` section 12 makes the assessment directory a trust
boundary rather than an organizing convention.

Traversal is asserted three ways because the three fail differently. A `..` component is caught by
the shape of the name. An absolute path is caught before that. A symlink is caught by neither --
the name is clean, and only resolving it reveals that the directory it lands in points somewhere
else. A test that checks only the first would pass against an implementation with the third hole
wide open.

Every test writes under `tmp_path`. Nothing here touches the repository or the real `data/`.
Issue #46.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from trace_ai.domain.hashing import content_hash
from trace_ai.infrastructure.filesystem.artifact_store import (
    AREAS,
    DEFAULT_ROOT,
    ArtifactStore,
    ArtifactStoreError,
    UnsafeFilenameError,
)

DOCUMENT = b"# Architecture Overview\n\nWebhook requests are validated.\n"


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore("asm-001", root=tmp_path)


def test_the_five_areas_are_the_ones_section_5_16_lists() -> None:
    assert AREAS == ("sources", "normalized", "outputs", "traces", "evaluation")


def test_the_layout_matches_the_document(store: ArtifactStore, tmp_path: Path) -> None:
    for name in AREAS:
        assert store.area(name) == tmp_path / "assessments" / "asm-001" / name
        assert store.area(name).is_dir()


def test_directories_are_created_on_demand_not_at_construction(tmp_path: Path) -> None:
    """Building a store to read from should not leave five empty directories behind."""
    ArtifactStore("asm-002", root=tmp_path)
    assert not (tmp_path / "assessments").exists()


def test_the_directory_is_named_for_the_identifier(store: ArtifactStore) -> None:
    """Section 5.16's example says `assessment-001`; DEC-018 settled the scheme afterwards.

    The directory is named for the real identifier, so there is one naming convention rather than
    a second one to keep in step with it.
    """
    assert store.assessment_root.name == "asm-001"


def test_an_unknown_area_is_rejected(store: ArtifactStore) -> None:
    with pytest.raises(ArtifactStoreError, match=re.escape("section 5.16")):
        store.area("scratch")


def test_a_store_must_be_bound_to_an_assessment() -> None:
    """`thr-007` names a Threat. A store rooted at one would create a plausible wrong directory."""
    with pytest.raises(ArtifactStoreError, match="names a Threat"):
        ArtifactStore("thr-007")


def test_a_malformed_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a valid identifier"):
        ArtifactStore("assessment-001")


def test_the_default_root_is_the_ignored_data_directory() -> None:
    """The store defaults into the directory `.gitignore` anchors a rule to."""
    assert DEFAULT_ROOT.name == "data"


def test_stored_content_is_byte_identical(store: ArtifactStore) -> None:
    """Section 5.4 preserves the original; DEC-019 hashes it; DEC-015 quotes it verbatim.

    A normalization applied at write time would break all three, and the breakage would not
    surface until an evidence hash failed against a document nobody had edited.
    """
    path = store.store_source("architecture-overview.md", DOCUMENT)
    assert path.read_bytes() == DOCUMENT


def test_line_endings_survive_storage(store: ArtifactStore) -> None:
    """The specific way "byte-identical" is usually lost."""
    crlf = b"line one\r\nline two\r\n"
    store.store_source("windows.md", crlf)
    assert store.read("sources", "windows.md") == crlf


def test_store_source_returns_the_path_the_document_model_records(
    store: ArtifactStore, tmp_path: Path
) -> None:
    path = store.store_source("architecture-overview.md", DOCUMENT)
    assert path == tmp_path / "assessments" / "asm-001" / "sources" / "architecture-overview.md"


def test_normalized_text_lands_in_its_own_area(store: ArtifactStore) -> None:
    path = store.store_normalized("architecture-overview.md", b"architecture overview\n")
    assert path.parent.name == "normalized"


def test_the_same_name_in_both_areas_does_not_collide(store: ArtifactStore) -> None:
    """A document and its normalization share a filename by design."""
    original = store.store_source("overview.md", DOCUMENT)
    normalized = store.store_normalized("overview.md", b"overview\n")
    assert original != normalized
    assert original.read_bytes() == DOCUMENT


def test_storing_the_same_content_twice_is_idempotent(store: ArtifactStore) -> None:
    first = store.store_source("overview.md", DOCUMENT)
    second = store.store_source("overview.md", DOCUMENT)
    assert first == second
    assert store.hash_of("sources", "overview.md") == content_hash(DOCUMENT)


def test_storing_different_content_under_a_used_name_is_refused(store: ArtifactStore) -> None:
    """Overwriting would leave every evidence reference pointing at bytes that no longer exist.

    DEC-015 forbids modifying `quoted_text` after creation and DEC-019 hashes the document over
    its raw bytes, so a silent replacement produces evidence that cannot be verified against a
    document nobody edited.
    """
    store.store_source("overview.md", DOCUMENT)
    with pytest.raises(ArtifactStoreError, match="different content"):
        store.store_source("overview.md", b"something else entirely\n")

    assert store.read("sources", "overview.md") == DOCUMENT, "the original must survive"


def test_an_interrupted_write_leaves_no_partial_artifact(
    store: ArtifactStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash mid-write must not leave a truncated file whose bytes no longer match the recorded
    content hash -- which would then be refused as `different content` and wedge the assessment.
    The write goes to a sibling temporary and is linked into place; a failure before the link
    leaves the target absent and cleans up the temporary."""
    import os

    def failing_link(src: object, dst: object) -> None:
        raise OSError("simulated crash before the link")

    # The store does `import os; os.link(...)`; the module object is shared, so patching it here
    # patches the store's call too.
    monkeypatch.setattr(os, "link", failing_link)

    with pytest.raises(OSError, match="simulated crash"):
        store.store_source("overview.md", DOCUMENT)

    sources = store.area("sources")
    assert not (sources / "overview.md").exists(), "a partial artifact was left behind"
    assert list(sources.iterdir()) == [], "the temporary was not cleaned up"

    # Recovery: with the fault gone, the same store call succeeds and reads back whole.
    monkeypatch.undo()
    store.store_source("overview.md", DOCUMENT)
    assert store.read("sources", "overview.md") == DOCUMENT


def test_two_assessments_do_not_collide_on_a_filename(tmp_path: Path) -> None:
    first = ArtifactStore("asm-001", root=tmp_path)
    second = ArtifactStore("asm-002", root=tmp_path)

    first.store_source("overview.md", b"first assessment\n")
    second.store_source("overview.md", b"second assessment\n")

    assert first.read("sources", "overview.md") == b"first assessment\n"
    assert second.read("sources", "overview.md") == b"second assessment\n"


def test_a_store_does_not_contain_another_assessments_path(tmp_path: Path) -> None:
    """The section 12 boundary, asserted directly rather than implied by path construction."""
    first = ArtifactStore("asm-001", root=tmp_path)
    second = ArtifactStore("asm-002", root=tmp_path)
    other = second.store_source("overview.md", DOCUMENT)

    assert not first.contains(other)
    assert second.contains(other)


def test_there_is_no_way_to_name_another_assessment(store: ArtifactStore) -> None:
    """Crossing the boundary is a different object to construct, not an argument to pass wrong.

    Asserted on the signatures, so adding an `assessment_id` parameter to a read or write method
    fails here with a docstring saying why that would be the wrong shape.
    """
    import inspect

    for name in ("store_source", "store_normalized", "read", "hash_of", "area"):
        parameters = set(inspect.signature(getattr(ArtifactStore, name)).parameters)
        assert "assessment_id" not in parameters, f"{name} takes another assessment's identifier"


@pytest.mark.parametrize(
    "filename",
    [
        "../../../etc/passwd",
        "..",
        "../overview.md",
        "sub/../../overview.md",
        "nested/overview.md",
        "",
        ".",
    ],
)
def test_a_traversing_filename_is_refused(store: ArtifactStore, filename: str) -> None:
    with pytest.raises(UnsafeFilenameError):
        store.store_source(filename, b"payload")


def test_an_absolute_filename_is_refused(store: ArtifactStore, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    with pytest.raises(UnsafeFilenameError, match="absolute"):
        store.store_source(str(outside), b"payload")
    assert not outside.exists()


def test_traversal_writes_nothing_at_all(store: ArtifactStore, tmp_path: Path) -> None:
    """The refusal has to happen before the write, not after it."""
    victim = tmp_path / "victim.md"
    victim.write_bytes(b"original\n")

    with pytest.raises(UnsafeFilenameError):
        store.store_source("../victim.md", b"overwritten\n")

    assert victim.read_bytes() == b"original\n"


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_a_symlinked_area_pointing_outside_is_refused(store: ArtifactStore, tmp_path: Path) -> None:
    """The case neither shape check catches: a clean name landing somewhere else.

    An implementation that validates only the filename passes every other traversal test in this
    file and writes into `elsewhere/` here.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    store.assessment_root.mkdir(parents=True)
    (store.assessment_root / "sources").symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(UnsafeFilenameError, match="symlink"):
        store.store_source("overview.md", DOCUMENT)

    assert list(elsewhere.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_reading_through_a_symlink_out_of_the_assessment_is_refused(
    store: ArtifactStore, tmp_path: Path
) -> None:
    secret = tmp_path / "other.md"
    secret.write_bytes(b"another assessment's document\n")
    store.area("sources")
    (store.assessment_root / "sources" / "overview.md").symlink_to(secret)

    with pytest.raises(UnsafeFilenameError, match="symlink"):
        store.read("sources", "overview.md")


def test_reading_a_missing_artifact_raises(store: ArtifactStore) -> None:
    with pytest.raises(ArtifactStoreError, match="is not stored"):
        store.read("sources", "absent.md")


def test_hash_of_uses_the_one_hashing_utility(store: ArtifactStore) -> None:
    """DEC-019: one utility computes and verifies every hash in the system."""
    store.store_source("overview.md", DOCUMENT)
    assert store.hash_of("sources", "overview.md") == content_hash(DOCUMENT)


def test_the_same_content_hashes_the_same_in_two_assessments(tmp_path: Path) -> None:
    first = ArtifactStore("asm-001", root=tmp_path)
    second = ArtifactStore("asm-002", root=tmp_path)
    first.store_source("overview.md", DOCUMENT)
    second.store_source("overview.md", DOCUMENT)

    assert first.hash_of("sources", "overview.md") == second.hash_of("sources", "overview.md")


def test_assessment_directories_are_owner_only(store: ArtifactStore, tmp_path: Path) -> None:
    """The store holds copies of material under review, on a machine DEC-004 assumes is local.

    Every directory the store creates under the data root must be owner-only, not just the leaf.
    `mkdir(parents=True, mode=0o700)` tightens only the leaf and leaves the ancestors at the umask
    default, so the assessment root and `assessments/` above it are checked too -- they are what
    #443 measured at 0o755.
    """
    if sys.platform == "win32":  # pragma: no cover -- POSIX mode bits do not apply
        pytest.skip("POSIX permissions")
    created = store.area("sources")
    for directory in (created, store.assessment_root, tmp_path / "assessments"):
        mode = directory.stat().st_mode & 0o777
        assert mode == 0o700, f"expected owner-only for {directory}, found {mode:o}"


def test_repr_names_the_assessment_and_the_root(store: ArtifactStore) -> None:
    """Logs and errors carry both, because a bare identifier is ambiguous across assessments."""
    text = repr(store)
    assert "asm-001" in text
    assert "ArtifactStore" in text
