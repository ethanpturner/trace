"""The assessment store: generated objects as JSON payloads in SQLite, per DEC-020.

One table holds every generated object type, keyed by `(assessment_id, id)`, with `object_type`,
`status`, and `created_at` lifted into columns and the validated object serialized into a payload.
**Pydantic is the only schema.** SQLite stores no field definitions, so adding, removing, or
retyping a field is a model change and not a migration -- which is the point, because the schema is
the least stable thing in the project and five decisions in two days changed it.

Three properties are structural rather than conventional.

**A repository is scoped to one assessment.** Every read is qualified by `assessment_id` and there
is no cross-assessment interface. `current-architecture.md` section 12's boundary is therefore a
property of the object you hold rather than a rule each query has to remember -- the same shape the
artifact store uses, for the same reason.

**Identifier allocation happens here, in the transaction that consumes the number.** DEC-018
assigns a generated identifier at insert from a monotonic counter per `(assessment_id, prefix)`,
which makes allocation a store concern and not a caller's. `InMemoryAllocator` restarts at 001 and
is for tests; this one survives the process, which is what DEC-017's pause-by-exiting requires.

**Schema versioning refuses rather than migrates.** A database written by an incompatible schema
version fails to open with a message naming both versions. DEC-020 makes that trade explicitly and
on evidence: regenerating an assessment costs a few dollars, and a migration written against a
model still under active decision costs hours and then needs maintaining.

What the database will not do is validate. With no column types and no constraints it accepts
whatever the application writes, so a bug that bypasses this module produces a row that fails on
read instead of on write. `save` validates on the way in and `_load` validates on the way out, and
a row that no longer parses raises `CorruptRecordError` rather than returning a partial object --
section 33 requires validation errors not be silently discarded, and a half-populated domain object
is exactly that.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Final, Self, TypeVar

from pydantic import ValidationError

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import PREFIXES, format_id, parse_id

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from types import TracebackType

__all__ = [
    "SCHEMA_VERSION",
    "AssessmentRepository",
    "AssessmentStore",
    "CorruptRecordError",
    "IncompatibleSchemaError",
    "StoreError",
    "WrongAssessmentError",
]

# Bumped when the *table layout* changes, not when a domain object changes. A model change is
# invisible here by design, which is the whole reason payloads are JSON.
SCHEMA_VERSION: Final = 1

DATABASE_FILENAME: Final = "trace.db"

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS store_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Every generated object, of every type. Identity and routing are columns; everything else is
-- inside `payload`. DEC-020: nothing in the MVP queries inside an object.
CREATE TABLE IF NOT EXISTS objects (
    assessment_id TEXT NOT NULL,
    id            TEXT NOT NULL,
    object_type   TEXT NOT NULL,
    status        TEXT,
    created_at    TEXT,
    payload       TEXT NOT NULL,
    PRIMARY KEY (assessment_id, id)
);

CREATE INDEX IF NOT EXISTS objects_by_type ON objects (assessment_id, object_type);
CREATE INDEX IF NOT EXISTS objects_by_status ON objects (assessment_id, object_type, status);

-- DEC-018's monotonic counters. `next_number` is the value the next allocation will use, so a
-- fresh row starts at 1 and a deleted object's number is never handed back.
CREATE TABLE IF NOT EXISTS identifier_counters (
    assessment_id TEXT NOT NULL,
    prefix        TEXT NOT NULL,
    next_number   INTEGER NOT NULL,
    PRIMARY KEY (assessment_id, prefix)
);
"""

ModelT = TypeVar("ModelT", bound=DomainModel)


class StoreError(RuntimeError):
    """Something the store must refuse."""


class IncompatibleSchemaError(StoreError):
    """The database was written by a schema version this build cannot read."""

    def __init__(self, found: int, expected: int) -> None:
        super().__init__(
            f"this database was written with store schema version {found}; this build reads "
            f"version {expected}. DEC-020 refuses rather than migrates: create a new database "
            f"and re-run the assessment."
        )
        self.found = found
        self.expected = expected


class WrongAssessmentError(StoreError):
    """An object belonging to a different assessment reached a scoped repository."""

    def __init__(self, object_id: str, belongs_to: str, scope: str) -> None:
        super().__init__(
            f"{object_id} belongs to {belongs_to}, and this repository is scoped to {scope}. "
            f"The assessment-data boundary is structural: use a repository for {belongs_to}."
        )


