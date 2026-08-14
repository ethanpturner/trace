# WS2: store transactionality and durability

Second workstream of the robustness program (#443), phase 1. The exploration reproduced two of
these against the real store, so they are corrected with regression tests that replay the exact
reproduction.

## What changed, in `infrastructure/database/store.py`

**Nested transactions are real, via savepoints, and a swallowed inner failure dooms the outer.**
`transaction()` tracked only a depth counter and called `self._connection.rollback()` on any
failure -- which rolls back the *whole* connection, not the inner unit. The reproduction: an outer
transaction allocates `thr-001`, an inner one allocates `thr-002` and raises, the caller swallows
the exception, and the next allocation returns `thr-001` again -- two live objects with one
identifier, DEC-018's core invariant broken, and `save`'s upsert silently replacing the first row.

The outermost `transaction()` now opens `BEGIN IMMEDIATE`; each nested one opens a `SAVEPOINT`. An
inner failure rolls back only its savepoint but sets a `_transaction_doomed` flag, and the
outermost commit refuses when doomed -- rolling the whole unit back and raising `StoreError` rather
than persisting a partial result. I chose doom-the-outer over plain savepoint semantics (where the
outer could still commit the surviving work) because DEC-018 allocates *inside* the transaction: a
partial commit after a nested abort is exactly how an identifier gets handed out twice. Normal
nesting where the inner succeeds is unchanged -- it releases the savepoint and commits with the
outer.

**One connection, one transaction scope, enforced.** Because repositories share the store's
connection, an open transaction on assessment A used to absorb assessment B's writes -- discarded if
A rolled back. `allocate` and `save` (and `transaction`) now refuse a write from an assessment other
than the one whose transaction is open, naming both. The connection moved to
`isolation_level=None` (autocommit) so this module owns BEGIN/SAVEPOINT/COMMIT/ROLLBACK explicitly
rather than fighting Python's implicit BEGIN, which cannot coexist with savepoints.

**`allocate` is one statement.** The SELECT-then-upsert read-modify-write became a single
`INSERT ... ON CONFLICT DO UPDATE SET next_number = next_number + 1 RETURNING next_number - 1`, so
two connections (a run and the view server) cannot read the same counter and mint the same
identifier; `BEGIN IMMEDIATE` plus a `busy_timeout` PRAGMA serializes the cross-process case, and
`sqlite3.Error` joined the CLI's expected errors so lock contention is a message, not a traceback.

**Schema refusal happens before any write, and the connection no longer leaks.** The version check
moved ahead of `executescript` (the old order ran `CREATE TABLE IF NOT EXISTS` against a database it
was about to declare unreadable), `__init__` closes the connection on any failure (the raise means
`__exit__` never runs), and a malformed non-integer version is now an `IncompatibleSchemaError`
rather than a bare `ValueError`.

**Owner-only permissions.** A new `infrastructure/filesystem/permissions.py` holds `mkdir_owner_only`
(walks and creates each missing ancestor at 0o700, since `mkdir(parents=True, mode=...)` tightens
only the leaf) and `restrict_to_owner` (chmods the database and its `-wal`/`-shm` companions to
0o600). Both the store and the artifact store use it; the database and every directory under the
data root are now owner-only, where the exploration measured 0o755 and 0o644.

## Tests

Added to `test_store.py`: the doomed-nesting reproduction, a propagated nested failure, successful
nesting, the cross-assessment write refusal, a two-connection allocation race, a malformed schema
version, connection-close-on-refusal (a small tracking-connection proxy asserts the schema was not
created and the connection was closed once), and database/root permissions. Extended
`test_artifact_store.py`'s permissions test to the ancestors. Full suite green; the hash-checked
ForgeFlow replay reproduces byte-for-byte, confirming the transaction rewrite did not change
pipeline output.

## Open next

WS3 (#444, workflow crash-safety) depends on this -- its orchestrator fixes assume transactions
behave, which they now do. The pause path (`_persist_pause`) opens a transaction that runs the
`begin_review` callback which opens a nested one; both are same-assessment, so the new scope guard
and savepoints handle them without change.
