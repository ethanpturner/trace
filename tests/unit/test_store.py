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


def test_the_database_file_and_its_root_are_owner_only(tmp_path: Path) -> None:
    """The database holds every payload, including verbatim confidential excerpts; sqlite creates
    it at 0o644 and mkdir leaves the root at the umask default unless each is tightened."""
    import sys

    if sys.platform == "win32":  # pragma: no cover -- POSIX mode bits do not apply
        pytest.skip("POSIX permissions")
    root = tmp_path / "data"
    with AssessmentStore.at_root(root) as store:
        store.repository("asm-001").save(an_assessment())
        assert store.path.stat().st_mode & 0o777 == 0o600
        assert root.stat().st_mode & 0o777 == 0o700
        for companion in ("trace.db-wal", "trace.db-shm"):
            path = root / companion
            if path.exists():
                assert path.stat().st_mode & 0o777 == 0o600


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


def test_a_malformed_schema_version_refuses_to_open(tmp_path: Path) -> None:
    """A hand-edited or corrupted version that is not an integer is refused, not a bare ValueError."""
    with AssessmentStore.at_root(tmp_path):
        pass
    connection = sqlite3.connect(tmp_path / "trace.db")
    connection.execute(
        "UPDATE store_metadata SET value = 'not-a-number' WHERE key = 'schema_version'"
    )
    connection.commit()
    connection.close()

    with pytest.raises(IncompatibleSchemaError) as caught:
        AssessmentStore.at_root(tmp_path)

    assert "not-a-number" in str(caught.value)


