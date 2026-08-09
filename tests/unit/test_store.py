"""Tests for the assessment store.

The objects this milestone persists -- `Assessment`, `SourceDocument`, `EvidenceReference` --
arrive with #49, #51, and #52. What exists now is the mechanism, so these tests use throwaway
models declared here. That is not a workaround: the store is generic over `DomainModel` by design,
because DEC-020 makes Pydantic the only schema and SQLite stores no field definitions. A test that
waited for the real models would be testing the same code paths with different field names.

The models below are shaped like the real ones in the ways the store depends on -- an `id`, an
`assessment_id` on everything except the assessment itself, a `status`, a `created_at` -- and
deliberately not in any other way.

Two properties get most of the attention. The assessment-data boundary is asserted directly rather
than inferred from the SQL, because `current-architecture.md` section 12 makes it a trust boundary
and DEC-020 records that one shared database puts it in the repository rather than in the storage.
And a row that no longer parses must raise, because the database validates nothing and section 33
requires validation errors not be silently discarded. Issue #47.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import Field

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import AssessmentId, EvidenceReferenceId, SourceDocumentId
from trace_ai.infrastructure.database.store import (
    SCHEMA_VERSION,
    AssessmentStore,
    CorruptRecordError,
    IncompatibleSchemaError,
    StoreError,
    WrongAssessmentError,
)


class FakeAssessment(DomainModel):
    """Shaped like section 5 where the store cares: an `asm-` id and no `assessment_id`."""

    id: AssessmentId
    name: str
    status: ObjectStatus = ObjectStatus.DRAFT
    created_at: datetime
    tags: list[str] = Field(default_factory=list)


class FakeDocument(DomainModel):
    id: SourceDocumentId
    assessment_id: AssessmentId
    filename: str
    content_hash: str
    status: ObjectStatus = ObjectStatus.DRAFT
    created_at: datetime


class FakeEvidence(DomainModel):
    id: EvidenceReferenceId
    assessment_id: AssessmentId
    source_document_id: SourceDocumentId
    quoted_text: str
    status: ObjectStatus = ObjectStatus.DRAFT
    created_at: datetime


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AssessmentStore]:
    with AssessmentStore.at_root(tmp_path) as opened:
        yield opened


def an_assessment(identifier: str = "asm-001", **overrides: object) -> FakeAssessment:
    fields: dict[str, object] = {
        "id": identifier,
        "name": "ForgeFlow Security Review",
        "created_at": now(),
        "tags": ["demo", "developer-platform"],
    }
    return FakeAssessment.model_validate(fields | overrides)


# ------------------------------------------------------------------------------------------
# The database file and its version
# ------------------------------------------------------------------------------------------


def test_the_database_lives_under_the_artifact_store_root(tmp_path: Path) -> None:
    """One gitignored `data/` root holds both halves of DEC-020's split."""
    with AssessmentStore.at_root(tmp_path) as store:
        assert store.path == tmp_path / "trace.db"
        assert store.path.is_file()


def test_the_schema_version_is_readable_from_a_fresh_database(store: AssessmentStore) -> None:
    assert store.schema_version == SCHEMA_VERSION


