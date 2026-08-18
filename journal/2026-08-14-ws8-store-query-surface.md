# WS8: store query surface, evidence-index caching, and a purge command

Eighth workstream of the robustness program (#449), the first of phase 4 (scalability). It carries a
decision-log entry (DEC-089) for the new command surface and a `SCHEMA_VERSION` bump. Three scale
limits, all masked by the small ForgeFlow scenario and surfacing at benchmark scale.

## What changed

**Identifier ordering no longer breaks past 999.** `objects` gained a `seq` column: a monotonic
insert order, assigned once and never moved by a replacement. `list`/`iterate`/`ids` order by it.
Sorting on the `id` text put `evd-1000` before `evd-999` (DEC-018 widens rather than wraps), which
silently reordered a moderate corpus and, because DEC-018 assigns identifiers in iteration order on
a rerun, changed which identifier attached to which object. The driver's `_sorted_by_id` is now keyed
on the identifier's number. The column is a table-layout change, so `SCHEMA_VERSION` moves to 2 and a
v1 database is refused rather than migrated (DEC-020) — the data root is gitignored and regenerable.
Populating `seq` is one atomic statement (`(SELECT COALESCE(MAX(seq),0)+1 FROM objects)`); writers
are serialized (WS2's `BEGIN IMMEDIATE`), so there is no race.

**An id-only read path.** `AssessmentRepository.ids(model, *, status=None)` returns identifiers over
the `id` column without parsing or validating a payload; `iterate()` yields validated objects one at
a time; `list_where(model, "status", value)` queries the one lifted column. The driver's evidence-id
reads — handed to an agent six times a run, never the evidence text — use `ids()`. (`ids`/`list_where`
are defined before the `list` method so their `list[...]` return annotations resolve to the builtin,
not the method that shadows it in class scope.)

**`EvidenceIndex` caches within one operation.** It memoizes the source documents it resolves and the
source files it reads, and lists the reference set once. `verify_all` over K references into one
document read that file K times; it now reads each source once. The critical-review phase built a
fresh index per threat, throwing the cache away — one index now serves the whole phase.

**Nothing shrank the store; now `trace assessment purge <id>` does.** It deletes one assessment's
rows, its identifier counters, and its directory — scoped, where `reset` removes the whole data root.
Destructive, so it follows `reset`'s shape: a dry run without `--force` previews and refuses (exit 3,
DEC-088). Rows go first in one transaction, then the directory. A retention cap keeps only the most
recent failed-attempt artifacts per assessment, which otherwise grew unbounded (one file per retry).

## Tests

`list`/`ids` return insert order not lexical (src-999 before src-1000); a replacement keeps its
position; `ids` returns even a row whose payload no longer parses (proving it does not validate);
`delete_all` removes one assessment and leaves others, resetting the counter; `verify_all` reads each
source file once (a spy on `artifacts.read`); `purge` removes one assessment's rows and directory and
nothing else's, with a dry-run refusal exiting 3. Full suite green (3718); ForgeFlow replay
byte-for-byte; scorecard/comparison/ablation unchanged.

## Open next

WS9 (#450, CI cost and blind spots) is the next scalability workstream — it also depends on WS12's
packaging fix for the wheel-smoke step.
