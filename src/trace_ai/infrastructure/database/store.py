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
from trace_ai.infrastructure.filesystem.permissions import mkdir_owner_only, restrict_to_owner

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
# invisible here by design, which is the whole reason payloads are JSON. v2 added `objects.seq`
# (DEC-089), so a v1 database is refused rather than migrated (DEC-020) -- the local data root is
# gitignored and regenerable.
SCHEMA_VERSION: Final = 2


def _trace_version() -> str:
    """The installed distribution version, or `unknown` from a tree with no metadata.

    Recorded once at store creation (DEC-090) so a `CorruptRecordError` can name the build that
    wrote a row rather than only the pydantic error, which stays within DEC-020's refuse-don't-
    migrate stance -- it makes the refusal actionable, not a migration."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("trace")
    except PackageNotFoundError:  # pragma: no cover - only from a tree without installed metadata
        return "unknown"


TRACE_VERSION: Final = _trace_version()

DATABASE_FILENAME: Final = "trace.db"

# The counter scope for identifiers that cannot belong to an assessment. DEC-018 scopes generated
# identifiers to their assessment, which works for all nineteen prefixes except `asm` itself: an
# assessment identifier has to be unique across the database, because it is what every other
# identifier is qualified by. `*` is not a valid identifier, so no assessment can collide with it.
GLOBAL_SCOPE: Final = "*"

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS store_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Every generated object, of every type. Identity and routing are columns; everything else is
-- inside `payload`. DEC-020: nothing in the MVP queries inside an object.
--
-- `seq` is a monotonic insert order, assigned once when a row is first written and never moved by a
-- later replacement (DEC-023 edits keep it). It is what `oldest first` orders by: sorting on `id`
-- text sorts `evd-1000` before `evd-999` (DEC-018 widens past 999 rather than wrapping), which
-- silently reorders a moderate corpus and, because DEC-018 assigns identifiers in that order on a
-- rerun, changes which identifier attaches to which object.
CREATE TABLE IF NOT EXISTS objects (
    assessment_id TEXT NOT NULL,
    id            TEXT NOT NULL,
    object_type   TEXT NOT NULL,
    status        TEXT,
    created_at    TEXT,
    seq           INTEGER NOT NULL,
    payload       TEXT NOT NULL,
    PRIMARY KEY (assessment_id, id)
);

CREATE INDEX IF NOT EXISTS objects_by_type ON objects (assessment_id, object_type);
CREATE INDEX IF NOT EXISTS objects_by_status ON objects (assessment_id, object_type, status);
CREATE INDEX IF NOT EXISTS objects_by_seq ON objects (seq);

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
    """The database was written by a schema version this build cannot read.

    `found` is the recorded value: an `int` for an ordinary version mismatch, or the raw string for
    a value that is not an integer at all (a corrupted or hand-edited metadata row). Both are the
    same refusal -- this build will not read the database -- so they share one error.
    """

    def __init__(self, found: int | str, expected: int) -> None:
        super().__init__(
            f"this database was written with store schema version {found!r}; this build reads "
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

    def __init__(
        self,
        assessment_id: str,
        object_id: str,
        model: str,
        cause: str,
        *,
        written_by: str = "unknown",
    ) -> None:
        super().__init__(
            f"{object_id} in {assessment_id} does not parse as {model}. The database was created by "
            f"trace {written_by}; the row was written by an incompatible model version, or by "
            f"something that bypassed this store. Underlying error: {cause}"
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
        # `SystemContext` is the one object with no identifier: DEC-034 keys it by
        # `(assessment_id, version)`, so its scope is read directly rather than from a prefix.
        scope = getattr(obj, "assessment_id", None)
        if isinstance(scope, str):
            return scope
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
        # Every ancestor owner-only, not just the leaf: `mkdir(parents=True, mode=...)` would leave
        # `data/` world-readable above an owner-only assessment directory.
        mkdir_owner_only(self.path.parent)
        # `isolation_level=None` puts the connection in autocommit mode, so this module owns
        # transaction control explicitly -- BEGIN IMMEDIATE, SAVEPOINT, COMMIT, ROLLBACK -- rather
        # than letting Python's sqlite3 issue an implicit BEGIN before each DML statement, which
        # cannot coexist with the savepoints `transaction()` needs for real nesting.
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            self._connection.row_factory = sqlite3.Row
            # Referential integrity lives in application code (DEC-020), so foreign keys are not
            # enabled; there are none to enforce. `busy_timeout` lets a second process (the view
            # server alongside a run) wait for a write lock rather than failing immediately.
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            # One connection means one transaction scope, so the depth and the owning assessment
            # live here rather than on a repository: two repositories for two assessments share
            # this connection, and a commit or rollback from either would otherwise land -- or
            # discard -- the other's pending work. `_doomed` records that a nested transaction
            # rolled back, so the outermost commit refuses rather than persisting a partial result.
            self._transaction_depth = 0
            self._transaction_owner: str | None = None
            self._transaction_doomed = False
            # Refuse an unreadable database *before* `executescript` writes into it. The old order
            # ran `CREATE TABLE IF NOT EXISTS` against a database it was about to declare
            # incompatible.
            self._refuse_incompatible_schema()
            self._connection.executescript(_SCHEMA)
            self._record_schema_version_if_absent()
            # SQLite creates the file and its WAL companions at 0o644; the payloads include verbatim
            # confidential excerpts, so tighten them once the tables (and thus the WAL) exist.
            restrict_to_owner(self.path)
        except BaseException:
            # A raise in __init__ means __enter__/__exit__ never run, so the connection would leak.
            self._connection.close()
            raise

    @classmethod
    def at_root(cls, root: Path) -> Self:
        """The database beside the artifact store, under the same gitignored `data/` root."""
        return cls(root / DATABASE_FILENAME)

    def _refuse_incompatible_schema(self) -> None:
        """Raise `IncompatibleSchemaError` if the database was written by another schema version.

        Runs before `executescript`, so it must not assume the metadata table exists. A fresh
        database (no `store_metadata` table, or the table without the row) is not incompatible; its
        version is recorded after the schema is created.
        """
        table = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'store_metadata'"
        ).fetchone()
        if table is None:
            return
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return
        try:
            found = int(row["value"])
        except TypeError, ValueError:
            raise IncompatibleSchemaError(str(row["value"]), SCHEMA_VERSION) from None
        if found != SCHEMA_VERSION:
            raise IncompatibleSchemaError(found, SCHEMA_VERSION)

    def _record_schema_version_if_absent(self) -> None:
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO store_metadata (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._connection.execute(
                "INSERT INTO store_metadata (key, value) VALUES ('trace_version', ?)",
                (TRACE_VERSION,),
            )

    @property
    def schema_version(self) -> int:
        """Readable from a fresh database and from an existing one."""
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            raise StoreError("store_metadata has no schema_version row; the database is malformed")
        return int(row["value"])

    @property
    def trace_version(self) -> str:
        """The build that created this database, or `unknown` for one made before it was recorded."""
        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'trace_version'"
        ).fetchone()
        return "unknown" if row is None else str(row["value"])

    def allocate_assessment_id(self) -> str:
        """The next `asm-NNN`, unique across this database.

        The one allocation that is not assessment-scoped, and the case DEC-018 does not name.
        Every other prefix counts within an assessment because `(assessment_id, id)` qualifies it;
        an assessment identifier has nothing above it to be qualified by, so its counter is held
        under `GLOBAL_SCOPE` and is unique database-wide.
        """
        return AssessmentRepository(self, GLOBAL_SCOPE).allocate("asm")

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

    def _guard_write_scope(self, assessment_id: str) -> None:
        """Refuse a write from an assessment other than the one whose transaction is open.

        The connection is shared, so a write from assessment B while assessment A holds an open
        transaction would be swept into A's unit of work -- and discarded if A rolls back, or
        committed early if B's write path committed. Both are silent corruption of an unrelated
        assessment. Refusing is the honest outcome: B waits until A's transaction closes. Writes
        outside any transaction (`_transaction_depth == 0`) are unaffected.
        """
        if self._transaction_depth > 0 and self._transaction_owner != assessment_id:
            raise StoreError(
                f"a transaction scoped to {self._transaction_owner} is open on this connection; "
                f"{assessment_id} cannot write until it closes. Two assessments share one "
                f"connection, so their writes cannot be interleaved within a transaction."
            )

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

        Nesting is real, not a shared counter. The outermost `transaction()` opens
        `BEGIN IMMEDIATE`; each nested one opens a `SAVEPOINT`, so an inner failure rolls back only
        the inner work. But a nested rollback *dooms* the whole unit: if an inner transaction rolls
        back and the caller swallows the exception, the outermost commit refuses and rolls the whole
        thing back instead. Committing the outer after an inner abort would persist a partial
        result and -- because DEC-018 allocates inside the transaction -- could hand the same
        identifier to two live objects (the exact failure this replaced). A cross-assessment
        `transaction()` while one is open is refused for the reason `_guard_write_scope` gives.
        """
        store = self._store
        depth = store._transaction_depth
        if depth > 0 and store._transaction_owner != self.assessment_id:
            self._store._guard_write_scope(self.assessment_id)
        savepoint = None if depth == 0 else f"sp_{depth}"
        if savepoint is None:
            store._transaction_owner = self.assessment_id
            store._transaction_doomed = False
            self._connection.execute("BEGIN IMMEDIATE")
        else:
            self._connection.execute(f"SAVEPOINT {savepoint}")
        store._transaction_depth = depth + 1
        try:
            yield self
        except BaseException:
            store._transaction_depth = depth
            if savepoint is None:
                self._connection.execute("ROLLBACK")
                store._transaction_owner = None
                store._transaction_doomed = False
            else:
                self._connection.execute(f"ROLLBACK TO {savepoint}")
                self._connection.execute(f"RELEASE {savepoint}")
                store._transaction_doomed = True
            raise
        else:
            store._transaction_depth = depth
            if savepoint is not None:
                self._connection.execute(f"RELEASE {savepoint}")
            elif store._transaction_doomed:
                self._connection.execute("ROLLBACK")
                store._transaction_owner = None
                store._transaction_doomed = False
                raise StoreError(
                    "a nested transaction rolled back and its error was swallowed; refusing to "
                    "commit a partial result. Let the inner failure propagate, or do not open a "
                    "nested transaction whose failure you intend to ignore."
                )
            else:
                self._connection.execute("COMMIT")
                store._transaction_owner = None

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
        self._store._guard_write_scope(self.assessment_id)
        # One statement, not a SELECT then an upsert: read-modify-write across two statements let
        # two callers read the same `next_number` and mint the same identifier. `next_number` is the
        # value the *next* allocation will use, so a fresh row inserts 2 and hands out 1, and a
        # conflict increments and hands out the pre-increment value. `RETURNING` reflects the row as
        # finally written, so `next_number - 1` is the number just allocated.
        row = self._connection.execute(
            "INSERT INTO identifier_counters (assessment_id, prefix, next_number) VALUES (?, ?, 2) "
            "ON CONFLICT (assessment_id, prefix) DO UPDATE SET next_number = next_number + 1 "
            "RETURNING next_number - 1 AS allocated",
            (self.assessment_id, prefix),
        ).fetchone()
        return format_id(prefix, int(row["allocated"]))

    def save(self, obj: DomainModel) -> None:
        """Persist a validated object. Replaces the row with the same identifier.

        Replacement is what DEC-023's in-place mutation means at this layer: the object keeps its
        identifier, its fields change, and the delta is recorded on a `ReviewerDecision`. Nothing
        here writes that decision -- the caller does, in the same transaction.

        `SystemContext` is stored under `<assessment_id>@v<version>`, because DEC-034 keys it by
        `(assessment_id, version)` and it carries no identifier of its own. The row key is that
        pair rendered rather than a new identifier: minting one would put a second name on an
        object the corpus deliberately leaves unnamed, and every revision would then have two.
        """
        scope = _scope_of(obj)
        row_key = obj.row_key()
        if scope != self.assessment_id:
            raise WrongAssessmentError(row_key, scope, self.assessment_id)
        self._store._guard_write_scope(self.assessment_id)

        payload = obj.model_dump_json()
        # `seq` is the next insert order, computed in the same statement as the insert -- a single
        # atomic statement, and writers are serialized (BEGIN IMMEDIATE / busy_timeout), so two
        # callers cannot read the same MAX. `ON CONFLICT DO UPDATE` deliberately omits `seq`, so a
        # replacement (a DEC-023 edit) keeps the row's original position.
        self._connection.execute(
            "INSERT INTO objects "
            "(assessment_id, id, object_type, status, created_at, seq, payload) "
            "VALUES (?, ?, ?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM objects), ?) "
            "ON CONFLICT (assessment_id, id) DO UPDATE SET "
            "object_type = excluded.object_type, status = excluded.status, "
            "created_at = excluded.created_at, payload = excluded.payload",
            (
                self.assessment_id,
                row_key,
                obj.stored_type,
                _column(obj, "status"),
                _column(obj, "created_at"),
                payload,
            ),
        )

    def get(self, model: type[ModelT], object_id: str) -> ModelT:
        """Read one object, validated. Raises if it is absent or no longer parses."""
        row = self._connection.execute(
            "SELECT payload FROM objects WHERE assessment_id = ? AND id = ? AND object_type = ?",
            (self.assessment_id, object_id, model.stored_type),
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

    # `iterate`, `ids`, and `list_where` are defined before `list` on purpose: within the class body
    # the name `list` binds to the method below, so a `-> list[...]` annotation in a method defined
    # *after* it resolves to the method rather than the builtin. Keeping the `list[...]` returns
    # ahead of that binding keeps them the builtin.
    def iterate(self, model: type[ModelT], *, status: str | None = None) -> Iterator[ModelT]:
        """Every object of one type, oldest first, yielded one at a time.

        The generator form of `list`: it validates and yields each row as the cursor produces it,
        so a caller that folds over a type without needing the whole set in memory does not
        materialize it. `list` is this collected.
        """
        sql = "SELECT id, payload FROM objects WHERE assessment_id = ? AND object_type = ?"
        parameters: list[object] = [self.assessment_id, model.stored_type]
        if status is not None:
            sql += " AND status = ?"
            parameters.append(status)
        cursor = self._connection.execute(sql + " ORDER BY seq", parameters)
        for row in cursor:
            yield self._load(model, row["id"], row["payload"])

    def ids(self, model: type[DomainModel], *, status: str | None = None) -> list[str]:
        """The identifiers of one type, oldest first, without reading or validating a payload.

        For the many call sites that need only "which ids exist" -- the driver reads the evidence
        identifiers six times a run to hand to an agent, and never the evidence text. Reading the
        `id` column over the existing index skips the JSON parse and the model validation a full
        `list` pays for every row.
        """
        sql = "SELECT id FROM objects WHERE assessment_id = ? AND object_type = ?"
        parameters: list[object] = [self.assessment_id, model.stored_type]
        if status is not None:
            sql += " AND status = ?"
            parameters.append(status)
        rows = self._connection.execute(sql + " ORDER BY seq", parameters).fetchall()
        return [row["id"] for row in rows]

    def list_where(self, model: type[ModelT], column: str, value: object) -> list[ModelT]:
        """Every object of one type whose `status` column equals `value`, oldest first.

        Only `status` is a queryable column (with `object_type` and `created_at`, the routing fields
        DEC-020 lifts out of the payload); a request for any other is refused rather than reaching
        inside the JSON, which DEC-020 says nothing in the MVP does.
        """
        if column != "status":
            raise StoreError(
                f"only the 'status' column is queryable; {column!r} lives inside the payload, which "
                f"DEC-020 keeps unqueried"
            )
        return self.list(model, status=None if value is None else str(value))

    def list(self, model: type[ModelT], *, status: str | None = None) -> list[ModelT]:
        """Every object of one type in this assessment, oldest first (insert order)."""
        return list(self.iterate(model, status=status))

    def counts_by_type(self) -> dict[str, int]:
        """How many objects of each type this assessment holds.

        Reported per type rather than for a named pair, so a type that does not exist yet is
        absent rather than silently zero.
        """
        rows = self._connection.execute(
            "SELECT object_type, COUNT(*) AS total FROM objects WHERE assessment_id = ? "
            "GROUP BY object_type ORDER BY object_type",
            (self.assessment_id,),
        ).fetchall()
        return {row["object_type"]: int(row["total"]) for row in rows}

    def count(self, model: type[DomainModel]) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS total FROM objects WHERE assessment_id = ? AND object_type = ?",
            (self.assessment_id, model.stored_type),
        ).fetchone()
        return int(row["total"])

    def delete(self, model: type[DomainModel], object_id: str) -> bool:
        """Delete one object this assessment owns, returning whether a row was removed.

        Scoped like every read: the `WHERE assessment_id = ?` clause cannot reach another
        assessment's rows. The identifier counter is deliberately untouched -- an identifier once
        allocated is never re-minted (DEC-018), so deleting `run-002` must not let a later run
        become a second `run-002`. Built for `trace runs prune` (DEC-017 amendment); nothing else
        deletes single rows.
        """
        with self.transaction():
            removed = self._connection.execute(
                "DELETE FROM objects WHERE assessment_id = ? AND object_type = ? AND id = ?",
                (self.assessment_id, model.stored_type, object_id),
            ).rowcount
        return removed > 0

    def delete_all(self) -> int:
        """Delete every row this assessment owns -- its objects and its identifier counters -- in
        one transaction, and return how many objects were removed.

        Scoped like every other operation here: the `WHERE assessment_id = ?` clauses cannot reach
        another assessment's rows, which is what makes a per-assessment purge safe where `reset`
        (which removes the whole data root) is not. The counters go too, so a re-created assessment
        of the same identifier starts numbering from one rather than continuing a deleted run's.
        """
        with self.transaction():
            removed = self._connection.execute(
                "DELETE FROM objects WHERE assessment_id = ?", (self.assessment_id,)
            ).rowcount
            self._connection.execute(
                "DELETE FROM identifier_counters WHERE assessment_id = ?", (self.assessment_id,)
            )
        return int(removed)

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
                self.assessment_id,
                object_id,
                model.__name__,
                str(error),
                written_by=self._store.trace_version,
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