def test_the_schema_version_is_readable_from_an_existing_database(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as first:
        first.repository("asm-001").save(an_assessment())
    with AssessmentStore.at_root(tmp_path) as second:
        assert second.schema_version == SCHEMA_VERSION
        assert second.repository("asm-001").get(FakeAssessment, "asm-001").name


def test_an_incompatible_schema_version_refuses_to_open(tmp_path: Path) -> None:
    """DEC-020 refuses rather than migrates, and the message has to say so."""
    with AssessmentStore.at_root(tmp_path):
        pass
    connection = sqlite3.connect(tmp_path / "trace.db")
    connection.execute("UPDATE store_metadata SET value = '99' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()

    with pytest.raises(IncompatibleSchemaError) as caught:
        AssessmentStore.at_root(tmp_path)

    assert "99" in str(caught.value)
    assert str(SCHEMA_VERSION) in str(caught.value)


# ------------------------------------------------------------------------------------------
# Round trips
# ------------------------------------------------------------------------------------------


def test_an_assessment_round_trips(store: AssessmentStore) -> None:
    original = an_assessment()
    repository = store.repository("asm-001")
    repository.save(original)

    assert repository.get(FakeAssessment, "asm-001") == original


def test_a_timezone_aware_timestamp_survives(store: AssessmentStore) -> None:
    """Naive and aware datetimes compare differently; a round trip that drops the offset lies."""
    stamp = datetime(2026, 8, 9, 14, 0, tzinfo=UTC)
    store.repository("asm-001").save(an_assessment(created_at=stamp))

    restored = store.repository("asm-001").get(FakeAssessment, "asm-001")
    assert restored.created_at == stamp
    assert restored.created_at.tzinfo is not None


def test_a_list_field_survives(store: AssessmentStore) -> None:
    store.repository("asm-001").save(an_assessment(tags=["demo", "isc2"]))
    assert store.repository("asm-001").get(FakeAssessment, "asm-001").tags == ["demo", "isc2"]


def test_a_document_and_an_evidence_reference_round_trip(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    document = FakeDocument(
        id="src-001",
        assessment_id="asm-001",
        filename="architecture-overview.md",
        content_hash="sha256:" + "a" * 64,
        created_at=now(),
    )
    evidence = FakeEvidence(
        id="evd-001",
        assessment_id="asm-001",
        source_document_id="src-001",
        quoted_text="Webhook requests are validated.",
        created_at=now(),
    )
    repository.save(document)
    repository.save(evidence)

    assert repository.get(FakeDocument, "src-001") == document
    assert repository.get(FakeEvidence, "evd-001").assessment_id == "asm-001"


def test_saving_the_same_identifier_replaces_the_row(store: AssessmentStore) -> None:
    """DEC-023 mutates in place: the object keeps its identifier and its fields change."""
    repository = store.repository("asm-001")
    repository.save(an_assessment(name="Draft name"))
    repository.save(an_assessment(name="Approved name", status=ObjectStatus.APPROVED))

    assert repository.count(FakeAssessment) == 1
    assert repository.get(FakeAssessment, "asm-001").name == "Approved name"


def test_listing_returns_only_the_requested_type(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    repository.save(an_assessment())
    repository.save(
        FakeDocument(
            id="src-001",
            assessment_id="asm-001",
            filename="a.md",
            content_hash="sha256:" + "b" * 64,
            created_at=now(),
        )
    )

    assert [o.id for o in repository.list(FakeAssessment)] == ["asm-001"]
    assert [o.id for o in repository.list(FakeDocument)] == ["src-001"]


def test_listing_can_filter_by_status(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    for index, status in enumerate((ObjectStatus.DRAFT, ObjectStatus.APPROVED), start=1):
        repository.save(
            FakeDocument(
                id=f"src-{index:03d}",
                assessment_id="asm-001",
                filename=f"{index}.md",
                content_hash="sha256:" + "c" * 64,
                status=status,
                created_at=now(),
            )
        )

    approved = repository.list(FakeDocument, status=ObjectStatus.APPROVED)
    assert [document.id for document in approved] == ["src-002"]


def test_find_returns_none_when_absent_and_get_raises(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    assert repository.find(FakeAssessment, "asm-404") is None
    with pytest.raises(StoreError, match="no FakeAssessment"):
        repository.get(FakeAssessment, "asm-404")


# ------------------------------------------------------------------------------------------
# The assessment-data boundary
# ------------------------------------------------------------------------------------------


def test_a_read_never_returns_another_assessments_object(store: AssessmentStore) -> None:
    """Section 12's boundary, asserted rather than inferred from the SQL."""
    store.repository("asm-001").save(an_assessment("asm-001", name="First"))
    store.repository("asm-002").save(an_assessment("asm-002", name="Second"))

    first = store.repository("asm-001")
    assert first.find(FakeAssessment, "asm-002") is None
    assert [a.id for a in first.list(FakeAssessment)] == ["asm-001"]


def test_the_same_identifier_in_two_assessments_is_two_objects(store: AssessmentStore) -> None:
    """DEC-018: an identifier is fully qualified only by `(assessment_id, id)`."""
    for assessment in ("asm-001", "asm-002"):
        store.repository(assessment).save(
            FakeDocument(
                id="src-001",
                assessment_id=assessment,
                filename=f"{assessment}.md",
                content_hash="sha256:" + "d" * 64,
                created_at=now(),
            )
        )

    assert store.repository("asm-001").get(FakeDocument, "src-001").filename == "asm-001.md"
    assert store.repository("asm-002").get(FakeDocument, "src-001").filename == "asm-002.md"


def test_writing_another_assessments_object_raises(store: AssessmentStore) -> None:
    foreign = FakeDocument(
        id="src-001",
        assessment_id="asm-002",
        filename="a.md",
        content_hash="sha256:" + "e" * 64,
        created_at=now(),
    )
    with pytest.raises(WrongAssessmentError, match="asm-002"):
        store.repository("asm-001").save(foreign)


def test_writing_another_assessment_object_raises(store: AssessmentStore) -> None:
    """An `Assessment` is its own scope, so the mismatch is between its id and the repository."""
    with pytest.raises(WrongAssessmentError):
        store.repository("asm-001").save(an_assessment("asm-002"))


def test_a_repository_must_be_scoped_to_an_assessment(store: AssessmentStore) -> None:
    with pytest.raises(StoreError, match="names a Threat"):
        store.repository("thr-007")


def test_listing_assessment_ids_returns_identifiers_and_nothing_else(
    store: AssessmentStore,
) -> None:
    """The one cross-assessment read, deliberately content-free."""
    store.repository("asm-001").save(an_assessment("asm-001"))
    store.repository("asm-002").save(an_assessment("asm-002"))

    assert store.assessment_ids() == ["asm-001", "asm-002"]


def test_an_object_without_an_assessment_id_is_refused(store: AssessmentStore) -> None:
    """A model that forgot the field must fail, not silently scope itself."""

    class Unscoped(DomainModel):
        id: SourceDocumentId

    with pytest.raises(StoreError, match="has no `assessment_id`"):
        store.repository("asm-001").save(Unscoped(id="src-001"))


# ------------------------------------------------------------------------------------------
# Identifier allocation
# ------------------------------------------------------------------------------------------


def test_allocation_numbers_from_one(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    assert [repository.allocate("thr") for _ in range(3)] == ["thr-001", "thr-002", "thr-003"]


def test_counters_are_per_assessment(store: AssessmentStore) -> None:
    """`thr-001` in two assessments is two objects, so both start at one."""
    assert store.repository("asm-001").allocate("thr") == "thr-001"
    assert store.repository("asm-002").allocate("thr") == "thr-001"
    assert store.repository("asm-001").allocate("thr") == "thr-002"


def test_counters_are_per_prefix(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    assert repository.allocate("thr") == "thr-001"
    assert repository.allocate("fnd") == "fnd-001"


def test_allocation_survives_the_process(tmp_path: Path) -> None:
    """The reason allocation is a store concern and `InMemoryAllocator` is not enough.

    DEC-017 pauses a run by persisting it and exiting. An allocator that restarted would re-mint
    identifiers the resumed run then collides with.
    """
    with AssessmentStore.at_root(tmp_path) as first:
        assert first.repository("asm-001").allocate("thr") == "thr-001"
        assert first.repository("asm-001").allocate("thr") == "thr-002"

    with AssessmentStore.at_root(tmp_path) as second:
        assert second.repository("asm-001").allocate("thr") == "thr-003"


def test_a_number_is_never_reused(store: AssessmentStore) -> None:
    """Monotonic per DEC-018: the numbering has gaps where objects were discarded."""
    repository = store.repository("asm-001")
    issued = [repository.allocate("evd") for _ in range(200)]
    assert len(set(issued)) == 200


def test_an_unregistered_prefix_is_refused(store: AssessmentStore) -> None:
    with pytest.raises(StoreError, match=re.escape("section 2.1")):
        store.repository("asm-001").allocate("xyz")


def test_a_failed_transaction_returns_the_number(tmp_path: Path) -> None:
    """The counter increments in the transaction that consumes it, so a rollback takes it back."""
    with AssessmentStore.at_root(tmp_path) as store:
        repository = store.repository("asm-001")

        with pytest.raises(RuntimeError, match="node failed"), repository.transaction() as scoped:
            assert scoped.allocate("thr") == "thr-001"
            raise RuntimeError("node failed")

        assert repository.allocate("thr") == "thr-001", "a rolled-back number was consumed anyway"


def test_a_committed_transaction_keeps_the_number(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    with repository.transaction() as scoped:
        allocated = scoped.allocate("thr")
    assert allocated == "thr-001"
    assert repository.allocate("thr") == "thr-002"


# ------------------------------------------------------------------------------------------
# Validation on the way out
# ------------------------------------------------------------------------------------------


def test_a_row_that_no_longer_parses_raises(store: AssessmentStore, tmp_path: Path) -> None:
    """The cost DEC-020 records: the database accepts anything, so reads have to check.

    Section 33 requires validation errors not be silently discarded, and a partially populated
    domain object flowing into the pipeline is exactly that -- worse than an exception, because
    the missing field surfaces somewhere else entirely.
    """
    store.repository("asm-001").save(an_assessment())

    connection = sqlite3.connect(store.path)
    connection.execute(
        "UPDATE objects SET payload = ? WHERE id = 'asm-001'",
        ('{"id": "asm-001", "created_at": "2026-08-09T14:00:00+00:00"}',),
    )
    connection.commit()
    connection.close()

    with pytest.raises(CorruptRecordError) as caught:
        store.repository("asm-001").get(FakeAssessment, "asm-001")

    assert "asm-001" in str(caught.value)
    assert "FakeAssessment" in str(caught.value)


def test_a_corrupt_row_raises_through_find_rather_than_returning_none(
    store: AssessmentStore,
) -> None:
    """`find` means "absent"; it must not also mean "unreadable"."""
    store.repository("asm-001").save(an_assessment())

    connection = sqlite3.connect(store.path)
    connection.execute("UPDATE objects SET payload = '{}' WHERE id = 'asm-001'")
    connection.commit()
    connection.close()

    with pytest.raises(CorruptRecordError):
        store.repository("asm-001").find(FakeAssessment, "asm-001")


def test_an_unparseable_payload_raises(store: AssessmentStore) -> None:
    store.repository("asm-001").save(an_assessment())

    connection = sqlite3.connect(store.path)
    connection.execute("UPDATE objects SET payload = 'not json' WHERE id = 'asm-001'")
    connection.commit()
    connection.close()

    with pytest.raises(CorruptRecordError):
        store.repository("asm-001").get(FakeAssessment, "asm-001")


def test_an_invalid_object_cannot_be_saved(store: AssessmentStore) -> None:
    """Validation on the way in: the model refuses before the store is reached."""
    with pytest.raises(ValueError, match="not a valid identifier"):
        an_assessment("assessment-001")


# ------------------------------------------------------------------------------------------
# Routing columns
# ------------------------------------------------------------------------------------------


def test_status_and_created_at_are_columns_not_payload_reads(store: AssessmentStore) -> None:
    """DEC-020 lifts identity and routing into columns so no query reads inside a payload."""
    store.repository("asm-001").save(an_assessment(status=ObjectStatus.APPROVED))

    connection = sqlite3.connect(store.path)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT object_type, status, created_at FROM objects").fetchone()
    connection.close()

    assert row["object_type"] == "FakeAssessment"
    assert row["status"] == "approved"
    assert row["created_at"]


def test_the_payload_holds_the_whole_object(store: AssessmentStore) -> None:
    original = an_assessment()
    store.repository("asm-001").save(original)

    connection = sqlite3.connect(store.path)
    payload = connection.execute("SELECT payload FROM objects").fetchone()[0]
    connection.close()

    assert FakeAssessment.model_validate_json(payload) == original
