"""Tests for `SourceDocument`.

Field names and required-ness are checked by `test_data_model_conformance.py` against
`data-model.md` section 7. This file covers the two vocabularies section 7 leaves to the object and
the consistency rule that makes `ingested_at`'s optionality safe.

The `trust_level` tests assert something the issue asked for the opposite of, and the reasoning is
in the module docstring: section 7 marks the field required, so it carries no default, and omitting
it raises rather than silently producing `untrusted`. Both designs fail safe; only this one fails
loudly, which is what you want from a security-relevant field when someone adds a call site.
Issue #52.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import (
    DEFAULT_TRUST_LEVEL,
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)

CONTENT = b"# Architecture Overview\n\nWebhook requests are validated.\n"

# Fixed so `ingested_at` values in these tests are comparable against it. A helper stamping the
# real clock would make every ingested-document case depend on when the suite ran.
REGISTERED_AT = datetime(2026, 8, 5, 20, 0, tzinfo=UTC)


def a_document(**overrides: object) -> SourceDocument:
    fields: dict[str, object] = {
        "id": "src-002",
        "assessment_id": "asm-001",
        "filename": "architecture-overview.md",
        "media_type": MediaType.MARKDOWN,
        "origin": SourceOrigin.UPLOADED_DOCUMENT,
        "content_hash": content_hash(CONTENT),
        "created_at": REGISTERED_AT,
        "ingestion_status": IngestionStatus.REGISTERED,
        "trust_level": TrustLevel.UNTRUSTED,
    }
    return SourceDocument.model_validate(fields | overrides)


# ------------------------------------------------------------------------------------------
# Trust level
# ------------------------------------------------------------------------------------------


def test_trust_level_has_exactly_the_four_documented_values() -> None:
    assert {member.value for member in TrustLevel} == {
        "untrusted",
        "reviewer_supplied",
        "system_fixture",
        "trusted_catalog",
    }


def test_omitting_trust_level_raises_rather_than_defaulting() -> None:
    """The control, stated the way section 7 types it.

    A required field cannot be left unchosen, so a call site added later fails at construction
    instead of inheriting `untrusted` quietly. That is the property worth having: being told about
    the new call site beats being protected from it without knowing.
    """
    fields = {
        "id": "src-002",
        "assessment_id": "asm-001",
        "filename": "a.md",
        "media_type": MediaType.MARKDOWN,
        "origin": SourceOrigin.UPLOADED_DOCUMENT,
        "content_hash": content_hash(CONTENT),
        "created_at": now(),
        "ingestion_status": IngestionStatus.REGISTERED,
    }
    with pytest.raises(ValidationError, match="trust_level"):
        SourceDocument.model_validate(fields)


def test_the_stated_value_for_material_under_review_is_untrusted() -> None:
    """What a caller passes for a document supplied for review, named rather than implied."""
    assert DEFAULT_TRUST_LEVEL is TrustLevel.UNTRUSTED
    assert a_document(trust_level=DEFAULT_TRUST_LEVEL).trust_level is TrustLevel.UNTRUSTED


def test_an_unknown_trust_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        a_document(trust_level="trusted")


def test_no_trust_level_grants_a_capability() -> None:
    """Section 7: even reviewer-supplied documents are generally data, not instructions.

    `trust_level` records a provenance claim. Nothing on this object turns any value of it into
    permission, and `agent-design.md` section 25 gives agents no way to act on document content
    regardless.
    """
    for level in TrustLevel:
        document = a_document(trust_level=level)
        assert document.trust_level is level
        assert not [name for name in SourceDocument.model_fields if "permission" in name]
        assert not [name for name in SourceDocument.model_fields if "execute" in name]


# ------------------------------------------------------------------------------------------
# Media type
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "media_type", ["text/markdown", "text/plain", "application/json", "application/yaml"]
)
def test_the_four_mvp_formats_are_accepted(media_type: str) -> None:
    assert a_document(media_type=media_type).media_type == media_type


def test_a_deferred_format_is_rejected_by_name() -> None:
    """PDF and Office ingestion are deferred, so a document in one has no loader branch.

    The message names the supported set, because the caller's next question is what to use.
    """
    with pytest.raises(ValidationError) as caught:
        a_document(media_type="application/pdf")

    message = str(caught.value)
    assert "application/pdf" in message
    for supported in ("text/markdown", "text/plain", "application/json", "application/yaml"):
        assert supported in message
    assert "section 5.4" in message


def test_an_arbitrary_string_is_not_a_media_type() -> None:
    with pytest.raises(ValidationError):
        a_document(media_type="markdown")


# ------------------------------------------------------------------------------------------
# Ingestion state (DEC-033)
# ------------------------------------------------------------------------------------------


def test_ingestion_status_has_exactly_three_values() -> None:
    """DEC-033. A status the code never writes is worse than absent: someone will branch on it."""
    assert {member.value for member in IngestionStatus} == {"registered", "ingested", "failed"}


def test_a_registered_document_has_neither_ingestion_output() -> None:
    """The state between `trace source add` and the ingestion node running."""
    document = a_document()
    assert document.ingestion_status is IngestionStatus.REGISTERED
    assert document.ingested_at is None
    assert document.normalized_path is None


def test_an_ingested_document_requires_both_outputs() -> None:
    """Section 7 makes both optional, which is what would let a document claim what it lacks."""
    stamp = now()
    ingested = a_document(
        ingestion_status=IngestionStatus.INGESTED,
        ingested_at=stamp,
        normalized_path="data/assessments/asm-001/normalized/architecture-overview.md",
    )
    assert ingested.ingested_at == stamp


@pytest.mark.parametrize(
    "missing",
    [
        {"ingested_at": None},
        {"normalized_path": None},
        {"ingested_at": None, "normalized_path": None},
    ],
)
def test_an_ingested_document_missing_an_output_is_rejected(missing: dict[str, object]) -> None:
    complete: dict[str, object] = {
        "ingestion_status": IngestionStatus.INGESTED,
        "ingested_at": now(),
        "normalized_path": "normalized/a.md",
    }
    with pytest.raises(ValidationError, match="unset"):
        a_document(**(complete | missing))


def test_a_failed_ingestion_is_representable() -> None:
    """The status carries the failure; `normalized_path` stays unset."""
    failed = a_document(ingestion_status=IngestionStatus.FAILED)
    assert failed.ingestion_status is IngestionStatus.FAILED
    assert failed.normalized_path is None


def test_a_failed_document_may_not_carry_a_normalized_artifact() -> None:
    with pytest.raises(ValidationError, match="has no normalized artifact"):
        a_document(ingestion_status=IngestionStatus.FAILED, normalized_path="normalized/a.md")


def test_a_registered_document_may_not_carry_a_normalized_artifact() -> None:
    with pytest.raises(ValidationError, match="has no normalized artifact"):
        a_document(normalized_path="normalized/a.md")


def test_the_failure_reason_is_not_a_field_here() -> None:
    """DEC-033: it lives on the `ExecutionRecord`, which section 27 already gives error fields.

    Two records of one event disagree the first time one is written and the other is not.
    """
    suspicious = [
        name
        for name in SourceDocument.model_fields
        if any(word in name for word in ("error", "failure", "reason", "message"))
    ]
    assert not suspicious, f"{suspicious} duplicates what the ExecutionRecord records"


def test_ingested_at_may_not_precede_created_at() -> None:
    stamp = now()
    with pytest.raises(ValidationError, match="cannot be ingested before it exists"):
        a_document(
            created_at=stamp,
            ingestion_status=IngestionStatus.INGESTED,
            ingested_at=stamp - timedelta(seconds=1),
            normalized_path="normalized/a.md",
        )


# ------------------------------------------------------------------------------------------
# Integrity and identity
# ------------------------------------------------------------------------------------------


def test_the_content_hash_covers_the_original_bytes() -> None:
    """DEC-019 hashes raw bytes, not normalized text.

    Normalizing first would mask exactly the changes the hash exists to detect -- a re-encoded or
    re-line-ended file is a changed file.
    """
    assert a_document().content_hash == content_hash(CONTENT)


def test_a_malformed_content_hash_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not a content hash"):
        a_document(content_hash="sha256:example")


def test_an_empty_filename_is_rejected() -> None:
    with pytest.raises(ValidationError):
        a_document(filename="   ")


def test_the_identifiers_must_name_the_right_objects() -> None:
    with pytest.raises(ValidationError, match="names an Assessment"):
        a_document(id="asm-001")
    with pytest.raises(ValidationError, match="names a Threat"):
        a_document(assessment_id="thr-007")


def test_an_undocumented_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        a_document(sanitized=True)


def test_a_document_round_trips_through_json() -> None:
    original = a_document(
        title="Architecture Overview",
        ingestion_status=IngestionStatus.INGESTED,
        ingested_at=datetime(2026, 8, 5, 20, 10, tzinfo=UTC),
        normalized_path="normalized/architecture-overview.md",
        metadata={"heading_level": 2},
    )
    restored = SourceDocument.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.trust_level is TrustLevel.UNTRUSTED
    assert restored.ingested_at is not None
    assert restored.ingested_at.tzinfo is not None


def test_the_document_is_immutable() -> None:
    with pytest.raises(ValidationError, match="frozen"):
        a_document().trust_level = TrustLevel.TRUSTED_CATALOG  # type: ignore[misc]
