# 2026-08-15 — Ranked evidence selection (#451, part 1)

The second of #451's three levers (the unified budget landed as WS10; prompt caching follows). This
one makes a budget overflow drop the *lowest-signal* excerpts rather than whichever sorted last.

## The change

Before this, when the untrusted region overflowed, the fill dropped whatever came last in ingestion
order — arbitrary, and worst on a large corpus where the dropped passages are simply the ones that
sort last. `budget.rank_excerpts` now orders excerpts before the fill: the documents the structured
input names as primary (`documentation.primary_documents`) come first, and the rest keep their
ingestion order (which is document-then-position). The order within each tier is preserved, so a
package with no priority documents, or one that does not overflow, renders exactly what it did
before. The context extractor — the one package that receives structured input — applies it and
records the basis (`ranking_basis`) in its metadata, so an exclusion is explicable.

The other packages have no structured input to rank by, and their ingestion order is already
document-then-position, so they are unchanged; ranking there would be a no-op.

## Replay safety

`DeterministicModel` matches recorded responses by schema and order, not by prompt text, so
reordering the excerpts in the prompt does not change what it returns — the ForgeFlow replay canary
is byte-for-byte unchanged and the scorecard/comparison/ablation checks stay current. (This also
means the WS10 deferral of ranking was more cautious than it needed to be: the reorder was always
replay-safe. It waited for #461 only because the *caching* lever's offline cache-token test needs
the envelope, and the two were bundled.)

## Verification

`ruff` / `ruff format` / `mypy` (strict) clean. Full suite 3809 passed. Replay canary byte-for-byte
(`sha256:63b3a83a…`). New tests: `rank_excerpts` (identity without priority, primary-first with
order preserved within tiers, overflow drops the non-primary excerpt) and two extractor tests
(primary documents ranked first; basis recorded).

## Open next

The last #451 lever — prompt caching (the `cache_control` the adapter declares but never sends) —
next, now unblocked by #461. Then the two minor #452 gaps.
