"""Tests for evidence retrieval and integrity verification.

This module is the interface `agent-design.md` section 22 requires agents to sit behind, so two
groups of tests are about what it refuses rather than what it returns: a lookup crossing
assessments, and any path leaving through `render_for_prompt`.

The verification tests are the reason `content_hash` is stored at all. `data-model.md` section 35
keeps hashes for filesystem artifacts, and a hash nothing checks is a hash that is always right.
Three outcomes are distinguished because a boolean would collapse *the file is gone* into *the
quotation is stale*, and those want different responses. Issue #56.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence import index as index_module
from trace_ai.services.evidence.index import (
    CheckedBy,
    EvidenceIndex,
    EvidenceNotFoundError,
    VerificationOutcome,
)
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader

FORGEFLOW_INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def indexed(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, list[EvidenceReference]]]:
    """One assessment with the whole ForgeFlow corpus loaded and indexed."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        references: list[EvidenceReference] = []
        for document in DocumentLoader(handle).load_directory(FORGEFLOW_INPUT):
            references.extend(index_document(handle, document))
        yield handle, references


# ------------------------------------------------------------------------------------------
# Retrieval
# ------------------------------------------------------------------------------------------


def test_get_returns_a_known_reference(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    index = EvidenceIndex(handle)

    assert index.get(references[0].id) == references[0]


def test_get_raises_for_an_unknown_identifier(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, _ = indexed
    with pytest.raises(EvidenceNotFoundError, match="evd-9999"):
        EvidenceIndex(handle).get("evd-9999")


def test_a_lookup_crossing_assessments_raises(tmp_path: Path) -> None:
    """The read-path enforcement of the section 12 boundary, asserted directly.

    The error is identical to the unknown-identifier one on purpose: a caller who could tell them
    apart could enumerate another assessment's identifiers by asking.
    """
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        configuration = default_configuration("primary-development", "stride-scenario-based")
        first = service.handle(service.create("First", configuration).id)
        second = service.handle(service.create("Second", configuration).id)

        document = DocumentLoader(first).load_document(
            FORGEFLOW_INPUT / "product-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
        references = index_document(first, document)

        with pytest.raises(EvidenceNotFoundError):
            EvidenceIndex(second).get(references[0].id)


def test_for_document_returns_references_in_chunk_order(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    document_id = references[0].source_document_id
    found = EvidenceIndex(handle).for_document(document_id)

    assert found
    assert all(reference.source_document_id == document_id for reference in found)
    assert [reference.chunk_index for reference in found] == sorted(
        reference.chunk_index or 0 for reference in found
    )


def test_for_document_returns_nothing_for_an_unknown_document(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, _ = indexed
    assert EvidenceIndex(handle).for_document("src-999") == []


def test_resolve_fails_on_the_first_unknown_identifier(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    with pytest.raises(EvidenceNotFoundError):
        EvidenceIndex(handle).resolve([references[0].id, "evd-9999"])


# ------------------------------------------------------------------------------------------
# Verification
# ------------------------------------------------------------------------------------------


def test_a_freshly_indexed_reference_matches(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    result = EvidenceIndex(handle).verify(references[0].id)

    assert result.outcome is VerificationOutcome.MATCHES
    assert result.checked_by is CheckedBy.LINE_RANGE
    assert result.ok


def test_verify_all_reports_nothing_after_indexing_the_corpus(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """Over a hundred references across eight documents, all verifiable against their sources."""
    handle, references = indexed
    assert len(references) > 100
    assert EvidenceIndex(handle).verify_all() == []


def test_editing_the_artifact_reports_content_changed(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """The stale-evidence case, and the reason `content_hash` is stored.

    DEC-015 forbids editing the reference to agree with the new text; a correction is a new
    reference. So the only thing verification can do is report, which is what it does.
    """
    handle, references = indexed
    reference = references[0]
    document = handle.objects.get(SourceDocument, reference.source_document_id)

    target = handle.artifacts.area("sources") / document.filename
    target.write_bytes(b"# Replaced\n\nThis document was edited after it was assessed.\n")

    result = EvidenceIndex(handle).verify(reference.id)
    assert result.outcome is VerificationOutcome.CONTENT_CHANGED
    assert result.checked_by is CheckedBy.LINE_RANGE


def test_removing_the_artifact_reports_missing_not_changed(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """The distinction a boolean would lose.

    A missing artifact means the assessment's own storage is damaged; changed content means the
    material under review moved on. The responses are different, so the outcomes are too.
    """
    handle, references = indexed
    reference = references[0]
    document = handle.objects.get(SourceDocument, reference.source_document_id)
    (handle.artifacts.area("sources") / document.filename).unlink()

    result = EvidenceIndex(handle).verify(reference.id)
    assert result.outcome is VerificationOutcome.ARTIFACT_MISSING
    # The two are distinct members rather than one truthiness. Asserted through the member set,
    # because mypy narrows `result.outcome` well enough to reject comparing it against the other
    # -- which is itself a small proof the two cannot be conflated.
    assert len({VerificationOutcome.ARTIFACT_MISSING, VerificationOutcome.CONTENT_CHANGED}) == 2


def test_verify_all_reports_only_the_mismatches(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    document = handle.objects.get(SourceDocument, references[0].source_document_id)
    (handle.artifacts.area("sources") / document.filename).write_bytes(b"# Replaced\n")

    failures = EvidenceIndex(handle).verify_all()
    affected = {r.id for r in references if r.source_document_id == document.id}

    assert failures
    assert {result.evidence_id for result in failures} <= affected
    assert all(not result.ok for result in failures)


def test_a_whitespace_only_edit_is_still_a_change(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """`quoted_text` is verbatim, so trailing whitespace is part of the quotation.

    This is what disabling whitespace stripping on that field buys: an edit that a normalizing
    comparison would forgive is still detected.
    """
    handle, references = indexed
    reference = next(r for r in references if r.start_line == 1)
    document = handle.objects.get(SourceDocument, reference.source_document_id)

    path = handle.artifacts.area("sources") / document.filename
    lines = path.read_bytes().split(b"\n")
    lines[0] = lines[0] + b"   "
    path.write_bytes(b"\n".join(lines))

    assert EvidenceIndex(handle).verify(reference.id).outcome is VerificationOutcome.CONTENT_CHANGED


def test_the_index_repairs_nothing(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """It reports; re-indexing is a decision someone makes."""
    handle, references = indexed
    document = handle.objects.get(SourceDocument, references[0].source_document_id)
    (handle.artifacts.area("sources") / document.filename).write_bytes(b"# Replaced\n")

    index = EvidenceIndex(handle)
    before = index.get(references[0].id)
    index.verify_all()

    assert index.get(references[0].id) == before, "verification mutated a reference"


# ------------------------------------------------------------------------------------------
# The prompt-facing shape
# ------------------------------------------------------------------------------------------


def test_rendered_evidence_carries_no_path(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """Asserted by searching the serialized output, not by inspecting keys.

    A model has no filesystem, and a path is the one field whose leakage would tell a document
    where it lives on the reviewer's machine.
    """
    handle, references = indexed
    rendered = EvidenceIndex(handle).render_for_prompt([r.id for r in references[:20]])
    serialized = json.dumps(rendered)

    assert "original_path" not in serialized
    assert "normalized_path" not in serialized
    assert str(handle.artifacts.assessment_root) not in serialized
    assert "/assessments/" not in serialized
    assert str(PROJECT_ROOT) not in serialized


def test_rendered_evidence_is_json_serializable_and_verbatim(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    rendered = EvidenceIndex(handle).render_for_prompt([references[0].id])
    restored = json.loads(json.dumps(rendered))

    assert restored[0]["quoted_text"] == references[0].quoted_text
    assert restored[0]["evidence_id"] == references[0].id
    assert restored[0]["source_filename"]


def test_the_injection_fixture_renders_unaltered(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """Passed through as data. Altering it here would hide it from the step meant to notice it."""
    handle, references = indexed
    carrying = [r for r in references if "AI ANALYSIS OVERRIDE" in r.quoted_text]
    assert carrying

    rendered = EvidenceIndex(handle).render_for_prompt([r.id for r in carrying])
    assert all("AI ANALYSIS OVERRIDE" in entry["quoted_text"] for entry in rendered)


def test_rendered_evidence_keeps_the_pointer_for_a_structured_source(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    structured = [r for r in references if r.json_pointer is not None]
    assert structured

    rendered = EvidenceIndex(handle).render_for_prompt([structured[0].id])
    assert rendered[0]["location"]["json_pointer"] == structured[0].json_pointer


def test_rendering_preserves_the_order_asked_for(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    handle, references = indexed
    wanted = [references[5].id, references[1].id, references[9].id]
    rendered = EvidenceIndex(handle).render_for_prompt(wanted)

    assert [entry["evidence_id"] for entry in rendered] == wanted


def test_rendering_an_unknown_identifier_raises(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]],
) -> None:
    """Silently omitting one would give a model a smaller evidence set than the caller asked for."""
    handle, references = indexed
    with pytest.raises(EvidenceNotFoundError):
        EvidenceIndex(handle).render_for_prompt([references[0].id, "evd-9999"])


# ------------------------------------------------------------------------------------------
# The module is the boundary, so it imports no provider
# ------------------------------------------------------------------------------------------

FORBIDDEN = frozenset({"anthropic", "openai", "langchain", "langgraph", "instructor", "langsmith"})


def test_the_index_imports_no_provider_sdk() -> None:
    """The module's purpose is to be the boundary later agent code sits behind.

    A provider import here would mean the boundary and the thing it bounds live in one file, and
    the next person would reasonably assemble a prompt in it.
    """
    source = Path(index_module.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert any(isinstance(node, ast.ClassDef) for node in ast.walk(tree)), (
        "the module did not parse"
    )
    assert not imported & FORBIDDEN, f"{imported & FORBIDDEN}"


def test_the_index_assembles_no_prompt() -> None:
    """`render_for_prompt` returns data. Delimiting is section 24's, and belongs with the agent."""
    rendered_type = EvidenceIndex.render_for_prompt.__annotations__["return"]
    assert "list" in str(rendered_type) and "dict" in str(rendered_type)


def test_verification_needs_no_api_key(
    indexed: tuple[AssessmentHandle, list[EvidenceReference]], monkeypatch: pytest.MonkeyPatch
) -> None:
    handle, _ = indexed
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert EvidenceIndex(handle).verify_all() == []