class CorruptRecordError(StoreError):
    """A stored row no longer parses into its model."""

    def __init__(self, assessment_id: str, object_id: str, model: str, cause: str) -> None:
        super().__init__(
            f"{object_id} in {assessment_id} does not parse as {model}. The row was written by "
            f"an incompatible model version, or by something that bypassed this store. "
            f"Underlying error: {cause}"
        )
        self.object_id = object_id


def _scope_of(obj: DomainModel) -> str:
    """Which assessment an object belongs to.

    An `Assessment` is its own scope: it carries no `assessment_id`, because it is the thing
    every other object's `assessment_id` points at. Decided by the identifier's prefix rather
    than by looking for the attribute, so an object that simply forgot the field is an error
    rather than a silent self-scoping.
    """
    identifier = getattr(obj, "id", None)
    if not isinstance(identifier, str):
        raise StoreError(f"{type(obj).__name__} has no string `id`; it cannot be persisted")

    if parse_id(identifier).prefix == "asm":
        return identifier

    scope = getattr(obj, "assessment_id", None)
    if not isinstance(scope, str):
        raise StoreError(
            f"{type(obj).__name__} {identifier} has no `assessment_id`. Every generated object "
            f"except the Assessment itself is scoped to one, per DEC-018."
        )
    return scope