def test_an_incompatible_database_is_not_written_to_and_its_connection_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-020 refuses rather than migrates, so the refusal must precede any write, and the raise
    happens in __init__ where __exit__ never runs -- the connection must be closed explicitly."""
    with AssessmentStore.at_root(tmp_path):
        pass
    connection = sqlite3.connect(tmp_path / "trace.db")
    connection.execute("UPDATE store_metadata SET value = '99' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()

    class _TrackingConnection:
        """The minimal surface `AssessmentStore.__init__` touches, recording the two facts under
        test: whether the schema was created, and whether the connection was closed."""

        def __init__(self, real: sqlite3.Connection) -> None:
            self._real = real
            self.close_calls = 0
            self.executed_script = False

        @property
        def row_factory(self) -> object:
            return self._real.row_factory

        @row_factory.setter
        def row_factory(self, value: object) -> None:
            self._real.row_factory = value  # type: ignore[assignment]

        def execute(self, sql: str, *parameters: object) -> sqlite3.Cursor:
            return self._real.execute(sql, *parameters)  # type: ignore[arg-type]

        def executescript(self, script: str) -> sqlite3.Cursor:
            self.executed_script = True
            return self._real.executescript(script)

        def close(self) -> None:
            self.close_calls += 1
            self._real.close()

    tracked: dict[str, _TrackingConnection] = {}
    real_connect = sqlite3.connect

    def tracking_connect(*args: object, **kwargs: object) -> _TrackingConnection:
        wrapper = _TrackingConnection(real_connect(*args, **kwargs))  # type: ignore[call-overload]
        tracked["connection"] = wrapper
        return wrapper

    # store.py does `import sqlite3` and calls `sqlite3.connect`; the module object is shared, so
    # patching connect here patches the store's call too.
    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    with pytest.raises(IncompatibleSchemaError):
        AssessmentStore.at_root(tmp_path)

    wrapper = tracked["connection"]
    assert wrapper.executed_script is False, "the schema was created before the version was checked"
    assert wrapper.close_calls == 1, "the connection leaked when the schema was refused"


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
# Ordering, id-only reads, and deletion (#449)
# ------------------------------------------------------------------------------------------


def _document(identifier: str) -> FakeDocument:
    return FakeDocument(
        id=identifier,
        assessment_id="asm-001",
        filename=f"{identifier}.md",
        content_hash="sha256:" + "d" * 64,
        created_at=now(),
    )


def test_list_orders_by_insert_order_not_lexical_id(store: AssessmentStore) -> None:
    """DEC-018 widens past 999 rather than wrapping, so `src-1000` sorts lexically before `src-999`.
    `list` orders by the monotonic `seq` (insert order), so a moderate corpus is not reordered."""
    repository = store.repository("asm-001")
    repository.save(_document("src-999"))
    repository.save(_document("src-1000"))
    assert [doc.id for doc in repository.list(FakeDocument)] == ["src-999", "src-1000"]


def test_a_replacement_keeps_its_insert_position(store: AssessmentStore) -> None:
    """A DEC-023 edit re-saves under the same identifier; `seq` is not moved, so the object keeps
    its place in the oldest-first order."""
    repository = store.repository("asm-001")
    repository.save(_document("src-001"))
    repository.save(_document("src-002"))
    repository.save(_document("src-001"))  # a re-save of the first
    assert [doc.id for doc in repository.list(FakeDocument)] == ["src-001", "src-002"]


def test_ids_returns_identifiers_without_parsing_the_payload(store: AssessmentStore) -> None:
    """`ids` reads the id column only, so it returns even for a row whose payload no longer parses --
    which `list` would raise on. That is the property that makes it cheap: no JSON, no validation."""
    repository = store.repository("asm-001")
    repository.save(_document("src-001"))

    connection = sqlite3.connect(store.path)
    connection.execute("UPDATE objects SET payload = '{}' WHERE id = 'src-001'")
    connection.commit()
    connection.close()

    assert repository.ids(FakeDocument) == ["src-001"], "ids must not parse the payload"
    with pytest.raises(CorruptRecordError):
        repository.list(FakeDocument)


def test_ids_are_in_insert_order(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    repository.save(_document("src-999"))
    repository.save(_document("src-1000"))
    assert repository.ids(FakeDocument) == ["src-999", "src-1000"]


def test_delete_all_removes_one_assessment_and_leaves_the_others(store: AssessmentStore) -> None:
    store.repository("asm-001").save(an_assessment("asm-001"))
    store.repository("asm-001").save(_document("src-001"))
    store.repository("asm-002").save(an_assessment("asm-002"))

    removed = store.repository("asm-001").delete_all()

    assert removed == 2
    assert store.repository("asm-001").count(FakeAssessment) == 0
    assert store.repository("asm-001").count(FakeDocument) == 0
    assert store.repository("asm-002").get(FakeAssessment, "asm-002").name
    # The counter went too, so a re-created object numbers from one again.
    assert store.repository("asm-001").allocate("thr") == "thr-001"


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
# Nested transactions and concurrency
# ------------------------------------------------------------------------------------------


def test_a_nested_transaction_that_succeeds_commits_with_the_outer(store: AssessmentStore) -> None:
    """Real nesting via savepoints: the inner allocation persists when both complete."""
    repository = store.repository("asm-001")
    with repository.transaction() as outer:
        first = outer.allocate("thr")
        with repository.transaction() as inner:
            second = inner.allocate("thr")
    assert (first, second) == ("thr-001", "thr-002")
    assert repository.allocate("thr") == "thr-003"


def test_a_swallowed_nested_rollback_dooms_the_outer_transaction(store: AssessmentStore) -> None:
    """The reproduction from #443: a swallowed inner failure must not commit a partial result.

    Before the fix, the inner rollback rolled back the whole connection, the counter was restored,
    and `c` was re-issued `thr-001` -- two live objects with one identifier. Now the inner failure
    dooms the outer: nothing commits, and the outer `with` raises rather than persisting half.
    """
    repository = store.repository("asm-001")
    with (
        pytest.raises(StoreError, match="nested transaction rolled back"),
        repository.transaction(),
    ):
        repository.allocate("thr")  # thr-001
        try:
            with repository.transaction():
                repository.allocate("thr")  # thr-002
                raise RuntimeError("inner node failed")
        except RuntimeError:
            pass  # the swallow that used to corrupt the counter
        repository.allocate("thr")

    # The whole unit rolled back, so the next allocation starts from one again -- no partial commit,
    # and no identifier handed out twice.
    assert repository.allocate("thr") == "thr-001"


def test_a_propagated_nested_failure_rolls_the_whole_unit_back(store: AssessmentStore) -> None:
    repository = store.repository("asm-001")
    with pytest.raises(RuntimeError, match="inner node failed"), repository.transaction():
        repository.allocate("thr")
        with repository.transaction():
            repository.allocate("thr")
            raise RuntimeError("inner node failed")

    assert repository.allocate("thr") == "thr-001"


def test_a_transaction_refuses_a_write_from_another_assessment(store: AssessmentStore) -> None:
    """The connection is shared, so an open transaction on one assessment cannot absorb another's
    write -- doing so would discard or early-commit an unrelated assessment's work."""
    first = store.repository("asm-001")
    second = store.repository("asm-002")
    with first.transaction():
        first.allocate("thr")
        with pytest.raises(StoreError, match="scoped to asm-001"):
            second.allocate("thr")
        with pytest.raises(StoreError, match="scoped to asm-001"):
            second.save(an_assessment("asm-002"))


def test_two_connections_allocate_distinct_identifiers(tmp_path: Path) -> None:
    """Two processes -- a run and the view server -- share the database file, not a connection.

    The read-modify-write allocate used to let both read the same `next_number`; the single
    `INSERT ... RETURNING` statement plus `BEGIN IMMEDIATE`/`busy_timeout` serializes them so the
    same identifier is never minted twice.
    """
    with AssessmentStore.at_root(tmp_path) as one, AssessmentStore.at_root(tmp_path) as two:
        issued = [
            one.repository("asm-001").allocate("thr"),
            two.repository("asm-001").allocate("thr"),
            one.repository("asm-001").allocate("thr"),
            two.repository("asm-001").allocate("thr"),
        ]
    assert sorted(issued) == ["thr-001", "thr-002", "thr-003", "thr-004"]


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