class AssessmentStore:
    """The SQLite database holding every assessment's generated objects.

    One database rather than one per assessment, per DEC-020. The cost is recorded there: the
    boundary becomes a property of the repository, so a query written outside one can cross it.
    That is why there is no method here that reads objects -- only `repository`, which returns a
    scoped view.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        # Referential integrity lives in application code (DEC-020), so foreign keys are not
        # enabled; there are none to enforce. WAL and NORMAL are the ordinary local defaults.
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(_SCHEMA)
        # One connection means one transaction scope, so the depth lives here rather than on a
        # repository: two repositories for two assessments share this connection, and a commit
        # from either would otherwise land the other's pending work.
        self._transaction_depth = 0
        self._check_schema_version()

    @classmethod
    def at_root(cls, root: Path) -> Self:
        """The database beside the artifact store, under the same gitignored `data/` root."""
        return cls(root / DATABASE_FILENAME)

    def _check_schema_version(self) -> None:
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO store_metadata (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._connection.commit()
            return
        found = int(row["value"])
        if found != SCHEMA_VERSION:
            raise IncompatibleSchemaError(found, SCHEMA_VERSION)

    @property
    def schema_version(self) -> int:
        """Readable from a fresh database and from an existing one."""
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"])

    def repository(self, assessment_id: str) -> AssessmentRepository:
        """A view scoped to one assessment. The only way to reach objects."""
        parsed = parse_id(assessment_id)
        if parsed.prefix != "asm":
            raise StoreError(
                f"a repository is scoped to an Assessment; {assessment_id!r} names a "
                f"{parsed.object_type}"
            )
        return AssessmentRepository(self, assessment_id)

    def assessment_ids(self) -> list[str]:
        """Every assessment with at least one stored object.

        The one deliberately cross-assessment read. It returns identifiers and no content, which
        is what a `trace assessment list` needs and is not a way to read another assessment's
        objects.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT assessment_id FROM objects ORDER BY assessment_id"
        ).fetchall()
        return [row["assessment_id"] for row in rows]

    def _commit_unless_in_transaction(self) -> None:
        """Commit a single statement, or leave it to the transaction that encloses it.

        Without this, every write would be its own transaction and DEC-018's requirement that a
        counter increment and the insert consuming it commit together would be unimplementable.
        """
        if self._transaction_depth == 0:
            self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AssessmentRepository:
    """Reads and writes for one assessment. Every statement carries its `assessment_id`."""

    def __init__(self, store: AssessmentStore, assessment_id: str) -> None:
        self._store = store
        self._connection = store._connection
        self.assessment_id = assessment_id

    @contextmanager
    def transaction(self) -> Iterator[Self]:
        """Group allocations and inserts so a number cannot be consumed by a failed write.

        DEC-018 increments the counter in the same transaction as the insert. Without that, a
        crash between the two leaves a gap that reads as a deleted object.
        """
        self._store._transaction_depth += 1
        try:
            yield self
        except BaseException:
            self._store._transaction_depth -= 1
            self._connection.rollback()
            raise
        else:
            self._store._transaction_depth -= 1
            self._store._commit_unless_in_transaction()

    def allocate(self, prefix: str) -> str:
        """The next identifier for `prefix` in this assessment (DEC-018).

        Monotonic and per-assessment: `thr-007` here and `thr-007` in another assessment are
        different objects, and an identifier is fully qualified only by `(assessment_id, id)`.
        """
        if prefix not in PREFIXES:
            raise StoreError(
                f"'{prefix}' is not one of the {len(PREFIXES)} prefixes in data-model.md "
                f"section 2.1"
            )
        cursor = self._connection.execute(
            "SELECT next_number FROM identifier_counters WHERE assessment_id = ? AND prefix = ?",
            (self.assessment_id, prefix),
        )
        row = cursor.fetchone()
        number = 1 if row is None else int(row["next_number"])
        self._connection.execute(
            "INSERT INTO identifier_counters (assessment_id, prefix, next_number) VALUES (?, ?, ?) "
            "ON CONFLICT (assessment_id, prefix) DO UPDATE SET next_number = ?",
            (self.assessment_id, prefix, number + 1, number + 1),
        )
        self._store._commit_unless_in_transaction()
        return format_id(prefix, number)

    def save(self, obj: DomainModel) -> None:
        """Persist a validated object. Replaces the row with the same identifier.

        Replacement is what DEC-023's in-place mutation means at this layer: the object keeps its
        identifier, its fields change, and the delta is recorded on a `ReviewerDecision`. Nothing
        here writes that decision -- the caller does, in the same transaction.
        """
        scope = _scope_of(obj)
        if scope != self.assessment_id:
            raise WrongAssessmentError(str(obj.id), scope, self.assessment_id)  # type: ignore[attr-defined]

        payload = obj.model_dump_json()
        self._connection.execute(
            "INSERT INTO objects (assessment_id, id, object_type, status, created_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (assessment_id, id) DO UPDATE SET "
            "object_type = excluded.object_type, status = excluded.status, "
            "created_at = excluded.created_at, payload = excluded.payload",
            (
                self.assessment_id,
                obj.id,  # type: ignore[attr-defined]
                type(obj).__name__,
                _column(obj, "status"),
                _column(obj, "created_at"),
                payload,
            ),
        )
        self._store._commit_unless_in_transaction()

    def get(self, model: type[ModelT], object_id: str) -> ModelT:
        """Read one object, validated. Raises if it is absent or no longer parses."""
        row = self._connection.execute(
            "SELECT payload FROM objects WHERE assessment_id = ? AND id = ? AND object_type = ?",
            (self.assessment_id, object_id, model.__name__),
        ).fetchone()
        if row is None:
            raise StoreError(f"no {model.__name__} with id {object_id!r} in {self.assessment_id}")
        return self._load(model, object_id, row["payload"])

    def find(self, model: type[ModelT], object_id: str) -> ModelT | None:
        """`get`, returning `None` when absent. A corrupt row still raises."""
        try:
            return self.get(model, object_id)
        except StoreError as error:
            if isinstance(error, CorruptRecordError):
                raise
            return None

    def list(self, model: type[ModelT], *, status: str | None = None) -> list[ModelT]:
        """Every object of one type in this assessment, oldest first by identifier."""
        sql = "SELECT id, payload FROM objects WHERE assessment_id = ? AND object_type = ?"
        parameters: list[object] = [self.assessment_id, model.__name__]
        if status is not None:
            sql += " AND status = ?"
            parameters.append(status)
        rows = self._connection.execute(sql + " ORDER BY id", parameters).fetchall()
        return [self._load(model, row["id"], row["payload"]) for row in rows]

    def count(self, model: type[DomainModel]) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS total FROM objects WHERE assessment_id = ? AND object_type = ?",
            (self.assessment_id, model.__name__),
        ).fetchone()
        return int(row["total"])

    def _load(self, model: type[ModelT], object_id: str, payload: str) -> ModelT:
        """Validate on the way out. A row that no longer parses is an error, not a partial object.

        Section 33 requires validation errors not be silently discarded, and the database accepts
        anything the application writes -- DEC-020 records that as the cost of having no column
        types. This is where that cost is paid, loudly.
        """
        try:
            return model.model_validate_json(payload)
        except ValidationError as error:
            raise CorruptRecordError(
                self.assessment_id, object_id, model.__name__, str(error)
            ) from error


def _column(obj: DomainModel, field: str) -> str | None:
    """Lift a routing field out of the payload, as text, if the object has one.

    Optional because not every object carries both. `status` and `created_at` are columns so the
    queries the corpus actually asks for -- by assessment, by type, by status -- do not read
    inside a payload; anything else stays in the JSON.
    """
    value = getattr(obj, field, None)
    if value is None:
        return None
    return value if isinstance(value, str) else json.loads(json.dumps(value, default=str))
